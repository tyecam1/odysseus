"""Stage 6 JOINED scenarios (gate round 3): the real control plane
(`estate_write_lane`, `estate_router.run_task`) talking to the REAL worker
logic (`estate_worker.handle`) in-process, with real decision files, real
git (worktree + bare origin) and runner attempts executed inline in their
units -- so each §G clause runs across both halves in one scenario.

Only three things are simulated: the transport hop (call_worker ->
estate_worker.handle, with the target host's identity), the unit launcher
(tests.helpers.fake_units), and transport failures injected on purpose."""
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import yaml

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()

import core.database as cdb
from core.database import EstateExecution, ParkLease, RoutingDecision, get_db_session
from src import estate_router, estate_worker, estate_worker_procs, park_lease_ops
from src import estate_write_lane as lane
from src.estate_worker_protocol import build_request, validate_response
from tests.helpers.fake_units import FakeUnits

LAB, HOME = "test-lab", "test-home"
_HOSTNAMES = {LAB: "THIS-HOST", HOME: "HOME-HOST"}


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


class Joined:
    def __init__(self, tmp_path, monkeypatch):
        from src import estate_worker_client as client
        self.client = client
        self.calls: list[tuple[str, str, dict]] = []
        self.drop_response: dict[str, int] = {}     # verb -> how many responses to drop (after handling)
        self.fail_before: dict[str, int] = {}       # verb -> how many requests to fail before handling
        self.before_hooks: list = []
        self.in_worker = False
        self.homes: dict[str, str] = {}             # host -> HOME for that host's worker (per-host inventory)
        self.monkeypatch = monkeypatch
        monkeypatch.setattr(client, "call_worker", self.call)

    def call(self, host_id, verb, payload, *, deadline_s):
        self.calls.append((host_id, verb, json.loads(json.dumps(payload))))
        for hook in self.before_hooks:
            hook(host_id, verb, payload)
        key = f"{verb}:close" if verb == "status" and payload.get("close") else verb
        if self.fail_before.get(key):
            self.fail_before[key] -= 1
            raise self.client.WorkerTransportError("worker_unreachable", f"test: {key} never reached the worker")
        request = build_request(verb, host_id, payload, deadline_s)
        previous = socket.gethostname
        previous_home = os.environ.get("HOME")
        self.monkeypatch.setattr(socket, "gethostname", lambda: _HOSTNAMES[host_id])
        if host_id in self.homes:
            os.environ["HOME"] = self.homes[host_id]
        self.in_worker = True
        try:
            response = estate_worker.handle(request)
        finally:
            self.in_worker = False
            self.monkeypatch.setattr(socket, "gethostname", previous)
            if previous_home is not None:
                os.environ["HOME"] = previous_home
        assert validate_response(response, request) == (True, None)
        if self.drop_response.get(key):
            self.drop_response[key] -= 1
            raise self.client.WorkerTransportError("worker_unreachable", f"test: {key} response dropped")
        if not response["ok"]:
            raise self.client.WorkerTransportError(response["error"]["code"], response["error"]["message"])
        return response

    def verbs(self):
        return [verb for _h, verb, _p in self.calls]


