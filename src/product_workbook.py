"""Two-sheet Overview/Details workbook writer per the Misumi canon contract
(exact 23-column Overview A:W, row-aligned Details, neutral category banding,
green gradient on the composite-score column only)."""

from __future__ import annotations

import io
import zipfile
from typing import Any, Dict, List

from src.product_research import sort_records

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
]

GBP = "£"


def _esc(text: Any) -> str:
    t = "".join(ch for ch in str(text) if ch >= " " or ch in "\t\n")
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
    """scored_sorted: output of product_research.sort_records."""
    categories = []
    for rec, _f, _s in scored_sorted:
        if rec["category"] not in categories:
            categories.append(rec["category"])
    band = {c: "F2F2F2" if i % 2 else "FFFFFF" for i, c in enumerate(categories)}

    fills = [("none", "00000000"), ("gray125", "00FF0000")]
    def add_fill(rgb):
        fills.append(("solid", "00" + rgb))
        return len(fills) - 1
    F_HDR = add_fill("DCE6F1")
    F_BAND = {c: add_fill(band[c]) for c, v in band.items()}
    F_LOW = add_fill("E8F5E9")   # gradient low end (green, light)
    F_HIGH = add_fill("2E7D32")  # gradient high end (green, deep)

    XFS = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
           '<alignment wrapText="1" vertical="top"/></xf>']
    def xf(fill_id=None, numfmt=None):
        a = ' applyNumberFormat="1"' if numfmt else ""
        fl = ' applyFill="1"' if fill_id is not None else ""
        XFS.append(f'<xf numFmtId="{164 if numfmt else 0}" fontId="0" '
                   f'fillId="{fill_id if fill_id is not None else 0}" borderId="0" xfId="0"{fl}{a} '
                   'applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>')
        return len(XFS) - 1
    S_TEXT = 0
    S_HDR = xf(F_HDR)
    S_BAND = {c: xf(fid) for c, fid in F_BAND.items()}
    S_MONEY = xf(numfmt=True)
    numfmts_xml = ('<numFmts count="1">'
                   '<numFmt numFmtId="164" formatCode="&quot;&#163;&quot;0.00"/>'
                   '</numFmts>')

    # green gradient per score decile (light -> deep green), score column only
    GRAD = []
    for level in range(10):
        rgb = ("_E8" if False else
               "%02X%02X%02X" % (0xE8 - level * 0x11, 0xF5 - level * 0x08, 0xE9 - level * 0x70))
        GRAD.append(xf(add_fill(rgb)))

    def score_style(score: float) -> int:
        return GRAD[min(9, int(score * 10))]

    main = []
    details = []

    def row_of(values, styles):
        return list(zip(values, styles))

    # header rows
    main.append([(h, S_HDR) for h in OVERVIEW_COLUMNS])
    details.append([(h, S_HDR) for h in DETAIL_COLUMNS])

    for rec, factors, score in scored_sorted:
        opts = rec.get("overview_options") or []
        status = f"{rec.get('buying_status', 'unknown')} (snapshot {snapshot_date})"
        vals = [
            rec["category"], rec["product_name"], rec.get("store_description") or rec.get("product_name", ""),
            score["percent"], rec.get("combined_rating"), rec.get("combined_popularity_index"),
            rec.get("unit_price"), rec.get("leafly_thc"), rec.get("sativa_pct"), rec.get("indica_pct"),
        ]
        styles = [S_BAND[rec["category"]], S_BAND[rec["category"]], S_BAND[rec["category"]],
                  score_style(score["score"]), S_TEXT, S_TEXT, S_MONEY,
                  S_TEXT, S_TEXT, S_TEXT]
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
            rec.get("raw_options"), score["percent"],
            str({k: v for k, v in dict(grade=factors.grade, rating=factors.rating,
                 price=factors.price, thc=factors.thc, si=factors.si,
                 popularity=factors.popularity).items() if v is not None}),
            score["weights_used"], "; ".join(score["missing_applicable"]),
            score["missing_penalty"], score["gamma"], score["gm"], score["b"], score["c"],
            str((factors.detail or {}).get("popularity", {})),
            rec.get("match_classification") or "", rec.get("primary_leafly_source") or "",
        ]
        details.append([(v, S_TEXT) for v in dvals])

    def sheet_xml(rows, freeze=True):
        rxs = []
        for rno, cells in enumerate(rows, start=1):
            cs = []
            for ci, (val, style) in enumerate(cells):
                ref = f"{_col(ci)}{rno}"
                if val is None or val == "":
                    cs.append(f'<c r="{ref}" s="{style}"/>')
                elif isinstance(val, (int, float)) and not isinstance(val, bool):
                    cs.append(f'<c r="{ref}" s="{style}"><v>{val}</v></c>')
                else:
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
                f'<sheetData>{"".join(rxs)}</sheetData></worksheet>')

    s1, s2 = sheet_xml(main), sheet_xml(details)
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
                   + numfmts_xml +
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
