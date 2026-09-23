"""Stage 6 worker contract (plan §6.0 S6.6, S6.8–S6.12), worker side:
decide_once (U70, U70a), start/runner/abort decisions (U46, U47, U48,
U61), fence/close/release and retention (U60, U62, U72), prepare record
and runner (U57, U58), quiescence gating (U67 fake-cgroupfs form, U68,
U73), finalize/push attempts with real git (U64, U71, U74, U65/U76 push),
and execution closure (U75)."""
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import yaml

import src.estate_worker as estate_worker
from src.estate_worker_protocol import build_request, validate_response
from tests.helpers.fake_units import FakeUnits

_REAL_RUNNER_UNITS_SUPPORTED = estate_worker.estate_worker_procs.runner_units_supported


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (config_dir / "estate.yaml").write_text(yaml.safe_dump({"hosts": [{
        "id": "test-lab", "hostname": "THIS-HOST", "role": "lab", "identity_verified": True,
        "worker": {"enabled": True, "transport": "local"},
    }]}))
    (config_dir / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [{"id": "test-repo", "path": str(repo_path)}],
    }))
    monkeypatch.setattr(estate_worker.estate_router, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    monkeypatch.setattr(estate_worker, "_SPOOL_ROOT", tmp_path / "aoteru" / "spool")
    monkeypatch.setattr(estate_worker, "_PREPARE_ROOT", tmp_path / "aoteru" / "prepare")
    monkeypatch.setattr(estate_worker, "machine_fingerprint", lambda: "0123456789abcdef")
    monkeypatch.setattr(estate_worker, "_worker_version", lambda: "abc123")
    # Never launch a real systemd unit from a unit test; FakeUnits opts in.
    monkeypatch.setattr(estate_worker.estate_worker_procs, "runner_units_supported",
                        lambda: (False, "unit tests: real runner units disabled"))
    monkeypatch.setattr(estate_worker, "_DECISION_FS_PROBED", {})
    return {"root": tmp_path, "repo": repo_path}


@pytest.fixture
def units(cfg, monkeypatch):
    return FakeUnits(cfg["root"], monkeypatch, estate_worker)


def _call(verb, payload=None):
    request = build_request(verb, "test-lab", payload or {}, 30)
    response = estate_worker.handle(request)
    assert validate_response(response, request) == (True, None)
    return response


def _result(verb, payload=None):
    response = _call(verb, payload)
    assert response["ok"] is True, response
    return response["result"]


def _spool(execution_id):
    return estate_worker._SPOOL_ROOT / execution_id


def _codex_payload(cfg, execution_id="E1", head="abc"):
    return {
        "execution_id": execution_id, "kind": "codex-write", "objective": "change",
        "repo_id": "test-repo", "timeout_s": 30,
        "lease": {"lease_id": "L1", "worktree_path": str(cfg["repo"]), "branch": "feature",
                  "expected_head_sha": head},
    }


@pytest.fixture
def verified(cfg, monkeypatch):
    state = {"head": "abc"}
    monkeypatch.setattr(estate_worker, "_worktree_verification", lambda *args: {
        "ok": True, "path": str(cfg["repo"]), "reason": None, "head_sha": state["head"], "clean": True,
    })
    return state


# ---------------------------------------------------------------------
# S6.11 decide_once
# ---------------------------------------------------------------------

def test_u46_decide_once_has_exactly_one_winner_under_threads(cfg):
    target = _spool("race") / "claim.json"
    results, barrier = [], threading.Barrier(8)

    def _contender(index):
        barrier.wait()
        results.append(estate_worker.decide_once(target, {"by": index}))

    threads = [threading.Thread(target=_contender, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    winners = [decided for won, decided in results if won]
    assert len(winners) == 1
    assert all(decided == winners[0] for _won, decided in results)
    assert not list(target.parent.glob(".*.tmp-*"))


def test_u70a_winner_loser_and_reader_fsync_before_returning(cfg, monkeypatch):
    target = _spool("durable") / "claim.json"
    fsynced = []
    real = estate_worker._fsync_dir
    monkeypatch.setattr(estate_worker, "_fsync_dir", lambda path: (fsynced.append(Path(path)), real(path)))
    estate_worker.decide_once(target, {"n": 1})
    assert target.parent in fsynced and target.parent.parent in fsynced   # new dir + its parent
    anchor = estate_worker._SPOOL_ROOT.parent
    for label, action in (("loser", lambda: estate_worker.decide_once(target, {"n": 2})),
                          ("reader", lambda: estate_worker.read_decision(target))):
        fsynced.clear()
        action()
        chain = [target.parent, target.parent.parent, anchor]
        assert all(directory in fsynced for directory in chain), label


def test_u70a_reader_of_a_paused_winner_fsyncs_after_observing(cfg, monkeypatch):
    """A winner paused between link and its own fsync: a reader that
    observes the file still returns only after ITS fsync of the chain."""
    target = _spool("paused") / "claim.json"
    paused, resume = threading.Event(), threading.Event()
    real_chain = estate_worker._fsync_chain
    order = []

    def _chain(directory):
        if threading.current_thread().name == "winner":
            paused.set()
            resume.wait(5)
        order.append(threading.current_thread().name)
        real_chain(directory)

    monkeypatch.setattr(estate_worker, "_fsync_chain", _chain)
    winner = threading.Thread(target=estate_worker.decide_once, args=(target, {"n": 1}), name="winner")
    winner.start()
    assert paused.wait(5)
    seen = {}
    reader = threading.Thread(target=lambda: seen.update(v=estate_worker.read_decision(target)), name="reader")
    reader.start()
    reader.join(5)
    assert seen["v"] == {"n": 1} and order == ["reader"]
    resume.set()
    winner.join(5)


def test_u70a_fsync_failure_means_the_caller_does_not_act(cfg, units, verified, monkeypatch):
    def _boom(path):
        raise OSError("fsync failed")
    monkeypatch.setattr(estate_worker, "_fsync_dir", _boom)
    response = _call("start", _codex_payload(cfg))
    assert response["ok"] is False
    assert units.spawned == []


def test_u70_decision_fs_unsupported_refuses_every_write_verb_before_claim(cfg, units, verified, monkeypatch):
    real_link = os.link

    def _link(src, dst):
        if ".decision-probe-" in str(dst):
            raise OSError(1, "Operation not permitted")
        return real_link(src, dst)

    monkeypatch.setattr(os, "link", _link)
    for verb, payload in (
        ("start", _codex_payload(cfg)),
        ("worktree.prepare", {"repo_id": "test-repo", "branch": "b", "base_ref": "HEAD",
                              "lease": {"lease_id": "LP", "host_id": "test-lab"}}),
    ):
        response = _call(verb, payload)
        assert response["ok"] is False and response["error"]["code"] == "executor_unavailable", verb
    assert not (_spool("E1") / "claim.json").exists()
    assert not (estate_worker._PREPARE_ROOT / "LP" / "claim.json").exists()
    assert units.spawned == []
    assert estate_worker._write_prerequisites()["decision_fs"] is False


def test_u68_runner_unit_probe_failure_refuses_before_claim(cfg, monkeypatch, verified):
    FakeUnits(cfg["root"], monkeypatch, estate_worker, supported=False)
    response = _call("start", _codex_payload(cfg))
    assert response["ok"] is False and response["error"]["code"] == "executor_unavailable"
    assert not (_spool("E1") / "claim.json").exists()
    assert _result("health")["write_prerequisites"]["runner_units"] is False


# ---------------------------------------------------------------------
# S6.6 start / runner / abort
# ---------------------------------------------------------------------

def test_u46_same_id_start_during_claim_answers_starting_and_spawns_once(cfg, units, verified):
    first = _result("start", _codex_payload(cfg))
    second = _result("start", _codex_payload(cfg))
    assert first["state"] == second["state"] == "starting"
    assert second["reused"] is True and len(units.spawned) == 1
    units.enter("aoteru-run-E1.service")
    estate_worker.decide_once(_spool("E1") / "run.json",
                              {"decision": "execute", **units.handle("aoteru-run-E1.service")})
    third = _result("start", _codex_payload(cfg))
    assert third["state"] == "running" and third["handle"]["unit"] == "aoteru-run-E1.service"
    assert len(units.spawned) == 1


def test_u47_deterministic_spawn_failure_is_start_failed_and_retained(cfg, units, verified, monkeypatch):
    def _refuse(*args, **kwargs):
        raise estate_worker.estate_worker_procs.ProcessLayerError("executor_unavailable", "no bus")
    monkeypatch.setattr(estate_worker.estate_worker_procs, "spawn_runner_unit", _refuse)
    first = _result("start", _codex_payload(cfg))
    assert first["state"] == "start_failed" and first["accepted"] is False
    retry = _result("start", _codex_payload(cfg))
    assert retry["state"] == "start_failed" and retry["reused"] is True
    assert (_spool("E1") / "claim.json").exists() and (_spool("E1") / "run.json").exists()


def test_u48a_observer_abort_wins_then_runner_never_executes(cfg, units, verified, monkeypatch):
    _result("start", _codex_payload(cfg))
    claim_path = _spool("E1") / "claim.json"
    old = json.loads(claim_path.read_text())
    old["claimed_at"] = "2020-01-01T00:00:00Z"
    os.chmod(claim_path, 0o644)
    claim_path.write_text(json.dumps(old))            # age the claim (test-only rewrite)
    assert _result("status", {"execution_id": "E1"})["state"] == "start_failed"
    calls = []
    monkeypatch.setattr(estate_worker.estate_router, "_execute_codex_with_sandbox",
                        lambda *a, **k: calls.append(1) or {"ok": True})
    units.enter("aoteru-run-E1.service")
    assert estate_worker._run_spooled("E1") == 0
    assert calls == []


def test_u48b_runner_decided_first_then_stale_observer_loses(cfg, units, verified):
    _result("start", _codex_payload(cfg))
    estate_worker.decide_once(_spool("E1") / "run.json",
                              {"decision": "execute", **units.handle("aoteru-run-E1.service")})
    claim_path = _spool("E1") / "claim.json"
    old = json.loads(claim_path.read_text())
    old["claimed_at"] = "2020-01-01T00:00:00Z"
    claim_path.write_text(json.dumps(old))
    status = _result("status", {"execution_id": "E1"})
    assert status["state"] == "running"
    assert estate_worker.read_decision(_spool("E1") / "run.json")["decision"] == "execute"


def test_u48c_observer_paused_mid_decision_never_overrides_execute(cfg, units, verified, monkeypatch):
    _result("start", _codex_payload(cfg))
    real = estate_worker.decide_once
    gate, go = threading.Event(), threading.Event()

    def _slow(target, content):
        if content.get("by") == "observer":
            gate.set()
            go.wait(5)
        return real(target, content)

    monkeypatch.setattr(estate_worker, "decide_once", _slow)
    monkeypatch.setattr(estate_worker, "STARTING_STALE_SECONDS", -1)
    observer = threading.Thread(target=lambda: _result("status", {"execution_id": "E1"}))
    observer.start()
    assert gate.wait(5)
    real(_spool("E1") / "run.json", {"decision": "execute", **units.handle("aoteru-run-E1.service")})
    go.set()
    observer.join(5)
    assert estate_worker.read_decision(_spool("E1") / "run.json")["decision"] == "execute"
    monkeypatch.setattr(estate_worker, "decide_once", real)
    assert _result("status", {"execution_id": "E1"})["state"] == "running"


def test_u73_terminal_record_with_populated_unit_stays_running(cfg, units):
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                      result={"ok": True, "output": "x"})
    pending = _result("status", {"execution_id": "E1"})
    assert pending["state"] == "running" and pending["terminal_pending"] is True
    assert pending["quiescent"] is False and "result" not in pending
    units.set_populated("aoteru-run-E1.service", None)
    done = _result("status", {"execution_id": "E1"})
    assert done["state"] == "succeeded" and done["quiescent"] is True


def test_u67_unknown_quiescence_blocks_exactly_like_populated(cfg, units, monkeypatch):
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"})
    monkeypatch.setattr(estate_worker.estate_worker_procs, "_CGROUP_ROOT", cfg["root"] / "missing-cgroupfs")
    status = _result("status", {"execution_id": "E1"})
    assert status["quiescent"] is None and status["process_alive"] is True
    assert status["state"] == "running"


def test_u67_runner_outside_its_dedicated_unit_aborts_before_executing(cfg, units, monkeypatch):
    units.write_spool("E1")
    calls = []
    monkeypatch.setattr(estate_worker.estate_router, "_execute_codex_with_sandbox",
                        lambda *a, **k: calls.append(1) or {"ok": True})
    for cgroup in (None, "/", units.cgroup("aoteru-run-OTHER.service"), "/user.slice/session-1.scope"):
        units.current_cgroup = cgroup
        estate_worker._run_spooled("E1")
    assert calls == []
    run = estate_worker.read_decision(_spool("E1") / "run.json")
    assert run["decision"] == "abort" and run["by"] == "runner"


def test_tree_quiescent_rules(cfg, units):
    procs = estate_worker.estate_worker_procs
    handle = units.handle("aoteru-run-X.service")
    units.set_populated("aoteru-run-X.service", True)
    assert procs.tree_quiescent(handle) is False
    units.set_populated("aoteru-run-X.service", False)
    assert procs.tree_quiescent(handle) is True
    units.set_populated("aoteru-run-X.service", None)
    assert procs.tree_quiescent(handle) is True                       # collected
    assert procs.tree_quiescent({**handle, "cgroup": "/"}) is None       # never the root cgroup
    assert procs.tree_quiescent({**handle, "unit": "other.service"}) is None
    assert procs.tree_quiescent(None) is None


# ---------------------------------------------------------------------
# S6.8 fence / close / release / retention
# ---------------------------------------------------------------------

def test_u69_fence_on_missing_spool_makes_the_id_permanently_unstartable(cfg, units, verified):
    fenced = _result("status", {"execution_id": "E1", "fence": True})
    assert fenced["state"] == "fenced" and fenced["fenced_now"] is True
    start = _result("start", _codex_payload(cfg))
    assert start["state"] == "fenced" and start["accepted"] is False and start["reused"] is True
    assert units.spawned == []


def test_u69_fence_on_starting_claim_aborts_the_runner(cfg, units, verified, monkeypatch):
    _result("start", _codex_payload(cfg))
    assert _result("status", {"execution_id": "E1", "fence": True})["state"] == "start_failed"
    calls = []
    monkeypatch.setattr(estate_worker.estate_router, "_execute_codex_with_sandbox",
                        lambda *a, **k: calls.append(1) or {"ok": True})
    units.enter("aoteru-run-E1.service")
    estate_worker._run_spooled("E1")
    assert calls == []


def test_status_without_fence_is_read_only_for_missing_spool(cfg, units):
    assert _result("status", {"execution_id": "E1"})["state"] == "unknown"
    assert not (_spool("E1") / "claim.json").exists()


def test_u62_spool_release_refused_for_live_or_starting_writer(cfg, units, verified):
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "running"})
    refused = _call("spool.release", {"execution_id": "E1", "resolution": "recovered"})
    assert refused["ok"] is False and refused["error"]["code"] == "authority_denied"
    units.set_populated("aoteru-run-E1.service", None)
    released = _result("spool.release", {"execution_id": "E1", "resolution": "recovered"})
    assert released["released"] is True and released["already_released"] is False
    again = _result("spool.release", {"execution_id": "E1", "resolution": "recovered"})
    assert again["already_released"] is True
    assert (_spool("E1") / "closed.json").exists()


