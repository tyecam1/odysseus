---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-16-constrained-manipulation-literature-grounding-and-novelty
title: Ground constrained manipulation benchmark novelty against literature
status: done
priority: high
task_type: evidence-synthesis
created_by: chatgpt
created_at: 2026-06-16T09:10:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/s2-benchmark-design/2026-06-16-constrained-manipulation-literature-grounding-and-novelty.md
  - automation/review/agent-tasks/**/2026-06-16-constrained-manipulation-literature-grounding-and-novelty.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 12-log/26-06/26-25/supervision-erfu-2026-06-15.md
  - 02-library/**
  - 11-projects/tye/annual reviews/1/annual-review-2026-research-report-draft-v2.md
  - 11-projects/cpi/conference-paper/**
outputs:
  - automation/review/s2-benchmark-design/2026-06-16-constrained-manipulation-literature-grounding-and-novelty.md
result_path: automation/review/s2-benchmark-design/2026-06-16-constrained-manipulation-literature-grounding-and-novelty.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: 10-inbox/prepare-next-week-s2-system-architecture-discussion.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Meeting outcome requires novelty, literature grounding, and framing against what already exists. Use Zotero/MCP if available, but write only a review-side packet."
---
# Task: Ground constrained manipulation benchmark novelty against literature

## Objective

Answer the supervision question: **what already exists, what is novel here, and how should the benchmark be framed against the literature?**

This must support the constrained-manipulation S2 benchmark route, especially dynamic obstruction avoidance and perceived safety/preferred separation in a chemical-free mock-up.

## Required output

Write one packet to:

- `automation/review/s2-benchmark-design/2026-06-16-constrained-manipulation-literature-grounding-and-novelty.md`

Include:

1. **Existing-work map**: glovebox, constrained manipulation, close-proximity HRC, preferred separation/perceived safety, obstruction avoidance, and process-lab analogues.
2. **Novelty claim candidates**: rank from strongest to weakest.
3. **Weak claims to avoid**: claims that will be exposed as generic robotics, ordinary obstacle avoidance, or overclaimed process automation.
4. **Benchmark contribution framing**: design-method, system-perspective, HRI/safety, or broad industrial HRC design-consideration route. Recommend one primary framing.
5. **Source traceability table**: each claim with supporting vault/Zotero source.
6. **Missing evidence list**: maximum five gaps that genuinely need follow-up retrieval.

## Hard constraints

- Do not create or modify canonical evidence notes.
- Do not fabricate citations. Mark unknowns clearly.
- Do not treat HRC buzzwords as novelty.
- Do not let the benchmark become detached from broad industrial HRC design-consideration scope. Treat process-specific relevance as conference-paper context rather than J1 scope.

## Acceptance criteria

The packet must produce defensible wording for the novelty and related-work frame, not just a literature dump.
