"""llm_call's `effort` kwarg (docs/aoteru-model-effort-routing.agent-task.md):
forwarded to a provider only when that provider has a configurable
reasoning-effort control. Today that's Mistral thinking-capable models
only — every other provider path is untouched by this parameter."""
import src.llm_core as llm_core


class _FakeResp:
    is_success = True

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


def _capture_payload(monkeypatch):
    captured = {}

    def fake_post(url, headers, **kwargs):
        captured["payload"] = kwargs.get("json")
        return _FakeResp()

    monkeypatch.setattr(llm_core, "httpx_post_kimi_aware", fake_post)
    monkeypatch.setattr(llm_core, "note_model_activity", lambda *a, **k: None)
    return captured


def test_llm_call_effort_forwarded_to_mistral_reasoning_effort(monkeypatch):
    captured = _capture_payload(monkeypatch)
    llm_core.llm_call(
        "https://api.mistral.ai/v1/chat/completions", "magistral-medium",
        [{"role": "user", "content": "hi"}], effort="low",
    )
    assert captured["payload"]["reasoning_effort"] == "low"


def test_llm_call_effort_highest_maps_to_mistral_high(monkeypatch):
    captured = _capture_payload(monkeypatch)
    llm_core.llm_call(
        "https://api.mistral.ai/v1/chat/completions", "magistral-medium",
        [{"role": "user", "content": "hi highest"}], effort="highest",
    )
    assert captured["payload"]["reasoning_effort"] == "high"


def test_llm_call_effort_omitted_keeps_existing_mistral_default(monkeypatch):
    captured = _capture_payload(monkeypatch)
    llm_core.llm_call(
        "https://api.mistral.ai/v1/chat/completions", "magistral-medium",
        [{"role": "user", "content": "hi default"}],
    )
    assert captured["payload"]["reasoning_effort"] == llm_core._MISTRAL_REASONING_EFFORT


def test_llm_call_effort_ignored_for_unsupported_provider(monkeypatch):
    """Ollama's native API has no reasoning-effort control — passing
    `effort` must not change its payload at all (unsupported-provider
    fallback: unchanged/default behaviour)."""
    captured = {}

    def fake_post(url, headers, **kwargs):
        captured["payload"] = kwargs.get("json")
        return _FakeResp()

    monkeypatch.setattr(llm_core, "httpx_post_kimi_aware", fake_post)
    monkeypatch.setattr(llm_core, "note_model_activity", lambda *a, **k: None)
    monkeypatch.setattr(llm_core, "_parse_ollama_response", lambda data: "ok")
    monkeypatch.setattr(llm_core, "get_context_length", lambda url, model: 4096)

    llm_core.llm_call(
        "http://127.0.0.1:11434", "qwen3:8b",
        [{"role": "user", "content": "hi"}], effort="high",
    )
    assert "reasoning_effort" not in captured["payload"]
