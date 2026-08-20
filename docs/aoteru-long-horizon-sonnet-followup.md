---
title: Aoteru long-horizon Sonnet continuation
status: execution-contract
owner: odysseus
as_of: 2026-08-20
scope: deep review, adaptive routing implementation, P8-P10 lab-first convergence
---

# Aoteru long-horizon Sonnet continuation

## Mission

Continue the existing Aoteru estate rollout from the current repository state. Do not restart P0-P7 or trust the prior checkpoint blindly. First perform a targeted adversarial deep review of what is actually committed and live, reconcile any stale claims, then implement the highest-leverage remaining work through the furthest truthful lab-first cutover possible.

Binding authorities, in order of relevance:

1. `docs/aoteru-estate-implementation-plan.md`
2. `docs/aoteru-estate-execution-contract.md`
3. `docs/aoteru-lab-first-continuation.md`
4. `docs/aoteru-model-host-routing-contract.md`
5. current config, tests, runtime evidence and Git history

Live evidence overrides old prose. Domain repositories retain their own authority and gates.

## Historical checkpoint to verify, not assume

The previous session reported P0-P7 as complete with live evidence; P0-P5 had fresh-context verification, while P6/P7 were assessed directly. At that checkpoint P8-P10 had not started. Earlier connectivity assumptions were corrected: `DESKTOP-7DJ1HMA` is the laptop/interface, lab is the current reachable worker, and home is registered but unavailable/unverified. Git push/authentication was previously a blocker but may now be resolved; establish current local/remote truth rather than repeating the old claim.

## Phase A — deep review before further implementation

Perform a compact but substantive audit, not a ceremonial re-run:

- reconcile `HEAD`, `origin/dev`, working tree and recent commits; preserve all valid work and push durable commits when authorised;
- inspect the actual P0-P7 evidence, implementations and tests against the four binding contracts above;
- specifically challenge P6/P7 because they lacked the same independent fresh-context verification as P0-P5;
- look for topology drift, duplicate authorities, false PASS states, stale host/model assumptions, unsafe privilege/network exposure, token-wasting duplication, and conflicts with existing upstream Odysseus or domain-repo capabilities;
- inspect whether the new model+host routing contract changes any conclusions or implementation choices already made in P0-P7;
- use deterministic checks first; use bounded read-only scouting for breadth; use one independent fresh-context verifier only where a material gate or architectural claim warrants it;
- correct real defects immediately and record the evidence. Do not redo already-proven work merely for reassurance.

Exit Phase A only with a concise machine-readable/committed statement of: confirmed passes, corrected defects, deferred gates, and first executable unmet gate.

## Phase B — implement the central adaptive model+host routing contract

Treat `docs/aoteru-model-host-routing-contract.md` as binding architecture and implement it centrally in Odysseus before domain-specific routing proliferates.

Required properties:

- laptop/interface owns conversation and dispatch, not heavy execution;
- lab is currently eligible/live; home remains registered but ineligible until live-verified;
- host eligibility/parking/authority is resolved before model selection;
- deterministic mechanisms precede inference;
- adequate local models precede paid inference where benchmark evidence supports the quality floor;
- cloud workers are routed through stable aliases/capabilities rather than duplicated hard-coded provider logic;
- worker handoffs carry objective + evidence/context pointers, not copied transcripts;
- one primary worker per work unit; independent second-model review only for defined verification, disagreement or failed gates;
- normal escalation is deterministic/local -> cheap worker -> routine strong worker -> frontier worker, governed by measured adequacy rather than static prestige;
- conversational Claude/Sonnet owns intent and user-facing synthesis, not default execution;
- no second queue, router, scheduler, agent lifecycle, parking authority, memory authority, or MCP business-logic layer.

Continuous improvement is required, not optional. Capture per-route telemetry sufficient to improve routing over time: task class, host/model/mechanism, success/failure, deterministic gate result, retries, escalation, latency, token/quota consumption where observable, context size, and verification outcome. Use recency-weighted empirical performance to re-score eligible routes. Permit bounded exploration/canary/shadow evaluation only among routes that already satisfy permissions and quality floors. Never silently weaken safety, domain gates, verification requirements or authority in the name of optimisation. New/home models and hosts enter through live discovery + benchmark qualification, not prose edits.

Prefer the weakest adequate mechanism. Do not spend frontier tokens on routing decisions that config/telemetry can make deterministically.

## Phase C — P8 domain convergence

Proceed with P8 wherever lab-buildable now. Deep-review existing `obsidian-PhD`, Misumi and upstream Odysseus capabilities before adding anything. For every capability touched, determine KEEP / EXTEND / WRAP / MOVE / RETIRE / NEW with evidence; `NEW` requires targeted inspection proving no suitable existing owner exists.

Converge domain integrations onto the central estate contracts without moving domain truth into Odysseus. Preserve repo-local governance, skills and permissions. Avoid duplicated retrieval, task, memory, model or approval systems.

## Phase D — P9 fault/security validation

Run every P9 test possible on the current laptop+lab single-worker slice, including at minimum truthful route failure, unavailable-home handling, lease/write exclusion, dirty-worktree preservation, service restart/persistence, private-only exposure, auth boundaries, model/runtime failure, stale inventory, partial result handling and durable blocked/retry state.

Home/dual-worker/failover tests that physically require the unavailable home PC remain `DEFERRED` with exact future evidence required. They are not PASS and do not block unrelated lab-first validation.

Use independent verification for security-critical or cutover-critical claims.

## Phase E — P10 lab-first cutover

Cut over only the functionality proven on the accessible estate. It is valid to reach `LAB-FIRST CUTOVER`; it is not valid to claim full-estate completion while home-dependent gates remain deferred.

The usable target is:

`user on laptop -> Aoteru/Sonnet conversational surface -> Odysseus memory/authority/host router -> parked lab worker -> deterministic/local/Claude/Codex worker -> verification -> compact result -> same laptop conversation`

Ensure generated bootstrap/context remains minimal and routing/memory state is retrieved on demand. Verify rollback, service persistence, repo cleanliness, origin durability and operator documentation.

## Execution discipline

- Work autonomously for the long horizon; do not repeatedly stop because home is unavailable.
- Ask for human action only when an actual privilege/credential/physical-device boundary prevents further safe work; when needed, report exactly one minimal command/action.
- Do not bypass harness/security boundaries by command rephrasing.
- Commit coherent increments and push when authorised; keep Git history and evidence truthful.
- Use Sonnet as lead. Use deterministic tools first, cheap/read-only agents for bounded scouting, and stronger/independent models only where the routing contract or verification need justifies them.
- Do not expose chain-of-thought or preserve verbose worker scratchpads; retain compact evidence/result envelopes and durable pointers.
- If a newly discovered defect invalidates an earlier phase, repair it and update the phase evidence rather than protecting the old PASS label.
- Stop only at a genuine human-only blocker, verified lab-first cutover, or usage limit. At stop, leave one durable checkpoint containing exact state, commits, passes, deferred gates, blockers and first next action.

## Success condition

The lab-first estate is operational from the laptop through one Aoteru surface; P0-P8 and all applicable P9/P10 gates are evidenced; model+host routing is central, adaptive and telemetry-driven; local compute is exploited before paid inference when adequate; no duplicate authority has been introduced; home remains a clean deferred worker that can join later through discovery/qualification without redesign.