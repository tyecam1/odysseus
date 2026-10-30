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


# --- round-6 review findings: UTS-46 IDN, malformed URLs, timestamp
# --- content in history


def test_idna_esszett_collapses_to_punycode():
    # stdlib IDNA 2003 maps ß->ss, which would keep faß.de and its
    # punycode spelling xn--fa-hia.de as TWO domains; UTS-46 does not
    idna = pytest.importorskip("idna")
    assert idna is not None
    a = mp.registrable_domain("https://faß.de/story")
    b = mp.registrable_domain("https://xn--fa-hia.de/story")
    assert a == b == "xn--fa-hia.de"
    # and it must NOT merge the genuinely distinct fass.de
    assert mp.registrable_domain("https://fass.de/x") == "fass.de"
    assert mp.registrable_domain("https://fass.de/x") != a


def test_malformed_url_yields_unknown_domain_not_crash():
    # one malformed article URL (bad IPv6 literal) must not abort the
    # whole source collection
    assert mp.registrable_domain("https://[bad/path") == "unknown"
    assert mp.registrable_domain("") == "unknown"


def test_first_seen_at_content_must_parse(tmp_path):
    # a structurally valid record carrying a bogus timestamp would flow
    # into reports as a false first-seen and break ISO ordering
    (tmp_path / "latest.json").write_text(
        json.dumps({"records": [
            {"event_id": "e1", "first_seen_at": "not-a-date"},
        ]}), encoding="utf-8")
    with pytest.raises(ValueError):
        mp.load_first_seen_index(tmp_path)


# --- round-7 review findings: no IDNA-2003 fallback, ill-typed feed
# --- fields, unknown-domain story keys, canonical timestamps ---


def test_missing_idna_package_never_applies_idna2003(monkeypatch):
    # without the idna package a non-ASCII host must classify "unknown",
    # NEVER fall back to stdlib IDNA 2003 (which maps faß.de to fass.de
    # and would split one publisher into two domains)
    monkeypatch.setattr(mp, "_idna", None)
    assert mp.registrable_domain("https://faß.de/story") == "unknown"
    assert mp.registrable_domain("https://BÜCHER.de./x") == "unknown"
    # ASCII hosts are unaffected by the package being absent
    assert mp.registrable_domain("https://fass.de/x") == "fass.de"
    assert mp.registrable_domain("https://example.co.uk/a") == "example.co.uk"


def test_ill_typed_feed_fields_do_not_abort_gdelt():
    # int/list url, list title, None seendate, int domain/country: no
    # combination of ill-typed GDELT fields may abort the whole source
    payload = {"articles": [
        {"url": 12345, "title": "int url"},
        {"url": ["https://x.example/a"], "title": "list url"},
        {"url": "https://a.example/1", "title": ["list title"],
         "seendate": None, "domain": 77, "sourcecountry": 42},
    ]}
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert len(result.records) == 1  # only the usable record survives
    rec = result.records[0].to_contract()
    assert rec["source"] == "gdelt-doc-2.0:a.example"
    assert rec["geography"] is None  # int sourcecountry coerced away


def test_unknown_domain_records_never_false_merge():
    # two UNPARSEABLE-URL articles sharing a title: syndication dedup on
    # (unknown, title) would drop a distinct publisher's story — the
    # story key must be unique per record instead (over-merge destroys
    # evidence; under-merge only loses one dedup opportunity)
    payload = {"articles": [
        {"url": "malformed one", "title": "Same Wire Story"},
        {"url": "malformed two", "title": "same wire story"},
    ]}
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert result.deduped_syndication == 0
    assert len(result.records) == 2


