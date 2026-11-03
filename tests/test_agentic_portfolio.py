"""Combined frontier must respect all three owners, source roots and stage boundaries."""
import sys
import argparse
import json
import subprocess
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

def test_lab_ssh_fallback_uses_registered_transport_without_local_clone(tmp_path, monkeypatch):
    ody, _, _ = estate(tmp_path, monkeypatch)
    monkeypatch.delenv("PHD_ROOT")
    monkeypatch.setenv("AOTERU_LAB_SSH_TARGET", "lab-worker")
    monkeypatch.setenv("AOTERU_LAB_REPO_ROOT", "/registered/lab/odysseus")
    observed = {}
    def fake_run(cmd, **kwargs):
        observed["cmd"] = cmd
        remote = {"stage": "L0-three-repository-frontier", "scope_complete": True,
                  "records": [], "counts": {}, "unavailable": {}}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(remote), "")
    monkeypatch.setattr(ap, "_ssh_run", fake_run)
    args = argparse.Namespace(stage="frontier", ref=None, tier="contract",
                              max_tokens=2500, offset=0, per_repo=4)
    result = ap.lab_frontier_over_ssh(args)
    assert result["scope_complete"] and result["transport"] == "registered_lab_ssh"
    assert observed["cmd"][:3] == ["ssh", "-n", "-T"]
    assert "BatchMode=yes" in observed["cmd"]
    assert "StrictHostKeyChecking=yes" in observed["cmd"]
    assert "--local-only" in observed["cmd"][-1]


def test_lab_ssh_failure_is_not_reported_as_complete(monkeypatch):
    monkeypatch.setenv("AOTERU_LAB_SSH_TARGET", "lab-worker")
    monkeypatch.setenv("AOTERU_LAB_REPO_ROOT", "/registered/lab/odysseus")
    def denied(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 255, "", "host key verification failed")
    monkeypatch.setattr(ap, "_ssh_run", denied)
    args = argparse.Namespace(stage="frontier", ref=None, tier="contract",
                              max_tokens=2500, offset=0, per_repo=4)
    with pytest.raises(ValueError, match="lab_ssh_execution_failed"):
        ap.lab_frontier_over_ssh(args)


def test_no_ssh_config_returns_none(monkeypatch):
    monkeypatch.delenv("AOTERU_LAB_SSH_TARGET", raising=False)
    monkeypatch.delenv("AOTERU_LAB_REPO_ROOT", raising=False)
    args = argparse.Namespace(stage="frontier", ref=None, tier="contract",
                              max_tokens=2500, offset=0, per_repo=4)
    assert ap.lab_frontier_over_ssh(args) is None


# --- Review round 1 (independent Sol review, 2026-11-02): portfolio regressions ---

def test_budget_is_shared_fairly_when_an_early_owner_has_large_records(tmp_path, monkeypatch):
    ody, _, _ = estate(tmp_path, monkeypatch)
    for i in range(15):
        make_card(ody, f"automation/review/agent-tasks/ready/big{i}.md", "B" * 700 + str(i), raw_status="ready")
    roots, missing = ap.resolve_roots(ody, {})
    result = ap.frontier(roots, missing, 0, 4, 900)
    assert {r["repo_id"] for r in result["records"]} == set(roots)
    assert len(json.dumps(result, ensure_ascii=False)) <= 900 * 3


def test_task_read_does_not_need_ssh_when_its_own_repo_is_available(tmp_path, monkeypatch, capsys):
    ody, _, _ = estate(tmp_path, monkeypatch)
    monkeypatch.delenv("PHD_ROOT")  # an unrelated sibling is missing
    monkeypatch.setenv("AOTERU_LAB_SSH_TARGET", "lab-worker")
    monkeypatch.setenv("AOTERU_LAB_REPO_ROOT", "/registered/lab/odysseus")

    def boom(*a, **k):
        raise AssertionError("ssh must not be attempted for an available local task")
    monkeypatch.setattr(ap, "_ssh_run", boom)
    monkeypatch.setattr(sys, "argv", ["agentic_portfolio.py", "task", "--repo-root", str(ody),
                                      "--ref", "odysseus:ready/o.md"])
    assert ap.main() == 0
    assert json.loads(capsys.readouterr().out)["ref"] == "odysseus:ready/o.md"


