"""Stage 7: `agent status` reports each alias's resolution on THIS host
through the canonical resolve_alias(alias, host) (qualification, per-host
binding, live inventory), not only the config's default binding."""
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agent"


def _load():
    loader = importlib.machinery.SourceFileLoader("agent_cli_status_caps", str(SCRIPT))
    spec = importlib.util.spec_from_loader("agent_cli_status_caps", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def test_status_capabilities_resolve_on_this_host(monkeypatch):
    module = _load()
    import src.estate_router as estate_router
    calls = []
    monkeypatch.setattr(estate_router, "resolve_alias", lambda alias, host_id=None: calls.append((alias, host_id)) or (
        {"resolved": True, "concrete_model": "qwen3:8b"} if alias == "local-fast"
        else {"resolved": False, "reason": f"alias {alias} not qualified on {host_id}"}))
    models = {"capabilities": [
        {"alias": "local-fast", "binding": "qwen3:8b", "qualified_hosts": {"hz2-workstation": {"evidence": "e"}}},
        {"alias": "code-fast", "binding": "ornith:9b", "qualified_hosts": {"other": {"evidence": "e"}}},
        {"alias": "code-strong", "binding": None, "qualified_hosts": {"hz2-workstation": {"evidence": "e", "binding": "m"}}},
    ]}
    rows = {r["alias"]: r for r in module._capabilities_on_this_host(models, {"id": "hz2-workstation"})}
    assert calls == [("local-fast", "hz2-workstation"), ("code-fast", "hz2-workstation"),
                     ("code-strong", "hz2-workstation")]
    assert rows["local-fast"]["resolved_on_this_host"] is True and rows["local-fast"]["concrete_model"] == "qwen3:8b"
    assert rows["code-fast"]["bound"] is True and rows["code-fast"]["qualified_on_this_host"] is False
    assert rows["code-fast"]["resolved_on_this_host"] is False and "not qualified" in rows["code-fast"]["reason"]
    assert rows["code-strong"]["bound"] is False and rows["code-strong"]["binding_on_this_host"] == "m"


def test_status_capabilities_unregistered_host_fails_closed(monkeypatch):
    module = _load()
    rows = module._capabilities_on_this_host({"capabilities": [{"alias": "local-fast", "binding": "q"}]}, None)
    assert rows == [{"alias": "local-fast", "bound": True, "qualified_on_this_host": False,
                     "binding_on_this_host": None, "resolved_on_this_host": False,
                     "reason": "this host is not registered in config/estate.yaml"}]


def test_status_capabilities_router_import_failure_degrades(monkeypatch):
    module = _load()
    import builtins
    real_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "src.estate_router":
            raise ImportError("cannot import name 'resolve_alias'")  # plain ImportError, not ModuleNotFoundError
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    rows = module._capabilities_on_this_host({"capabilities": [{"alias": "local-fast", "binding": "q"}]},
                                             {"id": "hz2-workstation"})
    assert rows[0]["resolved_on_this_host"] is None
    assert rows[0]["reason"].startswith("router unavailable:")