def test_u62_release_of_a_missing_spool_fences_it(cfg, units, verified):
    released = _result("spool.release", {"execution_id": "E9", "resolution": "not_started"})
    assert released["released"] is True
    assert _result("start", _codex_payload(cfg, "E9"))["state"] == "fenced"


def test_u60_unacknowledged_write_spool_is_never_compacted(cfg, units, monkeypatch):
    spool = units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                              result={"ok": True}, populated=False,
                              request={"execution_id": "E1", "kind": "codex-write"})
    (spool / "worker.log").write_text("log")
    old = time.time() - 30 * 24 * 3600
    os.utime(spool / "state.json", (old, old))
    estate_worker._gc_spools()
    assert (spool / "result.json").exists() and (spool / "worker.log").exists()
    assert _result("status", {"execution_id": "E1"})["handle"]["unit"] == "aoteru-run-E1.service"


def test_u60_released_write_spool_compacts_only_after_seven_days(cfg, units, monkeypatch):
    spool = units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                              result={"ok": True}, populated=False,
                              request={"execution_id": "E1", "kind": "codex-write"})
    _result("spool.release", {"execution_id": "E1", "resolution": "finalized"})
    estate_worker._gc_spools()
    assert (spool / "result.json").exists()
    monkeypatch.setattr(estate_worker, "SPOOL_COMPACT_AFTER_RELEASE_SECONDS", -1)
    estate_worker._gc_spools()
    assert not (spool / "result.json").exists()
    assert estate_worker._json_read(spool / "state.json")["state"] == "tombstone"
    for decision in ("claim.json", "run.json", "released.json", "closed.json"):
        assert (spool / decision).exists(), decision
    assert _result("status", {"execution_id": "E1"})["state"] == "tombstone"


