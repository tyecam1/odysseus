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

## Checkpoint 1 — Stage 6: EstateExecution through the worker (ACCEPTED)

Range `a0c361f..90a5810` on `feat/multihost-stage1-3-20260922`. Final adjudication: **gpt-6-sol ACCEPT, no findings**. Sol confirmed "the PR #575 Stage 6 minimum completion gate is met" in gate round 12, and gave a clean ACCEPT in the confirmation round.

Slices:

| Slice | Commit(s) | Content |
|---|---|---|
| 6a | 64ac950 | worker columns; dual-dialect partial indexes; transactional migration; `lease_serialized_transaction` |
| 6b | 78c95a6 | `lease_authority_state`; serialized reclaim/release; exact-lease renewal |
| 6c | 5b8d75f, e47f79c | worker `decide_once`; spool/runner decisions; fence/close/release; prepare, finalize and push attempts; transient user-service runner units; `tree_quiescent` |
| 6d | 8d7a931 | control-plane write lane: admission, observation, finalize, recovery, push, `park_with_worktree`, `run_task` switch |
| 6e | d0ebea3 | HTTP routes (`?wait`, push, recover, resolve-prepare, `?host=`); laptop `execution`/`recover`/`push`/`resolve-prepare`; live integration |

Adjudication fixes, in order: 22d31fd, 8e606fc, 36d7d33, 118f1ba, 9cbaaea, df4eb2f, 663d7fd, 9d12343, 83c9751, c008ada, 15fec47, f2baa90, a2d403d, a597d2b, 90a5810. Coverage completion: 831d916, 79b176d. A finalize race found by our own U71 test was fixed in e20f4d6.

Tests: `566 passed`, rc=0, run as the §E suite + `tests/test_estate_worker*.py` + `tests/test_estate_stage6_*.py` with the main-checkout venv (Python 3.12, SQLAlchemy 2.0.52, SQLite 3.53). The pre-Stage-6 baseline was 286. No pre-existing test regressed. Superseded pre-Stage-6 tests were migrated or replaced, as each commit records:

- six local-git finalize tests;
- nine closed-lane mechanics tests of the legacy in-process durable lane;
- the worker start/status/cancel contract tests.

Test coverage:

- **Real infrastructure** on this lab host:
  - real transient systemd user units, with no leftovers after any run;
  - a real `setsid` grandchild with `KillMode=process` (dead runner, live grandchild);
  - real git with a bare origin;
  - two real OS processes for SQLite serialization (I9);
  - the real `LocalTransport` worker subprocess (I4–I11).
- **Joined control-plane + real-worker scenarios**: U25, U27, U67, U71, U74, U75, U76.
- **U75 randomised interleavings**: 10 seeds, stable.
- **No paid inference** anywhere. Live runs dispatch the sentinel-gated `noop-sleep` kind through a test-only `_start_payload` patch.

Sol adjudication: 6a/6b (1 round + re-check), 6c (1 + re-check), 6d (1 + re-check), 6e (1), then 12 gate rounds and a confirmation. Every material finding was accepted and fixed; none was rejected. Notable real defects Sol found and we fixed:

