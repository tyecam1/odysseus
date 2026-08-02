---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-19-asi-evolve-compute-box-bundle-run
title: Run ASI-Evolve model-backed evidence bundle on the tunnel host
status: done
priority: high
task_type: evidence-extraction
created_by: claude
created_at: 2026-06-19T00:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_local_model: true
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
  - automation/review/agent-tasks/review/2026-06-19-asi-evolve-compute-box-bundle-run.agent-task.md
  - automation/review/02-library/02-evidence/asi-evolve/**
  - automation/review/quarantine/overnight-pdf-evidence/**
  - automation/review/research-engine/2026-06-18-asi-evolve-ingest-run-summary.md
  - automation/review/hygiene/2026-06-22-agent-worktree-branch-consolidation-review.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - 02-library/04-pdfs/Xu et al. - 2026 - ASI-Evolve AI Accelerates AI.pdf
outputs:
  - automation/review/02-library/02-evidence/asi-evolve/xuasievolveaiaccelerates2026.workflow-evidence-bundle.json
  - automation/review/02-library/02-evidence/asi-evolve/xuasievolveaiaccelerates2026.atomic-evidence-review.md
  - automation/review/02-library/02-evidence/asi-evolve/xuasievolveaiaccelerates2026.worker-audit.json
  - automation/review/02-library/02-evidence/asi-evolve/xuasievolveaiaccelerates2026.worker-critic.json
  - automation/review/research-engine/2026-06-18-asi-evolve-ingest-run-summary.md
result_path: automation/review/02-library/02-evidence/asi-evolve/xuasievolveaiaccelerates2026.workflow-evidence-bundle.json
review_report_path: automation/review/research-engine/2026-06-18-asi-evolve-ingest-run-summary.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Completed on the authorised remote compute box on 2026-06-22. Governed run overnight-20260622173324-p01-xuasievolveaiaccelerates2026 used qwen3:8b over 19 PDF pages and produced 10 quarantined spans plus six model proposals. The spans are retained as workflow-only support; all six routing proposals are rejected for HRC/DRM scope leakage."
completed_at: 2026-06-22T18:33:36+01:00
completed_by: codex_subscription
verification_verdict: pending-human-review
verification_by: codex
---

# ASI-Evolve model-backed evidence bundle

## Completion

The governed worker ran in an isolated clone on the remote compute box after model preflight and positive endpoint attestation. Durable review artifacts preserve the extracted spans, worker hashes and the scope-leakage adjudication. No generated proposal is approved for downstream application.