def test_u60_selftest_spool_compacts_after_terminal_ttl(cfg, units, monkeypatch):
    spool = units.write_spool("S1", run_unit="aoteru-run-S1.service", state={"state": "succeeded"},
                              result={"ok": True}, populated=False,
                              request={"execution_id": "S1", "kind": "noop-sleep"})
    estate_worker._gc_spools()
    assert (spool / "result.json").exists()
    old = time.time() - 8 * 24 * 3600
    os.utime(spool / "state.json", (old, old))
    estate_worker._gc_spools()
    assert estate_worker._json_read(spool / "state.json")["state"] == "tombstone"
    assert (spool / "claim.json").exists()


def test_u60_stale_decision_temp_files_are_removed(cfg, units):
    spool = units.write_spool("E1")
    temp = spool / ".run.json.tmp-1-deadbeef"
    temp.write_text("{}")
    old = time.time() - 3600
    os.utime(temp, (old, old))
    estate_worker._gc_spools()
    assert not temp.exists() and (spool / "claim.json").exists()


def test_u61_tombstoned_or_terminal_id_replay_never_spawns(cfg, units, verified, monkeypatch):
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                      result={"ok": True}, populated=False)
    _result("spool.release", {"execution_id": "E1", "resolution": "finalized"})
    monkeypatch.setattr(estate_worker, "SPOOL_COMPACT_AFTER_RELEASE_SECONDS", -1)
    estate_worker._gc_spools()
    replay = _result("start", _codex_payload(cfg))
    assert replay["reused"] is True and replay["state"] == "tombstone" and replay["accepted"] is False
    assert units.spawned == []


def test_u72_compaction_racing_claims_and_fences_never_loses_decisions(cfg, units, verified, monkeypatch):
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                      result={"ok": True}, populated=False)
    _result("spool.release", {"execution_id": "E1", "resolution": "finalized"})
    monkeypatch.setattr(estate_worker, "SPOOL_COMPACT_AFTER_RELEASE_SECONDS", -1)
    before = {name: (_spool("E1") / name).read_text() for name in ("claim.json", "run.json", "released.json")}
    stop = threading.Event()
    errors = []

    def _loop(action):
        while not stop.is_set():
            try:
                action()
            except Exception as exc:   # pragma: no cover - recorded for the assertion
                errors.append(exc)

    workers = [threading.Thread(target=_loop, args=(estate_worker._gc_spools,)),
               threading.Thread(target=_loop, args=(lambda: _call("start", _codex_payload(cfg)),)),
               threading.Thread(target=_loop, args=(lambda: _call("status", {"execution_id": "E1", "fence": True}),))]
    for worker in workers:
        worker.start()
    time.sleep(0.5)
    stop.set()
    for worker in workers:
        worker.join(5)
    assert errors == []
    after = {name: (_spool("E1") / name).read_text() for name in before}
    assert after == before and units.spawned == []
    assert any(_spool("E1").iterdir())


# ---------------------------------------------------------------------
# S6.9 prepare
# ---------------------------------------------------------------------

def _prepare_payload(lease_id="LP"):
    return {"repo_id": "test-repo", "branch": "feat/x", "base_ref": "HEAD",
            "lease": {"lease_id": lease_id, "host_id": "test-lab"}}


def test_u50_prepare_without_lease_is_refused_before_any_git(cfg, units, monkeypatch):
    called = []
    monkeypatch.setattr(estate_worker.worktree_ops, "create_or_reuse_worktree", lambda *a, **k: called.append(1))
    payload = _prepare_payload()
    payload.pop("lease")
    response = _call("worktree.prepare", payload)
    assert response["ok"] is False and response["error"]["code"] == "bad_request"
    assert called == [] and units.spawned == []


def test_u57_fence_first_then_delayed_prepare_never_mutates(cfg, units):
    fenced = _result("worktree.prepare_status", {"lease_id": "LP", "fence": True})
    assert fenced["state"] == "fenced"
    late = _result("worktree.prepare", _prepare_payload())
    assert late["state"] == "fenced" and late["reused"] is True
    assert units.spawned == []


def test_u57_prepare_record_is_idempotent_and_runner_outcomes(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker, "_DEFAULT_PREPARE_WAIT_S", 0.2)
    first = _result("worktree.prepare", _prepare_payload())
    assert first["state"] == "preparing" and first["reused"] is False
    again = _result("worktree.prepare", _prepare_payload())
    assert again["reused"] is True and len(units.spawned) == 1
    # runner runs in its unit and succeeds
    monkeypatch.setattr(estate_worker.worktree_ops, "create_or_reuse_worktree",
                        lambda repo, branch, base_ref: {"path": str(cfg["repo"]), "branch": branch})
    monkeypatch.setattr(estate_worker.worktree_ops, "verify_worktree", lambda repo, path, branch: {
        "ok": True, "path": path, "branch": branch, "head": "abc"})
    monkeypatch.setattr(estate_worker, "git_is_clean", lambda path: (True, ""))
    units.enter("aoteru-prepare-LP.service")
    assert estate_worker._run_prepare("LP") == 0
    still = _result("worktree.prepare_status", {"lease_id": "LP"})
    assert still["state"] == "preparing" and still["quiescent"] is False   # unit still populated
    units.set_populated("aoteru-prepare-LP.service", None)
    done = _result("worktree.prepare_status", {"lease_id": "LP"})
    assert done["state"] == "prepared" and done["clean"] is True and done["head_sha"] == "abc"


def test_u57_dead_runner_is_interrupted_only_when_quiescent(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker, "_DEFAULT_PREPARE_WAIT_S", 0.1)
    _result("worktree.prepare", _prepare_payload())
    record = estate_worker._PREPARE_ROOT / "LP"
    estate_worker.decide_once(record / "run.json",
                              {"decision": "execute", **units.handle("aoteru-prepare-LP.service")})
    units.set_populated("aoteru-prepare-LP.service", True)       # runner gone, orphan git alive
    assert _result("worktree.prepare_status", {"lease_id": "LP"})["state"] == "preparing"
    units.set_populated("aoteru-prepare-LP.service", None)
    assert _result("worktree.prepare_status", {"lease_id": "LP"})["state"] == "prepare_interrupted"


def test_u58_post_claim_exception_is_recorded_prepare_failed(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker, "_DEFAULT_PREPARE_WAIT_S", 0.1)
    _result("worktree.prepare", _prepare_payload())

    def _boom(*args, **kwargs):
        raise RuntimeError("git worktree add failed")
    monkeypatch.setattr(estate_worker.worktree_ops, "create_or_reuse_worktree", _boom)
    units.enter("aoteru-prepare-LP.service")
    estate_worker._run_prepare("LP")
    units.set_populated("aoteru-prepare-LP.service", None)
    status = _result("worktree.prepare_status", {"lease_id": "LP"})
    assert status["state"] == "prepare_failed" and "worktree add failed" in status["error"]


