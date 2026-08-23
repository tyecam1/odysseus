"""Tests for scripts/home_reentry_inventory.py (Workstream I) — a
generic, read-only host-inventory tool that must never hard-code imagined
home hardware and must never itself register/promote a host."""
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_spec = importlib.util.spec_from_file_location(
    "home_reentry_inventory", PROJECT_ROOT / "scripts" / "home_reentry_inventory.py"
)
hri = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hri)


def test_build_inventory_is_read_only_and_never_mutates_estate_config(monkeypatch, tmp_path):
    """The whole point: this script inventories, it never writes
    config/estate.yaml or promotes anything itself."""
    estate_yaml = PROJECT_ROOT / "config" / "estate.yaml"
    before = estate_yaml.read_text(encoding="utf-8")

    hri.build_inventory()

    after = estate_yaml.read_text(encoding="utf-8")
    assert before == after


def test_inventory_reports_all_expected_top_level_keys():
    inventory = hri.build_inventory()
    assert set(inventory) >= {
        "collected_at_host", "identity", "hardware", "tailscale",
        "ollama", "config_local_roots", "systemd_units", "note",
    }
    assert "reachability alone never implies trust" in inventory["note"].lower()


def test_ollama_unreachable_reports_cleanly(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise OSError("connection refused")
    monkeypatch.setattr(hri.urllib.request, "urlopen", fake_urlopen)

    result = hri._ollama_models()
    assert result == {"reachable": False}


def test_ollama_reachable_lists_model_names(monkeypatch):
    import json as _json

    class FakeResponse:
        def read(self):
            return _json.dumps({"models": [{"name": "qwen3:8b"}, {"name": "llama3:70b"}]}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr(hri.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse())

    result = hri._ollama_models()
    assert result == {"reachable": True, "count": 2, "models": ["qwen3:8b", "llama3:70b"]}


def test_systemd_units_strips_bullet_marker_from_failed_units(monkeypatch):
    """`systemctl list-units` prefixes a failed unit's line with a bullet
    character that isn't part of the unit name — a naive split()[0] would
    wrongly report '●' as a matching unit."""
    import types

    fake_output = (
        "● odysseus-chromadb.service loaded failed failed  Odysseus ChromaDB\n"
        "  odysseus-aoteru-lab.service loaded active running  Odysseus lab backend\n"
        "  unrelated.service loaded active running  Something else\n"
    )

    def fake_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=0, stdout=fake_output)
    monkeypatch.setattr(hri.subprocess, "run", fake_run)

    result = hri._systemd_units()
    assert result["matching_units"] == ["odysseus-chromadb.service", "odysseus-aoteru-lab.service"]
    assert "●" not in "".join(result["matching_units"])


def test_config_local_roots_reports_unresolved_without_guessing(tmp_path, monkeypatch):
    config_path = tmp_path / "config.local.json"
    config_path.write_text('{"AI_ROOT": "/does/not/exist", "PHD_ROOT": null}', encoding="utf-8")
    monkeypatch.setattr(hri, "_HOST_LOCAL_PATH", config_path)

    result = hri._config_local_roots()
    assert result["roots"]["AI_ROOT"]["exists"] is False
    assert result["roots"]["PHD_ROOT"]["value"] is None
