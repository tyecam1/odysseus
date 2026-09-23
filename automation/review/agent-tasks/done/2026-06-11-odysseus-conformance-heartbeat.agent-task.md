---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-odysseus-conformance-heartbeat
title: Odysseus conformance heartbeat consumed by research-engine-health
status: done
priority: high
task_type: implementation
created_by: claude-system-review
created_at: 2026-06-11T14:59:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths: []
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/routine-reports/system-design-review/2026-06-11-odysseus-research-engine-review.md
  - automation/config/odysseus_actions.yaml
  - automation/docs/odysseus-action-integrations.md
outputs: []
result_path: ""
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/351"
supersedes: []
duplicates: []
notes: "Addresses review finding F2. Sequencing constraint: stage-2 write enablement (PR-B in agent-ecosystem-centralisation-design.md) must not proceed before this lands and a live heartbeat is observed."
claimed_by: claude_subscription
claimed_at: 2026-06-11T16:54:50+01:00
---

# Task: Odysseus conformance heartbeat

## Objective

Make Odysseus conformance verifiable from the governed repo. Vault-side (this repo, via draft PR):

1. Define the heartbeat artifact contract: one dated JSON per scheduled cycle at `automation/review/routine-reports/odysseus-heartbeat/<date>.heartbeat.json` containing service version, SHA-256 of the `odysseus_actions.yaml` it loaded, enabled-action list, last-dispatch summary, and timestamp.
2. Validator/schema check for the heartbeat payload (fail closed on missing hash or unknown enabled actions).
3. `research-engine-health` gains warnings: heartbeat missing, stale (> configured cycle + grace), or allowlist-hash mismatch against the committed `odysseus_actions.yaml`.

Odysseus-repo side (separate repo `pewdiepie-archdaemon/odysseus`, linked work, not in this repo's scope): scheduler loads the allowlist, refuses actions outside it, writes the heartbeat through the existing review-side staging path.

## Constraints

Read-only on this repo's side beyond the schema/health changes; no new endpoint; heartbeat is a file artifact, not an API; no secrets in payloads. Capability docs updated in the same PR.

## Acceptance criteria

Health report warns correctly in all three failure modes (unit-tested with fixture heartbeats); contract documented; a live heartbeat from the box validates clean before stage-2 enablement is considered.

## Follow-up (Odysseus-repo side, out of scope here)

Vault side delivered 2026-06-11 (claude_subscription): contract + fail-closed validator check (`Scripts/automation/odysseus_heartbeat.py`), health warnings, `[odysseus]` staleness config, fixture-tested. Remaining work lives in `pewdiepie-archdaemon/odysseus` and needs its own task: scheduler loads `odysseus_actions.yaml`, refuses actions outside it, and stages one dated heartbeat per cycle conforming to the contract in `automation/docs/odysseus-action-integrations.md` (hash = SHA-256 over LF-normalised UTF-8 of the loaded allowlist). Until that lands and one live heartbeat validates clean, research-engine-health warns `odysseus-heartbeat-missing` and stage-2 write enablement stays blocked.

## Close-out

Vault-side deliverable merged on `main` via PR #351 (commit `0d39ec40`, `health: Odysseus conformance heartbeat - contract, validator, health warnings`). `Scripts/automation/odysseus_heartbeat.py` confirmed present on `origin/main`. The Odysseus-repo writer half is the separate task `2026-06-12-odysseus-heartbeat-writer` (live heartbeat observed; closed in the same sweep). Status moved review -> done 2026-06-15.
