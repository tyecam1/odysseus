"""Synthetic-fixture tests for src.chatgpt_ingest (PR #217 Gate B/C/D plumbing). No real export, no network."""
import io
import json
import os
import zipfile

import pytest

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

from src import chatgpt_ingest as ci


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    clear_fake_database_modules()
    import core.database as cdb
    import src.source_events as se
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    monkeypatch.setattr(se, "SOURCE_EVENT_PAYLOAD_DIR", tmp_path / "payloads")
    yield
    engine.dispose()
    os.unlink(tmpfile.name)


def _node(nid, parent, role, text, children=()):
    return {"id": nid, "parent": parent, "children": list(children),
            "message": {"id": nid, "author": {"role": role}, "content": {"parts": [text]}, "create_time": 1.0}
            if text is not None else None}


def _conv(cid, user_text, *, branch=False):
    mapping = {"root": _node("root", None, "system", None, ["u1"]),
               "u1": _node("u1", "root", "user", user_text, ["a1"] + (["a1b"] if branch else [])),
               "a1": _node("a1", "u1", "assistant", "old branch answer"),
               }
    cur = "a1"
    if branch:
        mapping["a1b"] = _node("a1b", "u1", "assistant", "ACTIVE branch answer")
        cur = "a1b"
    return {"conversation_id": cid, "title": "t", "current_node": cur, "mapping": mapping}


def _zip(path, convs):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("conversations-000.json", json.dumps(convs))
    return path


def _local(system, user):
    if "SECRET" in user:
        raise AssertionError("quarantined text reached the model")
    return json.dumps({"candidates": [{"kind": "decision", "description": "User decided to use mmWave radar for the PhD sensing study",
                                       "msgs": ["u1"], "domain": "obsidian-phd", "validity": "current_candidate",
                                       "sensitivity": "ordinary", "confidence": 0.9, "verdict": "approve"},
                                      {"kind": "preference", "description": "User likes trivia", "msgs": ["u1"],
                                       "domain": "neutral", "sensitivity": "ordinary", "confidence": 0.3,
                                       "verdict": "deny"}]})


def _strong(system, user):
    rows = json.loads(user)["rows"]
    return json.dumps({"rows": [{"id": r["id"], "decision": "accept", "destination": "automation/review/x", "rationale": "ok"}
                                for r in rows]})


def test_active_branch_only_and_reimport_skips_unchanged(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I decided on radar", branch=True), _conv("c2", "hi")])
    first = ci.stage(z, "imp", root=tmp_path)
    assert first["created"] == 2
    again = ci.stage(z, "imp", root=tmp_path)
    assert again["unchanged"] == 2 and again["created"] == 0
    msgs = ci.linearize(_conv("c1", "x", branch=True))
    assert [m["text"] for m in msgs] == ["x", "ACTIVE branch answer"]


def test_revised_conversation_is_linked_not_duplicated(tmp_path):
    ci.stage(_zip(tmp_path / "a.zip", [_conv("c1", "v1")]), "imp", root=tmp_path)
    r = ci.stage(_zip(tmp_path / "b.zip", [_conv("c1", "v2")]), "imp", root=tmp_path)
    assert r["revised"] == 1 and r["created"] == 0


def test_secret_text_is_quarantined_and_never_reaches_model(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "my api_key = SECRETVALUE123456")])
    out = ci.run_all(z, "imp", local=_local, strong=_strong, root=tmp_path)
    assert out["stage"]["quarantined"] == 1
    assert out["extract"]["quarantined"] == 1


def test_end_to_end_gates_and_idempotent_resume(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I decided on radar for my PhD sensing study")])
    out = ci.run_all(z, "imp", local=_local, strong=_strong, root=tmp_path)
    rep = out["report"]
    assert rep["candidates"] == 2
    # obsidian-phd accept is escalated to the human gate, never self-approved; first-pass deny is suppressed
    assert rep["review"].get("human_gate") == 1 and rep["review"].get("rejected") == 1
    assert rep["awaiting_human"] == 1
    assert out["handoff"] == {"obsidian-phd": 1}
    ledger = (tmp_path / "imp" / "handoff" / "obsidian-phd.jsonl").read_text()
    assert "radar" not in ledger          # pointer-only outbox, no description text
    again = ci.run_all(z, "imp", local=_local, strong=_strong, root=tmp_path)
    assert again["stage"]["unchanged"] == 1 and again["extract"]["processed"] == 0 and again["handoff"] == {}


def test_unsafe_archive_rejected(tmp_path):
    p = tmp_path / "bad.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("../evil.json", "[]")
    with pytest.raises(ValueError):
        list(ci.iter_conversations(p))


def test_unparseable_model_reply_is_retried_not_guessed(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "hello there")])
    ci.stage(z, "imp", root=tmp_path)
    assert ci.extract("imp", lambda s, u: "not json", root=tmp_path)["failed"] == 1
    assert ci.extract("imp", _local, root=tmp_path)["processed"] == 1


