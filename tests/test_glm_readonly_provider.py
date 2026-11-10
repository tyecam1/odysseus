import ast
import json
import os
import sys

import pytest

from routes.estate_routing_routes import DelegationPreflightUnit, RunTaskEnvelope
from core import database as cdb
from src import delegation_preflight, estate_router, estate_worker
from tests.helpers.sqlite_db import make_temp_sqlite


@pytest.fixture
def glm_admission(monkeypatch):
    outcomes = []
    monkeypatch.setenv("DATABASE_URL", "test-only")
    def admit(provider, **kwargs):
        assert provider == "glm"
        assert kwargs["launch_timeout"] > 0
        return {"allowed": True, "outcome_id": "test-outcome", "provider": provider}
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", admit)
    monkeypatch.setattr(estate_router, "_record_provider_outcome", lambda result, outcome_id: outcomes.append(result))
    monkeypatch.setattr(estate_router, "current_host_id", lambda: "lab")
    return outcomes


@pytest.fixture
def glm_health_db(monkeypatch):
    session, engine, handle = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session)
    monkeypatch.setenv("DATABASE_URL", "test-only")
    yield
    engine.dispose()
    os.unlink(handle.name)


def _launcher(tmp_path, monkeypatch, body):
    launcher = tmp_path / "claude-glm"
    launcher.write_text(f"#!{sys.executable}\n{body}\n")
    launcher.chmod(0o755)
    monkeypatch.setattr(estate_router, "_glm_launcher_path", lambda: launcher)
    return launcher


def _json_stdout(result="advice", model_usage=None, is_error=False):
    response = {"type": "result", "subtype": "success", "is_error": is_error,
                "result": result, "modelUsage": {"glm-5.3": {}} if model_usage is None else model_usage}
    return f"print({json.dumps(response)!r})"


def test_default_codex_and_explicit_glm_envelope():
    default = RunTaskEnvelope(objective="advise", allow_paid_escalation=True).to_task()
    assert "paid_provider" not in default["routing"]
    assert estate_router._resolve_paid_provider("code-strong")["provider"] == "codex"
    explicit = RunTaskEnvelope(objective="advise", allow_paid_escalation=True,
                               paid_provider="glm").to_task()
    assert explicit["routing"]["paid_provider"] == "glm"
    assert DelegationPreflightUnit(task_class="code_review", paid_provider="glm").paid_provider == "glm"


def test_unknown_provider_is_typed_and_never_defaults(monkeypatch):
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: pytest.fail("host probe occurred"))
    result = estate_router.resolve_route({"routing": {"paid_provider": "unknown"}})
    assert result["error_code"] == "unknown_provider"
    assert result["executed"] is False


def test_preflight_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [])
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kwargs: {
        "allowed": True, "provider": provider})
    result = delegation_preflight.delegation_preflight([{"task_class": "code_review",
                                                       "paid_provider": "unknown"}])
    assert result["units"][0]["error_code"] == "unknown_provider"


@pytest.mark.parametrize("executor,allow_paid,expected", [
    ("deterministic", True, "deterministic"),
    ("local", True, "local"),
    ("none", False, "none"),
    ("none", True, "glm"),
])
def test_preflight_glm_only_for_paid_advisory_route(monkeypatch, executor, allow_paid, expected):
    from src import estate_worker_client
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": "lab", "eligible": True, "qualified_executors": ["glm"]}])
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kwargs: {
        "allowed": True, "reason": "ready", "provider": provider})
    monkeypatch.setattr(estate_worker_client, "worker_health", lambda host_id: {
        "codex": {"available": False}, "glm": {"available": True}})
    monkeypatch.setattr(estate_router, "resolve_route", lambda task, record_decision=False: {
        "ok": executor != "none", "route": {"host": "lab", "executor": executor},
        "hosts_checked": [{"host_id": "lab", "qualified_executors": ["glm"]}],
        "decision_id": None})
    unit = DelegationPreflightUnit(task_class="code_review", objective="Review this", capabilities=["code-strong"],
                                   paid_provider="glm", allow_paid_escalation=allow_paid)
    recommendation = delegation_preflight.delegation_preflight([unit.model_dump()])["units"][0]
    route = recommendation["recommended_route"]
    assert (route if isinstance(route, str) else route["executor"]) == expected


