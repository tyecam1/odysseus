---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-19-s2-cad-to-system-model-supervision-pack
title: Convert S2 CAD into supervisor-facing system model pack
status: done
priority: high
task_type: system-modelling-diagram-synthesis
created_by: chatgpt
created_at: 2026-06-19T00:00:00+01:00
executor: claude_subscription
execution_mode: handoff
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
allowed_paths:
  - automation/review/agent-tasks/inbox/2026-06-19-s2-cad-to-system-model-supervision-pack.agent-task.md
  - automation/review/s2-system-modelling-2026-06-19/**
denied_paths:
  - 00-dashboards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
inputs:
  - 04-supportDesign/thesis-benchmark/s2-e1-minimum-safety-distance-benchmark.md
  - 04-supportDesign/thesis-benchmark/s2-e1-system-design-research-grounding.md
  - 04-supportDesign/thesis-benchmark/s2-hardware-capability-register.md
  - 10-inbox/s2-e1-cad-mockup-constrained-safety-distance-benchmark.md
  - 10-inbox/s2-e1-open-decisions-for-2026-06-22-supervision.md
  - 12-log/26-06/26-26/supervision-prep-2026-06-22.md
outputs:
  - automation/review/s2-system-modelling-2026-06-19/s2-cad-system-model-supervision-pack.md
result_path: automation/review/s2-system-modelling-2026-06-19/s2-cad-system-model-supervision-pack.md
handoff_model: claude
notes: "Use existing CAD screenshots or user-provided CAD notes if available locally. Do not invent exact CAD dimensions beyond documented values. Keep this supervisor-facing and decision-oriented."
---

# Convert S2 CAD into supervisor-facing system model pack

## Objective

Turn the existing S2-E1 CAD work into a concise supervisor-facing system model pack for the 2026-06-22 Erfu meeting.

This is not a polished CAD task. The output should make the experiment architecture, spatial logic, unresolved decisions and Monday asks visible.

## Agent execution contract

Work until the required output exists and the acceptance criteria are satisfied.

- Act once enough information exists. Do not re-derive established decisions, narrate unused options, or ask permission to write reversible review-side files.
- Pause only for a real blocker: destructive action, scope change, missing access, or missing CAD/screenshots that cannot be substituted by documented dimensions.
- If CAD screenshots are unavailable, still complete the pack using documented dimensions and add a short `CAD screenshots still needed` section.
- Before reporting completion, check every progress claim against a file read or file write from this run.
- Final response: output path, what it contains, unresolved decisions. No excess commentary.
- Do not add experiment scope, S3/S4 content, or visual polish tasks beyond the pack.

## Current experiment boundary

S2-E1 is a minimum safety-distance dynamic-obstacle benchmark for constrained manipulation. The robot must perform one useful bounded support action while preserving and logging a stated minimum safety distance from staged dynamic obstacles.

Current critical CAD issue:

- CPI glovebox/manual-depth reference is approximately 700-750 mm.
- Current uArm reach envelope is approximately 640 mm diameter.
- Therefore the CAD must not imply whole-box service. It should either preserve full-scale geometry with an active reachable sub-volume or justify a tabletop abstraction.

## Required input inspection

Read the active notes before writing:

1. `04-supportDesign/thesis-benchmark/s2-e1-minimum-safety-distance-benchmark.md`
2. `04-supportDesign/thesis-benchmark/s2-e1-system-design-research-grounding.md`
3. `04-supportDesign/thesis-benchmark/s2-hardware-capability-register.md`
4. `10-inbox/s2-e1-cad-mockup-constrained-safety-distance-benchmark.md`
5. `10-inbox/s2-e1-open-decisions-for-2026-06-22-supervision.md`
6. `12-log/26-06/26-26/supervision-prep-2026-06-22.md`

## Procedure

1. Read the six required inputs.
2. Extract only the meeting-relevant spatial and system decisions.
3. Produce the review-side supervision pack.
4. Check that both Mermaid diagrams are syntactically plausible.
5. Check that the pack does not imply full glovebox service, safety compliance, lost-part recovery as E1, or S3/S4 claims.
6. Include any concise supervisor-facing paste text inside the review pack; do not edit the supervision note.
7. Re-read the acceptance criteria and verify completion.

## Required output

Create:

`automation/review/s2-system-modelling-2026-06-19/s2-cad-system-model-supervision-pack.md`

Include:

- one-sentence decision needed;
- what the CAD currently proves;
- what the CAD does not prove;
- spatial model table;
- system architecture Mermaid diagram;
- control/safety loop Mermaid diagram;
- CAD views to show Monday;
- decisions to ask Erfu;
- what to ask Richard/NMIS later;
- what to ask Dino later;
- what not to discuss Monday.

## Diagram requirements

Include two Mermaid diagrams:

1. System architecture: mock-up, robot, human/operator, obstacle, sensor, state estimate, safety supervisor, robot response, evidence log, S2-S5 evaluation path.
2. Control/safety loop: minimum-distance estimate, nominal/caution/stop/reset states, robot support action, human authority, event logging.

Use existing wording from the active notes. Do not create a new experiment scope.

## CAD view requirements

Define exactly which CAD screenshots or views should be shown Monday:

1. full plan view with glovebox depth and port spacing;
2. robot reach envelope overlaid on active sub-volume;
3. camera/sensor field-of-view placeholder;
4. support-action zone and fixed return/presentation zone;
5. staged hand/arm or tool/container obstruction path;
6. minimum safety-distance envelope.

## Hard constraints

- Do not turn CAD into the research contribution.
- Do not reopen superseded S2 notes.
- Do not add lost-part recovery unless explicitly labelled S2-E2 or conditional on support-action approval.
- Do not claim safety compliance.
- Do not imply the uArm covers the whole glovebox.
- Do not make S2 a perceived-safety or advanced-control study.

## Acceptance criteria

The output must let Tye walk into Monday's meeting and ask:

1. Is this a valid first S2 benchmark boundary?
2. Should the CAD preserve full CPI geometry with an active reachable sub-volume, or use a tabletop abstraction?
3. What exact support action makes the robot useful rather than merely obstacle-aware?
4. Which first obstacle class and local S2 comparator should be used?
5. Which sensing/logging route is sufficient for the pilot?

Completion requires:

- the supervision pack exists;
- the pack contains both required diagrams;
- every CAD view needed for Monday is listed;
- the pack separates what CAD proves from what it does not prove;
- any proposed supervision-prep text remains inside the review-side pack;
- no denied paths or superseded notes are modified.
