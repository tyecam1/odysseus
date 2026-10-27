"""Deterministic Green Team x Leafly product-comparison scoring engine.

Scoring implementation referring to the private preference contract:
`tyecam1/misumi:docs/preferences/green-team-leafly-product-comparison-v1.md`
(canonical blob 3ac07e494e5575d8a61c730956f04627169533a3, version 1).

Order of operations:
grade estimation -> category factors -> source blending -> weighted GM ->
evidence shrink -> spread -> missing penalty -> availability-first sort.

No invented data: unavailable metrics are missing/inapplicable, never zero.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

CANON_REF = {
    "repository": "tyecam1/misumi",
    "path": "docs/preferences/green-team-leafly-product-comparison-v1.md",
    "revision": "3ac07e494e5575d8a61c730956f04627169533a3",
}

# --- canon constants (mirrored for validation only; Misumi doc is canon) ----
W_GRADE = 1.0
W_RATING = 1.0
W_PRICE = 1.0
W_THC = 1.0
W_SI = 1.0
W_POPULARITY = 0.25
RATING_FACTOR_CONFIDENCE = 0.8  # canon rating-factor confidence at full identity confidence
GAMMA = 6.0
SHRINK_PRIOR = 5.0
FACTOR_BAND = (0.5, 1.5)

GRADE_NUMERIC = {"A": 1.0, "AA": 2.0, "AA+": 2.5, "AAA": 3.0}

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

SCORING_METHODOLOGY = {
    "weights": {"grade": W_GRADE, "rating": W_RATING, "price": W_PRICE,
                "thc": W_THC, "si": W_SI, "popularity": W_POPULARITY},
    "applicable": {category: sorted(metrics) for category, metrics in APPLICABLE.items()},
    "normalization": "1 + confidence*(worse_count + 0.5*equal_count - 0.5*N)/(N+5); equal_count includes self",
    "factor_band": FACTOR_BAND,
    "singletons_and_equal_peers": "neutral multiplier 1",
    "price_peers": "same category and explicit unit basis; lower is preferred",
    "flower_reference_factors": {
        "thc": "higher supplied Leafly cultivar-reference THC percentage; never a batch measurement",
        "si": "higher stated sativa share; if only indica is supplied, compare 100-indica without filling missing source fields",
        "validation": "finite numeric percentage points [0,100]; paired orientation percentages must sum to 100",
        "normalization_strength": "1; a ranking parameter, not a claim of source certainty",
        "peers": "available valid flower reference values only; absent values are never estimated",
    },
    "grade_policy": "optional private caller injection; no personal product table bundled",
    "GM": "exp(sum(weight*log(factor))/sum(weight)) over present applicable factors",
    "B": "clip(0.5+(GM-1)*sum(weight)/(sum(weight)+2),0,1)",
    "C": "B^gamma/(B^gamma+(1-B)^gamma)",
    "gamma": GAMMA,
    "score": "clip(C*0.8^max(0,missing_applicable_count-1),0,1)",
    "missing": "unavailable applicable metrics count as missing; inapplicable metrics do not",
    "sort": "purchasable first; then category, score descending, unit price ascending",
}

_SIZE_GRAMS = [
    (re.compile(r"(\d+(?:\.\d+)?)\s*kg\b", re.I), 1000.0),
    (re.compile(r"(\d+(?:\.\d+)?)\s*mg\b", re.I), 0.001),
    (re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.I), 1.0),
]


def parse_quantity_grams(size_text: str) -> Optional[float]:
    """Grams implied by a size label, or None (packs/unknown are not grams)."""
    if not isinstance(size_text, str):
        return None
    low = size_text.lower().replace(",", ".")
    for rx, mult in _SIZE_GRAMS:
        m = rx.search(low)
        if m:
            if m.start() and low[m.start() - 1] in "-+.0123456789":
                return None
            grams = float(m.group(1)) * mult
            return grams if math.isfinite(grams) and grams > 0 else None
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
        equal = sum(1 for x in values if x == v)
    else:
        better = sum(1 for x in values if x < v)
        equal = sum(1 for x in values if x == v)
    f = 1.0 + confidence * (better + 0.5 * equal - 0.5 * n) / (n + SHRINK_PRIOR)
    return max(FACTOR_BAND[0], min(FACTOR_BAND[1], f))


def combined_rating(leafly: Tuple[Optional[float], Optional[int]],
                    seller: Tuple[Optional[float], Optional[int]],
                    leafly_identity_confidence: float = 1.0,
                    seller_identity_confidence: float = 1.0,
                    ) -> Tuple[Optional[float], Dict[str, Any]]:
    """Canon section 1.10: confidence/sample moderated blend; unrated != 0.

    Identity confidence is distinct from review-count reliability: it is the
    caller's confidence that the cited source page is the same cultivar/product
    as the retail record (canon: never substitute an unsupported Leafly
    cultivar name as a verified rating). It scales the source's weight before
    count moderation and never changes an unblended single-source value's
    identity, only its blend weight. Each confidence must lie in [0, 1].
    """
    for name, conf in (("leafly", leafly_identity_confidence),
                       ("seller", seller_identity_confidence)):
        if not (isinstance(conf, (int, float)) and not isinstance(conf, bool)
                and 0.0 <= conf <= 1.0):
            raise ValueError(f"{name}_identity_confidence must be in [0, 1]")
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
        "leafly_identity_confidence": leafly_identity_confidence,
        "seller_identity_confidence": seller_identity_confidence,
    }
    if l_val is None and s_val is None:
        return None, detail
    w_l = 0.0
    w_s = 0.0
    if l_val is not None and l_count:
        w_l = (leafly_identity_confidence * l_count
               / (leafly_identity_confidence * l_count + SHRINK_PRIOR))
    if s_val is not None and s_count:
        w_s = (seller_identity_confidence * s_count
               / (seller_identity_confidence * s_count + SHRINK_PRIOR))
    if l_val is not None and not l_count:
        # rated but count unknown: low weight, scaled by identity confidence
        w_l = 0.5 * leafly_identity_confidence / (1 + SHRINK_PRIOR)
    # weight-weighted identity confidence of the sources actually blended;
    # a single present source carries its own confidence unchanged
    total = w_l + w_s
    if total > 0:
        detail["combined_identity_confidence"] = (
            (w_l * leafly_identity_confidence
             + w_s * seller_identity_confidence) / total)
    else:
        # no defensible weight: the retained value's own confidence still
        # governs how strongly its factor may deviate
        detail["combined_identity_confidence"] = (
            leafly_identity_confidence if l_val is not None
            else seller_identity_confidence)
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
    valid = []
    for index, o in enumerate(options or []):
        if not isinstance(o, dict):
            excluded.append(f"option {index}: malformed option")
            continue
        price = o.get("price")
        size = o.get("size") or ""
        if not _finite_number(price) or price <= 0:
            excluded.append(f"{size}: invalid, nonfinite or zero/placeholder price")
            continue
        grams = parse_quantity_grams(size)
        if grams:
            eff = price / grams
            if not math.isfinite(eff):
                excluded.append(f"{size}: nonfinite unit price")
                continue
            valid.append({"source_option_index": index, "quantity_grams": grams,
                          "unit_price": eff, "unit_basis": "per g"})
            if best is None or eff < best:
                best, basis = eff, "per g"
        else:
            excluded.append(f"{size}: no parseable quantity")
    return best, basis, {"excluded_options": excluded,
                         "source_options": options, "valid_options": valid}


def _finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _flower_reference_values(record: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Validate supplied reference percentages, without modifying source fields.

    Orientation is compared on the sativa axis. The complement of a supplied
    indica percentage is a comparison coordinate, never a new source datum.
    """
    def percentage(value):
        return value if _finite_number(value) and 0 <= value <= 100 else None

    thc = percentage(record.get("leafly_thc"))
    sativa = percentage(record.get("sativa_pct"))
    indica = percentage(record.get("indica_pct"))
    if sativa is not None and indica is not None:
        orientation = sativa if math.isclose(sativa + indica, 100, abs_tol=1e-6) else None
    elif sativa is not None:
        orientation = sativa
    elif indica is not None:
        orientation = 100 - indica
    else:
        orientation = None
    return thc, orientation


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
    if seller_rank is not None and rc:
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
                    gamma: float = GAMMA,
                    weight_overrides: Optional[Mapping[str, float]] = None
                    ) -> Dict[str, Any]:
    """Canon section 3 equation, exact order of operations.

    weight_overrides lets a caller (e.g. the live workbook recalculation
    check) recompute with different metric weights; canon defaults unchanged.
    """
    applicable = APPLICABLE.get(category, {"rating", "price", "popularity"})
    weights = {"grade": W_GRADE, "rating": W_RATING, "price": W_PRICE,
               "thc": W_THC, "si": W_SI, "popularity": W_POPULARITY}
    if weight_overrides:
        weights = {**weights, **weight_overrides}
    weighted: List[Tuple[float, float]] = []
    def take(name: str, value: Optional[Any]):
        if name in applicable and value is not None and weights[name]:
            weighted.append((weights[name], float(value)))
    take("grade", factors.grade[0] if factors.grade else None)
    take("rating", factors.rating)
    take("price", factors.price[0] if factors.price else None)
    take("thc", factors.thc)
    take("si", factors.si)
    take("popularity", factors.popularity)

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


