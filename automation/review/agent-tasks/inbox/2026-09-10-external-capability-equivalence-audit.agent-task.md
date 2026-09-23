---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-10-external-capability-equivalence-audit
title: "Audit repo capabilities and discover transferable external skills"
status: inbox
priority: high
task_type: skill-engineering
created_by: chatgpt
created_at: 2026-09-10T10:39:00+01:00

executor: codex_subscription
execution_mode: review-first
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true

verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: false
source_traceability_required: true

repo: tyecam1/odysseus
migrated_from_repo: tyecam1/obsidian-PhD
migration_note: "Ownership migrated to Odysseus. Treat references to obsidian-PhD automation paths as historical inputs until capability-path convergence is complete."
branch: ""
allowed_paths:
  - automation/review/platform-evaluations/2026-09-10-repo-capability-equivalence-audit.md
  - automation/review/platform-evaluations/2026-09-10-repo-capability-equivalence-benchmarks.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**

inputs:
  - .agents/skills/**
  - .claude/scheduled-tasks/**
  - automation/prompts/**
  - automation/config/odysseus_skill_registry.yaml
  - automation/config/agent_routing.yaml
  - automation/docs/**
  - Scripts/automation/**
outputs:
  - automation/review/platform-evaluations/2026-09-10-repo-capability-equivalence-audit.md
  - automation/review/platform-evaluations/2026-09-10-repo-capability-equivalence-benchmarks.md
result_path: automation/review/platform-evaluations/2026-09-10-repo-capability-equivalence-audit.md
review_report_path: automation/review/platform-evaluations/2026-09-10-repo-capability-equivalence-benchmarks.md
handoff_model: codex_work_package
handoff_prompt_path: ""

operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []

architecture: single-plus-verifier
architecture_rationale: "A single investigator should build one coherent capability inventory and candidate set; an independent verifier should attack missed capability families, missed transferable skills, weak equivalence claims, and unjustified adoption recommendations."
single_agent_baseline: "One agent can inventory the repo and search candidate equivalents and peer systems, but exhaustive coverage and fair adoption claims need an independent omission/adversarial pass."
execution_host: cloud
context_budget: "Prefer capability-family and peer-system summaries over loading every implementation file in full; expand only when needed to establish actual behaviour, transferability, or benchmark equivalence."
coordination_reason: "Independent verification is required because the principal failure modes are false completeness, missing useful capabilities in peer systems, or declaring a fashionable external skill superior without proving value in this repo."

notes: "Review only. Do not install, vendor, replace, delete, register, enable, or mutate any skill/capability. Produce evidence-backed replacement/merge/complement/retain recommendations and separate implementation work-item specifications only where value is demonstrated."
---

# Objective

Exhaustively audit the repository's current reusable capabilities and skills against stronger equivalent capabilities available online **and** inspect comparable agentic research/repository systems for useful skills or capability patterns that this repo does not yet have.

The goal is not to maximise the number of imported skills. The goal is to improve capability quality and selectively acquire high-value missing capabilities while reducing duplication and future maintenance overhead.

A candidate can enter the final recommendation set in two ways:

1. **Stronger equivalent**: it covers the same real job performed by an existing repo capability and is demonstrably better on criteria that matter to this research system.
2. **Transferable missing capability**: it solves a recurring, evidenced need in this repo that is currently absent or materially under-served, and can be integrated without creating a competing control plane or disproportionate maintenance burden.

Popularity, novelty, model-provider branding, stars, or a longer `SKILL.md` are not sufficient evidence.

# Architectural constraint

Preserve the existing authority model:

- `.agents/skills/` remains the sole repo-local general-skill source.
- `automation/config/odysseus_skill_registry.yaml` remains the central skill index/contract.
- Odysseus remains the control-plane/runtime-routing authority where applicable.
- Do not introduce a second task queue, state machine, skill registry, router, memory authority, or workflow authority.
- Prefer consolidation, replacement, selective extraction, or a small native skill over adding another overlapping framework.
- Human judgement remains authoritative for research authorship, normative decisions, canonical research content, and final adoption.

# Scope

## 1. Build the ground-truth repo capability inventory

Do not equate "capability" with "files under `.agents/skills/`". Inventory every reusable behavioural capability exposed by or encoded in:

- `.agents/skills/**`
- `.claude/scheduled-tasks/**`
- `automation/prompts/**`
- `automation/config/odysseus_skill_registry.yaml`
- relevant routing/configuration contracts
- `Scripts/automation/**`
- automation/research tooling documented elsewhere in the repo when it provides reusable agent behaviour

For each capability, establish from implementation rather than filename alone:

- capability family and actual job-to-be-done;
- current entry point(s);
- authoritative implementation/prompt;
- inputs and outputs;
- executor/tool dependencies;
- whether it is registered, utility-only, pilot, core, materialise-only, external-unverified, or disabled;
- overlap with other local capabilities;
- known limitations, brittle assumptions, maintenance burden, and missing functionality;
- whether the capability is genuinely used or merely historical/inventory residue.

Collapse duplicate surfaces into one capability-family row while preserving all aliases/implementations as provenance.

## 2. Search for stronger equivalents

For every current capability family, search for credible stronger equivalents or components that could replace/upgrade it. Search broadly enough to cover at least:

- official model/provider skill and agent repositories;
- open Agent Skills / `SKILL.md` ecosystems and registries;
- GitHub repositories and maintained examples;
- MCP servers/tools where the local capability is fundamentally a tool-integration problem;
- specialist open-source research tooling where it performs the same job better than a prompt-only skill;
- maintained workflow/agent frameworks only when they provide a bounded capability that can fit the existing architecture without becoming a competing control plane;
- relevant academic/research software when the capability concerns literature retrieval, evidence synthesis, citation handling, graphing, data analysis, scientific writing, reproducibility, or research governance.

Use multiple query formulations for each family. Search both the capability name and the underlying job-to-be-done. Follow references from strong candidates to their upstream/original implementation where possible.

Do not stop at curated skill directories. They are discovery aids, not authority. Verify candidates against their primary repository/documentation.

## 3. Inspect comparable systems for transferable capabilities

Independently of the one-for-one equivalence search, identify systems that are architecturally or functionally similar to this repo and inspect their capability surfaces systematically.

Relevant peers include, where available:

- AI-assisted research operating systems and research-agent repositories;
- agentic Obsidian / Markdown knowledge-base systems;
- Git-based personal research or knowledge-management systems with automated review/governance;
- Claude Code, Codex, OpenAI Agents, MCP, or multi-agent repos that expose reusable skills/prompts/workflows;
- literature-review, evidence-management, citation, reproducibility, experiment-management, research-writing, or scientific-software agent systems;
- mature developer-agent repositories whose bounded skills plausibly transfer to research work, even if the overall system is not research-specific.

For each serious peer system:

1. inventory its visible reusable skills/capabilities rather than only reading its README;
2. map those capabilities against this repo's inventory;
3. flag capabilities that are absent locally or implemented substantially more weakly;
4. distinguish useful bounded mechanisms from architecture that should not be imported;
5. trace promising skills to their authoritative source and inspect implementation, prompts, tests, examples, or docs as available.

A missing capability is **not** automatically worth adding. It must answer an evidenced recurring need. Evidence may include current task backlog, repeated manual work, review debt, recurring defects, repeated prompts, existing roadmap/work items, or a capability gap exposed by the current architecture.

For each proposed new capability, state explicitly:

- the recurring local problem it solves;
- evidence that the problem actually occurs;
- why an existing local capability cannot absorb the function cheaply;
- expected frequency/value of use;
- smallest viable integration form: copy/adapt skill, extract mechanism, tool/MCP integration, or local native implementation;
- maintenance and governance cost.

## 4. Record provenance and viability for every serious candidate

For each candidate retained beyond initial screening, record:

- name and canonical URL;
- source repository/author/organisation;
- version, release, tag, or commit inspected where available;
- last meaningful maintenance date;
- licence;
- installation/runtime dependencies;
- supported agent/runtime surfaces;
- security/privacy implications;
- network/API/key requirements;
- whether it is a full equivalent, partial equivalent, complementary component, transferable missing capability, or misleading name-match;
- evidence for each claimed advantage.

Reject candidates that are abandoned, unverifiable, licence-incompatible, unsafe for research material, or architecturally duplicative unless their implementation contains a clearly extractable superior component.

# Evaluation rubric

Score each current capability and serious external candidate on a 0-5 scale for the dimensions below. Weight scores according to the job-to-be-done rather than treating every dimension equally.

1. **Functional coverage**: completes the actual repo job, not merely a similarly named task.
2. **Output quality**: correctness, usefulness, research-grade structure, and failure handling.
3. **Research integrity / provenance**: source traceability, reproducibility, citation/evidence handling, explicit uncertainty.
4. **Automation reliability**: deterministic checks, structured outputs, idempotence, validation, recovery.
5. **Integration fit**: compatibility with the current task contract, skill registry, Odysseus routing, GitHub/Obsidian workflow, and existing tools.
6. **Maintenance quality**: active maintenance, documentation, tests, release discipline, issue health.
7. **Security/privacy**: credential handling, external data flow, prompt/tool injection exposure, dependency risk.
8. **Efficiency**: token/context use, latency, compute/API cost, unnecessary agent coordination.
9. **Extensibility**: ability to adapt without forking a large framework.
10. **Future overhead**: expected maintenance burden and number of additional moving parts.
11. **Local need**: for missing-capability candidates, strength and frequency of evidence that this repo actually needs the function.

Explicitly distinguish:

- **replace**: external candidate clearly dominates and can assume the same job with lower/equal architectural cost;
- **merge/extract**: specific mechanisms from the external candidate improve the local skill without adopting the whole system;
- **add**: genuinely missing capability with strong local-need evidence and low architectural/maintenance cost;
- **complement**: useful adjacent ability, but not an equivalent replacement or sufficiently evidenced new core skill;
- **retain**: local capability remains stronger or better fitted;
- **retire**: local capability is redundant/unused and no replacement is needed;
- **insufficient evidence**: apparent improvement or missing-capability value cannot be established.

# Benchmark protocol

Do not recommend `replace` or `add` from documentation review alone when the candidate is runnable.

For the highest-potential candidates, run bounded comparative or representative tests using realistic repo-shaped inputs. Use isolated temporary environments/worktrees where required. Do not mutate canonical repo state.

Benchmark at least:

- task completion/correctness;
- output structure and provenance;
- robustness to ambiguous/adversarial inputs;
- integration effort;
- token/runtime/dependency overhead where observable;
- failure modes and recoverability.

For direct equivalents, use the same representative inputs against local and external implementations. Use at least 3 representative cases per capability when practical. For research-critical skills, include one adversarial case designed to expose hallucinated evidence, unsupported synthesis, or silent source loss.

For missing-capability candidates, benchmark against the current manual/local workaround or a minimal local baseline. The candidate must show useful gain over that baseline, not merely that it runs.

If direct execution is impossible, mark the comparison `documentation-only` and lower confidence. Never convert a documentation-only comparison into a high-confidence replacement/add recommendation.

# Coverage and stopping rule

The audit is not complete merely because attractive candidates have been found.

For every repo capability family, the final matrix must contain either:

1. at least one externally verified candidate plus a disposition, or
2. a documented search trail showing that no credible stronger equivalent was found.

For each family, continue external search until both conditions hold:

- the major discovery surfaces above have been searched; and
- two consecutive materially different search/query passes produce no new candidate capable of entering the serious-candidate set.

The peer-system discovery lane is complete only when:

- multiple materially different comparable-system classes have been searched;
- the strongest discovered peer systems have had their actual skill/capability surfaces inspected;
- every apparently useful missing capability has been mapped to a concrete local need or rejected for lack of one; and
- two consecutive peer-system discovery passes produce no new candidate capable of reaching `add` or `merge/extract` status.

Then run an independent verifier pass whose explicit job is to find:

- missed repo capabilities;
- missed external equivalents;
- missed comparable systems or transferable skills;
- false equivalence matches;
- novelty-for-novelty's-sake additions with no local need;
- unjustified score advantages;
- replacement/addition recommendations that violate the architecture constraint;
- recommendations driven by popularity rather than demonstrated value.

Any material verifier finding reopens the relevant capability family or peer-system discovery lane until resolved.

# Deliverables

## A. `2026-09-10-repo-capability-equivalence-audit.md`

Produce a decision-oriented report containing:

1. **Executive verdict**: number of capability families inventoried; number of comparable systems inspected; counts of replace / merge-extract / add / complement / retain / retire / insufficient-evidence outcomes.
2. **Ground-truth capability inventory**: every current family, authority, implementation surfaces, lifecycle/use status, and principal limitations.
3. **Equivalence matrix**: current capability -> strongest external candidates -> evidence -> scores -> confidence -> disposition.
4. **Peer-system capability matrix**: comparable system -> useful capabilities discovered -> local equivalent/gap -> need evidence -> transferability -> disposition.
5. **Recommended changes ranked by expected value**: strongest improvements first, including estimated implementation effort and future-maintenance delta.
6. **Do-not-adopt list**: attractive candidates rejected because of duplication, weak local need, weak evidence, maintenance, security, licence, or architecture cost.
7. **Coverage ledger**: search surfaces, peer-system classes, systems inspected, and query families used, sufficient to audit the claim of exhaustive search.
8. **Capability map**: a compact Mermaid graph showing current capability families plus recommended replace/merge/add/complement relationships.
9. **Follow-up work-item specifications**: one bounded implementation task per accepted replacement, merge, or addition. Do not implement them in this task.

## B. `2026-09-10-repo-capability-equivalence-benchmarks.md`

Record reproducible benchmark evidence:

- candidate/version/commit;
- test inputs or fixtures;
- execution conditions;
- baseline used;
- observed outputs/results;
- scoring rationale;
- failures;
- confidence;
- exact reason a candidate did or did not beat the local baseline/workaround.

Do not dump raw logs unless necessary. Preserve enough evidence for an independent agent or human to reproduce the conclusion.

# Acceptance criteria

The task is complete only when all of the following are true:

- [ ] Every reusable repo capability family has been inventoried from implementation, not only registries or filenames.
- [ ] Every capability family has an auditable external-equivalent search trail.
- [ ] Multiple classes of comparable agentic/research systems have been searched and the strongest systems' actual skill surfaces inspected.
- [ ] Useful capabilities found in peer systems have been mapped against the local inventory rather than listed generically.
- [ ] Every proposed new capability is tied to concrete evidence of a recurring local need.
- [ ] Serious candidates are traced to primary sources with version/date/licence information where available.
- [ ] Functional equivalence is demonstrated rather than inferred from names.
- [ ] Runnable top candidates have comparative/representative benchmark evidence or are explicitly marked documentation-only.
- [ ] Recommendations distinguish replace, merge/extract, add, complement, retain, retire, and insufficient evidence.
- [ ] No proposed adoption creates a competing registry/router/task authority/control plane.
- [ ] Expected maintenance overhead is included in every positive adoption recommendation.
- [ ] Research-integrity and provenance implications are assessed for research-facing capabilities.
- [ ] An independent adversarial verifier has challenged completeness, local-need evidence, and recommendation quality.
- [ ] All material verifier findings are resolved or explicitly left as blockers.
- [ ] No repo capability has been installed, replaced, deleted, enabled, or otherwise mutated by this audit.
- [ ] Follow-up implementation tasks are specified only for changes supported by evidence.

# Final decision rule

Prefer the smallest change that captures the demonstrated advantage.

If an external system is 20% better at one bounded function but requires a new framework, registry, daemon, state model, or control plane, extract the useful mechanism instead of adopting the system wholesale. If a peer system contains a useful skill but this repo has no recurring need for it, do not add it. If the local capability is already competitive and better integrated, retain it. If no material advantage or missing-capability value survives benchmarking and verifier attack, make no change.