@pytest.mark.parametrize("write_fields,expected", [
    ({}, "glm"),
    ({"mode": "implementation"}, None),
    ({"write": True}, None),
    ({"requires_repo_write": True}, None),
])
def test_glm_preflight_uses_explicit_write_intent(monkeypatch, write_fields, expected):
    from src import estate_worker_client
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": "lab", "eligible": True, "qualified_executors": ["glm"]}])
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kwargs: {
        "allowed": True, "reason": "ready", "provider": provider})
    monkeypatch.setattr(estate_worker_client, "worker_health", lambda host_id: {
        "codex": {"available": False}, "glm": {"available": True}})
    monkeypatch.setattr(estate_router, "resolve_route", lambda task, record_decision=False: {
        "ok": False, "route": {"host": "lab", "executor": "none"},
        "hosts_checked": [{"host_id": "lab", "qualified_executors": ["glm"]}]})
    unit = DelegationPreflightUnit(task_class="code_review", repo="odysseus",
                                   objective="Review the patch", paid_provider="glm",
                                   allow_paid_escalation=True, **write_fields)
    result = delegation_preflight.delegation_preflight([unit.model_dump()])["units"][0]
    assert result["recommended_route"] == expected
    assert result["ok"] is (expected == "glm")
    if expected is None:
        assert result["error_code"] == "provider_unqualified"
        assert "write route" in result["reason"]


def test_glm_preflight_infers_repository_implementation_write(monkeypatch):
    from src import estate_worker_client
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": "lab", "eligible": True, "qualified_executors": ["glm"]}])
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider, **kwargs: {
        "allowed": True, "reason": "ready", "provider": provider})
    monkeypatch.setattr(estate_worker_client, "worker_health", lambda host_id: {
        "codex": {"available": False}, "glm": {"available": True}})
    monkeypatch.setattr(estate_router, "resolve_route", lambda task, record_decision=False: {
        "ok": False, "route": {"host": "lab", "executor": "none"},
        "hosts_checked": [{"host_id": "lab", "qualified_executors": ["glm"]}]})
    units = [DelegationPreflightUnit(task_class="code_review", repo="odysseus",
                                    objective=objective, paid_provider="glm",
                                    allow_paid_escalation=True).model_dump()
             for objective in ("Implement the fix", "Review the patch")]
    implementation, review = delegation_preflight.delegation_preflight(units)["units"]
    assert implementation["recommended_route"] is None
    assert implementation["ok"] is False and implementation["error_code"] == "provider_unqualified"
    assert review["recommended_route"] == "glm" and review["ok"] is True


def test_unqualified_host_rejected_before_dispatch(monkeypatch):
    route = {"route": {"host": "lab", "executor": "none", "model_alias": "code-strong"},
             "decision_id": "decision", "hosts_checked": [{"host_id": "lab", "qualified_executors": ["codex"]}]}
    monkeypatch.setattr(estate_router, "resolve_route", lambda task: route)
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda *args, **kwargs: True)
    monkeypatch.setattr(estate_router, "_dispatch_advisory_call", lambda *args, **kwargs: pytest.fail("dispatched"))
    result = estate_router.run_task({"objective": "advise", "requirements": {"capabilities": ["code-strong"]},
                                    "routing": {"allow_paid_escalation": True, "paid_provider": "glm"}})
    assert result["error_code"] == "provider_unqualified"


def test_route_rejects_unqualified_glm_host(monkeypatch):
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": "lab", "eligible": True, "qualified_executors": ["codex"]}])
    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias, host_id: {"resolved": False})
    result = estate_router.resolve_route({"requirements": {"capabilities": ["code-strong"]},
                                          "routing": {"paid_provider": "glm"}}, record_decision=False)
    assert result["error_code"] == "provider_unqualified"
    assert result["executed"] is False


