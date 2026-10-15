"""A stock question is answered by resolving the item it names to a recorded item, never by counting shared words.

Found by an independent Opus review of PR #122 on the real food stock (48 items): "Do we still have any {item} left in stock?" answered
a confident "No matching food fact" for 21 of 48 items that "Do we have {item} in stock?" found (the evidence-word threshold counted
"still" and "left"; plural folding gave cookies -> cooky but cookie -> cookie, dumplings -> dumpling but dumpling -> dumpl), and two-word
items were answered from a different item that shared one word ("olive oil" from "olives", "coconut milk" from "milk").

Fixtures are synthetic. `test_every_real_stock_item_resolves_identically_across_phrasings` reads a real household checkout when
MISUMI_REAL_HOUSEHOLD_ROOT points at one (read-only); it is skipped otherwise, so CI never needs private data.
"""

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.misumi_routes import setup_misumi_routes
from services.memory.skills import SkillsManager
from src.misumi_household import (
    AMBIGUOUS, FOUND, NOT_PRESENT, UNRESOLVED, HouseholdReadOnlyAdapter, _norm, _singular, phrase_key, stock_item_mention,
)

STOCK = """# Food stock - synthetic fixture in the shape of the real file.
# Schema per item:
#   name:      what it is (required)
updated: 2026-06-23

items:
  - name: eggs
    category: fresh
    quantity: null
    expiry: null
    notes: ""
  - name: olives
    category: jar
    quantity: "1 jar"
  - name: coconut milk
    category: tinned
    quantity: 2 tins
  - name: cookies
    category: snack
    quantity: null
  - name: dumplings
    category: frozen
    quantity: "1 bag"
  - name: dark soy sauce
    category: sauce
    quantity: null
  - name: light soy sauce
    category: sauce
    quantity: null
  - name: Thai red curry paste
    category: sauce
    quantity: null
  - name: red wine vinegar
    category: sauce
    quantity: null
  - name: peanuts
    category: dry
    quantity: null
  - name: peanut butter
    category: jar
    quantity: null
  - name: tomatoes
    category: fresh_veg
    quantity: null
  - name: chopped tomatoes
    category: tinned
    quantity: null
  - name: butter
    category: fresh
    quantity: 0
  - name: birdseye chillies
    category: fresh_veg
    quantity: null
  - name: loaves
    category: bakery
    quantity: null
  - name: broccoli
    category: fresh_veg
    quantity: null
  - name: aubergine
    aliases: [eggplant, brinjal]
    quantity: null
  - name: SAMPLE saffron
    quantity: 99
    example: true
"""
ITEMS = [
    "eggs", "olives", "coconut milk", "cookies", "dumplings", "dark soy sauce", "light soy sauce", "Thai red curry paste",
    "red wine vinegar", "peanuts", "peanut butter", "tomatoes", "chopped tomatoes", "butter", "birdseye chillies", "loaves",
    "broccoli", "aubergine",
]
PHRASINGS = [
    "Do we have {n} in stock?",
    "Do we still have any {n} left in stock?",
    "Is there any {n} in stock?",
    "Have we got any {n} in stock?",
    "Got any {n} in stock?",
    "How much {n} do we have in stock?",
    "How many {n} do we have in stock?",
    "We're out of {n}?",
    "Are we out of {n}?",
    "Don't we have any {n} left?",
    "Any {n} left in the fridge?",
]


def _other_number(name: str) -> str:
    """The other grammatical number of a name's last word, by plain English rules written independently of the adapter."""
    words = name.split()
    word, low = words[-1], words[-1].lower()
    if low.endswith("ies"):
        new = word[:-3] + "y"
    elif low.endswith("ves") and low[:-3] in {"loa", "lea", "hal", "kni"}:
        new = word[:-3] + ("fe" if low.startswith("kni") else "f")
    elif low.endswith(("oes", "ches", "shes", "xes", "sses")):
        new = word[:-2]
    elif low.endswith("s") and not low.endswith("ss"):
        new = word[:-1]
    elif low.endswith("y") and low[-2:-1] not in set("aeiou"):
        new = word[:-1] + "ies"
    elif low.endswith(("o", "ch", "sh", "x")):
        new = word + "es"
    else:
        new = word + "s"
    return " ".join(words[:-1] + [new])