def test_prepare_runner_disables_git_hooks_and_auto_gc(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker, "_DEFAULT_PREPARE_WAIT_S", 0.1)
    _result("worktree.prepare", _prepare_payload())
    seen = {}

    def _capture(repo, branch, base_ref):
        seen.update({k: v for k, v in os.environ.items() if k.startswith("GIT_CONFIG_")})
        raise RuntimeError("stop")
    monkeypatch.setattr(estate_worker.worktree_ops, "create_or_reuse_worktree", _capture)
    for key in list(os.environ):
        if key.startswith("GIT_CONFIG_"):
            monkeypatch.delenv(key)
    units.enter("aoteru-prepare-LP.service")
    estate_worker._run_prepare("LP")
    pairs = {seen[f"GIT_CONFIG_KEY_{i}"]: seen[f"GIT_CONFIG_VALUE_{i}"] for i in range(int(seen["GIT_CONFIG_COUNT"]))}
    assert pairs["gc.auto"] == "0" and pairs["maintenance.auto"] == "false"
    assert Path(pairs["core.hooksPath"]).is_dir() and not any(Path(pairs["core.hooksPath"]).iterdir())


# ---------------------------------------------------------------------
# S6.10 finalize / push with real git
# ---------------------------------------------------------------------

def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(cfg, monkeypatch):
    origin = cfg["root"] / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    main = cfg["repo"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(main)], check=True)
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "README").write_text("r\n")
    _git(main, "add", "README")
    _git(main, "commit", "-q", "-m", "init")
    _git(main, "remote", "add", "origin", str(origin))
    worktree = cfg["root"] / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat/x", str(worktree))
    head = _git(worktree, "rev-parse", "HEAD")
    for key in list(os.environ):
        if key.startswith("GIT_CONFIG_"):
            monkeypatch.delenv(key)
    return {"main": main, "origin": origin, "wt": worktree, "head": head}


def _finalize_request(repo, execution_id="E1"):
    return {"execution_id": execution_id, "repo_id": "test-repo", "worktree_path": str(repo["wt"]),
            "branch": "feat/x", "commit_message": "apply", "expected_head_sha": repo["head"]}


def test_u64_history_bound_commit_and_no_change(cfg, repo):
    spool = _spool("E1")
    no_change = estate_worker._finalize_logic("E1", spool, _finalize_request(repo))
    assert no_change["outcome"] == "finalized" and no_change["committed"] is False
    assert no_change["push"]["state"] == "not_required"
    (repo["wt"] / "new.txt").write_text("x")
    done = estate_worker._finalize_logic("E1", spool, _finalize_request(repo))
    assert done["outcome"] == "finalized" and done["committed"] is True
    assert done["parent_sha"] == repo["head"]
    assert "Aoteru-Execution: E1" in _git(repo["wt"], "log", "-1", "--format=%B")
    assert done["push"]["state"] == "pushed"
    assert _git(repo["origin"], "rev-parse", "refs/heads/feat/x") == done["commit_sha"]


def test_u71_lost_response_retry_adopts_via_commit_record(cfg, repo):
    spool = _spool("E1")
    (repo["wt"] / "new.txt").write_text("x")
    first = estate_worker._finalize_logic("E1", spool, _finalize_request(repo))
    retry = estate_worker._finalize_logic("E1", spool, _finalize_request(repo))
    assert retry["outcome"] == "finalized" and retry["adopted"] is True
    assert retry["commit_sha"] == first["commit_sha"]


def test_u71_forged_trailer_without_commit_record_is_ambiguous(cfg, repo):
    (repo["wt"] / "foreign.txt").write_text("f")
    _git(repo["wt"], "add", "foreign.txt")
    subprocess.run(["git", "-C", str(repo["wt"]), "-c", "user.email=o@e", "-c", "user.name=o", "commit", "-q",
                    "-m", "operator\n\nAoteru-Execution: E1"], check=True)
    result = estate_worker._finalize_logic("E1", _spool("E1"), _finalize_request(repo))
    assert result["outcome"] == "finalize_ambiguous" and result["trailer_matches"] is True
    assert result.get("adopted") is not True


def test_u71_commit_record_that_no_longer_matches_head_is_refused(cfg, repo):
    spool = _spool("E1")
    (repo["wt"] / "new.txt").write_text("x")
    estate_worker._finalize_logic("E1", spool, _finalize_request(repo))
    (repo["wt"] / "later.txt").write_text("y")
    _git(repo["wt"], "add", "later.txt")
    subprocess.run(["git", "-C", str(repo["wt"]), "-c", "user.email=o@e", "-c", "user.name=o",
                    "commit", "-q", "-m", "later"], check=True)
    assert estate_worker._finalize_logic("E1", spool, _finalize_request(repo))["outcome"] == "authority_denied"


def test_u65_push_failure_then_exact_commit_retry_and_containment(cfg, repo):
    hook = repo["origin"] / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    (repo["wt"] / "new.txt").write_text("x")
    done = estate_worker._finalize_logic("E1", _spool("E1"), _finalize_request(repo))
    assert done["outcome"] == "finalized" and done["push"]["state"] == "failed"
    hook.unlink()
    retry = estate_worker._push_logic({"repo_id": "test-repo", "branch": "feat/x", "commit_sha": done["commit_sha"]})
    assert retry["push"]["state"] == "pushed" and retry["push"]["contained"] is False
    assert _git(repo["origin"], "rev-parse", "refs/heads/feat/x") == done["commit_sha"]
    # A later commit pushed first: the earlier exact commit is then "contained".
    (repo["wt"] / "later.txt").write_text("y")
    _git(repo["wt"], "add", "later.txt")
    subprocess.run(["git", "-C", str(repo["wt"]), "-c", "user.email=o@e", "-c", "user.name=o",
                    "commit", "-q", "-m", "later"], check=True)
    _git(repo["wt"], "push", "-q", "origin", "HEAD:refs/heads/feat/x")
    contained = estate_worker._push_logic({"repo_id": "test-repo", "branch": "feat/x",
                                           "commit_sha": done["commit_sha"]})
    assert contained["push"]["state"] == "pushed" and contained["push"]["contained"] is True
    assert _git(repo["origin"], "rev-parse", "refs/heads/feat/x") != done["commit_sha"]   # never rewound


def test_u66_push_of_absent_commit_is_not_found(cfg, repo):
    assert estate_worker._push_logic({"repo_id": "test-repo", "branch": "feat/x",
                                      "commit_sha": "0" * 40})["outcome"] == "not_found"


# ---------------------------------------------------------------------
# Attempt units, closure (S6.10 / S6.12)
# ---------------------------------------------------------------------

@pytest.fixture
def inline_attempts(units, monkeypatch):
    """Run finalize/push attempt runners synchronously inside their
    (fake) unit, then collect the unit as a real one would on exit."""
    real_spawn = units._spawn

    def _spawn(argv, cwd, log_path, unit):
        answer = real_spawn(argv, cwd, log_path, unit)
        if unit.startswith(("aoteru-finalize-", "aoteru-push-")):
            flag = argv.index("--run-finalize") if "--run-finalize" in argv else argv.index("--run-push")
            kind = "finalize" if argv[flag] == "--run-finalize" else "push"
            units.enter(f"{unit}.service")
            estate_worker._run_attempt(kind, argv[flag + 1], argv[flag + 2])
            if units.keep_populated is None or unit not in units.keep_populated:
                units.set_populated(f"{unit}.service", None)
        return answer

    units.keep_populated = set()
    monkeypatch.setattr(estate_worker.estate_worker_procs, "spawn_runner_unit", _spawn)
    return units


def test_u74_finalize_reports_only_when_every_attempt_is_quiescent(cfg, repo, inline_attempts, monkeypatch):
    monkeypatch.setattr(estate_worker, "_DEFAULT_GIT_UNIT_WAIT_S", 0.3)
    inline_attempts.write_spool("E1")
    (repo["wt"] / "new.txt").write_text("x")
    inline_attempts.keep_populated.add("aoteru-finalize-E1-1")
    first = _result("worktree.finalize", _finalize_request(repo))
    assert first["outcome"] == "finalize_in_progress"          # attempt 1 still populated
    inline_attempts.keep_populated.clear()
    second = _result("worktree.finalize", _finalize_request(repo))
    assert second["outcome"] == "finalize_in_progress"         # adopts, but attempt 1 still live
    inline_attempts.set_populated("aoteru-finalize-E1-1.service", None)
    third = _result("worktree.finalize", _finalize_request(repo))
    assert third["outcome"] == "finalized" and third["adopted"] is True


