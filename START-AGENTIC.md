# Start the Odysseus agentic work programme

Permanent operator command, from an authorised checkout of tyecam1/odysseus:

    Read and execute START-AGENTIC.md.

## Startup, with progressive context disclosure

0. **Mandatory small trust baseline, never deferred:** read the relevant authority and current operator approval rules from AGENTS.md, the global prompt register and the current routing/lease contract. No context budget may omit safety, scope, verification or approval requirements.
1. Resolve prompt_id estate-queue-priority-execution from config/initialising-prompts.yaml. Load only its current active immutable prompt body and docs/initialising-prompt-register.md. Preserve prompt version and application ID.
2. **L0, metadata only:** inspect the live queue frontier using:
       python scripts/agentic_context.py frontier --limit 12 --max-tokens 1500
   This parses only task frontmatter. It does not inject 40 task bodies, programme histories, memory or source files into context. For other authorised domain queues, use explicit --repo-root and --queue-rel, never an inferred shared memory namespace.
3. Check task IDs and live eligibility/authority; inspect at most 3-5 promising task contracts using:
       python scripts/agentic_context.py task --task-id TASK_ID --tier contract --max-tokens 2500
   Rank the candidates through the immutable initialiser's hard eligibility and delivery-priority rules. Only now read the relevant programme state sections, dependencies and relevant history.
4. **L2, bounded source activation:** after selecting a task, retrieve only files and line spans named by its concrete acceptance path; take definitions/signatures and targeted search results first, then adjacent implementation/tests only as needed. Repo histories, long reports, model cards, vendor docs, deep memory, log dumps and supplementary skills are deferred until an evidence gap explicitly needs them.
5. **L3, explicit escalation:** use the script's --tier full or broader source retrieval only on a named unresolved question. Give a brief reason and return to bounded context. Never pretend a truncation is complete reading. Never let retrieval scope bypass domain/source permissions.
6. Execute through existing aoteru preflight, ParkLease, EstateExecution, scoped review and release rules; reconcile the owning queue item; continue the next eligible item.

## Context efficiency invariant

- Each invocation has one active task ID, one smallest affected scope and one explicit verification target. Default to metadata and pointers, then reveal content just-in-time.
- Maintain a compact running state: task ID, authority/lease, source pointers, proven facts, current hypothesis, tests/results, blockers and next executable action. Keep transcripts and scratch exploration out of subsequent worker packets.
- Give workers a bounded evidence packet (task contract + relevant file/line references + acceptance tests), not the entire repo history or accumulated chat. Independent reviewers receive only the evidence needed for their review plus governing constraints.
- On phase changes, retire irrelevant context from the active packet but preserve immutable references/checkpoints. If selection changes, go back to L0/L1 rather than carrying the old task's source dumps forward.
- Record rough context size, files/sections actually opened, rejected irrelevant retrievals and any unnecessary re-reading as operational efficiency evidence. Do not invent exact tokenizer counts or claim measured token savings without paired runs.
- Read full material immediately when it is required for security, authority, a critical scientific claim, or correctness; efficiency never weakens necessary verification.
- The stage-specific implementation contract is docs/runtime-work-packages/context-budget-and-dynamic-activation.md. This launcher is a lightweight front end to that existing objective, not a new memory or skill activation authority.

## Explicit governance correction

No assistant message or memory note has waived owner-only merge, deployment, credential, security-sensitive or other protected approval gates. A claim of blanket waiver is inaccurate unless an explicit, scope-matched operator approval exists in the governing source. Do not modify dispatch-controller.md or related permissions based on such a claim.

This launcher creates no background daemon or automation. A session may run successive authorised items until it reaches real execution/runtime limits; stopping requires a durable checkpoint, not a promise of future unattended work.

If executed without the required repo or host tools, report the missing capability and the bounded read-only next action. Never pretend to have dispatched a worker.
