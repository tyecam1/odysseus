---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-19-s2-hardware-zotero-system-constraints
title: Ground S2 hardware constraints from Zotero hardware folder
status: done
priority: high
task_type: zotero-beaver-hardware-synthesis
created_by: chatgpt
created_at: 2026-06-19T00:00:00+01:00
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
source_traceability_required: true
repo: tyecam1/obsidian-PhD
allowed_paths:
  - automation/review/agent-tasks/review/2026-06-19-s2-hardware-zotero-system-constraints.agent-task.md
  - automation/review/s2-hardware-system-constraints-2026-06-19/**
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
  - 12-log/**
  - 00-dashboards/**
inputs:
  - Zotero collection: 60 Project Packs / 1_DS_I / hardware
  - 04-supportDesign/thesis-benchmark/s2-hardware-capability-register.md
  - 04-supportDesign/thesis-benchmark/s2-e1-minimum-safety-distance-benchmark.md
outputs:
  - automation/review/s2-hardware-system-constraints-2026-06-19/processing-report.md
  - automation/review/s2-hardware-system-constraints-2026-06-19/hardware-system-constraint-matrix.md
  - optional update: 04-supportDesign/thesis-benchmark/s2-hardware-capability-register.md
result_path: automation/review/s2-hardware-system-constraints-2026-06-19/hardware-system-constraint-matrix.md
review_report_path: automation/review/s2-hardware-system-constraints-2026-06-19/processing-report.md
handoff_model: codex
notes: "Use Beaver MCP and Zotero read-only. Do not mutate Zotero. Do not create canonical evidence notes unless explicitly justified by existing repo process. Prefer staged synthesis rows over ontology expansion."
---

# Ground S2 hardware constraints from Zotero hardware folder

## Objective

Use Beaver MCP and the Zotero database to inspect the collection:

`60 Project Packs / 1_DS_I / hardware`

Convert hardware papers, manuals, datasheets or hardware-relevant sources into concrete constraints for the S2-E1 experiment system model. This is not a general literature review. It is a rig-design constraint extraction task.

## Agent execution contract

Work autonomously until the required outputs exist and the acceptance criteria are satisfied.

- Act once you have enough information. Do not re-derive established decisions, survey irrelevant alternatives, or ask for permission to do reversible work already authorised by this task.
- Pause only for a destructive or irreversible action, a real scope change, missing credentials/access, or missing information that only Tye can provide.
- If blocked, write a blockage section in the processing report with: exact blocker, attempted route, partial outputs completed, and the next human action needed.
- Before reporting progress or completion, audit every claim against a tool result from this run. Do not claim a file was created, read, or updated unless you can point to the actual result.
- Keep final communication outcome-first and concise: files changed, what they contain, blockers, and next human decision if any.
- Do not reveal private chain-of-thought. Show concise rationale only where it changes a design decision.
- Do not add features, ontology, abstractions, evidence notes, or future-work branches beyond this task.

## Current experiment context

S2-E1 is currently framed as:

> Can a close-proximity collaborative robotic system avoid multiple dynamic obstacles to a minimum safety distance while still providing useful bounded support in a constrained process task?

The current physical route uses a tabletop or full-depth mock-up of an access-limited/glovebox-like workspace, a uArm Swift Pro-class desktop robot, candidate D435i/external sensing, optional end-effector vision, and coin-cell-like small inert objects.

## Required repository behaviour

1. Treat Zotero and Beaver MCP as read-only.
2. Do not mutate Zotero collections, metadata, PDFs, notes or annotations.
3. Do not alter ontology or standards files.
4. Do not create canonical evidence notes unless the repo process clearly supports it and there is no duplicate.
5. Stage uncertain findings under `automation/review/s2-hardware-system-constraints-2026-06-19/`.
6. Keep the output pragmatic and system-facing.

## Procedure

1. Resolve the Zotero collection path and record the exact collection name/key.
2. Inventory every item in the collection.
3. Read each item that plausibly constrains S2-E1 hardware, CAD, sensing, calibration, end-effector choice, safety boundary, or pilot logging.
4. Extract only system-design facts. Ignore general motivation, unrelated robotics claims, and broad background.
5. Write the processing report.
6. Write the hardware system constraint matrix.
7. Check the current hardware capability register for conflicts or missing stable facts.
8. Update the hardware capability register only if the new fact is stable, source-backed and directly useful.
9. Re-read the acceptance criteria and verify that every required output exists.

## Extraction targets

For each relevant item in the Zotero hardware folder, extract only information that constrains the experiment system model:

1. physical geometry;
2. reachability;
3. mounting and fixture requirements;
4. workspace/enclosure constraints;
5. camera/sensor placement;
6. calibration and transform-chain requirements;
7. gripper/end-effector implications;
8. object handling limits;
9. timing, latency, communication or logging constraints;
10. safety limitations and warnings;
11. failure modes;
12. buildability implications for Monday's CAD and later pilot work.

For each useful item, capture:

- source item and citekey if available;
- page number, PDF anchor, section, or manual heading;
- extracted fact or constraint;
- experiment-system layer;
- implication for S2-E1;
- whether it affects CAD, sensing, calibration, end-effector choice, pilot logging, or safety boundary.

## Required output 1: processing report

Create:

`automation/review/s2-hardware-system-constraints-2026-06-19/processing-report.md`

Include:

- collection resolution;
- item inventory;
- which items were read;
- which were useful;
- which were irrelevant;
- unresolved missing hardware information;
- whether any source conflicts with the current hardware capability register.

## Required output 2: hardware system constraint matrix

Create:

`automation/review/s2-hardware-system-constraints-2026-06-19/hardware-system-constraint-matrix.md`

Use this structure:

```markdown
---
title: S2 hardware system constraint matrix
artifact_type: workflow
status: done
created: 2026-06-19
project: phd-research
drm_phase: DS-I-to-PS
source_collection: "Zotero: 60 Project Packs / 1_DS_I / hardware"
---

# S2 hardware system constraint matrix

## Purpose

## Constraint matrix

| System layer | Constraint | Source | Design implication | Affects | Confidence | Action |
|---|---|---|---|---|---|---|

## CAD implications for Monday

## Pilot build implications

## Sensing and calibration implications

## End-effector implications

## Open technical questions
```

## Optional update

Update `04-supportDesign/thesis-benchmark/s2-hardware-capability-register.md` only if the hardware folder adds factual constraints that are stable, source-backed and directly useful. Keep any update concise. Do not rewrite the file.

## Acceptance criteria

The task is complete only if it answers:

> Which hardware facts from the Zotero hardware folder materially constrain the S2-E1 system model, CAD discussion, sensing route, calibration plan, gripper route and pilot logging?

Completion requires:

- processing report exists;
- hardware system constraint matrix exists;
- all relevant Zotero hardware items are accounted for;
- every material claim has a source anchor or is marked unresolved;
- any optional active-file update is minimal and justified;
- no denied paths, Zotero state, or ontology files are mutated.
