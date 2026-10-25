"""Deterministic Green Team x Leafly product-comparison scoring engine.

Implements the canonical operator contract:
`tyecam1/misumi:docs/preferences/green-team-leafly-product-comparison-v1.md`
(canonical blob 3ac07e494e5575d8a61c730956f04627169533a3, version 1).

Order of operations is exactly the canon's:
grade estimation -> category factors -> source blending -> weighted GM ->
evidence shrink -> spread -> missing penalty -> availability-first sort.

No invented data: unavailable metrics are missing/inapplicable, never zero.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# --- canon constants (mirrored for validation only; Misumi doc is canon) ----
W_GRADE = 1.0
W_RATING = 1.0
W_PRICE = 1.0
W_THC = 1.0
W_SI = 1.0
W_POPULARITY = 0.25
GAMMA = 6.0
SHRINK_PRIOR = 5.0
FACTOR_BAND = (0.5, 1.5)

GRADE_NUMERIC = {"A": 1.0, "AA": 2.0, "AA+": 2.5, "AAA": 3.0}

# Rarity-based estimates for otherwise-ungraded flower (canon section 4).
RARITY_GRADES = {
    "Stardawg": ("A", 1.0, 0.90),
    "Amnesia Haze": ("A", 1.0, 0.90),
    "Sundae Driver": ("AA", 2.0, 0.70),
    "Cookie Dawg": ("AA", 2.0, 0.75),
    "Mango Mirage": ("AA", 2.0, 0.30),
    "Gelato X Ice Cream Cake": ("AA+", 2.5, 0.45),
    "Vitamin Z": ("AA+", 2.5, 0.70),
    "Dante's Inferno": ("AA+", 2.5, 0.70),
    "Purple Octane": ("AA+", 2.5, 0.65),
}

# Metrics applicable per category; anything else is inapplicable (never a
# missing-data penalty). THC/Sativa-Indica apply to cannabis flower only in
# this model, because the sources only publish those there.
APPLICABLE = {
    "Cannabis flower": {"grade", "rating", "price", "thc", "si", "popularity"},
    "Hash and sift": {"grade", "rating", "price", "popularity"},
    "Other extracts": {"rating", "price", "popularity"},
    "Vapes": {"rating", "price", "popularity"},
    "Edibles": {"rating", "price", "popularity"},
    "Mushroom-related": {"rating", "price", "popularity"},
    "Mixed/miscellaneous": {"rating", "price", "popularity"},
}

_SIZE_GRAMS = [
    (re.compile(r"(\d+(?:\.\d+)?)\s*kg\b", re.I), 1000.0),
    (re.compile(r"(\d+(?:\.\d+)?)\s*mg\b", re.I), 0.001),
    (re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.I), 1.0),
]


def parse_quantity_grams(size_text: str) -> Optional[float]:
    """Grams implied by a size label, or None (packs/unknown are not grams)."""
    low = (size_text or "").lower().replace(",", ".")
    for rx, mult in _SIZE_GRAMS:
        m = rx.search(low)
        if m:
            return float(m.group(1)) * mult
    return None


def seller_grade_numeric(tier: Optional[str]) -> Optional[float]:
    if not tier:
        return None
    return GRADE_NUMERIC.get(tier.strip().upper())


@dataclass
class Factors:
    """Normalized, canon-shaped factor set for one record."""

    grade: Optional[Tuple[float, float]] = None  # (factor, confidence)
    rating: Optional[float] = None
    price: Optional[Tuple[float, str]] = None  # (factor, unit basis)
    thc: Optional[float] = None
    si: Optional[float] = None
    popularity: Optional[float] = None
    detail: Dict[str, Any] = field(default_factory=dict)


def _midrank_factor(values: List[float], index: int, confidence: float,
                    smaller_is_better: bool = False) -> float:
    """Canon section 3: tied midrank centred at 1 with shrinkage.

    f = 1 + confidence * (better + 0.5*equal - 0.5*N) / (N + 5)
    Single-peer data (N=1) yields exactly 1.0 (neutral), per canon.
    """
    n = len(values)
    if n <= 1:
        return 1.0  # canon: single defensible datum -> neutral factor
    v = values[index]
    if smaller_is_better:
        better = sum(1 for x in values if x > v)
        equal = sum(1 for x in values if x == v) - 1
    else:
        better = sum(1 for x in values if x < v)
        equal = sum(1 for x in values if x == v) - 1
    f = 1.0 + confidence * (better + 0.5 * equal - 0.5 * n) / (n + SHRINK_PRIOR)
    return max(FACTOR_BAND[0], min(FACTOR_BAND[1], f))


def combined_rating(leafly: Tuple[Optional[float], Optional[int]],
                    seller: Tuple[Optional[float], Optional[int]]
                    ) -> Tuple[Optional[float], Dict[str, Any]]:
    """Canon section 1.10: confidence/sample moderated blend; unrated != 0."""
    l_val, l_count = leafly
    s_val, s_count = seller
    # canon 1.10: a store average_rating of 0 with zero reviews is UNRATED
    if s_val is not None and not s_count and s_val == 0:
        s_val = None
    if l_val is not None and not l_count and l_val == 0:
        l_val = None
    detail: Dict[str, Any] = {
        "leafly_rating": l_val, "leafly_count": l_count,
        "seller_rating": s_val, "seller_count": s_count,
    }
    if l_val is None and s_val is None:
        return None, detail
    w_l = 0.0
    w_s = 0.0
    if l_val is not None and l_count:
        w_l = l_count / (l_count + SHRINK_PRIOR)
    if s_val is not None and s_count:
        w_s = s_count / (s_count + SHRINK_PRIOR)
    if l_val is not None and not l_count:
        w_l = 0.5 * (1 / (1 + SHRINK_PRIOR))  # rated but count unknown: low weight
    total = w_l + w_s
    if total <= 0:
        # a rating exists but has no defensible weight: treat as present, weak
        val = l_val if l_val is not None else s_val
        return val, {**detail, "weights": {"leafly": 0.0, "seller": 0.0},
                     "note": "no sample counts; unmoderated value retained in Details only"}
    blended = ((l_val or 0.0) * w_l + (s_val or 0.0) * w_s) / total
    detail["weights"] = {"leafly": w_l, "seller": w_s}
    return blended, detail


def unit_price(options: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[str], Dict[str, Any]]:
    """Canon section 2: min(price_j / size_j); excludes zero/unknown/malformed."""
    best: Optional[float] = None
    basis: Optional[str] = None
    excluded: List[str] = []
    for o in options or []:
        price = o.get("price")
        size = o.get("size") or ""
        if not price or price <= 0:
            excluded.append(f"{size}: zero/placeholder price")
            continue
        grams = parse_quantity_grams(size)
        if grams:
            eff = price / grams
            if best is None or eff < best:
                best, basis = eff, "per g"
        else:
            excluded.append(f"{size}: no parseable quantity")
    return best, basis, {"excluded_options": excluded}


def combined_popularity(leafly_count: Optional[int],
                        seller_rank: Optional[int], seller_total: int,
                        category: str,
                        cat_leafly_counts: List[Optional[int]],
                        cat_seller_ranks: List[Optional[int]]) -> Tuple[Optional[float], Dict[str, Any]]:
    """Canon section 1.11: separately normalized Leafly engagement and verified
    seller `orderby=popularity` ordinal, blended by geometric mean, then
    category-referenced. Seller rank 1 = most popular -> better."""
    detail: Dict[str, Any] = {"leafly_count": leafly_count,
                              "seller_rank": seller_rank, "seller_total": seller_total}
    lf: Optional[float] = None
    sf: Optional[float] = None
    lc = [c for c in (cat_leafly_counts or []) if c]
    if leafly_count and lc:
        lf = _midrank_factor([float(x) for x in lc], [float(x) for x in lc].index(float(leafly_count)), 0.7)
    rc = [r for r in (cat_seller_ranks or []) if r is not None]
    if seller_rank is not None and rc and len(rc) > 1:
        sf = _midrank_factor([float(x) for x in rc], [float(x) for x in rc].index(float(seller_rank)),
                             0.9, smaller_is_better=True)
    detail["leafly_factor"] = lf
    detail["seller_factor"] = sf
    if lf is None and sf is None:
        return None, detail
    if lf is None:
        return sf, detail
    if sf is None:
        return lf, detail
    return math.sqrt(lf * sf), detail


def composite_score(factors: Factors, category: str,
                    gamma: float = GAMMA) -> Dict[str, Any]:
    """Canon section 3 equation, exact order of operations."""
    applicable = APPLICABLE.get(category, {"rating", "price", "popularity"})
    weighted: List[Tuple[float, float]] = []
    def take(name: str, weight: float, value: Optional[Any]):
        if name in applicable and value is not None:
            weighted.append((weight, float(value)))
    take("grade", W_GRADE, factors.grade[0] if factors.grade else None)
    take("rating", W_RATING, factors.rating)
    take("price", W_PRICE, factors.price[0] if factors.price else None)
    take("thc", W_THC, factors.thc)
    take("si", W_SI, factors.si)
    take("popularity", W_POPULARITY, factors.popularity)

    present = {n for n, v in (
        ("grade", factors.grade), ("rating", factors.rating),
        ("price", factors.price), ("thc", factors.thc),
        ("si", factors.si), ("popularity", factors.popularity)) if v is not None}
    missing_applicable = sorted(applicable - present)

    w_sum = sum(w for w, _ in weighted)
    gm = (math.exp(sum(w * math.log(v) for w, v in weighted) / w_sum)
          if weighted and w_sum > 0 else 1.0)
    b = 0.5 + (gm - 1.0) * w_sum / (w_sum + 2.0)
    b = max(0.0, min(1.0, b))
    g = float(gamma)
    c = (b ** g) / (b ** g + (1.0 - b) ** g) if 0.0 < b < 1.0 else b
    m = len(missing_applicable)
    score = max(0.0, min(1.0, c * (0.8 ** max(0, m - 1))))
    return {
        "score": score,
        "percent": 100.0 * score,
        "gm": gm, "b": b, "c": c,
        "weights_used": w_sum,
        "factors_present": sorted(present),
        "missing_applicable": missing_applicable,
        "missing_penalty": 0.8 ** max(0, m - 1),
        "gamma": g,
    }


def apply_rarity_grade(records: List[Dict[str, Any]]) -> None:
    """Canon section 4: rarity-based estimate for ungraded flower, in place.
    Sets record['inferred_grade'] = {tier, numeric, confidence}; never touches
    a seller-reported grade."""
    for rec in records:
        if rec.get("category") != "Cannabis flower":
            continue
        if seller_grade_numeric(rec.get("seller_tier")) is not None:
            continue
        est = RARITY_GRADES.get(rec.get("product_name") or "")
        if est:
            tier, numeric, confidence = est
            rec["inferred_grade"] = {"tier": tier, "numeric": numeric,
                                     "confidence": confidence,
                                     "basis": "rarity/market-saturation estimate (canon section 4)"}


def build_factors(records: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Factors, Dict[str, Any]]]:
    """Category-relative factors for every record. Deterministic; ties handled
    with midranks; single-peer categories neutral."""
    apply_rarity_grade(records)
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        by_cat.setdefault(rec["category"], []).append(rec)

    out = []
    for cat, recs in by_cat.items():
        # category observation vectors
        grades = [(rec, (rec.get("inferred_grade") or {}).get("numeric")
                    if rec.get("inferred_grade") else seller_grade_numeric(rec.get("seller_tier")))
                  for rec in recs]
        gvals = [(rec, g) for rec, g in grades if g is not None]
        ratings = [(rec, rec.get("combined_rating")) for rec in recs]
        rvals = [(rec, v) for rec, v in ratings if v is not None]
        prices = [(rec, rec.get("unit_price")) for rec in recs]
        pvals = [(rec, v) for rec, v in prices if v is not None]
        leaf_counts = [rec.get("leafly_rating_count") for rec in recs]
        seller_ranks = [rec.get("seller_popularity_rank") for rec in recs]

        for rec in recs:
            f = Factors()
            conf = (rec.get("inferred_grade") or {}).get("confidence", 1.0) \
                if rec.get("inferred_grade") else 1.0
            if gvals:
                my_g = (rec.get("inferred_grade") or {}).get("numeric") \
                    if rec.get("inferred_grade") else seller_grade_numeric(rec.get("seller_tier"))
                if my_g is not None:
                    idx = [g for _, g in gvals].index(my_g)
                    f.grade = (_midrank_factor([g for _, g in gvals], idx, conf),
                               conf)
            if rvals and rec.get("combined_rating") is not None:
                idx = [v for _, v in rvals].index(rec["combined_rating"])
                f.rating = _midrank_factor([v for _, v in rvals], idx, 0.8)
            if pvals and rec.get("unit_price") is not None:
                idx = [v for _, v in pvals].index(rec["unit_price"])
                f.price = (_midrank_factor([v for _, v in pvals], idx, 0.9,
                                           smaller_is_better=True),
                           rec.get("unit_basis") or "per g")
            pop, pdet = combined_popularity(
                rec.get("leafly_rating_count"), rec.get("seller_popularity_rank"),
                len(seller_ranks), cat, leaf_counts, seller_ranks)
            f.popularity = pop
            f.detail = {"popularity": pdet}
            score = composite_score(f, cat)
            out.append((rec, f, score))
    return out


def sort_records(scored: List[Tuple[Dict[str, Any], Factors, Dict[str, Any]]]
                 ) -> List[Tuple[Dict[str, Any], Factors, Dict[str, Any]]]:
    """Canon section 1.5: availability first; then category, score DESC,
    minimum unit price ASC. Unbuyable/not-listed blocks at the bottom use the
    same inner ordering."""
    def block(rec):
        st = rec.get("buying_status") or "unknown"
        if st == "purchasable":
            return 0
        return 1  # out of stock / not listed / unknown all trail, retained

    def key(item):
        rec, _, score = item
        return (block(rec), rec.get("category", ""),
                -score["score"],
                rec.get("unit_price") if rec.get("unit_price") is not None else float("inf"))
    return sorted(scored, key=key)
