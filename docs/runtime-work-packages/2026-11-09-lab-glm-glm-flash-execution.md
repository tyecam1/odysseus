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

## Open, in order

1. Flash: find a genuine entitlement and concrete model identity, or record the precise blocker. Any credential or account action belongs to the operator and is not attempted here.
2. Add the smallest provider adapter to the central paid-provider registry and `/api/estate/run`, with typed per-provider quota and auth errors, no overlapping launches and no silent substitution.
3. Real `/api/estate/run` bounded runs for each qualified route; one separately authorised write-mode run per route under the existing lease and worktree rules; Codex-quota-to-qualified-GLM routing test; deployment, rollback and independent verification.

## Rollback

None needed: no code, configuration or service was changed.
