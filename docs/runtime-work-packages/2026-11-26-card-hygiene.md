# Card hygiene

Owning task `odysseus:ready/2026-11-26-card-hygiene-validator-and-sweeper.agent-task.md`

Implemented in the admitted worktree at base `c0c3354a1029f5a645a15fc33ccc5092a20f5fb1` under `estate-queue-priority-execution@v2`. Independent review and owner-lane delivery are pending. The owning card is still `ready`.

## Findings at HEAD

- [`agentic_context`](../../scripts/agentic_context.py) owns frontmatter parsing and per-queue checks. [`agentic_portfolio`](../../scripts/agentic_portfolio.py) owns the registered queue layouts and reuses that parser. The shared hygiene checks now attach codes and one-line warnings to cards in both discovery paths. This flags new and changed cards while existing queue entries remain readable.
- Parent links occur as `parent_task` references. The checks also recognise explicit `child_tasks` and `children` lists. The sweeper proposes `execution_mode: container`, which the runtime treats as non-executable when explicitly set.
- `approval_scope` already binds the permitted paths and result path. Explicit protected gate classes route to the owner. A missing, invalid or `none` class routes to the advisor tier. Approval eligibility, delegation activation, scope matching, revocation and owner acceptance use the existing gates. The legacy notification sort now uses priority and age. It can still display `due_date`; only `event_date` participates in expiry checks.
- The routing contract permits qualified Flash advisory and review lanes under their own rules. This card's executor-assignment rule applies to `glm_flash`, `glm-flash` and versioned Flash model names when the card assigns verification or judgement. Deterministic verification keeps its existing lane.
- Tagged Sol calls are stored as a ` |call=` JSON suffix on routing decisions. The sweeper uses completed, launched records with a concrete model and a card or PR subject. Misumi review cards lacked PR links. Two PhD review cards had numeric links, so the sweeper supports both registry-bound PR numbers and repository-qualified URLs.
- [`owner_ledger`](../../src/owner_ledger.py) stores owner and advisor decisions with a repo-bound scope. The existing daily digest facts hook shows open owner approval and acceptance gates, and current approval or decline decisions recorded in the last 24 hours by agent or advisor and by owner. Deferrals, escalations, revoked decisions and policy-level delegation are outside that count.

## Sweeper use

Run `python scripts/card_hygiene_sweep.py --help` for the existing registered repo selection and evidence options. The script writes `automation/review/card-hygiene/<repo>/proposals.json` in its Odysseus root. Each affected card gets one proposal with its findings and a hash of the decoded card text. The patch's `set` entries are concrete proposed edits. `needs_evidence` lists fields that require source evidence before a value can be proposed. Apply metadata changes through the owning repository's normal process.

`--routing-db` accepts a read-only SQLite source. `--fallback-header` accepts a trusted machine-generated report with structured `fallback_lane`, `task_ref`, `record_id`, `reviewer_model` and `head_sha`. `--pr-reviews` accepts a trusted JSON array of submitted PR reviews with a stable review ID, `commit_id`, `pull_request_url` and an attested `concrete_model` field. The sweeper skips prose fields. A reviewer proposal records the source, native record ID, model and reviewed head. Ambiguous or absent attestations produce a single bounded re-review proposal. Independent review and acceptance require their own evidence.

## Queue-copy verification

The 2026-11-26 scan used the Odysseus base above, Misumi `4e25918542ef6a11161c71b489e876273d2fbb0d` and obsidian-PhD `e5f3c282a5e4c63e2eba189c990cd2e540c09a23`. It compared SHA-256 for 364 canonical files, including archived cards, with zero changes. The only added files were the three per-repository proposal sets.

| Check | Odysseus | Misumi | obsidian-PhD |
|---|---:|---:|---:|
| Parsed live cards | 67 | 52 | 35 |
| Cards with proposals | 46 | 5 | 35 |
| Approval scope missing | 22 | 1 | 6 |
| Owner gate class required | 43 | 1 | 35 |
| Device-only host reason missing | 15 | 0 | 9 |
| Mechanical executor on judgement work | 2 | 0 | 0 |
| Executable container | 0 | 0 | 0 |
| Expired or invalid event date | 0 | 0 | 0 |
| Bounded re-review proposed | 0 | 4 | 8 |

The copied queues had no executable-container or expired-event finding. Fixtures exercise both cases. The routing snapshot had 11 completed, launched Sol records, one of which had a structured subject and head. None matched a scanned review card. GitHub returned no review submissions for obsidian-PhD PRs #465 and #466. The scan found no matching machine-generated fallback header. The fixtures verify attestation with native IDs from each of the three record sources and refuse a reviewer named only in prose.

`protected_handoff` applies to `misumi/agent-tasks/inbox/finance-market-media-intelligence-2026-10-29.md` because its YAML frontmatter could not be parsed. The sweep continued over the readable queues and returned status 1 to report incomplete coverage.

## Verification and delivery