def _root(tmp_path: Path, stock: str = STOCK) -> Path:
    target = tmp_path / "hh" / "household" / "food" / "stock.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stock, encoding="utf-8")
    (target.parent / "shopping-list.md").write_text("# Shopping list\n\n- [ ] milk\n", encoding="utf-8")
    return tmp_path / "hh"


@pytest.fixture()
def adapter(tmp_path):
    return HouseholdReadOnlyAdapter(_root(tmp_path))


# --- the singular/plural normaliser ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("singular,plural", [
    ("egg", "eggs"), ("tomato", "tomatoes"), ("potato", "potatoes"), ("mango", "mangoes"), ("mango", "mangos"),
    ("avocado", "avocados"), ("cookie", "cookies"), ("brownie", "brownies"), ("pie", "pies"), ("brie", "bries"),
    ("berry", "berries"), ("cherry", "cherries"), ("chilli", "chillies"), ("chilli", "chillis"), ("kiwi", "kiwis"),
    ("olive", "olives"), ("clove", "cloves"), ("loaf", "loaves"), ("leaf", "leaves"), ("half", "halves"), ("knife", "knives"),
    ("dumpling", "dumplings"), ("pudding", "puddings"), ("peach", "peaches"), ("sandwich", "sandwiches"), ("quiche", "quiches"),
    ("radish", "radishes"), ("box", "boxes"), ("glass", "glasses"), ("cheese", "cheeses"), ("sauce", "sauces"),
    ("spice", "spices"), ("noodle", "noodles"), ("pea", "peas"), ("honey", "honeys"), ("menu", "menus"), ("sloe", "sloes"),
    ("child", "children"), ("person", "people"), ("mouse", "mice"), ("tooth", "teeth"),
])
def test_singular_and_plural_forms_share_one_key(singular, plural):
    assert _singular(singular) == _singular(plural)
    assert _norm(singular) == _norm(plural)  # the lexical path folds them the same way (cookies/cookie, dumplings/dumpling)


@pytest.mark.parametrize("word", ["hummus", "couscous", "asparagus", "glass", "series"])
def test_words_that_only_look_plural_are_kept_whole(word):
    assert _singular(word) == word


@pytest.mark.parametrize("a,b", [("olive oil", "olives"), ("coconut milk", "milk"), ("egg", "eggplant"), ("peanut", "peanut butter")])
def test_different_items_never_share_a_key(a, b):
    assert phrase_key(a) != phrase_key(b)


# --- scaffolding is removed by pattern, not by a stop list ------------------------------------------------------------------


@pytest.mark.parametrize("question,mention", [
    ("Do we have olive oil in stock?", "olive oil"),
    ("Do we still have any dumplings left in stock?", "dumplings"),
    ("Is there any coconut milk in stock?", "coconut milk"),
    ("Got any eggs?", "eggs"),
    ("How many eggs do we have left?", "eggs"),
    ("How much butter is left in the fridge?", "butter"),
    ("We're out of Thai red curry paste?", "thai red curry paste"),
    ("Have we run out of stock cubes?", "stock cubes"),
    ("Do we have stock cubes in stock?", "stock cubes"),
    ("What quantity of tomatoes is in stock?", "tomatoes"),
    ("Can you check if we have any peanut butter please?", "peanut butter"),
    ("Do we have any left in stock?", ""),
])
def test_the_item_mention_is_what_remains_after_the_question_scaffolding(question, mention):
    assert stock_item_mention(question) == {"mention": mention}


