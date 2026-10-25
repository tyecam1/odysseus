"""Two-sheet Overview/Details workbook writer per the Misumi canon contract
(exact 23-column Overview A:W, row-aligned Details, neutral category banding,
green gradient on the composite-score column only)."""

from __future__ import annotations

import io
import json
import math
import zipfile
from typing import Any, Dict, List

from src.product_research import CANON_REF, SCORING_METHODOLOGY

OVERVIEW_COLUMNS = [
    "Category", "Title", "Green Team description", "Composite score (%)",
    "Combined rating / 5", "Combined popularity index / 100",
    "Minimum price per quantity", "Leafly THC (%)", "Sativa (%)", "Indica (%)",
    "Size 1", "Price 1", "Size 2", "Price 2", "Size 3", "Price 3",
    "Size 4", "Price 4", "Size 5", "Price 5", "Size 6", "Price 6",
    "Buying status (snapshot date)",
]
DETAIL_COLUMNS = [
    "Product key", "Category", "Title", "Buying status", "Seller URL",
    "Fetched (UTC)", "Green Team description (full)", "Leafly description",
    "Seller tier (reported)", "Inferred grade (rarity estimate)",
    "Inferred grade confidence", "Leafly rating", "Leafly rating count",
    "Seller rating", "Seller review count", "Seller popularity rank (ordinal)",
    "Unit price (min, GBP)", "Unit basis", "All advertised options (raw)",
    "Composite score (%)", "Normalized factors", "Factor weights used",
    "Missing applicable metrics", "Missing penalty", "Gamma", "GM", "B", "C",
    "Excluded price options", "Match classification", "Primary Leafly source",
    "Factor evidence and peer groups (JSON)", "Scoring methodology (JSON)",
    "Field dictionary (JSON)", "Raw record JSON part 1",
]

FIELD_DICTIONARY = {
    "Composite score (%)": "Relative comparison, not quality certainty; stored on a 0..1 scale",
    "Leafly THC (%)": "Cultivar reference THC, not a batch measurement; source percentage points",
    "Sativa (%) / Indica (%)": "Stated source orientation in percentage points, not measured effects",
    "Unit price": "Minimum defensible price per stated unit; compare category AND unit basis only",
    "Inferred grade": "Injected estimate with confidence/provenance, distinct from seller-reported tier",
    "Normalized factors": "Category-relative multipliers; 1 is neutral; absent is not zero",
    "Factor evidence and peer groups (JSON)": "Raw factor inputs, confidence, peer vectors and source pointers",
    "Raw record JSON parts": "Concatenate numbered parts in this row, then decode JSON for ALL input fields, variants and source metadata",
    "Text exceeding a cell limit": "Display preview is labelled; full value retained in raw record JSON parts",
}

JSON_CHUNK_SIZE = 30000  # below Excel's 32767-character cell text limit