def test_u74_attempt_without_run_decision_is_fenced_by_a_later_attempt(cfg, repo, inline_attempts, monkeypatch):
    monkeypatch.setattr(estate_worker, "_DEFAULT_GIT_UNIT_WAIT_S", 0.3)
    spool = inline_attempts.write_spool("E1")
    estate_worker.decide_once(spool / "finalize" / "attempt-1.json", {"request": {}})   # launcher crashed
    result = _result("worktree.finalize", _finalize_request(repo))
    assert result["outcome"] == "finalized" and result["attempt"] == 2
    assert estate_worker.read_decision(spool / "finalize" / "attempt-1.run.json")["decision"] == "abort"


def test_u75_closure_stops_a_later_finalize_before_any_git(cfg, repo, inline_attempts, monkeypatch):
    spool = inline_attempts.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                                        populated=False)
    closure = _result("status", {"execution_id": "E1", "close": True})
    assert closure["closed"] is True and closure["quiescent"] is True
    (repo["wt"] / "new.txt").write_text("x")
    late = _result("worktree.finalize", _finalize_request(repo))
    assert late["outcome"] == "execution_closed"
    assert _git(repo["wt"], "rev-parse", "HEAD") == repo["head"]
    assert not any(u["unit"].startswith("aoteru-finalize-") for u in inline_attempts.spawned)


def test_u75_attempt_recorded_before_closure_is_seen_by_the_closer(cfg, repo, units):
    spool = units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                              populated=False)
    estate_worker.decide_once(spool / "finalize" / "attempt-1.json", {"request": {}})
    estate_worker.decide_once(spool / "finalize" / "attempt-1.run.json",
                              {"decision": "execute", **units.handle("aoteru-finalize-E1-1.service")})
    units.set_populated("aoteru-finalize-E1-1.service", True)
    closure = _result("status", {"execution_id": "E1", "close": True})
    assert closure["quiescent"] is False
    assert any(u["kind"] == "finalize-1" and u["quiescent"] is False for u in closure["units"])


def test_u76_push_after_closure_still_runs(cfg, repo, inline_attempts, monkeypatch):
    hook = repo["origin"] / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    inline_attempts.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                                populated=False)
    (repo["wt"] / "new.txt").write_text("x")
    done = _result("worktree.finalize", _finalize_request(repo))
    assert done["outcome"] == "finalized" and done["push"]["state"] == "failed"
    _result("spool.release", {"execution_id": "E1", "resolution": "finalized"})
    hook.unlink()
    pushed = _result("worktree.push", {"execution_id": "E1", "repo_id": "test-repo", "branch": "feat/x",
                                       "commit_sha": done["commit_sha"]})
    assert pushed["pushed"] is True
    # a populated push unit never blocks the worktree aggregate
    spool = _spool("E1")
    estate_worker.decide_once(spool / "push" / "attempt-9.json", {"request": {}})
    estate_worker.decide_once(spool / "push" / "attempt-9.run.json",
                              {"decision": "execute", **inline_attempts.handle("aoteru-push-E1-9.service")})
    inline_attempts.set_populated("aoteru-push-E1-9.service", True)
    assert _result("status", {"execution_id": "E1"})["quiescent"] is True


def test_dead_runner_without_terminal_record_is_interrupted_only_when_quiescent(cfg, units):
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "running"})
    assert _result("status", {"execution_id": "E1"})["state"] == "running"
    units.set_populated("aoteru-run-E1.service", None)
    status = _result("status", {"execution_id": "E1"})
    assert status["state"] == "interrupted" and status["quiescent"] is True


# ---------------------------------------------------------------------
# 6c adjudication regressions
# ---------------------------------------------------------------------

def test_6c_f2_worktree_verification_runs_in_a_tracked_unit(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker.worktree_ops, "is_live_checkout_path", lambda *a: False)
    monkeypatch.setattr(estate_worker.worktree_ops, "verify_worktree", lambda repo, path, branch: {
        "ok": True, "path": path, "branch": branch, "head": "abc"})
    monkeypatch.setattr(estate_worker, "git_is_clean", lambda path: (True, ""))
    result = _result("worktree.verify", {"repo_id": "test-repo", "worktree_path": str(cfg["repo"]),
                                         "branch": "feature"})
    assert result["ok"] is True and result["clean"] is True and result["head_sha"] == "abc"
    assert len(units.verify_units) == 1 and units.verify_units[0].startswith("aoteru-verify-")


def test_6c_f2_every_worker_git_child_has_fsmonitor_and_hooks_disabled(cfg, units, monkeypatch):
    for key in list(os.environ):
        if key.startswith("GIT_CONFIG_"):
            monkeypatch.delenv(key)
    _result("health")
    pairs = {os.environ[f"GIT_CONFIG_KEY_{i}"]: os.environ[f"GIT_CONFIG_VALUE_{i}"]
             for i in range(int(os.environ["GIT_CONFIG_COUNT"]))}
    assert pairs["core.fsmonitor"] == "false" and pairs["gc.auto"] == "0"
    assert Path(pairs["core.hooksPath"]).name == ".no-hooks"


def test_6c_f3_starter_spawn_record_never_clobbers_a_fast_runner(cfg, units, verified, monkeypatch):
    real_spawn = units._spawn

    def _fast(argv, cwd, log_path, unit):
        answer = real_spawn(argv, cwd, log_path, unit)
        spool = _spool("E1")
        estate_worker.decide_once(spool / "run.json", {"decision": "execute", **units.handle(f"{unit}.service")})
        estate_worker._json_write(spool / "state.json", {"state": "succeeded"})
        estate_worker._json_write(spool / "result.json", {"ok": True, "output": "fast"})
        units.set_populated(f"{unit}.service", None)
        return answer

    monkeypatch.setattr(estate_worker.estate_worker_procs, "spawn_runner_unit", _fast)
    _result("start", _codex_payload(cfg))
    assert _result("status", {"execution_id": "E1"})["state"] == "succeeded"
    assert estate_worker._json_read(_spool("E1") / "state.json")["state"] == "succeeded"


def test_6c_f4_terminal_waits_for_the_aggregate_not_only_the_writer(cfg, units):
    spool = units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                              populated=False)
    estate_worker.decide_once(spool / "finalize" / "attempt-1.json", {"request": {}})
    estate_worker.decide_once(spool / "finalize" / "attempt-1.run.json",
                              {"decision": "execute", **units.handle("aoteru-finalize-E1-1.service")})
    units.set_populated("aoteru-finalize-E1-1.service", True)
    status = _result("status", {"execution_id": "E1"})
    assert status["state"] == "running" and status["terminal_pending"] is True
    units.set_populated("aoteru-finalize-E1-1.service", None)
    assert _result("status", {"execution_id": "E1"})["state"] == "succeeded"


@pytest.mark.parametrize("bad_id", ["x.service", "E1.scope", "a.b"])
def test_6c_f5_ids_can_never_form_a_unit_suffix(cfg, units, verified, bad_id):
    response = _call("start", _codex_payload(cfg, bad_id))
    assert response["ok"] is False and response["error"]["code"] == "bad_request"
    assert units.spawned == []


def test_6c_f1_closure_view_exposes_the_latest_quiescent_finalize_result(cfg, repo, inline_attempts):
    inline_attempts.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                                populated=False)
    (repo["wt"] / "new.txt").write_text("x")
    _result("worktree.finalize", _finalize_request(repo))
    closed = _result("status", {"execution_id": "E1", "close": True})
    assert closed["closed"] is True and closed["quiescent"] is True
    assert closed["finalize_result"]["outcome"] == "finalized"
    assert closed["finalize_result"]["commit_sha"] == _git(repo["wt"], "rev-parse", "HEAD")