def test_unpadded_timestamp_fails_closed(tmp_path):
    # 2026-9-30 PARSES but is noncanonical: it sorts AFTER 2026-10-01
    # lexicographically and would retain the WRONG first-seen time —
    # the merge gate must reject it, not accept it into ordering
    (tmp_path / "latest.json").write_text(
        json.dumps({"records": [
            {"event_id": "e1", "first_seen_at": "2026-9-30T00:00:00Z"},
        ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical"):
        mp.load_first_seen_index(tmp_path)


def test_hn_ill_typed_item_fields_do_not_abort():
    # non-numeric time/score and an int url on ONE item must degrade
    # that item's fields, never abort the HN collection
    items = {1: {"id": 1, "title": "Odd item", "url": 123,
                 "time": "abc", "score": "x"}}
    result = mp.collect_hackernews(
        top_n=1, collected_at="2026-10-29T10:00:00Z",
        first_seen_index={},
        fetch=lambda url, timeout: (
            [1] if "topstories" in url else items.get(1)
        ),
    )
    assert result.status == "ok"
    assert len(result.records) == 1
    rec = result.records[0].to_contract()
    assert rec["published_at"] is None
    assert rec["raw_metric"] == 0.0
    assert rec["source_url"] == "https://news.ycombinator.com/item?id=1"


def test_kraken_malformed_candle_skipped_not_fatal():
    # a structurally bad candle in the OHLC series must be skipped and
    # counted, never allowed to abort the Kraken collection
    payload = {"error": [], "result": {"XXBTZUSD": [
        [1790000000, "100", "101", "99", "100.5", "100.2", "12.5", 57],
        ["oops"],
        {"not": "a candle"},
        [1790003600, "100.5", "102", "100", "101.5", "101", "25.0", 91],
    ], "last": 1790003600}}
    result, summary = mp.collect_kraken(
        pair="BTCUSD", collected_at="2026-10-29T10:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert len(result.records) == 2
    assert summary["candles"] == 2
    assert summary["skipped_malformed_candles"] == 2
    assert summary["last_close"] == 101.5
    assert summary["last_volume"] == 25.0


# --- round-7 review findings: non-retryable HTTP errors, out-of-range
# --- timestamps, non-finite numbers, unusable titles, failed-source
# --- health fields ---


def test_non_retryable_http_error_fails_the_source_not_the_probe():
    # a 403 must become failed-source health (with the status recorded),
    # never an uncaught HTTPError that aborts the whole probe
    import urllib.error

    def forbidden(url, timeout):
        raise urllib.error.HTTPError(url, 403, "forbidden", {}, None)

    result = mp.collect_gdelt(
        "bitcoin", max_records=5, collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=forbidden, retries=3,
    )
    assert result.status == "failed"
    assert result.http_status == 403
    assert "403" in (result.error or "")


def test_exhausted_retries_record_status_and_retry_count(monkeypatch):
    # the 429-exhausted case must carry http_status 429 and the retry
    # budget in the structured health fields, not null/zero
    import urllib.error

    monkeypatch.setattr(mp.time, "sleep", lambda s: None)

    def always_429(url, timeout):
        raise urllib.error.HTTPError(url, 429, "rate", {}, None)

    result = mp.collect_gdelt(
        "bitcoin", max_records=5, collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=always_429, retries=3,
    )
    assert result.status == "failed"
    assert result.http_status == 429
    assert result.retries == 3


def test_out_of_range_kraken_timestamp_skipped_not_fatal():
    # int-but-out-of-range candle time (999999999999) previously passed
    # the parse and blew up in fromtimestamp; it must be skipped+counted
    payload = {"error": [], "result": {"XXBTZUSD": [
        [999999999999, "100", "101", "99", "100.5", "100.2", "12.5", 57],
        [1790003600, "100.5", "102", "100", "101.5", "101", "25.0", 91],
    ], "last": 1790003600}}
    result, summary = mp.collect_kraken(
        pair="BTCUSD", collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert len(result.records) == 1
    assert summary["skipped_malformed_candles"] == 1


def test_non_finite_feed_numbers_never_reach_records():
    # "1e999" (inf) and "NaN" volumes/scores must be dropped or zeroed:
    # json.dumps would otherwise emit Infinity/NaN into the snapshot
    hn_items = {1: {"id": 1, "title": "Big", "time": 1790000000,
                    "score": "1e999"}}
    hn = mp.collect_hackernews(
        top_n=1, collected_at="2026-10-30T00:00:00Z", first_seen_index={},
        fetch=lambda url, timeout: (
            [1] if "topstories" in url else hn_items.get(1)
        ),
    )
    assert hn.status == "ok"
    assert hn.records[0].to_contract()["raw_metric"] == 0.0

    import math
    payload = {"error": [], "result": {"XXBTZUSD": [
        [1790000000, "100", "101", "99", "1e999", "100.2", "12.5", 57],
        [1790003600, "100.5", "102", "100", "101.5", "101", "NaN", 91],
    ], "last": 1790003600}}
    kr, summary = mp.collect_kraken(
        pair="BTCUSD", collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert kr.status == "ok"
    assert kr.records == []
    assert summary["skipped_malformed_candles"] == 2
    assert all(
        math.isfinite(v) for r in kr.records
        for v in (r.raw_metric, r.normalized_metric or 0.0)
    )


def test_snapshot_writer_refuses_non_finite_json(tmp_path):
    # belt behind the collector guards: allow_nan=False makes any leak
    # a loud failure instead of invalid strict-JSON output
    import pytest as _pytest

    report = {
        "generated_at": "2026-10-30T00:00:00Z",
        "params": {},
        "source_results": [],
        "topics": [],
    }
    bad = mp.EvidenceRecord(
        event_id="e", topic_id="t", source="s", source_url="u",
        published_at=None, first_seen_at="2026-10-30T00:00:00Z",
        collected_at="2026-10-30T00:00:00Z", window="2026-10-30",
        source_access_rights="test", source_health="test",
        raw_metric=float("inf"),
    )
    carrier = mp.SourceResult("test", "ok", records=[bad])
    with _pytest.raises(ValueError):
        mp.write_snapshot(tmp_path, report, [carrier], Path(__file__))


def test_unusable_titles_never_false_merge_within_a_domain():
    # two DISTINCT stories from one domain whose titles are unusable
    # (non-string / empty) must not collapse onto the shared
    # ("domain", "") dedup key — both records survive
    payload = {"articles": [
        {"url": "https://one.example/a", "title": ["not", "a", "title"]},
        {"url": "https://one.example/b", "title": ""},
    ]}
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert result.deduped_syndication == 0
    assert len(result.records) == 2


# ---------------------------------------------------------------------
# round-9 pins: negative candle fields, pre-epoch candles, huge-int HN
# scores, non-int topstory ids, wrong-shape payloads, full-title keys,
# hosted-platform domains
# ---------------------------------------------------------------------


def test_negative_kraken_fields_skipped_not_fatal():
    # finite-but-negative close/volume previously produced -inf in
    # normalized_metric (volume / max_volume with a negative max) —
    # skipped+counted like other malformed candles
    payload = {"error": [], "result": {"XXBTZUSD": [
        [1790000000, "100", "101", "99", "-5", "100.2", "12.5", 57],
        [1790003600, "100.5", "102", "100", "101.5", "101", "-1e308", 91],
        [1790007200, "100.5", "102", "100", "101.5", "101", "1e-320", 91],
    ], "last": 1790007200}}
    result, summary = mp.collect_kraken(
        pair="BTCUSD", collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    # negative close and negative volume skipped; the POSITIVE
    # subnormal volume survives and normalises finitely
    assert len(result.records) == 1
    assert summary["skipped_malformed_candles"] == 2
    rec = result.records[0].to_contract()
    assert rec["raw_metric"] == 1e-320
    assert 0.0 <= rec["normalized_metric"] <= 1.0


def test_pre_epoch_kraken_timestamp_skipped():
    # -1 previously passed int() + fromtimestamp as a 1969 candle
    payload = {"error": [], "result": {"XXBTZUSD": [
        [-1, "100", "101", "99", "100.5", "100.2", "12.5", 57],
        [1790003600, "100.5", "102", "100", "101.5", "101", "25.0", 91],
    ], "last": 1790003600}}
    result, summary = mp.collect_kraken(
        pair="BTCUSD", collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert len(result.records) == 1
    assert summary["skipped_malformed_candles"] == 1
    # no pre-1970 market observation can reach the snapshot
    assert all(
        r.to_contract()["published_at"] >= "1970" for r in result.records
    )


def test_hn_huge_int_score_zeroed():
    # float(10**400) is OverflowError from a VALID JSON integer —
    # zeroed exactly like inf/NaN, never an abort
    item = {"id": 1, "title": "Big", "time": 1790000000, "score": 10**400}
    hn = mp.collect_hackernews(
        top_n=1, collected_at="2026-10-30T00:00:00Z", first_seen_index={},
        fetch=lambda url, timeout: (
            [1] if "topstories" in url else item
        ),
    )
    assert hn.status == "ok"
    assert hn.records[0].to_contract()["raw_metric"] == 0.0


def test_hn_non_int_topstory_ids_skipped_not_fatal():
    # inf/bool/str/float entries in the topstories list previously
    # reached int(item_id) and aborted the source with OverflowError
    good = {"id": 7, "title": "Good", "time": 1790000000, "score": 10}

    def fetch(url, timeout):
        if "topstories" in url:
            return [True, "x", 1.5, float("inf"), 7]
        return good if url.endswith("/7.json") else None

    hn = mp.collect_hackernews(
        top_n=5, collected_at="2026-10-30T00:00:00Z", first_seen_index={},
        fetch=fetch,
    )
    assert hn.status == "ok"
    assert len(hn.records) == 1
    rec = hn.records[0].to_contract()
    assert rec["raw_metric"] == 10.0
    assert "item errors=4" in rec["source_health"]


def test_gdelt_wrong_shape_payload_fails_source_not_probe():
    # a 200 response whose body is [1] is a failed source, never an
    # AttributeError aborting the probe
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: [1],
    )
    assert result.status == "failed"
    assert result.http_status == 200
    assert "articles list" in (result.error or "")


def test_kraken_wrong_shape_payload_fails_source_not_probe():
    # non-object payload, or a result that is not an object: failed
    # source with honest status/retries, never an abort
    for bad in ([1], {"error": [], "result": [1]}, {"error": [], "result": "x"}):
        result, summary = mp.collect_kraken(
            pair="BTCUSD", collected_at="2026-10-30T00:00:00Z",
            first_seen_index={}, fetch=lambda url, timeout, p=bad: p,
        )
        assert result.status == "failed"
        assert result.http_status == 200
        assert summary == {}


def test_long_titles_differing_late_never_merge():
    # two same-domain titles identical through word 12 and differing at
    # word 13 are DISTINCT stories — the story key uses the FULL title
    prefix = " ".join(f"w{i}" for i in range(12))
    payload = {"articles": [
        {"url": "https://one.example/a", "title": f"{prefix} alpha"},
        {"url": "https://one.example/b", "title": f"{prefix} beta"},
    ]}
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert result.deduped_syndication == 0
    assert len(result.records) == 2


def test_normalize_title_word_cap_is_opt_in():
    long_title = " ".join(f"w{i}" for i in range(20))
    # labels/topic ids keep the bounded form
    assert len(mp.normalize_title(long_title).split()) == 12
    # the syndication key passes the FULL normalised title
    assert mp.normalize_title(long_title, max_words=None) == long_title


def test_hosted_platform_hosts_are_distinct_publishers():
    # alpha.github.io and beta.github.io are DIFFERENT publishers, not
    # both "github.io" (the platform is a host, not the publisher)
    assert mp.registrable_domain("https://alpha.github.io/a") == "alpha.github.io"
    assert mp.registrable_domain("https://beta.github.io/b") == "beta.github.io"
    assert (
        mp.registrable_domain("https://alpha.github.io/a")
        != mp.registrable_domain("https://beta.github.io/b")
    )
    assert mp.registrable_domain("https://someone.substack.com/p/x") == "someone.substack.com"
    # classic multi-part suffixes unchanged
    assert mp.registrable_domain("https://site.co.uk/x") == "site.co.uk"


def test_hosted_platform_same_title_never_merges():
    payload = {"articles": [
        {"url": "https://alpha.github.io/post", "title": "Same Title"},
        {"url": "https://beta.github.io/post", "title": "Same Title"},
    ]}
    result = mp.collect_gdelt(
        "bitcoin", max_records=10, collected_at="2026-10-30T00:00:00Z",
        first_seen_index={}, fetch=lambda url, timeout: payload,
    )
    assert result.status == "ok"
    assert result.deduped_syndication == 0
    assert len(result.records) == 2
    domains = {r.source.split(":", 1)[1] for r in result.records}
    assert domains == {"alpha.github.io", "beta.github.io"}
