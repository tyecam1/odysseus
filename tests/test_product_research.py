"""Tests for the Green Team x Leafly scoring engine and workbook contract."""
import math
import copy
import json
import re
import zipfile
from xml.etree import ElementTree as ET
from io import BytesIO

import pytest

from src.product_research import (
    APPLICABLE, GAMMA, _midrank_factor, apply_rarity_grade, build_factors,
    combined_popularity, combined_rating, composite_score, parse_quantity_grams,
    seller_grade_numeric, sort_records, unit_price,
)
from src.product_workbook import DETAIL_COLUMNS, OVERVIEW_COLUMNS, build_workbook


def rec(name, category="Cannabis flower", **kw):
    r = {"product_name": name, "category": category, "buying_status": "purchasable"}
    r.update(kw)
    return r


# --- unit prices -------------------------------------------------------------

def test_unit_price_min_per_gram_excludes_zero_and_unknown():
    opts = [{"size": "1g", "price": 12.5}, {"size": "3.5g", "price": 30},
            {"size": "7g", "price": 0}, {"size": "1 PACK", "price": 20},
            {"size": "?", "price": 5}]
    best, basis, det = unit_price(opts)
    assert best == pytest.approx(30 / 3.5)
    assert basis == "per g"
    assert len(det["excluded_options"]) == 3


def test_parse_quantity_units():
    assert parse_quantity_grams("3.5g") == 3.5
    assert parse_quantity_grams("1000MG") == 1.0
    assert parse_quantity_grams("1 PACK") is None
    assert parse_quantity_grams("") is None


# --- ratings -----------------------------------------------------------------

def test_unrated_is_not_zero_stars():
    blended, detail = combined_rating((None, None), (0.0, 0))
    assert blended is None
    blended2, _ = combined_rating((None, None), (None, None))
    assert blended2 is None


def test_combined_rating_sample_weighting():
    # leafly 4.5 with 100 counts dominates seller 3.0 with 1 count
    blended, detail = combined_rating((4.5, 100), (3.0, 1))
    assert blended > 3.0 and blended < 4.5
    assert (blended - 3.0) > (4.5 - blended)  # pulled toward leafly
    assert detail["weights"]["leafly"] > detail["weights"]["seller"]


def test_combined_popularity_uses_verified_seller_ordinal():
    f, det = combined_popularity(1000, 1, 10, "Cannabis flower",
                                 [1000, 10, 5], [1, 2, 3])
    assert f is not None and det["seller_factor"] is not None
    # rank 1 (most popular) must score above rank 3
    f3, _ = combined_popularity(1000, 3, 10, "Cannabis flower",
                                [1000, 10, 5], [1, 2, 3])
    assert f > f3


def test_zero_reviews_is_not_zero_demand():
    f, _ = combined_popularity(None, 1, 10, "Hash and sift", [None, None], [1, 2])
    assert f is not None  # seller ordinal still carries popularity evidence


# --- scoring -----------------------------------------------------------------

def test_gamma_spread_midpoint_and_range():
    f = dict(grade=(1.0, 1.0))
    mid = composite_score(type("F", (), {"grade": (1.0, 1.0), "rating": 1.0,
                                          "price": (1.0, "per g"), "thc": 1.0,
                                          "si": 1.0, "popularity": 1.0,
                                          "detail": {}})(), "Cannabis flower")
    assert mid["percent"] == pytest.approx(50.0)
    # strong advantage approaches (but never fabricates) 100
    strong = composite_score(type("F", (), {"grade": (1.5, 1.0), "rating": 1.5,
                                             "price": (1.5, "per g"), "thc": 1.5,
                                             "si": 1.5, "popularity": 1.5,
                                             "detail": {}})(), "Cannabis flower")
    assert strong["percent"] > 90
    assert strong["percent"] <= 100


def test_missing_penalty_first_forgiven_then_compounded():
    # Cannabis flower: grade present only -> 5 applicable missing
    f1 = type("F", (), {"grade": (1.0, 1.0), "rating": None, "price": None,
                        "thc": None, "si": None, "popularity": None,
                        "detail": {}})()
    r1 = composite_score(f1, "Cannabis flower")
    assert r1["missing_penalty"] == pytest.approx(0.8 ** 4)
    # all applicable present -> penalty 1
    tall = type("F", (), {"grade": (1.0, 1.0), "rating": 1.0, "price": (1.0, "g"),
                          "thc": 1.0, "si": 1.0, "popularity": 1.0, "detail": {}})()
    assert composite_score(tall, "Cannabis flower")["missing_penalty"] == 1.0


