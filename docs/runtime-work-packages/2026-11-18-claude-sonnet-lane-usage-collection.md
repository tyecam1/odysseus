---
title: Claude Sonnet lane qualification and read-only usage collection
owner: odysseus
task: 2026-11-18-lazyusage-laptop-usage-startup (PR #287) backend slice
status: in-acceptance
created: 2026-11-18
---

# Claude Sonnet lane qualification and read-only usage collection

Implements the backend slice PR #287's skill requires: the smallest authorised
read-only usage collection (actual remaining allowances and reset times,
provider-stated only, never invented), plus governed qualification of the
Claude Sonnet subscription advisory lane after the operator's lab re-login.

## Usage collection (`src/provider_usage.py`, `GET /api/estate/usage`, `am usage`)

- **Codex (real numbers):** the ChatGPT-authenticated CLI's session rollouts
  carry `token_count` events with provider-stated `rate_limits`
  (`used_percent`, `window_minutes`, `resets_at`, `plan_type`). Numeric fields
  only; the most recent event with a non-null primary window wins (48 h / 40
  file bound). Live lab reading 2026-11-18 ~13:40Z: primary (5 h) 5.0 % used,
  resets 1795016288; secondary (weekly) 69.0 % used, resets 1795208916;
  plan plus.
- **Claude (unknown by design):** the official CLI 2.1.281 exposes no headless
  usage/allowance surface (no `usage`/`status` subcommand; account web views
  are not scraped; OAuth tokens are never intermediated). Remaining/reset stay
  `unknown`; dispatch health from the existing provider-outcome gate is
  reported alongside.
- **Z.AI (unknown by design):** the authenticated anthropic-compatible
  endpoint exposes no usage route — probed live 2026-11-18:
  `/v1/usage`, `/api/v1/usage`, `/v1/usage/limits`, `/api/promptusage`,
  `/v1/quota` all 404/NOT_FOUND. Remaining/reset stay `unknown`.
- The route is read-only (`estate:read`), returns no credentials or message
  content, and states that `unknown` never means zero.

## Claude Sonnet lane (`execute_claude`)

- Live isolation 2026-11-18: `--bare` skips the subscription login context —
  the exact execute_claude invocation returned "Not logged in · Please run
  /login", while the same invocation without `--bare` (and with only
  `--no-session-persistence`) authenticated and attested
  **`claude-sonnet-5`** via the rolling `sonnet` alias. Fix: `--bare`
  removed; a neutral empty working directory
  (`~/.cache/aoteru/claude-lane`) keeps project context out of the call.
- GLM launchers (`claude-glm`, `claude-glm-flash`, operator-owned) now pass
  `--dangerously-skip-permissions` per the operator's 2026-11-18 instruction
  (Claude CLI permission-mode changes for external models); both lanes
  re-attested live after the change (`glm-5.3-flash`, `glm-5.3`, clean JSON).

## Qualification

(to be appended after the governed live run through the deployed route)

## Qualification evidence (2026-11-18, this branch)

- `execute_claude` through the real provider route (authoritative controller
  DB): `ok: true`, **`concrete_model: claude-sonnet-5`** (attestation
  `provider-usage-response`), 3.0 s, output "OK"; provider health `claude`
  → `state: ok, allowed: true`. This is the governed evidence for the
  `claude` executor entry on `hz2-workstation` in this branch's
  `config/estate.yaml` (tool-less advisory lane only; write work stays on
  codex-write per the routing contract).
- Model note: the rolling `sonnet` alias resolved to `claude-sonnet-5` on
  this account/CLI (2.1.281); the attestation check accepts the rolling
  family, never a pinned version.
- Direct-CLI quirk recorded: `codex exec --model gpt-6.1-sol` is rejected
  with `model_not_found` on this ChatGPT-authenticated account; the write
  worker lane's launcher does run gpt-6.1-sol. Direct review gates must
  resolve from `codex debug models` (currently `gpt-6-sol`).
