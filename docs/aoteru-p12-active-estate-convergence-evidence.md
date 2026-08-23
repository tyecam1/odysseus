# P12 — active-estate convergence: evidence

Executed 2026-08-23 against `docs/aoteru-p12-active-estate-convergence.agent-task.md`.
This session ran on the **lab** host (`hz2-workstation` /
`dmem-HP-Z2-Tower-G9-Workstation-Desktop-PC`) throughout, not the laptop —
recorded honestly rather than fabricating laptop-side evidence, per the
task's own P12.0 step 2.

## Corrected topology (P12.0)

`config/estate.yaml` previously conflated "laptop" and "interface" as one
entity (`desktop-7dj1hma`, `role: interface`). Corrected:

- `desktop-7dj1hma` → `role: laptop` (human controller). Live via
  `tailscale status` from lab: `100.75.44.26`, active direct connection
  `185.17.164.207:56189`.
- new `interface-pc` entity → `role: interface`, hostname genuinely
  unknown, `verified: false` — deferred, not guessed from stale
  `192.168.4.37:8770` material.
- `glovebox` → `role: experiment-edge` (was `unassigned`) per operator
  statement. Live `tailscale status`/`tailscale ping` from lab, re-run
  twice this pass (P12.0 and P12.5), both show it **offline**, last seen
  36d, no ping reply — a real discrepancy between operator statement and
  tailnet evidence, recorded as such rather than trusting either side
  alone.
- `desktop-in7o23d` (home) — unchanged identity ambiguity
  (IN7O23D/IN7023D), now explicitly annotated
  registered-but-ineligible/deferred, not failed.
- `config/routing.yaml`'s `host_eligibility` updated to match:
  `laptop`/`interface`/`experiment-edge` all `execution_worker: false`;
  `lab`/`home` unchanged.

Lab live-inventory this pass matches durable evidence exactly: i9-12900K
(24 threads), 125.5GB RAM, RTX 3080 10240MiB (driver 560.35.03), Ollama
0.32.15, NVMe 984GB/504GB free, Odysseus backend `127.0.0.1:7001` healthy
(`/api/health` → 200).

## Controller → lab path (P12.1)

Session-limitation-honest: laptop→lab cannot be proven from a lab-run
session. Proved everything host-independent instead — four task classes
executed through the real production `run_task()`/`resolve_route()` path,
each with its own `RoutingDecision` row:

| task class | route | executed | gate |
|---|---|---|---|
| deterministic (no capability) | executor=deterministic | false (nothing to execute) | n/a |
| `local-fast` | `qwen3:8b` | true | pass |
| `code-fast` | `ornith:9b` | true | pass |
| repo-aware read (`repo: odysseus`) | `qwen3:8b` | true | pass |

Parked-mutation demo skipped deliberately — the task marks it optional
("only if...non-destructive and lease-verifiable"), and parking the live
working repo mid-session would risk interfering with this session's own
git state for no new evidence; the ParkLease conflict-check path is
already covered by 34+ passing tests.

**Laptop continuation gate (deferred sub-gate, not a P12 failure):** from
the laptop (`desktop-7dj1hma`), run the existing `scripts/agent claude
lab "<task>"` or a direct `agent status`/API call against
`http://dmem-hp-z2-tower-g9-workstation-desktop-pc.tail171792.ts.net:8080`
to close the actual laptop→lab leg. No code change is needed for this —
the surfaces above already exist and were exercised on the lab end.

## Unified multimodal path (P12.2)

`run_task()`'s plain-string `objective` was already structurally capable
of carrying OpenAI-style multimodal content (`objective` flows unmodified
into `messages[0]["content"]`; both `estimate_tokens`
(`src/model_context.py`) and `llm_call`'s multimodal conversion already
branch on `isinstance(content, list)`). LM4's belief that `run_task()`
"cannot carry multimodal content" was not re-verified before that script
was written. This pass:

