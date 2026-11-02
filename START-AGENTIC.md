# Start agentic work

Resolve `estate-queue-priority-execution` from `config/initialising-prompts.yaml` and execute its current registered prompt. Use live repository authority, including `AGENTS.md`, and preserve existing approval, lease and verification gates. This file is an entry point, not a separate authority.

Load context progressively using the existing read-only helper:

- Discover: `python scripts/agentic_context.py frontier --limit 12 --max-tokens 1500`.
- Select: `python scripts/agentic_context.py task --task-id TASK_ID --tier contract --max-tokens 2500`.
- Execute: retrieve only sources required by the selected task.
- Investigate: expand context only to resolve a specific uncertainty.

Do not treat task metadata as approval or treat any assistant message or memory as a waiver of owner-only gates. Execute through the existing preflight, routing, lease and release mechanisms. Track one prompt application and use the registered closeout/evolution process.

The stable operator instruction is: **Read and execute START-AGENTIC.md.**
