---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-30-methodological-spine-drafting-guidance-digest
title: Digest Zotero drafting papers into manuscript development guidance
status: done
priority: high
task_type: synthesis
created_by: codex-roadmap-router
created_at: 2026-06-30T13:15:00+01:00
executor: zotero_mcp
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
  - automation/review/routine-reports/methodological-spine-drafting/2026-06-30-scientific-manuscript-development-guidance.md
  - automation/review/routine-reports/methodological-spine-drafting/2026-06-30-scientific-manuscript-development-guidance.json
  - automation/review/routine-reports/methodological-spine-drafting/2026-06-30-agent-use-brief.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - Zotero collection: 30 Methodological Spine/Drafting
  - .agents/skills/zotero-kb/SKILL.md
  - .agents/skills/zotero-kb/scripts/zotero_kb.py
  - 09-resources/writing/personal-writing-style-agentic-method.md
  - 09-resources/writing/academic-writing-cycle.md
outputs:
  - automation/review/routine-reports/methodological-spine-drafting/2026-06-30-scientific-manuscript-development-guidance.md
  - automation/review/routine-reports/methodological-spine-drafting/2026-06-30-scientific-manuscript-development-guidance.json
  - automation/review/routine-reports/methodological-spine-drafting/2026-06-30-agent-use-brief.md
result_path: automation/review/routine-reports/methodological-spine-drafting/2026-06-30-scientific-manuscript-development-guidance.md
review_report_path: automation/review/routine-reports/methodological-spine-drafting/2026-06-30-scientific-manuscript-development-guidance.md
handoff_model: zotero_mcp
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Comprehensively digest the Zotero collection 30 Methodological Spine/Drafting into a source-grounded manuscript-development guidance layer. Keep it separate from personal stylistic guidance; do not create canonical writing guidance without later approval."
---

# Task: Digest Zotero drafting papers into manuscript development guidance

## Objective

Use the Zotero collection `30 Methodological Spine/Drafting` to produce a central, source-grounded manuscript development and scientific writing guidance layer. This should complement, not replace, the user's personal stylistic writing guidance.

## Required source set

Use every item in the Zotero collection, including bibliographic items with PDFs and standalone PDF attachments. Current collection inventory from read-only Zotero access:

- Michael Alley, `The Craft of Scientific Writing`
- Michael Alley, `The Craft of Scientific Presentations`
- `10902-REF2021-Guidance-on-Submission`
- Pottier et al., `Title, abstract and keywords`
- Adorno and Marinho, `The INCOMPLETE GUIDE to Academic Writing in Robotics Research`
- `emwa-261-every`
- `9780472034741-intro`
- Biber and Gray, `Challenging stereotypes about academic writing`
- Lipomi, `Style Guides and the Garlic, Shallots, and Butter of Scientific Writing`
- Kojima and Popiel, `Strategies on Reducing Wordiness`
- Gross, `Style and Arrangement in Scientific Prose`
- Mensh, Kording, and Markel, `Ten simple rules for structuring papers`

## Required output

Write:

- `automation/review/routine-reports/methodological-spine-drafting/2026-06-30-scientific-manuscript-development-guidance.md`
- `automation/review/routine-reports/methodological-spine-drafting/2026-06-30-scientific-manuscript-development-guidance.json`
- `automation/review/routine-reports/methodological-spine-drafting/2026-06-30-agent-use-brief.md`

## Content requirements

- Synthesise guidance logically by manuscript-development phase: problem framing, paper architecture, title/abstract/keywords, paragraph and sentence design, evidence presentation, readability, revision, response to venue criteria, and presentation transfer.
- Draw distinct, valuable guidance from each source; do not let Alley dominate by default.
- Preserve source traceability with citekeys, Zotero item IDs, attachment keys, page anchors where available, and short source-specific contribution notes.
- Clearly separate this literature-grounded guidance from the user's personal stylistic guidance.
- Add an agent-use brief explaining how future agents should use this guidance alongside personal style guidance without overfitting or inventing rules.

## Boundaries

- Read Zotero and PDFs only.
- Do not mutate Zotero, PDFs, annotations, Better BibTeX, canonical notes, or existing personal writing guidance.
- Do not write into `09-resources/**` in this task.
- If a source is unavailable or unreadable, record the gap explicitly rather than filling it from memory.

## Acceptance criteria

- Every collection item is represented in the source matrix.
- The guidance is concise enough to be used operationally by agents.
- The JSON source matrix identifies which guidance claims came from which source.
- The output avoids generic writing advice unless it is grounded in a collection source.