- stale-`starting` overwrite;
- a GET that dispatched or blocked;
- a late finalize running git after closure (fixed in three steps, ending with verification moved behind the runner's run decision);
- a dirty tree accepted at `start`;
- an untracked legacy write lane (both legacy lanes are now closed);
- a post-claim error read as `not_started`;
- verification-budget arithmetic.

One contract clarification was made at the gate: the §G U75 temporal qualification (15fec47). Sol classified the remaining finite-budget verification behaviour as a **minor availability residual**: a retryable, state-free `worktree_verification_unavailable` that creates no row and changes no lease.

Deliberate deviations from the plan text, recorded:

- The legacy in-process lanes (`execute_codex_write`, `execute_codex_write_durable`) were closed in Stage 6 rather than Stage 9, because they were live unsafe paths. Stage 9 still deletes them.
- Branch parks on the lab host prepare through `LocalTransport` (S6.9).

Pre-existing and known residuals, unchanged and recorded in plan §I.3:

- B9/B11: a host that never returns;
- B12: Linux deliberate same-user cgroup migration; Windows quiescence is `None`, so every Windows write verb refuses;
- B13: Windows `decide_once` durability;
- B10: `ix_source_events_source_external_unique` is still sqlite-only.

Operator actions before deploying Stage 6 to `odysseus-aoteru-lab.service`:

1. Re-check that `data/app.db` has no active ParkLease (S6.1 backfill note).
2. After restart, confirm `health.write_prerequisites.runner_units: true` from inside the system service. This covers user-bus access and the scope-migration inference.
3. `~/.aoteru/worker-spool/.no-hooks/` was created on lab by test runs. It is harmless.

Next: Stage 7 (host-specific capability qualification).

## Checkpoint 2 — Stage 7: host-specific capability qualification (ACCEPTED)

Range `e7d4ddb..8978b17` on `feat/multihost-stage1-3-20260922`. Final adjudication: **gpt-6-sol ACCEPT, no findings** (round 7, over the whole range).

| Commit | Content |
|---|---|
| 886608d | `qualified_hosts: {host: {evidence, binding?}}` in `config/models.yaml`; `resolve_alias(alias, host)` checks qualification first, then the per-host binding override, inventory and `gpu_yield`; canary `--worker-host` (attested `call_worker`, records the host, never writes config); §8 of the home setup doc |
| 71f412d | round 1: a host entry needs its own non-empty evidence; the paid fallback checks its routed host's executor qualification; `/route/alias` defaults to `current_host_id` and fails closed; preflight probes each unit's routed host; a vision-only worker canary exits nonzero |
| e292758 | round 2: a per-host binding qualifies a null-default alias; preflight `ok` needs executor qualification on the routed host; `agent explain` fails closed on an unregistered host |
| 9dc2490 | round 3: a "not qualified on" reason comes before the unbound check; the preflight summary names its probe host |
| d642f38, 5344f1f, 8978b17 | rounds 4–6: `agent status` resolves each capability on this host through `resolve_alias` (`resolved_on_this_host`, `reason`, `concrete_model`) and degrades on any router import failure; the regression test raises a plain `ImportError` and fails against the pre-fix guard |

Shipped config: every live alias is qualified on `hz2-workstation` only, with its LM4 evidence. `embedding` and `reranker` are structural-binding-only, and `code-strong` stays null. Lab routing is unchanged, and the Stage 7 config test pins home (`desktop-in7o23d`) as unqualified. Nothing auto-promotes.

Tests: `701 passed`, rc=0. That covers the §E suite, `tests/test_estate_worker*.py`, `tests/test_estate_stage6_*.py`, `tests/test_estate_stage7.py`, `tests/test_delegation_preflight.py` and every `tests/test_agent*.py`. The baseline was 566 plus the agent tests, and no test regressed. No paid inference was used.

Sol adjudication: 7 rounds. r1 REJECT (3 material, 2 minor) → r2 REJECT (1 material, 2 minor) → r3–r6 ACCEPT_WITH_FINDINGS (minors only) → r7 ACCEPT. Every finding was accepted and fixed, none was rejected, and Sol modified no files.

## Stop — Stage 8 is operator-gated (PR #575 stop condition)

Checked on 2026-09-23: `tailscale status` shows home `desktop-in7o23d` **offline, last seen 2 days ago**. Stage 8 needs a live host and operator approval. Stage 9 comes after Stage 8 in plan §I.1, and its `verified`-fallback removal assumes Stages 1–8 are done. The loop therefore stops here.

Operator actions needed, per plan §I.3 and Stage 8:

- B1: bring home online.
- B2: install the lab→home SSH key with its forced command.
- B3: capture and pin home's host key (governed commit).
- B4: set up the home checkout, venv and `config.local.json` roots.
- Complete Stage 4 runbook steps 1–7.
- B5/B6: install and authenticate Codex on home and check detached-spawn survival. These are optional and needed only for home `codex`/`codex-write`.
- B7: make the household (Misumi) contention decision.
- B8: approve the governed Stage 8 config commit.
- B13: provide Windows `decide_once` durability evidence before any home write lane.

After that, run the Stage 7 canary on home: `scripts/run_lm4_production_canary.py --worker-host desktop-in7o23d --aliases local-fast`.

Deferred, not done: the repository-boundary convergence in `docs/aoteru-repository-ownership-trajectory.md`. It is an explicit operator checkpoint at the backend completion boundary. The transitional task trail in `obsidian-PhD` was preserved and nothing was migrated.
