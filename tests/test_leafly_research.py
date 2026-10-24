"""Tests for the Leafly 76-row cultivar-research builder and its contract.

Covers: count invariant, name-beside-description layout, no fabricated
values, colour-coded blank scaffold columns, and idempotent SourceEvent
provenance. The repo's real research CSV is the primary fixture; a small
synthetic fixture covers validation failures.
"""
import os
import zipfile
from io import BytesIO
from xml.etree import ElementTree

import pytest

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

from src.leafly_research import (
    DEFAULT_CSV_PATH,
    EXPECTED_ROW_COUNT,
    LeaflyResearchValidationError,
    build_workbook,
    ingest_provenance,
    load_inventory,
    retrieval_records,
)

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


@pytest.fixture()
def rows():
    return load_inventory()


def test_inventory_has_exactly_76_rows(rows):
    assert len(rows) == EXPECTED_ROW_COUNT == 76


def test_every_row_has_description_and_classification(rows):
    for row in rows:
        assert row["product_name"]
        assert row["leafly_description"], row["product_name"]
        assert row["evidence_classification"], row["product_name"]


def test_source_urls_are_http_or_empty(rows):
    for row in rows:
        for key in ("primary_leafly_source", "additional_leafly_source"):
            assert not row[key] or row[key].startswith(("http://", "https://"))


def test_product_name_is_immediately_beside_description(rows):
    workbook = build_workbook(rows)
    sheet = _sheet_rows(workbook)
    header = _row_texts(sheet[0])
    assert header.index("Product name") == header.index("Leafly description") - 1


def _sheet_rows(workbook_bytes):
    with zipfile.ZipFile(BytesIO(workbook_bytes)) as archive:
        xml = archive.read("xl/worksheets/sheet1.xml")
    root = ElementTree.fromstring(xml)
    return root.find(f"{_NS}sheetData").findall(f"{_NS}row")


def _row_texts(row):
    return [
        "".join(t.text or "" for t in cell.iter(f"{_NS}t"))
        for cell in row.findall(f"{_NS}c")
    ]


def _row_refs(row):
    return [cell.attrib["r"] for cell in row.findall(f"{_NS}c")]


def _header_fill_map(workbook_bytes):
    """Map header-cell value -> fill style index from styles.xml."""
    with zipfile.ZipFile(BytesIO(workbook_bytes)) as archive:
        styles = ElementTree.fromstring(archive.read("xl/styles.xml"))
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    fills = styles.find(f"{_NS}fills").findall(f"{_NS}fill")
    def fill_rgb(index):
        rgb = fills[index].find(f"{_NS}patternFill/{_NS}fgColor")
        return rgb.attrib.get("rgb") if rgb is not None else None
    header = sheet.find(f"{_NS}sheetData").findall(f"{_NS}row")[0]
    mapping = {}
    for cell in header.findall(f"{_NS}c"):
        style = int(cell.attrib.get("s", "0"))
        text = "".join(t.text or "" for t in cell.iter(f"{_NS}t"))
        mapping[text] = fill_rgb(style)
    return mapping


def test_option_columns_are_colour_coded_and_blank(rows):
    workbook = build_workbook(rows)
    sheet = _sheet_rows(workbook)
    header = _row_texts(sheet[0])
    option_indexes = [
        i for i, t in enumerate(header)
        if t.startswith("Advertised package option")
    ]
    assert len(option_indexes) == 3
    # Each advertised option column has its own distinct header colour.
    fills = _header_fill_map(workbook)
    option_colours = {
        fills[t] for t in header if t.startswith("Advertised package option")
    }
    assert len(option_colours) == 3
    # Every body cell under the option and verified-price columns is empty.
    from src.leafly_research import OPTION_COLUMNS, PRICE_COLUMNS
    blank_headers = set(OPTION_COLUMNS) | set(PRICE_COLUMNS)
    blank_indexes = {header.index(t) for t in blank_headers}
    letters = [chr(ord("A") + i) for i in sorted(blank_indexes)]
    for row in sheet[1:]:
        refs = _row_refs(row)
        for letter in letters:
            for ref in refs:
                if ref.startswith(letter) and ref[len(letter):].isdigit():
                    cell = row.findall(f"{_NS}c")[refs.index(ref)]
                    assert not "".join(
                        t.text or "" for t in cell.iter(f"{_NS}t")
                    ), f"scaffold column cell {ref} must stay blank"


def test_no_invented_price_or_quantity_values(rows):
    """The research payload itself carries no price/quantity/stock offers."""
    import re
    price_pattern = re.compile(r"[£$]\s?\d|\d+\s?(?:oz|euros?|pounds?)", re.I)
    for row in rows:
        blob = " ".join(row.values())
        assert not price_pattern.search(blob), (
            f"price-like value in research fields for {row['product_name']!r}"
        )


def test_workbook_is_a_valid_zip_with_one_sheet(rows):
    workbook = build_workbook(rows)
    with zipfile.ZipFile(BytesIO(workbook)) as archive:
        names = archive.namelist()
        assert "xl/workbook.xml" in names
        assert "xl/styles.xml" in names
        sheet = archive.read("xl/worksheets/sheet1.xml")
    assert b"<row r=\"77\"" in sheet  # header + 76 rows


def test_repeated_build_is_deterministic(rows):
    assert build_workbook(rows) == build_workbook(rows)


def test_invalid_csv_rejected(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "category,product_name,leafly_description,evidence_classification,"
        "primary_leafly_source,additional_leafly_source\n"
        "Cannabis flower,Only One,,\n",
        encoding="utf-8",
    )
    with pytest.raises(LeaflyResearchValidationError):
        load_inventory(bad)


def test_duplicate_names_rejected(tmp_path):
    header = ("category,product_name,leafly_description,"
              "evidence_classification,primary_leafly_source,"
              "additional_leafly_source\n")
    row = ("Cannabis flower,Same Name,desc,exact,"
           "https://www.leafly.com/strains/same-name,\n")
    bad = tmp_path / "dup.csv"
    bad.write_text(header + row + row, encoding="utf-8")
    with pytest.raises(LeaflyResearchValidationError):
        load_inventory(bad)


# ---------------------------------------------------------------------------
# Provenance (SourceEvent) idempotency — isolated database per test
# ---------------------------------------------------------------------------

@pytest.fixture()
def _isolated_database(monkeypatch):
    clear_fake_database_modules()
    import core.database as cdb
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    yield
    engine.dispose()
    os.unlink(tmpfile.name)


def _cleanup():
    from core.database import SourceEvent, get_db_session
    with get_db_session() as db:
        db.query(SourceEvent).filter(
            SourceEvent.source == "leafly_cultivar_research"
        ).delete(synchronize_session=False)


@pytest.fixture()
def _clean_rows(_isolated_database):
    _cleanup()
    yield
    _cleanup()


def test_provenance_ingest_is_idempotent(rows, _clean_rows):
    first = ingest_provenance(rows)
    assert first["events_before"] == 0
    assert first["events_after"] == 76
    assert first["created_on_this_run"] == 76
    second = ingest_provenance(rows)
    assert second["events_after"] == 76
    assert second["created_on_this_run"] == 0


def test_provenance_records_carry_sources(rows, _clean_rows):
    ingest_provenance(rows)
    from core.database import SourceEvent, get_db_session
    with get_db_session() as db:
        event = (
            db.query(SourceEvent)
            .filter(
                SourceEvent.source == "leafly_cultivar_research",
                SourceEvent.external_id == "Black Truffle AA+",
            )
            .one()
        )
        payload_ref = event.payload_ref
    assert payload_ref is not None
    assert "black-truffle" in payload_ref
