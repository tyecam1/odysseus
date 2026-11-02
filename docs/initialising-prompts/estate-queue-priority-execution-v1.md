---
title: Estate queue priority and execution initialiser v1
status: active
created: 2026-11-02
scope: cross-repository-agent-task-dispatch
owner: tyecam1/odysseus
---

Prompt identity: estate-queue-priority-execution@v1

# Mission

Resume the existing Odysseus agentic work system. Recover the live authoritative task frontier, calculate a transparent, evidence-grounded priority, select the best eligible work, execute a bounded shippable increment through existing preflight, lease, routing and verification mechanisms, reconcile its task state, and repeat while authorised executable work remains.

This is an INITIALISER, not a new task registry, scheduler, dispatcher, portfolio database, priority engine or authority. Do not turn it into another planning project. Work is drawn from existing queues, not invented by this prompt.

# 1. Authority and recovery

- Confirm the repository, actual branch/HEAD, dirty state, active worktrees, leases, deployments and current execution outcomes using live interfaces. Read AGENTS.md, the shipping-first policy, docs/aoteru-model-host-routing-contract.md, queue READMEs and the relevant programme contract before selection. Do not treat an old checkpoint, memory, or task filename as live truth.
- Odysseus owns shared backend, execution, leases, model routing, infrastructure and its queue under automation/review/agent-tasks/{ready,inbox,blocked,done,rejected}. Misumi owns its personal/interface/persona queue; obsidian-PhD owns PhD research and evidence queue. The central PRIORITISATION VIEW may read all authorised queues but cannot transfer task ownership, edit another domain's scientific content without its authority, or create a competing master queue.
- Reconcile stale cards against merged PRs, verified deploys, acceptance evidence, active executions and duplicate/superseding items. A PR, passed CI or local implementation alone is not necessarily shipped.
- Respect the standing 2026-10-17 shipping-first instruction in AGENTS.md until its specified completion condition is evidenced or the operator explicitly changes it. Deliver accepted backlog and essential dependencies before optional visual polish, prompt tuning, speculative research or machinery redesign.
- Explicit correction: no blanket waiver of owner-only security-sensitive merge gates has been given by an assistant. If memory or a previous agent report claims otherwise, flag the claim as non-authoritative and correct the affected operational checkpoint through its governed process. Read dispatch-controller.md if available in the active estate; its tracked absence is not permission to override it. Owner-only merges, protected-branch merges, production deploys, permissions, spending, host trust and credentials require their respective CURRENT, explicit approval. Do not edit those policies or infer consent from an agent's own assertion.

# 2. Derive the eligible frontier before scoring

Read queue-card frontmatter (status, priority, risk_level, approval_required, verification_route, repo, inputs, outputs, dependencies, execution_host, context_budget, executor, branch and allowed/denied paths) and current programme dispositions.

Classify each open item as:
- EXECUTABLE: accepted work with met dependencies, appropriate authority, available worktree/lease path, qualified execution route and a verifiable bounded slice.
- ACTIONABLE PRECONDITION: a safe, authorised independent step such as a deterministic test, evidence reconciliation, review preparation or an approved lease request that would unlock completion.
- BLOCKED: exact human/physical/credential/model/provider/dependency gate and a trigger. Do not repeatedly retry or poll.
- ALREADY DELIVERED, DUPLICATE, SUPERSEDED or REJECTED: reconcile only with evidence and the required owner authority.

Not every inbox item is accepted. Do not autonomously promote untriaged proposals into the executable queue. Treat approval_required and verification_route as hard constraints, not scores. In particular, do not start a code-writing worker without its required active ParkLease; do not treat preflight as lease acquisition. Preserve one writer and the EstateExecution lifecycle; never submit a second implementation dispatch as a status poll.

If availability cannot be verified, qualify only the read-only action that establishes it. A missing input must never be silently scored as zero or fabricated.

# 3. Calculate priority from current evidence

First apply a LEXICOGRAPHIC delivery tier that numerical scoring cannot override:
A. Acceptance-critical safety/correctness repairs and continuation of already-started, accepted shipping work whose risk or delivery gate demands immediate attention.
B. Other accepted, already-started work with a credible end-to-end delivery path.
C. Accepted, ready, dependency-unblocked work with a credible end-to-end delivery path.
D. Inbox work only after governed triage and acceptance, when it unblocks A-C or the accepted backlog is genuinely exhausted.
Blocked, rejected, duplicate or unauthorised work is not executable regardless of score.

