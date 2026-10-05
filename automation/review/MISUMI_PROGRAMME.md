# MISUMI_PROGRAMME — live work-item queue

Canonical queue for the Misumi/Odysseus long-horizon programme. Created 2026-10-05 (application -08): referenced by the standing coordinator directive but never previously materialised; distilled from the v4 programme directive's acceptance items, `automation/review/misumi-long-horizon-programme-evidence.md` open gates, and the programme-specific agent-task cards. This file is the queue, not an evidence store — the evidence register and application traces remain authoritative for proof.

Rule of use: at each frontier, reconcile live state, take the highest-value non-blocked item, and update this file. An item may only move to `done` when it is implemented, live-proven where applicable, independently verified where required, merged/deployed, and reconciled into evidence. Failures stay recorded.

## Active queue (executable)

### P1 — Governed ratification surface for routing candidates — **done (application -08, PR #96, release ce8d353a8f)**
Live-proven 2026-10-05: real store readable on `:420` (both -07 demo candidates, full provenance); on a labelled side-by-side `:1420` instance with a scratch state root, four real correction sequences produced an `eligible, awaiting: user-ratification` candidate, the API promote recorded `operator_ratification` with principal, the learned route served (`rr-d0899f9686a8`), the API rollback restored the baseline, and the endpoint's 404/409 gates answered loudly on `:420` without mutating the household store.
Repeated-behaviour candidates reach `eligible, awaiting: user-ratification` but no authenticated act exists to promote or reject them. Build: `GET /misumi/routing/candidates` (inspectability, misumi:read), `POST /misumi/routing/candidates/{id}/promote` and `/reject` (misumi:execute; provenance records the token owner as the ratifying principal), `POST /misumi/routing/revisions/{id}/rollback`. Acceptance: gate enforcement tested; real store readable on `:420`; promote/reject/rollback exercised on a labelled side-by-side instance (`:1420`) so no synthetic evidence touches the household store; deployed by the staged release path.

### P2 — Independent verification: Sol retrospective review of -06/-07/-08 — **open, verification debt carried**
Attempted 2026-10-05 via the lab codex lane: dispatch returned `ok: false` (`worker_failed`; `code-strong` has no evidence-backed binding on the stale lab backend d2fc0bac). Blocked by the same operator lab-deploy gate as B3. The debt is recorded here and in the -08 trace; retry immediately after B3 lands. All -06/-07/-08 verification is currently Flash-self-verified plus deterministic tests; no independent model review has yet covered them.

### P3 — Accumulation of repetition-derived candidates — **open (nature-gated)**
Eligible-by-repetition candidates only arise from real household interactions. Not buildable; watched via P1's inspection endpoint.

## Blocked: operator authority (proceed-around recorded)

### B1 — Kiosk box bridge unpause → box-proxy routing verification + visible room-transition observation
The interface box (192.168.4.37:8770) is paused by a household decision. The moment it returns: run `scripts/host/verify-persona-routing-live.ps1` through the box proxy and observe the auto-mode room transition.

### B2 — Memory policy v0.2 ratification
Uniformly marked "proposed for ratification with named gaps" (re-inspected -07: no contradictory markers). Operator act.

### B3 — Lab deploy (sudo)
Lab runs `d2fc0bac32`; target `3f3119c393` (re-resolve dev immediately before presenting). Requires operator sudo on `hz2-workstation`.

### B4 — Backup inputs
Provider/path, public age recipient, permission to install `age`. Operator.

### B5 — Router weakness improvements (negation, indirect requests)
The labelled generalisation weaknesses are **ratified-contract behaviour** (v0.1 defines the algorithm); changing it is a contract change requiring operator ratification. Do not "fix" silently.

### B6 — Console hardening / sign-in decisions, physical kiosk acceptance
Operator/physical; details in the private misumi repository.

### B7 — v3 closeout sequence
Final live reconciliation → Opus synthesis (requires Opus availability; carried as debt while Flash coordinates) → fresh-context Sol #3 → closeout doc → activate the persona-growth successor card (`automation/review/agent-tasks/ready/2026-10-02-misumi-persona-growth-background-collaboration.agent-task.md`). Sequenced behind B1-B4 evidence and P2.

## Done (this queue's history)
- -08: governed ratification surface for routing candidates + this queue materialised (PR #96; live proof as recorded under P1/P2).
- -06: deterministic lead-persona routing + auto mode, live 12/12 (PRs #92/#58/#93).
- -07: shadow-mode adaptation with governed promotion; full causal chain live-proven incl. restart persistence and rollback (PRs #94/#60/#95); v4 directive registered complete.

## Terminal reconciliation (2026-10-05, applications -06 through -08)

**No executable programme items remain this session.** Every remainder is explicitly classified:

- **Operator authority:** B2 (memory policy v0.2 ratification), B3 (lab sudo deploy — also blocks P2's Sol retry and B7's Sol #3), B4 (backup inputs), B5 (router weakness changes — ratified-contract algorithm), B6 (console/physical decisions).
- **Household/physical:** B1 (kiosk box bridge paused by household decision — box-proxy verification and room-transition observation ready to run the moment it returns).
- **Lane unavailable (debt carried):** independent verification of -06/-07/-08 — the Sol/codex lane fails on the stale lab backend (recorded verbatim in trace -08); the Opus synthesis for the v3 closeout requires Opus availability (Flash coordinates, role contract unchanged). The dedicated GLM reasoning lane was not separately available this session; consequential designs were validated by the directive text, the ratified contract, deterministic tests and live proof instead — recorded here as reasoning debt alongside the Sol debt.
- **Nature-gated:** P3 (repetition-derived candidates need real household interactions; inspection endpoint live).

Executable work delivered this arc: -06 (automatic routing, 12/12 live), -07 (adaptation loop, full causal chain incl. restart persistence + rollback), -08 (ratification surface + this queue), each merged, deployed to the home release path, live-proven on the real runtime, and reconciled into the evidence register, traces and evolution graph.
