"""A grounded household answer must be evidence, not the nearest word match - and must not lose real facts.

Found by the 2026-10-06 kiosk real-path test: a records question routed correctly to `jin` on the household-read-only path, but the
reply was an unrelated retrieved line ("future views over the YAML"). The line sat in a notes file about a view that does not exist yet
and matched on common words ("play", "tonight"); the handler returned the first hit with no relevance floor.

An independent review of the first repair then showed the opposite failure on real data: "Do we have eggs in stock?" answered "no
match" because filler words ("do", "we") counted as content, and notes such as "Future: generated from stock.yaml", headings and
`plants: []` were still returned as evidence. The fixtures below copy the SHAPES of the real food, cleaning, plants and records files
(synthetic content): schema comments, `key: null` fields, TODO placeholders, template rows, pointer lines, headings.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.misumi_routes import setup_misumi_routes
from services.memory.skills import SkillsManager
from src.misumi_household import HouseholdReadOnlyAdapter

FILES = {
    "household/records/collection.yaml": """# Record collection - single source of truth.
# Schema per record:
#   moods:          list of free-vocabulary mood strings
#   condition:      ok / needs cleaning / damaged / null
updated: null  # TODO: set on first shelf audit

records:
  - artist: "Miles Davis"
    title: "Kind of Blue"
    year: 1959
    format: "LP"
    moods:
      - "late night"
      - "focused"
    condition: "needs cleaning"
    needs_cleaning: true
    example: false
  - artist: "Nina Simone"
    title: "Pastel Blues"
    year: 1965
    format: "LP"
    moods:
      - "sunny morning"
    condition: "ok"
    needs_cleaning: false
    example: false
  - artist: "Bill Evans"
    title: "Waltz for Debby"
    year: 1961
    format: "LP"
    moods:
      - "late night"
    condition: "ok"
    needs_cleaning: false
    example: false
  - artist: "EXAMPLE ARTIST A"
    title: "EXAMPLE RECORD ONE"
    year: 2001
    format: "LP"
    moods:
      - "late night"
      - "loud"
    condition: "needs cleaning"
    needs_cleaning: true
    notes: "EXAMPLE NOTE: demonstration entry only."
    example: true
""",
    "household/records/collection.md": """# Record collection

**Data lives in [`collection.yaml`](collection.yaml).** This file is the pointer plus future-facing notes.

- New arrival: add an entry to `collection.yaml`.
- What did we play: [`listening-log.md`](listening-log.md).
- Mood-based browsing and "what should I play tonight?" are future views over the YAML - see `agent-tasks/inbox/record-browsing-views.md`.

TODO: first shelf audit to populate `collection.yaml`.
""",
    "household/records/README.md": "# Records\n\n- `collection.yaml` - owned records\n- `wantlist.md` - records you are hunting\nSuggested editable moods: late night, sunny morning.\n",
    "household/records/wantlist.md": "# Wantlist\n\nRecords to hunt for. Move to `collection.yaml` when acquired.\n\n- [ ] YYYY-MM-DD - artist - title (max price? where seen?)\n",
    "household/records/arrivals.md": "# New arrivals\n\nDated log of records just acquired, newest first.\n\n- TODO: YYYY-MM-DD - artist - title (format)\n",
    "household/records/listening-log.md": "# Listening log\n\n| Date | Record(s) | Mood / occasion | Notes |\n|---|---|---|---|\n| _TODO_ | | | |\n",
    "household/food/stock.yaml": """# Food stock - single source of truth.
# Schema per item:
#   name:      what it is (required)
#   expiry:    YYYY-MM-DD or null - only if actually checked
updated: 2026-06-23

items:
  - name: eggs
    category: fresh
    quantity: null
    expiry: null
    notes: ""
  - name: tomatoes
    category: fresh_veg
    quantity: "1 carton"   # TODO recheck
    expiry: null
    notes: ""
  - name: garlic
    category: fresh_veg
    quantity: null
    expiry: null
    notes: ""
  - name: limes
    category: fresh_veg
    quantity: null
    expiry: null
    notes: ""
