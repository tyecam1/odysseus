---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-27-human-writing-skill
title: "Develop a source-safe /human academic writing skill"
status: review
priority: medium
task_type: writing-skill
created_by: chatgpt
created_at: 2026-07-27T14:00:00+01:00
updated_at: 2026-07-31T16:41:36+01:00
executor: claude_subscription
execution_mode: implementation
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: codex/human-writing-skill-20260731
allowed_paths:
  - automation/review/skills/**
  - automation/review/evals/**
  - automation/review/agent-tasks/**
  - automation/prompts/**
  - Scripts/automation/tests/**
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 02-library/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
inputs:
  - 09-resources/writing/**
  - 11-projects/tye/J1/drafting-sprint/llm-leverage-protocol.md
outputs:
  - automation/review/skills/human-writing.skill.md
  - automation/review/evals/human-writing-eval-corpus.md
  - automation/review/evals/human-writing-eval-report.md
result_path: automation/review/skills/human-writing.skill.md
review_report_path: automation/review/evals/human-writing-eval-report.md
handoff_model: claude_codex_review_package
operator_decision_path: automation/review/evals/human-writing-eval-report.md
linked_pr: ""
supersedes: []
duplicates: []
completed_by: codex
completed_at: 2026-07-31T16:41:36+01:00
notes: "The skill is for authorial voice and clarity, not AI-detector evasion or undisclosed authorship. PR-2 repair: executor normalised from claude_then_codex to claude_subscription; codex_subscription performs independent verification before merge."
---
# Develop a source-safe /human academic writing skill

## Goal

Create a bounded writing skill that transforms user-authored seed prose into the user's academic voice while preserving claims, citations, uncertainty and disciplinary meaning.

## Required behaviour

- Require human seed text before substantive rewriting.
- Prefer concrete subjects, active verbs, short sentences, top-down structure and explicit logical transitions.
- Remove generic AI cadence, throat-clearing, inflated significance, symmetry-for-its-own-sake and unsupported synthesis.
- Preserve source boundaries, claim ceilings, terminology and citations exactly unless an issue is explicitly flagged.
- Never invent evidence, references or results.
- Return a change log naming substantive edits and unresolved ambiguity.
- Refuse requests framed as detector evasion, fake authorship or concealment of prohibited AI use.

## Evaluation

Use paired samples from the user's accepted writing, rejected AI-like drafts and neutral technical prose. Score:

- semantic preservation;
- authorial similarity without phrase copying;
- clarity and concision;
- citation preservation;
- unsupported-claim rate;
- false-positive intervention on already-good prose.

## Acceptance criteria

- The skill can be invoked explicitly and does not auto-trigger on all writing.
- It produces critique plus a bounded revision, not wholesale ghostwriting.
- It passes citation and claim-diff checks.
- It does not collapse technical nuance into conversational vagueness.
- Human approval is required before deployment into the live writing workflow.

## Scope repair note (PR-2)

`09-resources/writing/**` is removed from `allowed_paths`. It is a read-only
seed-text input (see `inputs`), not a write target; the skill draft and eval
corpus/report stay staged under `automation/review/skills/**` and
`automation/review/evals/**`.

## Packet amendment — 2026-07-31 (dual-agreement W1)

`allowed_paths` extended to include `automation/docs/current-capabilities.md`
and `automation/docs/capability_manifest.json`.

Reason: adjudication round W1 ruled that this packet **is
capability-affecting now** — it adds executable, directly runnable
deterministic behaviour and tests — even though the artifact is staged,
uninstalled, non-dispatchable, partial and non-live.
`automation/AGENTS.md` requires every capability-affecting change to
update both capability-truth files in the same change, so capability
truth may not stay silent until promotion.

The implementing worker was correct to PARK the update rather than widen
its own packet: a worker authorising its own scope is the circularity this
programme has repeatedly refused. The amendment is therefore made as a
separate recorded act under the dual-agreement protocol, not by the worker
that needed it.

Authorised by: dual-agreement round W1, 2026-07-31. Scope: these two paths
only, for truthful `partial` entries.
