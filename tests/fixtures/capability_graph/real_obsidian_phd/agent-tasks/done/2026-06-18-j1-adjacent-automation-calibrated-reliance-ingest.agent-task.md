---
title: J1 adjacent automation and calibrated reliance evidence ingest
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-18-j1-adjacent-automation-calibrated-reliance-ingest
status: done
task_type: zotero-evidence-ingestion
executor: codex_subscription
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
created_by: chatgpt
created_at: 2026-06-18T00:00:00+01:00
approval_required: true
completed_at: 2026-06-22T00:00:00+01:00
result_path: automation/review/J1-new-adjacent-evidence-2026-06-18/README.md
review_report_path: automation/review/J1-new-adjacent-evidence-2026-06-18/j1-adjacent-evidence-synthesis-audit-2026-06-18.md
created: 2026-06-18
owner: agent
project: J1
priority: high
due: 2026-06-20
allowed_paths:
  - automation/review/agent-tasks/inbox/2026-06-18-j1-adjacent-automation-calibrated-reliance-ingest.agent-task.md
  - automation/review/J1-new-adjacent-evidence-2026-06-18/**
  - automation/review/02-library/02-evidence/J1-new-adjacent-evidence-2026-06-18/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
allowed_mutations:
  - zotero_collection_organisation
  - repo_staged_evidence_outputs
blocked_mutations:
  - canonical_manuscript_rewrite
  - ontology_changes
  - broad_scope_expansion
---

# J1 adjacent automation and calibrated reliance evidence ingest

## Purpose

Organise the newly gathered J1-adjacent papers in Zotero and process them into the vault evidence pipeline so they are ready for use in the J1 manuscript.

The task should strengthen J1 without broadening it into a generic HRC, XAI, human-autonomy teaming, or labour-policy review.

## Controlling J1 scope

J1 is a problematisation-driven conceptual-framework literature review on worker-centred industrial human-robot collaboration. It is not a generic HRC survey, CPI-only paper, lab-automation paper, or S2 protocol.

The manuscript spine is:

1. benchmark task design
2. human-factor signal design
3. control/safety route
4. transferability/adoption conditions

Read these before processing:

- `11-projects/tye/J1/j1-ground-truth-plan.md`
- `11-projects/tye/J1/j1-execution-plan.md`
- `11-projects/tye/J1/j1-section-2-method.md`
- `automation/review/J1-evidence-synthesis-audit-2026-06-16.md`
- `automation/review/j1-atomic-evidence-processing-2026-06-17/coverage-ledger.csv`

## Source bundle

The user has uploaded the following papers to Zotero `My Library` and locally in the current ChatGPT exchange:

- Simon et al. 2023 — `How Humans Comply With a (Potentially) Faulty Robot: Effects of Multidimensional Transparency`
- De Visser & Parasuraman 2011 — `Adaptive Aiding of Human-Robot Teaming: Effects of Imperfect Automation on Performance, Trust, and Workload`
- Loft et al. 2021/2023 — `The Impact of Transparency and Decision Risk on Human-Automation Teaming Outcomes`
- Du, Huang & Yang 2020 — `Not All Information Is Equal: Effects of Disclosing Different Types of Likelihood Information on Trust, Compliance and Reliance, and Task Performance in Human-Automation Teaming`
- Yang, Unhelkar, Li & Shah 2017 — `Evaluating Effects of User Experience and System Transparency on Trust in Automation`
- Miller & Parasuraman 2003 — `Beyond Levels of Automation: An Architecture for More Flexible Human-Automation Collaboration`
- Miller & Parasuraman 2007 — `Designing for Flexible Interaction Between Humans and Automation: Delegation Interfaces for Supervisory Control`
- Kaber & Endsley 2004 — `The Effects of Level of Automation and Adaptive Automation on Human Performance, Situation Awareness and Workload in a Dynamic Control Task`
- O'Neill et al. 2022 — `Human-Autonomy Teaming: A Review and Analysis of the Empirical Literature`
- Parker & Grote 2022 — `Automation, Algorithms, and Beyond: Why Work Design Matters More Than Ever in a Digital World`
- Welfare et al. 2019 — `Consider the Human Work Experience when Integrating Robotics in the Workplace`
- Endsley 2017 — `From Here to Autonomy: Lessons Learned From Human-Automation Research`
- Norman 1990 — `The Problem with Automation: Inappropriate Feedback and Interaction, not Over-Automation`
- Onnasch et al. 2014 — `Human Performance Consequences of Stages and Levels of Automation: An Integrated Meta-Analysis`
- Parasuraman & Riley 1997 — `Humans and Automation: Use, Misuse, Disuse, Abuse`

## Zotero organisation

Find the papers in Zotero `My Library`. Do not create duplicate Zotero items. If duplicates exist, report them rather than blindly merging unless the repo/Zotero process clearly permits merging.

Preferred folder routing:

### `50 Standards & benchmarks/J1 worker-centred HRC additions/automation and worker role`

- Parasuraman & Riley 1997
- Norman 1990
- Endsley 2017
- Onnasch et al. 2014
- Parker & Grote 2022
- Welfare et al. 2019

### `50 Standards & benchmarks/J1 worker-centred HRC additions/human-factor signal and calibrated reliance`

- De Visser & Parasuraman 2011
- Kaber & Endsley 2004
- Miller & Parasuraman 2003
- Miller & Parasuraman 2007
- Yang, Unhelkar, Li & Shah 2017
- Du, Huang & Yang 2020
- Loft et al. 2021/2023
- Simon et al. 2023
- O'Neill et al. 2022

If the exact collections do not exist, create the minimal collection structure under the nearest existing J1, standards, benchmark, or evidence collection. Do not reorganise unrelated Zotero folders.

For each Zotero item, verify:

- title
- authors
- year
- venue
- DOI or URL where available
- PDF attachment present
- citekey status
- duplicate candidates
- missing metadata requiring human review

## Repo processing

Process each paper according to the existing evidence pipeline. Search the repo first for existing paper, annotation, evidence, staging, or quarantine records using title fragments, first author, and citekey variants.

Create new outputs only where the paper adds manuscript-useful evidence. Prioritise paragraph-level synthesis value over atom count.

For each useful paper, produce:

1. paper/reference note if missing and required by repo convention
2. annotation note or staging annotation record if required
3. atomic evidence notes only where claim support is direct and useful
4. routing ledger mapping each useful atom to J1 section/subsection
5. synthesis audit showing how the bundle reinforces J1

## Target evidence routes

### §1 / §3 — worker role, automation trade-offs, benchmark task design

Support claims that:

- automation changes human work rather than simply removing it
- nominal automation performance can hide failure-recovery and monitoring burdens
- higher automation can improve routine performance while degrading situation awareness, manual recovery, or skilled intervention
- benchmark tasks must preserve skilled human contribution rather than reduce the worker to passive supervision
- work design and worker experience affect whether robotics integration is genuinely worker-centred

Relevant papers:

- Parasuraman & Riley 1997
- Norman 1990
- Endsley 2017
- Onnasch et al. 2014
- Parker & Grote 2022
- Welfare et al. 2019

### §4 — human-factor signal design and calibrated reliance

Support claims that:

- trust should be calibrated, not maximised
- workload should be interpreted as a task-event-specific trade-off, not simply minimised
- situation awareness depends on information availability, timing, and operator engagement
- transparency can improve reliance or reduce verification, but can also increase burden or have non-linear effects
- human-factor measures should be tied to specific events: accept, reject, verify, intervene, recover, hand over, or reallocate authority

Relevant papers:

- De Visser & Parasuraman 2011
- Kaber & Endsley 2004
- Yang, Unhelkar, Li & Shah 2017
- Du, Huang & Yang 2020
- Loft et al. 2021/2023
- Simon et al. 2023
- O'Neill et al. 2022

### §5 — control/safety route and authority/fallback design

Support claims that:

- automation level should be selected by task function and risk, not as a global autonomy level
- adaptive and adaptable automation have different authority, predictability, and workload implications
- delegation interfaces preserve human authority better than fixed automation in some supervisory contexts
- control-route selection should follow task, human-factor signal, reliability, and fallback requirements

Relevant papers:

- Miller & Parasuraman 2003
- Miller & Parasuraman 2007
- Kaber & Endsley 2004
- De Visser & Parasuraman 2011
- Endsley 2017

### §6 — transferability and adoption

Support claims that:

- transferability depends on work design, role quality, user authority, reliability, and operational support
- robotics integration should be evaluated against worker experience and organisational work design, not only local task performance
- evidence should report the source conditions under which successful HRC occurs

Relevant papers:

- Parker & Grote 2022
- Welfare et al. 2019
- O'Neill et al. 2022
- Parasuraman & Riley 1997

## Claim-ceiling rules

- Automation and human-factors classics may support general automation trade-offs, but not specific industrial HRC effectiveness unless paired with HRC evidence.
- Human-autonomy teaming reviews may support conceptual framing, but not direct claims about cobot deployment unless the reviewed evidence is industrial or robot-specific.
- Simulator studies may support mechanism claims about trust, workload, situation awareness, transparency, verification, and intervention behaviour, but not direct field adoption claims.
- Worker-experience and work-design papers may support worker-centred adoption logic, but not robot control design unless bridged through HRC/control evidence.
- Do not let XAI, generic AI trust, military-only autonomy, or driving-only transparency evidence dominate J1.

## Evidence note quality standard

Each atomic evidence note must include:

- YAML frontmatter following repo convention
- `artifact_type: evidence`
- source/citekey
- page number or page range
- exact claim supported
- claim ceiling
- J1 route: section and subsection
- relevance to J1 manuscript
- limitation/scope note
- links to relevant J1 planning files where appropriate

Prefer 2–4 high-value evidence atoms per paper unless the paper is exceptionally central. Avoid producing atom count for its own sake.

## Extraction focus

- Parasuraman & Riley 1997: use/misuse/disuse/abuse; workload, trust, risk, reliability, monitoring, salience; automation abuse defining operator role as by-product.
- Norman 1990: problem is inappropriate feedback/interaction; intermediate automation handles routine cases but fails on abnormalities; need continual feedback and system-level design.
- Endsley 2017: autonomy oversight conundrum; out-of-the-loop loss of situation awareness; interface features, LOA, adaptive automation, granularity of control.
- Onnasch et al. 2014: routine performance/workload benefits vs failure performance/situation-awareness costs; critical boundary around decision/action selection automation; function allocation trade-off.
- De Visser & Parasuraman 2011: imperfect automation can still help performance; adaptive automation improves trust/workload compared with static/no automation; task-load-triggered assistance.
- Kaber & Endsley 2004: LOA and adaptive automation affect performance, situation awareness, workload differently; intermediate LOA can preserve situation awareness; adaptive automation scheduling/workload trade-offs.
- Miller & Parasuraman 2003: beyond global LOA; task-model-based delegation; automation level should vary across subtasks/functions.
- Miller & Parasuraman 2007: adaptable delegation keeps human in charge; high LOA can reduce situation awareness, skill, acceptance; delegation supports flexible supervisory control.
- Yang et al. 2017: trust evolves dynamically; real-time trust and area-under-trust-curve; transparency affects momentary trust and cry-wolf effects.
- Du et al. 2020: not all likelihood information is equal; predictive values/overall likelihood support more appropriate reliance than hit/correct rejection rates; information design affects compliance/reliance/performance.
- Loft et al. 2021/2023: transparency and decision risk affect verification, rejection, decision time, workload; high-risk decisions may justify higher verification/workload; transparency can reduce verification and decision time without always improving accuracy.
- Simon et al. 2023: multidimensional transparency affects compliance with a potentially faulty robot; trust in signal and risk perception mediate/moderate compliance; robot-to-human and robot-of-human transparency should be distinguished.
- O'Neill et al. 2022: HAT definition and empirical review; task characteristics, agent characteristics, team composition, communication, training; broad framing only.
- Parker & Grote 2022: work design central to technology effects; technology affects autonomy/control, skill use, feedback, relational work, job demands; joint optimisation and human-centred design.
- Welfare et al. 2019: worker-valued positive attributes; negative work attributes; robotics should reduce negative attributes without eroding valued work.

## Required output folder

Create:

`automation/review/J1-new-adjacent-evidence-2026-06-18/`

Inside it create:

1. `README.md`
2. `zotero-organisation-ledger.csv`
3. `j1-routing-ledger.csv`
4. `j1-adjacent-evidence-synthesis-audit-2026-06-18.md`
5. proposed evidence notes in the proper evidence/staging location, following repo conventions

### `README.md`

Must state:

- what was processed
- Zotero collections used
- repo files created
- duplicate/missing metadata issues
- human review required

### `zotero-organisation-ledger.csv`

Columns:

- title
- first_author
- year
- citekey
- zotero_item_key
- zotero_collection
- pdf_present
- duplicate_status
- metadata_status
- action_taken
- notes

### `j1-routing-ledger.csv`

Columns:

- citekey
- paper
- evidence_note_path
- J1_section
- J1_subsection
- claim_supported
- claim_ceiling
- priority
- manuscript_use

### `j1-adjacent-evidence-synthesis-audit-2026-06-18.md`

Must include:

- whether the new bundle materially changes J1
- section-by-section contribution
- which papers should be cited first
- which papers are backup/context only
- remaining evidence gaps, if any
- warning against scope drift

## Do not

- Do not update the canonical J1 manuscript in this task unless an existing repo convention explicitly requires automatic manuscript insertion.
- Do not create generic summaries.
- Do not create evidence atoms without a clear J1 paragraph use.
- Do not modify ontology.
- Do not reorganise unrelated Zotero collections.

## Acceptance criteria

- Zotero items are placed in clear J1-adjacent collections.
- Metadata and PDF attachment status are audited.
- Existing repo records are checked before any new evidence is created.
- New evidence atoms follow repo conventions and include claim ceilings.
- J1 section routing is explicit.
- Final audit explains how the bundle reinforces J1 without scope drift.
- Final agent response reports files changed, number of papers processed, evidence notes created, duplicate/metadata issues, and top papers for immediate J1 citation.

## Recommended immediate-citation set

If processing succeeds, the likely first-citation set for manuscript use is:

1. Parasuraman & Riley 1997
2. Norman 1990
3. Endsley 2017
4. Onnasch et al. 2014
5. De Visser & Parasuraman 2011
6. Miller & Parasuraman 2007
7. Yang et al. 2017
8. Du et al. 2020
9. Loft et al. 2021/2023
10. Simon et al. 2023
11. Parker & Grote 2022
12. Welfare et al. 2019

## Commit message

`Process J1 adjacent automation and calibrated reliance evidence`