@pytest.fixture
def estate(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    main = tmp_path / "repo"
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(main)], check=True)
    for key, value in (("user.email", "j@example.com"), ("user.name", "j")):
        _git(main, "config", key, value)
    (main / "README").write_text("r\n")
    _git(main, "add", "README")
    _git(main, "commit", "-q", "-m", "init")
    _git(main, "remote", "add", "origin", str(origin))
    worktree = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat/x", str(worktree))
    head = _git(worktree, "rev-parse", "HEAD")
    executors = ["deterministic", "local", "codex", "codex-write"]
    (config / "estate.yaml").write_text(yaml.safe_dump({"hosts": [
        {"id": LAB, "hostname": "THIS-HOST", "role": "lab", "identity_verified": True,
         "worker": {"enabled": True, "transport": "local", "qualified_executors": executors}},
        {"id": HOME, "hostname": "HOME-HOST", "role": "home", "identity_verified": True, "tailscale": True,
         "worker": {"enabled": True, "transport": "ssh", "qualified_executors": executors}},
    ]}))
    (config / "repositories.yaml").write_text(yaml.safe_dump({"repos": [{"id": "odysseus", "path": str(main)}]}))
    (config / "models.yaml").write_text(yaml.safe_dump({
        "paid_providers": [{"name": "codex", "concrete_model_label": "codex-cli"}],
        "default_paid_provider": "codex",
        "capabilities": [{"alias": "local-fast", "binding": "m-fast",
                          "qualified_hosts": {LAB: {"evidence": "t"}, HOME: {"evidence": "t"}}}],
    }))
    monkeypatch.setattr(estate_router, "_CONFIG_DIR", config)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    monkeypatch.setattr(estate_worker, "_SPOOL_ROOT", tmp_path / "aoteru" / "spool")
    monkeypatch.setattr(estate_worker, "_PREPARE_ROOT", tmp_path / "aoteru" / "prepare")
    monkeypatch.setattr(estate_worker, "_DECISION_FS_PROBED", {})
    monkeypatch.setattr(estate_worker, "machine_fingerprint", lambda: "0123456789abcdef")
    monkeypatch.setattr(estate_worker, "_worker_version", lambda: "abc123")
    monkeypatch.setattr(estate_worker, "_DEFAULT_GIT_UNIT_WAIT_S", 0.5)
    monkeypatch.setattr(estate_worker.worktree_ops, "is_live_checkout_path",
                        lambda repo, path: Path(path).resolve() == main.resolve())
    monkeypatch.setattr(estate_worker.worktree_ops, "verify_worktree", lambda repo, path, branch: {
        "ok": Path(path).exists() and _git(path, "branch", "--show-current") == branch,
        "path": str(Path(path).resolve()), "branch": branch,
        "head": _git(path, "rev-parse", "HEAD") if Path(path).exists() else None, "reason": "verify"})
    for key in list(os.environ):
        if key.startswith("GIT_CONFIG_"):
            monkeypatch.delenv(key)
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    monkeypatch.setattr(lane, "_observe_worker_execution", lambda execution_id: None)
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    units = FakeUnits(tmp_path, monkeypatch, estate_worker)
    units.keep_populated = set()
    real_spawn = units._spawn

    def _spawn(argv, cwd, log_path, unit):
        answer = real_spawn(argv, cwd, log_path, unit)
        for flag, kind in (("--run-finalize", "finalize"), ("--run-push", "push")):
            if flag in argv:
                index = argv.index(flag)
                units.enter(f"{unit}.service")
                estate_worker._run_attempt(kind, argv[index + 1], argv[index + 2])
                if unit not in units.keep_populated:
                    units.set_populated(f"{unit}.service", None)
        return answer

    monkeypatch.setattr(estate_worker_procs, "spawn_runner_unit", _spawn)
    joined = Joined(tmp_path, monkeypatch)
    with get_db_session() as s:
        s.add(ParkLease(id="L1", repo_id="odysseus", host_id=HOME, worktree_path=str(worktree.resolve()),
                        branch="feat/x", status="active"))
    yield {"joined": joined, "units": units, "wt": worktree, "main": main, "origin": origin, "head": head,
           "tmp": tmp_path}
    engine.dispose()
    os.unlink(tmpfile.name)


def _run_writer(estate, execution_id, *, writes=True, monkeypatch=None):
    """Execute the admitted codex-write runner in its unit (real
    _run_spooled), with the sandboxed codex replaced by a file write."""
    worktree = estate["wt"]

    def _fake_codex(objective, **kwargs):
        if writes:
            (Path(kwargs["cwd"]) / "WRITTEN.txt").write_text("by the writer\n")
        return {"ok": True, "output": "done", "provider": "codex"}

    monkeypatch.setattr(estate_worker.estate_router, "_execute_codex_with_sandbox", _fake_codex)
    estate["units"].enter(f"aoteru-run-{execution_id}.service")
    assert estate_worker._run_spooled(execution_id) == 0
    estate["units"].set_populated(f"aoteru-run-{execution_id}.service", None)
    view, exc = lane._worker(HOME, "status", {"execution_id": execution_id}, deadline_s=20)
    assert exc is None
    lane._apply_view(execution_id, view)


def _row(execution_id):
    with get_db_session() as s:
        row = s.query(EstateExecution).filter(EstateExecution.id == execution_id).one()
        s.expunge(row)
        return row