def test_multiple_shards(tmp_path):
    p = tmp_path / "m.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("conversations-001.json", json.dumps([_conv("c2", "two")]))
        zf.writestr("conversations-000.json", json.dumps([_conv("c1", "one")]))
    assert [c["conversation_id"] for c in ci.iter_conversations(p)] == ["c1", "c2"]


def test_one_off_requests_are_denied_and_misumi_fiction_rerouted():
    c = ci.postfilter({"description": "User requests MATLAB code to plot a workspace", "first_pass": "approve", "domain": "misumi", "speaker_basis": "user_first_person"})
    assert c["first_pass"] == "deny" and c["domain"] == "neutral"
    keep = ci.postfilter({"description": "User prefers British English", "first_pass": "approve", "domain": "misumi", "speaker_basis": "user_first_person"})
    assert keep["first_pass"] == "approve"


def test_prompt_bump_supersedes_old_rows_not_duplicates(tmp_path, monkeypatch):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I decided on radar for my PhD sensing study")])
    ci.run_all(z, "imp", local=_local, strong=_strong, root=tmp_path)
    monkeypatch.setattr(ci, "PROMPT_VERSION", "v99")
    out = ci.extract("imp", _local, root=tmp_path)
    assert out["processed"] == 1
    latest = {}
    for r in ci._read_jsonl(tmp_path / "imp" / "ledger.jsonl"):
        latest[r["candidate_id"]] = r
    assert sum(r["active"] for r in latest.values()) <= 1       # old active row superseded, not duplicated


def test_stale_prompt_rows_are_not_reviewed_or_handed_off(tmp_path):
    work = tmp_path / "imp"
    work.mkdir()
    row = ci._row("imp", "c1", {"kind": "goal", "description": "old row", "msgs": [], "domain": "neutral", "validity": "unknown",
                                "sensitivity": "ordinary", "confidence": 0.9, "first_pass": "approve"}, "h")
    row["prompt"] = "v0"
    ci._append(work / "ledger.jsonl", row)
    assert ci.review("imp", _strong, root=tmp_path)["reviewed"] == 0


def test_filter_does_not_overmatch_and_fiction_interest_is_kept():
    ok = ci.postfilter({"description": "User keeps developing a warp-drive worldbuilding idea as a creative interest, for example ion rings",
                        "first_pass": "approve", "domain": "misumi", "speaker_basis": "user_first_person"})
    assert ok["first_pass"] == "approve" and ok["domain"] == "misumi"


def test_unproven_attribution_and_sensitive_terms_never_auto_approve():
    base = {"first_pass": "approve", "domain": "neutral", "sensitivity": "ordinary", "speaker_basis": "user_first_person"}
    third = ci.postfilter({**base, "description": "Cllr Emma Cox seeks a legal opinion", "speaker_basis": "on_behalf_of_other"})
    assert third["first_pass"] == "needs_stronger_model" and third["sensitivity"] == "restricted"
    ident = ci.postfilter({**base, "description": "User identifies as the chair of a parish council"})
    assert ident["first_pass"] == "needs_stronger_model"
    fine = ci.postfilter({**base, "description": "User prefers concise bullet points"})
    assert fine["first_pass"] == "approve" and fine["sensitivity"] == "ordinary"


def test_source_has_no_control_characters():
    import pathlib
    text = pathlib.Path(ci.__file__).read_text(encoding="utf-8")
    assert not [c for c in text if ord(c) < 32 and c not in "\n\t\r"]     # a stray \b in a patch once became a backspace


