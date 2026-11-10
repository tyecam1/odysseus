---
title: Enforce economical review-model pool across the estate
status: inbox
priority: high
owner_repository: tyecam1/odysseus
task_class: routing-review-cost-control
created: 2026-11-10
updated: 2026-11-10
---

## Objective
Make the operator's 2026-11-10 review preference **operational**, rather than merely documented. Reviews across Odysseus, Misumi and obsidian-PhD must prefer the cheapest *qualified and available* reviewer among **Haiku 5.5, Terra 6.1, GLM-Flash**. **No automatic Sol, Opus, Fable or similarly premium reviewer.** Implement only in the existing Odysseus routing/backend authority.

## Context
The operator's persistent preference has been committed to `AGENTS.md`,
`docs/aoteru-model-host-routing-contract.md` and
`docs/subscription-model-currency-policy.md` on 2026-11-10.
The current Codex subscription resolver selects newest premium regardless of review role,
and the existing paid provider adapters do not establish all three requested review routes.
Written policy is **not** runtime enforcement.

## Scope
- Read live `dev`, existing estate dispatch/resolver/worker config, provider qualification and review interfaces before editing.
- Distinguish review tasks from implementation, architecture, protected verification and canonical PhD research promotion.
- Route cheap bounded review by live eligibility, qualified host, available provider and observed quality; verify exact current provider model/Flash variant at dispatch, never assume the names are deployed.
- Run deterministic checks first, review only changed scope/new evidence, and suppress unchanged-HEAD repeat reviews.
- Premium review outside the three models needs an explicit operator approval for that review, recorded reason and quota estimate. If no qualified cheap verifier is available, preserve review debt; do not silently use Sol.
- Preserve mandated independence, safety/security/ethics/evidence and merge permissions. No new router or duplicated policy.
- Record actual reviewer, commit, scope, calls/tokens/quota where available, findings and exceptions.

## Acceptance
1. Tests cover all three eligible routes, unavailable/unqualified models, nonreview behaviour, unchanged-HEAD deduplication, premium refusal and explicitly approved exception.
2. Existing nonreview subscription currency, Astra opt-in, lease and authority gates remain intact.
3. Test required cross-provider independence and disallow implementing agent self-approval.
4. Live provider-level canary confirms actual identity and end-to-end reviewer outcome, or records a truthful unavailable blocker for each unqualified lane.
5. Update central config/docs, deploy to active workers, and verify real usage routing and quota reduction before marking done.