def apply_rarity_grade(records: List[Dict[str, Any]],
                       rarity_policy: Optional[Mapping[str, Dict[str, Any]]] = None) -> None:
    """Apply an explicitly injected policy to ungraded flower only.

    No personal lookup is bundled. Entries contain tier, confidence and
    provenance; the caller owns loading the private policy. Seller grades take
    precedence. Inferred values retain their source and estimation basis.
    """
    for rec in records:
        if rec.get("category") != "Cannabis flower":
            continue
        if seller_grade_numeric(rec.get("seller_tier")) is not None:
            continue
        est = (rarity_policy or {}).get(rec.get("product_name") or "")
        if est is not None:
            numeric = seller_grade_numeric(est.get("tier"))
            confidence = est.get("confidence")
            if (numeric is None or not _finite_number(confidence)
                    or not 0 <= confidence <= 1 or not est.get("provenance")):
                raise ValueError("injected grade policy requires tier, confidence [0,1] and provenance")
            rec["inferred_grade"] = {**est, "numeric": numeric,
                                     "basis": est.get("basis", "injected rarity estimate")}


def _effective_grade(rec: Dict[str, Any]) -> Tuple[Optional[float], float]:
    """Prefer reported grades while retaining any inference as raw audit data."""
    reported = seller_grade_numeric(rec.get("seller_tier"))
    if reported is not None:
        return reported, 1.0
    inferred = rec.get("inferred_grade") or {}
    return inferred.get("numeric"), inferred.get("confidence", 1.0)