def test_digest_clusters_across_conversations_and_ranks_by_support(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I decided on radar for my PhD sensing study"),
                                  _conv("c2", "Again: radar for the PhD sensing study")])
    ci.run_all(z, "imp", local=_local, strong=_strong, root=tmp_path)
    out = ci.digest("imp", root=tmp_path)
    text = (tmp_path / "imp" / "digest.md").read_text()
    assert "[2x decision" in text and out["items"] < out["rows"]


def test_coursework_variants_are_denied():
    base = {"first_pass": "approve", "domain": "obsidian-phd", "sensitivity": "ordinary", "speaker_basis": "user_first_person"}
    for d in ("User is solving a set of probability problems, correcting problem 41 part c",
              "User is working on ME 491 Programming Exercise 2 implementing policy iteration",
              "User works on a tutorial sheet for control systems"):
        assert ci.postfilter({**base, "description": d})["first_pass"] == "deny", d
    keep = ci.postfilter({**base, "description": "User is writing a PhD literature review on safety standards"})
    assert keep["first_pass"] == "approve"


def test_triage_skips_coursework_without_extraction_and_fails_open(tmp_path):
    calls = []

    def llm(system, user):
        calls.append(system)
        if system == ci.TRIAGE_SYSTEM:
            return json.dumps({"purpose": "coursework"})
        return _local(system, user)
    z = _zip(tmp_path / "e.zip", [_conv("c1", "solve problem 5 of my homework")])
    ci.stage(z, "imp", root=tmp_path)
    out = ci.extract("imp", llm, root=tmp_path)
    assert out["triaged_out"] == 1 and out["candidates"] == 0 and ci.EXTRACT_SYSTEM not in calls
    assert ci.triage(lambda s, u: "garbage", {"messages": [{"role": "user", "text": "x"}]}) is None   # fail open


def test_numeric_and_submission_backstops():
    base = {"first_pass": "approve", "domain": "neutral", "sensitivity": "ordinary", "speaker_basis": "user_first_person"}
    for d in ("User requires pressures with force 1779 kN and height 0.1 m",
              "User wants to submit compilable code to the autograder"):
        assert ci.postfilter({**base, "description": d})["first_pass"] == "deny", d
    assert ci.postfilter({**base, "description": "User reviews PR #157 on 2026-11-02"})["first_pass"] == "approve"


def test_digest_puts_restricted_rows_in_their_own_late_section(tmp_path):
    work = tmp_path / "imp"
    work.mkdir()
    for i, (sens, desc) in enumerate([("restricted", "private health matter"), ("ordinary", "prefers bullet points")]):
        row = ci._row("imp", f"c{i}", {"kind": "preference", "description": desc, "msgs": [], "domain": "neutral",
                                       "validity": "unknown", "sensitivity": sens, "confidence": 0.9, "first_pass": "approve"}, "h")
        ci._append(work / "ledger.jsonl", row)
    ci.digest("imp", root=tmp_path)
    text = (work / "digest.md").read_text()
    assert text.index("bullet points") < text.index("RESTRICTED") < text.index("health matter")


def test_top_digest_ranks_supported_items_first_and_excludes_restricted(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I decided on radar for my PhD sensing study"),
                                  _conv("c2", "Again: radar for the PhD sensing study")])
    ci.run_all(z, "imp", local=_local, strong=_strong, root=tmp_path)
    top = (tmp_path / "imp" / "digest-top.md").read_text()
    assert any(line.startswith("- [2x") for line in top.splitlines())


