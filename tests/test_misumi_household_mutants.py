"""Mutation-killing guards for the household item-question indexer (src/misumi_household.py).

Each test targets exactly one mutation of the indexer and passes only on the current code:

1. `_INDEXED_PATH` admitting `household/profile/` files (privacy allowlist).
2. The shopping-list alternative of `_INDEXED_PATH` losing its `^...$` anchoring (or any
   other loosening that lets shopping/grocery-NAMED files anywhere under household/ in).
3. Dropping the `_DOC_FILES` (README) exclusion.
4. The index cache key ignoring file size.
5. The index cache key ignoring mtime (a same-size in-place edit must still invalidate).
6. `_quoted` no longer stripping control characters.
7. The `_quoted` length limit being removed.
8. The shopping guard strength threshold being lowered to >= 1.

The `_write` helper is copied from tests/test_misumi_item_resolution.py; fixtures are
synthetic, tmp_path-based and deterministic (mtimes are set explicitly with os.utime).
"""

import json
import os
from pathlib import Path

import pytest

from src.misumi_household import FOUND, HouseholdReadOnlyAdapter, _quoted

STOCK = "items:\n  - name: eggs\n    quantity: 6\n"


def _write(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def _names(adapter: HouseholdReadOnlyAdapter) -> set:
    return {record["name"] for record in adapter.item_index()["records"]}


# --- 1. household/profile/ must never be part of the index allowlist ------------------------------------


def test_household_profile_files_are_never_indexed_whatever_their_name(tmp_path):
    root = _write(tmp_path / "hh", {
        "household/food/stock.yaml": STOCK,
        "household/profile/profile.yaml": "people:\n  - name: alice\n    phone: 07700 900123\n",
        "household/profile/food-stock.yaml": "items:\n  - name: secret snack\n",
    })
    adapter = HouseholdReadOnlyAdapter(root)
    index = adapter.item_index()
    assert index["files"] == ["household/food/stock.yaml"]
    assert not [record for record in index["records"] if "profile" in record["path"]]
    result = adapter.resolve_question("do we have alice?", None)
    assert result is None or result["records"] == []


# --- 2. only exactly a top-level shopping/grocery-list file is indexed ---------------------------------


@pytest.mark.parametrize("rel", [
    "household/health/shopping-notes.md",
    "household/finances/grocery-budget.yaml",
    "household/notes/my-shopping-list.md",
    "household/records/grocery-list-old.md",
    "household/health/shopping-list.md",
])
def test_shopping_or_grocery_named_files_outside_the_allowlist_are_never_indexed(tmp_path, rel):
    content = "items:\n  - name: sertraline\n    dose: 50mg\n" if rel.endswith((".yaml", ".yml")) \
        else "- [ ] secret list item\n"
    root = _write(tmp_path / "hh", {"household/food/stock.yaml": STOCK, rel: content})
    assert HouseholdReadOnlyAdapter(root).item_index()["files"] == ["household/food/stock.yaml"]


# --- 3. directory documentation (README) is never indexed or quoted -------------------------------------


def test_a_readme_in_an_allowlisted_directory_is_never_indexed(tmp_path):
    root = _write(tmp_path / "hh", {
        "household/food/stock.yaml": STOCK,
        "household/food/README.md": "- halloumi is kept in the fridge\n",
        "household/kitchen/README.md": "- the knife block holds the sharp knives\n",
    })
    adapter = HouseholdReadOnlyAdapter(root)
    assert adapter.item_index()["files"] == ["household/food/stock.yaml"]
    assert adapter.resolve_question("do we have halloumi in stock?", "food")["unparsed_lines"] == []
    assert adapter.resolve_question("any knives in the kitchen?", None)["unparsed_lines"] == []


# --- 4. the cache key counts file size -------------------------------------------------------------------


def test_an_edit_that_changes_only_the_size_invalidates_the_cached_index(tmp_path):
    root = _write(tmp_path / "hh", {"household/food/stock.yaml": "items:\n  - name: eggs\n"})
    adapter = HouseholdReadOnlyAdapter(root)
    assert _names(adapter) == {"eggs"}
    target = root / "household" / "food" / "stock.yaml"
    stat = target.stat()
    target.write_text("items:\n  - name: eggs\n  - name: dates\n", encoding="utf-8")  # new size ...
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # ... but the very same mtime
    assert "dates" in _names(adapter)


# --- 5. the cache key counts mtime ------------------------------------------------------------------------


def test_an_in_place_edit_of_the_same_size_invalidates_the_cached_index(tmp_path):
    root = _write(tmp_path / "hh", {"household/food/stock.yaml": "items:\n  - name: eggs\n"})
    adapter = HouseholdReadOnlyAdapter(root)
    assert _names(adapter) == {"eggs"}
    target = root / "household" / "food" / "stock.yaml"
    stat = target.stat()
    target.write_text("items:\n  - name: figs\n", encoding="utf-8")  # same size ...
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000))  # ... but a new mtime
    assert "figs" in _names(adapter)
    assert adapter.resolve_question("do we have figs in stock?", "food")["outcome"] == FOUND


# --- 6. _quoted strips control characters ------------------------------------------------------------------


def test_quoted_data_never_carries_control_characters():
    shown = _quoted("eggs\x1b[31m\rred\x07 pepper")
    assert not [char for char in shown if ord(char) < 32 or ord(char) == 127]
    # a mutant that keeps json.dumps escaping would smuggle them in as \uXXXX escapes
    assert "\\u001b" not in shown and "\\u0007" not in shown and "\\r" not in shown
    assert json.loads(shown) == "eggs [31m red pepper"


# --- 7. _quoted is length bounded ---------------------------------------------------------------------------


def test_quoted_data_is_length_bounded():
    shown = _quoted("milk " + "x" * 500)
    assert len(shown) <= 162 and shown.endswith('…"')
    tighter = _quoted("y" * 300, 80)
    assert len(tighter) <= 82 and tighter.endswith('…"')


# --- 8. a spelling-only relation to a list item is not a shopping-list question ------------------------------


def test_a_spelling_only_list_relation_is_not_a_shopping_question(tmp_path):
    root = _write(tmp_path / "hh", {"household/food/shopping-list.md": "- [ ] bread\n"})
    adapter = HouseholdReadOnlyAdapter(root)
    assert adapter.resolve_question("do we need to buy brea?", None) is None  # strength 1 is not enough
    found = adapter.resolve_question("do we need to buy bread?", None)
    assert found is not None and found["outcome"] == FOUND and found["deterministic"]


def test_a_nested_household_directory_does_not_make_a_shopping_list_indexable(tmp_path):
    root = _write(tmp_path / "hh", {
        "household/food/stock.yaml": STOCK,
        "household/health/household/shopping-list.yaml": "items:\n  - name: insulin\n",
        "household/finances/household/grocery_list.md": "- name: mortgage\n",
    })
    index = HouseholdReadOnlyAdapter(root).item_index()
    assert index["files"] == ["household/food/stock.yaml"]


@pytest.mark.parametrize("question", ["do we have brea for toast?", "do we have anything like brea?"])
def test_a_misspelling_inside_a_longer_phrase_offers_no_candidate_record(tmp_path, question):
    # a mention that is not a clean item name admits only strong (>= 2) relations as candidates; a one-edit spelling is 1
    root = _write(tmp_path / "hh", {"household/food/stock.yaml": "items:\n  - name: bread\n    quantity: 2\n"})
    result = HouseholdReadOnlyAdapter(root).resolve_question(question, None)
    assert result is not None and result["outcome"] != FOUND and result["candidates"] == []