def _admit(estate):
    result = lane.execute_write_via_worker("write it", repo_id="odysseus", host_id=HOME, wait_timeout=0)
    assert result["ok"] is True and result["dispatch"] == "new", result
    return result["execution_id"]


IDS = dict(lease_id="L1", host_id=HOME, repo_id="odysseus", branch="feat/x")


def test_joined_u71_second_finalize_adopts_because_commit_json_matches(estate, monkeypatch):
    """U71: 'second finalize_execution (payload carries execution_id) ->
    worker adopts HEAD because commit.json matches it -> finalized with
    push recorded.'"""
    execution_id = _admit(estate)
    _run_writer(estate, execution_id, monkeypatch=monkeypatch)
    assert _row(execution_id).lifecycle_state == "succeeded"
    joined = estate["joined"]
    joined.drop_response["worktree.finalize"] = 1        # worker commits; response lost
    joined.fail_before["status:close"] = 1               # the closure never reaches the worker
    first = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                    commit_message="apply")
    assert first["finalized"] is False
    commit_record = estate_worker._SPOOL_ROOT / execution_id / "finalize" / "commit.json"
    assert commit_record.exists()
    second = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="apply")
    finalize_payloads = [p for _h, v, p in joined.calls if v == "worktree.finalize"]
    assert len(finalize_payloads) == 2 and all(p["execution_id"] == execution_id for p in finalize_payloads)
    assert second["finalized"] is True and second["adopted"] is True
    assert second["commit_sha"] == json.loads(commit_record.read_text())["commit_sha"] == _git(estate["wt"], "rev-parse", "HEAD")
    assert second["push"]["state"] == "pushed"
    assert _git(estate["origin"], "rev-parse", "refs/heads/feat/x") == second["commit_sha"]
    assert _row(execution_id).worktree_resolution == "finalized"


def test_joined_u74_committed_record_missing_populated_attempt_blocks_recovery(estate, monkeypatch):
    """U74: 'a finalize attempt has committed (tree clean) but is still
    populated without commit.json -> recover_execution_lease refused
    writer_quiescence_unproven (aggregate false) and the lease stays active;
    after the attempt unit empties -> recovery allowed'."""
    execution_id = _admit(estate)
    _run_writer(estate, execution_id, monkeypatch=monkeypatch)
    real_decide = estate_worker.decide_once

    def _no_commit_record(target, content):
        if Path(target).name == "commit.json":
            raise OSError("test: crash between git commit and commit.json")
        return real_decide(target, content)
    monkeypatch.setattr(estate_worker, "decide_once", _no_commit_record)
    estate["units"].keep_populated.add(f"aoteru-finalize-{execution_id}-1")
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="apply")
    monkeypatch.setattr(estate_worker, "decide_once", real_decide)
    assert result["finalized"] is False
    assert _git(estate["wt"], "rev-parse", "HEAD") != estate["head"]               # committed
    assert _git(estate["wt"], "status", "--porcelain") == ""                        # tree clean
    assert not (estate_worker._SPOOL_ROOT / execution_id / "finalize" / "commit.json").exists()
    ids = {**IDS, "worktree_path": str(estate["wt"].resolve())}
    refused = lane.recover_execution_lease(execution_id, **ids)
    assert refused["code"] == "writer_quiescence_unproven"
    with get_db_session() as s:
        assert s.query(ParkLease).filter(ParkLease.id == "L1").one().status == "active"
    estate["units"].set_populated(f"aoteru-finalize-{execution_id}-1.service", None)
    recovered = lane.recover_execution_lease(execution_id, **ids)
    assert recovered["recovered"] is True
    assert recovered["recovery"]["head_sha"] == _git(estate["wt"], "rev-parse", "HEAD")
    assert recovered["recovery"]["finalize_ambiguous"] is True