def test_inapplicable_not_penalised_mushrooms():
    # mushroom with rating+price+popularity present => no missing metrics
    f = type("F", (), {"grade": None, "rating": 1.0, "price": (1.0, "per g"),
                       "thc": None, "si": None, "popularity": 1.0, "detail": {}})()
    r = composite_score(f, "Mushroom-related")
    assert r["missing_applicable"] == []
    assert r["missing_penalty"] == 1.0


def test_popularity_weight_actually_25_percent():
    # with everything else equal, popularity alone cannot move the score much
    base = type("F", (), {"grade": (1.2, 1.0), "rating": 1.2, "price": (1.2, "g"),
                          "thc": 1.2, "si": 1.2, "popularity": 1.0, "detail": {}})()
    pop = type("F", (), {"grade": (1.2, 1.0), "rating": 1.2, "price": (1.2, "g"),
                         "thc": 1.2, "si": 1.2, "popularity": 1.5, "detail": {}})()
    a = composite_score(base, "Cannabis flower")["percent"]
    b = composite_score(pop, "Cannabis flower")["percent"]
    assert 0 < b - a < 3.0  # weight 0.25 keeps the effect small


def test_single_peer_category_is_neutral():
    recs = [rec("Solo", "Vapes", combined_rating=4.0, unit_price=20.0,
                unit_basis="per g", leafly_rating_count=10,
                seller_popularity_rank=1)]
    scored = build_factors(recs)
    _, f, score = scored[0]
    assert f.rating == 1.0 and f.price[0] == 1.0
    assert score["gm"] == 1.0


def test_seller_only_singleton_popularity_is_present_and_neutral():
    _, factors, score = build_factors([rec("Synthetic", "Vapes", seller_popularity_rank=1)])[0]
    assert factors.popularity == 1.0
    assert "popularity" not in score["missing_applicable"]


def test_present_flower_reference_thc_and_orientation_are_scored():
    record = rec("Synthetic flower", leafly_thc=25, sativa_pct=75, indica_pct=25,
                 primary_leafly_source="https://example.invalid/cultivar")
    before = copy.deepcopy(record)
    _, factors, score = build_factors([record])[0]
    assert factors.thc == factors.si == 1.0
    assert {"thc", "si"}.isdisjoint(score["missing_applicable"])
    assert record == before
    assert factors.detail["thc"]["evidence_class"] == "cultivar_reference"
    assert "never a batch measurement" in factors.detail["thc"]["basis"]
    assert factors.detail["thc"]["source"] == record["primary_leafly_source"]
    assert factors.detail["si"]["raw_values"] == {"sativa_pct": 75, "indica_pct": 25}


def test_flower_reference_peers_ties_ordering_and_mean():
    records = [rec(f"Synthetic {i}", leafly_thc=thc, sativa_pct=sativa, indica_pct=100-sativa)
               for i, (thc, sativa) in enumerate([(10, 20), (25, 75), (25, 75), (30, 90)])]
    scored = build_factors(records)
    for metric in ("thc", "si"):
        values = [getattr(f, metric) for _, f, _ in scored]
        assert values[0] < values[1] == values[2] < values[3]
        assert sum(values) / len(values) == pytest.approx(1)
    scores = [score["score"] for _, _, score in scored]
    assert scores[0] < scores[1] == scores[2] < scores[3]
    equal = build_factors([rec(f"Synthetic equal {i}", leafly_thc=25, sativa_pct=75)
                           for i in range(3)])
    assert all(f.thc == f.si == 1 for _, f, _ in equal)


@pytest.mark.parametrize("category", sorted(set(APPLICABLE) - {"Cannabis flower"}))
def test_nonflower_reference_values_never_become_factors_or_peers(category):
    flower = rec("Synthetic flower", leafly_thc=25, sativa_pct=75)
    other = rec("Synthetic nonflower", category, leafly_thc=100, sativa_pct=100, indica_pct=0)
    scored = {r["product_name"]: (f, score) for r, f, score in build_factors([flower, other])}
    assert scored["Synthetic flower"][0].thc == scored["Synthetic flower"][0].si == 1
    factors, score = scored["Synthetic nonflower"]
    assert factors.thc is factors.si is None
    assert {"thc", "si"}.isdisjoint(score["missing_applicable"] + score["factors_present"])


