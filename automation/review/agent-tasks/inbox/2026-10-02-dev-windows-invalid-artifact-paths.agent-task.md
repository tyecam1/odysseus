---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-02-dev-windows-invalid-artifact-paths
title: "Make dev checkable on Windows: 171 tracked eval-artifact paths contain a colon"
status: inbox
priority: medium
task_type: implementation
created_by: claude
created_at: 2026-10-02T18:20:00+01:00
updated_at: 2026-10-02T18:20:00+01:00
executor: ""
execution_mode: review-first
architecture: single
architecture_rationale: "A rename of generated eval artifacts plus the one producer that names them; no new component."
single_agent_baseline: "One implementation owner renames the artifact directories, fixes the producer and any manifest that cites the old paths, and adds a guard test."
execution_host: compute-box
context_budget: medium
coordination_reason: "Found during the governed home deployment (Misumi long-horizon programme, application 2026-10-02-misumi-long-horizon-programme-04): a plain git clone of dev on the Windows home host fails at checkout, so every household release must be a hand-built sparse checkout."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - evals/local_models/**
  - scripts/**
  - docs/**
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - evals/local_models/results/artifacts/
outputs:
  - artifact directories whose names are valid on Windows, the producer fixed, manifests and docs updated, and a guard test
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Interim workaround in use: the household release checkouts exclude evals/local_models/results/artifacts/ with a sparse-checkout file (core.longpaths true, core.protectNTFS false). Do not rewrite history; a rename commit is enough."
---

# `dev` cannot be checked out on Windows as is

## Evidence (2026-10-02)

A plain `git clone` of `dev` on the home host (Windows 11) fails during checkout:

```text
error: invalid path 'evals/local_models/results/artifacts/lm1-a3-validation-1/qwen3:8b/ros_log_test-01__8000.json'
fatal: unable to checkout working tree          (exit 128, partial directory left behind)
```

171 tracked paths contain `:` (the directory names are model tags such as `qwen3:8b`, `lfm2.5:8b`, `ornith:9b`,
`qwen3.6:35b`, `qwen3.8:27b`, `nemotron-3.5-lightning:30b-a3b`), all under `evals/local_models/results/artifacts/`, first added
on 2026-08-21 (LM1 audit-repair and LM2 discovery work). The live household releases are sparse checkouts that exclude that tree,
which is why earlier cutovers worked, but nothing in the deployment runbook says so.

## Required work

1. Find where the artifact directory name is built (the local-model evaluation harness) and make it filesystem-safe (for
   example replace `:` with `_`), keeping the real model tag in the artifact's JSON.
2. Rename the existing 171 paths in one commit and update any manifest, result file or document that cites an old path.
3. Add a guard test that fails when a tracked path contains a character that is invalid on Windows (`: < > " | ? *`).
4. Add one line to `docs/operations/odysseus-host-deployment.md` saying how a release checkout is made on Windows until this is
   done, and remove it afterwards.

## Acceptance

- A plain `git clone` of `dev` on Windows completes without a sparse-checkout workaround.
- The guard test passes and fails on a deliberately bad path.
- No result or manifest still points at an old path.
