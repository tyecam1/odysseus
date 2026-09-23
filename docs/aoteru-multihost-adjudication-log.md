# Multihost staged implementation — adjudication log

Operating contract: tyecam1/obsidian-PhD PR #575
(`automation/review/agent-tasks/ready/2026-09-23-odysseus-staged-implementation-loop.agent-task.md`).
Architecture authority: `docs/aoteru-multihost-execution-implementation-plan.md`.

## Adjudication route

- **Preflight.** The delegation preflight was run in-process through `src.delegation_preflight.delegation_preflight`, the same function `POST /api/estate/preflight` uses. The laptop client has no backend token configured on lab.
  - The review unit was classified `codex_eligible` on `hz2-workstation`.
  - The implementation and architecture units were retained, and decision rows were recorded. Their `nondelegation_reason` values were `architecture_judgement`, and `other: PR #575 assigns implementation to the claude_subscription executor; routing implementation to Codex (the adjudicator's own model) would make the adjudicator review its own work`.
- **Adjudicator.** Codex CLI 0.155.1 on `hz2-workstation`, run as `codex exec -m gpt-6-sol --sandbox read-only`. This is the same executor and host that preflight selected.
  - It was not called through `/api/estate/run`, whose advisory lane has a 180 s deadline, which is too short for a stage review.
  - The operator asked for GPT-6 Sol. PR #575 says GPT-5.6 Sol. `gpt-6-sol` was confirmed to exist and was used, and every session header reports `model: gpt-6-sol`, `sandbox: read-only`.
  - Sol modified no files in any round.
- `/ultrareview` was not used.

## Checkpoint 0 — pre-Stage-6 contract closure (PR #575 prerequisite)

Base: `94ad496`. Scope: plan only, with no production code. The branch baseline, before and after, is `286 passed`, using the plan's §E suite with the main checkout's venv.

The gaps closed were codex-write spool/tombstone retention, ambiguous `worktree.prepare`, and finalize/push semantics. They are now S6.8–S6.12:

| Section | Contract |
|---|---|
| S6.6 | Rewritten around `decide_once`. The start claim and the runner execute-or-abort decision are the only truth. Age alone never yields `start_failed` |
| S6.8 | Spools are never deleted. A write spool compacts to a permanent tombstone only 7 days after `spool.release`. There is a `status` fence |
| S6.9 | The prepare runs in a detached runner with a per-`lease_id` decision record. `worktree.prepare_status` has a fence. Ambiguous prepares keep the `preparing` reservation. `preparing` is never reclaimable by age |
| S6.10 | `finalized` means committed locally, history-bound to `admission_head_sha`, and clean. Push is a separate fact, pushed by exact commit and never forced, with a governed retry `aoteru push` that needs no lease. Finalize is idempotent through a worker `commit.json`, and the trailer is informational only |
| S6.11 | `decide_once` is a hard-link, fail-if-exists decision. Directory durability comes from observe → fsync → act, and from ancestor fsync |
| S6.12 | Aggregate execution quiescence over transient user-service cgroups: the writer plus every finalize attempt. The per-execution closure fence `closed.json` follows Dekker ordering |

Sol adjudication, 11 rounds:

| Round | Verdict | Material findings (all accepted, none rejected) |
|---|---|---|
| r0 | REJECT | orphan git child vs pid liveness; stale `starting` overwrite; refusal after an ambiguous attempt; lost finalize response; `rename(2)` replaces an empty dir |
| r1 | REJECT | `setsid` escapes session scoping; finalize payload lacks `execution_id`; decision dir not fsynced; the trailer is forgeable |
| r2 | REJECT | a loser acts before the winner's fsync; terminal state not gated on quiescence; recovered-head push unrecordable |
| r3 | REJECT | fsync-before-read race; `.scope`/`.service` contradiction; finalize git unscoped |
| r4 | REJECT | parent-directory durability; overlapping finalize attempts |
| r5 | REJECT | recovery ignores in-flight finalize attempts |
| r6 | REJECT | a pre-authorised finalize arrives after recovery → closure fence added |
| r7 | REJECT | closure blocked the push retry → push exempted from closure |
| r8 | REJECT | recovery verified HEAD before closure → reordered |
| r9 | REJECT | closure vs `finalize_commit_present` deadlock → the refusal was removed |
| r10 | **ACCEPT_WITH_FINDINGS** | one minor wording conflict (the S6.2 aggregate named push attempts), fixed |

Live evidence gathered on lab (2026-09-23) to ground the S6.11/S6.12 findings:

- **Link and rename.** `os.link` raises `FileExistsError` on an existing target, and `os.rename` silently replaces an empty directory. This confirms r0 finding 5.
- **Session scan.** A `/proc` session scan does see an orphaned same-session grandchild.
- **Codex's sandbox is itself a `setsid`.** The Codex sandbox runs commands as `bwrap --as-pid-1 --new-session --die-with-parent … --unshare-pid`, which confirms r1 finding 1.
- **PID namespace rejected.** An unprivileged user+PID namespace wrapper would contain escapees, but Codex's `bwrap` probe hangs inside it.
- **systemd user units chosen.** `codex sandbox -P :workspace` writes inside a systemd user scope and inside a transient user service.
  - In a scope, a `setsid` grandchild stays in the cgroup (`populated 1`).
  - In a service, the runner recorded its dedicated `aoteru-svc-*.service` cgroup, and its leftover was killed on exit (`KillMode=control-group`).

Open items for later stages and the operator, as recorded in plan §I.3:

- **B9 / B11.** A lost execution or a `preparing` reservation on a host that never returns stays protected indefinitely.
- **B12.** Linux quiescence residual: deliberate same-user cgroup migration. Windows quiescence is `None` until job objects are implemented.
- **B13.** Windows `decide_once` crash-durability is unproven.
- **Stage 6 deploy check.** The backend must report `health.write_prerequisites.runner_units: true` from inside `odysseus-aoteru-lab.service` before the first real write.
- **Deploy-time inference to verify.** Scope mode is expected to fail from a system service because of cgroup v2 migration rules. That is inferred, not observed.

Next: Stage 6 implementation against S6.0–S6.12 and the §G U13–U76 / I4–I11 matrix.
