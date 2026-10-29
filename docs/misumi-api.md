# Misumi compatibility API

Odysseus exposes a Misumi-facing compatibility surface while retaining its generic UI and APIs. Personas select context; Odysseus enforces permissions.

Only `GET /misumi/health` is unauthenticated. Every other route uses normal Odysseus cookie or bearer-token auth. Create interface tokens with the `misumi_interface` profile, which grants only `misumi:read` and `misumi:execute`; the latter currently permits planning only because Phase A exposes no household write or task-execution path.

## Health

```http
GET /misumi/health
```

Reports liveness, Phase A, and household-root reachability. Use authenticated `GET /api/ready` and `GET /misumi/status` for dependency state.

## Respond

```http
POST /misumi/respond
Authorization: Bearer ody_...
Content-Type: application/json

{
  "prompt": "What is on the shopping list?",
  "persona": "sanji",
  "mood": "focused"
}
```

Response:

```json
{
  "text": "From household/food/shopping-list.md line 3: - [ ] miso",
  "state": "speaking",
  "mood": "focused",
  "source": "odysseus",
  "persona": "sanji",
  "who": "Sanji",
  "audio_url": null,
  "voice": null,
  "tts_provider": null,
  "consulted": [],
  "capsule_id": null,
  "handoff_ids": [],
  "sources": [
    {"path": "household/food/shopping-list.md", "line": 3, "snippet": "- [ ] miso", "score": 1}
  ]
}
```

Repository-backed answers cite the canonical path and line. Missing data or model state degrades explicitly; no action is claimed.

For successful Aoteru model replies, bounded consultation may append labelled contributions from at most two personas. `consulted` identifies personas that returned a contribution, `capsule_id` references the single local consultation capsule, and `handoff_ids` references local handoff records created from successful contributions. These fields are presentation and reference data only: they grant no permission, approval, autonomy, task execution, external action, or household write access.

Consultations are synchronous within the initiating `/respond` request. They do not start background work or persona swarms. Set `MISUMI_CONSULT=false` to disable consultation; the default is enabled. When disabled, `/respond` follows the legacy path and omits the three additive fields.

## Route inspection (developer)

```http
POST /misumi/route-explain
Authorization: Bearer ody_...
Content-Type: application/json

{"prompt": "Aoteru, help me plan a dinner party: menu, tidy-up schedule and music.", "persona": "auto"}
```

Returns a stateless preview of the base persona route and pre-reply team plan. It uses the same base routing and team-policy code as
`/misumi/respond`, and may read their persona policy configuration, but it is not a preview of the final `/respond` result. In particular,
it does not carry a persisted lead, apply learned routing, resolve household records, dispatch a tool, or run post-reply consultation.
Those boundaries are machine-readable:

```json
{
  "preview": {
    "scope": "base-persona-and-team",
    "omits": [
      "persisted_lead",
      "learned_routing",
      "household_resolution",
      "tool_dispatch",
      "post_reply_consultation"
    ]
  }
}
```

The response also reports the base lead and its reasons, the team-policy decision with supports/exclusions/reasons, a lexical
`household_domain` label, and the shared safety-gate labels. `household_domain` does not mean `/respond` will return a
`household-read-only` result: this endpoint does not query household records or claim deterministic household execution. Its team plan is
formed without a primary reply, so `/respond` may make a different post-reply consultation decision. It is neither a broad persona
showcase nor a final routing trace.

The endpoint needs `misumi:read`, never calls a model, writes no state, and does not read household records. `executes_model: false` and
`writes_state: false` describe this inspection request only; they do not predict whether a later `/misumi/respond` call will execute a
model, tool, consultation, household read, or state update. `persona` is `auto` (default) or a persona id the caller selected.
Persona ids are the ids supported by the current persona policy; matching ignores surrounding whitespace and case. An unknown id returns
422 rather than silently falling back to Aoteru.

## Per-turn task assignments for support personas

A persona recruited as a support keeps its identity and permanent role. For that one turn it is also given a **task assignment**,
`{"task_role": "critic", "focus_intents": ["budget"]}`: a task role plus the routing intents that justified recruiting it, taken only
from the evidence team selection already records (a persona named without intent evidence gets an empty focus). The assignment appears
on each support record of the `team` block in `/misumi/respond` and in `/misumi/route-explain`, is stated to the support in its
consultation prompt as one fixed sentence ("your identity and permanent role are unchanged"), and is reflected in the handover purpose
(`critic: analyse from the ... perspective, focusing on budget`). It is ephemeral: nothing is stored, learned or promoted, recruitment
rules are unchanged, a learned (structured) consult never receives one, and focus values are limited to plain tokens (maximum 5).

## Task planning