@pytest.mark.parametrize("value", [None, True, "25", -1, 101, float("nan"), float("inf")])
def test_invalid_flower_reference_values_are_missing_and_excluded_from_peers(value):
    records = [rec("Synthetic valid", leafly_thc=25, sativa_pct=75),
               rec("Synthetic invalid", leafly_thc=value, sativa_pct=value)]
    (_, valid, _), (_, invalid, score) = build_factors(records)
    assert valid.thc == valid.si == 1
    assert invalid.thc is invalid.si is None
    assert {"thc", "si"} <= set(score["missing_applicable"])
    assert invalid.detail["thc"]["excluded_reason"]
    assert invalid.detail["si"]["excluded_reason"]


def test_orientation_single_axis_comparison_keeps_source_missingness():
    records = [rec("Synthetic sativa", sativa_pct=75),
               rec("Synthetic indica", indica_pct=25),
               rec("Synthetic conflicting", sativa_pct=75, indica_pct=75)]
    before = copy.deepcopy(records)
    (_, sativa, _), (_, indica, _), (_, conflicting, score) = build_factors(records)
    assert sativa.si == indica.si == 1
    assert indica.detail["si"]["comparison_value"] == 75
    assert indica.detail["si"]["raw_values"] == {"sativa_pct": None, "indica_pct": 25}
    assert conflicting.si is None and "si" in score["missing_applicable"]
    assert records == before


def test_rarity_grade_only_for_ungraded_flower():
    recs = [rec("Synthetic ungraded"), rec("Synthetic seller", seller_tier="A"),
            rec("Synthetic edible", category="Edibles")]
    policy = {r["product_name"]: {"tier": "AA", "confidence": 0.6,
              "provenance": {"source": "synthetic-policy", "revision": "test-v1"}}
              for r in recs}
    apply_rarity_grade(recs)
    assert all("inferred_grade" not in r for r in recs)  # no bundled personal policy
    build_factors(recs, rarity_policy=policy)
    assert recs[0]["inferred_grade"]["tier"] == "AA"
    assert recs[0]["inferred_grade"]["numeric"] == 2.0
    assert recs[0]["inferred_grade"]["provenance"] == policy["Synthetic ungraded"]["provenance"]
    assert "inferred_grade" not in recs[1]  # seller grade preserved, no inference
    assert "inferred_grade" not in recs[2]  # not a flower


@pytest.mark.parametrize("entry", [
    {"tier": "AA", "confidence": 0.5},
    {"tier": "unknown", "confidence": 0.5, "provenance": "synthetic"},
    {"tier": "AA", "confidence": -0.1, "provenance": "synthetic"},
    {"tier": "AA", "confidence": float("nan"), "provenance": "synthetic"},
])
def test_invalid_injected_grade_policy_rejected(entry):
    with pytest.raises(ValueError):
        apply_rarity_grade([rec("Synthetic")], {"Synthetic": entry})


@pytest.mark.parametrize("values", [[4], [4, 4], [4, 4, 4], [1, 2, 2, 4, 9]])
@pytest.mark.parametrize("smaller", [False, True])
def test_midrank_ties_mean_and_direction(values, smaller):
    factors = [_midrank_factor(values, i, 0.8, smaller) for i in range(len(values))]
    assert sum(factors) / len(factors) == pytest.approx(1)
    if len(set(values)) == 1:
        assert factors == [1.0] * len(values)
    else:
        ordered = sorted(zip(values, factors))
        for (a, fa), (b, fb) in zip(ordered, ordered[1:]):
            if a == b:
                assert fa == fb
            else:
                assert (fa > fb) if smaller else (fa < fb)


def test_price_peers_require_same_category_and_unit_basis():
    records = [rec("gram", "Vapes", unit_price=1, unit_basis="per g"),
               rec("item", "Vapes", unit_price=100, unit_basis="per item"),
               rec("other category", "Edibles", unit_price=10, unit_basis="per g")]
    assert all(f.price[0] == 1 for _, f, _ in build_factors(records))
    records.append(rec("expensive gram", "Vapes", unit_price=2, unit_basis="per g"))
    factors = {r["product_name"]: f for r, f, _ in build_factors(records)}
    assert factors["gram"].price[0] > 1 > factors["expensive gram"].price[0]
    assert factors["item"].price == (1.0, "per item")


@pytest.mark.parametrize("price,basis", [(0, "per g"), (-1, "per g"),
    (float("nan"), "per g"), (float("inf"), "per g"), ("1", "per g"),
    (True, "per g"), (1, None), (1, "")])
