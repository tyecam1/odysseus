"""Failing-first regressions for the Sol review of #300-#304 at ad381be5 (gpt-6.2-sol, 2026-11-22).

Each test reproduces one finding before its fix:

P1 /decisions read other owners' debts; an outputs-only approval left writes without an allow-list;
P2 partial usage (cache-read + output) counted as a complete report; a gate-less legacy debt did not hold back
   an acceptance card; clearing a verification debt by recorded evidence left no acceptance queued; two observers
   could overwrite a successful finalisation; Discord de-duplication raced and a FIFO blocked the tick;
   a long transcript tail without session markers still steered provider health;
P3 Discord cards carried the internal task ref.
"""
import os
import threading
import time

import pytest

from tests.test_lazy_usage_delivery import activate, db, queue  # noqa: F401  (fixtures + helpers)
from tests.test_lazy_usage_reliability import SHA, WRITE, debt, terminal, verification_debt
from core.database import LazyUsageRun
from src import estate_router, lazy_usage_coordinator as coord, lazy_usage_runtime as rt, owner_decisions as od

ODY = "odysseus:ready/2026-11-22-sol-fixture.agent-task.md"


# ---- usage accounting -------------------------------------------------------------------------------------------

def test_cache_read_plus_output_is_a_fragment_not_a_complete_report():
    assert coord.usage_tokens({"cacheReadInputTokens": 20, "outputTokens": 7}, 150_000) == (0, 150_000)
    assert coord.usage_tokens({"cacheCreationInputTokens": 20, "output_tokens": 7}, 150_000) == (0, 150_000)


def test_ordinary_input_plus_output_is_still_measured():
    assert coord.usage_tokens({"inputTokens": 10, "outputTokens": 7, "cacheReadInputTokens": 3}, 150_000) == (20, 0)


# ---- write scope ------------------------------------------------------------------------------------------------

def test_a_card_without_allowed_paths_is_scoped_to_its_result_path_only():
    meta = {"outputs": ["docs/a.md", "docs/b.md"], "result_path": "docs/a.md"}
    assert rt._write_scope("odysseus", meta)["allowed"] == ["docs/a.md"]


def test_outputs_never_widen_the_scope_past_the_review_area_check():
    # `outputs` can name a canonical file while result_path sits in the review area: it must not be writable.
    meta = {"result_path": "automation/review/report.md", "outputs": ["docs/canonical.md", "minimal documentation updates"]}
    assert rt._write_scope("odysseus", meta)["allowed"] == ["automation/review/report.md"]


def test_explicit_allowed_paths_still_win():
    scope = rt._write_scope("odysseus", {"allowed_paths": ["docs/**"], "outputs": ["src/x.py"]})
    assert scope["allowed"] == ["docs/**"]


def test_an_outputs_only_card_is_scoped_to_its_literal_output_paths():
    meta = {"execution_mode": "implementation", "outputs": ["docs/result.md", "docs/other.md"]}
    assert rt._allowed_paths(meta) == ["docs/result.md", "docs/other.md"]
    assert rt._static_blocker("implementation", meta, True) is None


def test_prose_outputs_name_no_file_and_the_write_is_refused_before_dispatch():
    meta = {"execution_mode": "implementation", "outputs": ["minimal documentation/contract updates"]}
    assert rt._allowed_paths(meta) == []
    assert rt._static_blocker("implementation", meta, True) == "write_scope_missing"


def test_a_review_side_card_cannot_smuggle_a_canonical_output_past_the_review_area_check():
    meta = {"outputs": ["docs/canonical.md"]}
    assert rt._within_review_area(meta) is False


def test_a_run_checkpointed_with_an_empty_allow_list_cannot_finalise(db, queue, monkeypatch):
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "lease": {"repo_id": "odysseus", "host_id": "lab"},
                      "write_scope": {"allowed": [], "denied": []}}
    monkeypatch.setattr(rt.estate_write_lane, "finalize_execution",
                        lambda **kw: pytest.fail("finalisation must not run without an allow-list"))
    assert rt._finalize_owned(db, run, "exec-1") == {"finalized": False, "reason": "write_scope_missing"}


# ---- owner view -------------------------------------------------------------------------------------------------

def test_another_owners_debts_are_not_in_my_decision_view(db):
    terminal(db, ["odysseus"], owed=[debt(ODY, "owner_approval")])
    assert rt.all_owed_reviews(db, owner="bob") == []
    assert [d["task_ref"] for d in rt.all_owed_reviews(db, owner="operator")] == [ODY]
    assert [d["task_ref"] for d in rt.all_owed_reviews(db)] == [ODY]           # the backend tick sees all