- live-reran the LM4 `doc_image-01` vision fixture directly through
  `run_task()` (not the `resolve_route()+llm_call` bypass) — real
  `RoutingDecision`, correct "7421" MiB answer, `deterministic_gate: pass`.
- documented the accepted `str | list[dict]` shape explicitly in
  `execute_local`/`run_task` docstrings and type hints.
- added a regression test
  (`test_run_task_passes_multimodal_objective_through_unmodified`)
  proving the content list passes through unmodified, not stringified.

All current capability aliases (`local-fast`, `local-strong`, `code-fast`,
`reasoning-strong`, `vision`) now demonstrably traverse one
route/job/telemetry path. Plain-string callers unaffected (30/30 then
32/32 then 34/34 `test_estate_router.py` passes across this and the next
two phases).

## Paid worker convergence (P12.3)

Discovery: no `claude` binary on PATH, no `ANTHROPIC_API_KEY`, zero
`ModelEndpoint` DB rows — but `codex` CLI 0.116.0 is installed and
authenticated (`~/.codex/auth.json` present, "Logged in using ChatGPT").
Codex is therefore the one real paid mechanism available on this host,
and is what got bound — not a speculative Claude adapter.

Added `execute_codex()` (bounded: `--sandbox read-only`, `--ephemeral`,
scratch cwd, subprocess timeout) and wired it into `run_task()` as an
**opt-in** escalation (`task.routing.allow_paid_escalation: true`) for a
`needs_escalation` route — evidence-triggered, not automatic paid
fallback for routine work. Reuses `RoutingDecision`'s existing
`executor`/`escalated`/`escalation_reason` columns (already typed for
`codex`/`claude`) — no schema change.

**Real bounded end-to-end proof:** `code-strong` (intentionally unbound —
no LM2 winner ever targeted it) with `allow_paid_escalation: true`
executed against live `codex exec`, returned the exact expected output,
`deterministic_gate: pass`. The originating `RoutingDecision` row was
updated in place (not a second row):
`executor=codex, status=complete, escalated=True,
escalation_reason=insufficient_capability, model_alias=code-strong`.

Gate met: one real paid escalation succeeded through Odysseus.

## Resource-aware lab scheduling (P12.4)

No existing host-load/reservation mechanism found in `src/`/`core/`
before this pass (targeted search). Added the minimum:
`experiment_priority_active()` checks a host-local reservation file
(`~/.aoteru/experiment_reservation.json`, never committed) OR live
`nvidia-smi --query-compute-apps` evidence of a non-Ollama process
holding ≥500MiB on the shared RTX 3080 — either signal is sufficient.
Tagged the three heaviest/longest-running aliases in
`config/models.yaml` (`local-strong`, `reasoning-strong`, `vision`) with
`gpu_priority: yield_to_experiment`; `local-fast`/`code-fast` are
untagged (small, bounded, low contention risk) and stay eligible either
way.

Both states live-verified against the **real** production config (not
just the test fixture):

- idle: `reasoning-strong` → resolved (`nemotron-3.5-lightning:30b-a3b`);
  `local-fast` → resolved.
- with `~/.aoteru/experiment_reservation.json` `{"active": true}` present:
  `reasoning-strong` → withheld ("experiment priority active..."; deleted
  the marker file immediately after the test, no residual state).
  `local-fast` → still resolved.

Gate met: Aoteru cannot accidentally steal the RTX 3080 from an active
experiment — proven, not just coded.

## Glovebox Jetson qualification (P12.5)

Live-reachability re-checked twice this pass (P12.0 and again explicitly
for P12.5): `tailscale status` shows offline (36d), `tailscale ping`
times out with no reply. `role` corrected to `experiment-edge`;
`candidate_capability_tags: [ros2, realsense, experiment-capture,
edge-perception, robotics-logs]` recorded as vocabulary only — none
assigned live, since assigning them to an unreachable host would be
unearned eligibility. The P12.5.6 safe read-only proof is truthfully
deferred for the same reason (no route can be proven against a host this
session cannot reach), not a safety concession on a live host.

