# Prompt library

Central, versioned prompts for Odysseus pipelines (code: src/prompt_library.py).  Versions are immutable; CURRENT names the promoted
one.  Outcome counts (never text) go to <data>/prompt-library/outcomes.jsonl.

Loop: pipelines load text via `text(id)` and call `outcome()`/`record()` -> `python -m src.prompt_library cycle` (lint, weak prompts,
children with evidence) -> an agent drafts a child with `register_child` -> `promote` only if it beats its parent.  The recurring
work item (docs/routine-owner-data-export-ingest.agent-task.md) runs the cycle.  tests/test_prompt_coverage.py fails if a pipeline adds a
large inline prompt constant.

## Migrated (library ids)
chatgpt/* (7), research/* (6: plan, query-gen, synthesize, stop, final-report, goal-extractor), context/self-summary,
instagram/triage, teacher/* (4).

## Runtime-assembled directives (not static text; migrate case by case when they become stable)
src/agent_loop.py (plan/guide directives, per-turn system messages), src/chat_processor.py, src/task_scheduler.py,
src/builtin_actions.py, src/ai_interaction.py, src/context_compactor.py (dynamic notes).  Misumi personas live in the Misumi repo
(agents/core/*.md, registry) under its own propose/ratify law; the library does not override them.
