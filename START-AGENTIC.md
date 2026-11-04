# Start the usage-aware cross-repository work queue

Resolve `estate-queue-priority-execution` from `config/initialising-prompts.yaml` and execute its **current active** immutable prompt, not a pasted historical version.

Scope: the three separately governed queues in `odysseus`, `misumi` and `obsidian-phd`. Discover bounded metadata with:

```sh
python scripts/agentic_portfolio.py frontier --per-repo 4 --max-tokens 2500
python scripts/agentic_portfolio.py task --ref REPO_ID:BUCKET/FILE.md --tier contract --max-tokens 2500
```

These read-only commands require registered checkouts on **their execution host**. If the local checkout is incomplete, the portfolio tool automatically attempts an authenticated lab SSH fallback when the host-local `AOTERU_LAB_SSH_TARGET` and `AOTERU_LAB_REPO_ROOT` settings are present. SSH uses strict host-key checking and runs the same read-only tool on the lab, with recursion disabled. Never commit these host-specific values. If the invoking laptop lacks them, use the existing Odysseus lab SSH/remote-execution route to run discovery and subsequent preflight in the **lab checkout**; do not stop, demand a laptop clone or ask the operator to run shell commands. Confirm queue scope and worker eligibility independently. An SSH connection alone is insufficient to claim a successful discovery.

Before selecting, gather trustworthy current Claude, Codex and GLM usage evidence. Favour PhD research when Claude **and** Codex both have adequate task-sized allowance; favour shippable Odysseus backend and Misumi GUI work otherwise. Shipping-first, genuine urgency, ongoing near-complete work and safety gates take precedence; unknown quota is not zero quota.

Execute through each task's owning repository, existing preflight, qualified execution route, ParkLease and verification gates. Do not ask the operator to verify ordinary implementation. Reserve operator review for materials meant for other humans, subjective styling not determined by accepted precedent, and explicitly protected actions. Missing laptop checkout, a moving PR or a quota error is an execution-route issue, not a reason to halt all work.

Use progressive disclosure and record actual acceptance evidence. After delivering a task, update usage/priority and continue. Keep the initializer's application/evolution trace under the central register.

**Stable Claude Code command:** `/lazyUsage` from the Odysseus project (or from a user-level skill installation pointing to this checkout).