Structural guarantee already in place regardless of future reachability:
`src.estate_router.eligible_hosts()` only ever considers `role` in
`(lab, home)`, so `experiment-edge` can never become a generic execution
candidate for `local-fast`/`code-fast`/background work even once
reachable — no new code was needed to enforce this boundary.

## Fault/security tests (P12.6)

| check | result |
|---|---|
| model unavailable → bounded failure recorded | `test_resolve_alias_bound_but_not_live_fails_truthfully` |
| unverified host → ineligible | `test_eligible_hosts_explicit_verified_false_blocks_even_if_reachable` |
| conflicting park lease → mutation refused | existing `tests/test_agent_cli_parking_lease.py` (5 tests, unchanged) |
| experiment reservation → heavy route yields | new P12.4 tests + live proof above |
| multimodal task → unified route/telemetry | new P12.2 test + live proof above |
| generic task never routes to experiment-edge | structural (`eligible_hosts()` role filter) + `test_eligible_hosts_excludes_interface_role`-style coverage |
| auth failure → no bypass invented | `svc:odysseus-lab`: `AUTH_ENABLED=true`, `LOCALHOST_BYPASS=false` (config/estate.yaml, unchanged this pass) |
| no new public exposure | `tailscale funnel status` → "tainet only" for both URLs; `tailscale serve status --json` → `Web` handler proxying only to `127.0.0.1:7001`, no `AllowFunnel` key |

**Full-suite baseline:** `python3 -m pytest tests/` → **4906 passed, 11
failed, 4 skipped** (118s). All 11 failures are pre-existing and
unrelated to any file this task touched: 10 are `mcp_servers/*` collection
failures (`AttributeError: 'Server' object has no attribute 'list_tools'`
— an MCP SDK version mismatch predating this task) and 1 is
`test_upload_handler_atomicity.py::test_partial_write_recovery_via_bak`.
Not repaired, per the task's own "do not spend the phase repairing known
unrelated baseline failures unless a changed surface caused them" —
`estate_router.py`/`models.yaml`/`estate.yaml`/`routing.yaml` never touch
`mcp_servers/` or `src/upload_handler.py`.

`tests/test_estate_router.py` itself: 34/34 pass (8 new tests added
across P12.2–P12.4). `tests/test_agent_cli_parking_lease.py`: unchanged,
passing.

## Future host re-entry contracts (P12.7)

Not executed this phase — checklists only, per the task's "prepare, do
not execute."

**Interface PC re-entry** (when it next appears on tailnet/LAN):

1. confirm identity/hostname/OS/hardware/Tailscale/LAN role live — do not
   reuse the historical `192.168.4.37:8770` reference without
   re-verification.
2. inventory whatever UI/Misumi/Aoteru service is actually present there.
3. deploy/restore `svc:aoteru` (`config/estate.yaml`, currently
   `endpoint: null`) as the persistent authenticated front door only
   after private connectivity and rollback are proven.
4. integrate phone/mobile to that front door.
5. qualify as an execution worker only if hardware + benchmark evidence
   later justify it — never on mere reachability.

**Home PC re-entry** (when `desktop-in7o23d`/`desktop-in7023d` next
resolves live):

1. live-confirm identity (resolve the IN7O23D/IN7023D spelling ambiguity),
   OS, hardware.
2. inventory household/Misumi, storage, memory, GPU/model runtime, service
   state.
3. decide service placement (household/Misumi, memory-primary) from
   measured fit, not assumption.
4. if hardware can help compute, benchmark the same estate task classes
   against lab (reuse `evals/local_models/` harness, LM1–LM4 pattern)
   before adding any worker route.
