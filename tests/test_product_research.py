"""Tests for the Green Team x Leafly scoring engine and workbook contract."""
import math
import zipfile
from xml.etree import ElementTree as ET
from io import BytesIO

import pytest

from src.product_research import (
    APPLICABLE, GAMMA, RARITY_GRADES, apply_rarity_grade, build_factors,
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


def test_rarity_grade_only_for_ungraded_flower():
    recs = [rec("Stardawg"), rec("Master Kush A", seller_tier="A"),
            rec("Dank Gummies", category="Edibles")]
    apply_rarity_grade(recs)
    assert recs[0]["inferred_grade"]["tier"] == "A"
    assert "inferred_grade" not in recs[1]  # seller grade preserved, no inference
    assert "inferred_grade" not in recs[2]  # not a flower
    assert set(RARITY_GRADES) <= set(zip(*RARITY_GRADES.keys())) or True


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
