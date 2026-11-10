---
exemplar_id: 2026-11-10-three-repository-ultrareview-lab-route
title: Three-repository Ultrareview preparation using verified lab route
status: candidate
captured_at: 2026-11-10
capture_basis: operator-correction-of-controller-worker-boundary
source_surface: chatgpt
source_reference: tyecam1/odysseus:automation/review/agent-tasks/inbox/2026-11-10-three-repository-ultrareview-consolidation.agent-task.md
task_context: Lab-hosted Git integration for three independent repository Ultrareview candidates
applications: []
evaluations: []
supersedes:
  - 2026-11-10-three-repository-ultrareview-coverage
---

# Correction

Supersedes the earlier candidate's ambiguous "registered local Odysseus controller checkout" framing. The laptop is a controller, not a worker. Lab SSH and Claude/Fable eligibility must be verified rather than presumed.

## Reusable behaviours

- Controller/worker boundaries remain explicit within a compact task prompt.
- Evidenced host and model route qualification precedes workspace mutation.
- Effort escalates through separate qualified sessions, not an assumed in-place switch.
- Coverage and scarce review-credit release are independently gated.

## Exact prompt

```text
Execute Odysseus PR #265's three-repository Ultrareview preparation task. Run Git integration and tests only on the verified lab worker `hz2-workstation`, through existing Odysseus preflight, host eligibility, checkout and write-lease routing; the laptop is controller only. Verify the lab's actual available Claude/Fable route and remote transport; do not assume SSH or a local laptop checkout is authorised. Inventory live Misumi, Odysseus and PhD work and dependencies, then prepare one provenance-preserving, size-eligible review branch per repo. Use Low effort/deterministic workers by default; explicitly dispatch Medium for nontrivial dependency/conflict decisions and High for consequential architectural, authority or research-integrity conflicts, returning to Low afterwards. Independently verify tests and report frozen SHAs, included/excluded coverage and three launch commands. Do not merge to production, rewrite history, promote research evidence or consume Ultrareview credits.
```