def test_joined_u75_attempt_committing_while_closure_waits_records_post_commit_head(estate, monkeypatch):
    """U75: 'a finalize attempt committing while closure waits leads recovery
    to record the post-commit HEAD (with finalize_commit: true once
    commit.json exists), never the pre-commit HEAD'."""
    execution_id = _admit(estate)
    _run_writer(estate, execution_id, monkeypatch=monkeypatch)
    joined = estate["joined"]
    fired = {"done": False}

    def _finalize_lands_first(host_id, verb, payload):
        # The finalize attempt (authorised earlier) records and commits just
        # as recovery's closure arrives: it is recorded before the closer's
        # scan, so the closure must wait for it and see its commit.
        if verb == "status" and payload.get("close") and not fired["done"]:
            fired["done"] = True
            joined.before_hooks.clear()
            joined.call(HOME, "worktree.finalize", {
                "execution_id": execution_id, "repo_id": "odysseus", "worktree_path": str(estate["wt"]),
                "branch": "feat/x", "commit_message": "late", "expected_head_sha": estate["head"]}, deadline_s=60)
    joined.before_hooks.append(_finalize_lands_first)
    recovered = lane.recover_execution_lease(execution_id, **IDS, worktree_path=str(estate["wt"].resolve()))
    post = _git(estate["wt"], "rev-parse", "HEAD")
    assert post != estate["head"]
    assert recovered["recovered"] is True
    assert recovered["recovery"]["head_sha"] == post and recovered["recovery"]["finalize_commit"] is True


def test_joined_u76_populated_push_unit_blocks_neither_recovery_nor_release(estate, monkeypatch):
    """U76: 'A populated push unit never blocks recovery or spool.release'."""
    execution_id = _admit(estate)
    _run_writer(estate, execution_id, writes=False, monkeypatch=monkeypatch)
    spool = estate_worker._SPOOL_ROOT / execution_id
    estate_worker.decide_once(spool / "push" / "attempt-1.json", {"request": {}})
    estate_worker.decide_once(spool / "push" / "attempt-1.run.json",
                              {"decision": "execute", **estate["units"].handle(f"aoteru-push-{execution_id}-1.service")})
    estate["units"].set_populated(f"aoteru-push-{execution_id}-1.service", True)
    recovered = lane.recover_execution_lease(execution_id, **IDS, worktree_path=str(estate["wt"].resolve()))
    assert recovered["recovered"] is True
    assert (spool / "released.json").exists()                     # spool.release acknowledged too


def test_joined_u27_home_resolves_the_repo_cwd_from_its_own_inventory(estate, monkeypatch, tmp_path):
    """U27: 'codex-readonly on home fake gets repo_id and resolves cwd on
    home (fake asserts that path came from home inventory, not lab)'. Lab
    and home have DIFFERENT host-local inventories (their own HOME /
    ~/.aoteru/config.local.json AI_ROOT); the cwd must be home's."""
    joined = estate["joined"]
    roots = {}
    for host in (LAB, HOME):
        home_dir = tmp_path / f"home-{host}"
        (home_dir / ".aoteru").mkdir(parents=True)
        ai_root = tmp_path / f"ai-{host}"
        (ai_root / "odysseus-aoteru").mkdir(parents=True)
        (home_dir / ".aoteru" / "config.local.json").write_text(json.dumps({"AI_ROOT": str(ai_root)}))
        roots[host] = (home_dir, ai_root / "odysseus-aoteru")
    (estate_router._CONFIG_DIR / "repositories.yaml").write_text(yaml.safe_dump({"repos": [
        {"id": "odysseus", "path": "${AI_ROOT}/odysseus-aoteru"}]}))
    monkeypatch.setenv("HOME", str(roots[LAB][0]))                     # the control plane's own host
    joined.homes = {LAB: str(roots[LAB][0]), HOME: str(roots[HOME][0])}
    assert estate_router.resolve_repo_path("odysseus") == str(roots[LAB][1])   # lab inventory
    seen = {}
    monkeypatch.setattr(estate_router, "execute_codex",
                        lambda objective, timeout, cwd: seen.update(cwd=cwd) or {"ok": True, "output": "read"})
    result = estate_router._dispatch_read_only(HOME, "codex", {"objective": "inspect", "repo": "odysseus"}, timeout=30)
    assert result["ok"] is True and result["placement"]["executed_host"] == HOME
    assert seen["cwd"] == str(roots[HOME][1]) != str(roots[LAB][1])
    assert joined.calls[-1][2]["repo_id"] == "odysseus" and "cwd" not in joined.calls[-1][2]