```http
POST /misumi/task
Authorization: Bearer ody_...
Content-Type: application/json

{
  "prompt": "autonomously complete agentic routed tasks",
  "persona": "aoteru",
  "mode": "task",
  "approval": "none"
}
```

Task mode scans the documented file queues, ranks the critical path, and returns `planned` or `blocked` with candidates, files read, blockers, policy, and a handoff prompt. It never squeezes task state into chat text and never mutates the household repository.

Valid approval values are `none`, `plan_only`, `approved_read_only`, and `approved_execute`. Approval cannot enable Phase B household writes.

## Personas and skills

```http
GET /misumi/personas
GET /misumi/personas/kurisu/skills
POST /misumi/personas/kurisu/skills/audit
```

Skill lists are filtered by the versioned persona policy. Audits are admin-only and do not publish external skills.

Persona prompt context also reads `config/capabilities.yaml` from the assigned
household seed root when present. It exposes capability-group stewardship and
reviewed external patterns as bounded context only. Missing or malformed data
degrades safely, and the projection never grants tool authority or write access.

## External skill intake

```http
POST /misumi/skills/quarantine
GET  /misumi/skills/quarantine/{intake_id}
POST /misumi/skills/quarantine/{intake_id}/promote
GET  /misumi/skills/{candidate_id}/active
POST /misumi/skills/{candidate_id}/rollback
GET /misumi/skills/security-review/{skill}
```

The former mutable-ref `/misumi/skills/import-draft` route returns 410. Intake is
admin-only and accepts only a GitHub URL pinned to a lowercase full 40-character
commit together with a gap, capability IDs, SPDX licence, dependency pins, and
maintenance evidence. The constrained fetcher hands text bytes to a separate
quarantine; candidate code is never imported or executed. Static review covers
secrets, network access, destructive behaviour, prompt injection, persistence,
telemetry, dependencies, and capability overlap. Scripts, runtime dependencies,
unlicensed inputs, and flagged bundles remain quarantined.

Only prompt/data bundles that pass policy can be promoted, and promotion requires an
authenticated admin plus a meaningful approval reason. SkillsManager reads the
integrity-verified active-release pointer directly and never scans quarantine. A
rollback atomically repoints that pointer to a previously verified release. Every
stage, promotion, and rollback emits an immutable intake audit record.

## Status

```http
GET /misumi/status
```

Reports readiness, household reachability and Git dirtiness, task counts, persona skill counts, recent event-log count, Phase A, and `writes_allowed: false`.

The additive `memory` object reports capsule, inbox, open-loop, stale-loop and pending-handoff counts together with the newest capture, top open loop, recommended action and responsible persona. `memory.writes_allowed` is always `false`; local memory persistence does not grant household writes.

## Passive memory

All write routes below require the existing `misumi:execute` scope. Read routes require `misumi:read`.

```http
POST /misumi/memory/capture
GET /misumi/memory/inbox?limit=20
GET /misumi/memory/recent?limit=20
GET /misumi/memory/open-loops
POST /misumi/memory/{id}/confirm
POST /misumi/memory/{id}/route
POST /misumi/memory/{id}/close
GET /misumi/glance
```

Capture accepts `text` plus optional `source`, `type`, `persona`, `entities`, `next_action`, and `meta`. It returns the full capsule. Explicit type and persona values override deterministic inference; invalid values return 422. Confirm, route, and close append a new version of the capsule. Listings fold these versions and report `corrupt_lines` rather than failing on malformed JSONL records.

Route body:

```json
{"persona_primary": "ichigo", "persona_secondary": "kurisu"}
```

Close body is optional and may contain `{"resolution": "verified locally"}`.

## Local handoffs

```http
POST /misumi/handoff
GET /misumi/handoffs
GET /misumi/handoffs?status=pending
POST /misumi/handoffs/{id}/resolve
```

A handoff contains `from_persona`, `to_persona`, a short local `action`, and optional `capsule_id` and `note`. It is a local coordination record only. Actions containing outbound operations such as email, notification, payment, transfer, posting or calling are rejected.

## Interface-box configuration

After side-by-side validation, set the box-local `agentUrl` to:

```text
http://DESKTOP-IN7O23D:420/misumi
```

The interface-box server appends `/respond`. Store `ODYSSEUS_API_TOKEN` only in the box process environment; its proxy adds the Authorization header server-side. Keep port 4500 as the fallback until end-to-end evals pass.


## Durable transcripts and history controls

`POST /misumi/respond` now accepts `history_mode` (`"auto"` or `"off"`), an independent control for the ordinary conversation session history. `retention_mode` continues to govern semantic memory and artifacts. When `history_mode` is omitted the historical coupling is kept so that clients which send `retention_mode: "off"` to mean "store nothing" stay private; `persist_turn: false` is always incognito. The response reports `history_persisted`.

