"""Tests for the deterministic GT dataset reconciliation."""
import pytest

from src.gt_dataset_reconciliation import (
    find_duplicates, match_research_to_store, normalize_name, reconcile,
    verify_popularity_capture,
)


def row(name):
    return {"product_name": name}


def prod(pid, name, options=()):
    # modern capture shape: the store returns an affirmative purchasability
    # flag; legacy snapshots without it are covered by dedicated tests
    return {"id": pid, "name": name, "type": "variable", "in_stock": True,
            "is_purchasable": True,
            "options": [{"id": i} for i in options]}


def capture(ids):
    return {"captured_at": "2026-10-25T12:00:00+00:00",
            "source": "https://thegreenteam.store/wp-json/wc/store/v1/products?orderby=popularity",
            "method": "WooCommerce Store API orderby=popularity, full pagination",
            "total": len(ids),
            "ordering": [{"rank": i + 1, "id": pid, "name": f"p{pid}"}
                         for i, pid in enumerate(ids)]}


def test_normalize_unifies_entities_dashes_and_retail_grades():
    assert normalize_name("Animal Runtz &#8211; AA") == \
        normalize_name("Animal Runtz – AA")
    assert normalize_name("SuperBoof AA+") == normalize_name("SuperBoof")
    assert normalize_name("Cali Gold – Full Melt 90–120u") == \
        normalize_name("Cali Gold Full Melt 90-120u")


def test_research_78_join_to_69_products_and_two_store_only_additions():
    research = [row(f"Product {i}") for i in range(76)]
    store = [prod(900 + i, f"Product {i}") for i in range(67)]
    store += [prod(5000, "Amnesia Haze"), prod(5001, "10/10 Boys Vapes")]
    result = match_research_to_store(research, store)
    assert len(result["matched"]) == 67
    assert len(result["research_not_listed"]) == 9
    assert result["store_only_additions"] == [
        {"store_id": 5000, "store_name": "Amnesia Haze"},
        {"store_id": 5001, "store_name": "10/10 Boys Vapes"}]
    # the workbook record total: every research row + store-only additions
    assert len(research) + len(result["store_only_additions"]) == 78


def test_unmatched_research_rows_are_never_invented_into_matches():
    research = [row("Cookie Dawg"), row("Totally Absent Item")]
    store = [prod(1, "Cookie Dawg &#8211; AA")]
    result = match_research_to_store(research, store)
    assert result["matched"][0]["store_id"] == 1
    assert result["research_not_listed"] == [
        {"product_name": "Totally Absent Item", "classification": "not listed"}]


def test_popularity_capture_verification():
    good = capture([7, 3, 9])
    assert verify_popularity_capture(good) == []
    bad = dict(good, total=5)
    assert any("total" in p for p in verify_popularity_capture(bad))
    broken = dict(good, ordering=[good["ordering"][0], good["ordering"][2]])
    assert any("contiguous" in p for p in verify_popularity_capture(broken))
    dup = dict(good, ordering=[good["ordering"][0], dict(good["ordering"][0], rank=2)])
    assert any("duplicate" in p for p in verify_popularity_capture(dup))


def test_parent_child_relationships_use_option_variation_ids():
    store = [prod(1, "Parent", options=(11, 12, 13))]
    rel = parent_child(store)
    assert rel == [{"parent_id": 1, "parent_name": "Parent",
                    "type": "variable", "variation_ids": [11, 12, 13]}]


def parent_child(store):
    from src.gt_dataset_reconciliation import parent_child_relationships
    return parent_child_relationships(store)


def test_duplicates_detected_after_normalization():
    store = [prod(1, "Gelato &#8211; AA"), prod(2, "Gelato AA")]
    assert find_duplicates(store) == [{"normalized": "gelato",
                                       "names": ["Gelato &#8211; AA", "Gelato AA"]}]


def test_full_reconcile_classifies_and_totals():
    research = [row(f"P{i}") for i in range(5)] + [row("Delisted Item")]
    store = [prod(100 + i, f"P{i}", options=(200 + i,)) for i in range(5)]
    store.append(prod(1, "Brand New Product"))
    cap = capture([100, 101, 102, 103, 104, 1])  # Delisted absent from capture
    prior = store + [prod(999, "Removed Product")]
    result = reconcile(research, store, cap, prior)
    assert result["research_rows"] == 6 and result["store_products"] == 6
    assert result["popularity_capture_verified"] is True
    assert result["expected_record_total"] == 7  # 6 research + 1 store-only
    assert result["store_only_additions"] == [
        {"store_id": 1, "store_name": "Brand New Product"}]
    assert result["removals_vs_prior"] == [
        {"store_id": 999, "store_name": "Removed Product"}]
    assert result["purchase_status"]["purchasable_store_ids"] == [
        1, 100, 101, 102, 103, 104]
    assert result["purchase_status"]["purchasable_unverified_against_popularity"] == []
    assert len(result["parent_child"]) == 6