5. shadow/canary before promotion (same discipline LM4 established for
   local models) — never auto-promote on mere reachability.
6. preserve single-writer/lease and domain authority across hosts.

Neither host is required for P12 closure; both remain
registered-but-ineligible in `config/estate.yaml`.

## Acceptance criteria — status

1. ✅ estate config truthfully distinguishes laptop, lab, glovebox, home,
   interface.
2. ✅ laptop proven thin-controller by design (never a routing candidate,
   `routing.yaml`); lab proven general worker via 4 live task-class routes.
3. ⚠️ partial — proven from the lab end; the laptop-submitted leg is the
   documented continuation gate above (no laptop-run session this pass).
4. ✅ all current text + vision aliases traverse one `run_task()` path
   (live-proven for `local-fast`, `code-fast`, `vision`; structurally true
   for `local-strong`/`reasoning-strong` — same code path).
5. ✅ real paid escalation succeeded through Odysseus (`code-strong` →
   codex, live proof above).
6. ✅ lab GPU/background inference yields to experiment priority
   (live-proven both states).
7. ✅ Jetson live-inventoried (offline result, recorded truthfully) and
   structurally constrained to experiment-edge capabilities.
8. ⚠️ deferred, not proven — Jetson is unreachable; no route could be
   safely demonstrated against a host this session cannot reach.
9. ✅ home/interface ineligible with precise re-entry contracts (P12.7).
10. ✅ leases/authority/auth/private-exposure/LM4 bindings regression-clean
    (park-lease tests unchanged; `AUTH_ENABLED`/`LOCALHOST_BYPASS`
    unchanged; Funnel still tailnet-only; `config/models.yaml`'s 5 bound
    aliases untouched except the additive `gpu_priority` tag).
11. ✅ 4906/4917 collected tests pass; the 11 failures are pre-existing and
    unrelated (see P12.6 table).
12. ✅ evidence committed; verify `origin/dev` == local `HEAD` at closure
    (see final report).

## Residual risks, ranked by impact

1. **Laptop→lab direction genuinely untested end-to-end.** Everything on
   the lab side is proven; nothing has confirmed the laptop can actually
   reach and drive it. Low effort to close (see P12.1's continuation
   gate) but real until someone runs a session on the laptop itself.
2. **Glovebox identity/hardware is still hypothesis, not confirmed live**
   (Jetson Linux/JetPack version, `/data/s2-e1` layout) — offline for at
   least 36 days at time of writing. No experiment-edge capability should
   be trusted until it's next reachable and re-inventoried.
3. **`experiment_priority_active()`'s live-GPU signal is a heuristic**
   (≥500MiB non-Ollama process), not a real experiment-scheduler
   handshake — a robotics job using less VRAM, or one that never touches
   this GPU at all (e.g. pure Jetson-side work), won't trip it; the
   explicit reservation-file signal is the more reliable path and should
   be the one experiment tooling actually sets.
4. **`execute_codex()`'s bounded proof used a single trivial prompt.**
   The mechanism works, but no evidence yet exists for how it behaves
   under a genuinely hard/ambiguous task, retries, or cost/quota pressure
   — `paid_tokens`/cost accounting remains unpopulated (matches
   `config/routing.yaml`'s `budget_defaults`, which are still null by
   design).
5. **Pre-existing MCP SDK collection failures (10 tests) are untouched.**
   They predate this task and are out of scope here, but they mean
   `mcp_servers/email_server.py`, `memory_server.py`, `rag_server.py` have
   no passing test coverage right now — worth a dedicated fix outside P12.

## Next-phase recommendation

Not manufacturing a P13. Per the task's own guidance, the real triggers
are: the interface PC or home PC returning live (front-door/mobile
integration, or memory/secondary-worker qualification per the P12.7
checklists above), or enough real production `RoutingDecision` traffic
accumulating to justify the routing contract's full replay/shadow
evaluator. None of those conditions are met yet.
