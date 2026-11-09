---
name: lazyUsage
description: Select and ship governed work from the Odysseus, Misumi and PhD queues according to verified Claude, Codex and GLM capacity.
disable-model-invocation: true
---

Read and execute `START-AGENTIC.md` from the canonical Odysseus checkout, resolving the active `estate-queue-priority-execution` version.

Check current authenticated Claude, Codex and GLM usage before queue selection. Prefer PhD when both Claude and Codex have adequate capacity; otherwise prefer eligible Odysseus backend and Misumi GUI tasks that qualified available lanes can deliver. Treat unknown usage as unknown.

Run normal preflight, independent verification and authorised completion without requesting operator verification for ordinary work. Preserve protected gates and require operator review for external human-facing deliverables or style that cannot be inferred from accepted examples.

Do not require a laptop-local checkout. Use the existing registered lab SSH/remote-execution route before treating repository access as unavailable. Do not bypass repo ownership, leases, evidence or approval policies. Continue to the next eligible task after completion.

## Bounded persistence

A single invocation keeps working through recoverable blockers; it does not end after inventory or after one blocked lane. This adds no scheduler, daemon or router: the lab executes, Odysseus keeps authority, and the laptop is the control surface.

- **End a turn only for a named terminal condition**, and say which: (a) after the last delivery a fresh frontier read shows no eligible task whose owner authority permits it; (b) operator stop or interrupt, or a permission refusal that covers the whole authorised scope (a refusal of one action is recorded and independent work continues); (c) a budget is spent: 8 consecutive continuation turns with no delivered task, where delivery means the owning task's acceptance conditions are met (for example a merged and verified change or a closed task); a check or review counts only when it is what completes an accepted task, 4 hours elapsed, 12 paid model calls (Codex, Claude or GLM review or implementation runs), 150 tool calls in total, or the same failure three times; (d) only genuinely protected human-only gates remain.
- **Provider unavailable:** park only the verification-dependent acceptance, copy the verbatim error and stated reset time into the task's checkpoint as owed review, and dispatch other independently eligible work. A same-family GLM pass is labelled as such and never closes a gate that required Sol. A reset time already in the past means retry now, not a reason to wait or stop; check the clock before scheduling any wakeup.
- **`approval_required: true`:** read the owner authority (`AGENTS.md` "Standing operator preference: autonomous blocker resolution", the task's own gates) before treating it as a human gate. A stale flag does not stop the session; a protected action still does.
- **Checkpoint outside the conversation:** keep a compact, sanitised checkpoint (task id, acceptance criteria, completed work, owed review and its retry condition, next action; no raw prompt text or transcript) on the owning task's mutable status surface, so a resumed or compacted session continues without re-explanation. Write the append-only prompt-application trace (`evals/prompt-applications/estate-queue-priority-execution/`) at closeout, not as a live checkpoint.
- **Continuation mechanism:** verified on 2026-11-09 only that an operator-issued `/goal` installs a session-scoped Stop hook which blocks early stops in that session; it is not verified that a skill can invoke `/goal` itself, nor what survives compaction or process exit, so this skill relies on the rules above and does not assume more. An operator-set hook supplements these rules and does not raise any limit. This skill installs no Stop hook and never traps unrelated sessions.