@pytest.mark.parametrize("remote,reason", [
    ({"stage": "L3-explicit-full-task", "ref": "x", "metadata": {}, "body": "FULL"}, "unexpected"),
    ({"stage": "L0-three-repository-frontier", "records": "nope", "scope_complete": True}, "malformed"),
    ({"stage": "L0-three-repository-frontier", "records": [], "scope_complete": "yes"}, "malformed"),
    ({"stage": "L0-three-repository-frontier", "records": [{}] * 50, "scope_complete": True}, "malformed"),
    ({"stage": "L0-three-repository-frontier", "records": [], "scope_complete": True, "counts": {}, "unavailable": {}, "pad": "x" * 20000},
     "oversized|exceeds_budget"),
])
def test_malformed_or_overlarge_remote_frontier_is_rejected(monkeypatch, remote, reason):
    monkeypatch.setenv("AOTERU_LAB_SSH_TARGET", "lab-worker")
    monkeypatch.setenv("AOTERU_LAB_REPO_ROOT", "/registered/lab/odysseus")
    monkeypatch.setattr(ap, "_ssh_run",
                        lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, json.dumps(remote), ""))
    args = argparse.Namespace(stage="frontier", ref=None, tier="contract", max_tokens=2500, offset=0, per_repo=4)
    with pytest.raises(ValueError, match=reason):
        ap.lab_frontier_over_ssh(args)


@pytest.mark.parametrize("remote", [
    {"stage": "L3-explicit-full-task", "ref": "misumi:inbox/m.md", "metadata": {}, "body": "FULL"},  # tier mismatch
    {"stage": "L1-selected-contract", "ref": "misumi:inbox/other.md", "metadata": {}, "body": "x"},  # wrong task
    {"stage": "L1-selected-contract", "ref": "misumi:inbox/m.md", "metadata": [], "body": "x"},
])
def test_remote_task_answer_must_match_the_request(monkeypatch, remote):
    monkeypatch.setenv("AOTERU_LAB_SSH_TARGET", "lab-worker")
    monkeypatch.setenv("AOTERU_LAB_REPO_ROOT", "/registered/lab/odysseus")
    monkeypatch.setattr(ap, "_ssh_run",
                        lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, json.dumps(remote), ""))
    args = argparse.Namespace(stage="task", ref="misumi:inbox/m.md", tier="contract",
                              max_tokens=2500, offset=0, per_repo=4)
    with pytest.raises(ValueError, match="lab_ssh_"):
        ap.lab_frontier_over_ssh(args)


def test_selected_task_budget_counts_serialised_size(tmp_path, monkeypatch):
    ody, misumi, _ = estate(tmp_path, monkeypatch)
    path = misumi / "agent-tasks" / "inbox" / "esc.md"
    path.write_text("---\ntitle: esc\nstatus: open\n---\n" + '"\\\n\x01' * 5000, encoding="utf-8")
    roots, _ = ap.resolve_roots(ody, {})
    result = ap.selected(roots, "misumi:inbox/esc.md", "contract", 500)
    assert len(json.dumps(result, ensure_ascii=False)) <= 500 * 3


