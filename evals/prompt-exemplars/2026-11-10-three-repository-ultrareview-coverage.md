---
exemplar_id: 2026-11-10-three-repository-ultrareview-coverage
title: Three-repository cumulative Ultrareview preparation with quantified coverage
status: candidate
captured_at: 2026-11-10
capture_basis: operator-directed-cross-repository-review
source_surface: chatgpt
source_reference: tyecam1/odysseus:automation/review/agent-tasks/inbox/2026-11-10-three-repository-ultrareview-consolidation.agent-task.md
task_context: Prepare one existing-work ultrareview branch for each of Misumi, Odysseus and obsidian-PhD
applications: []
evaluations: []
supersedes: []
---

# Capture rationale

Combines provenance-preserving dependency-aware review-branch synthesis, diff-budget admission control and explicit free-credit operator release. It makes actual reviewed coverage auditable, while keeping the three repository ownership domains and sensitive research gates intact.

## Reusable behaviours

- Quantified coverage accounting over multiple dependent feature branches.
- Separated preparation from consumption of scarce premium review credits.
- Graph/merge ancestry and historical research gates remain explicit; no fake all-branches inclusion.
- Parallelise reconnaissance while serialising shared branch mutations.

## Assumptions / limits

- Run from the registered Odysseus controller checkout; live host routing, eligibility, accessible branches, credits and CLI limits must be reverified.
- The prompt is captured before any application as an unevaluated candidate exemplar; it does not prove review execution or create a new global initialiser.
- Intended model: authenticated current Fable (5.2 at capture) at high effort, not a standing version pin; escalation and alternatives follow Odysseus routing policy.

## Exact prompt

```text
From the registered local Odysseus controller checkout, follow AGENTS.md and execute the existing task card `automation/review/agent-tasks/inbox/2026-11-10-three-repository-ultrareview-consolidation.agent-task.md` using live aoteru preflight. Inventory recent work and source SHA ancestry across Misumi, Odysseus and obsidian-PhD; reconcile registered host worktrees, draft PR stacks and protected research gates. With isolated worktrees and normal merges, prepare three provenance-manifested, size-eligible Ultrareview candidate branches with maximum truthful coverage, measured against each authoritative base. Parallelise only independent read-only inventory/tests; record excluded or blocked work explicitly. Run deterministic and independent verification, freeze review SHAs, and present three exact launch commands. Do not launch Ultrareview, consume credits, merge to production, rewrite history, or promote research evidence without my separate approval.
```