def test_invalid_price_inputs_have_reasons(price, basis):
    record = rec("Synthetic", "Vapes", unit_price=price, unit_basis=basis)
    _, factor, score = build_factors([record])[0]
    assert factor.price is None and "price" in score["missing_applicable"]
    assert factor.detail["price"]["excluded_reason"]


def test_invalid_options_excluded_with_source_quantities_preserved():
    options = [{"size": "2g", "price": 10, "variant_id": "synthetic-v1"},
               {"size": "1g", "price": "bad"}, {"size": "0g", "price": 1},
               {"size": "-1g", "price": 1}, {"size": "1g", "price": float("inf")},
               {"size": "1g", "price": True}, None]
    best, basis, detail = unit_price(options)
    assert (best, basis) == (5, "per g")
    assert len(detail["excluded_options"]) == 6
    assert all(detail["excluded_options"])
    assert detail["source_options"] == options
    assert detail["valid_options"] == [{"source_option_index": 0, "quantity_grams": 2,
                                        "unit_price": 5, "unit_basis": "per g"}]


def test_every_item_gets_a_score():
    recs = [
        rec("A", combined_rating=4.0, unit_price=10.0, unit_basis="per g",
            leafly_rating_count=50, seller_popularity_rank=1),
        rec("B", category="Edibles", combined_rating=None, unit_price=None),
        rec("C", category="Hash and sift", seller_tier="AA", combined_rating=3.0,
            unit_price=6.7, unit_basis="per g", leafly_rating_count=5,
            seller_popularity_rank=3),
    ]
    scored = build_factors(recs)
    assert all(isinstance(s["score"], float) and 0.0 <= s["score"] <= 1.0
               for _, _, s in scored)


# --- sorting / workbook ------------------------------------------------------

def _scored(recs):
    return build_factors(recs)


def test_availability_first_then_category_score_price():
    recs = [
        rec("CheapLow", combined_rating=3.0, unit_price=5.0, unit_basis="per g",
            leafly_rating_count=5, seller_popularity_rank=2),
        rec("ExpHigh", combined_rating=4.9, unit_price=50.0, unit_basis="per g",
            leafly_rating_count=50, seller_popularity_rank=1),
        rec("OffList", buying_status="not listed", combined_rating=4.0,
            unit_price=1.0, unit_basis="per g", leafly_rating_count=99,
            seller_popularity_rank=1),
    ]
    ordered = sort_records(_scored(recs))
    names = [r["product_name"] for r, _, _ in ordered]
    # purchasable first, higher score first; not-listed last despite best metrics
    assert names == ["ExpHigh", "CheapLow", "OffList"]


def test_workbook_contract_two_sheets_exact_columns():
    recs = [
        rec("A", combined_rating=4.0, unit_price=10.0, unit_basis="per g",
            leafly_rating_count=50, seller_popularity_rank=1,
            store_description="seller text", permalink="https://x/1",
            overview_options=[{"size": "1g", "price": 10.0}],
            leafly_description="leafly text", match_classification="exact"),
        rec("B", category="Edibles", buying_status="not listed"),
    ]
    blob = build_workbook(sort_records(_scored(recs)), "2026-10-25")
    z = zipfile.ZipFile(BytesIO(blob))
    names = [n for n in z.namelist() if n.startswith("xl/worksheets")]
    assert len(names) == 2
    from xml.etree import ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    hdr = ["".join(t.text or "" for t in c.iter(ns + "t"))
           for c in root.find(ns + "sheetData").findall(ns + "row")[0].findall(ns + "c")]
    assert hdr == OVERVIEW_COLUMNS
    assert len(hdr) == 23
    root2 = ET.fromstring(z.read("xl/worksheets/sheet2.xml"))
    hdr2 = ["".join(t.text or "" for t in c.iter(ns + "t"))
            for c in root2.find(ns + "sheetData").findall(ns + "row")[0].findall(ns + "c")]
    assert hdr2 == DETAIL_COLUMNS


