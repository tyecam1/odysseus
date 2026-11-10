# Ultrareview contract - Odysseus routing spine and central integration (2026-11-10)

This file is the reviewer's brief. It is part of a synthetic review branch and is never merged.

## How this diff was built
- `ultra/20261110-integ` = `dev` plus normal merges of open PRs #261 (read-only GLM provider), #241 (central prompt library, contains #218 ChatGPT ingest) and #244 (call telemetry collector).
- The PR base rewinds a selected set of source paths to their 2026-10-20 state, so the diff shows three weeks of merged and unmerged work on those paths only. Everything else in the repository is at its integrated state and is available as context.
- Tests are deliberately outside the diff to fit the size limit. They exist under `tests/` (for example `tests/test_glm_readonly_provider.py`, `tests/test_chatgpt_ingest.py`, `tests/test_prompt_library.py`, and the estate router and Sol packet suites). Read and run them; report behaviour they do not cover.

## What this system is
Odysseus is a personal multi-host agent estate. `src/estate_router.py` decides which model and host take a task (local models on the lab and home PCs, paid providers such as Codex/Sol and GLM under quota), `src/delegation_preflight.py` and the write lane gate execution, and `companion/laptop_client/aoteru.py` is the laptop control client. Misumi is the household interface; `routes/misumi_routes.py` is the seam it plugs into.

## Review priorities, in order
1. **Routing correctness and fail-closed behaviour.** Provider selection, quota-health admission, fallback order, paid-provider gating, read-only versus write lanes, structural classification of provider failures. A task must never reach a paid, unqualified or write-capable lane that the policy excludes, and an unavailable provider must degrade rather than crash or loop. The GLM provider from #261 is meant to be inert until qualified: confirm no path activates it.
2. **Local compute.** Selection of local models and hosts, health and lease handling, timeouts, behaviour when a host is down or a model is missing. Flag any case where local capacity is skipped in favour of a paid provider without cause.
3. **Duplicated capability.** Find logic implemented more than once across `estate_router`, `sol_packet_compiler`, `subscription_model_policy`, `efficiency_pareto`, `agentic_portfolio`, `agentic_context`, `chatgpt_ingest` and the Misumi routes: provider and model catalogues, quota or usage parsing, prompt assembly, retry and timeout wrappers, state-file I/O, JSON-from-model parsing. Name the single owner each should have.
4. **Prompt library integrity.** `src/prompt_library.py` and `prompts/library/**`: version resolution through `CURRENT`, `register_child` and `promote` semantics, path traversal through prompt ids, behaviour on a missing or malformed version, and whether each migrated caller (`deep_research`, `teacher_escalation`, `context_compactor`, `goal_based_extractor`, `instagram_semantic`, `model_interaction_tools`) renders the same prompt it used inline before. Outcome records must hold counts only, never source text.
5. **Ingest pipeline.** `src/chatgpt_ingest.py`: resumability after interruption, idempotence on re-run, malformed export handling, private content leaking into logs, ledgers or committed paths, unbounded model-call fan-out.
6. **Misumi seam.** `routes/misumi_routes.py`, `misumi_safety_gate`, `misumi_advisory`: authentication and origin checks on every route, input validation, the safety gate failing closed, and whether the route surface is a stable contract an interface can plug into or an accretion of one-off endpoints.
7. **Token and call efficiency.** Redundant model calls, context that grows without bound, missing caching of derived state, packets larger than the admission check allows.

## Out of scope
Documentation wording, style, the finance PR #207, Instagram acquisition, and files outside the diff except as context.

## Reporting
For each finding give file and line, a concrete failing input or state, and the smallest fix. Mark consolidation findings separately from bugs. Prefer a few verified high-impact findings over many speculative ones.
