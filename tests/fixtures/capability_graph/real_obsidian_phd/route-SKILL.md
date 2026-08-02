---
name: route
description: Classify a task packet (or, advisory-only, a free-text description) against the architecture-selection gate, pick the cheapest sufficient lane on the Fable-Sol routing ladder, and emit the exact dispatch command, verification route, rollback, and handoff path. Free text is advisory only and can never authorise mutation. Authority-bearing actions (merge/accept/recover) require a separately recorded dual-agreement AGREE before they proceed.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---

# /route — Fable-Sol Routing Loop

Status: policy/contract only. This is a thin prose contract for a human
operator or an orchestrating agent to follow by hand. There is no runtime
router, scheduler, or service — nothing in this repo reads this file,
classifies a task, selects a lane, invokes `codex exec --model gpt-5.6-sol`, or spawns a
subagent automatically. Every invocation shown below is run manually.

This skill is UNREGISTERED in `automation/config/odysseus_skill_registry.yaml`
(utility-skill class): it carries no `task_type`, no dispatch surface, and
no write scope granted by registration, per that registry's own
conventions (the registry forbids registered-utility entries, and
`dispatchable: false` entries are inventory-only, never a dispatch grant).

## Use This Skill When

- deciding which lane should carry out a task packet, before dispatch
- stating the gate classification that justifies that lane
- deciding whether a proposed action needs the dual-agreement protocol
  before it can proceed
- failing closed — producing an operator decision card — when a task
  cannot be classified with confidence

Do not use this skill for:
- doing the work itself (`/route` routes; it never implements)
- granting a dual-agreement AGREE directly (it drafts the proposal; Sol's
  independent review and a recorded AGREE are separate steps)
- treating a free-text description as authorisation for any mutation
- dispatching anything under `automation/docs/dual-agreement-protocol.md`
  section 4 (never delegable — see "Authority-Bearing Actions" below)

## Repo Boundaries

- `/route` itself never writes canonical, evidence, ontology, or Zotero
  paths.
- Anything `/route` helps produce (dispatch notes, gate-classification
  records, decision-packet drafts) belongs under `automation/review/**` or
  as fields inside the task packet itself — never directly in canonical
  paths.
- `/route` grants no authority beyond what the named task packet's
  `allowed_paths` / `denied_paths` already state, and no authority beyond
  what a recorded dual-agreement AGREE already grants for one named
  instance.

## Primary Inputs

1. **Authoritative**: a task packet path under
   `automation/review/agent-tasks/**` (agent-task schema v1 or v2).
2. **Advisory only**: a free-text task description. Free text may inform
   discussion of the classification, but it can **never** by itself
   authorise dispatch of a mutating action, and it can never substitute
   for a lint-clean task packet (`python -m Scripts.automation
   agent-task-lint`).
3. `automation/docs/agent-architecture-selection-gate.md` — the
   classification contract.
4. `automation/docs/dual-agreement-protocol.md` — the authority mechanism
   for merge / accept / recover actions.
5. `automation/config/agent_routing.yaml` and
   `automation/config/model_execution_policy.yaml` — the executor,
   task_type, and role definitions the lane ladder resolves against.

## Classification (apply the gate)

Score the task against the ten dimensions in
`agent-architecture-selection-gate.md` section 2 (expected single-agent
baseline, decomposability, sequential interdependence, shared mutable
state, tool count, verification difficulty, coordination cost, context
fragmentation, blast radius, reversibility). The single-agent baseline is
the dominant dimension. Default to `architecture: single`; only climb the
ladder when section 4's conditions all hold and are stated explicitly.

Record the decision in the task packet's schema-v2 fields:
`architecture`, `architecture_rationale`, `single_agent_baseline`,
`execution_host`, `context_budget`, and `coordination_reason` (required
whenever `architecture != single`). Do not hard-code the Kim et al. ~45%
saturation figure as a cutoff — it is a selection prior, not a rule.

## Lane Ladder

Choose the cheapest sufficient rung. Climbing without a stated reason is
itself a gate violation.

1. **Deterministic script** — an existing CLI/report/lint under
   `Scripts/automation/**`. Prefer this first.
2. **Smaller model** — bounded parsing/inventory/fixture work, direct.
3. **Sol 5.6 worker** — `codex exec --model gpt-5.6-sol -s workspace-write
   -c model_reasoning_effort=high` against a lint-clean task packet or a
   `PLAN.md`: focused patches, tests, migrations, independent
   verification. Contract-nominal per `agent_routing.yaml` AND
   verified-working: this rung implemented every fix on PRs #436-#439.
   Prefer it for large tasks — Sol has the most usage headroom.
4. **Opus worker (Claude subagent)** — isolated worktree per task,
   bounded infrastructure/automation engineering. Use when Sol's sandbox
   blocks the target path (see Known constraints below).
5. **Sol audit** — `codex exec --model gpt-5.6-sol --sandbox read-only`,
   independent adjudication returning AGREE / AMEND / REJECT.
