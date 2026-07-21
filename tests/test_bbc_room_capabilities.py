"""Room capability declarations must always resolve against the live registry.

The first attempt at this used a hand-written map of ids. Nineteen of its twenty
ids did not exist on the real deployment, because model runtimes, connectors,
MCP tools and automations are projected from per-install database rows - the ids
that exist on a given box are exactly the ones a static seed cannot name.

Selecting by *kind* inverts that: ids are read out of the same projection the
unknown-id guard checks against, so a declaration cannot reference something
absent. These tests pin that property rather than pinning any particular id.
"""

from __future__ import annotations

import pytest

from src.bbc.models import Point, Room, Ship
from src.bbc.runtime import (
    ROOM_CAPABILITY_KINDS,
    ROOM_CAPABILITY_LIMIT,
    room_capability_ids,
    unknown_room_capability_ids,
)


class _Entry:
    def __init__(self, entry_id: str, kind: str) -> None:
        self.id = entry_id
        self.kind = kind


class _Registry:
    """Shaped like the real deployment: automations, MCP tools, one capability."""

    def __init__(self, automations: int = 33, tools: int = 16, capabilities: int = 1) -> None:
        self._entries = (
            [_Entry(f"capability:bbc.repository.inspect.{n}", "capability") for n in range(capabilities)]
            + [_Entry(f"automation:{n:08x}", "automation") for n in range(automations)]
            + [_Entry(f"mcp:builtin_browser:tool_{n}", "mcp_tool") for n in range(tools)]
        )

    def entries(self):
        return list(self._entries)

    def entry_ids(self):
        return {entry.id for entry in self._entries}


def _ship(resolved: dict[str, list[str]]) -> Ship:
    rooms = [
        Room(
            id=room_id,
            name=room_id.title(),
            function="test",
            position=Point(x=1, y=1),
            size=Point(x=1, y=1),
            capability_ids=resolved.get(room_id, []),
        )
        for room_id in ("bridge", "observatory", "archive", "commons", "engineering", "workshop")
    ]
    return Ship(id="bbc-odysseus", name="BBC Odysseus", active_room_id="bridge", rooms=rooms)


def test_every_resolved_id_exists_in_the_registry():
    """The property the static map violated nineteen times out of twenty."""
    registry = _Registry()
    resolved = room_capability_ids(registry)
    known = registry.entry_ids()
    assert resolved, "expected at least one room to resolve capabilities"
    for room_id, ids in resolved.items():
        missing = [entry_id for entry_id in ids if entry_id not in known]
        assert not missing, f"{room_id} declares unresolvable ids: {missing}"


def test_the_guard_finds_nothing_on_a_live_resolved_ship():
    registry = _Registry()
    assert unknown_room_capability_ids(_ship(room_capability_ids(registry)), registry) == {}


def test_the_guard_still_catches_a_fabricated_id():
    """The guard must be capable of failing, or it is decoration."""
    registry = _Registry()
    ship = _ship({"observatory": ["capability:does-not-exist"]})
    assert unknown_room_capability_ids(ship, registry) == {
        "observatory": ["capability:does-not-exist"]
    }


@pytest.mark.parametrize("registry", [None, _Registry(0, 0, 0)])
def test_an_unavailable_registry_yields_no_claims(registry):
    """No registry means no capabilities - never stale ones.

    Showing a capability the box cannot presently resolve is the exact failure
    this projection exists to prevent, so degrading to empty is correct rather
    than a gap to be filled with the last known good answer.
    """
    assert room_capability_ids(registry) == {}


def test_a_room_never_exceeds_the_display_limit():
    """The registry can project hundreds; a compartment listing all of them is
    a wall of text rather than an inventory."""
    resolved = room_capability_ids(_Registry(automations=500, tools=500))
    for room_id, ids in resolved.items():
        assert len(ids) <= ROOM_CAPABILITY_LIMIT, f"{room_id} listed {len(ids)}"


def test_unmapped_rooms_declare_nothing():
    """bridge, archive, engineering and research have no kind of their own.

    Inventing one would put claims on screen the registry cannot back.
    """
    resolved = room_capability_ids(_Registry())
    for room_id in ("bridge", "archive", "engineering", "research"):
        assert room_id not in ROOM_CAPABILITY_KINDS
        assert resolved.get(room_id, []) == []


def test_resolution_is_stable_between_calls():
    """An inventory that reshuffles between renders reads as activity that did
    not happen."""
    registry = _Registry()
    assert room_capability_ids(registry) == room_capability_ids(registry)
