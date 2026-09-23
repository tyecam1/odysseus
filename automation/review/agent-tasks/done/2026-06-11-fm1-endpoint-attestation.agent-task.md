---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-11-fm1-endpoint-attestation
title: Runtime attestation for SSH-forwarded model endpoint (close FM-1)
status: done
priority: medium
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
  - automation/config/model_execution_policy.yaml
  - automation/docs/remote-compute-thin-client-architecture.md
outputs:
  - automation/review/platform-evaluations/2026-06-16-fm1-endpoint-attestation.md
  - automation/config/model_execution_policy.yaml
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
result_path: automation/review/platform-evaluations/2026-06-16-fm1-endpoint-attestation.md
review_report_path: automation/review/platform-evaluations/2026-06-16-fm1-endpoint-attestation.md
handoff_model: codex_work_package
handoff_prompt_path: "automation/review/handoff-prompts/2026-06-11-fm1-endpoint-attestation.codex-work-package.md"
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Implemented by Codex on 2026-06-16 under explicit operator authorization after rebase. Uses configured model tag fingerprint attestation plus existing heuristic guards; live tunnel verification remains V2 human-verified."
---

# Task: FM-1 runtime endpoint attestation

## Objective

Replace heuristic local-Ollama guards with positive attestation that `127.0.0.1:11434` is the forwarded compute-box endpoint. Candidate mechanisms, simplest first:

1. Box-side identity fingerprint: pin the exact `/api/tags` model-set + a box-only sentinel marker (e.g. a tiny dummy model tag present only on the box); preflight verifies the pinned fingerprint.
2. Box-side reverse proxy adding an identity header with a non-secret box identifier; preflight requires it.
3. SSH-channel verification: assert the forwarding SSH process targets the known host key before trusting the port.

Pick the simplest mechanism that fails closed when a laptop-local Ollama answers; document the choice and residual risk in `model_execution_policy.yaml` and the thin-client architecture doc.

## Constraints

No public exposure; no secrets in repo or attestation payloads; existing heuristic guards retained as defense-in-depth; preflight remains read-only.

## Acceptance criteria

With a deliberate laptop-local Ollama serving 11434, `model-preflight --require-ready` and `model-endpoint-diagnostics --require-remote` both fail; with the genuine tunnel they pass; unit tests cover both paths; FM-1 marked closed in the architecture doc; capability docs updated.
