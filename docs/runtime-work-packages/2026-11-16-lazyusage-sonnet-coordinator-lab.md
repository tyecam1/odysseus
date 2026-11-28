# Sonnet coordinator retake — what was kept, what was rejected (2026-11-28)

This is the fresh delivery for card `2026-11-16-lazyusage-sonnet-coordinator-lab`. The previous
delivery (commit `129540ec`, 2026-11-21) was REJECTED in independent review and never merged: it
deleted the `CLAUDE_CONFIG_DIR` stub (`disableAllHooks` settings write, credentials symlink, env
override) and its test, replacing a live-proven isolation control (hook canary NOT firing,
2026-11-18) with unevidenced `--safe-mode --restricted` flags while re-exposing the operator's real
user config.

**Kept unchanged from dev (the rejection boundary):** the stub construction, the credentials
symlink, the `CLAUDE_CONFIG_DIR` env on every claude-lane subprocess (auth attestation AND
inference), and dev's launcher contract. The stub stays the primary isolation control.

**Taken from the rejected delivery (the retake-worthy parts, verified by the independent review):**

- coordinator `_ordered`: advisory plan order is now a tie-break WITHIN equal (queue bucket, owner
  priority) — a model plan can no longer promote a task past a higher owner priority;
- coordinator `_meter_tokens`: the dispatch token reservation is reconciled — measured usage
  releases the estimate, a call that definitely did not execute releases it, anything else keeps it;
  the advisor lane (no reservation) keeps dev's conservative charging, a fragment booking at least
  the estimate;
- estate_router `execute_claude`: endpoint-override refusal (first-party Anthropic endpoint only),
  pre-inference auth attestation (`auth status` must attest a first-party claude.ai subscription;
  run under the stub env), a per-call deadline carried from the auth check through inference, and
  `--tools "" --disallowedTools "*"` as defence in depth ON TOP of the stub;
- config: `routine_lanes` prefers claude-sonnet, but the lane stays UNQUALIFIED for coordination
  until the host records the exact-5.5 + unattended permission/billing attestation in
  `config/estate.yaml` (`qualified_executors` must name `claude-sonnet`; plain `claude` covers the
  advisory lane only). The coordinator refuses a plan whose effective model is not attested 5.5 and
  never reuses a legacy Sonnet plan. Until then GLM-Flash / GLM serve as today: behaviour is
  unchanged on the live estate.

**Recorded behavioural divergence (Opus condition, 2026-11-28):** the GLM-Flash lane now maps to
executor `glm-flash`, which is NOT in the host's `qualified_executors` (only plain `glm` is, for the
standard GLM route). Routine coordinator turns therefore run **glm-standard, not glm-flash**, until
GLM-Flash's own qualification is recorded in governed config — the same fail-closed boundary as the
claude-sonnet lane (the `test_standard_glm_qualification_does_not_authorise_flash` test pins it).
This is deliberate and honest: dev's mapping let flash ride the standard lane's qualification, which
the qualification card explicitly rejects ("Flash requires its own qualification").

**Rejected parts NOT taken:** stub removal; the "host qualification is recorded" wording that
implied a coordination qualification exists; marking the lane qualified without evidence.

Tests: `tests/test_lazy_usage_coordinator.py` carries the new guards (owner-priority fence,
qualification boundaries, endpoint refusal, unattested-subscription refusal, legacy-plan non-replay,
token reservation); `tests/test_lazy_usage_delivery.py` / `test_lazy_usage_reliability.py` keep dev's
stub-isolation tests. Card acceptance (a live Sonnet-coordinated activation on the lab) remains
operator-gated until the qualification evidence exists.
