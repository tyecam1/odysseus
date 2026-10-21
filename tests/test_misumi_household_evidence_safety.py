"""Evidence-safety invariants for the household retrieval paths (src/misumi_household.py).

One field-safety gate covers every path that can show a household line: the lexical search, the resolution hits, the evidence
given to the model and the record listing. These tests plant canary values in fields that are not on the safe allowlist and
assert that none of them can be seen through any public surface; they also cover the compound-item guard, the content-digest
cache key and the bounded candidate output.
"""

import json
import os
from pathlib import Path

import pytest

from src.misumi_household import (  # old
    _HIT_CANDIDATES, HouseholdReadOnlyAdapter, _unsafe_lines, names_non_physical,
)

CANARIES = ("hunter2", "50mg", "4929-1234-5678", "07700900123", "SW1A-secret")

CLEANING = (
    "tasks:\n"
    "  - name: descale kettle\n"
    "    area: kitchen\n"
    "    cadence: monthly\n"
    "    dose: 50mg\n"
    "    wifi_password: hunter2\n"
    "    notes: use the white vinegar\n"
    "  - name: wipe hob\n"
    "    area: kitchen\n"
    "    credentials:\n"
    "      name: hob login\n"
    "      value: 4929-1234-5678\n"
    "    contact_phone: 07700900123\n"
    "    postcode: SW1A-secret\n"
)
STOCK = (
    "items:\n"
    "  - name: milk\n"
    "    quantity: 2 cartons\n"
    "    medication_dose: 50mg\n"
    "    aliases:\n"
    "      - semi skimmed\n"
    "  - name: tea\n"
    "    quantity: 1 box\n"
    "    api_token: hunter2\n"
)


def _write(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def _adapter(tmp_path, files=None):
    root = _write(tmp_path / "hh", files or {"household/cleaning/rota.yaml": CLEANING, "household/food/stock.yaml": STOCK})
    return HouseholdReadOnlyAdapter(root)


def _no_canary(payload) -> None:
    blob = json.dumps(payload, default=str)
    for canary in CANARIES:
        assert canary not in blob, f"{canary!r} reached a household surface"


# --- 1. one field-safe representation on every retrieval path -------------------------------------------------------------


@pytest.mark.parametrize("query", [
    "descale kettle", "kitchen cleaning", "what cleaning tasks are monthly", "hob", "kettle dose", "wifi password for the kettle",
    "cleaning task white vinegar", "what is the postcode", "hob login",
])
def test_lexical_cleaning_search_never_shows_fields_outside_the_allowlist(tmp_path, query):
    adapter = _adapter(tmp_path)
    hits = adapter.search(query, domain="cleaning", limit=50)
    _no_canary(hits)


def test_lexical_search_still_answers_from_safe_fields(tmp_path):
    adapter = _adapter(tmp_path)
    hits = adapter.search("descale kettle", domain="cleaning")
    assert hits and "descale kettle" in json.dumps(hits)
    assert "white vinegar" in json.dumps(adapter.search("what do we use to descale the kettle vinegar", domain="cleaning"))


@pytest.mark.parametrize("query", ["do we have milk?", "do we have tea?", "do we have semi skimmed?", "what is in stock?",
                                   "how much milk is left?", "do we have oat milk?"])
def test_every_stock_surface_hides_unlisted_fields(tmp_path, query):
    adapter = _adapter(tmp_path)
    _no_canary(adapter.search(query, domain="food", limit=50))
    resolution = adapter.resolve_question(query, "food")
    if resolution is not None:
        _no_canary(adapter.resolution_hits(resolution))
        _no_canary(adapter.evidence_text(resolution))
    _no_canary(adapter.record_listing(["household/food/stock.yaml"]))


def test_unsafe_lines_masks_nested_and_flow_style_fields():
    lines = [
        "items:",                      # 0 grouping key (transparent)
        "  - name: milk",              # 1
        "    secrets:",                # 2 a bare key over entries only groups them: the leaf fields decide
        "      - name: inner",         # 3 a safe leaf field
        "      - value: hunter2",      # 4 an unlisted leaf field
        "    notes: |",                # 5 safe block scalar
        "      two cartons",           # 6
        "    token: |",                # 7 unsafe block scalar
        "      hunter2",               # 8
        "  - {name: tea, pin: 1234}",  # 9 flow style naming an unsafe key
    ]
    assert _unsafe_lines(lines) == {4, 7, 8, 9}


def test_files_outside_the_allowlist_keep_only_the_blocklist(tmp_path):
    root = _write(tmp_path / "hh", {"household/plants/plants.yaml": "plants:\n  - name: basil\n    health: thriving\n    wifi_password: hunter2\n"})
    hits = HouseholdReadOnlyAdapter(root).search("basil thriving", domain="plants")
    assert "thriving" in json.dumps(hits)
    _no_canary(hits)


# --- 2. compound physical items keep the stock guard -----------------------------------------------------------------------


@pytest.mark.parametrize("mention", ["energy drinks", "room spray", "space heater", "fuel tank cap", "time capsule snacks",
                                     "milk", "washing up liquid", "day cream"])
def test_a_physical_item_with_an_abstract_word_is_not_abstract(mention):
    assert not names_non_physical(mention)


@pytest.mark.parametrize("mention", ["time", "any time", "enough money", "plans", "free time", "a good idea", "the weather",
                                     "space", "some news", "wifi"])
def test_an_entirely_abstract_mention_is_abstract(mention):
    assert names_non_physical(mention)


# --- 3. the cache key follows content, not only size and mtime ------------------------------------------------------------


def test_an_equal_length_edit_that_restores_the_mtime_is_not_served_stale(tmp_path):
    adapter = _adapter(tmp_path, {"household/food/stock.yaml": "items:\n  - name: milk\n    quantity: 2 cartons\n"})
    target = adapter.root / "household" / "food" / "stock.yaml"
    before = target.stat()
    first = adapter.resolve_question("how much milk is left?", "food")
    assert "2 cartons" in adapter.resolution_hits(first)[0]["snippet"]
    target.write_text("items:\n  - name: milk\n    quantity: 9 cartons\n", encoding="utf-8")
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert target.stat().st_size == before.st_size
    second = adapter.resolve_question("how much milk is left?", "food")
    assert "9 cartons" in adapter.resolution_hits(second)[0]["snippet"]


# --- 4. a degraded response is bounded -------------------------------------------------------------------------------------


def test_thousands_of_related_records_give_a_bounded_response(tmp_path):
    body = "items:\n" + "".join(f"  - name: milk variant {n}\n    quantity: 1\n" for n in range(5000))
    adapter = _adapter(tmp_path, {"household/food/stock.yaml": body})
    resolution = adapter.resolve_question("do we have milk?", "food")
    hits = adapter.resolution_hits(resolution)
    assert len(json.dumps(hits)) < 6000
    assert len(hits[0]["candidates"]) <= _HIT_CANDIDATES
    assert hits[0]["candidates_omitted"] >= 4000
    assert len(adapter.evidence_text(resolution)) <= 6000
