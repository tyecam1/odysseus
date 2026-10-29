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

# www./m. mirrors of ONE registrable domain plus two distinct .co.uk
# publishers carrying the same wire story.
GDELT_MIRROR_PAYLOAD = {
    "articles": [
        {
            "url": "https://www.example.co.uk/a1",
            "title": "Bitcoin Surges Past Key Level",
            "seendate": "20261029T090000Z",
            "domain": "www.example.co.uk",
            "sourcecountry": "UnitedStates",
        },
        {
            "url": "https://m.example.co.uk/a1",
            "title": "Bitcoin surges past key level",
            "seendate": "20261029T093000Z",
            "domain": "m.example.co.uk",
            "sourcecountry": "",
        },
        {
            "url": "https://site-a.co.uk/a2",
            "title": "Ether Also Rises",
            "seendate": "20261029T100000Z",
            "domain": "site-a.co.uk",
            "sourcecountry": "",
        },
        {
            "url": "https://site-b.co.uk/a2",
            "title": "Ether also rises",
            "seendate": "20261029T100000Z",
            "domain": "site-b.co.uk",
            "sourcecountry": "",
        },
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


def gdelt_mirror_fetch(url, timeout):
    assert "gdeltproject" in url
    return GDELT_MIRROR_PAYLOAD


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
    # seendate is the monitor's retrieval time, NOT a publication time —
    # it must not be laundered into published_at
    assert rec["published_at"] is None
    assert "seendate" in rec["uncertainty"]
    assert "retrieval" in rec["uncertainty"]
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


def test_registrable_domain_normalisation():
    # bare hosts (GDELT's domain field) and URLs both normalise
    assert mp.registrable_domain("m.example.co.uk") == "example.co.uk"
    assert mp.registrable_domain("https://www.example.co.uk/a1") == "example.co.uk"
    assert mp.registrable_domain("https://site-a.co.uk/a2") == "site-a.co.uk"
    assert mp.registrable_domain("https://site-b.co.uk/a2") == "site-b.co.uk"
    assert mp.registrable_domain("https://sub.example.com/x") == "example.com"
    assert mp.registrable_domain("notahost") == "notahost"
    # a port must not corrupt the host, and distinct publishers under an
    # unlisted-in-round-1 multi-part suffix stay distinct
    assert mp.registrable_domain("www.example.co.uk:443") == "example.co.uk"
    assert mp.registrable_domain("a.co.kr") == "a.co.kr"
    assert mp.registrable_domain("b.co.kr") == "b.co.kr"
    assert mp.registrable_domain("a.co.kr") != mp.registrable_domain("b.co.kr")


def test_mirrors_of_one_registrable_domain_are_one_story():
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=gdelt_mirror_fetch,
    )
    assert result.deduped_exact == 0
    assert result.deduped_syndication == 1  # m.example.co.uk mirror folded
    domains = {r.source.split(":", 1)[1] for r in result.records}
    # 3 registrable domains: example.co.uk (mirrors collapsed),
    # site-a.co.uk, site-b.co.uk (distinct .co.uk publishers stay distinct)
    assert domains == {"example.co.uk", "site-a.co.uk", "site-b.co.uk"}
    report = mp.build_report(
        "2026-10-29T10:00:00Z", [result], {}, None, {"sources": ["gdelt"]}
    )
    topic = next(t for t in report["topics"] if t["topic_id"] == "gdelt:bitcoin")
    assert topic["records"] == 3  # 4 articles, one mirror deduplicated
    assert topic["distinct_domains"] == 3


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


def test_kraken_first_seen_carried_forward():
    # a closed candle seen in an earlier collection keeps its original
    # first_seen_at; first_seen must not reset to each collection time
    first, _ = mp.collect_kraken(
        pair="BTCUSD", collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=kraken_fetch,
    )
    index = {r.event_id: r.first_seen_at for r in first.records}
    second, _ = mp.collect_kraken(
        pair="BTCUSD", collected_at="2026-10-29T16:00:00Z",
        first_seen_index=index, fetch=kraken_fetch,
    )
    for rec in second.records:
        contract = rec.to_contract()
        assert contract["first_seen_at"] == "2026-10-29T10:00:00Z"
        assert contract["collected_at"] == "2026-10-29T16:00:00Z"


def test_first_seen_index_survives_source_selection_gap(tmp_path: Path):
    # a candle seen at 10:00 must keep that first_seen even when the
    # intervening snapshot (12:00, latest.json) collected NO candles —
    # the index merges every snapshot, not just the latest
    candle = [{"event_id": "e-candle-1", "first_seen_at": "2026-10-29T10:00:00Z"}]
    (tmp_path / "snapshot-20261029T100000Z.json").write_text(
        json.dumps({"records": candle}), encoding="utf-8")
    (tmp_path / "snapshot-20261029T120000Z.json").write_text(
        json.dumps({"records": [
            {"event_id": "e-hn-1", "first_seen_at": "2026-10-29T12:00:00Z"}
        ]}), encoding="utf-8")
    (tmp_path / "latest.json").write_text(
        json.dumps({"records": [
            {"event_id": "e-hn-1", "first_seen_at": "2026-10-29T12:00:00Z"}
        ]}), encoding="utf-8")

    index, previous = mp.load_first_seen_index(tmp_path)
    assert previous is not None
    assert index["e-candle-1"] == "2026-10-29T10:00:00Z"
    assert index["e-hn-1"] == "2026-10-29T12:00:00Z"


def test_first_seen_index_keeps_earliest_across_snapshots(tmp_path: Path):
    # same event seen at 10:00 and re-recorded at 16:00: earliest wins
    for stamp, seen in (("100000Z", "2026-10-29T10:00:00Z"),
                        ("160000Z", "2026-10-29T16:00:00Z")):
        (tmp_path / f"snapshot-20261029T{stamp}.json").write_text(
            json.dumps({"records": [
                {"event_id": "e-1", "first_seen_at": seen}
            ]}), encoding="utf-8")
    (tmp_path / "latest.json").write_text(
        json.dumps({"records": [
            {"event_id": "e-1", "first_seen_at": "2026-10-29T16:00:00Z"}
        ]}), encoding="utf-8")
    index, _ = mp.load_first_seen_index(tmp_path)
    assert index["e-1"] == "2026-10-29T10:00:00Z"


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


def test_gdelt_domain_derived_from_url_host_not_metadata():
    # the URL host is the authority for diversity counting; GDELT's
    # free-text ``domain`` metadata must not be able to merge two
    # distinct publishers (or split one) when it disagrees with the URL
    payload = {"articles": [{
        "url": "https://real-publisher.com/story",
        "title": "Real Story",
        "seendate": "20261029T090000Z",
        "domain": "spoofed-merge.example",
    }]}
    result = mp.collect_gdelt(
        "bitcoin", max_records=5, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert result.records[0].source == "gdelt-doc-2.0:real-publisher.com"


def test_gdelt_domain_falls_back_to_metadata_when_url_has_no_host():
    payload = {"articles": [{
        "url": "no-host-token",  # no dotted host in the URL itself
        "title": "Fallback Story",
        "seendate": "20261029T090000Z",
        "domain": "fallback.example",
    }]}
    result = mp.collect_gdelt(
        "bitcoin", max_records=5, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert result.records[0].source == "gdelt-doc-2.0:fallback.example"


def test_corrupt_snapshot_fails_closed(tmp_path: Path):
    (tmp_path / "snapshot-20261029T100000Z.json").write_text(
        "{ truncated", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt evidence snapshot"):
        mp.load_first_seen_index(tmp_path)


def test_non_object_latest_fails_closed(tmp_path: Path):
    (tmp_path / "latest.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="not a JSON object"):
        mp.load_first_seen_index(tmp_path)


def test_run_probe_refuses_to_run_over_corrupt_history(
    tmp_path: Path, capsys,
):
    # a corrupt history file must never be quietly treated as "no
    # history": the probe refuses (rc 2) rather than silently reset
    # every first-seen time the file carried
    (tmp_path / "latest.json").write_text("{ truncated", encoding="utf-8")
    args = mp.build_parser().parse_args(
        ["--out-dir", str(tmp_path), "--sources", "kraken-public-spot"])
    rc = mp.run_probe(args, Path(__file__))
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["fail_closed"] is True
    assert "unreadable history" in payload["error"]


# --- round-5 review findings: IDN hosts collapse; corrupt record
# --- STRUCTURE fails closed instead of resetting or crashing


def test_idn_host_spellings_are_one_domain():
    # bücher.de, BÜCHER.de. and xn--bcher-kva.de are ONE publisher
    a = mp.registrable_domain("https://bücher.de/story/a")
    b = mp.registrable_domain("https://xn--bcher-kva.de/story/a")
    c = mp.registrable_domain("https://BÜCHER.de./story/a")
    d = mp.registrable_domain("bücher.de")
    assert a == b == c == d == "xn--bcher-kva.de"


def test_percent_encoded_host_decodes_before_domain_extraction():
    a = mp.registrable_domain("https://b%C3%BCcher.de/x")
    assert a == "xn--bcher-kva.de"


def test_snapshot_records_not_a_list_fails_closed(tmp_path):
    # {"records": ["not-an-object"]} used to escape as AttributeError;
    # it must surface as the fail-closed ValueError instead
    (tmp_path / "latest.json").write_text(
        json.dumps({"records": ["not-an-object"]}), encoding="utf-8")
    with pytest.raises(ValueError):
        mp.load_first_seen_index(tmp_path)


def test_snapshot_missing_records_list_fails_closed(tmp_path):
    # an object without a records list used to merge as empty history,
    # silently losing every first-seen entry the snapshot carried
    (tmp_path / "latest.json").write_text(
        json.dumps({"generated_at": "2026-10-29T00:00:00Z"}),
        encoding="utf-8")
    with pytest.raises(ValueError):
        mp.load_first_seen_index(tmp_path)


def test_snapshot_record_missing_identity_fails_closed(tmp_path):
    (tmp_path / "latest.json").write_text(
        json.dumps({"records": [{"first_seen_at": "2026-10-29T00:00:00Z"}]}),
        encoding="utf-8")
    with pytest.raises(ValueError):
        mp.load_first_seen_index(tmp_path)
