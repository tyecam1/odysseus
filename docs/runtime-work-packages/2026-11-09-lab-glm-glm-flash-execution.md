# Lab GLM and GLM Flash execution: partial evidence (steps 1-2 only)

Task: `2026-11-09-qualify-glm-and-glm-flash-on-lab-odysseus`. Status of this document: **partial**. Only reconciliation and the host-local launcher smoke test were done. No backend integration, no `/api/estate/run` proof, no write-mode proof and no Flash qualification exist yet; the task stays unfinished.

## Reconciliation (read-only, 2026-11-09, lab `hz2-workstation`, `dev` at `6a67f639`)

- PR #38 (candidate GLM paid executor) is **closed unmerged**; PR #133 (commissioning and smoke-test gap record) is merged. Neither proves a live backend route.
- `src/` and `config/` contain no GLM paid-provider adapter or dispatch path; `config/models.yaml` mentions GLM only in a comment about an earlier local-model list. Codex remains the only qualified paid dispatch implementation, as the task states.
- The lab has a host-local launcher `~/.local/bin/claude-glm` (a Bourne shell script) which, by its own header, owns endpoint, model and credential setup. Its default model is `glm-5.3` (override variable `GLM_MODEL`). No separate Flash launcher exists on the lab and the launcher names no Flash model, so **Flash availability and entitlement are unverified**. No Flash model identity was assumed.
- Credential values were not inspected, printed or copied by this work; only non-credential lines of the launcher were read. The launcher itself may have read its stored credential when it ran.

## Launcher smoke test (standard GLM only)

Run on the lab with stdin supplied by a pipe, no terminal, 120 s timeout, exit status captured.

| Item | Result |
|---|---|
| Command | `printf 'Reply with exactly this string and nothing else: %s
' "$S" \| timeout 120 ~/.local/bin/claude-glm --print` on the lab, at about 2026-11-09 17:05 UTC (the sentinel epoch 1794241500 is the observed value) |
| Sentinel | `SENTINEL-1794241500-QX7` |
| Exit status | 0 |
| Response | `SENTINEL-1794241500-QX7`, identical to the sentinel |
| Model | the client reported `glm-5.3` in its stderr `unrecognized_model` notice; that notice does not attest which model served the response, and provider-side attestation was not obtained |
| Scope | launcher only; not an Odysseus backend test |

A launcher-only pass does not satisfy the task's acceptance, and it does not grant independent-review equivalence.

## Design decision (Sol `gpt-6-sol` read-only consultation, 2026-11-09)

Provider selection is an **explicit** `paid_provider: "glm"` field on `/api/estate/run`, validated against the paid-provider registry and host qualification. Omission keeps Codex. Unknown or unqualified providers are rejected; Flash is never inferred from a GLM request. No new router, queue, lease owner or credential store.

| Phase | Scope | Rollback |
|---|---|---|
| 1 | Explicit GLM **read-only advisory** only: `paid_provider` field in `RunTaskEnvelope.to_task()` and `DelegationPreflightUnit`; provider-aware `_resolve_paid_provider`, `_select_host`, `_dispatch_read_only`; `execute_glm` plus a dispatch-table entry; `glm-readonly` verb, readiness and inventory in `estate_worker.py`; `glm` health keyed separately in the existing `provider_outcome` records; registry entry in `config/models.yaml`; `glm` added to a host's `qualified_executors` only after a real backend proof. | remove host qualification and the registry route |
| 2 | Flash: discover entitlement and launcher; separate `glm-flash` key and adapter after its own proof; until then `provider_unqualified`, no substitution. | remove `glm-flash` qualification |
| 3 | Per-route write qualification under the existing lease, worktree, recovery and review gates (`execute_write_via_worker`, `_WRITE_KINDS`, `_validate_start`, `_run_spooled`). | remove that route's write qualification |
| 4 | Quota-only Codex-to-qualified-GLM failover; explicit `no_qualified_fallback` when none. | disable automatic failover |

Typed errors: `launcher_missing`, `entitlement_missing`, `auth_failed`, `quota_exhausted`, `rate_limited`, `transport_unreachable`, `timeout`, `model_mismatch`, `sandbox_failure`, worker or placement failure. Quota is classified from trusted failure evidence, never echoed prompt text. `--print` alone is not a read-only boundary; phase 1 must enforce one (for example the read-only tool allow-list) and test it.

Main risks to live Codex: GLM readiness displacing Codex in `_select_host`, an explicit request overriding the `code-strong` default, shared health keys, and any edit to `_execute_codex_with_sandbox` in phase 1 (left unchanged).

## Phase 1 live proof (read-only GLM, real router and worker path, in-process), 2026-11-10

Run on the lab (`hz2-workstation`) from a worktree containing the qualification change, with `DATABASE_URL` pointing at a throwaway SQLite file created for the run (no production database touched, application server not started). The request went through `estate_router.run_task` with the capability `code-strong`, `allow_paid_escalation` true and `paid_provider: "glm"`; route resolution, host qualification, the `glm-readonly` worker verb over the local transport and the restricted launcher (`--tools Read,Grep,Glob`, write and agent tools disallowed, `--strict-mcp-config`, `--bare`, `--disable-slash-commands`, `--no-session-persistence`) all ran for real. This is **not** an HTTP-level `/api/estate/run` call; that is a separate follow-up after deploy.

| Item | Observed |
|---|---|
| Prompt | one line asking for the exact string `GLM-PROOF-<epoch>` and nothing else (epoch 1794313009 in the recorded run) |
| Response | exactly the sentinel (`sentinel_match: True`) |
| Route | `executor: glm`, `host: hz2-workstation`, alias `code-strong`; reason "local capability was insufficient; glm executed on hz2-workstation read-only" |
| Execution record | `provider: glm`, `host_id: hz2-workstation`, `exit_code: 0`, `ok: true`, `latency_ms` about 4,000, `concrete_model: null`, **`model_unverified: true`** (the effective model is not attested; the client only reports `glm-5.3`, which is not an attestation) |
| Backend trace | a decision row for the task (`executor: glm`, `escalation_reason: insufficient_capability`) and a `provider_outcome` row for `glm` with health `ok`, recorded separately from Codex |
| Provider health before the run | `unknown`, "no recorded outcome; initial attempt permitted", allowed |

Negative controls (same setup, nothing launched; no `claude-glm` process existed afterwards):
- `paid_provider: "glm"` with `mode: implementation` and a repository: refused, `error_code: provider_unqualified`, "provider 'glm' has no qualified write route", `executed: false`.
- `paid_provider: "nonesuch"`: refused, `error_code: unknown_provider`, `executed: false`.

Not shown and still open: the HTTP `/api/estate/run` path after deploy, a Codex-quota-to-GLM failover (phase 4, not implemented), any write route (phase 3), GLM Flash (phase 2), effective-model attestation, and a run through the restarted production service. Rollback: revert the one-line `qualified_executors` change in `config/estate.yaml` and restart `odysseus-aoteru-lab.service`.

## Open, in order

1. Flash: find a genuine entitlement and concrete model identity, or record the precise blocker. Any credential or account action belongs to the operator and is not attempted here.
2. Add the smallest provider adapter to the central paid-provider registry and `/api/estate/run`, with typed per-provider quota and auth errors, no overlapping launches and no silent substitution.
3. Real `/api/estate/run` bounded runs for each qualified route; one separately authorised write-mode run per route under the existing lease and worktree rules; Codex-quota-to-qualified-GLM routing test; deployment, rollback and independent verification.

## Rollback

None needed: no code, configuration or service was changed.
