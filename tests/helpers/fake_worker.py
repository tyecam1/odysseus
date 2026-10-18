"""FakeWorker for Stage 6 control-plane tests (plan §G: "installed by
monkeypatching estate_worker_client" -- here at `call_worker`, the one
seam the control plane uses). It models the worker's *contract*
(decision-based start/fence/close, quiescence, finalize results) per host
and records every call with its host, so tests can assert exactly what was
sent where. Transport failures are raised as real WorkerTransportError."""
from __future__ import annotations

import copy
import itertools

_ids = itertools.count(1)


class FakeWorker:
    def __init__(self, monkeypatch, *, head="a" * 40, path="/w/feat", clean=True):
        from src import estate_worker_client as client
        self.client = client
        self.calls: list[tuple[str, str, dict]] = []
        self.executions: dict[str, dict] = {}
        self.head, self.path, self.clean = head, path, clean
        self.fail: dict[str, list] = {}           # verb -> queue of error codes to raise once each
        self.start_mode = "normal"                # normal | lost_after_spawn | refuse
        self.finalize_outcome = {"outcome": "finalized", "committed": True, "adopted": False,
                                 "commit_sha": "b" * 40, "parent_sha": head, "dirty_paths": ["x"],
                                 "push": {"state": "pushed", "commit_sha": "b" * 40}}
        self.prepare_answer = {"state": "prepared", "path": path, "branch": None, "head_sha": head,
                               "clean": True, "quiescent": True}
        self.prepare_status_answer = {"state": "fenced", "quiescent": True}
        self.push_answer = {"pushed": True, "push": {"state": "pushed", "contained": False}}
        self.on_call = None
        monkeypatch.setattr(client, "call_worker", self.call)

    # -- helpers -------------------------------------------------------
    def handle(self, execution_id):
        return {"pid": 4242, "create_time": 1, "cgroup": f"/app.slice/aoteru-run-{execution_id}.service",
                "unit": f"aoteru-run-{execution_id}.service"}

    def set_state(self, execution_id, state, *, quiescent=None, result=None):
        view = self.executions.setdefault(execution_id, {"claim": "start"})
        view["state"] = state
        view["quiescent"] = quiescent if quiescent is not None else state not in ("running", "starting")
        if result is not None:
            view["result"] = result

    def verbs(self, host=None):
        return [verb for h, verb, _p in self.calls if host is None or h == host]

    def _raise(self, code):
        raise self.client.WorkerTransportError(code, f"fake {code}")

    # -- the seam --------------------------------------------------------
    def call(self, host_id, verb, payload, *, deadline_s):
        self.calls.append((host_id, verb, copy.deepcopy(payload)))
        if self.on_call is not None:
            self.on_call(host_id, verb, payload)
        queue = self.fail.get(verb)
        if queue:
            self._raise(queue.pop(0))
        result = getattr(self, "_" + verb.replace(".", "_"))(payload)
        return {"ok": True, "result": result, "attestation": {"host_id": host_id}}

    def _worktree_verify(self, payload):
        return {"ok": True, "path": self.path, "reason": None, "head_sha": self.head, "clean": self.clean}

    def _view(self, execution_id):
        view = self.executions.get(execution_id)
        if view is None:
            return {"state": "unknown", "handle": None, "quiescent": True, "process_alive": False}
        if view["claim"] == "fence":
            return {"state": "fenced", "handle": None, "quiescent": True, "process_alive": False}
        out = {"state": view["state"], "quiescent": view["quiescent"],
               "process_alive": view["quiescent"] is not True, "closed": view.get("closed", False),
               "finalize_result": view.get("finalize_result"), "finalize_commit": view.get("finalize_commit"),
               "handle": self.handle(execution_id) if view["state"] not in ("starting", "start_failed") else None}
        if "result" in view:
            out["result"] = view["result"]
        return out

    def _start(self, payload):
        execution_id = payload["execution_id"]
        if execution_id in self.executions:
            return {"accepted": True, **self._view(execution_id), "reused": True}
        if self.start_mode == "refuse":
            self._raise("authority_denied")
        self.executions[execution_id] = {"claim": "start", "state": "running", "quiescent": False,
                                         "spawns": 1}
        if self.start_mode == "lost_after_spawn":
            self.start_mode = "normal"
            self._raise("worker_unreachable")
        return {"accepted": True, "state": "starting", "handle": None, "reused": False, "spawned": True}

    def _status(self, payload):
        execution_id = payload["execution_id"]
        view = self.executions.get(execution_id)
        if payload.get("fence") or payload.get("close"):
            if view is None:
                self.executions[execution_id] = view = {"claim": "fence"}
            elif view.get("state") == "starting":
                view["state"] = "start_failed"
                view["quiescent"] = True
        if payload.get("close") and view is not None:
            view["closed"] = True
        return self._view(execution_id)

    def _worktree_finalize(self, payload):
        view = self.executions[payload["execution_id"]]
        if view.get("closed"):
            return {"outcome": "execution_closed"}
        view["finalize_result"] = dict(self.finalize_outcome)
        return dict(self.finalize_outcome)

    def _spool_release(self, payload):
        view = self.executions.setdefault(payload["execution_id"], {"claim": "fence"})
        view["closed"] = True
        view["released"] = payload["resolution"]
        return {"released": True, "state": "x", "already_released": False}

    def _worktree_push(self, payload):
        return dict(self.push_answer)

    def _worktree_prepare(self, payload):
        answer = dict(self.prepare_answer)
        if answer.get("branch") is None:
            answer["branch"] = payload["branch"]
        return answer

    def _worktree_prepare_status(self, payload):
        return dict(self.prepare_status_answer)
