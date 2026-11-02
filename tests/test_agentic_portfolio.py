"""Combined frontier must respect all three owners, source roots and stage boundaries."""
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agentic_portfolio as ap  # noqa: E402


def make_card(root, rel, title, priority="high", raw_status="open"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump({
        "title": title,
        "priority": priority,
        "status": raw_status,
        "owner_target": "sonnet" if "misumi" in str(rel) else None,
    }) + "---\n# " + title + "\nSECRET_BODY_NOT_ALLOWED_IN_DISCOVERY\n", encoding="utf-8")
    return path


def estate(tmp_path, monkeypatch):
    ody = tmp_path / "odysseus"
    misumi = tmp_path / "misumi"
    phd = tmp_path / "obsidian-PhD"
    for path in (ody, misumi, phd):
        path.mkdir()
        (path / ".git").mkdir()
    (ody / "config").mkdir()
    template_m = "$" + "{HOUSEHOLD_ROOT}/misumi"
    template_p = "$" + "{PHD_ROOT}/obsidian-PhD"
    (ody / "config" / "repositories.yaml").write_text(yaml.safe_dump({
        "repos": [
            {"id": "odysseus", "root_var": "AI_ROOT", "path": "dummy"},
            {"id": "misumi", "root_var": "HOUSEHOLD_ROOT", "path": template_m},
            {"id": "obsidian-phd", "root_var": "PHD_ROOT", "path": template_p}
        ]
    }), encoding="utf-8")
    monkeypatch.setenv("HOUSEHOLD_ROOT", str(tmp_path))
    monkeypatch.setenv("PHD_ROOT", str(tmp_path))
    make_card(ody, "automation/review/agent-tasks/ready/o.md", "Odysseus work", raw_status="ready")
    make_card(misumi, "agent-tasks/inbox/m.md", "Misumi work")
    make_card(phd, "automation/review/agent-tasks/ready/p.md", "PhD work", raw_status="ready")
    return ody, misumi, phd


def test_all_three_queue_owners_visible_without_body(tmp_path, monkeypatch):
    ody, _, _ = estate(tmp_path, monkeypatch)
    roots, missing = ap.resolve_roots(ody, {})
    assert set(roots) == {"odysseus", "misumi", "obsidian-phd"}
    assert missing == {}
    result = ap.frontier(roots, missing, 0, 4, 2600)
    assert result["scope_complete"] is True
    assert len(result["records"]) == 3
    assert {r["repo_id"] for r in result["records"]} == set(roots)
    assert all(r["eligible"] == "unverified" for r in result["records"])
    assert "SECRET_BODY_NOT_ALLOWED_IN_DISCOVERY" not in str(result)
    assert "inbox" in {r["bucket"] for r in result["records"]}


def test_unavailable_repo_is_explicit_not_silently_ranked(tmp_path, monkeypatch):
    ody, _, _ = estate(tmp_path, monkeypatch)
    monkeypatch.delenv("PHD_ROOT")
    roots, missing = ap.resolve_roots(ody, {})
    result = ap.frontier(roots, missing, 0, 4, 2600)
    assert result["scope_complete"] is False
    assert result["unavailable"]["obsidian-phd"] == "root_environment_unset"
    assert not any(r["repo_id"] == "obsidian-phd" for r in result["records"])


def test_misumi_open_task_only_selected_by_exact_repo_ref(tmp_path, monkeypatch):
    ody, _, _ = estate(tmp_path, monkeypatch)
    roots, missing = ap.resolve_roots(ody, {})
    ref = "misumi:inbox/m.md"
    record = ap.selected(roots, ref, "contract", 1200)
    assert record["ref"] == ref
    assert record["metadata"]["title"] == "Misumi work"
    assert "SECRET_BODY_NOT_ALLOWED_IN_DISCOVERY" in record["body"]
    assert "unverified" in str(ap.frontier(roots, missing, 0, 4, 2600))
    for invalid in ("misumi:inbox/../m.md", "obsidian-phd:../../m.md",
                    "bogus:inbox/m.md", "misumi:done/m.md"):
        with pytest.raises((ValueError, OSError)):
            ap.selected(roots, invalid, "contract", 1200)


def test_per_repo_sampling_prevents_large_queue_domination(tmp_path, monkeypatch):
    ody, _, _ = estate(tmp_path, monkeypatch)
    for i in range(15):
        make_card(ody, f"automation/review/agent-tasks/ready/o{i}.md",
                  f"Backend-{i}", raw_status="ready")
    roots, missing = ap.resolve_roots(ody, {})
    result = ap.frontier(roots, missing, 0, 1, 2600)
    assert {r["repo_id"] for r in result["records"]} == set(roots)
    assert len([r for r in result["records"] if r["repo_id"] == "odysseus"]) == 1
    assert result["next_offset_per_repo"]["odysseus"] == 1


def test_symlinked_bucket_is_refused(tmp_path, monkeypatch):
    ody, misumi, phd = estate(tmp_path, monkeypatch)
    target = misumi / "agent-tasks" / "inbox"
    link = misumi / "agent-tasks" / "codex"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    rows, _, warnings = ap.collect("misumi", misumi)
    assert len(rows) == 1
    assert "misumi:codex:bucket_escape_refused" in warnings
