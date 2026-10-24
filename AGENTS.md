# Delegation invariant

For every substantive task unit: decompose it, resolve authority and repo,
inspect live eligible workers/executors, dispatch to the cheapest adequate
lane, verify, and escalate only on recorded evidence.

Before starting bounded implementation, refactoring, debugging, test
authoring, review, repository reconnaissance, batch, scan, test, index,
evaluation, or simulation work, run:

```text
aoteru preflight "<task>" [--repo <repo-id>]
```

The equivalent backend call is `POST /api/estate/preflight`. Follow its live
recommendation. Codex implementation requires an existing active repo write
lease; preflight and execution must never acquire one implicitly. Dispatch it
with the equivalent `POST /api/estate/run` envelope or:

```text
aoteru ask "<task>" --repo <id> --capability code-strong --allow-paid --implementation
```

Retain work in the controller only for intent, architecture or methodological
judgement, ambiguity resolution, cross-worker synthesis, arbitration, or final
acceptance. Record a concrete `nondelegation_reason` whenever retaining an
otherwise eligible unit.

`docs/aoteru-model-host-routing-contract.md` is the routing and authority
contract. Do not duplicate or override it here.

Subscription model version/tier is never a task-controlled variable. Apply
`docs/subscription-model-currency-policy.md`: only effort is selected, use
the newest authenticated model and fail closed rather than fall back. Local
models retain their separate qualification policy.

**Usage-limit failover:** For a verified Codex quota/usage-limit response, do not
park otherwise eligible work until reset. Apply the existing routing contract's
"Codex usage-limit → GLM failover" section: prefer an actually qualified GLM
implementation/review lane with the same task scope and lease; if unavailable,
continue independent deterministic/other qualified work and preserve the exact
review debt. Never treat an unmerged GLM candidate, launcher smoke test,
alias name, or credential discovery as worker qualification.


## Temporary operating priority: ship the existing backlog (2026-10-17)

**Operator instruction; effective until the accepted backlog is shipped, or the operator explicitly changes this priority.** Shipping takes precedence over optional refinement, optimisation, refactoring, speculative research, workflow redesign, prompt tuning, new feature ideation and new planning artifacts. This changes *work selection*, not safety, authority or acceptance thresholds.

- **Scope and baseline:** apply to Odysseus-owned work in `automation/review/agent-tasks/{ready,inbox,blocked}` and executable workstreams in its canonical programme queues. At the 2026-10-17 baseline (`dev` at `e8ba6a2e08084f857b2739c99d8fa35318cea6b0`) there were 8 `ready`, 15 `inbox`, and 8 `blocked` agent-task cards. Reconcile with live state; some inbox cards may be duplicate, superseded or already delivered. Domain-specific queues remain owned by their domain repositories.
- **Select work to deliver:** finish already-started and `ready` items that have a viable end-to-end delivery path before starting an unrelated improvement. Triage `inbox` only enough to identify accepted, high-value shippable work, duplicates and genuine dependencies. Choose the next slice by *time to verified delivery*, user value and dependency unblocking, rather than elegance of the architecture. Prefer a small complete vertical result over an extensively polished partial one.
- **Meaning of shipped:** acceptance conditions satisfied; minimum relevant tests and safety/security checks pass; changes merged and deployed/real-path exercised when the task requires it; queue/programme status and evidence updated. A draft, plan, PR, untested implementation, or a status-only move to `done` is **not shipped**. Do not weaken existing tests, review/ratification conditions, write leases, release controls, research validity or evidence floors to gain throughput.
- **Blockers and new work:** record an exact external blocker once and immediately advance another eligible item. Keep blocked accepted work in the unfinished backlog. Capture newly proposed nonessential work in `inbox` but defer execution; admit new work ahead of existing items only to fix a safety/correctness failure, fulfil an acceptance gate, or unblock delivery. Do not repeatedly optimise the delivery machinery itself unless measurement shows it blocks shipping.
- **Progress and exit:** each dispatch/review should identify the concrete item and expected shipping evidence; report counts of shipped, accepted remaining, untriaged, and blocked without gaming classifications. Maintain shipping-first until **all accepted baseline work and essential delivery dependencies** are genuinely shipped or individually closed as duplicate/obsolete/rejected with recorded justification and required authority. An external blocker, a green test suite, or an empty `ready` directory alone does not terminate this policy. Revert to normal refinement priority only after a documented final backlog reconciliation or explicit operator instruction.

## Global initialising prompt register

Odysseus owns the cross-repository initialising-prompt register:

- registry: `config/initialising-prompts.yaml`
- contract: `docs/initialising-prompt-register.md`
- immutable prompt bodies: `docs/initialising-prompts/**`
- append-only application traces: `evals/prompt-applications/**`
- opportunistic prompt exemplars: `evals/prompt-exemplars/**`

At the start of a substantive session, check whether the target repository/task matches an active registered initialiser. If the operator supplied a registered initialiser, resolve it by `prompt_id` + `version`; do not silently substitute another version.

At substantive session closeout, record one application trace when a registered initialiser was actually used. The trace records repository/branch, start/end commits, outcome, stop reason, models/routes used, verification evidence, and a rubric-based agent rating. Operator rating is separate and optional; never invent it.

**Prompt evolution is a graph loop, not in-place mutation.** Every completed application must create an evolution event under `evals/prompt-evolution/**`. Failure tags, weak rating dimensions and explicit operator feedback become evidence for a child prompt version. Clean runs create a reinforcement edge instead of cosmetic wording churn. Existing prompt versions and application traces remain immutable.

A child may become the active head only when its delta is traceable to observed performance and it preserves repository scope, authority, evidence/verification requirements, model-identity discipline and stop/safety gates. Prompt evolution must never improve its score by weakening the task.

### Opportunistic prompt-exemplar capture

Across **any task or domain**, notice when a prompt that is created, encountered,
or materially revised is unusually strong, novel, elegant, or reusable. Do not
wait for a pre-existing prompt category.

Capture the exact prompt in `evals/prompt-exemplars/**` when either:

- the operator explicitly identifies it as worth preserving; or
- the active agent has high confidence that it contains at least two unusually
  valuable prompt behaviours, such as task framing, decomposition, autonomy,
  verification, constraint/authority handling, model/tool coordination,
  context compression, stopping logic, or another novel reusable mechanism.

Capture is intentionally cheap and **does not grant authority**. A newly noticed
prompt is a `candidate` exemplar until execution evidence or explicit operator
review supports a stronger status. Preserve the exact prompt before distilling
components from it. Record why it was captured, the task/context, reusable
behaviours, and any later application/evaluation pointers.

Domain, repository, task class, or absence from the initialising-prompt register
must never by itself disqualify a prompt from exemplar capture. Conversely, do
not collect routine prompts merely to grow the gallery.

Exemplar capture should not interrupt the primary task. Capture at the next
natural write/closeout point, or preserve a bounded capture payload for later if
the owning repository is unavailable.

Repository-local agents must not create competing prompt registries. They may carry a lightweight pointer to this global register.