def test_6d_f1_live_or_unproven_verify_unit_blocks_verification_and_aggregate(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker, "_VERIFY_UNIT_WAIT_S", 0.3)
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"}, populated=False,
                      request={"execution_id": "E1", "kind": "codex-write",
                               "lease": {"worktree_path": str(cfg["repo"])}})
    units.verify_live = True
    response = _call("worktree.verify", {"repo_id": "test-repo", "worktree_path": str(cfg["repo"]),
                                         "branch": "feature"})
    assert response["ok"] is False and response["error"]["code"] == "executor_unavailable"
    status = _result("status", {"execution_id": "E1"})
    assert status["quiescent"] is False and status["state"] == "running"
    units.verify_live = False
    assert _result("status", {"execution_id": "E1"})["state"] == "succeeded"


def test_6d_f1_run_in_unit_timeout_stops_the_unit_and_reports_its_proof(monkeypatch, tmp_path):
    procs = estate_worker.estate_worker_procs
    killed = []

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)
    monkeypatch.setattr(procs.subprocess, "run", _timeout)
    monkeypatch.setattr(procs, "kill_unit", lambda unit: killed.append(unit) or {"ok": True})
    monkeypatch.setattr(procs, "tree_quiescent", lambda handle: True)
    with pytest.raises(procs.ProcessLayerError, match="timed out and was stopped"):
        procs.run_in_unit(["true"], str(tmp_path), "aoteru-verify-x", timeout=1)
    assert killed == ["aoteru-verify-x.service"]
    monkeypatch.setattr(procs, "tree_quiescent", lambda handle: False)
    monkeypatch.setattr(procs.time, "monotonic", iter(range(0, 10_000, 20)).__next__)
    with pytest.raises(procs.ProcessLayerError, match="NOT proven stopped"):
        procs.run_in_unit(["true"], str(tmp_path), "aoteru-verify-y", timeout=1)


# ---------------------------------------------------------------------
# §G coverage completion (6e adjudication finding 3), worker side
# ---------------------------------------------------------------------

def test_u57_same_lease_prepare_after_completion_returns_the_record(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker, "_DEFAULT_PREPARE_WAIT_S", 0.1)
    _result("worktree.prepare", _prepare_payload())
    record = estate_worker._PREPARE_ROOT / "LP"
    estate_worker.decide_once(record / "run.json", {"decision": "execute", **units.handle("aoteru-prepare-LP.service")})
    estate_worker._json_write(record / "result.json", {"state": "prepared", "path": "/w", "branch": "feat/x",
                                                       "head_sha": "abc", "clean": True})
    units.set_populated("aoteru-prepare-LP.service", None)
    again = _result("worktree.prepare", _prepare_payload())
    assert again["reused"] is True and again["state"] == "prepared" and len(units.spawned) == 1


@pytest.mark.parametrize("state", ["succeeded", "failed", "timed_out"])
def test_u60_every_unacknowledged_terminal_write_state_is_retained(cfg, units, state):
    spool = units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": state},
                              result={"ok": state == "succeeded"}, populated=False,
                              request={"execution_id": "E1", "kind": "codex-write"})
    old = time.time() - 60 * 24 * 3600
    os.utime(spool / "state.json", (old, old))
    estate_worker._gc_spools()
    assert (spool / "result.json").exists()


def test_u60_unacknowledged_start_failed_write_spool_is_retained(cfg, units):
    spool = units.write_spool("E1", request={"execution_id": "E1", "kind": "codex-write"})
    estate_worker.decide_once(spool / "run.json", {"decision": "abort", "by": "starter"})
    (spool / "result.json").write_text("{}")
    estate_worker._gc_spools()
    assert (spool / "result.json").exists()


def test_u62_release_refused_for_a_starting_writer(cfg, units):
    units.write_spool("E1")                                   # start claim, no run decision yet
    response = _call("spool.release", {"execution_id": "E1", "resolution": "not_started"})
    assert response["ok"] is False and response["error"]["code"] == "authority_denied"
    assert not (_spool("E1") / "run.json").exists()           # refused BEFORE any closure/fence
    assert not (_spool("E1") / "closed.json").exists()


def test_u69_delayed_original_start_released_after_the_fence_never_spawns(cfg, units, verified, monkeypatch):
    real = estate_worker.decide_once
    paused, go = threading.Event(), threading.Event()

    def _slow(target, content):
        if content.get("kind") == "start":
            paused.set()
            go.wait(5)
        return real(target, content)

    monkeypatch.setattr(estate_worker, "decide_once", _slow)
    outcome = {}
    original = threading.Thread(target=lambda: outcome.update(r=_call("start", _codex_payload(cfg))))
    original.start()
    assert paused.wait(5)
    monkeypatch.setattr(estate_worker, "decide_once", real)
    assert _result("status", {"execution_id": "E1", "fence": True})["state"] == "fenced"
    monkeypatch.setattr(estate_worker, "decide_once", _slow)
    go.set()
    original.join(5)
    assert outcome["r"]["result"]["state"] == "fenced" and units.spawned == []


def test_u70a_ancestor_fsync_order_is_leaf_to_anchor(cfg, monkeypatch):
    target = _spool("order") / "claim.json"
    estate_worker.decide_once(target, {"n": 1})
    order = []
    real = estate_worker._fsync_dir
    monkeypatch.setattr(estate_worker, "_fsync_dir", lambda path: (order.append(Path(path)), real(path)))
    estate_worker.read_decision(target)
    anchor = estate_worker._SPOOL_ROOT.parent
    assert order == [target.parent, target.parent.parent, anchor]


def test_u70a_paused_loser_still_fsyncs_before_returning(cfg, monkeypatch):
    target = _spool("loser") / "claim.json"
    estate_worker.decide_once(target, {"n": 1})
    calls = []
    real_chain = estate_worker._fsync_chain
    monkeypatch.setattr(estate_worker, "_fsync_chain", lambda d: (calls.append(Path(d)), real_chain(d)))
    won, decided = estate_worker.decide_once(target, {"n": 2})
    assert won is False and decided == {"n": 1} and calls[-1] == target.parent


def test_u70_decision_fs_unsupported_also_refuses_release_and_hides_codex_write(cfg, units, monkeypatch):
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"}, populated=False)
    monkeypatch.setattr(estate_worker, "_decision_fs_supported", lambda root: (False, "unsupported"))
    response = _call("spool.release", {"execution_id": "E1", "resolution": "finalized"})
    assert response["ok"] is False and response["error"]["code"] == "executor_unavailable"
    monkeypatch.setattr(estate_worker, "_ollama_inventory", lambda: (True, [], None))
    monkeypatch.setattr(estate_worker.estate_router, "_codex_available", lambda: (True, "x"))
    monkeypatch.setattr(estate_worker, "_probe_repo", lambda repo: {"resolved": False, "path": None,
                                                                   "head_sha": None, "branch": None, "clean": False})
    import scripts.home_reentry_inventory as home_inventory
    monkeypatch.setattr(home_inventory, "_hardware", lambda: {})
    assert _result("inventory", {"models_of_interest": []})["executors"]["codex-write"] is False


def test_u68_failing_systemd_run_refuses_prepare_but_not_read_only_execute(cfg, monkeypatch):
    procs = estate_worker.estate_worker_procs
    monkeypatch.setattr(procs, "_RUNNER_UNITS_PROBE", {})
    monkeypatch.setattr(procs.os, "name", "posix")
    monkeypatch.setattr(procs.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a[0], 1, stdout="", stderr="Failed to connect to bus"))
    monkeypatch.setattr(estate_worker.estate_worker_procs, "runner_units_supported", _REAL_RUNNER_UNITS_SUPPORTED)
    ok, detail = procs.runner_units_supported()
    assert ok is False and "probe failed" in detail
    response = _call("worktree.prepare", _prepare_payload())
    assert response["ok"] is False and response["error"]["code"] == "executor_unavailable"
    monkeypatch.setattr(estate_worker.estate_router, "execute_local",
                        lambda model, objective, timeout: {"ok": True, "output": "fine", "latency_ms": 1})
    execute = _result("execute", {"kind": "local-inference", "model": "m", "objective": "x", "timeout_s": 1})
    assert execute["ok"] is True


