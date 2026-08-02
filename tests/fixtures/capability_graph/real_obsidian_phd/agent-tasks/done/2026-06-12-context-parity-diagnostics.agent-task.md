---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-context-parity-diagnostics
title: Resolve the three context-parity unknowns (box checkout, ChromaDB, writer readiness)
status: done
priority: medium
task_type: diagnostics
created_by: claude_subscription
created_at: 2026-06-11T23:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V1_LLM_VERIFIED
risk_level: low
approval_required: false
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/agent-jobs/2026-06-12-context-parity-diagnostics.codex/**
  - automation/review/agent-tasks/**/2026-06-12-context-parity-diagnostics.agent-task.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/memory-context-audit.md
  - automation/docs/compute-box-pristine-and-work-clones.md
  - automation/docs/remote-upkeep-compute-box.md
outputs:
  - automation/review/agent-jobs/2026-06-12-context-parity-diagnostics.codex/diagnostics-report.md
result_path: automation/review/agent-jobs/2026-06-12-context-parity-diagnostics.codex/diagnostics-report.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Routed from the context-parity audit (task 2026-06-11-odysseus-memory-skill-context-parity): the three explicit unknowns must be resolved by observation on the compute box, not assumption. Read-only probes; one review-side report. 2026-06-12: executed by claude lane during the heartbeat deployment session (operator-approved deviation from codex routing); all three unknowns answered by observation, report at result_path. V1 rubric review by a non-producing lane still applies."
---

# Task: Context-parity diagnostics

Resolve, by read-only observation on the compute box, the three unknowns marked in
`memory-context-audit.md`:

1. **Box checkout freshness** — does `~/projects/vault-runtime` track `origin/main`, by what mechanism, and how stale is it now (`drm-git-auto-pull.timer` is disabled)?
2. **ChromaDB provenance** — what builds the `127.0.0.1:8100` index, from which checkout, with which chunking contract; is it rebuildable from the shared vault-context layer or a second chunking truth?
3. **Heartbeat writer readiness** — what exists in `~/projects/odysseus` toward the #351 writer contract (feeds task `2026-06-12-odysseus-heartbeat-writer`)?

## Constraints

Read-only on the box: no service restarts, no checkout mutation, no index rebuilds. One report at `result_path` with command transcripts as evidence.

## Stop condition

Stop when all three questions have observed answers (or an explicit cannot-determine with the blocking reason) in the report. Verification: V1 rubric review by a non-producing lane.

## Close-out

Diagnostics report merged on `main` via PR #360 (commit `eda2e7c4`, `ops: heartbeat live close-out + context-parity diagnostics report`). Deliverable `automation/review/agent-jobs/2026-06-12-context-parity-diagnostics.codex/diagnostics-report.md` confirmed present on `origin/main`. `linked_pr` was left empty by the producer; the report file is the durable evidence of delivery. Status moved review -> done 2026-06-15.
