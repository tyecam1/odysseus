from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.misumi_routes import setup_misumi_routes
from services.memory.oss_skill_ingestion import OSSSkillIngestion
from services.memory.skill_importer import ResolvedSource
from services.memory.skills import SkillsManager


COMMIT = "a" * 40
PINNED_URL = f"https://github.com/example/safe-skills/tree/{COMMIT}/planner"


def _body(url: str = PINNED_URL) -> dict[str, object]:
    return {
        "url": url,
        "candidate_id": "safe-planner",
        "gap_id": "gap.meal-planning",
        "capability_ids": ["household.recipe.plan"],
        "license_spdx": "MIT",
        "dependencies": [],
        "maintenance_evidence": "Pinned source reviewed by the operator.",
    }


def _client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    manager = SkillsManager(str(tmp_path / "data"))
    ingestion = OSSSkillIngestion(tmp_path / "data" / "oss-skill-intake")
    app = FastAPI()
    app.include_router(setup_misumi_routes(manager, oss_skill_ingestion=ingestion))
    return TestClient(app), manager, ingestion


def test_mutable_import_is_retired_and_quarantine_requires_full_commit(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)
    assert client.post("/misumi/skills/import-draft", json={"url": PINNED_URL}).status_code == 410
    response = client.post(
        "/misumi/skills/quarantine",
        json=_body("https://github.com/example/safe-skills/tree/main/planner"),
    )
    assert response.status_code == 400
    assert "40-character Git commit" in response.json()["detail"]


def test_admin_can_quarantine_review_and_promote_prompt_only_pinned_bundle(
    tmp_path,
    monkeypatch,
):
    from services.memory import skill_importer

    client, manager, _ = _client(tmp_path, monkeypatch)
    source = ResolvedSource(owner="example", repo="safe-skills", ref=COMMIT, path="planner")
    files = {
        "SKILL.md": "---\nname: safe-planner\ndescription: Plan safely.\n---\n\nAsk before assuming.\n",
        "references/schema.yaml": "version: 1\n",
        "LICENSE": "MIT License\n",
    }
    monkeypatch.setattr(skill_importer, "parse_skill_source", lambda _url: source)
    monkeypatch.setattr(skill_importer, "fetch_skill_bundle", lambda _url: (files, source))

    staged = client.post("/misumi/skills/quarantine", json=_body())
    assert staged.status_code == 200
    staged_body = staged.json()
    assert staged_body["status"] == "quarantined"
    assert staged_body["candidate_code_executed"] is False
    assert staged_body["publication_changed"] is False
    intake_id = staged_body["manifest"]["intake_id"]

    review = client.get(f"/misumi/skills/quarantine/{intake_id}")
    assert review.status_code == 200
    assert review.json()["review"]["policy_result"] == "eligible-for-explicit-approval"

    promoted = client.post(
        f"/misumi/skills/quarantine/{intake_id}/promote",
        json={"reason": "Reviewed pinned prompt-only bundle and licence."},
    )
    assert promoted.status_code == 200
    assert promoted.json()["status"] == "active"
    assert promoted.json()["candidate_code_executed"] is False

    active = client.get("/misumi/skills/safe-planner/active")
    assert active.status_code == 200
    assert active.json()["file_paths"] == ["LICENSE", "SKILL.md", "references/schema.yaml"]
    projected = [row for row in manager.load(owner="local-admin") if row["name"] == "oss-safe-planner"]
    assert len(projected) == 1
    assert projected[0]["status"] == "published"
