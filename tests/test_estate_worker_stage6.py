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
