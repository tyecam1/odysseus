---
title: Aoteru lab execution convergence evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-21
parent: docs/aoteru-lab-execution-convergence.md
---

# Lab execution convergence — evidence

Compact durable record for the independent-review convergence pass
(`docs/aoteru-lab-execution-convergence.md`). Each numbered finding from
that contract, what was verified, what was fixed, and the live/test
evidence.

## 1. GitHub durability

**Verified, not fabricated.** `git pull --ff-only` (start of this
session) and `git push origin dev --dry-run` both succeeded against
`https://github.com/tyecam1/odysseus.git` with working stored
credentials. Corrected in `docs/aoteru-estate-p10-evidence.md` and
`docs/aoteru-lab-first-operator-guide.md` (both previously claimed "not
achieved").

## 2. Dedicated lab systemd service

**Prepared and verified, not installed** (needs operator `sudo`).
`odysseus-aoteru-lab.service` (repo root): `User=agent`,
`WorkingDirectory=/home/agent/projects/odysseus-aoteru`, this checkout's
own venv, `127.0.0.1:7001` only (never `0.0.0.0`), `Restart=on-failure`.
Deliberately not a copy of the generic `odysseus-ui.service` template.
`systemd-analyze verify` reports no errors specific to this unit (only
unrelated pre-existing warnings from `snapd.service`/`netplan`, confirmed
present regardless of this unit). `PrivateTmp` was considered and
deliberately left out — `routes/shell_routes.py` and the cookbook/codex
tmux runners depend on host-visible `/tmp` paths this environment has no
live systemd instance to verify against.

## 3. Host eligibility hardening

**Real defect found and fixed.** `eligible_hosts()`/`host_reachable()`
checked only role + live reachability — an explicit `verified: false` in
`config/estate.yaml` (currently only `desktop-in7o23d`) was recorded but
never actually read anywhere. Fixed in `src/estate_router.host_reachable()`
(the one shared authority `scripts/agent` also imports): `verified: false`
is now a hard gate checked before reachability. A host with no `verified`
key at all still defaults to verified (lab/interface's existing
convention, not a new category).

Live-verified against the real registry:
```
eligible_hosts() -> hz2-workstation: eligible (this host)
                     desktop-in7o23d: NOT eligible
                     ("not verified (config/estate.yaml verified: false)
                      — reachability alone is not sufficient")
```
Tests: `test_eligible_hosts_explicit_verified_false_blocks_even_if_reachable`,
`test_host_reachable_missing_verified_key_defaults_true` (both new,
passing).

## 4. `LogicalSession` lifecycle

**Real defect found and fixed.** `scripts/agent`'s `cmd_claude` wrote
`status="active"` at session creation *before* checking whether a native
process would actually launch, then never updated it on either failure
path (no `claude` binary; native launch unimplemented) — every dispatch
attempt in this environment left a permanently "active" row.

Fixed: the real terminal status (`failed`, with a reason) is now written
at creation time on both known-failure paths instead of "active" then
never-updated. A `_reconcile_stale_sessions()` backstop sweeps any row
still `active` with no `claude_session_id` past a 300s staleness window
(covers a wrapper process dying mid-dispatch, which the creation-time fix
alone can't cover) — invoked at the start of `agent claude where` and
before creating a new session.

Live-verified: running `agent claude auto "test task"` wrote the new
session directly as `failed` (`active` count confirmed 0 afterward), and
the *same reconciliation run* retroactively cleaned up 6 pre-existing
rows this exact bug had left `active` since 2026-08-20 P5 testing — real
production data, not a synthetic fixture.

Tests: `tests/test_agent_cli_session_lifecycle.py` (3 new, passing).

## 5. Parking lease heartbeat/stale handling

**Real defect found and fixed.** `heartbeat_at` was set once at lease
creation and never renewed by anything; no staleness handling existed at
all — a crashed/killed `agent park` holder would block the repo forever
(the unique-index single-writer guarantee was sound but had no
expiry/renewal on top of it).

Fixed, without a second lease authority:
- `core.database.PARK_LEASE_STALE_SECONDS` (1800s) + `park_lease_is_stale()`
  — one shared staleness rule.
- `agent heartbeat <repo_id>` — new CLI command, renews `heartbeat_at` on
  the caller's active lease.
- `agent park` now auto-reclaims (releases) a *stale* active lease before
  inserting a new one, instead of failing closed forever; a *live*
  (non-stale) lease still fails closed exactly as before — unchanged
  single-writer guarantee for real conflicts.
- `src.estate_router.eligible_hosts()`'s conflicting-lease check now
  ignores a stale conflicting lease on another host (read-only check;
  reclaiming the row itself still only happens through `agent park`'s
  explicit path) — a dead holder no longer blocks routing forever either.
- `agent where`'s lease report now includes `allowed_write_scope` and a
  `stale` boolean — the technical write-enforcement signal a caller
  (human, or a future PreToolUse/git-hook gate) can act on instead of
  trusting `status == "active"` alone.

Tests: `tests/test_agent_cli_parking_lease.py` (5 new, passing) —
heartbeat renewal, stale-lease reclaim, live-lease still-fails-closed,
and `eligible_hosts()` ignoring a stale conflicting lease.

## 6. Execution gap (major)

**Real, major gap found and fixed.** `estate_router.resolve_route()`
answered WHERE+WHAT but never called a model; `scripts/agent`'s
`cmd_claude` explicitly stopped before native launch. Nothing in the
system actually ran a task end to end.

Fixed: `src.estate_router.execute_local()` + `run_task()`. `run_task()`
calls the existing `resolve_route()` unchanged (deterministic-first and
parking/domain gates untouched), then — only when the resolved executor
is `local`, the one executor with a live runtime in this environment —
actually executes via `src.llm_core.llm_call` (the existing provider-call
layer; no second HTTP client), bounded by a timeout, with every failure
mode caught and returned as a clean result rather than a raised
exception. Applies a minimal, non-fabricated deterministic gate
(non-empty response) and persists the real outcome (`status`,
`deterministic_gate`, `latency_ms`, `escalation_reason` where relevant)
back onto the *same* `routing_decisions` row `resolve_route()` already
created — one row per routed task, not a second telemetry authority.
Wired at the HTTP layer as `POST /api/estate/run` (same auth boundary as
its `/route` sibling — verified 401 without a cookie after restart).

Deliberately does not invent Claude/Codex execution — no binary/paid
endpoint exists in this environment, and `run_task()` reports a
`needs_escalation` route as unexecuted for the same honest reason
`resolve_route()` already gives.

**Live end-to-end evidence** (real Ollama, not mocked):
```
run_task({"task_class": "smoke-test",
          "objective": "Reply with exactly the single word: pong",
          "requirements": {"capabilities": ["local-fast"]}})
->  route: host=hz2-workstation, executor=local, concrete_model=qwen3:8b
    executed: true
    execution: {"ok": true, "output": "pong", "latency_ms": 12957}
    deterministic_gate: "pass"

routing_decisions row (same decision_id, re-queried after execution):
    status=complete, deterministic_gate=pass, latency_ms=12957,
    escalation_reason=None
```
This is the full target chain: task envelope -> authority/host/model
resolution -> local model execution -> deterministic verification/result
-> persisted telemetry, genuinely working, live, on this host.

Tests: 6 new in `tests/test_estate_router.py` (mocked — execution
success/failure gating, deterministic/needs_escalation routes correctly
left unexecuted, no-objective guard, bounded upstream-failure handling).

## 7. Routing depth (minimum next layer)

**Real gaps found and fixed**, scoped to exactly what the finding asked
for — no scoring/ranking system invented:

- **All requested capabilities validated**, not just the first:
  `resolve_route()` now resolves every alias in
  `requirements.capabilities` and only reports the route resolved when
  *all* of them are; `capability_resolutions` (full list) is returned
  alongside the existing `alias_resolution` (first, kept for backward
  compatibility).
- **Explicit host constraint respected**: `placement.requested_host`
  (when not `"auto"`) narrows eligibility to that host and fails
  truthfully (`"requested host ... is not eligible"`) rather than
  silently substituting a different eligible host — the previous
  behavior silently ignored this field entirely.
- **Quality floor never fabricated**: an explicit `routing.quality_floor`
  always fails truthfully (`quality_floor_error`) — `config/models.yaml`
  carries no benchmarked numeric quality score to check it against, and
  none is invented.
- **Context capacity checked where evidence exists**:
  `requirements.context_tokens`, when a local alias resolves, is checked
  against `src.model_context.get_context_length_known()`'s *known* window
  (reusing that module's own known-vs-fallback distinction); exceeding a
  known window fails truthfully (`context_error`), an unknown window is
  reported (`context_note`) rather than silently assumed adequate either
  way.
- **Budget constraints surfaced, not silently ignored**: no call/quota
  accounting exists yet in this slice; any `budget.*` field present in
  the envelope is now echoed back under `unverified_constraints` so a
  caller can see plainly it wasn't actually enforced, instead of the
  previous behavior of accepting-and-ignoring it silently.

Tests: 8 new in `tests/test_estate_router.py`, all passing; full 27-test
file re-verified live against the real `config/estate.yaml`/`models.yaml`
afterward (unchanged real-config behavior for the unaffected paths).

## 8. Full test suite + live e2e smoke

Ran the actual repository suite, not only the routing-focused tests:
**4885 passed, 4 skipped, 11 failed** (`python -m pytest -q`, ~118s).
All 11 failures independently confirmed pre-existing and unrelated by
re-running them against unmodified `dev` HEAD (`git stash` /
`git stash pop`) before this session's changes were applied — same 11
failures, same errors, on the untouched baseline:
- 10× `AttributeError: 'Server' object has no attribute 'list_tools'` —
  an MCP SDK version mismatch affecting `mcp_servers/email_server.py`,
  `memory_server.py`, `rag_server.py` (4 collection errors +
  `tests/test_imap_leak_fixes.py`'s 10 tests) — nothing this pass touched.
- 1× `test_upload_handler_atomicity.py::test_smoke_info_lookup_after_bak_recovery`
  — pre-existing, unrelated to routing/parking/execution changes (on
  baseline this file actually failed 2/2, not 1/2 — filesystem-state
  flakiness, not a regression from this session).

Zero regressions attributable to this session's changes. Live e2e smoke
is finding #6's evidence above (real task envelope through real Ollama
execution with persisted telemetry) — not repeated here.

## 9. Labelling reconciliation

`docs/aoteru-estate-p10-evidence.md` corrected in place (original record
kept, corrections called out inline, not silently rewritten): origin
durability "not achieved" -> achieved; the local-worker chain segment
upgraded from "routes only" to "routes AND executes"; title/label
upgraded from `LAB-FIRST CUTOVER` to `LAB-FIRST EXECUTION CUTOVER`,
justified by finding #6's live evidence, per the convergence contract's
explicit instruction not to use that label unless the path genuinely
works. `docs/aoteru-lab-first-operator-guide.md` rewritten to match
current CLI surface (`agent heartbeat`, `/api/estate/run`), current gaps
(only the systemd `sudo` install remains), and current verified-live
bullet list.

## 10. Deferred items preserved

Confirmed no regression: `docs/aoteru-estate-p6-evidence.md` (mobile)
still `DEFERRED`; `docs/aoteru-estate-p8-evidence.md`'s `obsidian-PhD`
cross-repo dependency still recorded `## Deferred`. Neither file was
touched this pass; nothing in this pass's fixes depends on or claims
progress on either.

## 11. Local-model strategy

Read and retained (`docs/aoteru-lab-local-model-strategy-2026-08-20.md`).
No models downloaded this pass — `config/models.yaml`'s existing bound
aliases (`qwen3:8b`, `gpt-oss:20b`, `qwen3-embedding:8b`, the reranker)
were reused as-is for finding #6's execution evidence. The benchmark
programme in that strategy doc remains the next bounded work package,
unstarted by design (execution plumbing had to exist first, and now
does).

## Net state

All 11 findings verified and, where real, fixed with live evidence and
passing tests. `LAB-FIRST EXECUTION CUTOVER` reached: the full chain
(task envelope -> authority/host/model resolution -> local model
execution -> deterministic verification/result -> persisted telemetry)
is genuinely live on this host, not merely resolved-but-inert as the
2026-08-20 record had it. Full-estate completion remains explicitly not
claimed — home/interface PCs and Claude/Codex execution remain correctly
deferred, unavailable dependencies, not fabricated.

One human action remains: `sudo` to install
`odysseus-aoteru-lab.service` (see `docs/aoteru-lab-first-operator-guide.md`).
