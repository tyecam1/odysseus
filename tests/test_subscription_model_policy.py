"""Fail-closed selection of current Codex subscription models."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from src import subscription_model_policy as policy


def mock_catalogue(monkeypatch, models, *, returncode=0):
    def run(argv, **kwargs):
        assert argv == ["/usr/bin/codex", "debug", "models"]
        assert kwargs["timeout"] > 0
        return SimpleNamespace(returncode=returncode, stdout=json.dumps({"models": models}))
    monkeypatch.setattr(subprocess, "run", run)


def test_newest_premium_version_is_selected(monkeypatch):
    mock_catalogue(monkeypatch, [
        {"slug": "gpt-5.6-sol", "visibility": "list"},
        {"slug": "gpt-6-astra", "visibility": "list"},
        {"slug": "gpt-6.1-sol", "visibility": "list"},
        {"slug": "gpt-6-luna", "visibility": "list"},
    ])
    assert policy.resolve_latest_codex_model("/usr/bin/codex") == "gpt-6.1-sol"


def test_future_version_is_selected_without_policy_change(monkeypatch):
    mock_catalogue(monkeypatch, [
        {"slug": "gpt-6.1-sol"}, {"slug": "gpt-7-astra"},
    ])
    assert policy.resolve_latest_codex_model("/usr/bin/codex") == "gpt-7-astra"


def test_future_generic_flagship_is_selected(monkeypatch):
    mock_catalogue(monkeypatch, [
        {"slug": "gpt-6.1-sol"}, {"slug": "gpt-7"},
    ])
    assert policy.resolve_latest_codex_model("/usr/bin/codex") == "gpt-7"


def test_same_version_prefers_flagship(monkeypatch):
    mock_catalogue(monkeypatch, [
        {"slug": "gpt-6.1-sol"}, {"slug": "gpt-6.1-astra"},
    ])
    assert policy.resolve_latest_codex_model("/usr/bin/codex") == "gpt-6.1-astra"


def test_old_catalogue_never_falls_back(monkeypatch):
    mock_catalogue(monkeypatch, [{"slug": "gpt-5.6-sol"}, {"slug": "gpt-6-sol"}])
    with pytest.raises(policy.SubscriptionModelError, match="predates"):
        policy.resolve_latest_codex_model("/usr/bin/codex")


def test_hidden_model_not_selected(monkeypatch):
    mock_catalogue(monkeypatch, [
        {"slug": "gpt-6.1-sol", "visibility": "list"},
        {"slug": "gpt-7-astra", "visibility": "hide"},
    ])
    assert policy.resolve_latest_codex_model("/usr/bin/codex") == "gpt-6.1-sol"


def test_failed_or_invalid_catalogue_fails_closed(monkeypatch):
    mock_catalogue(monkeypatch, [], returncode=1)
    with pytest.raises(policy.SubscriptionModelError):
        policy.resolve_latest_codex_model("/usr/bin/codex")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="not-json"))
    with pytest.raises(policy.SubscriptionModelError):
        policy.resolve_latest_codex_model("/usr/bin/codex")


@pytest.mark.parametrize("value", ["low", "medium", "high", "xhigh", "max"])
def test_effort_levels(monkeypatch, value):
    monkeypatch.setenv("AOTERU_SUBSCRIPTION_REASONING_EFFORT", value)
    assert policy.subscription_effort() == value


def test_invalid_effort_fails_closed(monkeypatch):
    monkeypatch.setenv("AOTERU_SUBSCRIPTION_REASONING_EFFORT", "none")
    with pytest.raises(policy.SubscriptionModelError):
        policy.subscription_effort()