Durable, owner-scoped, idempotent microphone transcripts live under `/misumi/transcript/*` (audio ingest, text ingest, wake attachment, bounded query/export, retention policy, box day-file import). Disabled by default (`ODYSSEUS_MISUMI_TRANSCRIPT_ENABLED`) and gated per owner. See `docs/misumi-durable-transcript-runtime.md`.

## Evaluation-linked demonstration (`/misumi/demo/*`)

A labelled view over the existing handlers, not a second execution path or schema (`src/misumi_demo.py`). Guest functionality needs `misumi:read`. Developer functionality (developer mode, a replaced prompt, developer replay) needs `misumi:execute`; this is enforced by the backend, so the interface's own `demoDeveloper` setting is not what restricts it.

- `GET /misumi/demo/scenarios`: the catalogue (`config/misumi_demo_scenarios.json`), whether guest mode is available on this instance and why, which scenarios have recordings, and the five evidence kinds.
- `POST /misumi/demo/run` `{scenario_id, mode: "guest"|"developer", execution: "live"|"replay", prompt?, session_id?}`: runs the scenario through the same `/respond` handler (household resolution, model, consultation; conversation history, learning and memory forced off) or, for music, the same `music_reply` parser and `MusicController` with a `SimulatedMusicProvider`. Returns one inspection record (`misumi-demo-inspection-v1`). Every section is labelled `observed`, `simulated`, `replay`, `offline_evaluation` or `shadow_proposal`, and every measurement is `measured` or `unavailable` with a reason (tokens, paid cost and model calls are not instrumented on this path and are reported unavailable, never estimated).
- **Guest mode** is fail-closed and re-verified on every request (`demo.verify_synthetic`): `MISUMI_DEMO_GUEST=1`; the household root and any other configured source root (`DOMAIN_ROOT_VARS`) are inside, or themselves carry, a `.synthetic-household` marker; the household root's content digest equals the approved fixture's (a copied marker on another tree is refused); no research root is set; `ODYSSEUS_DATA_DIR` is explicit and marked; the routing/persona/dialogue state stores are set and every writable root lies inside that data directory; `MISUMI_MUSIC=0`; no link inside the household leaves it. Diagnostics name variables, never paths. Prompts are the catalogue's exactly; prompts are the catalogue's exactly; the host name, source paths, shadow proposals and evaluations are not returned. Anything else answers 409/422.
- **Developer mode** may replace the prompt (`prompt_source: "operator-typed"`), shows the real model/backend/host, consultations, offline evaluation references and the experimental shadow allocation proposal (never executed, `live_effect: none`, labelled as having failed its promotion criteria), and a Phase B input row whose judgement fields are empty.
- **Session state and what persists.** Each demonstration session (caller + optional `session_id`) has its own simulated music runtime (in memory, at most 32 sessions, oldest evicted) and its own event log file under `<event log directory>/demo-sessions/`. A run still writes one ordinary operational event record there (route, persona, outcome, latency), so it is telemetry on disk until the session is reset, evicted, or the process restarts (stale files are removed at start-up). It does not write conversation history, learning, memory or the shared operational event log. The `guest_safety` object states this and nothing stronger.
- A live run and a reset must carry an explicit `session_id` (and never `default`): a shared default would let one visitor reset another. Replay needs none. A session's event file keeps only its most recent 50 records.
- `POST /misumi/demo/reset?session_id=`: only on a verified guest instance; clears that session's simulated playback and its own event file. The shared operational event log and other sessions are untouched.
- The evidence scenario adds `evidence_review`: the two records it is about are read straight from the synthetic files (no model) and quoted with file and line, with the catalogue's assessment (`unresolved` here, because a 2026-10-01 stock count and an unticked 'Need' line do not contradict each other and neither says how many tins exist today) and the evidence that would settle it. It is produced only from a verified synthetic root; if an expected record is missing the review says `unavailable`. The lead's own model answer stays labelled as unverified.
- Replay serves a stored inspection (`evals/misumi-demo/recordings`, captured by `evals/misumi-demo/record.py`, never overwritten) labelled as a replay. A recording's `capture` record names the recorder, the source revision, the fixture digest and how many live attempts were needed (a reasoning model sometimes returns an empty reply; a degraded run is retried up to three times and saved as degraded if it still fails). Only a recording that passes `demo.validate_recording` is offered: a developer live inspection of that scenario, stamped `provenance.synthetic_verified` for the shipped fixture's marker, naming only sources that exist in that fixture, with no host, absolute path, address, e-mail or token-looking text. `record.py` refuses to save from an instance that does not report verified synthetic provenance, and runs the same validator before writing.