6. **Fable decision** — accepts or reverts a **named** task packet along
   its declared verification route only. Fable never implements.

## Invocation Examples

Each lane below is labelled by its actual observed status in this
repository's own history — **verified-working**, **contract-nominal**, or
**observed-failing** — not by aspiration. Do not upgrade a label without a
fresh, stated observation.

### Sol adjudication / verdict — VERIFIED-WORKING (`codex exec --model gpt-5.6-sol --sandbox read-only`)

```
codex exec --model gpt-5.6-sol --sandbox read-only -c model_reasoning_effort=high 'Review decision packet automation/review/decision-packets/<packet>.decision-packet.md against automation/docs/dual-agreement-protocol.md section 2. Read the stated action, scope (task id, repo, branch, PR number), evidence, and rollback. Return exactly one verdict per item, ending in an exact "VERDICTS: <id>=<AGREE|AMEND|REJECT> ..." line. Do not modify any files.' < /dev/null
```

- Verified-working: every dual-agreement verdict recorded under
  `automation/review/operator-decisions/records/` was actually produced
  this way.
- `default_mode: read-only` per `model_execution_policy.yaml`;
  workspace-write is permitted only inside a named task, never for an
  adjudication read.
- The prompt must ask for an exact `VERDICTS:` line so the verdict is
  unambiguous to transcribe. The output is the verdict text only —
  recording an exercised AGREE as one `operator-decision-record` under
  `automation/review/operator-decisions/records/` is a separate, later
  step; `/route` never treats a verdict as already recorded.

### Sol mutating lane — VERIFIED-WORKING (`codex exec --model gpt-5.6-sol -s workspace-write`)

```
codex exec --model gpt-5.6-sol -s workspace-write -c model_reasoning_effort=high '<task prompt: task-packet path, allowed_paths/denied_paths, acceptance criteria, capability-truth update instruction if capability-affecting, exact commit/push/draft-PR instructions>' < /dev/null
```

- Contract-nominal: `automation/config/agent_routing.yaml` names
  `executor: codex_subscription` for `task_type: implementation`, so this
  is the lane the routing contract expects.
- Verified-working: this lane implemented every fix on PRs #436, #437,
  #438 and #439 (2026-07-28), across many runs.
- **`--model gpt-5.6-sol` is mandatory.** Omitting it silently selects the
  Codex default model, not Sol 5.6. A session that omits it will believe
  it is using Sol when it is not. This is a defect, not a shorthand.
- Canonical source of this contract:
  `<homeBase>/.claude/skills/route/SKILL.md`. Keep this copy consistent
  with it.

### Known constraints on the Sol lane

- **Always pass `< /dev/null`.** An open stdin is the diagnosed cause of
  every observed hang: `codex exec` blocks on "Reading additional input
  from stdin..." with zero output and no commits. This bites hardest
  inside a compound command or after a heredoc, where stdin stays open.
  This is the single most important rule in this section.
- **Always put a long brief in a `PLAN.md` file**, never inline. A long
  command-line argument fails with exit 126, "argument list too long".
  The short inline prompt shown in the mutating-lane example above is the
  correct shape for that case: it points at `PLAN.md` rather than
  carrying the brief itself.
- Piping the output is **not** a problem, despite an earlier entry here
  saying so. That diagnosis was recorded on 2026-07-27, tested, and
  disproven: a piped invocation with stdin closed completes normally.
  See the appended resolution in
  `automation/review/architecture/2026-07-27-codex-workspace-write-hang-incident.md`,
  which preserves the two superseded diagnoses rather than deleting them.
