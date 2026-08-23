---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-23-aoteru-legacy-preferences-functions-review
title: "Review legacy Odysseus preferences and functions for Aoteru"
status: backlog
priority: medium
task_type: bounded-legacy-convergence-review
created_by: chatgpt
created_at: 2026-08-23T23:03:00+01:00
executor: claude-sonnet-5
execution_mode: finite-evidence-led-review
repo: tyecam1/odysseus
branch: dev
---
# Review legacy Odysseus preferences and functions for Aoteru

## Mission

Review the previous Odysseus system and determine which user preferences, operator-facing behaviours, and useful functions should be preserved, adapted, or deliberately retired in the current Aoteru/Odysseus architecture.

This is a convergence review, not a mandate to recreate the old system.

## Scope

Use the preserved legacy implementation at `/home/agent/projects/odysseus` where available, plus its configuration, docs, tests, UI/operator surfaces, and durable data structures. Compare against the current implementation at `/home/agent/projects/odysseus-aoteru` and the current programme-state/architecture documents.

Review especially:
- explicit user/operator preferences and defaults;
- interaction and response preferences encoded in configuration or UI;
- useful commands, workflows, utilities, integrations, and convenience functions;
- recurring automation or memory behaviours;
- model/routing controls exposed to the operator;
- repository/workspace handling;
- status, history, explainability, recovery, and administrative functions;
- functions that became obsolete because the current architecture provides a cleaner equivalent.

Do not treat accidental legacy behaviour, architectural debt, duplicated orchestration, insecure exposure, stale hardware assumptions, or historical implementation details as requirements.

## Method

1. Inventory the legacy preference and function surfaces from code and documentation rather than relying on names or recollection.
2. Map each material item to the current system as one of:
   - `already-covered`;
   - `preserve-as-is`;
   - `adapt-minimally`;
   - `superseded`;
   - `retire`;
   - `needs-operator-decision`.
3. For anything not already covered, state the concrete user value, current gap, smallest compatible implementation, security/governance implications, and evidence that the capability was genuinely useful rather than merely present.
4. Prefer consolidation into existing Aoteru/Odysseus surfaces over adding parallel systems.
5. Separate user preference migration from feature migration: preferences should remain easy to inspect/change and must not be buried in model prompts or copied wholesale from legacy state.
6. Produce a ranked, bounded recommendation. Do not implement optional items during the review unless a defect prevents reliable comparison.

## Deliverable

Create one concise durable review document containing:
- legacy-to-current mapping table;
- preferences worth retaining;
- functions worth retaining or adapting;
- functions intentionally retired/superseded;
- unresolved operator decisions, if any;
- a minimal ranked implementation backlog only for material gaps.

Where feasible, link each recommendation to the exact legacy and current code/config/docs that support it.

## Acceptance

The review is complete when:
- material legacy operator preferences and functions have been systematically compared;
- no recommendation depends only on nostalgia or undocumented assumptions;
- every proposed carry-forward has explicit user value and an identified current home;
- obsolete/insecure/duplicative legacy behaviour is explicitly rejected rather than silently revived;
- the result does not reopen the completed Aoteru convergence programme or create an unbounded development loop.

## Trigger / stop condition

Run only after the current laptop activation closeout is complete and the system has entered normal use, unless a real usage problem makes this review necessary sooner.

Stop after the review and bounded recommendations. Any implementation should be commissioned separately from the ranked findings.