def test_retriage_supersedes_rows_when_triage_rule_changes_and_for_others_is_skipped(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I decided on radar for my PhD sensing study")])
    ci.run_all(z, "imp", local=_local, strong=_strong, root=tmp_path)

    def llm(system, user):
        return json.dumps({"purpose": "for_others"}) if system == ci.TRIAGE_SYSTEM else _local(system, user)
    out = ci.retriage("imp", llm, root=tmp_path)
    assert out["superseded_convs"] == 1 and out["superseded_rows"] >= 1
    latest = {}
    for r in ci._read_jsonl(tmp_path / "imp" / "ledger.jsonl"):
        latest[r["candidate_id"]] = r
    assert not any(r["active"] for r in latest.values())
    assert "for_others" in ci.SKIP_PURPOSES


def test_community_terms_are_restricted():
    base = {"first_pass": "approve", "domain": "misumi", "sensitivity": "ordinary", "speaker_basis": "user_first_person"}
    out = ci.postfilter({**base, "description": "User campaigns for safer parks in the ward"})
    assert out["sensitivity"] == "restricted"


def test_refilter_denies_assistant_rows_and_enforces_cap_idempotently(tmp_path):
    work = tmp_path / "imp"
    work.mkdir()
    def add(desc, kind, conf, cid="c1"):
        row = ci._row("imp", cid, {"kind": kind, "description": desc, "msgs": [], "domain": "neutral", "validity": "unknown",
                                   "sensitivity": "ordinary", "speaker_basis": "user_first_person", "confidence": conf,
                                   "first_pass": "approve"}, "h")
        ci._append(work / "ledger.jsonl", row)
    add("The assistant suggests replugging the board", "procedure", 0.9)
    for i in range(6):
        add(f"User holds distinct standing preference number {i} alpha{i}", "preference", 0.5 + i / 20)
    first = ci.refilter("imp", root=tmp_path)
    assert first["capped"] == 2 and first["changed"] >= 3
    latest = {}
    for r in ci._read_jsonl(work / "ledger.jsonl"):
        latest[r["candidate_id"]] = r
    assert sum(r["active"] for r in latest.values()) == 4
    assert not any(r["active"] for r in latest.values() if r["description"].startswith("The assistant"))
    assert ci.refilter("imp", root=tmp_path) == {"changed": 0, "capped": 0}


def _enrich_llm(system, user):
    if system == ci.TRIAGE_SYSTEM:
        return json.dumps({"purpose": "work_or_life"})
    if system == ci.PREF_SYSTEM:
        return json.dumps({"preferences": [{"description": "User prefers British English and concise bullet points",
                                            "msgs": ["u1"], "domain": "misumi"}]})
    return _local(system, user)


def test_enrich_extracts_preferences_and_questions_and_is_idempotent(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I always want British English. What is the range of mmWave radar for pose sensing?"),
                                  _conv("c2", "Quick one: What is the range of mmWave radar for pose sensing?")])
    ci.run_all(z, "imp", local=_enrich_llm, strong=_strong, root=tmp_path)
    latest = {}
    for r in ci._read_jsonl(tmp_path / "imp" / "ledger.jsonl"):
        latest[r["candidate_id"]] = r
    live = [r for r in latest.values() if r["active"] and r["review"] != "superseded"]
    assert any(r["kind"] == "preference" and r.get("source") == "enrich" for r in live)
    qs = [r for r in live if r["kind"] == "question"]
    assert len(qs) == 2 and all(r["review"] == "not_reviewed" for r in qs)
    again = ci.enrich("imp", _enrich_llm, root=tmp_path)
    assert again["checked"] == 0
    out = ci.digest("imp", root=tmp_path)
    assert out["recurring_questions"] == 1 and out["preferences"] >= 1
    top = (tmp_path / "imp" / "digest-top.md").read_text()
    assert top.index("Your preferences") < top.index("Your recurring questions")


def test_enrich_rescues_preferences_from_coursework_but_skips_for_others_and_homework_questions(tmp_path):
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I prefer detailed R solutions. Can you solve problem 5?"),
                                  _conv("c2", "I always want formal tone. Please draft for my client.")])
    ci.stage(z, "imp", root=tmp_path)

    def llm(system, user):
        if system == ci.TRIAGE_SYSTEM:
            return json.dumps({"purpose": "coursework" if "problem 5" in user else "for_others"})
        return _enrich_llm(system, user)
    ci.extract("imp", llm, root=tmp_path)
    out = ci.enrich("imp", llm, root=tmp_path)
    assert out["skipped_for_others"] == 1 and out["preferences"] == 1 and out["questions"] == 0