def test_u71_concurrent_finalizes_of_one_execution_make_one_commit(cfg, repo):
    spool = _spool("E1")
    (repo["wt"] / "new.txt").write_text("x")
    results, barrier = [], threading.Barrier(2)

    def _go():
        barrier.wait()
        results.append(estate_worker._finalize_logic("E1", spool, _finalize_request(repo)))

    threads = [threading.Thread(target=_go) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    log = _git(repo["wt"], "log", "--format=%s", f"{repo['head']}..HEAD").splitlines()
    assert len(log) == 1
    finalized = [r for r in results if r["outcome"] == "finalized"]
    assert finalized and all(r["commit_sha"] == _git(repo["wt"], "rev-parse", "HEAD") for r in finalized)


def test_u74_finalize_and_push_attempts_launch_dedicated_units_with_runner_flags(cfg, repo, inline_attempts, monkeypatch):
    monkeypatch.setattr(estate_worker, "_DEFAULT_GIT_UNIT_WAIT_S", 0.3)
    inline_attempts.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                                populated=False)
    (repo["wt"] / "new.txt").write_text("x")
    done = _result("worktree.finalize", _finalize_request(repo))
    _result("worktree.push", {"execution_id": "E1", "repo_id": "test-repo", "branch": "feat/x",
                              "commit_sha": done["commit_sha"]})
    launched = {u["unit"]: u["argv"] for u in inline_attempts.spawned}
    finalize_argv = launched["aoteru-finalize-E1-1"]
    push_argv = launched["aoteru-push-E1-1"]
    assert finalize_argv[-3:] == ["--run-finalize", "E1", "1"] and "--root" in finalize_argv
    assert push_argv[-3:] == ["--run-push", "E1", "1"]


def test_u75_randomised_closure_vs_finalize_never_commits_unseen(cfg, repo, inline_attempts, monkeypatch):
    """Across randomised interleavings of a finalize attempt and a closer:
    whenever the closure reported quiescent, either no commit happened or
    the closure view carries that commit's finalize result."""
    import random
    monkeypatch.setattr(estate_worker, "_DEFAULT_GIT_UNIT_WAIT_S", 0.5)
    for index in range(8):
        execution_id = f"R{index}"
        _git(repo["wt"], "reset", "-q", "--hard", repo["head"])
        inline_attempts.write_spool(execution_id, run_unit=f"aoteru-run-{execution_id}.service",
                                    state={"state": "succeeded"}, populated=False)
        (repo["wt"] / f"f{index}.txt").write_text("x")
        seen = {}
        request = {**_finalize_request(repo, execution_id)}

        def _finalize():
            time.sleep(random.random() * 0.05)
            seen["finalize"] = _call("worktree.finalize", request)

        def _close():
            time.sleep(random.random() * 0.05)
            seen["close"] = _result("status", {"execution_id": execution_id, "close": True})

        threads = [threading.Thread(target=_finalize), threading.Thread(target=_close)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        final = _result("status", {"execution_id": execution_id, "close": True})
        head = _git(repo["wt"], "rev-parse", "HEAD")
        if head != repo["head"]:
            assert (final["finalize_result"] or {}).get("commit_sha") == head, index
        _git(repo["wt"], "clean", "-q", "-fd")



def test_u46_first_start_paused_after_claim_before_spawn(cfg, units, verified, monkeypatch):
    real_spawn = units._spawn
    paused, go = threading.Event(), threading.Event()

    def _paused_spawn(*args, **kwargs):
        paused.set()
        go.wait(5)
        return real_spawn(*args, **kwargs)
    monkeypatch.setattr(estate_worker.estate_worker_procs, "spawn_runner_unit", _paused_spawn)
    outcome = {}
    first = threading.Thread(target=lambda: outcome.update(a=_result("start", _codex_payload(cfg))))
    first.start()
    assert paused.wait(5)
    second = _result("start", _codex_payload(cfg))
    assert second == {**second, "accepted": False, "state": "starting", "reused": True}
    assert "execution_failed" not in json.dumps(second)
    go.set()
    first.join(5)
    assert len(units.spawned) == 1
    estate_worker.decide_once(_spool("E1") / "run.json",
                              {"decision": "execute", **units.handle("aoteru-run-E1.service")})
    assert _result("status", {"execution_id": "E1"})["state"] == "running"


def test_u70a_loser_returns_after_its_own_fsync_while_winner_is_paused(cfg, monkeypatch):
    target = _spool("pw") / "claim.json"
    real_chain = estate_worker._fsync_chain
    paused, resume = threading.Event(), threading.Event()
    order = []

    def _chain(directory):
        if threading.current_thread().name == "winner":
            paused.set()
            resume.wait(5)
        order.append(threading.current_thread().name)
        real_chain(directory)

    monkeypatch.setattr(estate_worker, "_fsync_chain", _chain)
    winner = threading.Thread(target=estate_worker.decide_once, args=(target, {"n": 1}), name="winner")
    winner.start()
    assert paused.wait(5)                       # winner linked, paused BEFORE its fsync
    seen = {}
    loser = threading.Thread(target=lambda: seen.update(r=estate_worker.decide_once(target, {"n": 2})),
                             name="loser")
    loser.start()
    loser.join(5)
    assert seen["r"] == (False, {"n": 1}) and order == ["loser"]   # loser fsynced itself, first
    resume.set()
    winner.join(5)


def test_u67_populated_grandchild_state_keeps_prepare_preparing_and_writer_alive(cfg, units, monkeypatch):
    """U67: 'runner dead + grandchild alive -> tree_quiescent False -> prepare
    stays preparing (not prepare_interrupted), status.process_alive true,
    recovery refused' (the populated-cgroup fact itself is proven on a real
    unit by test_u67_real_unit_setsid_grandchild_keeps_the_cgroup_populated;
    recovery refusal on quiescent false: test_u42c/test_u74 control tests)."""
    monkeypatch.setattr(estate_worker, "_DEFAULT_PREPARE_WAIT_S", 0.1)
    _result("worktree.prepare", _prepare_payload())
    record = estate_worker._PREPARE_ROOT / "LP"
    estate_worker.decide_once(record / "run.json", {"decision": "execute",
                                                     **units.handle("aoteru-prepare-LP.service", pid=999999)})
    units.set_populated("aoteru-prepare-LP.service", True)          # runner pid dead, grandchild alive
    assert _result("worktree.prepare_status", {"lease_id": "LP"})["state"] == "preparing"
    units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "running"})
    status = _result("status", {"execution_id": "E1"})
    assert status["process_alive"] is True and status["quiescent"] is False
    closing = _result("status", {"execution_id": "E1", "close": True})
    assert closing["quiescent"] is False                          # what recovery precondition 4 reads


def test_u76_populated_push_unit_never_blocks_spool_release(cfg, units):
    """U76: 'A populated push unit never blocks recovery or spool.release'."""
    spool = units.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"}, populated=False)
    estate_worker.decide_once(spool / "push" / "attempt-1.json", {"request": {}})
    estate_worker.decide_once(spool / "push" / "attempt-1.run.json",
                              {"decision": "execute", **units.handle("aoteru-push-E1-1.service")})
    units.set_populated("aoteru-push-E1-1.service", True)
    closing = _result("status", {"execution_id": "E1", "close": True})
    assert closing["quiescent"] is True                           # recovery precondition 4 satisfied
    assert _result("spool.release", {"execution_id": "E1", "resolution": "recovered"})["released"] is True



def test_gate4_late_finalize_after_closure_runs_no_git_at_all(cfg, repo, inline_attempts, monkeypatch):
    """U75: '... and runs no git command' -- not even worktree verification."""
    inline_attempts.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                                populated=False)
    _result("status", {"execution_id": "E1", "close": True})
    touched = []
    monkeypatch.setattr(estate_worker, "_worktree_verification", lambda *a: touched.append(a) or pytest.fail("git"))
    monkeypatch.setattr(estate_worker, "_run_git", lambda *a, **k: touched.append(a) or pytest.fail("git"))
    assert _result("worktree.finalize", _finalize_request(repo))["outcome"] == "execution_closed"
    assert touched == []



