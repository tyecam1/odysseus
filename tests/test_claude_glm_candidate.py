import json

from src import estate_router


def test_codex_remains_default_and_glm_requires_explicit_candidate_opt_in():
    assert estate_router._resolve_paid_provider("code-strong")["provider"] == "codex"
    blocked = estate_router._resolve_paid_provider("code-strong", "glm")
    assert blocked["provider"] is None
    selected = estate_router._resolve_paid_provider("code-strong", "glm", True)
    assert selected["provider"] == "glm"
    assert selected["concrete_model_label"] == "glm-5.3"


def test_unknown_paid_provider_fails_truthfully():
    result = estate_router._resolve_paid_provider("code-strong", "does-not-exist", True)
    assert result["provider"] is None
    assert "unknown" in result["reason"]


def test_glm_launcher_response_records_model_and_usage(monkeypatch):
    class FakeProcess:
        returncode = 0

        def communicate(self, prompt, timeout):
            assert prompt == "inspect repository"
            return (json.dumps({"result": "done", "model": "glm-5.3",
                                "usage": {"input_tokens": 4, "output_tokens": 2}}), "")

    monkeypatch.setattr(estate_router, "_resolve_claude_glm_launcher", lambda: ("claude-glm", "available"))
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: FakeProcess())
    result = estate_router.execute_claude_glm("inspect repository")
    assert result["ok"] is True
    assert result["model"] == "glm-5.3"
    assert result["usage"]["output_tokens"] == 2


def test_glm_launcher_missing_is_not_replaced_by_another_provider(monkeypatch):
    monkeypatch.setattr(estate_router, "_resolve_claude_glm_launcher", lambda: (None, "missing"))
    result = estate_router.execute_claude_glm("inspect repository")
    assert result == {"ok": False, "provider": "glm", "error": "missing"}
