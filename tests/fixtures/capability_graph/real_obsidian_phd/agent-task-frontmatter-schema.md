# Agent-Task Front Matter Schema

Canonical YAML front matter for every file under `automation/review/agent-tasks/**`.
One task = one Markdown file. Status must agree with the lifecycle folder.
New task files MUST use `artifact_type: agent-task`. `artifact_type: workflow`
remains valid for existing task files only (grandfathered; no historical
churn). Settled by operator instruction in consolidation cycle 4 (2026-07-16);
lint enforcement is routed to the validation ladder PR.

`task_schema: agent-task/v1` is the default/write schema. `task_schema:
agent-task/v2` is additive (PR-2, 2026-07-27): v1 stays fully valid; v2 adds
optional architecture-selection fields, validated only when present. See
"Schema v2 additions" below.

## Schema

```yaml
---
# identity
artifact_type: agent-task           # agent-task (new files) | workflow (existing files, grandfathered)
task_schema: agent-task/v1           # agent-task/v1 | agent-task/v2 (additive; see Schema v2 additions)
task_id: 2026-06-10-example-slug     # <YYYY-MM-DD>-<kebab-slug>, unique, stable
title: ""                            # short imperative title
status: inbox                        # inbox|ready|running|review|done|rejected|blocked
priority: medium                     # high|medium|low
task_type: routine-report            # see task-type vocabulary below
created_by: ""                       # human|chatgpt|claude|codex|odysseus|<routine-name> (lowercase; suffix variants grandfathered)
created_at: 2026-06-10T00:00:00+00:00

# execution
executor: remote_shell               # derived from automation/config/agent_routing.yaml executors at lint time (currently remote_shell|remote_model|odysseus|claude_subscription|codex_subscription|gpt_subscription|zotero_mcp|human)
execution_mode: batch                # batch|scheduled|interactive|handoff|central-orchestrator|implementation|design-then-implementation|isolated-evaluation|review-first
requires_remote_compute: false
requires_local_model: false          # true = remote box local-model inference (never laptop)
requires_zotero: false               # read-only unless approval_required is true
requires_mcp: false
requires_web: false

# verification and risk
verification_route: V2_HUMAN_VERIFIED  # V0_AUTO|V1_LLM_VERIFIED|V2_HUMAN_VERIFIED|V3_BLOCKED
risk_level: low                      # low|medium|high
approval_required: true              # human approval gate independent of verification
source_traceability_required: true

# scope (fail closed)
repo: tyecam1/obsidian-PhD
branch: ""                           # working branch, if any
allowed_paths: []                    # exact write-scope allowlist
denied_paths:                        # always includes canonical roots
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**

# data flow
inputs: []                           # exact source paths
outputs: []                          # expected durable output paths (review-side)
result_path: ""                      # primary durable output once produced
review_report_path: ""               # verification report, if separate
handoff_model: ""                    # claude_work_package|codex_work_package|gpt_work_package|remote_model_job
handoff_prompt_path: ""              # pinned prompt for subscription/model handoffs

# linkage
operator_decision_path: ""           # decision card/record, if any
linked_pr: ""                        # PR URL or number, if any
supersedes: []                       # task_ids replaced by this task
duplicates: []                       # task_ids identified as duplicates

notes: ""                            # one bounded paragraph; no scope expansion
---
```

## Field rules

- `task_id` never changes after creation; renames are a new task with `supersedes`.
- `status` is the only lifecycle field; folder move and status edit happen together.
- `executor` decides who performs; `verification_route` decides who may accept.
  They are set independently by `automation/config/agent_routing.yaml`.
- `allowed_paths` empty => read-only task. Ordinary task `allowed_paths` remain
  review-side only under `automation/review/**`.
- A central orchestration task may use `task_type: orchestration` or
  `execution_mode: central-orchestrator` and declare a bounded extended write
  scope for repo mechanics (`automation/docs/**`, `.github/**`, `Scripts/**`,
  `08-template/**`, `10-inbox/**`, `00-dashboards/**`, `README.md`,
  `AGENTS.md`) when the task itself names those paths. This is not a general
  queue widening rule and does not override canonical research denials.
- A bounded implementation task may use `execution_mode: implementation` with
  a declared `branch` and `verification_route: V2_HUMAN_VERIFIED` to declare
  writes under `Scripts/automation/**`, `automation/docs/**`,
  `automation/config/**`, `automation/prompts/**`, `.agents/skills/**`, and
  `automation/logs/observability/**` (PR-2, 2026-07-27). Review-only
  (`automation/review/**`) remains the default for every other task; denied-path
  defaults stay required verbatim for the implementation class (no
  `00-dashboards/**` omission).
