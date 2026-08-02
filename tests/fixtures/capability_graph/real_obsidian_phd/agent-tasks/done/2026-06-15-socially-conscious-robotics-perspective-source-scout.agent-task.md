---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-06-15-socially-conscious-robotics-perspective-source-scout
title: Scout outside-field sources for socially conscious robotics writing
status: done
priority: medium
task_type: synthesis
created_by: human
created_at: 2026-06-15T12:10:00+00:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/routine-reports/source-scouting/2026-06-15-socially-conscious-robotics-perspective-sources.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/decision-packets/magnifica-humanitas-source-ledger-adjudication-2026-06-09.md
  - 11-projects/tye/J1/j1-section-2-method.md
  - 02-library/04-pdfs/Blessing and Chakrabarti - 2009 - DRM, a Design Research Methodology.pdf
outputs:
  - automation/review/routine-reports/source-scouting/2026-06-15-socially-conscious-robotics-perspective-sources.md
result_path: ""
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: automation/review/decision-packets/magnifica-humanitas-source-ledger-adjudication-2026-06-09.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "Scout outside-field sources for introductions, problematisation, and normative framing in socially conscious robotics/HRC papers. Do not create canonical notes, mutate Zotero, promote evidence, or treat literary/doctrinal/philosophical sources as empirical causal evidence."
---

# Task: Scout outside-field sources for socially conscious robotics writing

## Objective

Find and triage outside-field sources that can play the same role as `Magnifica Humanitas`: sources that strengthen the paper style, introductions, problematisation, and normative framing for socially conscious robotics without being misused as empirical HRC evidence.

## Source families to inspect

- Robotics and AI cultural sources, including Asimov's robot stories/laws and Karel Capek's `R.U.R.`.
- Cybernetics and technology criticism, including Norbert Wiener, Lewis Mumford, Jacques Ellul, Langdon Winner, and Andrew Feenberg.
- Labour, automation, and work dignity sources, including Harry Braverman, David Noble, Shoshana Zuboff, and worker-centred STS sources.
- Care ethics, human dignity, and social justice sources, including Joan Tronto, Amartya Sen, Martha Nussbaum, and Catholic Social Doctrine sources such as `Laborem Exercens`, `Laudato Si`, `Fratelli Tutti`, `Antiqua et Nova`, and `Magnifica Humanitas`.
- Human-centred technology, HCI, and STS bridge sources, including Lucy Suchman, Susan Leigh Star, Geoffrey Bowker, Helen Nissenbaum, and Lilly Irani.

## Required output

Write one review-side report at:

`automation/review/routine-reports/source-scouting/2026-06-15-socially-conscious-robotics-perspective-sources.md`

The report must include:

- 20 to 40 candidate sources with full citation metadata where available;
- whether each source is already in Zotero/library, should be added later, or should only be noted;
- source role: introduction hook, problematisation source, normative criterion, historical analogy, cautionary contrast, or paper-style influence;
- DRM mapping: RC/problematisation, standard-normative, success-criteria framing, or writing-only;
- explicit exclusion: whether the source must not be used as empirical causal evidence;
- 5 to 8 highest-priority sources for immediate paper use;
- suggested locations in current paper writing: introduction, motivation, problematisation, discussion, limitations, or future work.

## Guardrails

- Do not write canonical paths.
- Do not mutate Zotero, Better BibTeX exports, PDFs, or external databases.
- Do not create evidence notes.
- Do not propose ontology nodes unless a separate human-gated decision packet is needed.
- Do not cite speculative or fictional sources as evidence that a robotics mechanism works.
- Prefer sources that support the user's minimalist academic style: concise, socially aware, and grounded in the relationship between robotics, work, dignity, agency, surveillance, skill, and power.

## Acceptance criteria

- The report clearly separates empirical evidence from perspective sources.
- The report gives a short actionable shortlist for socially conscious robotics paper introductions.
- Each candidate has a traceable source path, URL, DOI, ISBN, or Zotero lookup instruction.
- The report names what not to use each source for.