def test_capture_violations_flag_unverified_purchase_status():
    research = [row("P0")]
    store = [prod(100, "P0"), prod(777, "Off Capture")]
    cap = capture([100])  # missing 777
    result = reconcile(research, store, cap)
    assert result["popularity_capture_verified"] is False
    assert result["popularity_capture_violations"]
    assert 777 in result["purchase_status"]["purchasable_unverified_against_popularity"]


def test_capture_extras_are_not_silent():
    research = [row("P0"), row("P1")]
    store = [prod(100, "P0"), prod(101, "P1")]
    cap = capture([100, 101, 999])  # stale/extra id
    result = reconcile(research, store, cap)
    assert result["popularity_capture_verified"] is False
    assert any("capture ids absent from the store capture" in v
               for v in result["popularity_capture_violations"])


def test_out_of_stock_products_are_not_purchasable():
    research = [row("P0"), row("P1")]
    store = [prod(100, "P0"), dict(prod(101, "P1"), in_stock=False)]
    cap = capture([100, 101])
    result = reconcile(research, store, cap)
    assert result["purchase_status"]["purchasable_store_ids"] == [100]
    assert result["purchase_status"]["out_of_stock_store_ids"] == [101]


def test_normalized_name_collision_never_drops_a_product():
    research = [row("Gelato AA")]
    store = [prod(2, "Gelato AAA"), prod(1, "Gelato AA")]  # same normalized name
    result = match_research_to_store(research, store)
    assert len(result["matched"]) == 1
    # the unmatched collision member must still be reported, deterministically
    assert result["store_only_additions"] == [
        {"store_id": 2, "store_name": "Gelato AAA"}]
    # and reversing the input order must not change the matched id
    flipped = match_research_to_store(research, list(reversed(store)))
    assert flipped["matched"][0]["store_id"] == result["matched"][0]["store_id"]


def test_collision_group_matches_successive_research_rows():
    research = [row("Gelato AA"), row("Gelato AAA")]
    store = [prod(2, "Gelato AAA"), prod(1, "Gelato AA")]  # same normalized name
    result = match_research_to_store(research, store)
    assert sorted(m["store_id"] for m in result["matched"]) == [1, 2]
    assert result["research_not_listed"] == []
    assert result["store_only_additions"] == []


def test_ambiguous_substring_never_matches():
    research = [row("Hash")]
    store = [prod(1, "Hash Lemon"), prod(2, "Lemon Hash Plaza")]
    result = match_research_to_store(research, store)
    assert result["matched"] == []
    assert result["research_not_listed"] == [
        {"product_name": "Hash", "classification": "not listed"}]
    assert [a["store_id"] for a in result["store_only_additions"]] == [1, 2]


def test_not_purchasable_flag_excludes_from_purchasable_ids():
    # in_stock=true but is_purchasable=false is NOT purchasable; a dated
    # snapshot without the field keeps its previous behaviour.
    research = [row("P0"), row("P1"), row("P2")]
    store = [prod(100, "P0"),
             dict(prod(101, "P1"), is_purchasable=False),
             prod(102, "P2")]
    cap = capture([100, 101, 102])
    result = reconcile(research, store, cap)
    assert result["purchase_status"]["purchasable_store_ids"] == [100, 102]
    assert result["purchase_status"]["not_purchasable_store_ids"] == [101]
    # stock status stays separate from purchasability
    assert 101 not in result["purchase_status"]["out_of_stock_store_ids"]
    assert 101 not in result["purchase_status"]["purchase_eligibility_unknown_store_ids"]


def test_purchase_eligibility_flags_classified_separately():
    # Affirmative true = verified purchasable; explicit false = verified
    # not purchasable; absent field = unknown eligibility (strict mode).
    research = [row("P0"), row("P1"), row("P2"), row("P3")]
    store = [dict(prod(100, "P0"), is_purchasable=True),
             dict(prod(101, "P1"), is_purchasable=False),
             {k: v for k, v in prod(102, "P2").items()
              if k != "is_purchasable"},  # field absent entirely
             dict(prod(103, "P3"), in_stock=False)]
    cap = capture([100, 101, 102, 103])
    result = reconcile(research, store, cap)
    ps = result["purchase_status"]
    assert ps["purchasable_store_ids"] == [100]
    assert ps["not_purchasable_store_ids"] == [101]
    assert ps["purchase_eligibility_unknown_store_ids"] == [102]
    assert ps["out_of_stock_store_ids"] == [103]


def test_legacy_purchase_classification_preserves_historical_ids():
    # A dated snapshot captured before the store exposed is_purchasable
    # keeps its historical in-stock classification; verified purchases
    # still exclude explicit false.
    research = [row("P0"), row("P1"), row("P2")]
    store = [prod(100, "P0"),
             dict(prod(101, "P1"), is_purchasable=False),
             prod(102, "P2")]
    cap = capture([100, 101, 102])
    result = reconcile(research, store, cap, legacy_purchase_classification=True)
    ps = result["purchase_status"]
    assert ps["purchasable_store_ids"] == [100, 102]
    assert ps["not_purchasable_store_ids"] == [101]
    assert ps["purchase_eligibility_unknown_store_ids"] == []