- `denied_paths` may grow, never shrink, relative to the defaults above. Central
  orchestration tasks may omit `00-dashboards/**` from the default denied set
  only when dashboards are explicitly listed in their bounded write scope.
- `executor` is validated against `automation/config/agent_routing.yaml`
  `executors:` keys at lint time; the routing contract and the lint cannot
  diverge. `task_type` is validated against `agent_routing.yaml` `routes:`
  keys plus the explicit lint allowlist in
  `Scripts/automation/agent_task_lint.py` (`ADDITIONAL_REGISTERED_TASK_TYPES`)
  described in "Task-type vocabulary" below. `execution_mode` is validated
  against the enum in the Schema block above. Unknown executors, task types,
  or execution modes are lint errors.
- Topology note: the session-level Claude hook
  (`.claude/hooks/block_canonical_edits.py`) gates `00-dashboards/**`
  unconditionally regardless of task frontmatter; a central-orchestration
  omission of that deny is therefore effective only for non-Claude executors,
  and Claude sessions still require the scoped approval-token flow. Recorded
  2026-07-16 (consolidation PR 2); any reconciliation is routed to a later PR,
  not this one.
- `requires_local_model: true` is valid only with `requires_remote_compute: true`
  (`automation/config/model_execution_policy.yaml` forbids laptop execution).
- `approval_required: true` is mandatory when any of: canonical-adjacent
  decision input, Zotero/PDF mutation downstream, external publish, PR merge.
- Claim/completion provenance (claimed_by, claimed_at, completed_by,
  completed_at, verification_verdict, verification_by) is appended by executors
  and verifiers at transition time; absent fields mean the transition has not
  happened.

## Task-type vocabulary

A `task_type` is registered if it is either a routing-table entry or an
explicitly listed additional type. Both sets are enforced by
`Scripts/automation/agent_task_lint.py`; unknown `task_type` values are lint
errors.

Routing-table entries (`automation/config/agent_routing.yaml` `routes:`):
`validation`, `diagnostics`, `retrieval-index`, `repo-hygiene`,
`routine-report`, `zotero-report`, `evidence-extraction`, `annotation-routing`,
`evidence-readiness`, `decision-packet`, `synthesis`, `critique`,
`implementation`, `refactor`, `debugging`, `pr-review`, `migration`,
`human-approval`.

Additional registered types (orchestration, architecture-evaluation and
related programme/audit work not yet formalised as routing-table entries;
`ADDITIONAL_REGISTERED_TASK_TYPES` in `Scripts/automation/agent_task_lint.py`):
`aggregation`, `architecture-evaluation`, `architecture-observability`,
`audit`, `automation-qa`, `automation-ux`, `data-organisation`,
`evaluation-observability`, `evidence-ingest-and-system-audit`,
`evidence-review`, `evidence-synthesis`, `extraction-backend-pilot`,
`harness-protocol`, `instruction-authoring`, `literature-integrity-audit`,
`memory-architecture`, `orchestration`, `platform-adjudication`,
`platform-evaluation`, `prompt-workflow-update`, `recurring_update`,
`repo-governance-audit`, `repo-hygiene-verification`, `repo-residue-review`,
`requirements`, `research-support-packet`, `retrieval-evaluation`,
`review-lane-reconciliation`, `review-surface-refresh`, `review-triage`,
`skill-engineering`, `system-modelling-diagram-synthesis`, `writing-plan`,
`writing-skill`, `zotero-beaver-evidence-ingestion`,
`zotero-beaver-hardware-synthesis`, `zotero-evidence-ingestion`.

Extend either list by PR only.

## Schema v2 additions (additive)

`task_schema: agent-task/v2` accepts every v1 field plus the following
optional architecture-selection fields. Validated only when present; omitting
them all keeps a v2 task identical in behaviour to v1.

```yaml
architecture: single                 # single|single-plus-verifier|coordinated-2|parallel-n
architecture_rationale: ""           # free text: why this topology for this task
single_agent_baseline: ""            # free text: what the single-agent baseline result/expectation is
execution_host: laptop               # laptop|compute-box|cloud
context_budget: ""                   # free text or token/byte budget note
coordination_reason: ""              # required when architecture != single
flat_verification_status: ""         # misumi-related tasks only (repo must reference tyecam1/misumi)
```

- `architecture` and `execution_host`, when present, must be one of the listed
  enum values; unknown values are lint errors.
- `coordination_reason` is required whenever `architecture` is present and is
  not `single`; a coordinated/parallel task without a stated reason is a lint
  error.
- `flat_verification_status` is valid only on tasks whose `repo` field
  references `misumi` (e.g. `tyecam1/misumi`); present on a non-misumi task it
  is a lint error.
- `architecture_rationale`, `single_agent_baseline`, and `context_budget` are
  free text with no enum; they are not currently lint-validated beyond normal
  YAML parsing.