Within each eligible tier, rate the following 0-4, with one brief cited reason per rating:
V = user-visible value or required operating benefit;
F = verified delivery readiness (not a guessed probability);
B = dependent work genuinely unblocked;
U = demonstrated deadline urgency (zero when there is no known deadline);
S = verified safety/correctness or operational-risk reduction;
E = remaining effort to acceptance (cost penalty);
C = coordination / task-switching overhead (penalty);
X = uncertainty in evidence, feasibility or acceptance (penalty).

Initial transparent ranking heuristic:

    score = 6V + 5F + 4B + 3U + 3S - 3E - 2C - 2X

The weights are a STARTING HEURISTIC, not a measured predictive model. Keep their values fixed within the application; do not tune them to force a preferred outcome. Rate only from concrete task cards, verified current milestones, actual deadlines and measured progress. Where a material dimension is unknown, record UNKNOWN and an honest plausible range; perform the smallest useful verification, or rank conservatively without pretending precision. A narrow score difference or overlapping ranges is a tie, broken by time to verified delivery, then reduced dependency risk, then lower cost. A documented critical deadline or safety emergency is handled through the governing escalation policy, not a fabricated rating.

Display at most the five highest candidates with task ID, owner, tier, score/range, evidence, blocked gates, estimated next shippable result and qualified route. Select the highest eligible item. Avoid an exhaustive narrative audit on every wakeup; refresh only changed state after the first run.

# 4. Execute the selected slice

- Identify the smallest end-to-end increment with a concrete result and acceptance evidence. State the task ID, owning repo, active authority, dependency checks, objective, falsification/acceptance test, current deployed state, intended files, risk, reviewer and stop gate.
- Run the existing aoteru preflight for the task and repo; inspect live qualified workers, provider quota, host/locality, budget and applicable review lane. Prefer deterministic execution and the cheapest ADEQUATE qualified route. Use current authenticated subscription-model policy; do not hard-code an older Sol/Claude/GLM version or silently downgrade a reserved verifier.
- Use existing ParkLease, controlled worktree and EstateExecution mechanisms for mutation. No implicit lease acquisition, second queue, shared-writer collision, bypass flags, arbitrary SSH permission widening or parallel changes to the same authority. One implementation owner; independent bounded read-only verification where consequential.
- Implement, test, review, commit, PR, integrate and release only through current gates. Security and owner-only changes remain pending approval if not explicitly authorised. Do not call a task shipped until acceptance and the required deployed/real-path evidence are actually satisfied.
- On quota/host/provider outages, record the specific lane with observed reset/trigger once, stop retrying it and execute another eligible independent slice. A failed model attempt is not an excuse to park deterministic work. On uncertain remote execution, query its ID read-only; never dispatch again to poll.

# 5. Reconcile and repeat

After each bounded delivery, update only the owning task card and authoritative programme/evidence records: result, tests, review, commit/PR, deployment evidence, remaining acceptance, actual dependencies and blocker. Do not close a card by changing status without meeting its real completion definition.

Recalculate affected priority candidates when an item finishes, a dependency releases, an important deadline changes, new evidence appears, or resource eligibility materially changes. Preserve working focus rather than switching on trivial numerical differences. Continue with the next eligible task during the same active execution session. Do not spend the whole session ranking the queue.

When there is no eligible executable or actionable-precondition work within the current authority, report the exact blocked frontier and minimal human actions once. Do not fabricate future/background execution. A genuine runtime/context/tool limit may end a session after a durable checkpoint.

# 6. Compact output and continuity

At initial selection, give only: top candidate and reason; next two alternatives; exact permission/dependency gates; selected model/host/effort and actual execution route. Do not repeat the whole backlog.

After meaningful progress, give: task ID; verified outcome; what is merged/deployed versus merely drafted; next selected item; any decision requiring explicit owner action.

If this registered prompt was used, preserve its prompt_id/version and one application ID across the session. On close, append one application trace and one evolution event through the existing global initialising-prompt register. Preserve exact evidence, agent rating and actual operator feedback only; never fabricate operator approval or ratings. Evolve into a NEW immutable version only when observed performance supports a semantic change; do not mutate this version in place.

Begin by reading the live estate and queue authority, deriving the eligible frontier and immediately executing the highest-ranked authorised shippable increment.
