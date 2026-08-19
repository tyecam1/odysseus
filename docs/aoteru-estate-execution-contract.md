---
title: Aoteru estate execution contract
status: execution-contract
owner: odysseus
as_of: 2026-08-19
canonical_plan: docs/aoteru-estate-implementation-plan.md
---

# Aoteru estate execution contract

Execution-only wrapper for the canonical estate plan. It does not replace architecture truth in `docs/aoteru-estate-implementation-plan.md`.

## Goal

Execute the canonical Aoteru estate programme P0→P10 autonomously from the verified `tyecam1/odysseus` environment, then leave `docs/future-work/continuous-estate-steward.md` as the next bounded programme.

## Odysseus lineage — binding

`tyecam1/odysseus` is the Aoteru target fork and canonical destination for domain-neutral estate capability.

The existing lab deployment at `/home/agent/projects/odysseus` tracking `pewdiepie-archdaemon/odysseus` is an upstream/runtime capability source, not an unrelated system. Preserve the running service while auditing it capability-by-capability. Appropriate, port, wrap or generalise every useful feature into the Aoteru target where it fits the canonical ownership model. Do not duplicate an adequate upstream feature and do not replace the running deployment until parity, rollback and cutover are proven.

For every planned capability establish:

`capability | existing implementation(s) | canonical owner | KEEP/EXTEND/WRAP/MOVE/RETIRE/NEW | evidence`

`NEW` is allowed only after targeted inspection of Aoteru Odysseus, upstream Odysseus, Misumi, obsidian-PhD and relevant live runtime shows no adequate implementation.

Never create a second queue/task lifecycle/schema, router/model gateway, scheduler/agent loop, memory authority, retrieval/vector authority, capability registry, MCP business-logic layer or approval authority.

## Authority

- Odysseus: neutral estate discovery, execution, routing, jobs, parking and personal-memory broker.
- Misumi: Aoteru persona and household policy.
- obsidian-PhD: PhD knowledge, research workflow, evidence/trust/write gates.
- Other repos retain their own local authority.

Before acting in another repo, load and obey its live `CLAUDE.md`, `AGENTS.md` and relevant rules. Live implementation/runtime truth overrides stale planning prose. Never move domain-specific authority merely for convenience.

## Method

Execute P0→P10 strictly in dependency order. Resume from the first gate not demonstrably passed.

For each phase:

`inspect truth → smallest dependency-safe slice → implement → test → fresh-context verify gate → repair until PASS → record compact evidence → coherent commit → continue`

Do not stop between phases or merely report findings.

Use one existing Odysseus task/progress mechanism as durable state. Create no parallel planning/task system. Store paths, hashes, test results and decisions rather than duplicated prose. Do not reread completed evidence unless a dependency changed.

## Resource policy

Use the weakest adequate mechanism:

`deterministic shell/test → Haiku Explore → Sonnet`

- Haiku Explore: bounded read-only search, inventory, archaeology, comparison and log reduction.
- Parallelise only independent read-only scopes.
- Sonnet lead: implementation, integration and unresolved judgement.
- Fresh-context Sonnet verifier: phase gates only.
- Add no further agent role unless repeated evidence shows lower total cost/complexity.
- Do not use model inference for deterministic work.
- Do not select/download large local models before P0 inventory and P7 benchmark evidence.

Prefer existing skills/hooks/MCPs/connectors. CLI is preferred where simpler. Deterministic hooks enforce hard invariants.

## Laptop Claude routing skill — required UX

The normal human interface should remain the user's local laptop Claude session. Implement one user-scoped, Odysseus-owned Claude skill generated/installed by `agent sync`; it is an ergonomic wrapper over the existing estate-control/`agent` routing plane, never a second router or authority.

Required logical modes:

- `auto <task>`: resolve the appropriate host/repo/session from live estate state;
- `lab <task>`: dispatch/resume a native lab-PC Claude execution context;
- `home <task>`: dispatch/resume a native home-PC Claude execution context;
- `where`: report the current logical remote sessions/parking state;
- explicit interactive handoff only when genuinely needed.

The laptop conversation remains the front end. Normal routed work is executed remotely next to the repo, preferably through non-interactive Claude/agent execution, and returns a compact structured result to the laptop conversation; do not require the operator to enter nested SSH terminals for ordinary work.

Claude transcripts are machine-local. Do not pretend one transcript is shared across PCs. Odysseus must persist the logical session mapping needed to resume the correct native remote session, minimally `{logical_session, host, repo/worktree, claude_session_id_or_name, lease, last_result/handoff}`. If cross-machine transcript continuity is later needed, implement it only through a validated shared SessionStore/equivalent rather than copying opaque session files ad hoc.

The skill must contain no hard-coded hostnames, paths, repo maps, credentials or business logic. It queries live Odysseus state and obeys parking, target-repo governance and fallback rules. If the requested host is unavailable, explicit `lab`/`home` fails truthfully; `auto` may choose another valid route.

Gate this UX across the existing phase sequence rather than introducing a new phase: P1 installs/discovers the user-scoped skill and live host IDs; P3 proves lab/home native dispatch + session mapping + parking; P5 proves invocation from an arbitrary local laptop Claude repo/session without importing domain configuration or spending Claude inference merely to route.

## Human escalation

Before asking the operator, independently establish all four:

1. proposed action is correct against current evidence;
2. human authority, credential or physical action is genuinely required;
3. no authorised alternative can complete the objective;
4. an independent verifier agrees.

Otherwise continue autonomously.

When blocked, ask once using only:

`BLOCKED | WHY HUMAN | EXACT ACTION | EXPECTED RESULT | WHAT CONTINUES AFTER`

After approval of a bounded objective, revalidate assumptions then execute that objective autonomously through implementation, debugging, retries, testing, verification and normal commit/PR handling. Ask again only for a materially new authority/risk boundary.

The future WhatsApp approval channel is transport for existing human authority, not a second approval authority. Do not implement an insecure/ad-hoc version before its dependencies and validation are ready.

## Safety

- Preserve repo governance and research-integrity gates.
- No public model/MCP/shell/control endpoints.
- No active-active writes.
- Once parking exists, no mutation outside its lease/write scope.
- No secrets, model weights or live memory DBs in Git.
- Derived memory/indexes are never domain truth.
- No false completion or silent permission/model escalation.
- Preserve old implementations during migration until parity + rollback are proven.

## Phase order

P0 freeze/inventory/backups/capability + upstream dedup audit
P1 estate registry + operator bay
P2 private connectivity
P3 parking + remote native execution
P4 central Aoteru memory
P5 Claude Code/MCP/hooks integration
P6 mobile universal access
P7 local-model benchmark + cost routing
P8 domain convergence
P9 fault/security validation
P10 cutover

## Start

Read applicable Odysseus operating instructions, the canonical plan, this contract and existing compact progress state. Inspect Git/runtime truth and begin the first unmet P0 gate immediately.

Initial response only:

`PHASE | STATE | DELEGATION | GATE`

Then work autonomously; do not wait for `continue`.
