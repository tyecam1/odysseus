Model used: Codex, GPT-6-based; exact runtime model identifier is not exposed to this session.

STATUS: packet 1 of N, unreviewed (Sol review owed)

# Sol packet efficiency: evidence audit and admission contract

Audit date: 2026-11-02. Task: `2026-10-01-sol-packet-efficiency`.
This is the review-first documentation packet only. N is not specified by the
task; it is not an invented implementation schedule. No Sol or astra invocation
was made or requested during this work. Historical model identifiers below are
observations, not proposed model defaults.

## Scope, authority and evidence boundary

The binding task is
`automation/review/agent-tasks/ready/2026-10-01-sol-packet-efficiency.agent-task.md`.
Its listed inputs were read: `AGENTS.md`, `config/models.yaml`,
`config/routing.yaml`, `docs/aoteru-model-host-routing-contract.md`, the inbox
cards `2026-09-13-daily-model-usage-reset-harvest` and
`2026-09-13-operating-contract-model-role-evaluation-system`, and the ready
card `2026-10-01-system-one-research-decision-layer` (all card names have the
`.agent-task.md` suffix). Subscription currency was reconciled against
`docs/subscription-model-currency-policy.md`.

Only this report is authorised for modification. The task's broader allowed
paths do not enlarge that permission; `companion/**` remains denied. There is
no compiler implementation, scheduler, queue, routing/configuration change,
promotion, deployment, PR, merge or push in this packet.

Repository baseline: `100378b619e183b0784e96387dd6c0935a1e1de0` on
`claude/sol-packet-efficiency-20261001`. The locally readable `dev` ref is
`75b24f72bce3257dd835a7ff74125ae9201423eb` (2026-10-27); `origin/dev` is
`5cbcaf8910fa62a048fbdf2077618265ed9d4dcc`. Neither was fetched or updated.
These refs are local evidence, not an attestation of current remote dev.
The local control-plane database was opened read-only and showed an existing
active repo-write lease matching this branch and worktree. No lease was acquired.
Private lease, session, host and account identifiers are deliberately omitted.

Delegation record:

- Collection and source inspection: deterministic shell/Python tools, with
  read-only SQL for local records. `aoteru preflight` was attempted for packet 1
  before reconnaissance and failed with exit 127, `aoteru: command not found`.
  Backend access was also unavailable: socket creation returned
  `PermissionError: Operation not permitted`. The live collaboration inventory
  contained only the current controller; no qualified external lane was attested.
  `nondelegation_reason: other: canonical preflight CLI is missing and backend
  sockets are denied; retain bounded local evidence collection using deterministic
  tools without launching an unverified or prohibited model lane`.
- Classification, admission semantics and synthesis:
  `nondelegation_reason: architecture_judgement`. These are methodological
  judgments grounded in the evidence below; they do not qualify a worker.
- Document/source/count checks: deterministic local tools. Final acceptance:
  `nondelegation_reason: final_acceptance`; independent Sol review remains owed.

The initialiser register `config/initialising-prompts.yaml` was checked. Neither
the J1 method-loop scope nor the Misumi convergence-programme task classes match
this bounded routing audit. No registered initialiser was applied. No separate
trace, evolution event or exemplar file is created under the one-file limit.

## Baseline audit

### Sampling method and denominators

This is a reproducible convenience sample of surviving local CLI transcripts,
cross-checked against repository artifacts and local dev history. It is not a
random sample or a census of subscription use.

1. Enumerate `/tmp/sol*.log` with modification timestamps in
   `[2026-10-22T00:00:00Z, 2026-10-27T00:00:00Z)`: **21 files**. This covers the
   latest five-day interval containing these surviving logs, near local dev's
   last recorded changes. Modification times are completion proxies, not
   authenticated call-start times.
2. Require a real Codex CLI header, explicit historical Sol model, and a user
   request scoped to Odysseus. Exclude `sol_status.log` (status bookkeeping, no
   invocation header) and `solri.log`, `sol_ret.log`, `sol_m3.log` (requests scoped
   to the separate Misumi repository). Do not count extra rounds merely mentioned
   inside a prompt. Do not count `.md`, `.out`, `.run` or `.status` copies again.