def test_explicit_glm_preserves_local_route(monkeypatch):
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": "lab", "eligible": True, "qualified_executors": ["local"]}])
    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias, host_id: {
        "resolved": True, "concrete_model": "local-model"})
    task = {"requirements": {"capabilities": ["code-strong"]}}
    default = estate_router.resolve_route(task, record_decision=False)
    explicit = estate_router.resolve_route({**task, "routing": {"paid_provider": "glm"}},
                                           record_decision=False)
    assert explicit == default
    assert explicit["route"]["executor"] == "local"


def test_explicit_glm_preserves_deterministic_route_on_unqualified_host(monkeypatch):
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": "lab", "eligible": True, "qualified_executors": ["codex"]}])
    monkeypatch.setattr(estate_router, "_record_decision", lambda *args, **kwargs: "decision")
    result = estate_router.run_task({"task_class": "audit", "routing": {"paid_provider": "glm"}})
    assert result["ok"] is True
    assert result["route"]["executor"] == "deterministic"
    assert result["executed"] is False


def test_omitted_provider_keeps_codex_paid_fallback(monkeypatch):
    from src import estate_worker_client
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": "lab", "eligible": True, "qualified_executors": ["codex"]}])
    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias, host_id: {"resolved": False})
    monkeypatch.setattr(estate_worker_client, "worker_health", lambda host_id: {
        "codex": {"available": True}})
    chosen = []
    monkeypatch.setattr(estate_router, "provider_allows_dispatch", lambda provider: (
        chosen.append(provider) or {"reason": "ready"}))
    result = estate_router.resolve_route({"requirements": {"capabilities": ["code-strong"]}},
                                         record_decision=False)
    assert result["route"]["host"] == "lab"
    assert result["route"]["executor"] == "none"
    assert chosen == ["codex"]


def test_explicit_glm_selects_qualified_host(monkeypatch):
    from src import estate_worker_client
    hosts = [{"host_id": "codex-host", "qualified_executors": ["codex", "local"]},
             {"host_id": "glm-host", "qualified_executors": ["glm"]}]
    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias, host_id: {"resolved": False})
    monkeypatch.setattr(estate_worker_client, "worker_health", lambda host_id: {
        "glm": {"available": host_id == "glm-host"}})
    host, _, executor = estate_router._select_host(hosts, ["code-strong"], paid_provider="glm")
    assert host["host_id"] == "glm-host" and executor == "none"


def test_unready_glm_host_is_not_selected(monkeypatch):
    from src import estate_worker_client
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": "glm-host", "eligible": True, "qualified_executors": ["glm"]}])
    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias, host_id: {"resolved": False})
    monkeypatch.setattr(estate_worker_client, "worker_health", lambda host_id: {
        "glm": {"available": False}})
    result = estate_router.resolve_route({"requirements": {"capabilities": ["code-strong"]},
                                          "routing": {"paid_provider": "glm"}}, record_decision=False)
    assert result["error_code"] == "provider_unavailable"
    assert result.get("route") is None and result["executed"] is False


def test_glm_dispatch_rechecks_worker_readiness(monkeypatch):
    from src import estate_worker_client
    route = {"route": {"host": "lab", "executor": "none", "model_alias": "code-strong"},
             "decision_id": "decision", "hosts_checked": [{"host_id": "lab", "qualified_executors": ["glm"]}]}
    monkeypatch.setattr(estate_router, "resolve_route", lambda task: route)
    monkeypatch.setattr(estate_router, "_update_decision_outcome", lambda *args, **kwargs: True)
    monkeypatch.setattr(estate_worker_client, "worker_health", lambda host_id: {
        "glm": {"available": False}})
    monkeypatch.setattr(estate_router, "_dispatch_advisory_call", lambda *args, **kwargs: pytest.fail("dispatched"))
    result = estate_router.run_task({"objective": "Review the patch", "requirements": {"capabilities": ["code-strong"]},
                                    "routing": {"allow_paid_escalation": True, "paid_provider": "glm"}})
    assert result["error_code"] == "provider_unavailable" and result["executed"] is False


