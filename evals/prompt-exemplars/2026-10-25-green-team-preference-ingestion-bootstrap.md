---
exemplar_id: 2026-10-25-green-team-preference-ingestion-bootstrap
captured_on: 2026-10-25
capture_basis: operator-requested-ingestion-prompt
status: candidate
source_task: automation/review/agent-tasks/inbox/2026-10-25-green-team-preference-ingestion-telegram-mcp.agent-task.md
canonical_preference_repo: tyecam1/misumi
canonical_preference_path: docs/preferences/green-team-leafly-product-comparison-v1.md
---

# Exact bootstrap prompt

```text
You are operating against my canonical GitHub estate, not a blank new project. Ingest and implement the Green Team × Leafly product comparison preferences and the Telegram MCP merchant-enquiry capability.

CANON AND ORDER:
1. Read tyecam1/misumi PR #88 (https://github.com/tyecam1/misumi/pull/88), then the complete docs/preferences/green-team-leafly-product-comparison-v1.md on its PR branch. Resolve or merge according to repository governance before treating the document as authoritative on main. Record the exact canonical commit hash.
2. Read tyecam1/odysseus PR #163 (https://github.com/tyecam1/odysseus/pull/163), especially automation/review/agent-tasks/inbox/2026-10-25-green-team-preference-ingestion-telegram-mcp.agent-task.md. The task is not shipped just because its PR exists.
3. Reconcile LIVE default branches, AGENTS.md/CLAUDE.md, active queue/shipping-first policy, tool inventory, implementation paths, Misumi ownership, Odysseus authority, and any existing overlapping capability. Perform aoteru preflight and satisfy normal repo write-lease/governance before editing. Never create a second router, task queue, memory store, approval authority, or another personal-preferences canon.

INGESTION:
- Make Misumi's preference file discoverable by the EXISTING Odysseus memory/source-ingestion and task-planning systems. Index/ingest a provenance-bearing pointer including repo, path, commit, version, timestamp and validation status, rather than duplicating preference prose as independent truth.
- Prove an ordinary fresh agent session can retrieve the current specification without relying on this chat transcript. On discrepancy, defer to Misumi canon and recorded explicit operator updates.
- Use the source workbook, dated seller snapshot, Leafly provenance and fresh public evidence whenever available. Do not pretend the historical workbook is on disk unless the exact bytes/path can be verified; route through approved artifact/files mechanisms.

DELIVERABLE AND TESTING:
- Preserve exactly two sheets (Overview + Details). The Overview has the exact 23 columns A:W in the Misumi spec, including full seller description, percent composite score, combined rating, combined popularity, normalized unit price, THC, sativa/indica, six size/price pairs and dated buying status. Seller/inferred A grades and all raw/uncertain evidence belong in Details.
- Implement deterministic category-specific normalized factors and comparable-unit prices, equal weights for grade/rating/price/THC/sativa-indica, 0.25 popularity weight, Leafly + seller source separation, rarity-grade estimates with confidence for ungraded flowers, score coverage for EVERY item, 20% compounded penalty from the SECOND missing APPLICABLE metric, gamma=6 editable percentile spread, and availability-first sorting. Do not mistake ratings for actual sales popularity or rarity for certified quality. Keep only neutral alternating category fills and a green gradient on the score.
- Attempt genuine full-store WooCommerce popularity ordering with documented paginated evidence; if blocked, retain a clearly named review-engagement proxy instead of inventing rank. Repair descriptions and size/price coverage without guessing variants, and distinguish not-listed from verified out-of-stock.
- Run evidence-integrity, dynamic-row, numerical, score-equivalence, unit/category-fairness, missingness, source-matching, full-description retention, availability, sorting, Excel import/export and no-formula-error tests. Produce a validation report and a fresh downloadable workbook if the dataset is available.

TELEGRAM MCP:
- Discover and reuse an existing, supported MCP Telegram adapter if possible; no parallel MCP business logic. Confirm a verified merchant chat destination and whether Bot API can reach it. If Bot API cannot initiate the chat, explain that and request only the explicit account/channel setup truly needed; never invent a recipient or use unapproved account sessions.
- Provide a safe workflow to draft, preview, explicitly approve, send and read lawful NON-TRANSACTIONAL customer-service/product-information enquiries. Keep Telegram bot/session secrets out of Git and logs, enforce least privilege, no silent/background sends or automatic follow-ups, and do not enable purchases, payment, shipping arrangements or restricted-product transactions through the integration.
- Mark merchant replies unverified until source-reconciled; never silently overwrite the seller data. Test missing connection, wrong recipient, revocation, duplicate send, approval bypass, privacy and response provenance.

EXECUTION AND FINISH:
Carry the bounded task through the existing estate routing/testing/review workflow rather than stopping at documentation. Respect the active shipping-first backlog rule; if unadmitted, record the task as pending and do not bypass priority. Do not call a queued feature deployed. At close, report exactly:
CANON_REF (repo/path/commit/version) | PRs/merges | INGESTION_PROOF (fresh-session retrieval) | WORKBOOK_TESTS | STORE_POPULARITY_SOURCE | TELEGRAM_MCP (connected/draft-only/blocked) | APPROVAL_BOUNDARY | REMAINING_BLOCKERS.
If truly blocked by permissions, credentials or external access, state precisely what user action is needed, save completed independent work, and never claim success without end-to-end evidence.
```

## Why this exemplar

Preserves a self-describing, cross-repository ingestion prompt with explicit owner boundaries, fresh-session retrieval proof, numerical/evidence verification, and Telegram MCP external-send approval gates. It is a candidate, **not** a registered active initialiser; it does not grant merge, execution, or contact authority.

## Known limitations

The Misumi preferences and Odysseus task remain open PRs until reviewed and merged. The historical XLSX is not uploaded to Git. Neither true seller sales-based popularity nor a reachable merchant Telegram address is established; Telegram MCP is unconfigured. No application trace or model rating exists yet.

## Later verification

Record application traces and possible promotion through Odysseus' pre-existing initialising prompt register if warranted by observed results. Do not create a second registry.