def attach_combined_inputs(records: List[Dict[str, Any]]) -> None:
    """Caller-owned preflight: populate rec["combined_rating"] from raw Leafly
    and seller rating fields (canon section 1.10) when not already set.

    Callers generating the workbook must invoke this before build_factors;
    the raw-snapshot join itself stays caller-owned so no dataset-specific
    logic is bundled here. Unrated values (average_rating 0 with zero
    reviews) stay unrated. Both `seller_rating_count` and the workbook
    schema's `seller_review_count` field names are accepted.

    Note build_factors itself only stays non-mutating when no rarity_policy
    is injected; an injected policy records rec["inferred_grade"] by design.
    """
    for rec in records:
        if rec.get("combined_rating") is not None:
            continue
        if (rec.get("leafly_rating") is None
                and rec.get("seller_rating") is None):
            continue
        blended, detail = combined_rating(
            (rec.get("leafly_rating"), rec.get("leafly_rating_count")),
            (rec.get("seller_rating"),
             rec.get("seller_rating_count",
                     rec.get("seller_review_count"))),
            rec.get("leafly_identity_confidence", 1.0),
            rec.get("seller_identity_confidence", 1.0))
        rec["combined_rating"] = blended
        rec["combined_rating_detail"] = detail


def build_factors(records: List[Dict[str, Any]], *,
                  rarity_policy: Optional[Mapping[str, Dict[str, Any]]] = None
                  ) -> List[Tuple[Dict[str, Any], Factors, Dict[str, Any]]]:
    """Category-relative factors for every record. Deterministic; ties handled
    with midranks; single-peer categories neutral."""
    apply_rarity_grade(records, rarity_policy)
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        by_cat.setdefault(rec["category"], []).append(rec)

    out = []
    for cat, recs in by_cat.items():
        # category observation vectors
        grades = [_effective_grade(rec) for rec in recs]
        gvals = [g for g, _ in grades if g is not None]
        ratings = [(rec, rec.get("combined_rating")) for rec in recs]
        rvals = [(rec, v) for rec, v in ratings if v is not None]
        prices_by_basis: Dict[str, List[float]] = {}
        for rec in recs:
            price, basis = rec.get("unit_price"), rec.get("unit_basis")
            if _finite_number(price) and price > 0 and isinstance(basis, str) and basis.strip():
                prices_by_basis.setdefault(basis, []).append(price)
        leaf_counts = [rec.get("leafly_rating_count") for rec in recs]
        seller_ranks = [rec.get("seller_popularity_rank") for rec in recs]
        reference_values = [_flower_reference_values(rec) for rec in recs] if cat == "Cannabis flower" else []
        thc_peers = [thc for thc, _ in reference_values if thc is not None]
        orientation_peers = [si for _, si in reference_values if si is not None]

        for rec, (my_g, conf) in zip(recs, grades):
            f = Factors()
            if my_g is not None:
                f.grade = (_midrank_factor(gvals, gvals.index(my_g), conf), conf)
            if rvals and rec.get("combined_rating") is not None:
                idx = [v for _, v in rvals].index(rec["combined_rating"])
                # canon 3 confidence-shrink, as for grades: the rating
                # factor's deviation is scaled by the identity confidence
                # of the sources behind the combined rating, so a likely
                # wrong-cultivar rating relaxes toward neutral while the
                # raw star value and provenance stay in Details
                rating_conf = min(1.0, RATING_FACTOR_CONFIDENCE * rec.get(
                    "combined_rating_detail",
                    {}).get("combined_identity_confidence", 1.0))
                f.rating = _midrank_factor([v for _, v in rvals], idx,
                                           rating_conf)
            price, basis = rec.get("unit_price"), rec.get("unit_basis")
            pvals = prices_by_basis.get(basis, []) if isinstance(basis, str) else []
            if pvals and _finite_number(price) and price > 0:
                f.price = (_midrank_factor(pvals, pvals.index(price), 0.9,
                                           smaller_is_better=True), basis)
            pop, pdet = combined_popularity(
                rec.get("leafly_rating_count"), rec.get("seller_popularity_rank"),
                len(seller_ranks), cat, leaf_counts, seller_ranks)
            f.popularity = pop
            f.detail = {"popularity": pdet,
                        "price": {"raw_value": price, "unit_basis": basis,
                                  "peer_values": pvals, "confidence": 0.9,
                                  "excluded_reason": None if f.price else
                                  "missing/invalid positive price or explicit unit basis"}}
            if cat == "Cannabis flower":
                thc, orientation = _flower_reference_values(rec)
                for name, value, peers, raw in (
                    ("thc", thc, thc_peers, {"leafly_thc": rec.get("leafly_thc")}),
                    ("si", orientation, orientation_peers,
                     {"sativa_pct": rec.get("sativa_pct"), "indica_pct": rec.get("indica_pct")}),
                ):
                    if value is not None:
                        setattr(f, name, _midrank_factor(peers, peers.index(value), 1.0))
                    f.detail[name] = {
                        "raw_values": raw, "comparison_value": value, "peer_values": peers,
                        "normalization_strength": 1.0,
                        "evidence_class": "cultivar_reference" if name == "thc" else "source_orientation",
                        "source": rec.get("primary_leafly_source"),
                        "basis": SCORING_METHODOLOGY["flower_reference_factors"][name],
                        "excluded_reason": None if value is not None else
                        "missing/invalid reference percentage or inconsistent orientation pair",
                    }
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
