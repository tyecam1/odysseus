---
title: Aoteru estate P3 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-20
parent: docs/aoteru-estate-execution-contract.md
---

# P3 — parking + remote native execution (lab-first slice)

Compact durable record. Do not reread unless a dependency changes.

Per `docs/aoteru-lab-first-continuation.md`: implement end-to-end on the
lab worker first, keep the schema host-agnostic, defer anything needing a
second host/the laptop rather than blocking on it.

## Built

- `core/database.ParkLease` (`park_leases` table): `repo_id`, `host_id`,
  `worktree_path`, `branch`, `session_id`, `allowed_write_scope`, `status`,
  `heartbeat_at`, `released_at` + `TimestampMixin`.
- **Single-writer guarantee is a real DB constraint, not an app-level
  check-then-act race**: partial unique index
  `ix_park_leases_active_repo_unique` on `repo_id` WHERE `status='active'`.
  Confirmed via `sqlite_master` schema dump (see below) — SQLite itself
  rejects a second active row for the same `repo_id`.
- `scripts/agent park <repo_id> [--host] [--branch] [--session]` /
  `agent release <repo_id> [--host]` — extends the existing P1 CLI, no
  second launcher. `agent where` now reports the real active lease instead
  of a hardcoded `null`.
- Fail-closed dirty-tree check: `git status --porcelain` on the resolved
  repo path; anything non-clean, or the git command itself failing, refuses
  to park. No WIP-branch auto-creation (that's the multi-host "switching
  clone" case from plan §8 step 5 — deferred, see below).
- Host-mismatch guard: `agent park` refuses to acquire a lease on any
  `--host` other than the machine it's actually running on. Remote lease
  acquisition (a laptop session parking a repo *on* the lab host) needs
  P5's routing layer, not a bare DB insert from wherever the CLI happens to
  run — deferred, not implemented as a shortcut.

## Verified (live, on this host)

```text
schema:  CREATE TABLE park_leases (...)
         CREATE INDEX ix_park_leases_repo_host_status ON park_leases (repo_id, host_id, status)
         CREATE UNIQUE INDEX ix_park_leases_active_repo_unique ON park_leases (repo_id) WHERE status = 'active'

dirty-tree fail-closed:
  repo had real uncommitted changes (this session's own edits) ->
  `agent park odysseus` -> "refusing to park 'odysseus': working tree has
  uncommitted changes (fail-closed — commit/stash first)"

clean park:
  `agent park odysseus --branch dev --session test-session-1` -> ok:true,
  lease_id recorded

where reflects lease:
  `agent where` -> lease.lease_id/host_id/branch/session_id/heartbeat_at
  all match what park returned

conflicting lease (the actual gate test):
  second `agent park odysseus` while the first lease is still active ->
  "'odysseus' is already parked (active lease exists) — release it first"
  (IntegrityError from the partial unique index, caught and reported)

release + re-park:
  `agent release odysseus` -> ok:true; `agent where` -> lease: null;
  `agent park odysseus` again -> new lease_id (proves release actually
  frees the slot, not just flips a flag the unique index still honors)

release with nothing active:
  `agent release odysseus` after already released ->
  "no active lease for 'odysseus' on 'hz2-workstation'" (clear failure,
  not a silent no-op)

guard rails:
  --host <not-this-machine> -> refused with explanation
  unknown repo_id -> refused, points at config/repositories.yaml
  registered-but-unresolved repo (misumi) -> refused with the same
  root-var-not-set reason `agent status` already reports

state left clean: no active lease exists on `odysseus` after this test run.
```

## Deferred (needs a second host or the laptop — not blocking further phases)

- **ff-only sync / clone-state reconciliation on host switch** (plan §8
  step 5-6): meaningless with one host — there's nothing to sync *to*.
- **Split-brain test** (target clone dirty on the *other* host): needs a
  second host to be dirty on.
- **SSH launch into the parked worktree**: needs a laptop session to launch
  *from*; the worktree itself is real and resolvable (`worktree_path` in
  the lease is the actual live path), but nothing has SSH'd in and started
  work in it yet.
- **"laptop can park and run tests on either PC without knowing paths"**:
  the "without knowing paths" half is proven — `agent park odysseus`
  resolves the real path internally, the caller never supplies one. The
  "from the laptop, either PC" half needs that session to exist.
- **Heartbeat renewal**: `heartbeat_at` is set once at creation; no renewal
  loop implemented yet. Not one of the three explicit gate tests — left as
  a known simplification rather than built speculatively.

## Gate

Plan §12 P3 gate: "same repo cannot acquire conflicting write leases;
dirty/split-brain tests fail closed; laptop can park and run tests on
either PC without knowing paths."

- [x] same repo cannot acquire conflicting write leases (DB-constraint
      enforced, live-tested)
- [x] dirty case fails closed (live-tested with a genuinely dirty tree)
- [ ] split-brain case — deferred, needs a second host
- [ ] laptop can park on either PC — mechanism proven path-agnostic;
      laptop-initiated half deferred, needs a laptop session

**P3: PARTIAL, lab-first slice complete.** Everything buildable and
testable with the lab host alone is done and verified live, not just
implemented. Remaining items are genuinely gated on a second host/the
laptop, per the lab-first contract — not blocking continuation into P4.
