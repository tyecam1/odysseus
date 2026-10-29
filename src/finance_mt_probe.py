"""Deterministic MT-00 public-source market/media trend probe.

Task card ``agent-tasks/inbox/finance-market-media-intelligence-2026-10-29.md``
(canonical spec ``misumi/docs/core/finance-market-media-trend-goals-v0.1.md``,
goal MT-00). Collects one bounded, timestamped snapshot from public
official sources only, emits records in the shared evidence contract and a
compact digest. This module is collection only: it never interprets,
hypothesises or recommends — interpretation is reserved for persona L.

Design rules (spec):
- public official sources only: GDELT DOC 2.0, Hacker News official API,
  public exchange spot candles (Kraken public REST, no auth);
- excluded upstreams (X cookies, private Reddit, YouTube internals,
  retailer scraping, paid APIs) are not implemented at all;
- every observation carries published_at, first_seen_at and collected_at
  distinctly. published_at is set ONLY when the source itself provides a
  verified publisher timestamp (HN item time, exchange candle open):
  GDELT's ``seendate`` is the monitor's retrieval time, not a publication
  time, so GDELT records carry published_at = null with the seendate
  recorded in ``uncertainty`` — never inferred. Syndicated copies are
  deduplicated (exact URL, then registrable-domain + normalised title,
  so m.example.co.uk and www.example.co.uk are ONE story) and counted as
  ONE source per registrable domain, never as independent corroboration;
- bounded retries with backoff; no background scheduling, no persistence
  beyond the out-dir snapshot files.

stdlib-only on purpose (leafly precedent): no new runtime dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse

PROBE_NAME = "finance-mt-probe"
PROBE_VERSION = "0.4"
USER_AGENT = (
    f"{PROBE_NAME}/{PROBE_VERSION} (odysseus finance MT-00; "
    "household research, read-only public APIs; github.com/tyecam1)"
)

SOURCE_GDELT = "gdelt-doc-2.0"
SOURCE_HN = "hackernews-official"
SOURCE_KRAKEN = "kraken-public-spot"

GDELT_URL = (
    "https://api.gdeltproject.org/api/v2/doc/doc"
    "?query={query}&mode=artlist&maxrecords={max_records}&format=json&sort=datedesc"
)
HN_TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
KRAKEN_OHLC_URL = (
    "https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
)

SOURCE_ACCESS_RIGHTS = {
    SOURCE_GDELT: (
        "public-official-api;no-auth;no-key;rate-limit-respected;research use; "
        "full text not republished, only URLs/metadata/timestamps retained"
    ),
    SOURCE_HN: (
        "public-official-api (github.com/HackerNews/API);no-auth;no-key; "
        "fetched item metadata only"
    ),
    SOURCE_KRAKEN: (
        "public-official-rest (api.kraken.com public market data);no-auth; "
        "no trading credential;public rate limit respected"
    ),
}

# The shared evidence contract, verbatim field set from the canonical spec.
EVIDENCE_FIELDS = [
    "event_id",
    "topic_id",
    "market_entity",
    "source",
    "source_url",
    "published_at",
    "first_seen_at",
    "collected_at",
    "geography",
    "raw_metric",
    "normalized_metric",
    "window",
    "sampling_bias",
    "source_access_rights",
    "source_health",
    "uncertainty",
    "hypothesis_id",
    "link_to_market_candles",
]

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")
_MAX_TITLE_WORDS = 12

# Common multi-part public suffixes where the registrable domain is the
# last THREE labels (example.co.uk, not co.uk). Not a full Public Suffix
# List: an unlisted multi-part suffix UNDER-counts diversity (two
# distinct publishers collapse to one label) — conservative for
# corroboration, never an overstatement of it.
MULTI_PART_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au",
    "co.jp", "ne.jp", "or.jp", "co.kr", "or.kr", "go.kr", "com.br",
    "com.mx", "com.ar", "com.pe", "com.uy", "com.vn", "com.cn", "com.tw",
    "com.hk", "com.sg", "com.my", "com.ph", "co.id", "co.il", "co.nz",
    "co.za", "co.in", "com.tr", "com.ua", "com.gr", "com.pl", "co.th",
}


class SourceUnavailableError(RuntimeError):
    """A public source failed its bounded retry budget."""


@dataclass
class EvidenceRecord:
    event_id: str
    topic_id: str
    source: str
    source_url: str
    published_at: Optional[str]  # None unless the source itself provides one
    first_seen_at: str
    collected_at: str
    window: str
    source_access_rights: str
    source_health: str
    market_entity: Optional[str] = None
    geography: Optional[str] = None
    raw_metric: Optional[float] = None
    normalized_metric: Optional[float] = None
    sampling_bias: Optional[str] = None
    uncertainty: Optional[str] = None
    hypothesis_id: Optional[str] = None
    link_to_market_candles: Optional[str] = None

    def to_contract(self) -> Dict[str, Any]:
        data = asdict(self)
        return {name: data.get(name) for name in EVIDENCE_FIELDS}


@dataclass
class SourceResult:
    source: str
    status: str  # ok | failed
    records: List[EvidenceRecord] = field(default_factory=list)
    http_status: Optional[int] = None
    retries: int = 0
    error: Optional[str] = None
    deduped_exact: int = 0
    deduped_syndication: int = 0


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_event_id(source: str, source_url: str) -> str:
    digest = hashlib.sha256(f"{source}|{source_url}".encode("utf-8")).hexdigest()
    return digest[:16]


def _canonical_host(host: str) -> str:
    """Canonical hostname form: percent-decoded, lowercased, trailing
    dot stripped, and non-ASCII labels IDNA-encoded — so ``bücher.de``,
    ``BÜCHER.de.`` and ``xn--bcher-kva.de`` all collapse to one
    publisher instead of counting as two domains."""
    host = (host or "").strip()
    try:
        host = unquote(host)
    except Exception:
        pass  # keep the raw form; still canonicalised below
    host = host.lower().strip().rstrip(".")
    if host and not host.isascii():
        try:
            host = host.encode("idna").decode("ascii")
        except Exception:
            pass  # odd unicode input: fall through on the raw form
    return host


def registrable_domain(url: str) -> str:
    """Registrable domain of a URL or bare hostname (GDELT's ``domain``
    field is a bare host, possibly with a port). Handles common
    multi-part public suffixes so that m.example.co.uk and
    www.example.co.uk collapse to example.co.uk while two different
    .co.uk publishers stay distinct, and canonicalises the host (case,
    trailing dot, percent-encoding, IDN/punycode) so one publisher's
    Unicode and ASCII hostname spellings count as ONE domain. Not a
    full Public Suffix List — see MULTI_PART_SUFFIXES for the documented
    failure direction.

    Known residual (documented, deliberate): redirector/launcher hosts
    (e.g. news.google.com → publisher) still count as their own domains;
    resolving them would require fetching every article URL, which this
    probe does not do. Diversity counts may therefore overstate when a
    story is syndicated via redirector links — interpretation stays with
    persona L."""
    host = _canonical_host(urlparse(url).hostname or "")
    if not host:
        host = (url or "").strip()
        if "://" in host:
            host = host.split("://", 1)[1]
        host = host.split("/", 1)[0]
    # tolerate user:pass@ and :port in bare-host input
    host = _canonical_host(host.split("@")[-1].split(":")[0])
    parts = [p for p in host.split(".") if p]
    if not parts:
        return "unknown"
    last_two = ".".join(parts[-2:]) if len(parts) >= 2 else ""
    if last_two in MULTI_PART_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return last_two
    return host


def normalize_title(title: str) -> str:
    text = _PUNCT_RE.sub(" ", (title or "").lower())
    text = _WS_RE.sub(" ", text).strip()
    return " ".join(text.split()[:_MAX_TITLE_WORDS])


def parse_gdelt_seen(seendate: str) -> Optional[str]:
    # GDELT format 20261029T120000Z -> ISO-8601
    match = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$", seendate or "")
    if not match:
        return None
    y, m, d, hh, mm, ss = match.groups()
    return f"{y}-{m}-{d}T{hh}:{mm}:{ss}Z"


def http_get_json(
    url: str,
    *,
    timeout_s: float = 30.0,
    retries: int = 3,
    backoff_base_s: float = 4.0,
    fetch: Optional[Callable[[str, float], Any]] = None,
) -> Tuple[Any, int, int]:
    """Bounded GET with exponential backoff. ``fetch`` is injectable for
    offline tests (returns a JSON-decodable payload or raises)."""
    last_error: Optional[Exception] = None
    attempt = 0
    for attempt in range(1, retries + 1):
        try:
            if fetch is not None:
                payload = fetch(url, timeout_s)
                return payload, 200, attempt - 1
            req = urllib_request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib_request.urlopen(req, timeout=timeout_s) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body), resp.status, attempt - 1
        except HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(backoff_base_s * (2 ** (attempt - 1)))
    raise SourceUnavailableError(f"{url}: {last_error} after {retries} attempts")


# --------------------------------------------------------------------------
# source collectors
# --------------------------------------------------------------------------

def collect_gdelt(
    query: str,
    *,
    max_records: int = 75,
    collected_at: str,
    first_seen_index: Dict[str, str],
    fetch: Optional[Callable] = None,
    retries: int = 3,
) -> SourceResult:
    url = GDELT_URL.format(
        query=query.replace(" ", "%20"), max_records=max_records
    )
    try:
        payload, status, used_retries = http_get_json(
            url, retries=retries, fetch=fetch
        )
    except SourceUnavailableError as exc:
        return SourceResult(SOURCE_GDELT, "failed", error=str(exc))

    articles = (payload or {}).get("articles") or []
    records: List[EvidenceRecord] = []
    seen_urls = set()
    seen_stories = set()  # (registrable domain, normalised title)
    deduped = 0
    deduped_syndication = 0
    topic_id = f"gdelt:{normalize_title(query)[:40]}"
    for art in articles:
        source_url = art.get("url") or ""
        if not source_url or source_url in seen_urls:
            deduped += 1
            continue
        seen_urls.add(source_url)
        # Never trust the raw host string for diversity counting:
        # normalise to the registrable domain so m./www. mirrors of one
        # publisher are one source, and count the story once per
        # registrable domain even when the URL differs. The URL host is
        # the authority — GDELT's free-text ``domain`` metadata is only a
        # fallback when the URL carries no parseable dotted host, so a
        # spoofed/absent metadata field can neither merge two distinct
        # publishers nor split one.
        domain = registrable_domain(source_url)
        if "." not in domain:
            domain = registrable_domain(art.get("domain") or "")
        story_key = (domain, normalize_title(art.get("title") or ""))
        if story_key in seen_stories:
            deduped_syndication += 1
            continue
        seen_stories.add(story_key)
        seen_iso = parse_gdelt_seen(art.get("seendate", ""))
        event_id = stable_event_id(SOURCE_GDELT, source_url)
        records.append(
            EvidenceRecord(
                event_id=event_id,
                topic_id=topic_id,
                source=f"{SOURCE_GDELT}:{domain}",
                source_url=source_url,
                published_at=None,
                first_seen_at=first_seen_index.get(event_id, collected_at),
                collected_at=collected_at,
                geography=art.get("sourcecountry") or None,
                raw_metric=1.0,
                sampling_bias=(
                    "GDELT covers a sample of global news monitoring; "
                    "syndication counted once per registrable domain; volume "
                    "is media attention, not demand"
                ),
                source_access_rights=SOURCE_ACCESS_RIGHTS[SOURCE_GDELT],
                source_health=(
                    f"http 200; retries={used_retries}; articles={len(articles)}"
                ),
                uncertainty=(
                    "high (single-source sample; GDELT seendate "
                    f"{seen_iso or art.get('seendate') or 'unknown'} is the "
                    "monitor's retrieval timestamp, not a verified publisher "
                    "timestamp — published_at is unknown for this source)"
                ),
                window=collected_at[:10],
            )
        )
    return SourceResult(
        SOURCE_GDELT, "ok", records, http_status=status, retries=used_retries,
        deduped_exact=deduped, deduped_syndication=deduped_syndication,
    )


def collect_hackernews(
    *,
    top_n: int = 25,
    collected_at: str,
    first_seen_index: Dict[str, str],
    fetch: Optional[Callable] = None,
    retries: int = 3,
) -> SourceResult:
    def item_url(item_id: int) -> str:
        return HN_ITEM_URL.format(item_id=item_id)

    try:
        ids, status, used_retries = http_get_json(
            HN_TOPSTORIES_URL, retries=retries, fetch=fetch
        )
    except SourceUnavailableError as exc:
        return SourceResult(SOURCE_HN, "failed", error=str(exc))
    if not isinstance(ids, list):
        return SourceResult(SOURCE_HN, "failed", error="topstories payload not a list")

    records: List[EvidenceRecord] = []
    errors = 0
    for item_id in ids[:top_n]:
        try:
            item, _, _ = http_get_json(item_url(int(item_id)), retries=1, fetch=fetch)
        except (SourceUnavailableError, ValueError, TypeError):
            errors += 1
            continue
        if not isinstance(item, dict) or item.get("title") is None:
            continue
        source_url = (
            item.get("url")
            or f"https://news.ycombinator.com/item?id={item_id}"
        )
        event_id = stable_event_id(SOURCE_HN, str(item_id))
        published = (
            iso(datetime.fromtimestamp(item["time"], tz=timezone.utc))
            if item.get("time")
            else None
        )
        records.append(
            EvidenceRecord(
                event_id=event_id,
                topic_id="hn:frontpage",
                source=f"{SOURCE_HN}:news.ycombinator.com",
                source_url=source_url,
                published_at=published,
                first_seen_at=first_seen_index.get(event_id, collected_at),
                collected_at=collected_at,
                raw_metric=float(item.get("score") or 0),
                sampling_bias=(
                    "HN front page skews tech-adjacent attention; score is "
                    "platform engagement, not demand"
                ),
                source_access_rights=SOURCE_ACCESS_RIGHTS[SOURCE_HN],
                source_health=(
                    f"topstories http {status}; items fetched={len(records) + 1};"
                    f" item errors={errors}"
                ),
                uncertainty="medium (scores self-selected by community voting)",
                window=collected_at[:10],
            )
        )
    return SourceResult(
        SOURCE_HN, "ok" if records else "failed", records,
        http_status=status, retries=used_retries,
        error=None if records else "no items",
    )


def collect_kraken(
    *,
    pair: str = "BTCUSD",
    interval_min: int = 60,
    keep_candles: int = 24,
    collected_at: str,
    first_seen_index: Optional[Dict[str, str]] = None,
    fetch: Optional[Callable] = None,
    retries: int = 3,
) -> Tuple[SourceResult, Dict[str, Any]]:
    url = KRAKEN_OHLC_URL.format(pair=pair, interval=interval_min)
    try:
        payload, status, used_retries = http_get_json(url, retries=retries, fetch=fetch)
    except SourceUnavailableError as exc:
        return SourceResult(SOURCE_KRAKEN, "failed", error=str(exc)), {}

    errors = (payload or {}).get("error") or []
    if errors:
        return SourceResult(
            SOURCE_KRAKEN, "failed", http_status=status, retries=used_retries,
            error=f"kraken error payload: {errors}",
        ), {}
    result = (payload or {}).get("result") or {}
    candles: List[List[Any]] = []
    result_key = None
    for key, value in result.items():
        if key == "last" or not isinstance(value, list):
            continue
        candles = value
        result_key = key
        break
    if not result_key:
        return SourceResult(
            SOURCE_KRAKEN, "failed", http_status=status, retries=used_retries,
            error="no OHLC series in result",
        ), {}

    candles = candles[-keep_candles:]
    first_seen_index = first_seen_index or {}
    market_pair = f"{pair[:3]}/{pair[3:]}" if len(pair) == 6 else pair
    max_volume = max((float(c[6]) for c in candles), default=0.0) or 1.0
    records: List[EvidenceRecord] = []
    for candle in candles:
        ts = iso(datetime.fromtimestamp(int(candle[0]), tz=timezone.utc))
        event_id = stable_event_id(SOURCE_KRAKEN, f"{result_key}:{candle[0]}")
        volume = float(candle[6])
        records.append(
            EvidenceRecord(
                event_id=event_id,
                topic_id=f"kraken:{result_key}",
                market_entity=market_pair,
                source=SOURCE_KRAKEN,
                source_url=url.split("?")[0] + f"?pair={pair}&interval={interval_min}",
                published_at=ts,
                first_seen_at=first_seen_index.get(event_id, collected_at),
                collected_at=collected_at,
                raw_metric=volume,
                normalized_metric=round(volume / max_volume, 6),
                sampling_bias="single exchange spot volume; not global market depth",
                source_access_rights=SOURCE_ACCESS_RIGHTS[SOURCE_KRAKEN],
                source_health=f"http {status}; retries={used_retries}; candles={len(candles)}",
                uncertainty="low (official exchange public data)",
                link_to_market_candles=f"kraken:{result_key}:{candle[0]}",
                window=f"{ts[:10]}",
            )
        )
    summary = {
        "pair_requested": pair,
        "pair_returned": result_key,
        "interval_minutes": interval_min,
        "candles": len(candles),
        "oldest": records[0].published_at if records else None,
        "newest": records[-1].published_at if records else None,
        "last_close": float(candles[-1][4]) if candles else None,
        "last_volume": float(candles[-1][6]) if candles else None,
    }
    return SourceResult(
        SOURCE_KRAKEN, "ok", records, http_status=status, retries=used_retries
    ), summary


# --------------------------------------------------------------------------
# aggregation / digest
# --------------------------------------------------------------------------

def aggregate_topics(records: List[EvidenceRecord]) -> List[Dict[str, Any]]:
    by_topic: Dict[str, List[EvidenceRecord]] = {}
    for rec in records:
        by_topic.setdefault(rec.topic_id, []).append(rec)
    topics = []
    for topic_id, recs in by_topic.items():
        domains = {
            rec.source.split(":", 1)[1] if ":" in rec.source else rec.source
            for rec in recs
            if not rec.topic_id.startswith("kraken:")
        }
        first_seen = min(
            (r.first_seen_at for r in recs if r.first_seen_at), default=None
        )
        published = sorted(
            {r.published_at[:10] for r in recs if r.published_at}
        )
        topics.append(
            {
                "topic_id": topic_id,
                "records": len(recs),
                "distinct_domains": len(domains),
                "domains": sorted(domains),
                "first_seen_at": first_seen,
                "published_days": published,
                "attention_velocity_per_day": round(len(recs) / max(len(published), 1), 3),
                "sampling_bias": recs[0].sampling_bias,
                "uncertainty": recs[0].uncertainty,
                "hypothesis_id": None,
                "interpretation": "reserved for persona L (not determined by probe)",
            }
        )
    topics.sort(key=lambda t: (-t["distinct_domains"], -t["records"]))
    return topics


def build_report(
    collected_at: str,
    results: List[SourceResult],
    market_context: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    records = [r for res in results for r in res.records]
    topics = aggregate_topics(records)
    prev_report = (previous or {}).get("report") or previous or {}
    baseline_note = (
        "no prior snapshot (first collection); baseline comparison unavailable"
        if not previous
        else f"baseline snapshot {previous.get('generated_at')} "
        f"({len(prev_report.get('topics') or [])} topics)"
    )
    return {
        "probe": PROBE_NAME,
        "probe_version": PROBE_VERSION,
        "generated_at": collected_at,
        "params": params,
        "source_results": [
            {
                "source": res.source,
                "status": res.status,
                "records": len(res.records),
                "http_status": res.http_status,
                "retries": res.retries,
                "deduped_exact": res.deduped_exact,
                "deduped_syndication": res.deduped_syndication,
                "error": res.error,
            }
            for res in results
        ],
        "topics": topics,
        "market_context": market_context,
        "baseline": baseline_note,
        "comparators": (
            "source diversity = distinct registrable domains; syndicated "
            "duplicates deduplicated; naive keyword alert = single-source count"
        ),
        "excluded_sources": [
            "x-cookies", "private-reddit", "youtube-internal",
            "retailer-scraping", "paid-apis",
        ],
    }


def render_digest_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# MT-00 trend probe digest — {report['generated_at']}")
    lines.append("")
    lines.append(
        f"Probe `{report['probe']}` v{report['probe_version']}. "
        "Collection only — interpretation, hypotheses and recommendations are "
        "reserved for persona L. Source diversity counts distinct registrable "
        "domains; syndication is never counted as independent corroboration."
    )
    lines.append("")
    lines.append("## Source health")
    lines.append("")
    lines.append(
        "| source | status | records | retries | deduped | synd-deduped | error |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for res in report["source_results"]:
        lines.append(
            f"| {res['source']} | {res['status']} | {res['records']} "
            f"| {res['retries']} | {res['deduped_exact']} "
            f"| {res['deduped_syndication']} | {res['error'] or ''} |"
        )
    lines.append("")
    lines.append("## Attention (top topics by distinct-domain diversity)")
    lines.append("")
    lines.append(
        "| topic | records | distinct domains | first seen | velocity/day |"
        " uncertainty |"
    )
    lines.append("|---|---|---|---|---|---|")
    for topic in report["topics"][:5]:
        lines.append(
            f"| `{topic['topic_id']}` | {topic['records']} "
            f"| {topic['distinct_domains']} | {topic['first_seen_at']} "
            f"| {topic['attention_velocity_per_day']} | {topic['uncertainty']} |"
        )
    lines.append("")
    if report.get("market_context"):
        ctx = report["market_context"]
        lines.append("## Market context (public exchange candles)")
        lines.append("")
        lines.append(
            f"- {ctx.get('pair_returned')}: {ctx.get('candles')} candles "
            f"({ctx.get('interval_minutes')}m), {ctx.get('oldest')} → "
            f"{ctx.get('newest')}, last close {ctx.get('last_close')}, "
            f"last volume {ctx.get('last_volume')}"
        )
        lines.append("")
    lines.append(f"Baseline: {report['baseline']}")
    lines.append("")
    lines.append(
        "Excluded by policy: " + ", ".join(report["excluded_sources"]) + "."
    )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# snapshot persistence (append-only out-dir)
# --------------------------------------------------------------------------

def _load_snapshot_json(path: Path) -> Dict[str, Any]:
    """Load a snapshot JSON object. A corrupt/truncated snapshot is a
    LOST-EVIDENCE event, never a skip: raising (fail closed) forces
    repair of the file instead of silently resetting every first-seen
    time it carried."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"corrupt evidence snapshot {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"evidence snapshot {path.name} is not a JSON object")
    return data