def test_a_gateless_legacy_debt_holds_back_the_acceptance_card():
    legacy = {"task_ref": ODY, "task_id": "x", "error": "quota", "opened_at": "2026-11-20T10:00:00"}
    accept = {"task_ref": ODY, "task_id": "x", "gate": "owner_acceptance", "opened_at": "2026-11-21T10:00:00"}
    assert od.build_cards([legacy, accept]) == []


def test_a_discord_message_does_not_carry_the_internal_task_ref():
    text = od.render(od.build_cards([{"task_ref": ODY, "task_id": "2026-11-22-sol-fixture", "gate": "owner_acceptance",
                                      "opened_at": "2026-11-21T10:00:00"}]))
    assert "ready/" not in text and "agent-task" not in text and "sol fixture" in text


# ---- recorded verification must queue acceptance ------------------------------------------------------------------

def test_recorded_verification_of_a_finalised_write_queues_owner_acceptance(db, queue):
    good = [{"result": "pass", "commit_sha": SHA, "ref": "pytest tests -q: 9748 passed", "verified_by": "tye"}]
    ref = queue.add("odysseus", "w", **{**WRITE, "verification_evidence": good})
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "owed_reviews": [verification_debt(ref)]}
    rt._resolve_met_debts(run, ref, rt.refresh_frontier(["odysseus"]))
    gates = [d["gate"] for d in run.checkpoint["owed_reviews"]]
    assert gates == ["owner_acceptance"]
    assert run.checkpoint["owed_reviews"][0]["commit_sha"] == SHA
    rt._resolve_met_debts(run, ref, rt.refresh_frontier(["odysseus"]))              # idempotent
    assert [d["gate"] for d in run.checkpoint["owed_reviews"]] == ["owner_acceptance"]


# ---- concurrent finalisation ----------------------------------------------------------------------------------------

def test_a_losing_observer_reports_the_winners_finalisation_with_its_commit(db, queue, monkeypatch):
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "lease": {"repo_id": "odysseus", "host_id": "lab"},
                      "write_scope": {"allowed": ["src/**"], "denied": []}}
    monkeypatch.setattr(rt.estate_write_lane, "finalize_execution",
                        lambda **kw: {"finalized": False, "reason": "finalize_failed"})
    monkeypatch.setattr(rt, "_execution_finalization", lambda run_, execution_id: {"committed": True, "commit_sha": SHA})
    outcome = rt._finalize_owned(db, run, "exec-1")
    assert outcome["finalized"] is True and outcome["already_finalized"] is True
    assert outcome["committed"] is True and outcome["commit_sha"] == SHA


def test_a_settled_task_is_not_reopened_for_acceptance_by_a_later_verification_record(db, queue):
    good = [{"result": "pass", "commit_sha": SHA, "ref": "pytest tests -q: 9748 passed", "verified_by": "tye"}]
    ref = queue.add("odysseus", "w", **{**WRITE, "verification_evidence": good})
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "owed_reviews": [verification_debt(ref)],
                      "settled_reviews": {rt._task_key(ref): {"at": "2099-01-01T00:00:00", "status": "done"}}}
    rt._resolve_met_debts(run, ref, rt.refresh_frontier(["odysseus"]))
    assert run.checkpoint["owed_reviews"] == []


def test_activation_does_not_import_another_owners_debts(db):
    terminal(db, ["odysseus"], owed=[debt(ODY, "owner_approval")])
    bob = db.get(LazyUsageRun, rt.activate_run(db, "bob", ["odysseus"], {}, None)["id"])
    assert [d for d in bob.checkpoint.get("owed_reviews", []) if d.get("task_ref") == ODY] == []


# ---- Discord channel and state files --------------------------------------------------------------------------------

def _within(seconds, fn):
    box = {}
    thread = threading.Thread(target=lambda: box.update(value=fn()), daemon=True)
    thread.start()
    thread.join(seconds)
    return not thread.is_alive(), box.get("value")


def _unblock(path):
    try:
        os.close(os.open(path, os.O_RDWR | os.O_NONBLOCK))
    except OSError:
        pass


def test_a_fifo_channel_file_cannot_block_the_lifecycle_tick(tmp_path):
    fifo = tmp_path / "decision_channel.json"
    os.mkfifo(fifo)
    try:
        finished, value = _within(2, lambda: od._load_channel(fifo))
    finally:
        _unblock(fifo)
    assert finished and value[0] == "bad_channel"