""",
    "household/food/stock.md": "# Food stock\n\nData lives in [`stock.yaml`](stock.yaml).\n",
    "household/food/kitchen-equipment.yaml": "items:\n  - mortar and pestle\n  - crush_garlic\n",
    "household/food/shopping-list.md": (
        "# Shopping list\n\nTick or delete when bought. Future: generated from `stock.yaml` (see `agent-tasks/inbox/shopping-list-generator.md`).\n\n"
        "## Need\n- [ ] desk\n- [ ] tv stand\n\n- [ ] TODO: first real item\n\n## Maybe / when cheap\n\n- [ ] TODO\n"
    ),
    "household/cleaning/rota.md": (
        "# Cleaning rota\n\nTwo people. Task definitions live in [`tasks.yaml`](tasks.yaml).\n\n**People:** Person A = TODO name, Person B = TODO name.\n\n"
        "| Task | This week | Next week |\n|---|---|---|\n| _populate from tasks.yaml_ | B | A |\n\n"
        "Rotation is manual for now - swap the columns when the week flips. Automation is a future task: `agent-tasks/inbox/rota.md`.\n"
    ),
    "household/cleaning/history.md": "# Cleaning history\n\nHousehold log, not an audit trail. One line when something is worth remembering (swaps, skipped weeks).\n",
    "household/cleaning/tasks.yaml": "tasks:\n  - name: bathroom clean\n    area: bathroom\n    cadence: weekly\n  - name: kitchen clean\n    area: kitchen\n    cadence: weekly\n",
    "household/plants/plants.yaml": "# Plant registry seed.\nstatus: proposed\nplants: []\n",
    "household/maintenance/open.md": (
        "# Open loops\n\n- TODO: call plumber about the boiler leak (urgent)\n- [Boiler service](boiler.md) booked for 2026-10-20\n"
        "- Future work: replace the broken extractor fan\n"
    ),
}


def _write_root(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


@pytest.fixture()
def household(tmp_path: Path) -> Path:
    return _write_root(tmp_path / "household-repo", FILES)


@pytest.fixture()
def client(household, tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(household))
    app = FastAPI()
    app.include_router(setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
    return TestClient(app)


def _ask(client, prompt, persona="jin"):
    response = client.post("/misumi/respond", json={"prompt": prompt, "persona": persona})
    assert response.status_code == 200
    return response.json()


def _no_match(body, domain):
    assert body["source"] == "household-read-only"
    assert body["sources"] == []
    assert f"no matching {domain} fact" in body["text"].lower()


# --- the reported defect, end to end through the respond route -------------------------------------------------------


def test_the_kiosk_recommendation_question_is_not_answered_with_a_note_about_a_future_view(client):
    body = _ask(client, "What should I play tonight?")
    _no_match(body, "records")
    assert "future views" not in body["text"].lower()
    assert "recommendation" in body["text"].lower()


@pytest.mark.parametrize("prompt", ["What record should I play?", "Which record suits my mood?", "Do we own any Beatles records?"])
def test_records_questions_without_evidence_are_an_explicit_grounded_failure(client, prompt):
    body = _ask(client, prompt)
    _no_match(body, "records")
    assert "collection.yaml line" not in body["text"]


def test_a_direct_relevant_query_returns_a_real_entry(client):
    body = _ask(client, "Which records are late night?")
    assert body["source"] == "household-read-only"
    assert "Kind of Blue" in body["text"]
    assert "EXAMPLE" not in body["text"]


def test_a_paraphrase_finds_the_same_entry(client):
    body = _ask(client, "Which album would suit a late night?")
    assert "Kind of Blue" in body["text"]
    assert "EXAMPLE" not in body["text"]


def test_a_near_neighbour_query_about_one_title_returns_that_title(client):
    body = _ask(client, "What does the music collection say about Pastel Blues?")
    assert "Pastel Blues" in body["text"]
    assert "Kind of Blue" not in body["text"]


def test_several_real_records_can_match_and_placeholders_never_do(client):
    body = _ask(client, "Which records are late night?")
    snippets = " ".join(item["snippet"] for item in body["sources"])
    assert len(body["sources"]) >= 2  # Kind of Blue and Waltz for Debby both carry the mood
    assert "EXAMPLE" not in snippets and "YYYY" not in snippets
    assert {item["path"] for item in body["sources"]} == {"household/records/collection.yaml"}


# --- real facts must still be found (the false "no match" the review found) ---------------------------------------------


@pytest.mark.parametrize("prompt,needle", [
    ("Do we have eggs in stock?", "eggs"),
    ("Do we have any tomatoes in stock?", "tomatoes"),
    ("Have we got any limes in stock?", "limes"),
    ("Is there any garlic in stock?", "garlic"),
])
def test_everyday_stock_questions_find_the_item(client, prompt, needle):
    body = _ask(client, prompt, persona="sanji")
    assert body["source"] == "household-read-only"
    assert needle in body["text"].lower()
    assert "future:" not in body["text"].lower()


def test_a_garlic_question_prefers_the_stock_file_over_a_cooking_note(client):
    body = _ask(client, "Is there any garlic in stock?", persona="sanji")
    assert body["sources"][0]["path"] == "household/food/stock.yaml"


def test_a_question_that_names_the_list_returns_its_real_items_not_the_heading(client):
    body = _ask(client, "what is on the shopping list?", persona="sanji")
    assert body["source"] == "household-read-only"
    assert "desk" in body["text"]
    assert "# Shopping list" not in body["text"] and "TODO" not in body["text"]
    assert all("shopping-list.md" in item["path"] for item in body["sources"])


def test_an_unpopulated_rota_is_reported_as_no_match_not_as_a_note(client):
    body = _ask(client, "What's on the cleaning rota this week?", persona="misato")
    _no_match(body, "cleaning")


def test_an_empty_registry_is_reported_as_no_match_not_as_an_empty_list(client):
    body = _ask(client, "When should I water the plants?", persona="ginko")
    _no_match(body, "plants")


def test_a_question_about_a_task_finds_it(client):
    body = _ask(client, "Whose turn is it to clean the bathroom?", persona="misato")
    assert body["source"] == "household-read-only"
    assert "bathroom" in body["text"].lower()


def test_existing_grounded_lookup_still_works(client):
    body = _ask(client, "what is on the shopping list?", persona="sanji")
    assert "shopping-list.md" in body["sources"][0]["path"]


# --- the retrieval layer on its own ----------------------------------------------------------------------------------


def test_search_never_returns_headings_placeholders_empty_values_pointers_or_unbuilt_view_notes(household):
    adapter = HouseholdReadOnlyAdapter(household)
    banned = ("future views", "Future:", "future task", "YYYY", "_TODO_", "TODO name", "first real item", "plants: []", "# ", "populate from")
    for query, domain in (
        ("what should I play tonight", "records"), ("record browsing views over the YAML", "records"), ("wantlist title price", "records"),
        ("shopping list generated from stock", "shopping"), ("cleaning rota automation task", "cleaning"), ("plants registry", "plants"),
        ("data lives in collection", "records"),
    ):
        for hit in adapter.search(query, domain=domain, limit=20):
            assert not any(token in hit["snippet"] for token in banned), (query, hit)


def test_search_never_returns_a_demonstration_entry(household):
    adapter = HouseholdReadOnlyAdapter(household)
    hits = adapter.search("example record one needs cleaning demonstration", domain="records", limit=20)
    assert not [hit for hit in hits if "EXAMPLE" in hit["snippet"]]


def test_an_example_flag_inside_a_nested_list_does_not_hide_the_parent_entry(tmp_path):
    root = _write_root(tmp_path / "hh", {
        "household/plants/plants.yaml": (
            "plants:\n  - name: basil\n    care:\n      - step: prune\n        example: true\n  - name: mint\n    example: true\n"
        ),
    })
    adapter = HouseholdReadOnlyAdapter(root)
    assert [hit["snippet"] for hit in adapter.search("basil", domain="plants")] == ["- name: basil"]
    assert adapter.search("mint", domain="plants") == []  # the entry's own example flag still hides it


def test_search_labels_a_structured_hit_with_the_entry_it_belongs_to(household):
    adapter = HouseholdReadOnlyAdapter(household)
    hits = adapter.search("records late night", domain="records", limit=5)
    assert hits and hits[0]["entry"] == "Miles Davis - Kind of Blue"


def test_search_requires_more_than_one_stray_word_when_the_query_has_several_terms(household):
    adapter = HouseholdReadOnlyAdapter(household)
    assert adapter.search("Do we own any Beatles records", domain="records", limit=5) == []


def test_a_single_distinctive_term_still_matches(household):
    adapter = HouseholdReadOnlyAdapter(household)
    hits = adapter.search("Pastel", domain="records", limit=5)
    assert hits and "Pastel Blues" in hits[0]["snippet"]


def test_search_folds_case_plurals_and_verb_endings(household):
    adapter = HouseholdReadOnlyAdapter(household)
    assert adapter.search("RECORD condition needs cleaning", domain="records", limit=3)
    assert adapter.search("tomato", domain="food", limit=3)  # stored as "tomatoes"
    assert adapter.search("who is cleaning the bathroom", domain="cleaning", limit=3)  # stored as "bathroom clean"


# --- real facts that merely look like placeholders or pointers are kept ----------------------------------------------------


def test_a_real_todo_item_a_linked_fact_and_future_work_are_still_evidence(household):
    adapter = HouseholdReadOnlyAdapter(household)
    assert any("boiler leak" in hit["snippet"] for hit in adapter.search("boiler leak", domain="maintenance"))
    assert any("booked for 2026-10-20" in hit["snippet"] for hit in adapter.search("boiler service booked", domain="maintenance"))
    assert any("extractor fan" in hit["snippet"] for hit in adapter.search("broken extractor fan", domain="maintenance"))


def test_a_trailing_todo_comment_does_not_hide_the_value_it_follows(household):
    adapter = HouseholdReadOnlyAdapter(household)
    hits = adapter.search("tomatoes carton", domain="food", limit=5)
    assert any(hit["snippet"] == 'quantity: "1 carton"' for hit in hits)
