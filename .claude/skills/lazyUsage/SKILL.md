---
name: lazyUsage
description: Select and ship governed work from the Odysseus, Misumi and PhD queues according to verified Claude, Codex and GLM capacity.
disable-model-invocation: true
---

Read and execute `START-AGENTIC.md` from the canonical Odysseus checkout, resolving the active `estate-queue-priority-execution` version.

Check current authenticated Claude, Codex and GLM usage before queue selection. Prefer PhD when both Claude and Codex have adequate capacity; otherwise prefer eligible Odysseus backend and Misumi GUI tasks that qualified available lanes can deliver. Treat unknown usage as unknown.

Run normal preflight, independent verification and authorised completion without requesting operator verification for ordinary work. Preserve protected gates and require operator review for external human-facing deliverables or style that cannot be inferred from accepted examples.

Do not require a laptop-local checkout. Use the existing registered lab SSH/remote-execution route before treating repository access as unavailable. Do not bypass repo ownership, leases, evidence or approval policies. Continue to the next eligible task after completion.