_U25_SCENARIOS = {
    # id: (requested_host, capability, repo, per-host models, per-host repo resolves, failure injection)
    "U1": ("lab", "local-fast", None, {LAB: ["m-fast"], HOME: ["m-fast"]}, None, None),
    "U2": ("home", "local-fast", None, {LAB: ["m-fast"], HOME: ["m-fast"]}, None, None),
    "U3": (None, "local-fast", None, {LAB: ["m-fast"], HOME: ["m-fast"]}, None, None),
    "U4": (None, "home-only", None, {LAB: ["m-fast"], HOME: ["m-fast", "m-home"]}, None, None),
    "U5": ("home", "local-fast", None, {LAB: ["m-fast"], HOME: ["m-fast"]}, None, "home_health_unreachable"),
    "U6": ("home", "local-fast", None, {LAB: ["m-fast"], HOME: ["m-fast"]}, None, "home_health_after_expiry"),
    # U7 at Stage 6: "model only on lab" -- per-host qualified_hosts
    # enforcement is Stage 7; here the home inventory lacks the model.
    "U7": ("home", "code-lab", None, {LAB: ["m-code"], HOME: ["m-fast"]}, None, None),
    "U8": ("home", "local-fast", None, {LAB: ["m-fast"], HOME: []}, None, None),
    # U9 uses a repo with no standing lease (the fixture parks `odysseus` on home).
    "U9": (None, "local-fast", "scratch-repo", {LAB: ["m-fast"], HOME: ["m-fast"]}, {LAB: True, HOME: False}, None),
    "U10": ("home", "local-fast", None, {LAB: ["m-fast"], HOME: ["m-fast"]}, None, "execution_failed"),
    "U11": ("home", "local-fast", None, {LAB: ["m-fast"], HOME: ["m-fast"]}, None, "placement_mismatch"),
}
_U25_EXPECTED_HOST = {"U1": LAB, "U2": HOME, "U3": LAB, "U4": HOME, "U5": None, "U6": None, "U7": None,
                      "U8": None, "U9": LAB, "U10": HOME, "U11": HOME}


@pytest.mark.parametrize("scenario", sorted(_U25_SCENARIOS, key=lambda k: int(k[1:])))
def test_joined_u25_persisted_decisions_across_u1_to_u11(estate, monkeypatch, scenario):
    """U25: 'for U1–U11, RoutingDecision.host_id == route.host and
    executed_host_id ∈ {route.host, null}; never another host except under
    placement_mismatch' -- each U1–U11 routing scenario, real routing, real
    worker verbs per host, decisions read back from routing_decisions."""
    requested, capability, repo, models, repo_resolves, failure = _U25_SCENARIOS[scenario]
    joined = estate["joined"]
    (estate_router._CONFIG_DIR / "models.yaml").write_text(yaml.safe_dump({
        "paid_providers": [{"name": "codex", "concrete_model_label": "codex-cli"}],
        "default_paid_provider": "codex",
        "capabilities": [
            {"alias": "local-fast", "binding": "m-fast", "qualified_hosts": {LAB: {"evidence": "t"}, HOME: {"evidence": "t"}}},
            {"alias": "home-only", "binding": "m-home", "qualified_hosts": {LAB: {"evidence": "t"}, HOME: {"evidence": "t"}}},
            {"alias": "code-lab", "binding": "m-code", "qualified_hosts": {LAB: {"evidence": "t"}}},
        ],
    }))
    host_of = {name: host for host, name in _HOSTNAMES.items()}
    monkeypatch.setattr(estate_worker, "_ollama_inventory", lambda: (
        True, [{"name": m, "digest": "d"} for m in models[host_of[socket.gethostname()]]], None))
    monkeypatch.setattr(estate_worker.estate_router, "_codex_available", lambda: (True, "x"))
    monkeypatch.setattr(estate_worker.estate_router, "experiment_priority_active", lambda: (False, "idle"))
    monkeypatch.setattr(estate_worker, "_probe_repo", lambda repo_id: {
        "resolved": (repo_resolves or {}).get(host_of[socket.gethostname()], True),
        "path": "/p", "head_sha": "h", "branch": "b", "clean": True})
    import scripts.home_reentry_inventory as home_inventory
    import src.model_context as model_context
    monkeypatch.setattr(home_inventory, "_hardware", lambda: {})
    monkeypatch.setattr(model_context, "get_context_length_known", lambda base, model: (8192, True))
    from src import estate_worker_client
    estate_worker_client.clear_caches()
    if failure == "execution_failed":
        monkeypatch.setattr(estate_worker.estate_router, "execute_local",
                            lambda model, objective, timeout: (_ for _ in ()).throw(RuntimeError("boom")))
    else:
        monkeypatch.setattr(estate_worker.estate_router, "execute_local",
                            lambda model, objective, timeout: {"ok": True, "output": "hi", "latency_ms": 1})
    if failure == "home_health_after_expiry":
        estate_worker_client.worker_health(HOME)                     # cached healthy ...
        estate_worker_client.clear_caches()                          # ... TTL expires ...
    if failure in ("home_health_unreachable", "home_health_after_expiry", "placement_mismatch"):
        def _hook(h, verb, payload):
            if failure == "placement_mismatch" and verb == "execute":
                raise joined.client.WorkerTransportError("placement_mismatch", "x", observed_host_id="intruder")
            if failure != "placement_mismatch" and h == HOME and verb == "health":
                raise joined.client.WorkerTransportError("worker_unreachable", "home down")
        joined.before_hooks.append(_hook)
    task = {"objective": "hi", "requirements": {"capabilities": [capability]}}
    if requested:
        task["placement"] = {"requested_host": requested}
    if repo:
        task["repo"] = repo
    result = estate_router.run_task(task)
    expected = _U25_EXPECTED_HOST[scenario]
    executes = [(h, v) for h, v, _p in joined.calls if v == "execute"]
    if expected is None:
        assert executes == [], scenario                            # nothing executed anywhere
        assert result.get("executed") is not True
    else:
        assert result["route"]["host"] == expected, (scenario, result.get("reason"))
        assert executes and {h for h, _v in executes} == {expected}
    with get_db_session() as s:
        rows = s.query(RoutingDecision).all()
        for row in rows:
            assert row.executed_host_id in (row.host_id, None), scenario
            if expected is not None and row.id == result.get("decision_id"):
                assert row.host_id == expected
                if failure == "placement_mismatch":
                    assert row.executed_host_id is None and row.actual_route == "placement_mismatch:intruder"
                elif failure is None:
                    assert row.executed_host_id == expected


