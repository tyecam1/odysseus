---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-19-odysseus-remote-compute-dispatch-guard
title: Add remote-compute dispatch guard, odysseus doctor, per-job liveness (P2)
status: blocked
blocked_reason: Odysseus draft PR 2 was closed without merging (verified 2026-10-03); the doctor and liveness remainder has no implementation and no owner.
recheck_condition: re-scope against the Stage 5 and 6 worker, health and routing contracts, then decide whether a doctor command and liveness window are still wanted.
priority: medium
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
repo: tyecam1/odysseus
migrated_from_repo: tyecam1/obsidian-PhD
migration_note: "Ownership migrated to Odysseus. Treat references to obsidian-PhD automation paths as historical inputs until capability-path convergence is complete."
branch: ""
allowed_paths:
  - automation/review/agent-tasks/review/2026-06-19-odysseus-remote-compute-dispatch-guard.agent-task.md
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
  - automation/config/odysseus_actions.yaml
  - automation/config/settings.ini
outputs:
  - Scripts/automation/** (dispatch guard + odysseus doctor + liveness)
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
result_path: automation/review/routine-reports/odysseus-runtime/2026-06-22-compute-box-runtime-attestation.md
review_report_path: automation/review/routine-reports/odysseus-runtime/2026-06-22-compute-box-runtime-attestation.md
handoff_model: codex
handoff_prompt_path: automation/review/agent-tasks/inbox/2026-06-19-odysseus-remote-compute-dispatch-guard.agent-task.md
operator_decision_path: ""
linked_pr: "https://github.com/tyecam1/odysseus/pull/2"
supersedes: []
duplicates:
  - 2026-06-10-elongate-odysseus-timeouts
  - 2026-06-11-fm1-endpoint-attestation
  - 2026-06-12-context-parity-diagnostics
notes: "Implemented odysseus-doctor and a fail-closed pre-dispatch route check in the vault. It reports tunnel, endpoint, heartbeat, schedule and Git state and refuses remote/model tasks when prerequisites are absent. Draft Odysseus PR #2 adds five-minute liveness and a one-hour model/research timeout; 12 focused tests pass on the compute box. No runtime deployment or restart was performed."
completed_at: 2026-06-22T19:00:00+01:00
completed_by: codex_subscription
verification_verdict: pending-human-review
verification_by: codex
---

# Remote-compute dispatch guard, odysseus doctor, per-job liveness (P2)

## Completion

The vault now provides the one-shot diagnostic and route gate. The external runtime change is staged as a draft PR for human deployment review.

## Source

Review `…/2026-06-19-odysseus-automatic-process-improvement-review.md` finding **P2**. This session a `requires_remote_compute` task dead-ended in a tunnel-less sandbox (`127.0.0.1:11434` refused). Also: `agent_job_timeout_seconds = 14400` gives a 4h blind window.

## Scope (implement)

1. **Dispatch routing guard**: the dispatcher must refuse to route `requires_remote_compute: true` / `requires_local_model: true` tasks to any executor that is not the tunnel/compute-box host, returning a clear "route to compute-box host" message instead of an exit-1 model failure. Optionally add a deferred/queued mode that parks such a task for the box runner.
2. **`odysseus doctor`**: one-shot status command reporting tunnel, endpoint reachability, heartbeat age, schedule-attestation freshness, and git-clean state in a single output.
3. **Per-job liveness**: emit a progress heartbeat every N minutes during long model jobs and shorten the blind reclaim window so a hung job is reclaimed before 4h.

## Guardrails

- Diagnostics and routing logic only; do not enable any disabled write action; no autonomous merge (branch + draft PR).

## Capability truth (mandatory)

Update `current-capabilities.md` + `capability_manifest.json`; run `python -m unittest Scripts.automation.tests.test_capability_truth_contracts`.

## Acceptance criteria

- Routing guard refuses misrouted remote-compute tasks with a clear message; covered by tests.
- `odysseus doctor` returns tunnel/endpoint/heartbeat/schedule/git status in one call.
- Per-job liveness ping implemented; blind window reduced; tested.
- Capability docs updated; truth tests pass. No canonical/Zotero mutation.

## Programme disposition (2026-10-03, convergence Phase 9 reconciliation)

**State: stale blocker, superseded in part; the remainder is optional and unowned**

Re-grounded against `dev` on 2026-10-03. The recorded unblock condition can never occur: draft Odysseus PR #2 ("gate DRM jobs and emit liveness") was **closed without merging**.
The intent of scope item 1 (refuse misrouted `requires_remote_compute` / `requires_local_model` work with a clear reason instead of an executor failure) is met on `dev` by the estate router: `resolve_alias`
withholds a host with a named reason (not benchmark-qualified, GPU busy, unverified), never falls back silently and never executes on the control-plane host. Scope items 2 and 3 (an `odysseus doctor` command and per-job
liveness pings with a shorter reclaim window) have **no implementation on `dev`**; worker `health`, `aoteru status` and `aoteru execution --wait` cover part of the diagnostic need but not the liveness window. This card's inputs
are obsidian-PhD automation paths. Decision: keep `blocked`, with the blocked reason corrected below; re-scope against the Stage 5 and 6 worker and health contracts before any work. It is not named in the convergence programme's closeout bullets, none of which depends on it, so it does not block closeout. No work in this programme is attributed to it. It stays where it is, with the Odysseus queue as owner.
