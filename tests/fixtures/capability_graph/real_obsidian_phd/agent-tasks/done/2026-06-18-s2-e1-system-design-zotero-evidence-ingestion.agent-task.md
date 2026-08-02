---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-18-s2-e1-system-design-zotero-evidence-ingestion
title: Ground S2-E1 system design in Zotero evidence
status: done
priority: high
task_type: zotero-beaver-evidence-ingestion
created_by: chatgpt
created_at: 2026-06-18T00:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
completed_at: 2026-06-22T00:00:00+01:00
completed_by: codex_subscription
verification_verdict: accept
verification_by: human
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/agent-tasks/inbox/2026-06-18-s2-e1-system-design-zotero-evidence-ingestion.agent-task.md
  - automation/review/02-library/02-evidence/**
  - automation/review/s2-e1-system-design-evidence-ingestion-2026-06-18/**
denied_paths:
  - 03-concept/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/decisions/**
  - 07-standards/**
  - 12-log/**
  - 00-dashboards/**
inputs:
  - Zotero collection: 50 Standards & benchmarks/experiment system design
  - 04-supportDesign/thesis-benchmark/s2-e1-minimum-safety-distance-benchmark.md
  - 04-supportDesign/thesis-benchmark/s2-e1-framework-safety-perception-literature-targeting.md
  - 04-supportDesign/operator-task-fit-adaptive-support/experiment-design-ledger.md
outputs:
  - 04-supportDesign/thesis-benchmark/s2-e1-system-design-research-grounding.md
  - automation/review/s2-e1-system-design-evidence-ingestion-2026-06-18/processing-report.md
result_path: 04-supportDesign/thesis-benchmark/s2-e1-system-design-research-grounding.md
review_report_path: automation/review/s2-e1-system-design-evidence-ingestion-2026-06-18/critical-review-2026-06-19.md
handoff_model: codex
handoff_prompt_path: automation/review/agent-tasks/inbox/2026-06-18-s2-e1-system-design-zotero-evidence-ingestion.agent-task.md
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Use Beaver MCP/Zotero read-only. If canonical evidence creation is uncertain, stage evidence in the processing report rather than polluting the vault."
---

# Ground S2-E1 system design in Zotero evidence

## Objective

Use Beaver MCP and the Zotero database to fully ingest the papers in:

`50 Standards & benchmarks/experiment system design`

The main objective is to develop the research-grounded system design for the S2-E1 experiment:

`S2-E1 minimum safety-distance dynamic-obstacle benchmark`

The thesis does **not** aim to make a novel contribution in safety-separation enforcement or perception. Treat safety separation and perception as adopted, literature-grounded subsystems. The contribution is the design and evaluation of a constrained-process HRC benchmark that combines task fit, human role, safety-bounded robot support, and adoption value.

## Required repository behaviour

1. Inspect the repo processes before writing:
   - ontology and artifact conventions;
   - evidence note conventions;
   - Beaver/Zotero workflow conventions;
   - thesis-benchmark folder conventions;
   - existing S2-E1 files and decision ledger.

2. Treat Zotero and Beaver MCP as read-only.
   - Do not mutate Zotero.
   - Do not rename Zotero collections.
   - Do not alter PDFs.
   - Do not change ontology.

3. Avoid duplication.
   - Reuse existing evidence notes if they already exist.
   - Create new atomic evidence only where repo process allows and where no equivalent evidence already exists.
   - If unsure whether to create a canonical evidence note, stage the evidence in `automation/review/s2-e1-system-design-evidence-ingestion-2026-06-18/processing-report.md` rather than polluting the vault.

## Source set

Process every paper in the Zotero collection:

`50 Standards & benchmarks/experiment system design`

Expected paper families include, but are not limited to:

- Saenz et al. — safety-aware HRC design / MBSE-style design support.
- Marvel & Norcross — implementing speed and separation monitoring.
- Byner et al. — dynamic speed and separation monitoring.
- Magrini et al. — open industrial HRC cells and layered control.
- Karagiannis et al. — adaptive switching safety zones.
- Scalera et al. — robot-stopping approaches and fluency metrics.
- Scholz et al. — sensor-enabled safety systems review.
- Bonci et al. — industrial human-robot perception survey.
- Navarro et al. — proximity perception survey.
- Svarny et al. — SSM and PFL with RGB-D/OpenPose.
- Iodice et al. — visual perception, decision framework, confidence/fallback.
- Cutajar et al. — multimodal sensing for SSM, RGB-D + LiDAR, behaviour tree.
- Yahia et al. — 3D spatial safety monitoring and critical distance.
- Bdiwi et al. — dynamic safety-related finite-state modes.
- Any other paper present in the Zotero folder.

## Extraction target

For each paper, extract only evidence that helps design the experiment system.

Route extracted evidence against these system layers:

1. System design / architecture
2. Task/process boundary
3. Perception / state estimation
4. Separation-distance model
5. Safety supervisor
6. Robot response
7. Evidence / benchmark metrics
8. Validation, assumptions and limitations

For each useful evidence item, capture:

- source paper;
- exact page number or PDF anchor where possible;
- short claim;
- system layer;
- extracted design implication for S2-E1;
- whether it is:
  - baseline adoption evidence;
  - optional upgrade evidence;
  - limitation/risk evidence;
  - metric/evaluation evidence.

Use the vault’s atomic evidence process. Keep evidence atomic: one evidence note or row should support one claim or design implication.

## Specific analysis questions

### A. System architecture

What system architecture should S2-E1 use?

Expected abstraction:

`physical/task system → perception/state estimate → separation model → safety supervisor → robot response → evidence log`

Identify which papers justify:

- module boundaries;
- interface signals;
- safety-aware design workflow;
- model-based design or V-model logic;
- state-machine or behaviour-tree logic;
- digital twin/simulation support if relevant.

### B. Safety separation

What separation-enforcement method should be adopted as baseline?

Expected stance:

- baseline: speed and separation monitoring / zoned supervisor;
- response states: nominal, caution, stop, reset;
- dynamic speed adaptation can be considered after the basic supervisor is working;
- CBFs, safety filters and optimisation are upgrades, not the first system claim.

Extract:

- protective separation variables;
- stopping assumptions;
- uncertainty/latency assumptions;
- zone or distance calculation method;
- stop/slow/resume logic;
- validation requirements.

### C. Perception

What perception system is sufficient for S2-E1?

Expected stance:

- perception serves the safety supervisor;
- the system needs human/robot/object/separation state, not full scene understanding;
- baseline: RGB-D + robot-state logging;
- upgrade: multi-view RGB-D or RGB-D + LiDAR if occlusion dominates;
- optional later: proximity sensing, fiducials, CAD/6D pose, mesh-based distance.

Extract:

- sensor placement;
- output state variables;
- occlusion handling;
- confidence/fallback logic;
- sensor health checks;
- latency;
- separation-distance representation.

### D. Evidence and benchmark metrics

What should the benchmark log?

Minimum candidate metrics:

- minimum separation distance;
- separation violation count;
- time below threshold if any;
- supervisor state transitions;
- robot stop/slow events;
- nuisance stops;
- latency;
- task completion/progress;
- robot idle time;
- human intrusion/event timing;
- confidence-loss events.

Extract which papers justify each metric.

## Required output files

Create or update exactly one detailed synthesis note in:

`04-supportDesign/thesis-benchmark/s2-e1-system-design-research-grounding.md`

Use concise academic writing. Do not write a literature review. Write a design-grounding note.

Recommended structure:

```markdown
---
title: S2-E1 system design research grounding
artifact_type: evidence
status: active
created: 2026-06-18
updated: 2026-06-18
project: phd-research
drm_phase: DS-I-to-PS
linked_experiment: 04-supportDesign/thesis-benchmark/s2-e1-minimum-safety-distance-benchmark.md
source_collection: Zotero/50 Standards & benchmarks/experiment system design
---

# S2-E1 system design research grounding

## Purpose

## Adopted system stance

## System layer matrix

| System layer | Primary papers | Adopted design implication | Open risk |
|---|---|---|---|

## Baseline architecture

## Safety separation baseline

## Perception baseline

## Supervisor state model

## Evidence and benchmark metrics

## Upgrade routes deferred

## Open decisions still requiring supervisor input

## Source coverage audit
```

Also update `04-supportDesign/thesis-benchmark/index.md` if repo convention allows, adding the new note as a literature-grounding note, not as the active experiment specification.

Do not overwrite the active S2-E1 specification unless the repo process explicitly requires it. Prefer linking to it.

## Required processing report

Create:

`automation/review/s2-e1-system-design-evidence-ingestion-2026-06-18/processing-report.md`

Report:

1. Files created or updated.
2. Number of Zotero items inspected.
3. Number of PDFs successfully processed.
4. Number of atomic evidence items created or routed.
5. Papers not processed and why.
6. Any duplicated or pre-existing evidence reused.
7. Remaining design gaps.
8. Exact next human decision needed.

## Quality bar

The output should make it possible to draw the S2-E1 system architecture directly from the literature.

The final design stance should be clear:

- S2-E1 uses a safety-supervised HRC architecture.
- Safety separation is adopted from SSM/zoned/distance-supervisor literature.
- Perception is adopted as a service for separation estimation and evidence logging.
- Novelty is in the constrained-process benchmark design and adoption-value evaluation, not in perception or safety-control invention.

## Acceptance criteria

- Every Zotero item in the target collection is inspected or explicitly listed as unprocessed.
- All extracted evidence is routed to one of the eight system layers.
- Evidence is atomic, page-anchored where possible, and not duplicated.
- The synthesis note contains a system-layer matrix and a baseline architecture usable for diagramming.
- The synthesis note distinguishes baseline adoption from optional upgrades.
- The processing report gives a complete coverage audit.