@pytest.mark.skipif(os.name == "nt" or not estate_worker_procs.runner_units_supported()[0],
                    reason="needs real systemd user units")
def test_joined_u67_real_setsid_grandchild_refuses_recovery_until_the_unit_is_gone(estate, monkeypatch):
    """U67: 'runner dead + grandchild alive -> tree_quiescent False ->
    prepare stays preparing (not prepare_interrupted), status.process_alive
    true, recovery refused.' A REAL transient unit whose runner exits while
    a setsid'd grandchild lives backs the execution's handle; the control
    plane's recovery goes through the real worker and the real cgroup."""
    import uuid
    monkeypatch.setattr(estate_worker_procs, "_CGROUP_ROOT", Path("/sys/fs/cgroup"))
    execution_id = _admit(estate)
    unit = f"aoteru-probe-{uuid.uuid4().hex}"
    marker = estate["tmp"] / "cg.txt"
    script = estate["tmp"] / "runner.sh"
    # The runner exits at once; its setsid'd grandchild lives on in the
    # unit's cgroup (KillMode=process leaves it): runner DEAD, grandchild ALIVE.
    script.write_text(f"#!/bin/sh\ncat /proc/self/cgroup > {marker}\nsetsid sleep 60 </dev/null >/dev/null 2>&1 &\nexit 0\n")
    script.chmod(0o755)
    # launch the REAL unit (bypass the fixture's fake launcher for this one call)
    import subprocess as _sp
    env = {**os.environ, "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")}
    _sp.run(["systemd-run", "--user", f"--unit={unit}", "--collect", "--quiet", "-p", "KillMode=process",
             "--", str(script)], check=True, env=env)
    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    cgroup = marker.read_text().strip().split("::", 1)[1]
    handle = {"pid": 1, "create_time": 1, "cgroup": cgroup, "unit": f"{unit}.service"}
    time.sleep(0.5)
    members = (Path("/sys/fs/cgroup") / cgroup.lstrip("/") / "cgroup.procs").read_text().split()
    comms = [Path(f"/proc/{pid}/comm").read_text().strip() for pid in members]
    assert comms == ["sleep"], comms                  # the runner (sh) is dead; only the grandchild lives
    try:
        # The admitted execution's runner decided `execute` in that unit.
        spool = estate_worker._SPOOL_ROOT / execution_id
        estate_worker.decide_once(spool / "run.json", {"decision": "execute", **handle})
        with get_db_session() as s:
            s.query(EstateExecution).filter(EstateExecution.id == execution_id).update({
                "lifecycle_state": "interrupted", "worker_handle_json": json.dumps(handle, sort_keys=True)})
        view, exc = lane._worker(HOME, "status", {"execution_id": execution_id}, deadline_s=20)
        assert exc is None and view["process_alive"] is True and view["quiescent"] is False
        ids = {**IDS, "worktree_path": str(estate["wt"].resolve())}
        refused = lane.recover_execution_lease(execution_id, **ids)
        assert refused["recovered"] is False and refused["code"] == "writer_quiescence_unproven"
        with get_db_session() as s:
            assert s.query(ParkLease).filter(ParkLease.id == "L1").one().status == "active"
        # A prepare whose runner lives in the same kind of populated unit stays `preparing`.
        record = estate_worker._PREPARE_ROOT / "LP"
        estate_worker.decide_once(record / "claim.json", {"kind": "prepare", "request": {}})
        estate_worker.decide_once(record / "run.json", {"decision": "execute", **handle})
        prep, exc = lane._worker(HOME, "worktree.prepare_status", {"lease_id": "LP"}, deadline_s=20)
        assert exc is None and prep["state"] == "preparing"
    finally:
        _sp.run(["systemctl", "--user", "kill", "--signal=KILL", f"{unit}.service"], capture_output=True, env=env)
    deadline = time.monotonic() + 10
    while estate_worker_procs.tree_quiescent(handle) is not True and time.monotonic() < deadline:
        time.sleep(0.1)
    recovered = lane.recover_execution_lease(execution_id, **IDS, worktree_path=str(estate["wt"].resolve()))
    assert recovered["recovered"] is True



