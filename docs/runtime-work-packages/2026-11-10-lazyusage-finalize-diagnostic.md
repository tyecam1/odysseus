# Packet C: finalize diagnostic evidence

Status: instrumentation candidate; **root cause unresolved, not committed or
deployed**. Owning task: `2026-11-09-lazyusage-bounded-persistent-continuation`.

Work uses admitted codex-write execution
`c3efedb0-cc28-47ab-8dee-aca472c377d7` and its existing active lease
`d27a491d-fd14-4d7a-b861-698e72614eae`, on
`task/lazyusage-backend-persistence`, starting at `cc9bf999`.
No second implementation dispatch or lease was acquired. Controller retention
is limited to final acceptance (`nondelegation_reason: final_acceptance`).
No registered initialiser was applied for this bounded defect packet.

## Changes and deterministic evidence

`_finalize_logic` retains the failed git subcommand, return code and trimmed
stdout/stderr (200 characters each) across retries and subsequent successful
probes. Launch failures and timeouts retain partial output with a null exit
code when none was observed. Every unsuccessful result carries that evidence
when a git command failed. Authority errors retain it in the protocol's existing message field
as well as the durable attempt result. Commit messages/argv are not captured.
History, adoption, concurrency, closure and lease requirements are unchanged.

Unit regressions cover failed add/commit/status commands, output bounds,
commit failure followed by changed history, durable attempt results, and
authority-error transport. A real missing-name commit failure reproduces the
staged-files/failed-commit shape and preserves git's actual error; this is a
diagnostic control, **not evidence of the production root cause**.

The live diagnostic uses `_launch_runner` -> `_run_attempt`, disposable HOME,
config, main repo, linked worktree and bare remote. It checks a successful
commit/push and an intentionally failing commit, with a 30-second result wait
and dedicated-unit cleanup. No paid invocation or live worktree is involved.

Run outside the restricted Codex sandbox on Lab, from this branch:

```bash
DATABASE_URL=sqlite:///:memory: /home/agent/projects/odysseus-aoteru/venv/bin/python \
  -m pytest -q -rs tests/test_estate_worker_units_live.py -k finalize
```

The combined finalize/control/gate/live-unit/lazy-runtime/lazy-acceptance/
laptop-client/provider-override suite passed **324 tests with five live-unit
skips** in 67.23 seconds on the final code. Eight focused diagnostic checks
also passed. The combined run used packet B's existing `/tmp` selector-timeout
launcher because this sandbox denies asyncio socket wakeups. Production code
and test policy were not changed for that restriction. Syntax and
`git diff --check` passed.

## Exact remaining blockers and recheck

- The standard CLI is absent and the bundled client has no backend config.
  Direct preflight initially encountered the read-only production DB. A
  read-only source snapshot copied to `/tmp` then confirmed the healthy,
  qualified Lab host and exact active lease; provider state is unknown while
  this already-admitted launch is running. It does not authorize another
  dispatch. Home is unavailable from this sandbox.
- Real-unit cases skip with `Failed to connect to bus: Operation not
  permitted`. No runner environment comparison or real-unit success is claimed.
  The same git side-process settings succeed in a disposable ordinary process.
  A Lab diagnostic result was requested; recheck when it becomes available,
  then apply only an evidence-supported worker/runner fix.
- Staging this packet fails with `Unable to create
  '/home/agent/projects/odysseus-aoteru/.git/worktrees/task_lazyusage-backend-persistence/index.lock':
  Read-only file system`. This sandbox's gitdir restriction is separate from
  the original finalize defect. Commit remains owed when an authorized writer
  can access the branch's gitdir. No merge was attempted.

The worker lane owns the remaining diagnosis/fix, live regression and commit;
the packet is not accepted as the requested completed defect fix.