def test_symlinked_card_or_bucket_cannot_be_selected(tmp_path, monkeypatch):
    ody, misumi, _ = estate(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.md").write_text("---\ntitle: EXTERNAL\n---\nEXTERNAL_BODY\n", encoding="utf-8")
    try:
        (misumi / "agent-tasks" / "codex").symlink_to(outside, target_is_directory=True)
        (misumi / "agent-tasks" / "inbox" / "link.md").symlink_to(outside / "x.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    roots, _ = ap.resolve_roots(ody, {})
    for ref in ("misumi:codex/x.md", "misumi:inbox/link.md"):
        with pytest.raises(ValueError):
            ap.selected(roots, ref, "full", 2000)


def test_date_valued_title_does_not_break_the_portfolio(tmp_path, monkeypatch):
    import datetime
    ody, misumi, _ = estate(tmp_path, monkeypatch)
    (misumi / "agent-tasks" / "inbox" / "d.md").write_text(
        "---\n" + yaml.safe_dump({"title": datetime.date(2026, 11, 2), "status": "open"}) + "---\nbody\n",
        encoding="utf-8")
    roots, missing = ap.resolve_roots(ody, {})
    result = ap.frontier(roots, missing, 0, 4, 2600)
    json.dumps(result)
    assert any(r.get("title") == "2026-11-02" for r in result["records"])


GOOD_RECORD = {"ref": "misumi:inbox/m.md", "repo_id": "misumi", "bucket": "inbox", "title": "t", "eligible": "unverified"}


def _remote_frontier(records, **extra):
    base = {"stage": "L0-three-repository-frontier", "scope_complete": True,
            "counts": {}, "unavailable": {}, "records": records}
    base.update(extra)
    return base


def _ask_remote(monkeypatch, remote):
    monkeypatch.setenv("AOTERU_LAB_SSH_TARGET", "lab-worker")
    monkeypatch.setenv("AOTERU_LAB_REPO_ROOT", "/registered/lab/odysseus")
    monkeypatch.setattr(ap, "_ssh_run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, json.dumps(remote), ""))
    args = argparse.Namespace(stage="frontier", ref=None, tier="contract", max_tokens=2500, offset=0, per_repo=4)
    return ap.lab_frontier_over_ssh(args)


def test_valid_remote_frontier_is_accepted(monkeypatch):
    assert _ask_remote(monkeypatch, _remote_frontier([GOOD_RECORD]))["transport"] == "registered_lab_ssh"


@pytest.mark.parametrize("bad", [
    None, "string", [], {**GOOD_RECORD, "body": "FULL TASK BODY"}, {**GOOD_RECORD, "repo_id": "evil"},
    {**GOOD_RECORD, "bucket": "../escape"}, {**GOOD_RECORD, "ref": "misumi:inbox/sub/m.md"},
    {**GOOD_RECORD, "ref": "obsidian-phd:inbox/m.md"}, {**GOOD_RECORD, "ref": "misumi:done/m.md"},
    {**GOOD_RECORD, "title": {"a": {"b": {"c": {"d": 1}}}}},
])
def test_remote_frontier_records_are_validated_individually(monkeypatch, bad):
    with pytest.raises(ValueError, match="malformed"):
        _ask_remote(monkeypatch, _remote_frontier([GOOD_RECORD, bad]))


@pytest.mark.parametrize("missing", ["counts", "unavailable"])
def test_remote_frontier_requires_its_envelope_fields(monkeypatch, missing):
    remote = _remote_frontier([GOOD_RECORD])
    del remote[missing]
    with pytest.raises(ValueError, match="malformed"):
        _ask_remote(monkeypatch, remote)


def test_ssh_error_warning_is_inside_the_budgeted_envelope(tmp_path, monkeypatch):
    ody, _, _ = estate(tmp_path, monkeypatch)
    for i in range(6):
        make_card(ody, f"automation/review/agent-tasks/ready/w{i}.md", "W" * 400 + str(i), raw_status="ready")
    roots, missing = ap.resolve_roots(ody, {})
    for budget in (700, 900, 1200, 2600):
        try:
            result = ap.frontier(roots, missing, 0, 4, budget, transport_warning="lab_ssh_transport_failure: " + "E" * 400)
        except ValueError as exc:
            assert "budget" in str(exc)
            continue
        assert len(json.dumps(result, ensure_ascii=False)) <= budget * 3
        assert result["scope_complete"] is False and result["warnings"][-1].startswith("lab_ssh_transport_failure")


def test_pagination_is_budgeted_before_it_is_filled(tmp_path, monkeypatch):
    ody, _, _ = estate(tmp_path, monkeypatch)
    for i in range(30):
        make_card(ody, f"automation/review/agent-tasks/ready/p{i:02d}.md", "P" * 90 + str(i), raw_status="ready")
    roots, missing = ap.resolve_roots(ody, {})
    for budget in range(500, 1100, 7):
        try:
            result = ap.frontier(roots, missing, 0, 6, budget)
        except ValueError as exc:
            assert "budget" in str(exc)
            continue
        assert len(json.dumps(result, ensure_ascii=False)) <= budget * 3, budget


def test_ssh_runner_stops_a_flooding_remote_instead_of_buffering_it():
    import sys
    flood = [sys.executable, "-c", "import sys\nwhile True: sys.stdout.write('x' * 65536)"]
    with pytest.raises(ValueError, match="lab_ssh_output_exceeded"):
        ap._ssh_run(flood, timeout=20, max_out=200_000, max_err=4096)
    noisy_err = [sys.executable, "-c", "import sys\nwhile True: sys.stderr.write('e' * 65536)"]
    with pytest.raises(ValueError, match="lab_ssh_output_exceeded"):
        ap._ssh_run(noisy_err, timeout=20, max_out=200_000, max_err=4096)


def test_ssh_runner_returns_normal_output_and_enforces_timeout():
    import sys
    done = ap._ssh_run([sys.executable, "-c", "print('ok')"], timeout=20, max_out=1000, max_err=1000)
    assert done.returncode == 0 and done.stdout.strip() == "ok"
    with pytest.raises(subprocess.TimeoutExpired):
        ap._ssh_run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1, max_out=1000, max_err=1000)
