---
exemplar_id: 2026-11-12-fable-misumi-ftl-visual-acceptance-brief
title: "Fable: Misumi FTL HUD design adjudication and cheaper-model handoff"
status: candidate
captured_at: 2026-11-12
capture_basis: agent-nomination
source_surface: "ChatGPT PhD Research strategic directive discussion"
source_reference: "2026-11-12 limited Fable access strategy"
task_context: "Single small visual-design decision pass. Current HUD increment is merged; defect repair remains separate."
applications: []
evaluations: []
supersedes: []
---

# Capture rationale

Uses high-value design judgement to turn aesthetic intent into acceptance criteria while separating security defects, visual iteration and preserved 3D worlds.

## Reusable behaviours

- Audit actual interface constraints and prior design decisions before proposing style.
- Provide a testable visual hierarchy and state inventory rather than generic redesign adjectives.
- Reserve screenshot iteration and implementation for cheaper models.

## Task-specific assumptions / limitations

- Do not modify the ratified PS2 3D scenes, persona authority or backend contracts.
- Security/privacy defects and real-device verification take precedence over cosmetic deployment.

## Exact prompt

```text
Work inside live misumi on main. Read AGENTS, ratified PS2 persona design, the 16 October FTL HUD ambition, merged HUD PR #105 and outstanding defect task from PR #109. PR #108 is a synthetic ultrareview and must never be merged. Preserve the existing 3D scenes, characters, camera and lighting.

Judge the current 2D ship HUD and operator flow against the actual 1024x768 kiosk, keyboard/touch/voice states and Odysseus-backed status. Identify the few highest-leverage visual and interaction changes: hierarchy, navigation, pixel typography, 8/16-bit component language, steel/bone/amber palettes, alert/status semantics and readable space backgrounds. Distinguish visual problems from functional/security defects. Do not redesign an unavailable screenshot from imagination.

Deliver one compact acceptance brief with current/target state comparisons, a small component/token specification, required screenshots and interaction-state checks, and at most three ordered, narrowly scoped PRs for a cheaper implementation model. If a real screenshot is accessible, mark up one representative screen; otherwise state that visual validation is pending. No overhaul, autonomous deployment, new endpoints or edits to 3D assets.
```
