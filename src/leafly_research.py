"""Deterministic Leafly cultivar-research workbook and provenance builder.

Backs the operator's 76-row investigation inventory
(``automation/review/source-data/2026-10-24-leafly-76-research.csv``).

Scope is deliberately narrow (task card
``2026-10-24-leafly-cultivar-reference-enrichment``):

- neutral, source-grounded descriptive research only;
- advertised package/price comparison columns are colour-coded, clearly
  labelled scaffolding that stays blank until the operator supplies verified
  observations (operator authorisation 2026-10-24). Nothing here invents,
  scrapes or estimates prices, quantities, stock or availability;
- no retailer credentials, ordering links or purchase recommendations.

The XLSX writer is a small stdlib (zipfile) implementation so neither the
runtime nor CI needs openpyxl for this read-only research artifact.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = (
    REPO_ROOT / "automation" / "review" / "source-data"
    / "2026-10-24-leafly-76-research.csv"
)

SOURCE_NAME = "leafly_cultivar_research"
EXPECTED_ROW_COUNT = 76

# Columns rendered after the verified research columns. Each advertised
# package option gets its own colour-coded column; price-comparison columns
# stay blank until verified data is supplied by the operator.
OPTION_COLUMNS = [
    "Advertised package option 1 (stated amount)",
    "Advertised package option 2 (stated amount)",
    "Advertised package option 3 (stated amount)",
]
PRICE_COLUMNS = [
    "Usual price (verified only)",
    "Advertised price (verified only)",
    "Difference vs usual (verified only)",
]
SCAFFOLD_NOTE = (
    "Blank by design: filled only from operator-verified observations. "
    "Never estimated or scraped."
)

# Muted, distinct header fills for the option/price scaffold columns.
_COLUMN_FILLS = {
    OPTION_COLUMNS[0]: "D9E2F2",
    OPTION_COLUMNS[1]: "DDEBD8",
    OPTION_COLUMNS[2]: "F2E6D9",
    PRICE_COLUMNS[0]: "E8E2EF",
    PRICE_COLUMNS[1]: "E2EFEF",
    PRICE_COLUMNS[2]: "EFE2E2",
}

_HEADER_FILL = "DCE6F1"


class LeaflyResearchValidationError(ValueError):
    """Raised when the research CSV violates the task-card invariants."""


def load_inventory(csv_path: str | Path = DEFAULT_CSV_PATH) -> List[Dict[str, str]]:
    """Parse and validate the research CSV into normalized row dicts."""
    path = Path(csv_path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            {k: (v or "").strip() for k, v in row.items() if k is not None}
            for row in reader
        ]
    _validate(rows, source=str(path))
    return rows


def _validate(rows: List[Dict[str, str]], *, source: str) -> None:
    if len(rows) != EXPECTED_ROW_COUNT:
        raise LeaflyResearchValidationError(
            f"{source}: expected {EXPECTED_ROW_COUNT} rows, found {len(rows)}"
        )
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):  # header is line 1
        name = row.get("product_name", "")
        description = row.get("leafly_description", "")
        if not name:
            raise LeaflyResearchValidationError(f"{source}:{index}: missing product_name")
        if name in seen:
            raise LeaflyResearchValidationError(
                f"{source}:{index}: duplicate product_name {name!r}"
            )
        seen.add(name)
        if not description:
            raise LeaflyResearchValidationError(
                f"{source}:{index}: {name!r} has no description; use an explicit "
                "'no reliable match' statement instead of leaving it empty"
            )
        if not row.get("evidence_classification"):
            raise LeaflyResearchValidationError(
                f"{source}:{index}: {name!r} missing evidence_classification"
            )
        for key in ("primary_leafly_source", "additional_leafly_source"):
            url = row.get(key, "")
            if url and not url.startswith(("http://", "https://")):
                raise LeaflyResearchValidationError(
                    f"{source}:{index}: {name!r} {key} is not an http(s) URL"
                )


def revision_hash(row: Dict[str, str]) -> str:
    """Stable content hash for one inventory row (card field ``revision_hash``)."""
    material = "\n".join(
        row.get(key, "") for key in (
            "category", "product_name", "leafly_description",
            "closest_leafly_reference", "evidence_classification",
            "primary_leafly_source", "additional_leafly_source",
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def ingest_provenance(rows: List[Dict[str, str]]) -> Dict[str, int]:
    """Record each row through the neutral SourceEvent contract. Idempotent.

    The SourceEvent content is the name plus its source-grounded description;
    metadata carries the match classification and Leafly references. A second
    identical run is a no-op per row (record_source_event contract).
    """
    from core.database import SourceEvent, get_db_session
    from src.source_events import record_source_event

    with get_db_session() as db:
        before = (
            db.query(SourceEvent)
            .filter(SourceEvent.source == SOURCE_NAME)
            .count()
        )
    for row in rows:
        record_source_event(
            SOURCE_NAME,
            row["product_name"],
            f"{row['product_name']}\n{row['leafly_description']}",
            metadata={
                "category": row.get("category", "unknown"),
                "closest_leafly_reference": row.get("closest_leafly_reference", ""),
                "evidence_classification": row.get("evidence_classification", ""),
                "primary_leafly_source": row.get("primary_leafly_source", ""),
                "additional_leafly_source": row.get("additional_leafly_source", ""),
                "revision_hash": revision_hash(row),
                "csv_path": str(DEFAULT_CSV_PATH.relative_to(REPO_ROOT)),
            },
        )
    with get_db_session() as db:
        after = (
            db.query(SourceEvent)
            .filter(SourceEvent.source == SOURCE_NAME)
            .count()
        )
    return {
        "rows": len(rows),
        "events_before": before,
        "events_after": after,
        "created_on_this_run": after - before,
    }


def retrieval_records(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Read-only lookup records for the retrieval surface (no invented fields)."""
    records: List[Dict[str, Any]] = []
    for row in rows:
        records.append({
            "category": row.get("category", "unknown"),
            "product_name": row.get("product_name", ""),
            "leafly_description": row.get("leafly_description", ""),
            "closest_leafly_reference": row.get("closest_leafly_reference", ""),
            "match_classification": row.get("evidence_classification", ""),
            "primary_leafly_source": row.get("primary_leafly_source", ""),
            "additional_leafly_source": row.get("additional_leafly_source", ""),
            "revision_hash": revision_hash(row),
        })
    return records