def test_glm_exact_stdin_readonly_args_and_attested_model(tmp_path, monkeypatch, glm_admission):
    capture = tmp_path / "stdin"
    args_capture = tmp_path / "args"
    _launcher(tmp_path, monkeypatch,
              "import pathlib, sys\n"
              f"pathlib.Path({str(capture)!r}).write_text(sys.stdin.read())\n"
              f"pathlib.Path({str(args_capture)!r}).write_text(repr(sys.argv[1:]))\n"
              + _json_stdout())
    prompt = "A prompt with --flag and quota exhausted quoted text\n"
    result = estate_router.execute_glm(prompt, timeout=2)
    assert result["ok"] is True
    assert capture.read_text() == prompt
    args = ast.literal_eval(args_capture.read_text())
    assert args[:4] == ["--print", "--output-format", "json", "--tools"]
    assert args[4].split(",") == ["Read", "Grep", "Glob"]
    assert args[5] == "--disallowedTools"
    assert set(args[6].split(",")) == {"Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "Task", "Skill"}
    assert not set(args[4].split(",")) & {"Bash", "Write", "Edit", "NotebookEdit"}
    assert args[7:] == ["--strict-mcp-config", "--bare",
                        "--disable-slash-commands", "--no-session-persistence"]
    assert "--mcp-config" not in args
    assert result["provider"] == "glm" and result["host_id"] == "lab"
    assert result["exit_code"] == 0 and result["concrete_model"] == "glm-5.3"
    assert result["output"] == "advice" and result["model_unverified"] is False
    assert result["model_attestation"] == "provider-usage-response"
    assert result["model_currency_attested"] is False
    assert glm_admission[-1]["state"] == "completed"


def test_glm_empty_prompt_and_missing_launcher(tmp_path, monkeypatch, glm_admission):
    empty = estate_router.execute_glm("   ")
    assert empty["ok"] is False and empty["executed"] is False
    monkeypatch.setattr(estate_router, "_glm_launcher_path", lambda: tmp_path / "missing")
    missing = estate_router.execute_glm("advice")
    assert missing["error_code"] == "launcher_missing"
    assert missing["executed"] is False


@pytest.mark.parametrize("usage,observed", [
    ({}, []),
    ({"claude-sonnet": {}}, ["claude-sonnet"]),
    ({"glm-5.3": {}, "glm-5.2": {}}, ["glm-5.3", "glm-5.2"]),
])
def test_glm_model_usage_mismatch_has_no_provider_cooldown(
        tmp_path, monkeypatch, glm_health_db, usage, observed):
    _launcher(tmp_path, monkeypatch,
              "import sys\n" + _json_stdout(model_usage=usage)
              + "\nprint('quota exceeded', file=sys.stderr)")
    result = estate_router.execute_glm("Review the patch", timeout=2)
    assert result["ok"] is False and result["error_code"] == "model_mismatch"
    assert result["model_unverified"] is True and result["concrete_model"] is None
    assert result["observed_models"] == observed
    assert result["model_currency_attested"] is False
    assert estate_router.provider_allows_dispatch("glm")["allowed"] is True
    with cdb.get_db_session() as db:
        rows = db.query(cdb.RoutingDecision).filter_by(executor="glm").all()
        assert len(rows) == 1 and rows[0].task_class == "provider_attempt"


def test_glm_missing_model_usage_fails_closed(tmp_path, monkeypatch, glm_admission):
    response = {"type": "result", "subtype": "success", "is_error": False, "result": "advice"}
    _launcher(tmp_path, monkeypatch, f"print({json.dumps(response)!r})")
    result = estate_router.execute_glm("Review the patch", timeout=2)
    assert result["error_code"] == "model_mismatch" and result["observed_models"] == []


def test_glm_error_result_is_failure(tmp_path, monkeypatch, glm_admission):
    _launcher(tmp_path, monkeypatch, _json_stdout(is_error=True))
    result = estate_router.execute_glm("Review the patch", timeout=2)
    assert result["ok"] is False and result["error_code"] == "nonzero_exit"
    assert result["model_unverified"] is True
    assert glm_admission[-1]["state"] == "failed"


@pytest.mark.parametrize("stdout", ["not json", json.dumps({"type": "other", "is_error": False, "result": "advice"})])
def test_glm_bad_output_has_no_provider_cooldown(tmp_path, monkeypatch, glm_health_db, stdout):
    _launcher(tmp_path, monkeypatch,
              f"import sys\nprint({stdout!r})\nprint('quota exceeded', file=sys.stderr)")
    result = estate_router.execute_glm("Review the patch", timeout=2)
    assert result["ok"] is False and result["error_code"] == "bad_output"
    assert result["model_unverified"] is True
    assert estate_router.provider_allows_dispatch("glm")["allowed"] is True
    with cdb.get_db_session() as db:
        rows = db.query(cdb.RoutingDecision).filter_by(executor="glm").all()
        assert len(rows) == 1 and rows[0].task_class == "provider_attempt"


@pytest.mark.parametrize("prompt,expected,cooled", [
    ("Review the patch", "quota_exhausted", True),
    ("usage limit reached", "bad_output", False),
])
def test_glm_garbled_nonzero_stdout_uses_scrubbed_stderr(
        tmp_path, monkeypatch, glm_health_db, prompt, expected, cooled):
    _launcher(tmp_path, monkeypatch,
              "import sys\nprint('not json')\n"
              "print('usage limit reached', file=sys.stderr)\nsys.exit(7)")
    result = estate_router.execute_glm(prompt, timeout=2)
    assert result["error_code"] == expected and result["exit_code"] == 7
    health = estate_router.provider_allows_dispatch("glm")
    assert health["allowed"] is not cooled
    assert health["state"] == ("quota_exhausted" if cooled else "unknown")


@pytest.mark.parametrize("status,expected,cooled", [
    (429, "rate_limited", True),
    (401, "auth_failed", True),
    (403, "auth_failed", True),
    (500, "nonzero_exit", False),
    (None, "nonzero_exit", False),
])
def test_glm_error_result_uses_api_status_without_result_text(
        tmp_path, monkeypatch, glm_health_db, status, expected, cooled):
    response = {"type": "result", "is_error": True, "result": "usage limit reached"}
    if status is not None:
        response["api_error_status"] = status
    _launcher(tmp_path, monkeypatch,
              "import sys\n" + f"print({json.dumps(response)!r})\n"
              "print('quota exhausted', file=sys.stderr)")
    result = estate_router.execute_glm("Review the patch", timeout=2)
    assert result["error_code"] == expected and result["ok"] is False
    health = estate_router.provider_allows_dispatch("glm")
    assert health["allowed"] is not cooled
    assert health["state"] == (expected if cooled else "unknown")


@pytest.mark.parametrize("stderr,expected", [
    ("authentication failed", "auth_failed"),
    ("quota exceeded", "quota_exhausted"),
    ("rate limit exceeded", "rate_limited"),
    ("ordinary error", "nonzero_exit"),
])
def test_glm_nonzero_classifies_only_launcher_stderr(tmp_path, monkeypatch, glm_admission, stderr, expected):
    _launcher(tmp_path, monkeypatch,
              "import sys\n"
              + _json_stdout("quota exceeded in echoed prompt") + "\n"
              + f"print({stderr!r}, file=sys.stderr)\n"
              + "sys.exit(7)")
    result = estate_router.execute_glm("sensitive prompt", timeout=2)
    assert result["error_code"] == expected and result["exit_code"] == 7
    assert "sensitive prompt" not in str(result)
    assert "quota exceeded in echoed prompt" not in str(result)
    assert glm_admission[-1]["stderr"] == stderr + "\n"


def test_glm_echoed_prompt_cannot_exhaust_quota(tmp_path, monkeypatch, glm_admission):
    prompt = "Review this text: quota exhausted"
    _launcher(tmp_path, monkeypatch,
              "import sys\n"
              + _json_stdout() + "\n"
              + "print(sys.stdin.read(), file=sys.stderr)\n"
              + "sys.exit(7)")
    result = estate_router.execute_glm(prompt, timeout=2)
    assert result["error_code"] == "nonzero_exit"
    assert glm_admission[-1]["stderr"].strip() == " ".join(["\ue000"] * len(prompt.split()))
    assert estate_router._provider_outcome(glm_admission[-1])["state"] != "quota_exhausted"


@pytest.mark.parametrize("prompt,stderr,expected,retained", [
    ("usage limit", "usage limit", "nonzero_exit", "\ue000 \ue000\n"),
    ("Please investigate limit reached soon", "limit reached", "nonzero_exit", "\ue000 \ue000\n"),
    ("Review the request", "usage limit reached", "quota_exhausted", "usage limit reached\n"),
    ("429", "Prompt: 429", "nonzero_exit", "Prompt: \ue000\n"),
    ("usage limit", "error: usage limit", "nonzero_exit", "error: \ue000 \ue000\n"),
    ("inspect output", "HTTP 429 Too Many Requests: usage limit reached", "quota_exhausted",
     "HTTP 429 Too Many Requests: usage limit reached\n"),
])
def test_glm_stderr_removes_prompt_tokens_before_classification(
        tmp_path, monkeypatch, glm_admission, prompt, stderr, expected, retained):
    _launcher(tmp_path, monkeypatch, "import sys\n"
              + _json_stdout() + "\n"
              + f"print({stderr!r}, file=sys.stderr)\n"
              + "sys.exit(7)")
    result = estate_router.execute_glm(prompt, timeout=2)
    assert result["error_code"] == expected
    assert glm_admission[-1]["stderr"] == retained
    health = estate_router._provider_outcome(glm_admission[-1])
    if expected == "nonzero_exit":
        assert health["state"] == "unknown" and health["retry_after"] is None
    else:
        assert health["state"] == expected


def test_scrubbing_cannot_create_quota_marker_or_cooldown(tmp_path, monkeypatch, glm_health_db):
    _launcher(tmp_path, monkeypatch,
              "import sys\n" + _json_stdout() + "\nprint('quota zexceeded', file=sys.stderr)\nsys.exit(7)")
    result = estate_router.execute_glm("z", timeout=2)
    assert result["error_code"] == "nonzero_exit" and result["exit_code"] == 7
    health = estate_router.provider_allows_dispatch("glm")
    assert health["allowed"] is True and health["state"] == "unknown"


def test_generic_429_is_not_glm_provider_limit(tmp_path, monkeypatch, glm_health_db):
    _launcher(tmp_path, monkeypatch,
              "import sys\n" + _json_stdout() + "\nprint('MCP tool failed: 429', file=sys.stderr)\nsys.exit(7)")
    result = estate_router.execute_glm("Review the patch", timeout=2)
    assert result["error_code"] == "nonzero_exit"
    health = estate_router.provider_allows_dispatch("glm")
    assert health["allowed"] is True and health["state"] == "unknown"


def test_glm_timeout_kills_process(tmp_path, monkeypatch, glm_admission):
    _launcher(tmp_path, monkeypatch, "import time\ntime.sleep(30)")
    result = estate_router.execute_glm("advice", timeout=0.05)
    assert result["error_code"] == "timeout"
    assert result["executed"] is True
    assert estate_router._provider_outcome(glm_admission[-1])["state"] == "unreachable"


@pytest.mark.parametrize("failure", ["launcher_missing", "timeout"])
def test_glm_host_local_failure_does_not_cool_provider(
        tmp_path, monkeypatch, glm_health_db, failure):
    if failure == "launcher_missing":
        monkeypatch.setattr(estate_router, "_glm_launcher_path", lambda: tmp_path / "missing")
    else:
        _launcher(tmp_path, monkeypatch, "import time\ntime.sleep(30)")
    result = estate_router.execute_glm("Review the implementation", timeout=0.05)
    assert result["error_code"] == failure
    assert estate_router.provider_allows_dispatch("glm")["allowed"] is True
    with cdb.get_db_session() as db:
        attempts = db.query(cdb.RoutingDecision).filter_by(executor="glm").all()
        assert len(attempts) == 1
        assert attempts[0].task_class == "provider_attempt"
        assert attempts[0].status == "failed"
        attempt = json.loads(attempts[0].escalation_reason)
        assert attempt["error_code"] == failure
        assert attempt["attempt_outcome"]["retry_after"] is None


def test_glm_provider_quota_still_cools_provider(tmp_path, monkeypatch, glm_health_db):
    _launcher(tmp_path, monkeypatch,
              "import sys\n" + _json_stdout() + "\nprint('quota exceeded', file=sys.stderr)\nsys.exit(7)")
    result = estate_router.execute_glm("Review the implementation", timeout=2)
    assert result["error_code"] == "quota_exhausted"
    health = estate_router.provider_allows_dispatch("glm")
    assert health["state"] == "quota_exhausted" and health["allowed"] is False
    with cdb.get_db_session() as db:
        rows = db.query(cdb.RoutingDecision).filter_by(executor="glm").all()
        assert len(rows) == 1 and rows[0].task_class == "provider_outcome"


def test_glm_rate_health_is_provider_scoped():
    glm = estate_router._provider_outcome({"ok": False, "provider": "glm", "exit_code": 1,
                                           "stderr": "429 rate limit"})
    codex = estate_router._provider_outcome({"ok": False, "provider": "codex", "exit_code": 1,
                                             "stderr": "429 rate limit"})
    assert glm["state"] == "rate_limited"
    assert codex["state"] == "unknown"


def test_worker_glm_readonly_dispatch(monkeypatch):
    monkeypatch.setattr(estate_worker.estate_router, "current_host_id", lambda: "lab")
    monkeypatch.setattr(estate_worker.estate_router, "_load_yaml", lambda name: {
        "hosts": [{"id": "lab", "worker": {"qualified_executors": ["glm"]}}]})
    monkeypatch.setattr(estate_worker.estate_router, "execute_glm", lambda objective, **kwargs: {
        "ok": True, "output": objective, "provider": "glm"})
    result = estate_worker._verb_execute({"kind": "glm-readonly", "objective": "advise", "timeout_s": 1})
    assert result["provider"] == "glm" and result["output"] == "advise"


def test_worker_glm_readonly_rejects_unqualified_host(monkeypatch):
    monkeypatch.setattr(estate_worker.estate_router, "current_host_id", lambda: "lab")
    monkeypatch.setattr(estate_worker.estate_router, "_load_yaml", lambda name: {
        "hosts": [{"id": "lab", "worker": {"qualified_executors": ["codex"]}}]})
    monkeypatch.setattr(estate_worker.estate_router, "execute_glm", lambda *args, **kwargs: pytest.fail("dispatched"))
    with pytest.raises(estate_worker.WorkerError) as error:
        estate_worker._verb_execute({"kind": "glm-readonly", "objective": "advise", "timeout_s": 1})
    assert error.value.code == "executor_unqualified"


def test_worker_health_reports_glm_launcher_readiness(tmp_path, monkeypatch):
    launcher = tmp_path / "claude-glm"
    launcher.write_text("#!/bin/sh\n")
    launcher.chmod(0o755)
    monkeypatch.setattr(estate_worker.estate_router, "_glm_launcher_path", lambda: launcher)
    monkeypatch.setattr(estate_worker, "_ollama_inventory", lambda: (False, [], "offline"))
    monkeypatch.setattr(estate_worker.estate_router, "_codex_available", lambda: (False, "absent"))
    monkeypatch.setattr(estate_worker.estate_router, "experiment_priority_active", lambda: (False, "idle"))
    monkeypatch.setattr(estate_worker.estate_router, "host_gpu_admission_config", lambda host: None)
    monkeypatch.setattr(estate_worker, "_in_flight_execution_ids", lambda: [])
    monkeypatch.setattr(estate_worker, "_write_prerequisites", lambda: {})
    assert estate_worker._verb_health({})["glm"]["available"] is True
