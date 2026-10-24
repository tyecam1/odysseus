# Subscription model currency policy

Status: proposed implementation, 2026-10-22. Authority: Odysseus routing; research
repositories must reference, not duplicate, this runtime policy.

## Invariant

For **subscription-backed** inference, the model version and capability tier are
not user-selectable or pinned by task/repository/prompt. Only reasoning **effort**
may be selected. Every new invocation must use the newest eligible premium
general-purpose model reported by the authenticated provider/CLI at dispatch,
not whichever model a stale ~/.codex/config.toml names. A candidate that
cannot be verified is not a reason to fall back to an older model.

This is separate from local models, embeddings, deterministic scripts, and
non-subscription APIs. Their qualification and benchmark controls remain intact.
It does not enlarge write permissions, replace independent verification or
relax PhD research authority.

## Codex subscription, current implemented path

- `src/subscription_model_policy.py` calls `codex debug models` on the chosen
  worker, using that CLI's authenticated, account-specific model catalogue.
- It selects the greatest numeric model version among visible premium
  `gpt-N[.M]` and `gpt-N[.M]-sol` models; at the same version an explicit
  Sol slug is preferred over generic GPT. This is model *currency*, not
  route-cost optimization. Older Luna/Terra models and historical Codex
  models are not eligible subscription execution fallbacks.
- **Astra exclusion (owner standing rule, 2026-10-22):** `gpt-N[.M]-astra`
  slugs are never selected automatically; Astra requires explicit human
  instruction and, at runtime, the operator-set `AOTERU_ALLOW_ASTRA=1`
  opt-in. Without it, Astra entries are invisible to the selector.
- A **minimum version floor**, currently GPT 6.0 (the newest release the
  live authenticated catalogue actually offers as of 2026-10-24), prevents
  an out-of-date catalogue from silently selecting a retired premium tier.
  This is a safety condition, not an operator model knob. Later eligible
  versions are auto-selected. The floor must never be pinned above what the
  live catalogue offers; doing so fails dispatch closed against reality.
- On dispatch the code passes `--model <resolved>` explicitly on BOTH
  read-only and workspace-write runs. The only configurable inference dial
  is `AOTERU_SUBSCRIPTION_REASONING_EFFORT` (low, medium, high, xhigh, max;
  default high), passed as `model_reasoning_effort`.
- Success results carry `concrete_model`, `reasoning_effort`, and catalogue
  provenance. A missing CLI, malformed catalogue, unavailable premium model,
  outdated catalogue, or invalid effort fails closed. No outdated retry.
- `codex debug models` is an authenticated CLI view which may itself be stale
  or incomplete because provider rollout and client versions differ. It is
  **not proof** that no newer model exists globally. Update the CLI and
  investigate discrepancies whenever known provider releases exceed this view.
  Do not dump the entire debug catalogue into logs: it may contain large
  instruction templates.

## Other subscription execution paths

- Claude Code: use the CLI's **`opus` rolling family alias**, not a
  versioned model ID, and keep its CLI updated. Any configured aliases or
  environment substitutions that pin an older snapshot are non-compliant.
  The alias must be independently verified against its effective model
  before claiming runtime enforcement; provider safety substitutions and
  client-version drift can still occur.
- Other subscription CLIs (e.g. GLM): no executable latest-model attestation
  is yet installed here. They must NOT be claimed compliant or silently
  routed under this policy until a tested provider-specific latest resolver,
  effective-version record and fail-closed guard exist.
- Historical research reports should retain the exact model originally used.
  Normative instructions, runnable templates and router configuration must
  never encode an old model ID as the default.

## Verification and activation

1. Before merging, run
   `pytest tests/test_subscription_model_policy.py tests/test_estate_router.py -q`
   and the established estate worker/write-lane tests.
2. Run real `codex debug models` using the same account and binary selected
   by Odysseus on the lab worker. Independently confirm the newest
   subscription-model release/access and that the resolved model matches.
3. Exercise an advisory run and a separately lease-authorised write run,
   including failure modes. Confirm no old-model fallback and that results
   contain the actual model ID and effort.
4. Audit user-level CLI config, existing automation environments, active
   Claude Code scripts, other research repositories and model-change rollout.
5. Deploy to actual workers and monitor divergences. GitHub code alone does
   not update a running estate.

**Scope limit:** no software can guarantee instant migration at every provider
release without a reliable real-time vendor feed and an authenticated eligibility
check. This implementation assures newest according to its live CLI catalogue
with a current known floor, and reports uncertainty rather than guessing.
