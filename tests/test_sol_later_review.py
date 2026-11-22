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

def test_an_outputs_only_card_is_scoped_to_its_outputs():
    scope = rt._write_scope("odysseus", {"outputs": ["docs/a.md", "docs/b.md"], "result_path": "docs/a.md"})
    assert scope["allowed"] == ["docs/a.md", "docs/b.md"]


def test_explicit_allowed_paths_still_win():
    scope = rt._write_scope("odysseus", {"allowed_paths": ["docs/**"], "outputs": ["src/x.py"]})
    assert scope["allowed"] == ["docs/**"]


def test_a_write_with_no_scope_at_all_is_refused_before_dispatch():
    meta = {"execution_mode": "implementation", "outputs": []}
    assert rt._allowed_paths(meta) == []
    assert rt._static_blocker("implementation", {**meta, "allowed_paths": ["src/**"]}, True) is None
    assert rt._static_blocker("implementation", {"execution_mode": "implementation", "result_path": ""}, True) in {
        "write_scope_missing", "no_deliverable_surface"}


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

def test_a_losing_observer_does_not_overwrite_a_successful_finalisation(db, queue, monkeypatch):
    run = db.get(LazyUsageRun, activate(db))
    run.checkpoint = {**run.checkpoint, "lease": {"repo_id": "odysseus", "host_id": "lab"},
                      "write_scope": {"allowed": ["src/**"], "denied": []}}
    monkeypatch.setattr(rt.estate_write_lane, "finalize_execution",
                        lambda **kw: {"finalized": False, "reason": "finalize_failed"})
    monkeypatch.setattr(rt, "_execution_finalized", lambda run_, execution_id: True)
    outcome = rt._finalize_owned(db, run, "exec-1")
    assert outcome["finalized"] is True and outcome.get("already_finalized") is True


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
    assert len(sent) == 1 and sorted(results) == ["nothing_new", "sent"]


# ---- provider health ----------------------------------------------------------------------------------------------

def test_a_long_transcript_tail_without_session_markers_does_not_set_auth_failed():
    tail = "I am reading the authentication module and its 401 handler. " * 12
    result = estate_router._provider_outcome({"ok": False, "provider": "codex",
                                              "error": "codex exec exited 1:\n" + tail})
    assert result["state"] != "auth_failed"