@pytest.mark.parametrize("question", ["What should I cook tonight?", "What's the milk expiry in stock?", "tomatoes carton", "cheese"])
def test_open_questions_are_not_item_questions(question):
    assert stock_item_mention(question) is None


# --- three-way outcome ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ITEMS)
def test_every_phrasing_and_both_numbers_resolve_to_the_same_record(adapter, name):
    expected = None
    for form in (name, _other_number(name)):
        for phrasing in PHRASINGS:
            result = adapter.resolve_item(phrasing.format(n=form), domain="food")
            assert result and result["outcome"] == FOUND, (phrasing.format(n=form), result and result["outcome"])
            ids = [record["id"] for record in result["records"]]
            assert len(ids) == 1
            expected = expected or ids[0]
            assert ids[0] == expected, phrasing.format(n=form)


def test_the_still_left_phrasing_that_used_to_say_no_match_finds_the_item(adapter):
    for name in ITEMS:
        hits = adapter.search(f"Do we still have any {name} left in stock?", domain="food")
        assert hits and hits[0]["resolution"] == FOUND and hits[0]["entry"] == name


@pytest.mark.parametrize("question,partial", [
    ("Do we have olive oil in stock?", "olives"),
    ("Do we have soy sauce in stock?", "dark soy sauce"),
    ("Is there any vinegar in stock?", "red wine vinegar"),
    ("Do we have curry paste in stock?", "Thai red curry paste"),
    ("Any brocoli in stock?", "broccoli"),
])
def test_a_partial_match_is_reported_as_unconfirmed_never_as_yes_or_no(adapter, question, partial):
    result = adapter.resolve_item(question, domain="food")
    assert result["outcome"] == AMBIGUOUS
    assert partial in [record["name"] for record in result["candidates"]]
    (hit,) = adapter.search(question, domain="food")
    assert hit["resolution"] == AMBIGUOUS and hit["snippet"].startswith("Not confirmed") and partial in hit["snippet"]
    assert "entry" not in hit


def test_coconut_milk_is_not_answered_from_milk_nor_milk_from_coconut_milk(tmp_path):
    milk_only = HouseholdReadOnlyAdapter(_root(tmp_path / "a", "items:\n  - name: milk\n    quantity: 1 pint\n"))
    assert milk_only.resolve_item("Do we have coconut milk in stock?", domain="food")["outcome"] == AMBIGUOUS
    coconut_only = HouseholdReadOnlyAdapter(_root(tmp_path / "b", "items:\n  - name: coconut milk\n    quantity: 2 tins\n"))
    assert coconut_only.resolve_item("Do we have milk in stock?", domain="food")["outcome"] == AMBIGUOUS
    assert coconut_only.resolve_item("Do we have coconut milk in stock?", domain="food")["outcome"] == FOUND


def test_word_order_counts_only_when_the_words_are_exactly_the_same(adapter):
    assert adapter.resolve_item("Do we have sauce soy dark in stock?", domain="food")["outcome"] == FOUND
    assert adapter.resolve_item("Do we have soy dark in stock?", domain="food")["outcome"] == AMBIGUOUS


def test_a_mention_that_names_a_recorded_category_is_a_candidate_not_a_no(tmp_path):
    adapter = HouseholdReadOnlyAdapter(_root(tmp_path, "items:\n  - name: brie\n    category: cheese\n    quantity: null\n"))
    result = adapter.resolve_item("Do we have any cheese in stock?", domain="food")
    assert result["outcome"] == AMBIGUOUS and [record["name"] for record in result["candidates"]] == ["brie"]


def test_an_alias_resolves_to_its_record(adapter):
    result = adapter.resolve_item("Do we have any eggplants in stock?", domain="food")
    assert result["outcome"] == FOUND and result["records"][0]["name"] == "aubergine"


