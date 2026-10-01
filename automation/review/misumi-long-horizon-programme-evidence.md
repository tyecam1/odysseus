# Misumi long-horizon programme â€” operating evidence

Prompt: `misumi-long-horizon-programme@v1` (register: `config/initialising-prompts.yaml`).
Application: `2026-10-01-misumi-long-horizon-programme-01` (Sonnet orchestrator, laptop session).
Contract: `automation/review/agent-tasks/inbox/2026-10-01-misumi-long-horizon-session-operating-contract.agent-task.md`.
This file is compact evidence for the programme. It is not a task queue, router, lease or memory authority.

## Operator policy changes recorded

### 2026-10-01 â€” Sol is a retrospective verifier, not a synchronous stage gate

> From 2026-10-01, Sol is an independent retrospective verifier for this programme, not a synchronous stage gate. Sonnet may progress and merge based on deterministic tests, live acceptance evidence and normal repository safeguards. Sol findings are incorporated later as repair work when substantiated.

Operator rules attached to the change:
- Sol still reviews, asynchronously: it receives the integrated commits, exact test results, runtime and routing evidence and later Stage 8 evidence. No automatic rollback; findings are classified by severity and substantiated material defects become governed repair tasks.
- Merges proceed when the work is based on current `dev`, conflicts are correctly resolved, relevant targeted and broader regression tests meet the existing repository standard, live evidence shows no material defect, and there is no unresolved authority, security or data-loss concern. Each such merge records that it was accepted pending retrospective Sol review.
- A depleted provider lane (for example Codex quota) must not be treated as general compute unavailability; only the action that truly needs that lane is marked blocked.
- Programme-related writes to governed feature/docs branches in `tyecam1/misumi` and `tyecam1/odysseus` are authorised when required by `misumi-long-horizon-programme@v1`, through PRs, leases/worktrees and normal controls. This does not authorise bypassing permission-system denials or destructive or unrelated writes.
- Home worker enablement (Stage 8) is approved subject to the existing qualification and benchmark gates; being online and reachable is necessary but does not by itself make home worker-eligible.

## Stage log

### Phase 0 â€” repository, queue and deployment truth
- Live baseline: `odysseus@dev` fb19b20c â†’ 90e25703 during the session; `misumi@main` e89c4ff6 â†’ e643a3f9.
- Misumi backlog: 61 pre-existing unresolved records + 1 new owner card, all classified. Misumi PR #41 (docs only) merged 2026-10-01: `docs/audits/2026-10-01-misumi-backlog-classification.md`. No card state changed.
- Home PC (read-only probes, host key matched the pinned fingerprint): Windows 11, Ryzen 7 5800X, 32 GB RAM, RTX 3070 8 GB, Ollama with five models, STT `MisumiSTT/0.1` faster-whisper `tiny.en` on :4600, household Odysseus runtime on :420 healthy. **Production is `odysseus-releases/e68288238b3c` = dev as of 2026-07-18**, which predates the September durable-execution and multihost work, so home is not yet worker-qualified and needs a release upgrade. Persistence is via scheduled tasks `Odysseus-Misumi` (logon), `homebase-controller` (boot) and `Misumi-Agent-Stack` (logon). Home is not estate-eligible (`verified: false`, no estate worker).
- Lab (`hz2-workstation`) is the only eligible worker. Live checkout at `d2fc0ba` (dev 2026-09-11).
- Interface PC (DESKTOP-RIFPR07): interface-box release `20260721-114230-44cd0e4f6c7a`, loopback :8770 and LAN TLS :8771.