def test_gate5_attempt_fenced_between_closure_read_and_launch_never_touches_git(cfg, repo, inline_attempts,
                                                                               monkeypatch):
    """U75: 'Randomised thread interleavings on a real temp dir never
    produce both a git call and a successful recovery' -- the gate-round-5
    interleaving: the attempt records itself and reads no closure, then a
    closer closes and fences it before its runner decides; afterwards no
    worktree git runs and the closure proves quiescence."""
    inline_attempts.write_spool("E1", run_unit="aoteru-run-E1.service", state={"state": "succeeded"},
                                populated=False)
    (repo["wt"] / "new.txt").write_text("x")
    real_launch = estate_worker._launch_runner
    closure = {}

    def _closer_wins_first(flag, args, **kwargs):
        closure["view"] = _result("status", {"execution_id": "E1", "close": True})   # closes + fences attempt 1
        return real_launch(flag, args, **kwargs)
    monkeypatch.setattr(estate_worker, "_launch_runner", _closer_wins_first)
    touched = []
    real_verify, real_git = estate_worker._worktree_verification_local, estate_worker._run_git
    monkeypatch.setattr(estate_worker, "_worktree_verification_local",
                        lambda *a: touched.append(("verify", a)) or real_verify(*a))
    monkeypatch.setattr(estate_worker, "_run_git",
                        lambda path, args, **k: touched.append(("git", args)) or real_git(path, args, **k))
    answer = _result("worktree.finalize", _finalize_request(repo))
    assert closure["view"]["quiescent"] is True                   # recovery could proceed ...
    assert answer["outcome"] != "finalized" and touched == []     # ... and no git ever ran
    assert _git(repo["wt"], "rev-parse", "HEAD") == repo["head"]
    run = estate_worker.read_decision(_spool("E1") / "finalize" / "attempt-1.run.json")
    assert run["decision"] == "abort" and run["by"] == "fence"



def test_gate6_verification_git_is_read_only_and_never_rewrites_the_index(cfg, repo, monkeypatch):
    """Gate round 6 finding 1: a (possibly late) verification may observe a
    worktree but can never mutate it -- `git status` under the worker's
    environment takes no optional locks and leaves the index untouched even
    when its stat data is stale."""
    from src.park_lease_ops import git_is_clean
    tracked = repo["wt"] / "README"
    index = Path(_git(repo["wt"], "rev-parse", "--git-dir")) / "index"
    old = time.time() - 3600
    os.utime(tracked, (old, old))                  # stale stat info -> an ordinary status would refresh
    before = (index.read_bytes(), index.stat().st_mtime_ns)
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    estate_worker._disable_git_side_processes(estate_worker._SPOOL_ROOT)
    assert os.environ["GIT_OPTIONAL_LOCKS"] == "0"
    clean, _reason = git_is_clean(str(repo["wt"]))
    assert clean is True
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before



def test_gate7_start_refuses_a_dirty_tree_and_the_runner_rechecks_before_codex(cfg, units, verified, monkeypatch):
    """Gate round 7 finding 2: changes arriving after admission are never
    mixed in -- start refuses a dirty tree pre-claim, and a runner that finds
    the tree changed after winning `execute` never runs the writer."""
    monkeypatch.setattr(estate_worker, "_worktree_verification", lambda *a: {
        "ok": True, "path": str(cfg["repo"]), "reason": None, "head_sha": "abc", "clean": False})
    refused = _call("start", _codex_payload(cfg))
    assert refused["ok"] is False and refused["error"]["code"] == "authority_denied"
    assert not (_spool("E1") / "claim.json").exists()
    # Clean at start, dirty by the time the runner has decided `execute`.
    state = {"clean": True}
    monkeypatch.setattr(estate_worker, "_worktree_verification", lambda *a: {
        "ok": True, "path": str(cfg["repo"]), "reason": None, "head_sha": "abc", "clean": state["clean"]})
    _result("start", _codex_payload(cfg))
    state["clean"] = False
    ran = []
    monkeypatch.setattr(estate_worker.estate_router, "_execute_codex_with_sandbox",
                        lambda *a, **k: ran.append(1) or {"ok": True})
    units.enter("aoteru-run-E1.service")
    estate_worker._run_spooled("E1")
    assert ran == []
    assert estate_worker._json_read(_spool("E1") / "state.json")["state"] == "failed"
    assert "not run" in estate_worker._json_read(_spool("E1") / "result.json")["error"]


def test_gate7_verify_units_are_scoped_per_worktree(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker, "_VERIFY_UNIT_WAIT_S", 0.3)
    scopes = []
    monkeypatch.setattr(estate_worker.estate_worker_procs, "verify_units_quiescent",
                        lambda scope=None: scopes.append(scope) or scope != estate_worker._verify_scope("/busy"))
    monkeypatch.setattr(estate_worker, "_worktree_verification_local", lambda *a: {
        "ok": True, "path": a[1], "reason": None, "head_sha": "h", "clean": True})
    busy = _call("worktree.verify", {"repo_id": "test-repo", "worktree_path": "/busy", "branch": "b"})
    other = _call("worktree.verify", {"repo_id": "test-repo", "worktree_path": "/other", "branch": "b"})
    assert busy["ok"] is False and other["ok"] is True
    assert units.verify_units[-1].startswith(f"aoteru-verify-{estate_worker._verify_scope('/other')}-")


def test_gate8_post_claim_failures_never_surface_as_worker_errors(cfg, units, verified, monkeypatch):
    real_write = estate_worker._json_write

    def _broken(path, value):
        if Path(path).name == "spawn.json":
            raise OSError("disk full")
        return real_write(path, value)
    monkeypatch.setattr(estate_worker, "_json_write", _broken)
    response = _call("start", _codex_payload(cfg))
    assert response["ok"] is True                         # answered from the decision files
    assert (_spool("E1") / "claim.json").exists() and len(units.spawned) == 1


def test_gate8_same_path_verification_waits_for_a_transient_unit(cfg, units, monkeypatch):
    monkeypatch.setattr(estate_worker, "_worktree_verification_local", lambda *a: {
        "ok": True, "path": a[1], "reason": None, "head_sha": "h", "clean": True})
    units.verify_live = True
    threading.Timer(0.6, lambda: setattr(units, "verify_live", False)).start()
    response = _call("worktree.verify", {"repo_id": "test-repo", "worktree_path": "/reused", "branch": "b"})
    assert response["ok"] is True                         # waited, then verified; not refused


def test_gate9_verify_bounds_are_consistent_by_construction():
    """Gate round 9: a same-path verification waits longer than a late verify
    unit's whole bounded lifetime (run limit + stop-and-proof), and every
    control-plane verify call's deadline covers that wait plus the run."""
    from src import estate_write_lane
    lifetime = estate_worker.VERIFY_UNIT_TIMEOUT_S + estate_worker.VERIFY_KILL_PROOF_S
    assert estate_worker._VERIFY_UNIT_WAIT_S > lifetime
    assert estate_worker.VERIFY_CALL_DEADLINE_S >= estate_worker._VERIFY_UNIT_WAIT_S + estate_worker.VERIFY_UNIT_TIMEOUT_S
    assert estate_write_lane._VERIFY_DEADLINE_S == estate_worker.VERIFY_CALL_DEADLINE_S
    import inspect
    source = inspect.getsource(estate_write_lane)
    assert source.count('"worktree.verify"') == source.count("deadline_s=_VERIFY_DEADLINE_S")
    worker_source = inspect.getsource(estate_worker._worktree_verification)
    assert "timeout=VERIFY_UNIT_TIMEOUT_S" in worker_source


def test_gate9_late_unit_within_its_lifetime_never_refuses_a_same_path_verification(cfg, units, monkeypatch):
    """Scaled schedule: the late unit lives for most of the wait bound (as a
    10 s run + 15 s stop would under the 35 s bound); the new verification
    waits it out and succeeds."""
    monkeypatch.setattr(estate_worker, "_VERIFY_UNIT_WAIT_S", 3.5)
    monkeypatch.setattr(estate_worker, "_worktree_verification_local", lambda *a: {
        "ok": True, "path": a[1], "reason": None, "head_sha": "h", "clean": True})
    units.verify_live = True
    threading.Timer(2.5, lambda: setattr(units, "verify_live", False)).start()
    assert _call("worktree.verify", {"repo_id": "test-repo", "worktree_path": "/reused", "branch": "b"})["ok"] is True
