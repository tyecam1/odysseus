"""A grounded household answer must be evidence, not the nearest word match.

Found by the 2026-10-06 kiosk real-path test: a records question routed correctly to `jin` on the household-read-only path,
but the reply was an unrelated retrieved line ("future views over the YAML"). The line sat in a notes file about a view that
does not exist yet and matched on common words ("play", "tonight"); the handler returned the first hit with no relevance floor.

The fixture mirrors the shape of the real records domain (real entries, an `example: true` placeholder, a README, a pointer
file with "future views" prose, TODO placeholders) with synthetic content.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.misumi_routes import setup_misumi_routes
from services.memory.skills import SkillsManager
from src.misumi_household import HouseholdReadOnlyAdapter

COLLECTION_YAML = """# Record collection - single source of truth.
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
"""

COLLECTION_MD = """# Record collection

**Data lives in [`collection.yaml`](collection.yaml).** This file is the pointer plus future-facing notes.

- New arrival: add an entry to `collection.yaml`.
- What did we play: [`listening-log.md`](listening-log.md).
- Mood-based browsing and "what should I play tonight?" are future views over the YAML - see `agent-tasks/inbox/record-browsing-views.md`.

TODO: first shelf audit to populate `collection.yaml`.
"""

README_MD = """# Records

- `collection.yaml` - owned records
- `wantlist.md` - records you are hunting
Suggested editable moods: late night, sunny morning, focused, loud, relaxed.
"""

WANTLIST_MD = "# Wantlist\n\n- [ ] YYYY-MM-DD - artist - title (max price? where seen?)\n"
LISTENING_LOG_MD = "# Listening log\n\n| Date | Record(s) | Mood / occasion | Notes |\n|---|---|---|---|\n| _TODO_ | | | |\n"


@pytest.fixture()
def household(tmp_path: Path) -> Path:
    root = tmp_path / "household-repo"
    records = root / "household" / "records"
    records.mkdir(parents=True)
    (records / "collection.yaml").write_text(COLLECTION_YAML, encoding="utf-8")
    (records / "collection.md").write_text(COLLECTION_MD, encoding="utf-8")
    (records / "README.md").write_text(README_MD, encoding="utf-8")
    (records / "wantlist.md").write_text(WANTLIST_MD, encoding="utf-8")
    (records / "listening-log.md").write_text(LISTENING_LOG_MD, encoding="utf-8")
    food = root / "household" / "food"
    food.mkdir(parents=True)
    (food / "shopping-list.md").write_text("# Shopping list\n- [ ] miso\n", encoding="utf-8")
    return root


@pytest.fixture()
def client(household, tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(household))
    app = FastAPI()
    app.include_router(setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
    return TestClient(app)


def _ask(client, prompt):
    response = client.post("/misumi/respond", json={"prompt": prompt, "persona": "jin"})
    assert response.status_code == 200
    return response.json()


def _paths_and_lines(body):
    return [(item["path"], item["snippet"]) for item in body["sources"]]


# --- the reported defect, end to end through the respond route -------------------------------------------------------


def test_the_kiosk_recommendation_question_is_not_answered_with_a_note_about_a_future_view(client):
    body = _ask(client, "What should I play tonight?")
    assert body["source"] == "household-read-only"
    assert "future views" not in body["text"].lower()
    assert body["sources"] == []
    assert "no matching records fact" in body["text"].lower()


def test_no_good_result_is_an_explicit_grounded_failure(client):
    body = _ask(client, "Do we own any Beatles records?")
    assert body["source"] == "household-read-only"
    assert body["sources"] == []
    assert "no matching records fact" in body["text"].lower()
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
    snippets = " ".join(snippet for _, snippet in _paths_and_lines(body))
    assert len(body["sources"]) >= 2  # Kind of Blue and Waltz for Debby both carry the mood
    assert "EXAMPLE" not in snippets and "TODO" not in snippets and "YYYY" not in snippets
    assert {item["path"] for item in body["sources"]} == {"household/records/collection.yaml"}


def test_existing_grounded_lookup_still_works(client):
    body = _ask(client, "what is on the shopping list?")
    assert body["source"] == "household-read-only"
    assert "shopping-list.md" in body["sources"][0]["path"]


# --- the retrieval layer on its own ----------------------------------------------------------------------------------


def test_search_skips_notes_about_unbuilt_views_pointers_todos_and_placeholder_entries(household):
    adapter = HouseholdReadOnlyAdapter(household)
    for query in ("what should I play tonight", "record browsing views over the YAML", "first shelf audit", "wantlist title price"):
        text = " ".join(hit["snippet"] for hit in adapter.search(query, domain="records", limit=10))
        assert "future views" not in text and "TODO" not in text and "YYYY" not in text, query


def test_search_never_returns_a_demonstration_entry(household):
    adapter = HouseholdReadOnlyAdapter(household)
    hits = adapter.search("example record one needs cleaning demonstration", domain="records", limit=20)
    assert not [hit for hit in hits if "EXAMPLE" in hit["snippet"]]


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


def test_search_ignores_plural_and_case_when_matching(household):
    adapter = HouseholdReadOnlyAdapter(household)
    assert adapter.search("RECORD condition needs cleaning", domain="records", limit=3)
