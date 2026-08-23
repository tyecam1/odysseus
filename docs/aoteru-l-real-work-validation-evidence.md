# Workstream L — real-work validation evidence

Ran 2026-08-23, lab host (`hz2-workstation`), against the live production
Odysseus service — real `RoutingDecision` rows, real Ollama models, real
`codex` CLI. Not a second offline test harness: every result below has a
`decision_id` in `core.database.RoutingDecision` (except the two
intentionally-blocked host cases, which never reach routing/decision
recording at all — they fail before that, which is itself the correct
truthful-block behaviour).

## 1. Local task (stays local)

`src.estate_router.run_task()` with `capabilities: [local-fast]`:

- objective: "what does `execute_local` do?" (this session's own code)
- resolved: `qwen3:8b`, executed locally
- result: `ok: true`, `retries: 0`, `latency_ms: 5838`, `deterministic_gate: pass`
- decision_id: `002ce653-a010-4d9b-a551-23d124524b33`

Confirms the retry-instrumentation added this session
([[C-execution-plane]]) reports `retries: 0` correctly on a first-attempt
success, not just on paths that actually retried.

## 2. Multimodal task

`run_task()` with `capabilities: [vision]`, objective = a 2-part OpenAI-
style content list (text + a `data:image/png;base64,...` 1x1 PNG):

- resolved: `gemma4:12b`, executed locally
- result: `ok: true`, `retries: 0`, `latency_ms: 6004`
- decision_id: `798de194-24a6-4511-aec0-498412dccfea`
- model's answer was factually wrong ("Black" for a red pixel) — a model
  *quality* issue, not an infrastructure one; the multimodal envelope
  round-tripped end-to-end for real (P12.2's structural claim, re-proven
  live rather than only regression-tested).

## 3. Experiment-priority reservation

Wrote `~/.aoteru/experiment_reservation.json` (`active: true`), then:

- `agent explain local-strong` -> `resolved: false`, reason: `"withheld —
  experiment priority active (...)"` — correctly yields (tagged
  `gpu_priority: yield_to_experiment` in `config/models.yaml`)
- `agent explain local-fast` -> still `resolved: true` (never yields, by
  design) — confirms the yield is scoped to the tagged aliases, not a
  global GPU lock
- reservation file removed immediately after (host-local, never committed)

## 4. Codex paid escalation

`src.estate_router.execute_codex()` directly, objective: independent
review of this session's own `_scope_owner` security-gating change
(`routes/estate_routing_routes.py`) — a real, high-consequence fixture,
per [[C-execution-plane]]'s item 8 ("test cross-provider independent
verification where one real high-consequence fixture justifies it").

- `ok: true`, `provider: codex`, `latency_ms: 27175` — the paid escalation
  mechanism itself works end-to-end (process launch, timeout handling,
  telemetry capture all real).
- **Real finding, not fabricated success**: codex's own sandboxed file
  read failed inside this container — `bwrap: Unknown option --argv0` on
  every local read attempt, so it could not actually open
  `estate_routing_routes.py` despite `-C <repo root>` and `--sandbox
  read-only`. It answered with a generic (still substantively correct)
  security-review checklist instead of a grounded review of the real
  code. `bubblewrap 0.6.1` / `codex-cli 0.116.0` recorded for whoever
  investigates the flag incompatibility — not something this session
  attempts to patch (a sandboxing-tool version mismatch, not application
  code, and changing it is a bigger, separately-reviewable action).
- Not repeated after the first failure — "never blindly repeat a paid
  prompt" ([[C-execution-plane]]) applies even to a call that partially
  failed; the finding itself is the useful result.

## 5. Intentionally unavailable-host task (durable truthful block)

`agent park obsidian-phd` (a real registered repo, per
[[F-cross-repo-governance]]):

```
error: 'obsidian-phd' does not resolve on this host: unresolved: PHD_ROOT not set in /home/agent/.aoteru/config.local.json
```

Clean, non-destructive, informative failure — exit code 1, no traceback,
no guessed path, no fabricated access. `agent status` reports the same
three repos (`misumi`, `obsidian-phd`, `s2-e1-ros2-measurement-spine`)
consistently as `unresolved`.

## Not run this pass

- **PhD evidence/retrieval or S2-E1 ROS/log task**: both need an actual
  reachable clone, which doesn't exist on any host this session reaches
  (see [[F-cross-repo-governance]]) — item 5 above (the truthful block)
  is the honest substitute the task doc itself allows ("one intentionally
  unavailable-host task that produces a durable truthful block").
- No second/repeated paid-escalation call, deliberately, per the "never
  blindly repeat a paid prompt" invariant — one real call with a genuine
  (if partially negative) result is the correct amount of paid spend for
  this validation pass, not a retry loop chasing a clean success.
