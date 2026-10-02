"""The estate registry's prose must not contradict its governed state or the Ratified Phase 4 architecture.

``config/estate.yaml`` carries long explanatory comments written at different dates. The worker block is the governed
truth; these tests keep the prose from claiming something the block (or the ratified architecture) contradicts:

* no ``svc:memory`` broker service (Phase 4 adopts no memory broker, no lab replica and no automatic failover);
* no prose saying the home worker is disabled or has no executors while its block is enabled;
* the estate plan marks its memory-broker section as superseded.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ESTATE = ROOT / "config" / "estate.yaml"


def _flat(text: str) -> str:
    return re.sub(r"[#\s]+", " ", text).lower()


def _service_entries(node):
    if isinstance(node, dict):
        if str(node.get("id", "")).startswith("svc:"):
            yield node
        for value in node.values():
            yield from _service_entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _service_entries(value)


def test_the_registry_describes_no_memory_broker_or_lab_read_cache():
    registry = yaml.safe_load(ESTATE.read_text(encoding="utf-8"))
    services = list(_service_entries(registry))
    assert services, "expected the logical services to be listed"
    assert "svc:memory" not in {s["id"] for s in services}
    for service in services:
        description = _flat(str(service.get("description", "")))
        for stale in ("memory broker", "read-cache", "read cache", "home primary"):
            assert stale not in description, f"{service['id']}: {stale!r}"


def test_home_worker_prose_does_not_contradict_its_governed_state():
    registry = yaml.safe_load(ESTATE.read_text(encoding="utf-8"))
    home = next(h for h in registry["hosts"] if h["id"] == "desktop-in7o23d")
    assert home["worker"]["enabled"] is True and home["worker"]["qualified_executors"] == ["deterministic", "local"]
    flat = _flat(ESTATE.read_text(encoding="utf-8"))
    for stale in (
        "explicit disabled worker pending qualification evidence",
        "worker stays disabled, with no qualified executors",
        "the estate worker stays disabled",
    ):
        assert stale not in flat, stale
    assert "enabled: true" in flat and "codex-write" in flat  # the replacement prose names the governed state


def test_the_estate_plan_marks_its_memory_broker_section_as_superseded():
    plan = (ROOT / "docs" / "aoteru-estate-implementation-plan.md").read_text(encoding="utf-8")
    assert "superseded_in_part_by:" in plan.split("---", 2)[1]
    section = plan.split("## 6. Aoteru memory broker", 1)[1][:2500]
    assert "Superseded in part (2026-10-02)" in section
    for adopted_no in ("no memory broker", "no lab memory replica", "no automatic failover"):
        assert adopted_no in section
    assert "svc:memory        # broker API" not in plan


def test_the_execution_contract_no_longer_names_a_personal_memory_broker():
    contract = (ROOT / "docs" / "aoteru-estate-execution-contract.md").read_text(encoding="utf-8")
    assert "personal-memory broker" not in contract
