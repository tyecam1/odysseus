"""Fake systemd runner units for Stage 6 worker tests.

Only the *launch* (`systemd-run`), the runner's own-cgroup lookup and the
unit kill are faked. Quiescence goes through the REAL
`estate_worker_procs.tree_quiescent`, pointed at a temp cgroupfs tree whose
`cgroup.events` files this helper writes, so the populated/absent rules are
exercised exactly as on a host.
"""
from __future__ import annotations

from pathlib import Path

_APP_SLICE = "/user.slice/user-1003.slice/user@1003.service/app.slice"


class FakeUnits:
    def __init__(self, tmp_path, monkeypatch, estate_worker, *, prepare_result=None, supported=True):
        self.worker = estate_worker
        self.procs = estate_worker.estate_worker_procs
        self.root = Path(tmp_path) / "cgroupfs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.spawned: list[dict] = []
        self.killed: list[str] = []
        self.current_cgroup = None
        self.prepare_result = prepare_result
        monkeypatch.setattr(self.procs, "_CGROUP_ROOT", self.root)
        monkeypatch.setattr(self.procs, "runner_units_supported",
                            lambda: (supported, "fake units" if supported else "fake: unsupported"))
        monkeypatch.setattr(self.procs, "spawn_runner_unit", self._spawn)
        monkeypatch.setattr(self.procs, "own_cgroup", lambda: self.current_cgroup)
        monkeypatch.setattr(self.procs, "kill_unit", self._kill)
        monkeypatch.setattr(self.procs, "run_in_unit", self._run_in_unit)
        self.verify_live = False
        monkeypatch.setattr(self.procs, "verify_units_quiescent", lambda scope=None: not self.verify_live)
        self.verify_units: list[str] = []

    def _run_in_unit(self, argv, cwd, unit, *, timeout=60.0, input_text=None):
        """Synchronous tracked unit: run the verification body in-process
        (inheriting the test's monkeypatches) and report it as collected."""
        import json
        import subprocess
        assert "--run-verify" in argv and unit.startswith("aoteru-verify-")
        self.verify_units.append(unit)
        request = json.loads(input_text)
        try:
            answer = self.worker._worktree_verification_local(
                request["repo_id"], request["worktree_path"], request["branch"])
        except self.worker.WorkerError as exc:
            answer = {"error": {"code": exc.code, "message": str(exc)}}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(answer) + "\n", stderr="")

    @staticmethod
    def cgroup(unit: str) -> str:
        return f"{_APP_SLICE}/{unit}"

    def set_populated(self, unit: str, populated: bool | None) -> None:
        """True/False write cgroup.events; None removes the cgroup (collected)."""
        path = self.root / self.cgroup(unit).lstrip("/")
        if populated is None:
            events = path / "cgroup.events"
            if events.exists():
                events.unlink()
            return
        path.mkdir(parents=True, exist_ok=True)
        (path / "cgroup.events").write_text(f"populated {1 if populated else 0}\nfrozen 0\n")

    def handle(self, unit: str, pid: int = 4242) -> dict:
        return {"pid": pid, "create_time": 1, "cgroup": self.cgroup(unit), "unit": unit}

    def enter(self, unit: str) -> None:
        """Make the next runner invocation believe it lives in `unit`."""
        self.current_cgroup = self.cgroup(unit)
        self.set_populated(unit, True)

    def _spawn(self, argv, cwd, log_path, unit):
        service = f"{unit}.service"
        self.spawned.append({"argv": argv, "cwd": cwd, "log": log_path, "unit": unit})
        self.set_populated(service, True)
        if unit.startswith("aoteru-prepare-") and self.prepare_result is not None:
            lease_id = unit[len("aoteru-prepare-"):]
            record = self.worker._PREPARE_ROOT / lease_id
            self.worker.decide_once(record / "run.json",
                                    {"decision": "execute", **self.handle(service), "at": "t"})
            self.worker._json_write(record / "result.json", dict(self.prepare_result))
            self.set_populated(service, None)
        return {"unit": service}

    def _kill(self, unit):
        self.killed.append(unit)
        if unit:
            self.set_populated(unit, None)
        return {"ok": True, "detail": ""}

    def write_spool(self, execution_id, *, run_unit=None, state=None, result=None, populated=True,
                    request=None):
        """A spool whose start claim and (optionally) runner execute decision
        already exist -- the state a real start + runner leave behind."""
        spool = self.worker._SPOOL_ROOT / execution_id
        self.worker.decide_once(spool / "claim.json", {
            "kind": "start", "claimed_at": self.worker._utcnow(),
            "request": request or {"execution_id": execution_id, "kind": "codex-write"},
        })
        if run_unit is not None:
            self.worker.decide_once(spool / "run.json", {"decision": "execute", **self.handle(run_unit), "at": "t"})
            self.set_populated(run_unit, True if populated else None)
        if state is not None:
            self.worker._json_write(spool / "state.json", state)
        if result is not None:
            self.worker._json_write(spool / "result.json", result)
        return spool