def test_a_state_path_that_is_a_fifo_cannot_block_the_tick(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    state = tmp_path / "decision_cards_sent.json"
    os.symlink(fifo, state)
    try:
        finished, value = _within(2, lambda: od._read_state(state))
    finally:
        _unblock(fifo)
    assert finished and value == {}


def test_two_callers_do_not_both_send_the_same_card(tmp_path):
    channel = tmp_path / "decision_channel.json"
    channel.write_text('{"kind": "discord", "url": "https://discord.com/api/webhooks/123/abc"}')
    os.chmod(channel, 0o600)
    state = tmp_path / "state.json"
    sent = []

    def slow_post(url, payload, timeout):
        sent.append(payload)
        time.sleep(0.4)
        return 204

    owed = [{"task_ref": ODY, "task_id": "x", "gate": "owner_acceptance", "opened_at": "2026-11-21T10:00:00"}]
    results = []
    threads = [threading.Thread(target=lambda: results.append(
        od.notify(owed, state_path=state, channel_path=channel, post=slow_post, clock=lambda: 1_000.0,
                  min_interval=0))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert len(sent) == 1 and sorted(results) == ["busy", "sent"]


# ---- provider health ----------------------------------------------------------------------------------------------

def test_a_long_transcript_tail_without_session_markers_does_not_set_auth_failed():
    tail = "I am reading the authentication module and its 401 handler. " * 12
    result = estate_router._provider_outcome({"ok": False, "provider": "codex",
                                              "error": "codex exec exited 1:\n" + tail})
    assert result["state"] != "auth_failed"


def test_an_explicit_zero_input_count_is_a_real_report():
    assert coord.usage_tokens({"inputTokens": 0, "cacheReadInputTokens": 20, "outputTokens": 7}, 150_000) == (27, 0)


def test_a_genuine_auth_failure_with_long_diagnostics_still_sets_auth_failed():
    detail = "diagnostic line about the request pipeline and retry policy. " * 10
    result = estate_router._provider_outcome({"ok": False, "provider": "codex", "stderr": "ERROR 401 Unauthorized",
                                              "error": "codex exec exited 1:" + chr(10) + detail})
    assert result["state"] == "auth_failed"


# ---- round 3 -----------------------------------------------------------------------------------------------------

def test_a_json_text_finalisation_column_is_parsed_not_dict_converted():
    assert rt._json_record('{"committed": true, "commit_sha": "abc"}') == {"committed": True, "commit_sha": "abc"}
    assert rt._json_record({"commit_sha": "abc"}) == {"commit_sha": "abc"}
    assert rt._json_record(None) == {} and rt._json_record("not json") == {} and rt._json_record("[1]") == {}


def test_a_scalar_outputs_value_is_one_path_not_its_characters():
    assert rt._allowed_paths({"outputs": "docs/report.md"}) == ["docs/report.md"]


@pytest.mark.parametrize("path", ["docs/./report.md", "docs/../report.md", "docs//report.md", "/abs/report.md",
                                  "docs/*.md", "../x.md"])
def test_non_canonical_output_paths_are_never_a_scope(path):
    assert rt._allowed_paths({"outputs": [path]}) == []


@pytest.mark.skipif(os.sep != "/", reason="a backslash is a separator only on Windows")
def test_a_posix_file_name_with_backslashes_is_not_the_slash_path_it_resembles():
    from src.estate_worker import _scope_violation
    name = chr(92).join(["automation", "review", "report.md"])
    assert _scope_violation(name, ["automation/review/report.md"], []) is True
    assert _scope_violation("automation/review/report.md", ["automation/review/report.md"], []) is False


def _verified_debt(ref, opened):
    return {**verification_debt(ref), "opened_at": opened}


def test_an_old_settlement_does_not_suppress_acceptance_of_a_newer_attempt(db, queue):
    good = [{"result": "pass", "commit_sha": SHA, "ref": "pytest tests -q: 9748 passed", "verified_by": "tye"}]
    ref = queue.add("odysseus", "w", **{**WRITE, "verification_evidence": good})
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "owed_reviews": [_verified_debt(ref, "2026-11-22T00:00:00")],
                      "settled_reviews": {rt._task_key(ref): {"at": "2020-01-01T00:00:00", "status": "superseded"}}}
    rt._resolve_met_debts(run, ref, rt.refresh_frontier(["odysseus"]))
    assert [d["gate"] for d in run.checkpoint["owed_reviews"]] == ["owner_acceptance"]


def test_a_task_whose_verification_queued_acceptance_is_not_dispatched_again_after_the_card_changed(db, queue):
    ref = queue.add("odysseus", "w", **WRITE)
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "owed_reviews": [
        {**verification_debt(ref), "gate": "owner_acceptance", "acceptance_after_verification": True}]}
    assert rt._recent_blocker(run, ref, "a-revision-the-ledger-has-never-seen") == "awaiting_owner_acceptance"


def test_markerless_stdout_after_the_launcher_header_never_sets_auth_failed():
    prose = "I am reading the authentication code and its 401 handler. " * 10
    result = estate_router._provider_outcome({"ok": False, "provider": "codex",
                                              "error": "codex exec exited 1: " + prose + chr(10) + prose})
    assert result["state"] != "auth_failed"
