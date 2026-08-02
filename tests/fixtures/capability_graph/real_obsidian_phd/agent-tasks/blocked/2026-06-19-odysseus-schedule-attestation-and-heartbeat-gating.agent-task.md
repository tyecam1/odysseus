---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-19-odysseus-schedule-attestation-and-heartbeat-gating
title: Add schedule attestation, stale-heartbeat self-refusal, allowlist drift check (P1)
status: blocked
blocked_reason: Runtime self-refusal remains in draft Odysseus PR 2 and is undeployed.
recheck_condition: PR 2 is reviewed, merged, deployed and the live service attestation passes.
priority: high
task_type: implementation
created_by: claude
created_at: 2026-06-19T00:00:00+01:00
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
allowed_paths:
  - automation/review/agent-tasks/review/2026-06-19-odysseus-schedule-attestation-and-heartbeat-gating.agent-task.md
  - automation/review/routine-reports/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/architecture/2026-06-19-odysseus-automatic-process-improvement-review.md
  - automation/review/routine-reports/agent-routine-migration-audit/2026-06-15.live-agent-routine-migration-audit.md
  - automation/review/routine-reports/odysseus-heartbeat/2026-06-15.heartbeat.json
  - automation/config/odysseus_actions.yaml
  - automation/config/settings.ini
outputs:
  - automation/review/routine-reports/odysseus-schedule-attestation/2026-06-22.odysseus-schedule-attestation.json
  - automation/review/routine-reports/odysseus-schedule-attestation/2026-06-22.odysseus-schedule-attestation.md
  - automation/review/routine-reports/odysseus-heartbeat/2026-06-22.heartbeat.json
  - Scripts/automation/odysseus_runtime.py
  - Scripts/automation/odysseus_heartbeat.py
result_path: automation/review/routine-reports/odysseus-schedule-attestation/2026-06-22.odysseus-schedule-attestation.json
review_report_path: automation/review/routine-reports/odysseus-runtime/2026-06-22-compute-box-runtime-attestation.md
handoff_model: codex
handoff_prompt_path: automation/review/agent-tasks/inbox/2026-06-19-odysseus-schedule-attestation-and-heartbeat-gating.agent-task.md
operator_decision_path: ""
linked_pr: "https://github.com/tyecam1/odysseus/pull/2"
supersedes: []
duplicates:
  - 2026-06-11-odysseus-conformance-heartbeat
  - 2026-06-12-odysseus-heartbeat-writer
  - 2026-06-12-odysseus-central-interface-registry
notes: "Completed vault-side implementation and live compute-box attestation on 2026-06-22. The 19-task snapshot is sanitized, drift-capable and zombie-aware; the fresh heartbeat matches the allowlist and now fails if a disabled action is claimed enabled. Cowork is explicitly unavailable. Runtime self-refusal is implemented and tested in draft PR #2 but remains undeployed pending human review."
completed_at: 2026-06-22T19:00:00+01:00
completed_by: codex_subscription
verification_verdict: pending-human-review
verification_by: codex
---

# Schedule attestation, stale-heartbeat self-refusal, allowlist drift check (P1)

## Completion

The initial attestation baseline and fresh heartbeat are committed review artifacts. Vault-side gates are active in validation; service-side refusal remains a draft deployment change.

## Source

Review `…/2026-06-19-odysseus-automatic-process-improvement-review.md` findings P1 (shadow state; heartbeat staleness not self-enforcing; action allowlist is contract-only and can drift). The latest committed heartbeat (2026-06-15) is already stale against `heartbeat_cycle_minutes 1440 + grace 360`.

## Scope (implement on a branch; PR for human merge)

1. **Schedule-attestation export** (read-only): dump (a) the Odysseus `ScheduledTask` table, (b) heartbeat `enabled_actions`, (c) the Cowork schedule list into one dated committed artifact under `automation/review/routine-reports/`. Diff successive exports to surface drift. Repo becomes source of truth.
2. **Stale-heartbeat self-refusal**: the action/runtime layer must auto-refuse actuation when the heartbeat is stale (cycle+grace breached), independent of the manual R3 gate. Surface heartbeat age in `odysseus-interface-health`.
3. **Allowlist-vs-enabled drift check**: assert heartbeat `enabled_actions` ⊆ allowlist-enabled in `odysseus_actions.yaml`; flag any mismatch with a failing exit under `--require-pass`.

## Guardrails

- Vault write-scope is review-side only (allowed_paths). Code changes are branch + draft-PR deliverables.
- Read-only export and fail-closed checks only; do not enable any disabled write action. No autonomous merge.

## Capability truth (mandatory, in the PR)

Update `current-capabilities.md` + `capability_manifest.json`; run `python -m unittest Scripts.automation.tests.test_capability_truth_contracts`.

## Acceptance criteria

- Attestation export produces a committed dated artifact and a drift diff; tests cover it.
- Actuation refuses on stale heartbeat (stale fixture test); interface-health reports heartbeat age.
- Drift check flags allowlist/enabled mismatch with failing exit under `--require-pass`.
- Capability docs updated; truth tests pass. No write action enabled. No canonical/Zotero mutation.
