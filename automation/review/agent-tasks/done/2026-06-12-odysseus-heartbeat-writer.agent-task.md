---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-odysseus-heartbeat-writer
title: Implement Odysseus-side heartbeat writer for the #351 contract (R2)
status: done
priority: high
task_type: implementation
created_by: claude_subscription
created_at: 2026-06-11T23:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/odysseus-heartbeat/**
  - automation/review/agent-tasks/**/2026-06-12-odysseus-heartbeat-writer.agent-task.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - Scripts/automation/odysseus_heartbeat.py
  - automation/config/odysseus_actions.yaml
  - automation/docs/odysseus-action-integrations.md
  - automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/integration-repair-plan.md
outputs:
  - automation/review/routine-reports/odysseus-heartbeat/<date>.heartbeat.json
result_path: ""
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: "tyecam1/odysseus#1"
supersedes: []
duplicates: []
notes: "R2 from the approved context-parity decision packet. Writer code lives in the operator's Odysseus deployment fork (tyecam1/odysseus, draft PR #1; upstream pewdiepie-archdaemon#4032 closed - external repo cannot gate deployment). Vault-side contract and validator merged in PR #351; runner hook merged in #358. 2026-06-12 claim: executed by claude lane (operator approved deviation from codex routing in-session). DEPLOYED AND LIVE 2026-06-12 ~10:12 BST: writer snapshot at ~/.local/share/drm-remote-upkeep/vault_heartbeat.py, full write-enabled runner cycle produced 2026-06-12.heartbeat.json (allowlist_hash_match true, service_version 0.9.1, validate + 32 truth tests passed in-cycle), pushed and staged in draft PR #359. Stuck-dirty upkeep checkout (failed cycles 06-11/06-12 05:17) was unstuck first; stale HF-draft dirt preserved at box ~/box-salvage-20260612 (all content confirmed superseded by main). Acceptance met pending V2: operator confirms the clean heartbeat, then R3 stage-2 flag flip proceeds as its own PR. OPEN_PR stays false on the box until gh is installed; PRs for pushed upkeep branches are opened laptop-side."
---

# Task: Odysseus-side heartbeat writer (R2)

Implement, in the Odysseus repo, the writer half of the heartbeat contract merged in #351:

- One dated `automation/review/routine-reports/odysseus-heartbeat/<date>.heartbeat.json` per scheduled cycle, carrying `service_version`, `actions_yaml_sha256` (SHA-256 over LF-normalised UTF-8 of the loaded `odysseus_actions.yaml` — mind CRLF checkouts), `enabled_actions`, `last_dispatch`, `generated_at`.
- Written through the existing review-side staging path; no new endpoint, no secrets in payloads.
- Cycle/grace defaults per `[odysseus]` settings (1440/360 min).

## Acceptance

`python -m Scripts.automation validate` reports the live heartbeat clean (no missing/stale/invalid/hash-mismatch warnings) for at least one real scheduled cycle. This is the gate for stage-2 enablement (R3, design §9 PR-B): **do not flip `task-transition` or `routine-report-stage` to enabled in this task.**

## Stop condition

Stop when one live heartbeat validates clean and the Odysseus-repo PR is linked here. Verification: V2 — operator confirms the clean validator run before R3 proceeds.

## Close-out

Writer half deployed and live 2026-06-12; one live heartbeat validated clean. Vault-side staging hook merged via PR #358 (commit `145d064a`) and live close-out via PR #359/#360 (commit `c979f27b`/`eda2e7c4`); the writer code lives in the operator's Odysseus fork (`tyecam1/odysseus#1`). Live deliverable `automation/review/routine-reports/odysseus-heartbeat/2026-06-12.heartbeat.json` confirmed present on `origin/main`. Status moved review -> done 2026-06-15. The R3 stage-2 flag flip (`task-transition`/`routine-report-stage`) is explicitly NOT part of this close-out and remains a separate human-gated PR.