def test_decision_pass_and_questions_are_guided_by_preferences_and_decisions(tmp_path):
    def llm(system, user):
        if system == ci.TRIAGE_SYSTEM:
            return json.dumps({"purpose": "work_or_life"})
        if system == ci.PREF_SYSTEM:
            return json.dumps({"preferences": []})
        if system == ci.DECISION_SYSTEM:
            return json.dumps({"decisions": [{"description": "Chooses mmWave radar over cameras for pose sensing because of privacy",
                                              "msgs": ["u1"], "domain": "obsidian-phd"}]})
        return _local(system, user)
    z = _zip(tmp_path / "e.zip", [_conv("c1", "I decided on radar instead of cameras. What is the range of mmWave radar for pose sensing?"),
                                  _conv("c2", "What is the range of mmWave radar for pose sensing in a cobot cell?")])
    out = ci.run_all(z, "imp", local=llm, strong=_strong, root=tmp_path)
    assert out["extract"]["enrich"]["decisions"] >= 1
    d = ci.digest("imp", root=tmp_path)
    assert d["decision_rules"] >= 1 and d["recurring_questions"] == 1
    top = (tmp_path / "imp" / "digest-top.md").read_text()
    assert "guided by [decision]" in top
    assert top.index("Your decisions and the rules behind them") < top.index("Your recurring questions")


def _tier_setup(tmp_path):
    convs = [_conv(f"k{i}", f"I decided on radar for pose sensing in the cobot cell {i}") for i in range(3)]
    convs += [_conv(f"h{i}", f"homework integral calculus problem {i}") for i in range(3)]

    def base(system, user):
        if system == ci.TRIAGE_SYSTEM:
            return json.dumps({"purpose": "coursework" if "homework" in user else "work_or_life"})
        if system in (ci.PREF_SYSTEM, ci.DECISION_SYSTEM):
            return json.dumps({"preferences": [], "decisions": []})
        return _local(system, user)
    z = _zip(tmp_path / "e.zip", convs)
    ci.run_all(z, "imp", local=base, strong=_strong, root=tmp_path)
    return base


def test_lexicon_learns_core_language_and_scan_ranks_it_first(tmp_path):
    _tier_setup(tmp_path)
    out = ci.build_lexicon("imp", root=tmp_path, min_pos=1)
    assert out["positive_conversations"] == 3 and out["negative_conversations"] == 3
    terms = json.loads((tmp_path / "imp" / "lexicon.json").read_text())["terms"]
    assert "radar" in terms and "homework" not in terms
    ci.scan("imp", root=tmp_path)
    scores = json.loads((tmp_path / "imp" / "scan.json").read_text())
    assert min(scores[f"k{i}"]["score"] for i in range(3)) > max(scores[f"h{i}"]["score"] for i in range(3))


def test_deepread_uses_strong_reader_on_top_scored_conversations_and_supersedes_baseline(tmp_path):
    _tier_setup(tmp_path)
    ci.build_lexicon("imp", root=tmp_path, min_pos=1)
    ci.scan("imp", root=tmp_path)
    seen = []

    def reader(system, user):
        seen.append(user)
        return json.dumps({"candidates": [{"kind": "preference", "description": "User prefers radar over cameras for privacy",
                                           "msgs": ["u1"], "domain": "obsidian-phd", "validity": "current_candidate",
                                           "sensitivity": "ordinary", "speaker_basis": "user_first_person",
                                           "confidence": 0.9, "verdict": "approve"}]})
    out = ci.deepread("imp", reader, root=tmp_path, max_conversations=2, min_score=0.1)
    assert out["read"] == 2 and out["candidates"] == 2 and all("radar" in u for u in seen)
    latest = {}
    for r in ci._read_jsonl(tmp_path / "imp" / "ledger.jsonl"):
        latest[r["candidate_id"]] = r
    strong_rows = [r for r in latest.values() if r.get("reader") == "local-strong"]
    assert len(strong_rows) == 2 or len({r["conversation_id"] for r in strong_rows}) == 2
    for cid in {r["conversation_id"] for r in strong_rows}:
        base = [r for r in latest.values() if r["conversation_id"] == cid and r.get("reader") != "local-strong" and r["active"]]
        assert not base                       # baseline rows for that conversation are superseded
    assert ci.deepread("imp", reader, root=tmp_path, max_conversations=2, min_score=0.1)["read"] <= 1   # idempotent


def _pending_rows(tmp_path, n, kind="goal", domain="neutral"):
    work = tmp_path / "imp"
    work.mkdir(exist_ok=True)
    for i in range(n):
        row = ci._row("imp", f"c{i}", {"kind": kind, "description": f"User holds standing item number {i} zeta{i}", "msgs": [],
                                       "domain": domain, "validity": "unknown", "sensitivity": "ordinary",
                                       "speaker_basis": "user_first_person", "confidence": 0.9, "first_pass": "approve"}, "h")
        ci._append(work / "ledger.jsonl", row)