def test_workbook_losslessness_and_alignment():
    recs = [
        rec("A", combined_rating=4.0, unit_price=10.0, unit_basis="per g",
            leafly_rating_count=50, seller_popularity_rank=1,
            store_description="FULL seller description " * 10,
            permalink="https://seller/a", overview_options=[{"size": "1g", "price": 10.0}],
            leafly_description="leafly text", match_classification="exact"),
    ]
    blob = build_workbook(sort_records(_scored(recs)), "2026-10-25")
    z = zipfile.ZipFile(BytesIO(blob))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    s1 = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    s2 = ET.fromstring(z.read("xl/worksheets/sheet2.xml"))
    r1 = s1.find(ns + "sheetData").findall(ns + "row")
    r2 = s2.find(ns + "sheetData").findall(ns + "row")
    assert len(r1) == len(r2)  # row-aligned Overview/Details
    text = "".join(t.text or "" for t in s1.iter(ns + "t"))
    assert ("FULL seller description " * 10).strip() in text
    d2 = "".join(t.text or "" for t in s2.iter(ns + "t"))
    assert "https://seller/a" in d2 and "leafly text" in d2


def test_workbook_row_order_matches_sorted_scores():
    recs = [
        rec("Low", combined_rating=3.0, unit_price=5.0, unit_basis="per g",
            leafly_rating_count=5, seller_popularity_rank=2),
        rec("High", combined_rating=4.9, unit_price=50.0, unit_basis="per g",
            leafly_rating_count=50, seller_popularity_rank=1),
    ]
    blob = build_workbook(sort_records(_scored(recs)), "2026-10-25")
    z = zipfile.ZipFile(BytesIO(blob))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    data = root.find(ns + "sheetData").findall(ns + "row")[1:]
    names = ["".join(t.text or "" for t in row.findall(ns + "c")[2].iter(ns + "t"))
             for row in data]
    assert names[0] == "High"


# Synthetic regression probes adapted from /tmp/pr167-independent-acceptance.py.
XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _workbook_xml(blob):
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        return {name: ET.fromstring(archive.read(name)) for name in archive.namelist()
                if name.endswith((".xml", ".rels"))}


def _cell_value(cell):
    value = cell.find(XML_NS + "v")
    return value.text if value is not None else "".join(t.text or "" for t in cell.iter(XML_NS + "t"))


def test_workbook_valid_argb_formats_widths_and_score_only_gradient():
    record = rec("Synthetic", unit_price=5, unit_basis="per g", leafly_thc=25,
                 sativa_pct=75, indica_pct=25, overview_options=[{"size": "2g", "price": 10}])
    scored = build_factors([record])
    # Exercise all gradient deciles, including endpoints, independently of scoring.
    rows = [(dict(record, product_name=f"Synthetic {i}"), scored[0][1],
             dict(scored[0][2], score=i / 10, percent=i * 10)) for i in range(11)]
    blob = build_workbook(rows, "2026-10-25")
    xml = _workbook_xml(blob)
    styles = xml["xl/styles.xml"]
    rgbs = [node.attrib["rgb"] for node in styles.iter(XML_NS + "fgColor")]
    assert all(re.fullmatch("[0-9A-F]{8}", rgb) for rgb in rgbs)
    fills = styles.find(XML_NS + "fills")
    xfs = styles.find(XML_NS + "cellXfs")
    assert int(fills.attrib["count"]) == len(fills)
    assert int(xfs.attrib["count"]) == len(xfs)
    custom_formats = {int(n.attrib["numFmtId"]): n.attrib["formatCode"]
                      for n in styles.find(XML_NS + "numFmts")}
    assert "0.00" in custom_formats[164]
    assert custom_formats[165] == '0.0"%"'
    overview = xml["xl/worksheets/sheet1.xml"]
    assert overview.find(XML_NS + "dimension").attrib["ref"] == "A1:W12"
    for name in ("xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"):
        root = xml[name]
        pane = root.find(f"{XML_NS}sheetViews/{XML_NS}sheetView/{XML_NS}pane")
        assert pane.attrib["topLeftCell"] == "A2" and pane.attrib["state"] == "frozen"
        widths = root.find(XML_NS + "cols")
        assert len(widths) >= 23 and all(float(col.attrib["width"]) >= 14 for col in widths)
    for row in overview.find(XML_NS + "sheetData")[1:]:
        for cell in row:
            style = xfs[int(cell.attrib["s"])]
            assert int(style.attrib["fillId"]) < len(fills)
            fill = fills[int(style.attrib["fillId"])].find(f"{XML_NS}patternFill/{XML_NS}fgColor")
            if cell.attrib["r"].startswith("D"):
                assert style.attrib["numFmtId"] == "10"
                rgb = fill.attrib["rgb"]
                red, green, blue = (int(rgb[i:i + 2], 16) for i in (2, 4, 6))
                assert green > red and green > blue
                assert 0 <= float(_cell_value(cell)) <= 1
            elif fill is not None:
                assert fill.attrib["rgb"] in {"FFFFFFFF", "FFF2F2F2"}
            if cell.attrib["r"].startswith(("G", "L")):
                assert style.attrib["numFmtId"] == "164"
            if cell.attrib["r"].startswith(("H", "I", "J")):
                assert style.attrib["numFmtId"] == "165"
    # Actually load the generated artifact whenever the environment supplies a reader.
    try:
        import openpyxl
    except ImportError:
        pass  # XML package, ARGB, style indices and numeric-format checks above are mandatory.
    else:
        workbook = openpyxl.load_workbook(BytesIO(blob))
        assert workbook.sheetnames == ["Overview", "Details"]
        assert workbook["Overview"].max_column == 23
        assert workbook["Overview"]["G2"].value == 5
        assert workbook["Overview"]["D12"].value == 1
        assert workbook["Overview"]["D12"].number_format == "0.00%"


