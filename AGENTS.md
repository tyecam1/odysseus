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