def test_review_survives_truncated_replies_by_salvaging_and_splitting(tmp_path):
    _pending_rows(tmp_path, 8)
    calls = []

    def llm(system, user):
        rows = json.loads(user)["rows"]
        calls.append(len(rows))
        keep = rows[:3]                                  # a reply that stops after 3 complete rows, cut mid-object
        full = json.dumps({"rows": [{"id": r["id"], "decision": "accept", "destination": "x", "rationale": "ok"} for r in keep]})
        return full[:-2] + ',{"id":"' + rows[-1]["id"][:6]
    out = ci.review("imp", llm, root=tmp_path, inv=lambda d: [])
    assert out["failed"] == 0 and out["reviewed"] == 8 and len(calls) > 1


def test_review_runs_preferences_before_other_kinds(tmp_path):
    _pending_rows(tmp_path, 2, kind="procedure")
    work = tmp_path / "imp"
    pref = ci._row("imp", "p1", {"kind": "preference", "description": "User prefers terse replies", "msgs": [], "domain": "neutral",
                                 "validity": "unknown", "sensitivity": "ordinary", "speaker_basis": "user_first_person",
                                 "confidence": 0.9, "first_pass": "approve"}, "h")
    ci._append(work / "ledger.jsonl", pref)
    order = []

    def llm(system, user):
        rows = json.loads(user)["rows"]
        order.append(rows[0]["kind"])
        return json.dumps({"rows": [{"id": r["id"], "decision": "accept", "destination": "x", "rationale": "ok"} for r in rows]})
    ci.review("imp", llm, root=tmp_path, inv=lambda d: [])
    assert order[0] == "preference"


def test_rescreen_rejects_third_person_and_transient_and_gates_planning_rows(tmp_path):
    work = tmp_path / "imp"
    work.mkdir()
    descs = ["She submitted a call-in request for Application 25/01505/OUT", "User confirmed that the CI has passed the full automation tests again",
             "Objects to the planning application because drainage is unreliable", "User prefers concise answers"]
    for i, d in enumerate(descs):
        row = ci._row("imp", f"c{i}", {"kind": "decision", "description": d, "msgs": [], "domain": "neutral", "validity": "unknown",
                                       "sensitivity": "ordinary", "speaker_basis": "user_first_person", "confidence": 0.9,
                                       "first_pass": "approve"}, "h")
        ci._append(work / "ledger.jsonl", {**row, "review": "accepted_candidate"})
    out = ci.rescreen("imp", root=tmp_path)
    assert out == {"rejected": 2, "gated": 1}
    assert ci.rescreen("imp", root=tmp_path) == {"rejected": 0, "gated": 0}


def test_resolve_gates_agent_decides_and_escalates_only_credentials(tmp_path):
    work = tmp_path / "imp"
    work.mkdir()
    descs = ["User prefers concise answers", "User stores the api key in a note", "User's mother likes watercolour painting",
             "Planning matter for a neighbour"]
    ids = {}
    for i, d in enumerate(descs):
        basis = "third_party_or_assistant" if i == 3 else "user_first_person"
        sens = "restricted" if i == 3 else "ordinary"
        row = ci._row("imp", f"c{i}", {"kind": "preference", "description": d, "msgs": [], "domain": "misumi", "validity": "unknown",
                                       "sensitivity": sens, "speaker_basis": basis, "confidence": 0.9, "first_pass": "approve"}, "h")
        ci._append(work / "ledger.jsonl", {**row, "review": "human_gate"})
        ids[d] = row["candidate_id"]

    def llm(system, user):
        rows = json.loads(user)["rows"]
        return json.dumps({"rows": [{"id": r["id"], "decision": "accept", "rationale": "durable"} for r in rows]})
    out = ci.resolve_gates("imp", llm, root=tmp_path, inv=lambda d: [])
    assert out == {"accepted": 1, "rejected": 1, "people_wing": 1, "escalated": 1, "failed": 0}
    latest = {r["candidate_id"]: r for r in ci._read_jsonl(work / "ledger.jsonl")}
    assert latest[ids["User's mother likes watercolour painting"]]["wing"] == "people"
    assert latest[ids["User stores the api key in a note"]]["review"] == "human_gate"
    assert ci.resolve_gates("imp", llm, root=tmp_path, inv=lambda d: [])["accepted"] == 0
