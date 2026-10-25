---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-25-green-team-preference-ingestion-telegram-mcp
title: "Ingest Green Team comparison canon and add governed Telegram MCP merchant enquiries"
status: inbox
priority: normal
task_type: ingestion-and-integration
created_by: chatgpt
created_at: 2026-10-25T12:17:00+00:00
executor: policy-selected
execution_mode: bounded-implementation
risk_level: high
approval_required: true
requires_mcp: true
requires_web: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
source_of_truth:
  repository: tyecam1/misumi
  path: docs/preferences/green-team-leafly-product-comparison-v1.md
  version: 1
  branch: main
canonical_runtime_owner: tyecam1/odysseus
allowed_paths:
  - automation/review/**
  - docs/**
  - integrations/**
  - src/**
  - core/**
  - routes/**
  - services/**
  - config/**
  - tests/**
  - evals/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
  - "**/*telegram*session*"
outputs:
  - validated preference contract loaded from Misumi canon
  - deterministic product research ingestion and XLSX export plan or implementation
  - evidence-backed source reconciliation and category-neutral score tests
  - Telegram MCP capability assessment and operator-approved safe non-transactional messaging adapter
  - security and acceptance verification with exact blocked prerequisites
  - docs and operator handoff
---
post_merge_status: misumi-pr-88-merged; canon resolves at tyecam1/misumi@main (blob 3ac07e494e5575d8a61c730956f04627169533a3, main head 075b1547f668); restated parameters in this exemplar are non-authoritative summaries


> **Canon precedence (2026-10-25, post-merge).** Misumi PR #88 is MERGED: the canonical document now resolves at `tyecam1/misumi@main:docs/preferences/green-team-leafly-product-comparison-v1.md` (content blob `3ac07e494e5575d8a61c730956f04627169533a3`, main head `075b1547f668`). Numeric parameters, weights, schema and ordering restated anywhere in this card or the exemplar are **non-authoritative summaries**; on any discrepancy resolve to the Misumi document at a pinned commit. Nothing here satisfies 'done' while implementation, tests or external evidence are outstanding.


# Green Team/Leafly preference ingestion + Telegram MCP integration

## Ownership/intent

The operator asked the system to **remember and enforce all decisions** from the iterative 78-row Green Team/Leafly Excel build and to **add the ability to communicate with the store via Telegram MCP**. The canonical preferences and workbook schema are **not duplicated here**: always read `tyecam1/misumi@main:docs/preferences/green-team-leafly-product-comparison-v1.md` at a pinned commit. Treat its section 1 preferences, section 3 composite-equation/order of operations, section 5 exact two-sheet deliverable and section 6 Telegram boundary as binding. An implementation must not be called done because the spec was saved.

Odysseus owns execution, MCP integration, tool routing, explicit external-send approval, job/task lifecycle, provenance/audit transport, and source-status reporting. Misumi owns the personal product-comparison preferences and any user-specific intended research criteria. No household data moves into the public Odysseus repository; only a **pointer**, generic integration contracts and non-sensitive synthetic tests may be public.

## Preliminary research that must not be overstated

- Historical source workbook: `leafly76-rarity-grades-expanded-scores.xlsx` from conversation, **not necessarily attached or present on a future agent host**. The workbook's existence on a ChatGPT sandbox in a previous session does not grant Odysseus access. Use the system's existing approved file transfer/input mechanism or obtain the exact artifact through an authorised source if needed.
- 78 historical comparison records, captured retailer API subset of 69 products (24 Oct 2026). Nine research records were not listed then. **No guarantee these statuses persist.**
- Seller rating count/mean can be found in WooCommerce Store API `review_count`, `average_rating` on accessible product records, but a blank/zero-store rating with no reviews is unrated, not zero-star.
- WooCommerce Store API supports `orderby=popularity`: https://developer.woocommerce.com/docs/apis/store-api/resources-endpoints/products . Whether the specific shop exposes retrievable rank/quantity is not yet proven. Must capture full, paginated, timestamped ranked results before claiming the actual seller popularity order.
- Leafly rating counts contribute the independent Leafly-side popularity evidence, moderated by match certainty; seller review counts are a weaker engagement proxy where a real store sort is unavailable.
- Telegram MCP not yet established. **Bot API cannot initiate arbitrary merchant DMs** unless bot was contacted/added to the chat: https://core.telegram.org/bots . Investigate supported existing adapters first; don't claim installation from the spec.

## Mandatory task sequence

