---
title: Aoteru estate P10 evidence — LAB-FIRST EXECUTION CUTOVER
status: compact-evidence
owner: odysseus
as_of: 2026-08-21
parent: docs/aoteru-long-horizon-sonnet-followup.md
updated_by: docs/aoteru-lab-execution-convergence.md
---

# P10 — lab-first cutover

Compact durable record. Do not reread unless a dependency changes.

> **2026-08-21 convergence update** (`docs/aoteru-lab-execution-convergence.md`):
> an independent review correctly identified that the original
> 2026-08-20 record below claimed a cutover before the routing authority
> actually *executed* anything, and that two of its "not achieved" claims
> had since become stale. The original table/claims are kept below for
> audit trail; corrections are called out inline rather than silently
> rewriting history. Net effect: origin durability is now genuinely
> achieved, and the local-worker hop now genuinely executes (not just
> resolves) — see `docs/aoteru-lab-first-operator-guide.md` for the live
> evidence. The label is upgraded accordingly to `LAB-FIRST EXECUTION
> CUTOVER`.

Per the long-horizon contract's explicit instruction: "It is valid to
reach `LAB-FIRST CUTOVER`; it is not valid to claim full-estate completion
while home-dependent gates remain deferred." This declares the former,
not the latter.

## The usable target chain, checked segment by segment

```text
user on laptop -> Aoteru/Sonnet conversational surface -> Odysseus
memory/authority/host router -> parked lab worker -> deterministic/
local/Claude/Codex worker -> verification -> compact result -> same
laptop conversation
```

| segment | status | evidence |
|---|---|---|
| user on laptop -> conversational surface | **untested from this session** | this session runs on lab, not the laptop — genuinely cannot test this hop |
| -> Odysseus memory/authority/host router | **live, verified** | P4 (memory+provenance), Phase B (routing authority) — both HTTP-tested, both independently verified |
| -> parked lab worker | **live, verified** | P3 (parking, DB-enforced single-writer, live-tested) |
| -> deterministic/local worker | **live, verified, EXECUTES** (updated 2026-08-21) | originally only routed (`resolve_alias` + live Ollama check, P9 fix), not executed; `src.estate_router.run_task()` now actually calls the resolved model via `src.llm_core.llm_call`, applies a deterministic non-empty-response gate, and persists the real outcome/latency to `routing_decisions` — live-tested end to end against real Ollama (`qwen3:8b`) from this session |
| -> Claude/Codex worker | **not available in this environment** | no `claude` binary (P5), no paid `ModelEndpoint` configured — correctly reported unbound, not fabricated |
| -> verification | **live, repeated** | 8 independent fresh-context verifier passes across P0–P9/Phase B, all PASS |
| -> compact result -> same laptop conversation | **untested from this session** | same laptop-access limitation as the first hop |

Net: everything **after** the laptop hop and **before** the Claude/Codex
hop is built and verified. The chain's two ends (laptop origin, paid
worker) are real, acknowledged gaps — not something more work from this
session can close, since they need either a laptop-run session or
credentials/binaries this environment doesn't have.

## Rollback, persistence, cleanliness, durability, documentation

- **Rollback**: fresh backup snapshot taken and integrity-verified this
  phase (`backups/odysseus-backup-20260820-153106.tar.gz`, 58 files). All
  code changes are normal git commits on `dev` — revertible, nothing
  destructive or irreversible was done at any point this session.
- **Service persistence**: survives a process restart (P9, verified
  twice). Does **not** survive a host reboot — no systemd unit installed,
  blocked on `sudo` (no passwordless sudo in this session). Recorded as an
  open gap in `docs/aoteru-lab-first-operator-guide.md`, not silently
  accepted as done.
- **Repo cleanliness**: `git status --short` empty at time of writing.
- **Origin durability**: **achieved** (updated 2026-08-21; originally
  recorded "not achieved" — `git push origin dev` failed with `could not
  read Username for 'https://github.com'`, `gh` unauthenticated). The
  remote now uses `https://github.com/tyecam1/odysseus.git` with working
  stored credentials — `git pull --ff-only` and `git push origin dev
  --dry-run` both verified live this pass. Commits are no longer
  local-only.
- **Operator documentation**: written this phase —
  `docs/aoteru-lab-first-operator-guide.md` (day-to-day CLI usage,
  restart procedure, rollback procedure, explicit scope statement).

## What is NOT claimed

- Full-estate completion — explicitly not claimed; home/interface PCs
  remain deferred, unverified dependencies.
- Mobile/phone access — `svc:aoteru` correctly not stood up on lab (P2/P6
  correction), no phone reachable regardless.
- Unattended reboot survival — real gap; a dedicated
  `odysseus-aoteru-lab.service` unit is now prepared and
  `systemd-analyze verify`-clean (2026-08-21) but still needs operator
  `sudo` to install — see `docs/aoteru-lab-first-operator-guide.md`.
- Claude/Codex execution — still correctly not fabricated; no `claude`
  binary or paid `ModelEndpoint` in this environment. The local-model
  execution path is real but that hop remains local-only for this reason.
- ~~GitHub-visible history~~ — corrected 2026-08-21: achieved, see above.

## Gate

Plan §12 P10: "A successful current cutover may be labelled only
`LAB-FIRST CUTOVER`, never full-estate completion. Full-estate completion
remains blocked until the deferred home-dependent gates pass."

**LAB-FIRST CUTOVER: reached** (2026-08-20). **Upgraded to LAB-FIRST
EXECUTION CUTOVER on 2026-08-21**: the routing authority no longer merely
resolves a route, it actually executes it against a live local model,
gates the result deterministically, and persists the true outcome —
closing the gap the 2026-08-20 record left open (`resolve_route` alone
never called a model). Full-estate completion is still correctly not
claimed. One operator-only action remains (`sudo` for systemd
persistence) — not something this session can resolve itself.