### Discovery: an ambient transcript mechanism is already deployed (contradicts the programme premise)
- The deployed interface box contains a ratified (2026-07-20) text-only ambient transcript store: ships disabled, finite 14-day window, credential-shaped windows dropped, persistent hard mute, visible listening banner, endpoints `/ambient`, `/ambient/transcript`, `/ambient/mute`. Live config: `ambientCapture=true`, `ambientRetentionDays=14`; `capture-state.json` reports `muted: false` (2026-09-29).
- A home scheduled task `MisumiTranscriptPull` (daily 03:30; `C:\AI\misumi-transcript-pull.ps1`, read with operator authority, no secrets embedded) pulls completed days from the box to `E:\AI\misumi-transcripts\` over SSH with a forced-command key. It never deletes on the box and has **no purge step for E:**. One day file (`ambient-2026-07-21.jsonl`, 17 KB) has been held on home since 2026-07-22, longer than the 14-day box window. Contents were not read.
- **Repository truth â‰  deployment truth.** Source SHA `44cd0e4f6c7a` is not in `tyecam1/misumi`, the home checkout, or any checkout on the laptop; `deploy-from-laptop.ps1` takes it from `git rev-parse HEAD` of whatever local checkout it ran in. The ratified contract `docs/operations/ambient-capture-contract.md` is not on `misumi@main` or any branch checked. `misumi@main` `interface-box/server.py` contains no ambient code. A read-only, secret-scanned snapshot of the deployed files (70 files, `config.json` and logs excluded) is held for a recovery branch; creating that branch was denied by auto-mode and is left for the operator.
- Opus gate 3 ruling (advisory): home stays the single transcript write authority; the 2026-07-20 contract is the gate for ambient production on the box's own terms, with the "everyone in range knows and agrees" condition currently undocumented; coexist then wrap (Odysseus importer from E:, then box forwards text events with an `event_id`, then retire the pull); retention stays finite in every store; the mute must not be bypassable; restore repo truth first.

### Phase 1 â€” multihost integration (in progress)
- `feat/multihost-stage1-3-20260922` (Stages 1â€“7, 54 commits, each Sol-accepted on its own branch) was unmerged and 42 commits behind `dev`. `integration/multihost-stages1-7-20261001` is the controlled integration surface.
- Fresh ParkLease `fc96865e-4f5f-47ea-8cdd-81f81637d20a` on `integration/multihost-stages1-7-20261001`; the stale 2026-09-22 lease was reclaimed through normal `aoteru park` semantics. Worktree: `/home/agent/aoteru-worktrees/odysseus/integration_multihost-stages1-7-20261001`.
- Merge of `origin/dev` (90e25703): only documentation conflicted. `docs/aoteru-model-host-routing-contract.md` merged cleanly (dev's initialising-prompt envelope and telemetry plus the branch's `identity_verified` / `worker` / `qualified_hosts` model). `docs/aoteru-repository-ownership-trajectory.md` (add/add) was resolved manually: dev's newer 2026-09-23 ownership rules as base, an explicit Misumi / Odysseus / obsidian-PhD authority table, and the branch's multihost continuity notes. Merge commit `f4dedc45`, two parents.
- Lab Codex lane hit its usage limit (execution `8a65072e-192a-476f-b5aa-ce35e6d51e5e`, no repo mutation); the merge and tests were then done with the existing SSH management transport as user `agent` inside the leased worktree. Preflight had reported Codex "live" while quota was exhausted â€” see `2026-10-01-provider-quota-health-in-routing-preflight`.
- Tests (lab venv, Python 3.12.13, pytest 9.1.1):
  - targeted multihost/lifecycle set: 487 passed, 1 failed (`test_joined_u75_randomised_stale_finalize_vs_recovery[6]`, a real-thread-timing test); it passed 8/8 in isolation on both the pre-merge branch head (`803c89c`) and the integration tree, and the full suite run passed it, so it is classified as a load/timing flake, not a regression.
  - full regression suite on the integration tree: 5656 passed, 4 skipped, 0 failed, 19 errors, all `no such table: source_events` (the known pre-existing `test_source_events.py` waiver); baseline comparison against `origin/dev` @ 90e25703 recorded below.

  - baseline: `origin/dev` @ 90e25703 (git-archive copy on the lab) gives 5277 passed, 5 skipped, 19 errors and 1 failure that is an archive artefact (`test_real_checkout_roadmap_fixtureâ€¦` needs a real checkout). The 19 errors are identical â†’ **no new regressions in the lab environment**; +379 passing tests from the multihost work.
- PR #44 `feat(estate): integrate multihost Stages 1-7 onto dev` opened against `dev`. CI findings:
  - `Check PR title` and `Check PR description` failed on format only; fixed (Conventional Commits title; repo template sections).
  - `gitleaks` fails on one commit only, `ddb5ec37` (old LM2 evaluation artifacts) â€” the same pre-existing finding recorded on PR #41; nothing from this branch.
  - CI `pytest` (informational, `continue-on-error`): 5637 passed, 22 skipped, 19 errors (the same `source_events` waiver) and **1 new failure**, `tests/test_agent_cli_explain.py::test_explain_assembles_resolution_hosts_and_evidence`. Root cause: the Stage 7 fail-closed behaviour of `agent explain` for an unregistered host was correct, but the test did not pin `current_host_id`, so it passed only on the lab. Fixed in the test (commit `59b3796`, one hermetic monkeypatch, no behavioural change).
- Stage 8 home qualification progress: home checkout bundle transferred and cloned to `E:\aoteru\odysseus-aoteru`; the Windows checkout is incomplete because the repository contains eval-artifact paths with `:` in the name (`evals/local_models/results/artifacts/*/qwen3:8b/â€¦`). Applying a sparse-checkout exclusion on home was **denied by auto-mode ("Remote Shell Writes")** and left as is: home carries only an inactive partial clone and the bundle; no service, scheduled task, authorized key or household path was touched. The follow-on runbook steps (venv, `config.local.json`, forced-command key, host-key pin, health check, detached-spawn check, canary) are pending that decision.

- **PR #44 merged into `dev`** as merge commit `f901b8996f2f` (merge, not squash, preserving the Stage 1-7 commit identities), after the CI re-run on `59b3796`: pytest 5638 passed, 0 failed, 19 pre-existing `source_events` errors; title/description checks pass; `gitleaks` still fails only on the pre-existing `ddb5ec37` finding. **Accepted pending retrospective Sol review** (operator policy 2026-10-01). Not deployed.
- Lease: `aoteru release odysseus` for lease `fc96865e-4f5f-47ea-8cdd-81f81637d20a` was **denied by auto-mode ("Production Deploy")**; the lease is left to go stale and be reclaimed through the normal path. Lab live-service deployment of the merged `dev`, and the remaining Stage 8 home steps, are therefore pending operator permission.

## Denials recorded (auto-mode; not bypassed)
1. "Modify Shared Resources" â€” a local `git diff` of two scratch docs (cleared by the operator's later authorisation).
2. "Credential Materialization" â€” first attempt to read `C:\AI\misumi-transcript-pull.ps1` (later read under explicit operator authority; no secrets embedded).
3. Unexplained "dangerous" â€” creating a scratch clone of `tyecam1/misumi` and replacing its `interface-box/` directory to build the recovery branch for the deployed interface-box snapshot; left for the operator. The secret-scanned snapshot (70 files) is retained in the session scratch area.
4. "Remote Shell Writes" â€” sparse-checkout configuration and restore inside the new home clone (above).

(Remaining sections are appended as stages complete: PR #44 merge record, Stage 8 home qualification, Phase 2 transcript runtime, retrospective Sol review.)