- Implementation worker `4cd3896f-f55d-4cef-b3ca-2babde6ea3df` was admitted on lab as `codex-write` under lease `5f327b17-dd4a-4114-9857-592559334f2c`. The lease matched this worktree and the admission base. The authenticated subscription resolver reported `gpt-6.2-sol`. The controller's per-launch model receipt is pending worker finalisation. Deterministic verification used Python and pytest without a model.
- Deterministic preflight selected the lab. The plain pytest process stalled on sandboxed socket wakeups. The final run uses the existing [test-only selector workaround](2026-11-09-lazyusage-lab-persistence-acceptance.md), with an isolated data directory and in-memory database.
- Focused pytest reported `577 passed, 1 skipped, 1 warning in 33.20s`. Python syntax, changed-path scope and `git diff --check` passed.
- The full run was incomplete at the worker handoff. At 03:26:38 UTC, 6,302 of 10,605 collected tests had reported results (6,242 passed, 50 skipped, 1 xfailed and 9 failed). The existing worker deadline was 03:27:29 UTC. The suite log is `/tmp/odysseus-hygiene-suite.0irjRQ/full.log`.
- The nine observed failures all reproduced on a separate checkout of the admitted commit using the same launcher. Five failed on TCP socket creation, one on a Unix socket bind, one on DNS resolution, and two on LazyUsage stop-state assertions. The full green acceptance gate remains open.
- During verification `origin/dev` advanced to `5498873c76c9932664c7ce18a5b006cfe3880c0e` with changes confined to the liveness task and its documentation. The implementation and tests stayed on the admitted base.
- The estate preflight could not admit a fresh Sol review while the Codex launch outcome was pending. It reported the labelled GLM advisory lane ready and GLM-Flash unqualified on lab. The estate HTTP client had no configured backend, and the lab loopback endpoint was unreachable from this sandbox. A qualifying review must be cross-family and examine the final diff. The controller owns that dispatch and retains final acceptance.

## Cross-family review and controller fixes (2026-11-26)

Reviewer: claude-opus-5-5 (Claude family; the author is Codex, GPT family, so the review is independent), in two passes.

**Pass 1 on the worker's commit `fb9ef772`: CHANGES_REQUIRED.** Three P1 defects, all in routing that this card's own plan said must not change who the owner is asked:
1. `owner_inbox_runtime._scan` sent every card without a non-"none" `owner_gate_class` to an "advisor tier" and skipped it from the phone, although no advisor worker is enabled: all 13 waiting approvals (none carries a class) would have silently stopped reaching the owner, and escalated or high-risk cards could never return.
2. `lazy_usage_runtime._owner_notification_debts` filtered the same cards out of the Discord decision cards and the alert channel, so no fallback route existed either.
3. The digest's "Owner gates: N open" counted only what reached the phone (0 while 13 waited).
Smaller findings (accepted and recorded as follow-ups below).

**Controller fixes landed with this commit:** the gate class now only NARROWS advisor routing (an advisor-eligible card is routed to the advisor only when it is unclassified or "none", the floor admits it, the owner's delegation is in force and the advisor has not escalated it; every other card reaches the owner, including every card while the advisor worker is off); an unknown or misspelt class fails closed to the owner; the legacy-notification filter is removed and the tests that pinned it are restored; the digest's open count is every waiting gate and the advisor line is kept; the three tests Codex had inverted are restored and the three Opus asked for added (unclassified high-risk reaches the phone, unclassified after declined delegation reaches the phone, an escalated card returns to the owner); the explicit-class case is its own parametrised test. Small validator fixes: a YAML datetime `event_date` is accepted, `_DEVICE_RESOURCE` no longer accepts "gpu"/"display" (the lab has GPUs) and accepts "signed-in"/"Chrome profile".

**Pass 2 on the fixes: APPROVE_WITH_CONDITIONS** (all three conditions applied: a test pinning the legacy-notification path, the explicit-class case isolated from the escalation, an unknown class failing closed to the owner).

**Verification:** full lab pytest suite on the fixed branch: 10571 passed, 47 skipped, 5 xfailed (and 10543 passed on the unmodified worker commit)

**Accepted follow-ups (not blockers):** a debt's `priority` is copied when the debt opens and can go stale (read it from the frontier); `non_executable_container` is a dispatch change (0 live Odysseus cards use `execution_mode: container`; other repositories were not counted); `agentic_portfolio` now emits `hygiene_warnings`, `result_path` and the hygiene fields, so a client that validates the older record shape must be deployed together with the lab (validate codes, not reason text); the validator rules are warnings, not rejections of new or changed cards; `MECHANICAL_ONLY_EXECUTORS` is a local constant, not the routing contract's set; `output_task`/`selected` derive parents from the single card; the sweeper's fallback-header format and the PR JSON's `concrete_model` are unproven sources and the attestation backfill accepts a single matching record when a card has no `review_head_sha`; the author's actual serving model must be filled from Codex's `model:` line before acceptance.