def load_first_seen_index(out_dir: Path) -> Tuple[Dict[str, str], Optional[Dict[str, Any]]]:
    """First-seen map merged across EVERY snapshot in out_dir (earliest
    wins), plus the latest snapshot for baseline comparison. Reading
    only latest.json would lose first-seen times whenever a run's source
    selection omits a source (e.g. an intervening no-Kraken run would
    reset candle first_seen times); the full scan makes the index
    monotone across source-selection changes. Corrupt history (any
    snapshot, or latest.json) raises ValueError — it must never be
    quietly treated as "no history", which would reset first-seen
    times without a trace."""
    latest = out_dir / "latest.json"
    previous: Optional[Dict[str, Any]] = None
    if latest.exists():
        previous = _load_snapshot_json(latest)

    def merge_into(index: Dict[str, str], data: Dict[str, Any], name: str) -> None:
        # Structural validation: a snapshot whose records are missing,
        # not a list, or contain non-object / identity-less entries is a
        # LOST-EVIDENCE event exactly like a corrupt file — skipping it
        # (or crashing on it) would silently drop or destroy first-seen
        # history, so it fails closed with a ValueError.
        records = data.get("records")
        if not isinstance(records, list):
            raise ValueError(
                f"evidence snapshot {name} has no records list"
            )
        for i, rec in enumerate(records):
            if not isinstance(rec, dict):
                raise ValueError(
                    f"evidence snapshot {name}: record #{i} is not an object"
                )
            event_id = rec.get("event_id")
            first_seen = rec.get("first_seen_at")
            if not isinstance(event_id, str) or not event_id:
                raise ValueError(
                    f"evidence snapshot {name}: record #{i} has no event_id"
                )
            if not isinstance(first_seen, str) or not first_seen:
                raise ValueError(
                    f"evidence snapshot {name}: record #{i} has no "
                    "first_seen_at"
                )
            current = index.get(event_id)
            if current is None or first_seen < current:
                index[event_id] = first_seen

    index: Dict[str, str] = {}
    for snapshot_path in sorted(out_dir.glob("snapshot-*.json")):
        merge_into(index, _load_snapshot_json(snapshot_path), snapshot_path.name)
    if previous:
        merge_into(index, previous, "latest.json")
    return index, previous


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_snapshot(
    out_dir: Path,
    report: Dict[str, Any],
    results: List[SourceResult],
    code_file: Path,
) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = report["generated_at"].replace(":", "").replace("-", "")
    records = [rec.to_contract() for res in results for rec in res.records]
    snapshot = {
        "generated_at": report["generated_at"],
        "report": report,
        "records": records,
    }
    snapshot_path = out_dir / f"snapshot-{stamp}.json"
    snapshot_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    digest_path = out_dir / f"digest-{stamp}.md"
    digest_path.write_text(render_digest_markdown(report), encoding="utf-8")
    manifest = {
        "probe": PROBE_NAME,
        "probe_version": PROBE_VERSION,
        "generated_at": report["generated_at"],
        "code_sha256": sha256_file(code_file),
        "params": report["params"],
        "snapshot": snapshot_path.name,
        "snapshot_sha256": sha256_file(snapshot_path),
        "digest": digest_path.name,
        "digest_sha256": sha256_file(digest_path),
        "source_status": report["source_results"],
    }
    manifest_path = out_dir / f"run-manifest-{stamp}.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "latest.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {
        "snapshot": str(snapshot_path),
        "digest": str(digest_path),
        "manifest": str(manifest_path),
        "manifest_json": manifest,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def run_probe(args: argparse.Namespace, code_file: Path) -> int:
    collected = iso(utc_now())
    out_dir = Path(args.out_dir)
    try:
        first_seen_index, previous = load_first_seen_index(out_dir)
    except ValueError as exc:
        # fail closed: running over unreadable history would silently
        # reset every first-seen time the corrupt file carried
        print(json.dumps(
            {
                "ok": False,
                "fail_closed": True,
                "error": f"refusing to run over unreadable history: {exc}",
            }, indent=2,
        ))
        return 2
    results: List[SourceResult] = []
    market_context: Dict[str, Any] = {}

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    if SOURCE_GDELT in sources:
        results.append(
            collect_gdelt(
                args.gdelt_query,
                max_records=args.max_records,
                collected_at=collected,
                first_seen_index=first_seen_index,
                retries=args.retries,
            )
        )
    if SOURCE_HN in sources:
        results.append(
            collect_hackernews(
                top_n=args.hn_top,
                collected_at=collected,
                first_seen_index=first_seen_index,
                retries=args.retries,
            )
        )
    if SOURCE_KRAKEN in sources:
        kraken_result, market_context = collect_kraken(
            pair=args.kraken_pair,
            interval_min=args.kraken_interval,
            keep_candles=args.kraken_candles,
            collected_at=collected,
            first_seen_index=first_seen_index,
            retries=args.retries,
        )
        results.append(kraken_result)

    params = {
        "sources": sources,
        "gdelt_query": args.gdelt_query,
        "max_records": args.max_records,
        "hn_top": args.hn_top,
        "kraken_pair": args.kraken_pair,
        "kraken_interval": args.kraken_interval,
        "kraken_candles": args.kraken_candles,
        "retries": args.retries,
    }
    report = build_report(collected, results, market_context, previous, params)
    paths = write_snapshot(out_dir, report, results, code_file)
    healthy = sum(1 for res in results if res.status == "ok")
    print(
        json.dumps(
            {
                "ok": healthy > 0,
                "healthy_sources": healthy,
                "total_sources": len(results),
                "records": sum(len(res.records) for res in results),
                "topics": len(report["topics"]),
                "manifest": paths["manifest"],
                "snapshot": paths["snapshot"],
                "digest": paths["digest"],
            },
            indent=2,
        )
    )
    return 0 if healthy > 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROBE_NAME,
        description="MT-00 bounded public-source trend probe (collection only)",
    )
    parser.add_argument("--out-dir", default="automation/review/finance/mt00")
    parser.add_argument(
        "--sources", default=f"{SOURCE_GDELT},{SOURCE_HN},{SOURCE_KRAKEN}",
        help="comma-separated: gdelt-doc-2.0,hackernews-official,kraken-public-spot",
    )
    parser.add_argument("--gdelt-query", default="bitcoin")
    parser.add_argument("--max-records", type=int, default=75)
    parser.add_argument("--hn-top", type=int, default=25)
    parser.add_argument("--kraken-pair", default="BTCUSD")
    parser.add_argument("--kraken-interval", type=int, default=60)
    parser.add_argument("--kraken-candles", type=int, default=24)
    parser.add_argument("--retries", type=int, default=3)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    code_file = Path(__file__).resolve()
    return run_probe(args, code_file)


if __name__ == "__main__":
    sys.exit(main())
