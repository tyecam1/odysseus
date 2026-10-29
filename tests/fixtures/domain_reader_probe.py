"""Real-app subprocess acceptance probe; only caller-owned synthetic fixtures."""
import ast
import asyncio
import importlib
import inspect
import json
import os
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app
from fastapi.testclient import TestClient


def loop_factory():
    # This sandbox denies socketpair(), including asyncio's cross-thread wakeup.
    # A timer wakes the REAL TestClient loop; no application/transport mock.
    loop = asyncio.new_event_loop()

    def pulse():
        loop.call_later(.01, pulse)

    pulse()
    return loop


own = app.RUNTIME_PROFILE.repository_id
foreign = "obsidian-phd" if own == "misumi-homebase" else "misumi-homebase"
title = "OWN_MISUMI_CANARY" if own == "misumi-homebase" else "OWN_PHD_CANARY"
forbidden = "OWN_PHD_CANARY" if own == "misumi-homebase" else "OWN_MISUMI_CANARY"
source = app.RUNTIME_PROFILE.source_root
relative = "agent-tasks/inbox/own.md" if own == "misumi-homebase" else "10-inbox/own.md"
observed = []

with TestClient(app.app, backend_options={"loop_factory": loop_factory}) as client:
    assert client.get("/api/health").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/static/bbc/ship.js").status_code == 200
    assert client.get(f"/api/bbc/v1/repositories/{own}").status_code == 401
    if not app.auth_manager.is_configured:
        assert client.post("/api/auth/setup", json={"username": "fixture", "password": "SyntheticOnly123!"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "fixture", "password": "SyntheticOnly123!"}).status_code == 200

    systems = client.get("/api/bbc/v1/repositories").json()["systems"]
    assert {item["id"] for item in systems} == {"misumi-homebase", "obsidian-phd", "odysseus"}
    assert [item["id"] for item in systems if item["configured"]] == [own]
    response = client.get(f"/api/bbc/v1/repositories/{own}/work-nodes")
    assert response.status_code == 200, response.text
    assert title in response.text and forbidden not in response.text
    response = client.post("/api/bbc/v1/capabilities/bbc.repository.inspect/invoke", json={"inputs": {"repository_id": own, "relative_path": relative}})
    assert response.status_code == 200, response.text
    assert title in response.text and forbidden not in response.text

    denied = [
        ("GET", f"/api/bbc/v1/repositories/{foreign}", None),
        ("GET", f"/api/bbc/v1/repositories/{foreign}/work-nodes", None),
        ("GET", "/api/bbc/v1/repositories/odysseus/resolve?q=private", None),
        ("GET", "/api/bbc/v1/repositories/unknown", None),
        ("POST", "/api/bbc/v1/capabilities/bbc.repository.inspect/invoke", {"inputs": {"repository_id": foreign}}),
        ("POST", "/api/bbc/v1/capabilities/bbc.repository.inspect/invoke", {"inputs": {"repository_id": own, "relative_path": "../foreign.md"}}),
        ("POST", "/api/bbc/v1/capabilities/bbc.repository.inspect/invoke", {"inputs": {"repository_id": own, "relative_path": relative.replace("own.md", "escape.md")}}),
        ("POST", f"/api/bbc/v1/repositories/{own}/refresh", {}),
        ("POST", "/api/bbc/v1/navigation-transactions", {}),
        ("POST", "/api/bbc/v1/room-conferences", {}),
    ]
    for path in ("/api/chat", "/api/tools", "/api/tasks", "/api/shell/stream", "/api/mcp", "/api/auth/integrations/presets", "/api/integrations", "/api/estate/run", "/api/estate/park", "/api/worker", "/unknown", "/api/bbc/v1/capabilities/unknown/invoke", "/api/bbc/v1/registry"):
        denied.extend((method, path, {}) for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"))
    for method, path, payload in denied:
        response = client.request(method, path, json=payload)
        assert response.status_code == 403, (method, path, response.status_code, response.text)
        assert forbidden not in response.text and str(source.parent) not in response.text
        observed.append(response.status_code)

    # Exercise the existing bearer scopes as well as browser authentication.
    from core.database import ApiToken, SessionLocal
    import bcrypt
    token = "ody_synthetic_reader_token_0000000000000000000000000"
    with SessionLocal() as db:
        if db.query(ApiToken).filter_by(id="reader-fixture").first() is None:
            db.add(ApiToken(id="reader-fixture", name="fixture", token_prefix=token[:8], token_hash=bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode(), owner="fixture", scopes="bbc:read,bbc:invoke", is_active=True))
            db.commit()
    client.cookies.clear()
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get(f"/api/bbc/v1/repositories/{own}").status_code == 200
    assert client.post("/api/bbc/v1/capabilities/bbc.repository.inspect/invoke", json={"inputs": {"repository_id": own}}).status_code == 200
    assert client.post("/api/estate/run", json={}).status_code == 403

    assert not getattr(app.app.state, "_startup_tasks", [])
    assert not hasattr(app, "task_scheduler")
    assert not hasattr(app, "mcp_manager")
    assert "src.app_initializer" not in sys.modules
    assert "src.task_scheduler" not in sys.modules
    assert "src.rag_singleton" not in sys.modules
    # Inspect actual tasks in the running TestClient event loop, not an integer setting.
    async def task_names():
        return [task.get_coro().__qualname__ for task in asyncio.all_tasks()]
    tasks = client.portal.call(task_names)
    assert not any(any(word in name.lower() for word in ("monitor", "reconcile", "skill", "mcp", "scheduler", "keepalive")) for name in tasks), tasks
    children_file = Path(f"/proc/self/task/{os.getpid()}/children")
    children = children_file.read_text().split() if children_file.exists() else None
    assert children == [], "Linux probe found background child processes"

# All existing estate/park/worker function entrypoints refuse before examining
# arguments, writing rows/files, enumerating sources, or starting a process.
direct = 0
for name in ("park_lease_ops", "estate_router", "estate_write_lane", "estate_worker", "estate_worker_client", "estate_worker_procs", "worktree_ops"):
    module = importlib.import_module(f"src.{name}")
    for node in ast.parse(Path(module.__file__).read_text()).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        function = getattr(module, node.name)
        args, kwargs = [], {}
        for param in inspect.signature(function).parameters.values():
            if param.default is not inspect.Parameter.empty:
                continue
            if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
                args.append("synthetic")
            elif param.kind == param.KEYWORD_ONLY:
                kwargs[param.name] = "synthetic"
        try:
            function(*args, **kwargs)
        except PermissionError:
            direct += 1
        else:
            raise AssertionError(f"reader allowed direct {name}.{node.name}")

from src.estate_worker_client import LocalTransport, SshTransport
for transport in (LocalTransport(), SshTransport({})):
    try:
        transport.send({}, deadline_s=1)
    except PermissionError:
        direct += 1
    else:
        raise AssertionError("reader allowed direct transport")

import runpy
try:
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/agent"))
except PermissionError:
    direct += 1
else:
    raise AssertionError("reader allowed estate CLI initialization")

from src.bbc.runtime import build_runtime
runtime = build_runtime(data_dir=app.RUNTIME_PROFILE.data_root, app_root=source)
for name in ("refresh_repository", "create_navigation", "transition_navigation", "run_room_conference", "transition_room_conference"):
    method = getattr(runtime, name)
    args, kwargs = [], {}
    for param in inspect.signature(method).parameters.values():
        if param.default is not inspect.Parameter.empty:
            continue
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            args.append("synthetic")
        elif param.kind == param.KEYWORD_ONLY:
            kwargs[param.name] = "synthetic"
    try:
        method(*args, **kwargs)
    except PermissionError:
        direct += 1
    else:
        raise AssertionError("reader allowed direct BBC mutation")

from core.database import ParkLease, EstateExecution, LogicalSession, RoutingDecision, lease_serialized_transaction, engine
from sqlalchemy import text
try:
    with lease_serialized_transaction(repo_id="synthetic"):
        raise AssertionError("reader admitted authority transaction")
except PermissionError:
    direct += 1
for table in ("park_leases", "estate_executions"):
    try:
        with engine.begin() as connection:
            connection.execute(text(f"/* reader boundary */ DELETE FROM {table}"))
    except PermissionError:
        direct += 1
    else:
        raise AssertionError("reader admitted authority SQL")
for row in (
    ParkLease(id="synthetic", repo_id="synthetic", host_id="synthetic", worktree_path="/synthetic"),
    EstateExecution(id="synthetic", objective="synthetic", executor="synthetic", provider="synthetic", host_id="synthetic", repo_id="synthetic"),
):
    with SessionLocal() as db:
        db.add(row)
        try:
            db.commit()
        except PermissionError:
            db.rollback()
            direct += 1
        else:
            raise AssertionError("reader admitted authority ORM insertion")
with SessionLocal() as db:
    assert all(db.query(model).count() == 0 for model in (ParkLease, EstateExecution, LogicalSession, RoutingDecision))

print("READER_EVIDENCE=" + json.dumps({"profile": app.RUNTIME_PROFILE.name, "denied_http": len(observed), "direct_refusals": direct, "authority_rows": 0, "startup_jobs": 0, "child_processes": children, "tasks": tasks, "threads": [t.name for t in threading.enumerate()]}))