def test_workbook_raw_record_round_trip_arbitrary_fields_variants_and_dictionary():
    records = [rec("Synthetic long", product_key="synthetic-v1", unit_basis="per g", unit_price=5,
                   raw_options=[{"size": f"{i}g", "price": i * 5,
                                 "variant_id": f"synthetic-option-{i}", "extra": [1, 2]}
                                for i in range(1, 9)],
                   additional_source_metadata={"url": "https://example.invalid/source", "confidence": 0.4},
                   arbitrary_new_field={"text": "=1+1<&>\x00\r\n", "unknown": None},
                   store_description="Synthetic evidence " * 2500),
               rec("Synthetic short", category="Vapes", product_key="synthetic-v2")]
    scored = sort_records(build_factors(records))
    before = copy.deepcopy(records)
    blob = build_workbook(scored, "2026-10-25")
    xml = _workbook_xml(blob)
    overview_rows = xml["xl/worksheets/sheet1.xml"].find(XML_NS + "sheetData")
    detail_rows = xml["xl/worksheets/sheet2.xml"].find(XML_NS + "sheetData")
    headers = [_cell_value(cell) for cell in detail_rows[0]]
    part_indices = [i for i, name in enumerate(headers) if name.startswith("Raw record JSON part ")]
    assert len(part_indices) > 1  # long raw JSON is split, never silently truncated
    assert len(overview_rows) == len(detail_rows) == len(records) + 1
    for overview_row, detail_row, (record, _, _) in zip(overview_rows[1:], detail_rows[1:], scored):
        raw = "".join(_cell_value(detail_row[i]) for i in part_indices)
        assert json.loads(raw) == record
        assert _cell_value(overview_row[1]) == record["product_name"] == _cell_value(detail_row[2])
        methodology = json.loads(_cell_value(detail_row[headers.index("Scoring methodology (JSON)")]))
        assert methodology["weights"] == {"grade": 1, "rating": 1, "price": 1,
                                          "thc": 1, "si": 1, "popularity": 0.25}
        assert methodology["gamma"] == 6
        assert methodology["canon_ref"]["repository"] == "tyecam1/misumi"
        assert "Field dictionary (JSON)" in headers
    assert records == before
    assert not any(node.tag == XML_NS + "f" for root in xml.values() for node in root.iter())
    try:
        import openpyxl
    except ImportError:
        return  # Raw XML values above still verify the complete JSON round trip.
    workbook = openpyxl.load_workbook(BytesIO(blob))
    assert workbook.sheetnames == ["Overview", "Details"]
    assert workbook["Overview"].max_column == 23
    assert workbook["Overview"].max_row == workbook["Details"].max_row == len(records) + 1
    for row_number, (record, _, _) in enumerate(scored, start=2):
        raw = "".join(workbook["Details"].cell(row_number, i + 1).value or "" for i in part_indices)
        assert json.loads(raw) == record
        assert workbook["Overview"].cell(row_number, 2).value == workbook["Details"].cell(row_number, 3).value


def test_workbook_empty_input_keeps_schema():
    xml = _workbook_xml(build_workbook([], "2026-10-25"))
    assert xml["xl/worksheets/sheet1.xml"].find(XML_NS + "dimension").attrib["ref"] == "A1:W1"
    assert len(xml["xl/worksheets/sheet2.xml"].find(XML_NS + "sheetData")) == 1