# ---------------------------------------------------------------------------
# Minimal stdlib XLSX writer (inline strings + flat header fills only)
# ---------------------------------------------------------------------------

def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _col_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def build_workbook(rows: List[Dict[str, str]]) -> bytes:
    """Render the validated rows as a colour-coded XLSX workbook (bytes).

    Layout (requirement: product name immediately beside its description):
      A category | B product_name | C leafly_description | D classification
      E closest reference | F primary source | G additional source
      H-J advertised package options (colour-coded, blank)
      K-M verified price comparison (colour-coded, blank)
    """
    header = [
        "Category", "Product name", "Leafly description", "Match classification",
        "Closest Leafly reference", "Primary Leafly source",
        "Additional Leafly source",
    ] + OPTION_COLUMNS + PRICE_COLUMNS

    fills: list[tuple[str, str]] = [("none", "00000000"), ("gray125", "00FF0000")]
    fill_index: Dict[str, int] = {}
    for colour in {*_COLUMN_FILLS.values(), _HEADER_FILL}:
        fills.append(("solid", f"00{colour}"))
        fill_index[colour] = len(fills) - 1

    xfs: list[str] = []
    header_style: Dict[str, int] = {}
    for colour in {*_COLUMN_FILLS.values(), _HEADER_FILL}:
        xfs.append(
            '<xf numFmtId="0" fontId="0" fillId="%d" borderId="0" xfId="0" '
            'applyFill="1" applyAlignment="1"><alignment wrapText="1" '
            'vertical="top"/></xf>' % fill_index[colour]
        )
        header_style[colour] = len(xfs) - 1
    body_style = len(xfs)
    xfs.append(
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" '
        'applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>'
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        f'<fills count="{len(fills)}">'
        + "".join(
            (
                '<fill><patternFill patternType="none"/></fill>'
                if kind == "none"
                else '<fill><patternFill patternType="gray125"/></fill>'
                if kind == "gray125"
                else f'<fill><patternFill patternType="solid"><fgColor rgb="{value}"/>'
                     '<bgColor indexed="64"/></patternFill></fill>'
            )
            for kind, value in fills
        )
        + "</fills>"
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f'<cellXfs count="{len(xfs)}">' + "".join(xfs) + "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )

    def cell(ref: str, text: str, style: Optional[int] = None) -> str:
        attrs = f' s="{style}"' if style is not None else ""
        return (
            f'<c r="{ref}"{attrs} t="inlineStr"><is>'
            f"<t xml:space=\"preserve\">{_xml_escape(text)}</t></is></c>"
        )

    row_xml: list[str] = []
    # Header row with per-column fills.
    cells = []
    for col, title in enumerate(header):
        colour = _HEADER_FILL
        for key, styled in _COLUMN_FILLS.items():
            if title == key:
                colour = styled
                break
        cells.append(cell(f"{_col_letter(col)}1", title, header_style[colour]))
    row_xml.append(f'<row r="1">{"".join(cells)}</row>')

    for r, row in enumerate(rows, start=2):
        values = [
            row.get("category", ""), row.get("product_name", ""),
            row.get("leafly_description", ""), row.get("evidence_classification", ""),
            row.get("closest_leafly_reference", ""), row.get("primary_leafly_source", ""),
            row.get("additional_leafly_source", ""),
        ] + [""] * (len(OPTION_COLUMNS) + len(PRICE_COLUMNS))
        cells = []
        for col, value in enumerate(values):
            if value:
                cells.append(cell(f"{_col_letter(col)}{r}", value, body_style))
            else:
                cells.append(f'<c r="{_col_letter(col)}{r}" s="{body_style}"/>')
        row_xml.append(f'<row r="{r}">{"".join(cells)}</row>')

    last_col = _col_letter(len(header) - 1)
    last_row = len(rows) + 1
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<dimension ref="A1:{last_col}{last_row}"/>'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        f'<autoFilter ref="A1:{last_col}{last_row}"/>'
        "</worksheet>"
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Leafly76" sheetId="1" '
        'r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()