- **Sol cannot write `.agents/**`** — its managed filesystem profile
  treats that tree as read-only and rejects the patch ("writing outside
  of the project"). Route edits to `.agents/skills/**` to a Claude
  subagent or the orchestrator instead.
- **Sol usually cannot commit in a linked worktree**, because the
  worktree index lives under the main repo's `.git/worktrees/` and falls
  outside its writable sandbox. Expect to leave changes unstaged and have
  the orchestrator commit and push.

### Implementation worker — VERIFIED, current preferred mutating lane (Claude subagent, isolated worktree)

Directive pattern — the same shape actually used to dispatch PR-1 (#433),
PR-2 (#434), and this PR (#435):

```
Work ONLY in the existing git worktree at <worktree-path>, already
checked out on branch <branch-name> with the task packet seeded. Read
automation/review/agent-tasks/inbox/<task-id>.agent-task.md first.
Implement its Required design and Acceptance criteria exactly; respect
allowed_paths/denied_paths strictly. If the change is capability-affecting,
update automation/docs/current-capabilities.md and
automation/docs/capability_manifest.json in the same change and run
python -m unittest Scripts.automation.tests.test_capability_truth_contracts.
Commit with a Co-Authored-By trailer, push the branch, and open a DRAFT
pull request. Do not merge.
```

- Verified: PR-1, PR-2, and this PR were all actually implemented this
  way, not through the codex workspace-write lane above.
- `isolation: one-isolated-worktree-per-task` per
  `model_execution_policy.yaml` — never the operator's own checkout.
- The worker gains no authority beyond the named task packet's
  `allowed_paths` / `denied_paths`; it must not merge its own PR.
- This routes around Sol's sandbox limits (it cannot write `.agents/**`
  or commit in a linked worktree), not around any lane failure: the
  2026-07-27 hang was diagnosed as stdin left open and is fixed by
  `< /dev/null`. It is not a change to `agent_routing.yaml`, which still
  names `codex_subscription` as the nominal `implementation` executor.

## Emit (per routing decision)

For every routed task, state explicitly:

- the gate classification that justified the lane (the scored dimensions,
  or a short reasoned proxy)
- the lane selected, and why the rung below was insufficient and the rung
  above unjustified
- the exact dispatch command (as in the examples above)
- the verification route: `V0_AUTO`, `V1_LLM_VERIFIED`,
  `V2_HUMAN_VERIFIED`, `V3_BLOCKED`, or the distinct **delegated
  acceptance (dual-agreement)** class from
  `automation/docs/verification-routing-policy.md` — never state a
  dual-agreement delegation as `V2_HUMAN_VERIFIED`; it always carries a
  machine-delegated provenance label instead
- the rollback path
- the handoff path (the task packet's `result_path`,
  `review_report_path`, and `operator_decision_path` fields)

## Authority-Bearing Actions (merge / accept / recover)

Any action listed in `dual-agreement-protocol.md` section 3 — PR merges
confined to automation/infrastructure/review surfaces, agent-task
lifecycle accept/close/supersede, estate-maintenance commits and
interrupted-run recovery, branch/worktree/draft-PR creation, routine
dependency/config upkeep — requires, before it proceeds:

1. **Propose.** Fable writes a decision packet: exact action, exact scope
   (task id, repository, branch, PR number), evidence, rollback.
2. **Independent review.** Sol reviews via `codex exec --model
   gpt-5.6-sol --sandbox read-only` and returns exactly one verdict:
   AGREE, AMEND, or REJECT. The reviewer must not mutate PR state — it
   returns a verdict; the orchestrator executes.
3. **Record and execute.** Only a recorded AGREE authorises the action,
   and only for that **one named instance** — no class-wide authority.
   The exercised agreement is recorded as one `operator-decision-record`
   under `automation/review/operator-decisions/records/`.
4. **Escalate otherwise.** REJECT or unresolved AMEND escalates to a
   human operator decision card; the action does not proceed.

`dual-agreement-protocol.md` section 4 is **never delegable** through
this loop: canonical-root writes, evidence/ontology/trust-tier/provenance
changes, Zotero/PDF/BibTeX mutation, external publication, upstream
repositories, force-push/history-rewrite/branch deletion, model
download/training approvals, raw research data ingestion, `s2-e1-ros2-
measurement-spine` changes, misumi persona truth, and autolab merges.
`/route` must refuse to propose dispatch for any of these and route
straight to a human operator decision card instead.

## Fail-Closed Rules

Refuse and emit an operator decision card — do not guess, do not proceed
— when any of the following holds:

- `task_type` is not a recognised key in `agent_routing.yaml` `routes:`
  (plus the lint's `ADDITIONAL_REGISTERED_TASK_TYPES` allowlist)
- `executor` is not one of the enumerated executors in `agent_routing.yaml`
  (or the 8-executor fallback the lint uses when that file is unreadable)
- `execution_mode` is unrecognised, or a bounded write-scope class
  (`central-orchestrator` / `implementation`) is claimed without its
  required companion fields (a declared `branch` and
  `verification_route: V2_HUMAN_VERIFIED` for the `implementation` class)
- the requested action sits in `dual-agreement-protocol.md` section 4
  (never delegable)
- the only input available is free text and the requested action would
  mutate anything beyond drafting a proposal or decision packet
- the named task packet fails `python -m Scripts.automation
  agent-task-lint`
- the gate classification cannot be stated with a stated reason (for
  example, climbing above `single` without an explicit
  independent-streams argument per gate section 4)

An operator decision card lands under
`automation/review/operator-decisions/**` following that surface's
existing conventions. `/route` never silently defaults to dispatch when
classification is uncertain.

## What /route Is Not

- Not a runtime router, scheduler, or service. No code in this repo
  selects an architecture, dispatches an agent, or enforces the gate.
- Not a registered, dispatchable skill. It carries no `task_type` and
  grants itself no dispatch surface — see the utility-skill comment block
  in `automation/config/odysseus_skill_registry.yaml`.
- Not an authority source. It never substitutes for a recorded
  dual-agreement AGREE, a human-issued `/approve` canonical-edit token, or
  the human gates enumerated in `automation/AGENTS.md`.