def test_joined_u75_closure_waits_on_a_committing_attempt_and_records_post_commit_head(estate, monkeypatch):
    """U75: 'a finalize attempt committing while closure waits leads recovery
    to record the post-commit HEAD (with finalize_commit: true once
    commit.json exists), never the pre-commit HEAD'. The attempt runs in its
    own thread and is paused INSIDE its git commit while recovery closes."""
    execution_id = _admit(estate)
    _run_writer(estate, execution_id, monkeypatch=monkeypatch)
    units = estate["units"]
    at_commit, release_commit = threading.Event(), threading.Event()
    real_git = estate_worker._git

    def _git_pausing_at_commit(path, args, **kwargs):
        if args and args[0] == "commit":
            at_commit.set()
            release_commit.wait(10)
        return real_git(path, args, **kwargs)
    monkeypatch.setattr(estate_worker, "_git", _git_pausing_at_commit)
    attempt_threads = []

    def _spawn_async(argv, cwd, log_path, unit):
        units.spawned.append({"argv": argv, "unit": unit})
        units.set_populated(f"{unit}.service", True)
        index = argv.index("--run-finalize")
        units.current_cgroup = units.cgroup(f"{unit}.service")

        def _attempt():
            estate_worker._run_attempt("finalize", argv[index + 1], argv[index + 2])
            units.set_populated(f"{unit}.service", None)
        thread = threading.Thread(target=_attempt)
        attempt_threads.append(thread)
        thread.start()
        at_commit.wait(10)            # runner decided `execute` and reached its git commit
        return {"unit": f"{unit}.service"}
    monkeypatch.setattr(estate_worker_procs, "spawn_runner_unit", _spawn_async)
    first = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                    commit_message="apply")
    assert first["finalized"] is False                    # attempt still committing
    pre = estate["head"]
    ids = {**IDS, "worktree_path": str(estate["wt"].resolve())}
    waiting = lane.recover_execution_lease(execution_id, **ids)
    assert waiting["recovered"] is False and waiting["code"] == "writer_quiescence_unproven"
    assert _row(execution_id).worktree_resolution == "unresolved"      # pre-commit HEAD never recorded
    release_commit.set()
    for thread in attempt_threads:
        thread.join(20)
    post = _git(estate["wt"], "rev-parse", "HEAD")
    assert post != pre
    recovered = lane.recover_execution_lease(execution_id, **ids)
    assert recovered["recovered"] is True
    assert recovered["recovery"]["head_sha"] == post and recovered["recovery"]["finalize_commit"] is True
