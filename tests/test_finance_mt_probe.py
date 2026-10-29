"""Offline tests for the MT-00 public-source probe (src/finance_mt_probe.py).

No network: all fetching goes through the injected ``fetch`` callable.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import finance_mt_probe as mp


GDELT_PAYLOAD = {
    "articles": [
        {
            "url": "https://example.com/a1",
            "title": "Bitcoin Surges Past Key Level",
            "seendate": "20261029T090000Z",
            "domain": "example.com",
            "sourcecountry": "UnitedStates",
        },
        {
            "url": "https://other.example.org/a2",
            "title": "Bitcoin surges past key level",  # syndicated copy
            "seendate": "20261029T093000Z",
            "domain": "other.example.org",
            "sourcecountry": "",
        },
        {"url": "https://example.com/a1", "title": "Duplicate url"},  # exact dup
    ]
}

HN_TOP = [1, 2, 3]
HN_ITEMS = {
    1: {"id": 1, "title": "Show HN: probe", "url": "https://example.com/h1",
        "time": 1790000000, "score": 250, "descendants": 40},
    2: {"id": 2, "title": "Crypto thing", "time": 1790003600, "score": 80},
    3: {"id": 3, "title": None},  # skipped
}

KRAKEN_PAYLOAD = {
    "error": [],
    "result": {
        "XXBTZUSD": [
            [1790000000, "100", "101", "99", "100.5", "100.2", "12.5", 57],
            [1790003600, "100.5", "102", "100", "101.5", "101", "25.0", 91],
        ],
        "last": 1790003600,
    },
}


def gdelt_fetch(url, timeout):
    assert "gdeltproject" in url
    return GDELT_PAYLOAD


def hn_fetch(url, timeout):
    if "topstories" in url:
        return HN_TOP
    item_id = url.rsplit("/", 1)[-1].split(".")[0]
    return HN_ITEMS.get(int(item_id))


def kraken_fetch(url, timeout):
    assert "api.kraken.com" in url
    return KRAKEN_PAYLOAD


def test_gdelt_records_follow_evidence_contract():
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=gdelt_fetch,
    )
    assert result.status == "ok"
    assert len(result.records) == 2  # exact duplicate URL deduplicated
    assert result.deduped_exact == 1
    rec = result.records[0].to_contract()
    for field_name in mp.EVIDENCE_FIELDS:
        assert field_name in rec, field_name
    assert rec["published_at"] == "2026-10-29T09:00:00Z"
    assert rec["first_seen_at"] == "2026-10-29T10:00:00Z"
    assert rec["collected_at"] == "2026-10-29T10:00:00Z"
    assert rec["source"].startswith("gdelt-doc-2.0:")
    assert "no-auth" in rec["source_access_rights"]


def test_syndication_counts_distinct_domains_not_articles():
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=gdelt_fetch,
    )
    report = mp.build_report(
        "2026-10-29T10:00:00Z", [result], {}, None, {"sources": ["gdelt"]}
    )
    topic = report["topics"][0]
    # two articles, two different registrable domains -> diversity 2,
    # but they are ONE normalised story (syndication), never 2 sources
    assert topic["records"] == 2
    assert topic["distinct_domains"] == 2
    assert topic["hypothesis_id"] is None
    assert "persona L" in topic["interpretation"]


def test_hn_records_and_normalization():
    result = mp.collect_hackernews(
        top_n=5, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=hn_fetch,
    )
    assert result.status == "ok"
    assert len(result.records) == 2  # item 3 (title None) skipped
    rec = result.records[0].to_contract()
    assert rec["raw_metric"] == 250.0
    assert rec["source_url"].startswith("https://example.com/h1")
    assert rec["topic_id"] == "hn:frontpage"


def test_kraken_candles_recorded_with_market_entity():
    result, summary = mp.collect_kraken(
        pair="BTCUSD", interval_min=60, keep_candles=24,
        collected_at="2026-10-29T10:00:00Z", fetch=kraken_fetch,
    )
    assert result.status == "ok"
    assert summary["pair_returned"] == "XXBTZUSD"
    assert summary["candles"] == 2
    assert summary["last_close"] == 101.5
    rec = result.records[0].to_contract()
    assert rec["market_entity"] == "BTC/USD"
    assert rec["raw_metric"] == 12.5
    assert rec["normalized_metric"] == round(12.5 / 25.0, 6)
    assert rec["link_to_market_candles"].startswith("kraken:XXBTZUSD:")


def test_first_seen_carried_forward_from_prior_snapshot(tmp_path: Path):
    first = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=gdelt_fetch,
    )
    report = mp.build_report(
        "2026-10-29T10:00:00Z", [first], {}, None, {}
    )
    mp.write_snapshot(tmp_path, report, [first], Path(__file__))
    index, previous = mp.load_first_seen_index(tmp_path)
    assert previous is not None
    event_id = first.records[0].event_id
    assert index[event_id] == "2026-10-29T10:00:00Z"

    second = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-29T16:00:00Z",
        first_seen_index=index, fetch=gdelt_fetch,
    )
    rec = second.records[0].to_contract()
    assert rec["first_seen_at"] == "2026-10-29T10:00:00Z"
    assert rec["collected_at"] == "2026-10-29T16:00:00Z"
    report2 = mp.build_report(
        "2026-10-29T16:00:00Z", [second], {}, previous, {}
    )
    assert "baseline" in report2


def test_retry_then_success_and_exhaustion(monkeypatch):
    calls = {"n": 0}

    def flaky(url, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            import urllib.error

            raise urllib.error.HTTPError(url, 429, "rate", {}, None)
        return GDELT_PAYLOAD

    result = mp.collect_gdelt(
        "bitcoin", max_records=5, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=flaky, retries=3,
    )
    assert result.status == "ok"

    def always_429(url, timeout):
        import urllib.error

        raise urllib.error.HTTPError(url, 429, "rate", {}, None)

    monkeypatch.setattr(mp.time, "sleep", lambda s: None)
    failed = mp.collect_gdelt(
        "bitcoin", max_records=5, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=always_429, retries=2,
    )
    assert failed.status == "failed"
    assert "429" in (failed.error or "") or "attempts" in (failed.error or "")


def test_digest_markdown_shape(tmp_path: Path):
    gdelt = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=gdelt_fetch,
    )
    kraken, summary = mp.collect_kraken(
        pair="BTCUSD", collected_at="2026-10-29T10:00:00Z", fetch=kraken_fetch
    )
    report = mp.build_report(
        "2026-10-29T10:00:00Z", [gdelt, kraken], summary, None, {}
    )
    text = mp.render_digest_markdown(report)
    assert "MT-00 trend probe digest" in text
    assert "reserved for persona L" in text
    assert "x-cookies" in text  # exclusions stated
    assert "first collection" in text  # baseline honesty
    assert "| `gdelt:bitcoin` |" in text


def test_cli_exit_codes(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(mp.time, "sleep", lambda s: None)

    import urllib.error

    def down(url, timeout):
        raise urllib.error.HTTPError(url, 429, "rate", {}, None)

    args = mp.build_parser().parse_args(
        ["--out-dir", str(tmp_path), "--sources", "gdelt-doc-2.0",
         "--retries", "1"]
    )
    real_get = mp.http_get_json
    monkeypatch.setattr(
        mp, "http_get_json",
        lambda url, **kw: real_get(url, **{**kw, "fetch": down}),
    )
    rc = mp.run_probe(args, Path(__file__))
    assert rc == 2  # all sources failed

    monkeypatch.setattr(
        mp, "http_get_json",
        lambda url, **kw: real_get(url, **{**kw, "fetch": gdelt_fetch}),
    )
    rc = mp.run_probe(args, Path(__file__))
    assert rc == 0
    manifest = json.loads(
        (tmp_path / "latest.json").read_text(encoding="utf-8")
    )
    assert manifest["records"]
