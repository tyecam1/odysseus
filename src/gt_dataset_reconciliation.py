"""Deterministic Green Team x Leafly dataset reconciliation.

Resolves the closeout's "80 records versus the historical 78-row comparison"
question from primary evidence only: the research CSV rows, a dated store
capture (WooCommerce Store API), and the verified ``orderby=popularity``
capture. Produces product IDs, parent/variation relationships, additions,
removals, duplicates and purchase-status classification. Private datasets
stay with the caller; this module ships no data.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


def normalize_name(name: str) -> str:
    """Research/store name normalizer: unify dashes, HTML entities, grades."""
    name = str(name)
    for entity, char in (("&#8211;", "-"), ("&amp;", "&"), ("&#8212;", "-")):
        name = name.replace(entity, char)
    for ch in (chr(0xFFFD), "-", "–", "—"):
        name = name.replace(ch, " ")
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(a|aa|aa\+|aaa)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def verify_popularity_capture(capture: Mapping[str, Any]) -> List[str]:
    """Verify a captured ``orderby=popularity`` ordinal; returns violations.

    Genuine full pagination means the ordering is a contiguous 1..N rank list
    over N unique product ids, and the capture states its own total.
    """
    problems: List[str] = []
    ordering = capture.get("ordering") or []
    if capture.get("total") != len(ordering):
        problems.append(f"total {capture.get('total')!r} != len(ordering) {len(ordering)}")
    ranks = [item.get("rank") for item in ordering]
    if ranks != list(range(1, len(ordering) + 1)):
        problems.append("ranks are not a contiguous 1..N ordinal")
    ids = [item.get("id") for item in ordering]
    if len(set(ids)) != len(ids):
        problems.append("duplicate product ids in the ordering")
    if not capture.get("method"):
        problems.append("capture does not state its capture method")
    return problems


def match_research_to_store(
    research_rows: Sequence[Mapping[str, Any]],
    store_products: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Deterministically join research rows to store products.

    Returns matched pairs (with store ids), research rows with no store match
    (classified not listed), and store-only additions. Never invents matches:
    equality first, then a UNIQUE substring containment, then nothing.
    Normalized-name collisions never silently drop a product: one member of a
    collision group may be matched and the rest are reported under
    ``store_only_additions`` (and ``duplicates``).
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for product in store_products:
        groups.setdefault(normalize_name(product["name"]), []).append(product)
    for group in groups.values():
        group.sort(key=lambda p: p["id"])  # deterministic pick order

    def take_group(key: str) -> Optional[Dict[str, Any]]:
        """Pop the lowest-id remaining member; leftovers stay reportable."""
        group = groups.get(key)
        if not group:
            return None
        hit = group.pop(0)
        if not group:
            del groups[key]
        return hit

    matched: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    for row in research_rows:
        key = normalize_name(row["product_name"])
        hit = take_group(key)
        if hit is None:
            candidates = [sk for sk in sorted(groups)
                          if key in sk or sk in key]
            if len(candidates) == 1:  # ambiguous partial names never match
                hit = take_group(candidates[0])
        if hit is None:
            unmatched.append({"product_name": row["product_name"],
                              "classification": "not listed"})
        else:
            matched.append({"product_name": row["product_name"],
                            "store_id": hit["id"], "store_name": hit["name"]})
    additions = [{"store_id": p["id"], "store_name": p["name"]}
                 for group in sorted(groups.items()) for p in group[1]]
    additions.sort(key=lambda a: a["store_id"])
    return {"matched": matched, "research_not_listed": unmatched,
            "store_only_additions": additions}


def parent_child_relationships(store_products: Sequence[Mapping[str, Any]]
                               ) -> List[Dict[str, Any]]:
    """Every store product is a variable parent; its options are variations."""
    out = []
    for product in store_products:
        out.append({
            "parent_id": product["id"],
            "parent_name": product["name"],
            "type": product.get("type"),
            "variation_ids": [o["id"] for o in product.get("options") or []],
        })
    return out


def find_duplicates(records: Iterable[Mapping[str, Any]], key: str = "name"
                    ) -> List[Dict[str, Any]]:
    seen: Dict[str, List[Any]] = {}
    for record in records:
        seen.setdefault(normalize_name(record[key]), []).append(record[key])
    return [{"normalized": k, "names": v} for k, v in sorted(seen.items())
            if len(v) > 1]


def reconcile(research_rows: Sequence[Mapping[str, Any]],
              store_products: Sequence[Mapping[str, Any]],
              popularity_capture: Mapping[str, Any],
              prior_store_products: Optional[Sequence[Mapping[str, Any]]] = None,
              legacy_purchase_classification: bool = False,
              ) -> Dict[str, Any]:
    """Full deterministic reconciliation record."""
    match = match_research_to_store(research_rows, store_products)
    store_ids = {p["id"] for p in store_products}
    pop_violations = verify_popularity_capture(popularity_capture)
    pop_ids = {item["id"] for item in popularity_capture.get("ordering") or []}
    uncovered = store_ids - pop_ids
    if uncovered:
        pop_violations = pop_violations + [
            f"{len(uncovered)} store products absent from the popularity capture"]
    extras = pop_ids - store_ids
    if extras:
        pop_violations = pop_violations + [
            f"{len(extras)} capture ids absent from the store capture"]
    pop_verified = not pop_violations
    # purchasable requires stock AND presence in the popularity capture;
    # out-of-stock store products are classified separately.
    # purchasable additionally requires the seller's purchasability flag
    # where the capture records it (dated snapshots may omit the field);
    # in_stock alone is stock presence, not verified purchasability.
    raw_in_stock_ids = {p["id"] for p in store_products
                        if p.get("in_stock")}
    in_stock_ids = set(raw_in_stock_ids)
    # in-stock but explicitly not purchasable: a distinct classification,
    # never conflated with stock status
    not_purchasable_ids = {p["id"] for p in store_products
                           if p.get("in_stock")
                           and p.get("is_purchasable") is False}
    # Purchase eligibility is a separate axis from stock status. Only an
    # affirmative is_purchasable=True supports verified-purchasable;
    # False is verified-not-purchasable; an absent field is unknown
    # eligibility (unless the caller declares the snapshot legacy, i.e.
    # captured before the store exposed the flag, preserving that
    # snapshot's historical classification).
    eligibility_unknown_ids = {p["id"] for p in store_products
                               if p.get("in_stock")
                               and "is_purchasable" not in p}
    in_stock_ids -= not_purchasable_ids
    if legacy_purchase_classification:
        # historical classification: unknown-eligibility rows stay in the
        # in-stock classification and the unknown bucket stays empty
        eligibility_unknown_ids = set()
        in_stock_ids -= not_purchasable_ids
    else:
        in_stock_ids -= eligibility_unknown_ids
    purchase = {
        "purchasable_store_ids": sorted(in_stock_ids & pop_ids),
        "out_of_stock_store_ids": sorted(
            (store_ids - raw_in_stock_ids) - not_purchasable_ids),
        "not_purchasable_store_ids": sorted(not_purchasable_ids),
        "purchase_eligibility_unknown_store_ids": sorted(
            eligibility_unknown_ids),
        "purchasable_unverified_against_popularity":
            sorted(in_stock_ids - pop_ids),
    }
    removals: List[Dict[str, Any]] = []
    if prior_store_products is not None:
        prior_ids = {p["id"] for p in prior_store_products}
        removals = [{"store_id": i, "store_name": p["name"]}
                    for i, p in sorted(
                        {p["id"]: p for p in prior_store_products}.items())
                    if i not in store_ids]
    return {
        "research_rows": len(research_rows),
        "store_products": len(store_products),
        "matched": match["matched"],
        "research_not_listed": match["research_not_listed"],
        "store_only_additions": match["store_only_additions"],
        "removals_vs_prior": removals,
        "duplicates": find_duplicates(store_products),
        "parent_child": parent_child_relationships(store_products),
        "popularity_capture_verified": pop_verified,
        "popularity_capture_violations": pop_violations,
        "purchase_status": purchase,
        "expected_record_total": (len(research_rows)
                                  + len(match["store_only_additions"])),
    }
