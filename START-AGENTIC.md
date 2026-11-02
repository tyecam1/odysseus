# Start the prioritised cross-repository work queue

Resolve `estate-queue-priority-execution` from `config/initialising-prompts.yaml` and execute its current registered prompt.

The scope is **all three** existing task authorities: `odysseus`, `misumi`, and `obsidian-phd`. Discover each through the registered local checkout in `config/repositories.yaml`. Cross-repository discovery is read-only; ownership, preflight, write leases, acceptance, and approval always remain with the task's repository.

Use progressive context disclosure:

- **Discover:** `python scripts/agentic_portfolio.py frontier --per-repo 4 --max-tokens 2500`. This opens only task frontmatter and samples every available repository.
- **Select:** `python scripts/agentic_portfolio.py task --ref REPO_ID:BUCKET/FILE.md --tier contract --max-tokens 2500`. Resolve the exact reference from the discovery results.
- **Execute:** Read only necessary implementation and acceptance evidence after a task is selected.
- **Investigate:** Expand into history and full documents only when a specific question warrants it.

If registered checkouts are unavailable, report `scope_complete=false` and the missing repositories. Do not claim a complete global ranking or silently fall back to the Odysseus queue. Obtain missing read-only access through existing governed mechanisms when available.

Use the active priority policy in `AGENTS.md`, the central routing/lease contract and the relevant domain-owner approval gates. Task metadata never grants permission; no past assistant statement or memory waives owner-only gates.

A session may progress multiple authorised work items while preserving one prompt application identity. Record results through the existing register's closeout and evolution process.

**Stable command:** `/next-work` from the Odysseus project.
