"""Stage 7: host-specific capability qualification
(docs/aoteru-multihost-execution-implementation-plan.md Stage 7)."""
from pathlib import Path

import pytest
import yaml

from src import estate_router

REPO_ROOT = Path(__file__).resolve().parents[1]
LAB, HOME = "hz2-workstation", "desktop-in7o23d"


@pytest.fixture
def models(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()

    def _write(capabilities):
        (config / "models.yaml").write_text(yaml.safe_dump({"capabilities": capabilities}))
    monkeypatch.setattr(estate_router, "_CONFIG_DIR", config)
    import src.estate_worker_client as client
    inventory = {LAB: set(), HOME: set()}
    monkeypatch.setattr(client, "worker_inventory", lambda host_id, models=None, **kw: {
        "models": [{"name": name} for name in sorted(inventory[host_id])]})
    monkeypatch.setattr(client, "worker_health", lambda host_id, **kw: {"gpu_yield": {"active": False}})
    return _write, inventory


def test_alias_not_qualified_on_host_fails_even_if_model_present(models):
    write, inventory = models
    write([{"alias": "code-fast", "binding": "ornith:9b", "qualified_hosts": {LAB: {"evidence": "e"}}}])
    inventory[HOME].add("ornith:9b")
    result = estate_router.resolve_alias("code-fast", HOME)
    assert result["resolved"] is False and result["reason"] == f"alias code-fast not qualified on {HOME}"
    inventory[LAB].add("ornith:9b")
    assert estate_router.resolve_alias("code-fast", LAB)["resolved"] is True


def test_alias_qualified_but_model_absent_on_host_fails(models):
    write, inventory = models
    write([{"alias": "local-fast", "binding": "qwen3:8b",
            "qualified_hosts": {LAB: {"evidence": "e"}, HOME: {"evidence": "e"}}}])
    result = estate_router.resolve_alias("local-fast", HOME)
    assert result["resolved"] is False and "not currently live" in result["reason"]


def test_per_host_binding_override(models):
    write, inventory = models
    write([{"alias": "local-fast", "binding": "qwen3:8b",
            "qualified_hosts": {LAB: {"evidence": "e"}, HOME: {"evidence": "h", "binding": "llama3.1:8b"}}}])
    inventory[HOME].add("llama3.1:8b")
    inventory[LAB].add("qwen3:8b")
    home = estate_router.resolve_alias("local-fast", HOME)
    assert home["resolved"] is True and home["concrete_model"] == "llama3.1:8b" and home["evidence"] == "h"
    assert estate_router.resolve_alias("local-fast", LAB)["concrete_model"] == "qwen3:8b"


def test_missing_qualified_hosts_fails_closed(models):
    write, inventory = models
    write([{"alias": "local-fast", "binding": "qwen3:8b"}])
    inventory[LAB].add("qwen3:8b")
    result = estate_router.resolve_alias("local-fast", LAB)
    assert result["resolved"] is False and "not qualified" in result["reason"]


def test_removing_a_host_from_qualified_hosts_removes_it_from_routing(models):
    write, inventory = models
    inventory[HOME].add("qwen3:8b")
    write([{"alias": "local-fast", "binding": "qwen3:8b", "qualified_hosts": {HOME: {"evidence": "e"}}}])
    assert estate_router.resolve_alias("local-fast", HOME)["resolved"] is True
    write([{"alias": "local-fast", "binding": "qwen3:8b", "qualified_hosts": {}}])
    assert estate_router.resolve_alias("local-fast", HOME)["resolved"] is False


def _shipped():
    return yaml.safe_load((REPO_ROOT / "config" / "models.yaml").read_text())["capabilities"]


def test_shipped_models_config_every_bound_alias_declares_qualified_hosts():
    bound = [c for c in _shipped() if c.get("binding") is not None]
    assert {c["alias"] for c in bound} >= {"local-fast", "local-strong", "code-fast", "reasoning-strong",
                                           "vision", "embedding", "reranker"}
    for entry in bound:
        qualified = entry.get("qualified_hosts") or {}
        assert LAB in qualified and qualified[LAB].get("evidence"), entry["alias"]
    structural = {c["alias"]: c for c in bound}
    assert structural["embedding"]["qualified_hosts"][LAB]["evidence"] == "structural-binding-only"
    assert structural["reranker"]["qualified_hosts"][LAB]["evidence"] == "structural-binding-only"
    assert next(c for c in _shipped() if c["alias"] == "code-strong").get("binding") is None


def test_shipped_models_config_home_not_qualified():
    """Changed only by Stage 8's governed enablement commit."""
    for entry in _shipped():
        assert HOME not in (entry.get("qualified_hosts") or {}), entry["alias"]


def test_canary_worker_host_executes_through_the_worker_and_records_the_host(monkeypatch):
    import scripts.run_lm4_production_canary as canary
    import src.estate_worker_client as client
    calls, persisted = [], []

    def _fake(host_id, verb, payload, *, deadline_s):
        calls.append((host_id, verb, payload))
        return {"ok": True, "attestation": {"host_id": host_id},
                "result": {"ok": True, "output": "42", "latency_ms": 7}}
    monkeypatch.setattr(client, "call_worker", _fake)
    monkeypatch.setattr(canary, "_persist", lambda *a, **k: persisted.append((a, k)))
    monkeypatch.setattr(canary, "_score", lambda task, output: (output == "42", "scored"))
    monkeypatch.setattr(canary, "_objective_for", lambda task: "question")
    monkeypatch.setattr(canary, "binding_for_host", lambda alias, host: "qwen3:8b")
    task = {"task_id": "recon-01", "task_class": "recon"}
    result = canary.run_text_task_on_worker(HOME, "local-fast", task, "corpus")
    assert result["status"] == "pass" and result["attested_host"] == HOME
    assert calls == [(HOME, "execute", {"kind": "local-inference", "model": "qwen3:8b",
                                        "objective": "question", "timeout_s": 120.0})]
    assert persisted[0][1]["worker_host"] == HOME
    # an attestation from another host is a failure, never a pass
    monkeypatch.setattr(client, "call_worker", lambda host_id, verb, payload, *, deadline_s: {
        "ok": True, "attestation": {"host_id": "intruder"}, "result": {"ok": True, "output": "42"}})
    assert canary.run_text_task_on_worker(HOME, "local-fast", task, "corpus")["status"] == "fail"


def test_canary_worker_host_is_not_gated_on_qualification_and_never_edits_config(monkeypatch):
    import scripts.run_lm4_production_canary as canary
    before = (REPO_ROOT / "config" / "models.yaml").read_text()
    assert canary.binding_for_host("local-fast", HOME) == "qwen3:8b"     # home unqualified, still measurable
    assert canary.binding_for_host("code-strong", HOME) is None
    assert (REPO_ROOT / "config" / "models.yaml").read_text() == before