3. The resulting **17 invocation attempts** each have one CLI header. Read the
   header, request and final answer/error for purpose and outcome; retain no
   hidden reasoning or raw transcript content in this report. Log identities and
   checksums below allow a local reviewer to reproduce the selection.
4. Cross-check purposes and changes against `git log dev`, commit messages and
   the two repository evidence documents cited below. A merge commit, a task's
   `created_by`, or a promised future review is not itself another call.

Use one primary classification per invocation. Classify by the consequential
purpose, not incidental setup: a substantive review that reads files is not
automatically a context-reconstruction call. A review after material repairs is
not an unchanged repeat. An independent review classification preserves the
review obligation; it does not prove that every such item must have a separate
invocation. Combining still requires all six admission tests.

### Invocation-level ledger

Dates/times below are log modification times in UTC. Log pointers resolve under
`/tmp/`; historical verdicts and test claims are transcript observations, not
new validation of those changes by this audit.

| ID | Timestamp | Log / historical model | Primary classification | Evidence and repository cross-check |
| --- | --- | --- | --- | --- |
| A01 | 10-22 17:47:44 | `sol_pr150.log`; `gpt-6-sol` | necessary independent review | Cgroup-marker fix: changes requested for accepting a partial `0::` marker. Dev `32dfa6f` (#150) records the resulting test repair. |
| A02 | 10-22 17:49:58 | `sol_pr151.log`; `gpt-6-sol` | necessary independent review | Addressed household questions: changes requested for stripping content names. Dev `797d965` (#151); `automation/review/misumi-long-horizon-programme-evidence.md` records repair and acceptance. |
| A03 | 10-22 17:52:04 | `sol_pr152.log`; `gpt-6-sol` | necessary independent review | Truncated JSON: changes requested for nested metadata disclosure and weak boundary tests. Dev `2cf6d8d` (#152) records root-answer recovery. |
| A04 | 10-22 17:54:41 | `sol_pr153.log`; `gpt-6-sol` | necessary independent review | Route preview: changes requested, including an unbounded persona field. Dev `79ca6aa` (#153) and the programme evidence record scope/validation corrections. |
| A05 | 10-26 05:13:58 | `sol173.log`; `gpt-6.1-sol` | necessary independent review | Think-prefix salvage: changes requested because two new tests also pass on the old implementation. Dev `850e550` records discriminating replacements before #173 merged as `9e53627`. |
| A06 | 10-26 05:39:34 | `solscope.log`; `gpt-6.1-sol` | unavoidable single decision | One bounded decision: select the smallest persona-development increment under canon/authority constraints. The assignment increment appears in dev `271d9a1` and #174. Source reading supports that decision; the record does not show a separate reconstruction-only invocation. |
| A07 | 10-26 06:04:23 | `sol174.log`; `gpt-6.1-sol` | necessary independent review | Independent review of the completed assignment increment: approve, including recruitment comparisons and ordinary/structured consultation probes. Dev #174 (`76ab490`), with review repairs in `991cc88`. This follows A06's implementation, not unchanged evidence. |
| A08 | 10-26 06:12:49 | `sol_pr170.log`; `gpt-6.1-sol` | necessary independent review | Memory-source YAML relocation: approve after preservation and old-file failure checks. Dev #170 (`eb25608`). A small diff alone does not establish that review could safely be omitted. |
| A09 | 10-26 06:15:02 | `sol_pr172.log`; `gpt-6.1-sol` | necessary independent review | Supervision task status vocabulary: approve after schema/lifecycle consumer checks. Dev #172 (`b2d5258`). Its schema context differs from A08's memory registry; adjacent completion times do not prove substantial reusable context. |
| A10 | 10-26 12:17:28 | `sol_spot.log`; `gpt-6.1-sol` | necessary independent review | Binding fourth-pass request targets changed delayed-401 token handling at `998e9fc`; approve. Dev `e047590` (#176) preserves the earlier distinct repair rounds in its commit body. No inference that all four rounds survive as separate sampled logs. |
| A11 | 10-26 12:40:17 | `sol_s177.log`; `gpt-6.1-sol` | necessary independent review | Noninteractive setup: changes requested because the recovery command loses the selected callback port. Dev `e5ea451` (#177) records the fix. |
| A12 | 10-26 15:42:25 | `sol_music.log`; `gpt-6.1-sol` | failed or low-value | Music integration review attempt ends in a provider usage-limit error, with no reviewer verdict. Two printed error lines belong to this one header/attempt, not two calls. Intended change subsequently appears in dev `ed303f2` (#179). |
| A13 | 10-26 17:30:02 | `sol_orph.log`; `gpt-6.1-sol` | necessary independent review | Merged native-storage gate: changes requested for pathname/handle binding under ancestor substitution and a test descriptor leak. Requested two-dot diff was stale; reviewer identified the actual range. Dev `8e494ac` (#178), `08dd8bf` (#182), and storage acceptance documentation in `4a66527`. |
| A14 | 10-26 17:50:50 | `sol_dev.log`; `gpt-6.1-sol` | necessary independent review | Device-selection fourth-pass request includes new repairs; changes requested for `play it on the laptop` selecting an unintended title. Dev `92092f0` (#180). Not evidence of unchanged confirmation. |
| A15 | 10-26 18:07:39 | `sol_ta.log`; `gpt-6.1-sol` | necessary independent review | Title/artist matching: changes requested for substring/prefix collisions and duplicate-write reservation paths. Dev `f9b3ce9` (#184). |
| A16 | 10-26 18:25:58 | `sol_ff.log`; `gpt-6.1-sol` | necessary independent review | Field-filter second-pass request explicitly follows a near-miss fallback repair; approve. Dev `0f49602` (#185). This is changed code, not repeated unchanged verification. |
| A17 | 10-26 18:46:06 | `sol_rt.log`; `gpt-6.1-sol` | necessary independent review | Read-retry third-pass request explicitly follows dispatch-deadline repair; approve. Dev `72e9051` (#186). Distinct provider/deadline obligations remain. |

Full SHA-256 identities of the local evidence (no transcripts are copied):

```text
A01 2f45fecd0f03ee48f62fd47d21f2a9dc776fa3ec6b059421ccacad54cb26b6cd
A02 a3285b169227bff3e8ee17edd2d363a6cb5b6de0e04b958881cb36e627390d94
A03 67bd367d70a75b3955303818e7f451cd34a51da59339bafd166051e364b406d1
A04 043e3686c9c068536c9d5d1df40c7bb529cdc0c521140b3be73d6cb11411af50
A05 b0fe22cd79e6e9a8afc293800235b293646f1e23e71f789ce07dc300c1f06b95
A06 be49d7cd8b06157d822f93cf39455dee70a41e696ed7eafd9d016d5dc9f7f8c0
A07 6b629c8b16ceaa0b93d95390cfa8e94ce2c6eec5dffa754cf8783020f1f40840
A08 35359912a0b7e65ad822b4ff75c3fe53a873263298004325aebab4936ba11cf6
A09 de6fb1b0a34b2177bd0c5ce929f1f59e11c1dbc30a9d028832ac5fe5feb3ca54
A10 388bea7a87a8c6fd0c1c603213289853b1265d055e8031c846cb4b8712ca8ada
A11 5ab9f64ab0fb2d064e81256fc0dbca155151ba58818edcb4411bf985c596d47e
A12 19778cd89668b8e4705c1e37a132275a18680f51d65545abc5b4118875c222ff
A13 dfe1269da1d38572692cce0be7da0e2b564da6ec7535033737d759b50eb6bf26
A14 db5c81837d796e28ce1da50ca2bc1447274a710c219df634fb7cfe017b99d684
A15 3eb371fdd6ec7f0762bd902feb91e8c9e3348fa4b0f10840950b8fff4b13fcef
A16 d37bf43f96bc4b7943fa9e4dc311379b0b60c368913f04c62f8c380716cd2350
A17 ed687d922b4837295b3d52ba48f58aeec7bb6e838dd3975f4f6056cc1aa1b07e
```

### Counts, fragmentation and reduction ceiling

| Primary category | Count / 17 |
| --- | ---: |
| unavoidable single decision | 1 |
| could have been combined | 0 demonstrated |
| repeated unchanged verification | 0 demonstrated |
| context reconstruction | 0 as primary purpose |
| wording-polish | 0 demonstrated |
| necessary independent review | 15 |
| failed or low-value | 1 |
| Total | 17 |

The 15 completed reviews contain **9 changes-requested verdicts and 6 approvals**;
A06 supplies one scoping result and A12 no verdict. These are outputs, not 16
accepted consequential decisions: per-item acceptance, human corrections and
missed defects are not consistently recorded. Four headers identify `gpt-6-sol`
and thirteen `gpt-6.1-sol`.

Sixteen logs have a CLI `tokens used` footer, summing to **1,286,122**. This is
only the sum of that historical scalar: the logs do not establish comparable
input/output/cache accounting or subscription-quota cost. It cannot serve as
the denominator for accepted decisions per input token, context tokens avoided,
or money saved. A12 has no such footer. Timings above do not measure latency.

**A realistic numeric upper bound on quality-preserving call reduction is not
estimable from this sample.** There are zero proven mergeable groups under all
six admission rules, but that is not a 0% upper bound. A02/A04 share route/auth
context, and A15-A17 share the music stack; they are candidates for a later
compatibility reconstruction. Their concurrent readiness, urgency, exact common
snapshots, independence obligations and output budgets are missing. A06 must
precede the implementation reviewed by A07. Successive fixes cannot simply be
replayed as if all were ready at once.

The one directly observed failed-call opportunity is A12: **1/17 = 5.9%** of
sampled attempts produced no verdict because of quota. Avoiding that one
attempt would be a conditional failure-avoidance saving if authoritative quota
state were available before dispatch. It is neither a batching upper bound nor
a demonstrated saving: the record does not establish advance detectability.
There is no evidential basis here for an estate-wide percentage or a claim
that larger packets retain quality. Preserve all substantive review coverage.

Repository corroboration outside the sample:

- `automation/review/misumi-operational-closeout-2026-10-06.md`, section 7,
  records two Sol reviews of a multi-area overlay and a third attempt with no
  verdict after quota exhaustion. It also records consequential new findings
  after repairs and an omitted overlay producing misleading findings. This is
  evidence that bundling already happens and that evidence preparation matters;
  these older calls are outside the 17-call denominator.
- `docs/estate-deterministic-execution-proposal-20261026.md` (dev `96f37aa`)
  records model-backed transport work failing on quota, and Sol's correction
  that deterministic route completion is not command execution. The narrative
  does not enumerate authenticated Sol invocations, so it adds no call count.
- `automation/review/misumi-long-horizon-programme-evidence.md` records the
  #150-#153 repairs and sandbox verification limits. Do not count its summaries
  again as new calls.

### Telemetry reconciliation and inaccessible evidence

Read-only SQL over the local control-plane SQLite `routing_decisions` table,
filtering `created_at >= '2026-10-01'` and a case-insensitive `sol` match in
`concrete_model`, found **19 Sol-labelled rows** dated 2026-10-24 through
2026-10-26. All have `status=complete`, but none has an `execution_id` or
`result_json` payload; `context_tokens` and `paid_tokens` are null. They cannot
be joined to an execution objective/verdict or reliably deduplicated against
the transcripts. They are **19 unclassifiable route records, not 19 additional
calls**. No purpose is invented from `task_class=unclassified` or
`implementation`. The live schema contains extra lifecycle columns beyond the
checked-out `RoutingDecision` declaration, another reason not to assume parity.

Not accessible/established here: remote dev/GitHub review threads; live estate
API, worker health/inventory and provider quota/reset state; provider billing
or complete authenticated session exports; other machines' execution stores;
overwritten/deleted prior rounds; exact input/output/cache token splits and
shared-context token overlap; per-item accepted outcomes and later human
corrections; paired packetised replay, independent defect labels and safe size
limits. The selected `/tmp` logs are ephemeral local evidence, not committed
artifacts. A reviewer without that store can check repository corroboration but
cannot reproduce the full invocation audit from Git alone. Survivorship,
security-review concentration and model-version drift limit generalisation.

## Small packet vocabulary

| Class | Admission purpose | Boundary |
| --- | --- | --- |
| decision | Several bounded choices over the same evidence/context base. | Preserve each question/options/criterion; do not combine sequential decisions whose inputs depend on another answer. |
| verification | Several completed cheaper-worker outputs needing the same strong-review role. | Candidates stay separately attributable; preserve required fresh contexts and implementer/verifier independence. |
| collision/adversarial | Related novelty, closest-prior or counterexample checks for one scientific question. | Do not reveal held-out labels or let one challenge prescribe another's answer. |
| gate | Compact evidence for one consequential gate or authorial decision. | One gate is the unit. Packet preparation grants no authority to make a human-reserved decision. |

## Deterministic compiler checklist (specification only)

The task's six conjunctive admission rules are binding. The following makes
their decision procedure explicit; it is not runnable code or new routing
authority. Methodological judgments must arrive as source-backed preparation
metadata, not be guessed by a compiler from prose. Unknown is not safe.

### Prepare and validate each item

- Require the task's fields: `decision_id`, `parent_task`, `role_required`,
  `question`, `decision_type`, `consequence`, `evidence_pointers`,
  `shared_context_key`, `candidate_options`, `acceptance_criteria`,
  `independence_required`, `deadline`. IDs must be unique and stable; question,
  evidence and acceptance criteria must be nonempty. Options may be empty only
  for a schema that explicitly permits an open judgment. Deadline is an explicit
  timestamp or an explicit no-deadline value, never a missing implicit default.
- Resolve repository/domain authority, read/write scope, privacy/locality,
  parent-task permission, required review role/provider separation and exact
  evidence revisions first. Validate with existing routing/lease authorities.
  Hash source manifests; a shared key without identical versioned sources is
  insufficient. Remove already rule/test-settled questions from model work.
- Require a preparation manifest recording unresolved questions, completed
  candidate outputs, deterministic checks and their limits. Invalid/incomplete
  items return `NEEDS_PREPARATION`; they are not sent blindly as singletons.
- Preparation supplies: normalised role and review protocol; packet class;
  scientific-question/gate identity where relevant; urgency/blocking status;
  fresh-context and separate-adjudication requirements; dependency and
  label-exposure relationships; pairwise non-contamination certificates with
  evidence; bounded input/output estimates; and time-benefit/urgency-cost bounds.
  These are proposed compiler inputs, not claims that today's envelope has them.

### Admit a multi-item candidate only if every check passes

1. **Same role:** all items have the same normalised adjudication/review role,
   protocol and compatible packet class. Normalisation uses a governed explicit
   equivalence map; unknown roles are not approximately matched by a model name.
   Gate items share one gate; collision items share one scientific question.
2. **Substantial reusable context:** all share an exact versioned context
   manifest under compatible access constraints. Compute the duplicate context
   tokens removed minus packet-wrapper overhead using one declared estimator.
   Require positive net reuse and passage of the governed material-reuse
   threshold, with its evidence/version recorded. A key or topic match alone
   fails. If that threshold has no evidence-backed value, do not invent one:
   return `SINGLE(context_reuse_unestablished)`.
3. **Independence preserved:** `independence_required=true`, mandatory fresh
   context, high-consequence separate adjudication, dependency on another item's
   unresolved answer, or expected-label exposure vetoes co-location. Every pair
   must have a valid non-contamination certificate. No same-call synthesis may
   certify its own required independent review. Missing certificates or unclear
   independence return `SINGLE(independence_unestablished)`; known vetoes return
   `SINGLE(independence_required)`. All-pairs checks prevent transitive chaining
   of A-compatible-with-B and B-compatible-with-C into an unsafe A/B/C packet.
4. **Comfortable capacity:** obtain known current context/output limits from
   the eligible route and measured safe packet policy. Account for global
   constraints, shared context once, every item's unique evidence/question,
   schema overhead, per-item rationale/uncertainty reserves, synthesis and
   headroom. Require total input plus reserved output/headroom within the
   context bound, output reserve within output bound, and item count within
   the measured safe region. Unknown limits/policy or any truncation/shallow
   treatment risk returns `SINGLE(capacity_unestablished_or_exceeded)`. Do not
   drop evidence or required outputs to force a fit. A singleton that cannot
   safely fit needs preparation/escalation, not automatic dispatch.
5. **Attribution complete:** each item retains its explicit ID, question,
   evidence pointers and acceptance criterion plus allowed verdicts, uncertainty
   to surface, escalation trigger and matters not to reopen. Require a parsable
   result for every ID; one missing/malformed result leaves that item unresolved
   without converting other items to failures or claiming packet-wide success.
6. **Waiting justified:** any urgent/blocking item bypasses accumulation and
   is sent singly when otherwise eligible. For remaining items require
   `benefit_lower_bound(wait) > urgency_cost_upper_bound(wait)` in explicitly
   comparable policy units, backed by recorded evidence. The proposed wait
   must satisfy every deadline and a bounded evidence-backed accumulation
   window. Unknown bounds, no configured window, or insufficient readiness
   return `SINGLE(wait_not_justified)`; do not guess permanent constants.

All existing authority, provider availability, qualification, budget and domain
gates remain prerequisites to dispatch. Failure of those prerequisites is
`BLOCKED`, not permission to choose another model or acquire a lease. The
subscription path still resolves model currency at dispatch; packet size is
not a user-facing research tuner and model version/tier is not a task knob.

### Compile, dispatch and suppress unnecessary follow-up

- Process existing pending items in a stable order (deadline, then stable ID;
  explicit no-deadline sorts last). Test the entire candidate and every pair
  before each addition. An oversized set is partitioned only into groups that
  each pass all tests. Record the policy/evidence version and a batch/single
  reason for every item. This specifies deterministic grouping, not an optimal
  packing claim or permission to create a new pending-work store.
- Emit shared evidence and global constraints once, then each item's question,
  unique pointers and output schema. Deduplicate only identical content/revision
  with the same access semantics; preserve per-item citations. Include legitimate
  cross-item synthesis, unresolved IDs and recommended escalations at the end.
- Require each result to carry `decision_id`, verdict, concise rationale,
  evidence references, uncertainty and whether another strong call could
  plausibly change the decision. Verification uses `PASS / REVISE / ESCALATE`;
  decision/gate verdict sets come from their declared options/authority. Record
  later acceptance, defects and corrections separately from model self-report.
- Compare question/evidence/candidate/criterion manifest hashes with the prior
  result. An unchanged conclusion defaults to reuse. Another call requires a
  recorded material packet defect, new evidence, consequential verifier finding
  or ambiguity exceeding a declared threshold. Wording polish and confirmation
  alone do not trigger Sol. Never suppress a still-required independent check.
- Use the existing dispatcher when blocking work is ready, compatible reuse is
  sufficient, safe capacity is reached, the bounded window expires, or reliable
  near-reset capacity exists for useful authorised work. Near reset never
  manufactures work, splits a coherent packet, bypasses admission or consumes
  completion margin. No new scheduler/queue is authorised by this checklist.

## Existing attachment points found in source

Paths/functions below were inspected at the task baseline. These are later
packet attachment candidates, not implemented hooks or evidence of live parity.

| Existing file and symbols | Present responsibility / later attachment |
| --- | --- |
| `src/delegation_preflight.py`: `recommended_lane_for_task`, `delegation_preflight`, `_valid_nondelegation_reason` | Classify units, consult live routing and validate retention reasons. Carry packet-preparation/retention evidence through this boundary rather than bypassing it. |
| `routes/estate_routing_routes.py`: `TaskEnvelope`, `RunTaskEnvelope.to_task`, `DelegationPreflightUnit`, `setup_estate_routing_routes` (nested `preflight_task`, `run_task_route`) | Existing `/api/estate/preflight` and `/api/estate/run` envelopes/auth. Future packet fields require explicit schema propagation; unknown fields must not silently disappear. |
| `src/estate_router.py`: `eligible_hosts`, `resolve_alias`, `resolve_route`, `run_task`, `_dispatch_read_only` | Authority/host/capability resolution and actual worker dispatch. Candidate admission belongs before non-urgent strong dispatch, after hard eligibility. `resolve_route` alone does not execute a call; deterministic `run_task` can return `executed: false`. |
| `src/estate_router.py`: `_record_decision`, `_update_decision_outcome` | Existing per-task route and execution-outcome writes. Later record packet ID, per-item identity, batched/single reason, reuse estimates and actual outcomes here without duplicating route rows as call counts. |
| `src/estate_router.py`: `_execute_codex_with_sandbox`, `execute_codex`, `_codex_write_authority`, `execute_codex_write_durable`, `_resolve_paid_provider` | Bounded advisory/write execution, model identity, provider mapping and existing lease checks. Packet work cannot bypass sandbox/lease/currency rules. Success currently returns output, latency, model/effort/catalogue provenance; it does not parse CLI token accounting. |
| `src/estate_write_lane.py`: `execute_write_via_worker`, `_record_outcome`, `get_estate_execution`, `execution_provenance` | Durable write admission, observation and provenance. `_record_outcome` currently treats nonempty successful output as its minimal deterministic gate, not accepted consequential decisions or independent quality proof. Preserve lifecycle/lease binding. |
| `src/park_lease_ops.py`: `active_lease_for_repo`, `lease_authority_state` | Canonical write authority, including stale-but-execution-protected leases. Reuse, never manufacture authority from packet admission. |
| `src/estate_worker.py`: `_verb_health`, `_verb_execute`, `_verb_status`, `_run_spooled` | Worker availability, bounded execution and durable observation. Health's Codex check is binary/auth availability, not authoritative remaining quota. Status observation is not another model call. |
| `core/database.py`: `RoutingDecision`, `EstateExecution`, `BenchmarkResult` | Existing route outcome, durable execution and benchmark records. Packet/item outcomes, corrections and shared-context reuse need explicit later representation; their existence is not implied by these classes. Local DB/schema drift was observed above. |
| `src/routing_evaluator.py`: `aggregate_routing_decisions`, `load_and_aggregate`, `compute_delegation_metrics`, `get_decision_by_id` | Existing read-only aggregation/lookup. Extend its evidence handling for packet denominators and missing usage; this module does not execute paired historical replay. |
| `src/model_context.py`: `estimate_tokens`, `get_context_length_known`, `select_bounded_context` | Existing context knowledge and approximate sizing. `estimate_tokens` is a character-based heuristic; `select_bounded_context` sizes local allocation, not a proven Sol packet-quality limit. Reuse estimates with provenance; validate strong-model output reserves separately. |
| `src/llm_core.py`: `stream_llm`, `_stream_llm_inner`; `src/agent_loop.py`: `_compute_final_metrics` | Streaming provider usage and response metrics; metrics distinguish real from estimated usage. This path's input/output usage is not automatically available for subprocess CLI runs. Do not claim complete telemetry merely because both paths have token-related fields. |
| `config/models.yaml`, `config/routing.yaml`; the two inbox owner cards listed under scope | Existing capability/provider policy and budget/verification defaults; global model-role evidence and usage-harvest ownership. No policy edits here. The harvest card remains an integration dependency, not a second scheduler to build in packet 1. |

Later telemetry must distinguish invocation attempt, packet, item, review round
and accepted outcome. Attach packet ID, class, item IDs/count, role/contract and
evidence hashes, reuse estimate/source, input/output usage or explicit unknown,
per-item verdict/acceptance/defects/corrections, latency, follow-up trigger and
single/batched reason to existing owners. Avoid secrets, raw sensitive context
and hidden reasoning. Missing usage is null, not zero; a gate pass based on
nonempty output is not an accuracy label.

## Acceptance accounting

These rows follow the task's acceptance checklist in order. “Specified” means
documented here; it does not mean implemented, exercised, independently reviewed
or promoted.

| Task acceptance criterion | Packet 1 disposition |
| --- | --- |
| Recent Sol usage has a quantified fragmentation baseline | Partial: 17-call classified sample, source identities, counts and limits exist. Representative estate-wide fragmentation and a safe reduction ceiling remain unestablished. |
| One small packet vocabulary is defined | Satisfied as an unreviewed specification: four classes above. |
| A deterministic compatibility/admission rule exists | Satisfied as an unreviewed specification/checklist; compiler implementation and numeric policy calibration remain owed. |
| Repeated shared context is represented once where safe | Specified; no compiled packets produced. |
| Cheaper workers prepare decision-ready evidence before Sol | Specified; this audit used deterministic collection. Runtime preparation integration remains owed. |
| Every packet returns attributable per-item decisions | Schema obligation specified; no new packet/model execution. |
| Mandatory fresh-context/independent checks cannot accidentally be batched | Explicit fail-closed veto specified; executable enforcement/negative tests remain owed. |
| Routing records batched/single reasons | Attachment points/reason semantics identified; no runtime recording added. |
| Historical replay shows materially fewer calls/tokens per accepted decision | Not satisfied: no paired replay or accepted-decision denominator. |
| Consequential quality and defect detection do not regress | Not satisfied: no controlled comparison or independent labels. |
| Packet-size stress test identifies a safe region | Not satisfied; no thresholds invented. |
| Unchanged conclusions do not trigger repeated Sol verification by default | Reuse/follow-up rule specified; dispatch enforcement remains owed. |
| Usage-reset harvest can exploit coherent packets | Interface boundary specified; no harvest integration or quota attestation. |
| Model-role-contract telemetry records packet ID/count/reuse/outcomes/corrections | Required fields and owners identified; no schema/storage changes. |
| Affected tests and task lint pass | Docs-only scope: deterministic report/source/count checks apply. Runtime tests and canonical agent-task lint are not claimed; task metadata is unchanged. |
| Independent verification precedes promotion | Still owed. This file is unreviewed and unpromoted; no Sol review was requested under the operator's prohibition. |

Packet 1 provides an auditable limited baseline and a reviewable contract. It
does not ship the parent backlog item. Continue only after the owed review and
appropriate later-packet authority; preserve the task's stop rule when measured
batching ceases to improve useful accepted work or degrades quality, latency or
independence.

## Deterministic verification of this document

Local checks recomputed the 17 ledger classifications, 9/6 review verdict split,
4/13 historical model split, all 17 transcript hashes, and the 16-footer sum.
Read-only SQL confirmed the separate 19-row telemetry exclusion. All explicit
repository file references exist; AST inspection confirmed all 45 named source
symbols in the attachment table, including nested route handlers. Status/model
disclosures, trailing whitespace, and patterns for private host paths, addresses,
UUIDs and credentials were checked. Only the permitted report is changed.
These are deterministic consistency checks, not independent review of the
methodological classifications or safety specification. No runtime test-suite
pass or canonical task-lint pass is claimed. Verification preflight was attempted
again and returned the same missing-CLI error; the recorded local-tool retention
reason applies. Commit is restricted to the existing leased task branch.

Commit blocker: staging this exact file with `git add --` failed with exit 128:
Git could not create `index.lock` because the linked Git metadata is on a
read-only filesystem in this sandbox. The document remains untracked and
uncommitted on the task worktree. No branch update, alternate Git metadata,
merge, push or PR was attempted. A lease-authorised executor with writable Git
metadata must stage and commit this file on the same task branch; Sol review
remains owed independently of that filesystem blocker.