def test_a_genuinely_absent_item_is_not_present_only_when_that_is_safe(adapter):
    result = adapter.resolve_item("Do we have saffron in stock?", domain="food")  # SAMPLE saffron is a demonstration entry
    assert result["outcome"] == NOT_PRESENT and result["read"] == ["household/food/stock.yaml"] and result["checked"] == len(ITEMS)
    assert adapter.search("Do we have saffron in stock?", domain="food") == []
    assert adapter.resolve_item("Do we have red peppers in stock?", domain="food")["outcome"] == NOT_PRESENT  # a shared "red" is not a near miss


@pytest.mark.parametrize("question", [
    "Do we have food for dinner in stock?", "Do we have anything to cook with in stock?", "Do we have any left in stock?",
])
def test_an_unparsed_mention_is_unresolved_not_a_confident_no(adapter, question):
    result = adapter.resolve_item(question, domain="food")
    assert result["outcome"] == UNRESOLVED
    (hit,) = adapter.search(question, domain="food")
    assert hit["snippet"].startswith("Not confirmed")


def test_an_empty_inventory_never_says_an_item_is_absent(tmp_path):
    adapter = HouseholdReadOnlyAdapter(_root(tmp_path, "# TODO populate\nitems: []\n"))
    assert adapter.resolve_item("Do we have eggs in stock?", domain="food")["outcome"] == UNRESOLVED


def test_quantity_zero_is_a_present_record_that_is_out_of_stock(adapter):
    (hit,) = adapter.search("Do we have any butter left in stock?", domain="food")
    assert hit["resolution"] == FOUND and hit["in_stock"] is False and "out of stock" in hit["context"]
    (eggs,) = adapter.search("Do we have eggs in stock?", domain="food")
    assert eggs["in_stock"] is None and "quantity: not recorded" in eggs["context"]  # unknown, never guessed


def test_a_question_that_is_not_about_one_item_keeps_the_ordinary_lookup(adapter):
    assert adapter.resolve_item("What should I cook tonight?", domain="food") is None


# --- end to end through the respond route ---------------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(_root(tmp_path)))
    app = FastAPI()
    app.include_router(setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
    return TestClient(app)


def _ask(client, prompt):
    response = client.post("/misumi/respond", json={"prompt": prompt, "persona": "sanji"})
    assert response.status_code == 200
    return response.json()


def test_route_answers_olive_oil_as_unconfirmed_with_the_partial_candidate(client):
    body = _ask(client, "Do we have olive oil in stock?")
    assert body["source"] == "household-read-only"
    assert "Not confirmed" in body["text"] and "olives" in body["text"] and "No matching" not in body["text"]


def test_route_finds_cookies_with_the_still_left_phrasing(client):
    body = _ask(client, "Do we still have any cookies left in stock?")
    assert "(cookies)" in body["text"] and "name: cookies" in body["text"]


def test_route_says_no_match_for_an_absent_item(client):
    body = _ask(client, "Do we have saffron in stock?")
    assert body["sources"] == [] and "no matching food fact" in body["text"].lower()


# --- real household data (local only) -------------------------------------------------------------------------------------


REAL_ROOT = os.environ.get("MISUMI_REAL_HOUSEHOLD_ROOT", "")


@pytest.mark.skipif(not REAL_ROOT or not Path(REAL_ROOT).is_dir(), reason="MISUMI_REAL_HOUSEHOLD_ROOT not set (real data is local only)")
def test_every_real_stock_item_resolves_identically_across_phrasings():
    adapter = HouseholdReadOnlyAdapter(REAL_ROOT)
    records = adapter.item_index("food")["records"]
    assert records
    failures = []
    for record in records:
        for form in (record["name"], _other_number(record["name"])):
            for phrasing in PHRASINGS:
                result = adapter.resolve_item(phrasing.format(n=form), domain="food")
                ids = [r["id"] for r in result["records"]] if result and result["outcome"] == FOUND else []
                if ids != [record["id"]]:
                    failures.append((record["id"], phrasing, result and result["outcome"]))
    assert not failures, f"{len(failures)} phrasings did not resolve to their record, e.g. {failures[:5]}"