1. **Preflight and truth audit**: on latest `tyecam1/odysseus@dev`, load `AGENTS.md`, `docs/aoteru-estate-execution-contract.md`, existing MCP integration, task queue, approval gate and existing memory-source ingestion. On Misumi `main`, load `AGENTS.md`, `CLAUDE.md`, `docs/memory-architecture.md`, canonical preference path above. Follow Odysseus `aoteru preflight`/write-lease requirements before any mutation. Do not start an overlapping queue/memory/router. Honour the current shipping-first backlog priority; this is an inbox task until admitted under normal governance.
2. **Register/ingest without duplicating canon**: in the existing source ingestion or approved personal domain-mapping route, refer to Misumi's pref document by repo/path/revision; preserve original operator choices (6 factors, per-category reference, popularity 0.25, gamma 6, missing penalties, buying-status ordering, exact A:W overview). Build small, provenance-bearing lookup and validation; no automatic raw-chat-to-source promotion, no new vector-memory authority. Track loaded preference commit hash and schema version; fail clearly on inaccessible Misumi Git.
3. **Source adapter**: inspect and reuse existing WooCommerce/Leafly web data mechanisms; only add minimal dedicated code if not covered. Collect published product ID/slug, full description, publication status, `is_in_stock`, `is_purchasable`, variation sizes/individual prices, currencies, review counts/ratings and dated product links. Attempt complete `orderby=popularity` pagination without inventing sales counts. Keep "unknown", "not listed", "out of stock", and "purchasable" distinguishable. Record failed/blocked retrieval and do not silently substitute stale popularity evidence.
4. **Deterministic scoring/report**: implement or wire the formula from Misumi canon as specified, with category-specific tie-aware normalization, five 1.0-weight factors and 0.25-weight combined popularity, meaningful source confidence, optional rarity estimates strictly distinguished from seller grades, and penalty after gamma calibration. Do not conflate a relative score with quality certainty. Score every record; select only category-applicable factors. Export exactly `Overview` and `Details`; retain price/description evidence, category band styling and score-only green gradient. Available products first, globally unbuyable/unlisted records last; sort within available-status blocks by category, score DESC, unit price ASC. Do not fabricate options beyond source evidence. Feature must be usable on fresh future datasets with dynamic counts, not hard-coded 78 rows.
5. **Telegram capability reconnaissance**: inspect whether a trustworthy Telegram MCP connector/server already exists and is compatible with the Odysseus MCP registry and approval hooks. Identify whether the merchant exposes an actual verified Telegram destination (a store website link is not proof of an authenticated Telegram account). Do not guess handles or send to unverified destinations. Bot API is possible only in an established chat; otherwise a separately consented user-account Telegram client may be technically required, which must undergo higher-risk credential/session review. Any external dependency/credential must be user-supplied and recorded as a blocker, not committed or worked around.
6. **Messaging feature scope**: provide `merchant_contact.prepare_draft`, `merchant_contact.review`, `merchant_contact.send_approved`, and `merchant_contact.read_replies` through **existing** Odysseus approval/tool plumbing, as a reusable Telegram MCP integration rather than hardcoding one retailer. Limit to lawful, non-transactional customer-support/product-information communications; no automation of orders, payments, shipping or restricted-product transactions. Outbound sends require an explicit scoped user approval **for the exact recipient and exact message content**, no silent follow-ups, and a redactable audit trail. If no Telegram access is connected, show exact user setup/permission blocker and leave the send control unavailable (draft-only is acceptable). Never store credentials, SMS codes or MTProto sessions in Git or emit them in logs.
7. **Reply verification and review**: incoming merchant responses are unverified `merchant_claim` data. Store message metadata/source timestamps with secure retention, preserve the source thread pointer; require source reconciliation and approval before applying it to structured comparison cells. User should be able to see what source changed which value, when, and why. No covert periodic contact.
8. **Acceptance and tests**: build synthetic-category and source-quality tests. Validate exact Overview 23 columns and Details, all values and formulas, price option/source preservation, missingness across categories, seller/Leafly engagement separation, category-mean neutrality, score spread gamma/penalty order, partial-store retrieval and 69/9 historical fixture as a *fixture* only. Test Telegram permission denial, unavailable MCP, wrong recipient, bot cannot initiate, duplicate sends/retries, redaction, inbound untrusted content, and approving exact content. Produce a failure-first report; no claims of live send/reply until an explicitly authorised **non-transactional** test has been completed.
9. **Verification and handoff**: record changes, live source commit hashes, implementation checks, sample workbook and diffs, and the unresolved external prerequisites. Respect active backlog policy, independent verification and the appropriate `dev` review/merge gates. Do not self-declare deployed if merely documented.

## Done means

- Misumi canonical preferences actually retrievable from ordinary agent sessions via the existing governed source route and visibly used when the user requests this report.
- Rerunnable source-to-XLSX result, validated for the user-chosen two-sheet schema and scoring, or explicitly stated unimplemented gaps with an owned acceptance task.
- Telegram MCP connection *and* lawful merchant-contact workflow **separately** proven, or accurately blocked with exactly specified required consent/credentials/contact identifiers. A drafted adapter or this task document is not working Telegram access.
- No silent external sends, unverified sales ranks, fabricated metrics, leaked credentials, new authority split or duplicated queue.
- The operator receives a compact `canon_ref | runtime_commit/PR | tests | ingest proof | Telegram status | exact blocker` report.

## Minimal operator kickoff to ingest the contract

> Use `tyecam1/misumi@main:docs/preferences/green-team-leafly-product-comparison-v1.md` as the authority, and this task card as the bounded execution checklist. Confirm the live repository state before implementation, route through Aoteru preflight/lease, preserve Misumi domain authority and Odysseus execution ownership, validate workbook formulas and output, and gate Telegram MCP outbound messages on explicit operator approval. Do not claim capability without end-to-end evidence.

## Implementation progress (2026-10-25, feat/green-team-research)

- `src/product_research.py`: deterministic canon scoring (midrank category factors, single-peer neutral, combined rating with unrated!=0, verified `orderby=popularity` ordinal popularity, weights 5x1 + 0.25 popularity, GM -> B -> gamma-6 spread -> 0.8^max(0,m-1) penalty, rarity-grade table).
- `src/product_workbook.py`: exact two-sheet Overview(23 col A:W)/Details writer, category banding + green gradient on score only.
- `src/merchant_contact.py`: transport-agnostic governed merchant-contact adapter (draft/approve/send/read; exact-content approval, verified-recipient gate, duplicate-send block, merchant_claim inbound classification). Draft-only: no Telegram MCP transport is configured (operator blocker).
- Tests: tests/test_product_research.py + tests/test_merchant_contact.py (27 passed).
- Store popularity: verified orderby=popularity works; full 69-product ordinal captured 2026-10-25 (operator snapshot file).
- Canon ingested as SourceEvent `misumi_preference_canon` (misumi@main 075b1547, blob 3ac07e49, validation all-pass).