def _json(value: Any) -> str:
    # ASCII escapes also preserve control characters that XML cannot represent.
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _esc(text: Any) -> str:
    t = "".join(ch for ch in str(text)
                if ch in "\t\n\r" or " " <= ch <= "\ud7ff" or "\ue000" <= ch <= "\ufffd"
                or "\U00010000" <= ch <= "\U0010ffff")
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def build_workbook(scored_sorted, snapshot_date: str) -> bytes:
    """Return XLSX bytes; never opens or overwrites a user's workbook.

    scored_sorted is the output of product_research.sort_records. All records
    must be JSON-serializable; unsupported values fail explicitly.
    """
    scored_sorted = list(scored_sorted)
    raw_records = [_json(rec) for rec, _, _ in scored_sorted]
    raw_parts = [[raw[i:i + JSON_CHUNK_SIZE] for i in range(0, len(raw), JSON_CHUNK_SIZE)]
                 for raw in raw_records]
    part_count = max((len(parts) for parts in raw_parts), default=1)
    detail_columns = DETAIL_COLUMNS + [f"Raw record JSON part {i}" for i in range(2, part_count + 1)]
    categories = []
    for rec, _f, _s in scored_sorted:
        if rec["category"] not in categories:
            categories.append(rec["category"])
    band = {c: "F2F2F2" if i % 2 else "FFFFFF" for i, c in enumerate(categories)}

    fills = [("none", "00000000"), ("gray125", "00FF0000")]
    def add_fill(rgb):
        fills.append(("solid", "FF" + rgb))
        return len(fills) - 1
    F_HDR = add_fill("DCE6F1")
    F_BAND = {c: add_fill(band[c]) for c, v in band.items()}

    XFS = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
           '<alignment wrapText="1" vertical="top"/></xf>']
    def xf(fill_id=None, numfmt=0):
        a = ' applyNumberFormat="1"' if numfmt else ""
        fl = ' applyFill="1"' if fill_id is not None else ""
        XFS.append(f'<xf numFmtId="{numfmt}" fontId="0" '
                   f'fillId="{fill_id if fill_id is not None else 0}" borderId="0" xfId="0"{fl}{a} '
                   'applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>')
        return len(XFS) - 1
    S_TEXT = 0
    S_HDR = xf(F_HDR)
    S_BAND = {c: xf(fid) for c, fid in F_BAND.items()}
    S_MONEY = xf(numfmt=164)
    S_PERCENT = xf(numfmt=10)  # numeric fraction, shown as 0.00%
    S_SOURCE_PERCENT = xf(numfmt=165)  # source percentage points (e.g. 25)
    numfmts = {164: '"£"0.00', 165: '0.0"%"'}
    unit_money_styles = {}

    def unit_money_style(basis):
        if basis is None or basis == "":
            return S_MONEY
        # Strip XML-invalid characters before escaping Excel literals, so a
        # removed control character cannot leave a dangling backslash.
        basis = "".join(ch for ch in str(basis) if _esc(ch))
        if basis not in unit_money_styles:
            numfmt = 164 + len(numfmts)
            # Excel's backslash quotes the next character literally, including
            # quotes, backslashes and format operators such as ; and [Red].
            numfmts[numfmt] = numfmts[164] + "".join("\\" + ch for ch in " " + basis)
            unit_money_styles[basis] = xf(numfmt=numfmt)
        return unit_money_styles[basis]

    # green gradient per score decile (light -> deep green), score column only
    GRAD = []
    for level in range(10):
        # Interpolate bounded RGB channels between two green endpoints.
        rgb = "".join(f"{round(low + (high - low) * level / 9):02X}"
                      for low, high in zip((232, 245, 233), (117, 187, 121)))
        GRAD.append(xf(add_fill(rgb), numfmt=10))

    def score_style(score: float) -> int:
        return GRAD[max(0, min(9, int(score * 10)))]

    main = []
    details = []

    def row_of(values, styles):
        return list(zip(values, styles))

    # header rows
    main.append([(h, S_HDR) for h in OVERVIEW_COLUMNS])
    details.append([(h, S_HDR) for h in detail_columns])

    for record_index, (rec, factors, score) in enumerate(scored_sorted):
        opts = rec.get("overview_options") or []
        status = f"{rec.get('buying_status', 'unknown')} (snapshot {snapshot_date})"
        vals = [
            rec["category"], rec["product_name"], rec.get("store_description") or rec.get("product_name", ""),
            score["score"], rec.get("combined_rating"), rec.get("combined_popularity_index"),
            rec.get("unit_price"), rec.get("leafly_thc"), rec.get("sativa_pct"), rec.get("indica_pct"),
        ]
        styles = [S_BAND[rec["category"]], S_BAND[rec["category"]], S_BAND[rec["category"]],
                  score_style(score["score"]), S_TEXT, S_TEXT, unit_money_style(rec.get("unit_basis")),
                  S_SOURCE_PERCENT, S_SOURCE_PERCENT, S_SOURCE_PERCENT]
        for k in range(6):
            if k < len(opts):
                vals += [opts[k].get("size"), opts[k].get("price")]
                styles += [S_TEXT, S_MONEY]
            else:
                vals += [None, None]
                styles += [S_TEXT, S_TEXT]
        vals.append(status)
        styles.append(S_TEXT)
        main.append(row_of(vals, styles))

        dvals = [
            rec.get("product_key") or rec["product_name"], rec["category"], rec["product_name"],
            rec.get("buying_status", "unknown"), rec.get("permalink") or "", rec.get("fetched") or "",
            rec.get("store_description") or "", rec.get("leafly_description") or "",
            rec.get("seller_tier") or "", (rec.get("inferred_grade") or {}).get("tier", ""),
            (rec.get("inferred_grade") or {}).get("confidence"),
            rec.get("leafly_rating"), rec.get("leafly_rating_count"),
            rec.get("seller_rating"), rec.get("seller_review_count"),
            rec.get("seller_popularity_rank"),
            rec.get("unit_price"), rec.get("unit_basis"),
            _json(rec.get("raw_options")), score["score"],
            _json({k: v for k, v in dict(grade=factors.grade, rating=factors.rating,
                 price=factors.price, thc=factors.thc, si=factors.si,
                 popularity=factors.popularity).items() if v is not None}),
            score["weights_used"], "; ".join(score["missing_applicable"]),
            score["missing_penalty"], score["gamma"], score["gm"], score["b"], score["c"],
            _json(rec.get("price_detail", {}).get("excluded_options", [])),
            rec.get("match_classification") or "", rec.get("primary_leafly_source") or "",
            _json(factors.detail), _json({"canon_ref": CANON_REF, **SCORING_METHODOLOGY}),
            _json(FIELD_DICTIONARY),
        ]
        dvals.extend(raw_parts[record_index] + [None] * (part_count - len(raw_parts[record_index])))
        dstyles = [S_TEXT] * len(dvals)
        dstyles[16], dstyles[19] = S_MONEY, S_PERCENT
        details.append(row_of(dvals, dstyles))

    def sheet_xml(rows, widths, freeze=True):
        rxs = []
        for rno, cells in enumerate(rows, start=1):
            cs = []
            for ci, (val, style) in enumerate(cells):
                ref = f"{_col(ci)}{rno}"
                if val is None or val == "":
                    cs.append(f'<c r="{ref}" s="{style}"/>')
                elif (isinstance(val, (int, float)) and not isinstance(val, bool)
                      and math.isfinite(val)):
                    cs.append(f'<c r="{ref}" s="{style}"><v>{val}</v></c>')
                else:
                    if isinstance(val, (dict, list, tuple)):
                        val = _json(val)
                    val = str(val)
                    if len(val) > JSON_CHUNK_SIZE:
                        val = val[:JSON_CHUNK_SIZE] + " [preview; full value in Details raw record JSON]"
                    cs.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is>'
                              f'<t xml:space="preserve">{_esc(val)}</t></is></c>')
            rxs.append(f'<row r="{rno}">{"".join(cs)}</row>')
        width = max((len(c) for c in rows), default=1)
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<dimension ref="A1:{_col(width - 1)}{len(rows)}"/>'
                '<sheetViews><sheetView workbookViewId="0">'
                + (f'<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>' if freeze else '')
                + '</sheetView></sheetViews>'
                + '<cols>' + ''.join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
                                     for i, w in enumerate(widths, start=1)) + '</cols>'
                f'<sheetData>{"".join(rxs)}</sheetData></worksheet>')

    overview_widths = [24, 30, 60, 20, 20, 24, 24, 18, 16, 16] + [14, 14] * 6 + [42]
    detail_widths = [24, 24, 30, 20, 40, 24, 60, 60] + [28] * (len(detail_columns) - 8)
    s1, s2 = sheet_xml(main, overview_widths), sheet_xml(details, detail_widths)
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<sheets><sheet name="Overview" sheetId="1" r:id="rId1"/>'
          '<sheet name="Details" sheetId="2" r:id="rId2"/></sheets></workbook>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          '</Types>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/styles.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   + f'<numFmts count="{len(numfmts)}">'
                   + "".join(f'<numFmt numFmtId="{numfmt}" formatCode="'
                             + _esc(code).replace("\t", "&#9;").replace("\n", "&#10;").replace("\r", "&#13;")
                             + '"/>' for numfmt, code in numfmts.items())
                   + '</numFmts>' +
                   '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
                   f'<fills count="{len(fills)}">'
                   + "".join(
                       '<fill><patternFill patternType="none"/></fill>' if k == "none"
                       else '<fill><patternFill patternType="gray125"/></fill>' if k == "gray125"
                       else f'<fill><patternFill patternType="solid"><fgColor rgb="{v}"/><bgColor indexed="64"/></patternFill></fill>'
                       for k, v in fills)
                   + '</fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                   '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                   f'<cellXfs count="{len(XFS)}">{"".join(XFS)}</cellXfs>'
                   '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        z.writestr("xl/worksheets/sheet1.xml", s1)
        z.writestr("xl/worksheets/sheet2.xml", s2)
    return buf.getvalue()
