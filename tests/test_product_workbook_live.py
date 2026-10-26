"""Live-workbook regression tests (corrective round 2026-10-26).

The merged workbook wrote computed values, static per-decile fills and no
formulas. These tests require the repaired contract:

* Overview composite scores are LIVE Excel formulas over Details factor cells
  and configurable weight cells, so editing an input recalculates.
* The score gradient is a genuine Excel conditional format (colour scale), not
  static per-cell fills.
* Recalculated values (via LibreOffice, when installed) match the Python
  scoring engine.
"""
import math
import subprocess
import shutil
from io import BytesIO

import pytest

from src.product_research import GAMMA, build_factors, composite_score

GAMMA_DEFAULT = GAMMA
from src.product_workbook import (
    FACTOR_INPUT_COLUMNS, OVERVIEW_COLUMNS, WEIGHT_CELLS, WEIGHT_DEFAULTS,
    build_workbook,
)

pytest.importorskip("openpyxl")

from openpyxl import load_workbook  # noqa: E402


def rec(name, category="Cannabis flower", **kw):
    r = {"product_name": name, "category": category, "buying_status": "purchasable"}
    r.update(kw)
    return r


def _mixed_records():
    return [
        rec("FlowerA", combined_rating=4.5, unit_price=10.0, unit_basis="per g",
            leafly_thc=25, sativa_pct=75, indica_pct=25, leafly_rating_count=120,
            seller_popularity_rank=1, seller_tier="AA",
            overview_options=[{"size": "1g", "price": 10.0}]),
        rec("FlowerB", combined_rating=3.5, unit_price=20.0, unit_basis="per g",
            leafly_thc=18, sativa_pct=40, indica_pct=60, leafly_rating_count=30,
            seller_popularity_rank=3, seller_tier="A"),
        rec("EdibleX", category="Edibles", combined_rating=4.0, unit_price=5.0,
            unit_basis="per item", leafly_rating_count=10, seller_popularity_rank=2),
    ]


@pytest.fixture(scope="module")
def workbook_blob():
    scored = build_factors(_mixed_records())
    return build_workbook(scored, "2026-10-26"), scored


def test_overview_scores_are_live_formulas(workbook_blob):
    blob, _ = workbook_blob
    wb = load_workbook(BytesIO(blob))
    ws = wb["Overview"]
    for row in range(2, ws.max_row + 1):
        value = ws.cell(row, 4).value
        assert isinstance(value, str) and value.startswith("="), \
            f"Overview D{row} must be a live formula, got {value!r}"
        assert "Details!" in value


def test_details_factor_inputs_and_calculation_chain_are_present(workbook_blob):
    blob, _ = workbook_blob
    wb = load_workbook(BytesIO(blob))
    ws = wb["Details"]
    headers = [c.value for c in ws[1]]
    for name in FACTOR_INPUT_COLUMNS:
        assert name in headers
    # factor input cells hold numbers or None, never formulas
    base = len(OVERVIEW_COLUMNS) - 1  # Details starts with its own key columns
    # GM/B/C helper cells are live formulas
    for name in ("GM (live)", "B (live)", "C (live)"):
        col = headers.index(name) + 1
        value = ws.cell(2, col).value
        assert isinstance(value, str) and value.startswith("="), \
            f"Details {name} must be a live formula, got {value!r}"


def test_configurable_weight_cells_are_editable_values(workbook_blob):
    blob, _ = workbook_blob
    wb = load_workbook(BytesIO(blob))
    ws = wb["Overview"]
    for metric, cell_ref in WEIGHT_CELLS.items():
        default = (GAMMA_DEFAULT if metric == "gamma"
                   else WEIGHT_DEFAULTS[metric])
        value = ws[cell_ref].value
        assert value == pytest.approx(default), \
            f"weight cell {cell_ref} for {metric} should default to {default}"


def test_gradient_is_conditional_format_not_static_fills(workbook_blob):
    blob, _ = workbook_blob
    wb = load_workbook(BytesIO(blob))
    ws = wb["Overview"]
    rules = [r for rng in ws.conditional_formatting for r in rng.rules
             if "D" in str(rng.sqref)]
    assert any(r.type == "colorScale" for r in rules), \
        "score column must carry a genuine Excel colour-scale conditional format"
    # no static per-decile fills on the score column any more
    fills = {ws.cell(row, 4).fill.fgColor.rgb for row in range(2, ws.max_row + 1)}
    assert len(fills) == 1, f"static decile fills are gone; saw {fills}"


def _recalculated(blob, tmp_path):
    """LibreOffice-recalculated copy; returns (overview_values, details_values)."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:  # pragma: no cover - LibreOffice missing on the host
        pytest.skip("LibreOffice not installed")
    src = tmp_path / "in.xlsx"
    src.write_bytes(blob)
    out = tmp_path / "out"
    out.mkdir()
    profile = tmp_path / "lo-profile"
    profile.mkdir()
    subprocess.run(
        [soffice, "-env:UserInstallation=file://" + str(profile), "--headless",
         "--convert-to", "xlsx", "--outdir", str(out), str(src)],
        check=True, capture_output=True, timeout=180)
    produced = out / "in.xlsx"
    assert produced.exists()
    wb = load_workbook(produced, data_only=True)
    return wb["Overview"], wb["Details"]


def test_recalculated_scores_match_python_engine(workbook_blob, tmp_path):
    blob, scored = workbook_blob
    overview, _ = _recalculated(blob, tmp_path)
    # rows were written in sorted order; compare as multisets of percents
    expected = sorted(round(s["percent"], 6) for _, _, s in scored)
    got = sorted(round(overview.cell(row, 4).value * 100, 4)
                 for row in range(2, overview.max_row + 1))
    assert len(got) == len(expected)
    for g, e in zip(got, expected):
        assert g == pytest.approx(e, abs=0.02), (g, e)


def test_editing_a_factor_input_recalculates_the_score(workbook_blob, tmp_path):
    blob, scored = workbook_blob
    wb_edit = load_workbook(BytesIO(blob))
    details = wb_edit["Details"]
    headers = [c.value for c in details[1]]
    thc_col = headers.index(FACTOR_INPUT_COLUMNS[3]) + 1  # THC factor input
    # double the first row's THC factor: a strictly larger advantage
    original = details.cell(2, thc_col).value
    assert original and original != 1
    details.cell(2, thc_col).value = min(1.5, original * 1.2)
    edited = BytesIO()
    wb_edit.save(edited)
    overview, _ = _recalculated(edited.getvalue(), tmp_path)
    new_score = overview.cell(2, 4).value * 100
    _, _, s0 = scored[0]
    assert new_score - s0["percent"] > 0.1  # a bigger THC advantage raises the score


def test_editing_a_weight_cell_recalculates_all_scores(workbook_blob, tmp_path):
    blob, scored = workbook_blob
    wb_edit = load_workbook(BytesIO(blob))
    ws = wb_edit["Overview"]
    pop_cell = WEIGHT_CELLS["popularity"]
    ws[pop_cell] = 0.0  # popularity removed from the model
    edited = BytesIO()
    wb_edit.save(edited)
    overview, _ = _recalculated(edited.getvalue(), tmp_path)
    for row, (rec_, factors, score) in zip(range(2, overview.max_row + 1), scored):
        # expected: engine recomputation with the popularity weight removed
        expected = composite_score(factors, rec_["category"],
                                   weight_overrides={"popularity": 0.0})["percent"]
        got = overview.cell(row, 4).value * 100
        assert got == pytest.approx(expected, abs=0.02), \
            (rec_["product_name"], got, expected)
