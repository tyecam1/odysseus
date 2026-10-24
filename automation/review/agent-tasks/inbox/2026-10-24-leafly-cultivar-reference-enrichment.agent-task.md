---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-24-leafly-cultivar-reference-enrichment
title: "Source-grounded Leafly cultivar enrichment for a 76-name research inventory"
status: inbox
priority: medium
task_type: implementation
created_by: operator-request-via-chatgpt
created_at: 2026-10-24T16:53:00+01:00
updated_at: 2026-10-24T16:53:00+01:00
executor: ""
execution_mode: review-first
architecture: single
architecture_rationale: "Reuse Odysseus ingestion, SourceEvent provenance, scheduler and retrieval. Keep public Leafly cultivar research distinct from Glasgow gig event data and from retailer-specific commercial inventory."
single_agent_baseline: "One qualified implementation owner with deterministic parsing and independent source-identity verification."
execution_host: lab
context_budget: medium
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - src/**
  - routes/**
  - tests/**
  - config/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - AGENTS.md
  - src/source_events.py
  - src/task_scheduler.py
  - src/rag_manager.py
  - src/url_safety.py
  - automation/review/agent-tasks/inbox/2026-10-24-weekly-external-source-sync-glasgow-gigs.agent-task.md
outputs:
  - curated Leafly source references and normalized cultivar notes, each with provenance and match classification
  - bounded optional refresh/reconciliation using the existing Odysseus scheduler
  - read-only research lookup from the current retrieval interface
  - fixture-driven tests and end-to-end evidence
result_path: ""
review_report_path: ""
handoff_model: ""
operator_decision_path: ""
duplicates: []
supersedes: []
notes: "Source-grounded descriptive research only. No retail drug pricing, quantity tiers, ordering, authentication, store inventory monitoring or commerce API. Operator clarification 2026-10-24 (owner, via Dispatch): the investigation spreadsheet keeps colour-coded, clearly-labelled ADVERTISED-package-option and VERIFIED-price-comparison columns as blank scaffolding, to be filled only from operator-verified observations; values are never estimated, scraped or invented. Prohibitions on credentials, stock monitoring, ordering and purchase recommendations stand unchanged."
---

# Leafly cultivar references for an investigation inventory

## User intent

The operator supplied a previously compiled **76-row research inventory** of names appearing in a third-party store and requested Leafly-based descriptive context added to an XLSX, plus a durable agentic requirement in the Odysseus repo. A local ChatGPT workbook titled `green_team_investigation_with_leafly.xlsx` was produced in the conversation; **do not assume it is present on any lab filesystem**. The product names and vetted Leafly source-match seeds appear below so the work item is actionable from the repo alone.

The intent is **non-transactional research and evidence tagging**. Leafly is a cultivar-reference source, not an authority on a third-party product's actual contents, chemical assay, batch identity, availability or quality.

### Cross-task ownership

Companion task: `automation/review/agent-tasks/inbox/2026-10-24-weekly-external-source-sync-glasgow-gigs.agent-task.md`.

Both may reuse existing neutral extraction, scheduling, provenance and retrieval surfaces. They must not share domain schemas, result records or ranking logic. Misumi continues to own its Glasgow events experience; this task has no influence on event recommendation filtering.

## Baseline source / match inventory

**Flower (36):**
Animal Runtz AA; Black Truffle AA+; Blue Pebbles AAA; Cherry Draco AA; Cherry Fanta AA; Cocoa Kush AA+; Cookie Dawg; Dante's Inferno; Doja AAA; Frost Bite AA; Gelato X Ice Cream Cake; Giraffe Pussy AAA; Grape God AA+; London Jelly AA; Mango Mirage; Master Kush A; Original Bubblegum AA; Papaya AA+; Permanent Chimera AA+; Purple Headband AA+; Purple Octane; Rainbow Runtz AA+; Shadow Runtz AA+; Slipstream AA+; Stardawg; Sundae Driver; Super Gelato AA; SuperBoof AA+; Tango AAA; Tropicana Cookies AA+; Vitamin Z; Zkittlez AAA; Zoap AA+; Zoap X Sangria AA+; Zookies AA+; Zushi AA.

**Hash / sift (25):**
Biscotti Sherbert Triple Filtered Hash; Cali Gold Full Melt Static 90–120u; Cali Gold Cured Bubble Hash SuperBoof; Cali Gold Hash Mix (BubbleXMousse); Cali Gold Triple Filtered Bubble Hash 73–120u; Cali Plates × Jolly Good Limited Edition Frozen Sift; Candy Static; Frontline WPFF; Kosher Static; La Mousse Hash Lemon; La Mousse Hash Patek; Moroccan Static Donald Duck; Moroccan Static Durian Kush; Moroccan Static Tropical Escape; Moroccan Triple Filtered Dry Sift 90/120µ; Moroccan Triple Filtered Hash €41 Stamp; Moroccan Triple Filtered Hash Grandaddy Purple; Moroccan Triple Filtered Hash Porsche Stamp; Mush Rush Static Hash Gelato S1; Purple Octane Static; Starburst Full Melt Hash; TerryGuyz Plasma Charged Frozen Sift; TLC Static Hash 130/73u; TLC Static Hash 139/73u; ViceCity Plasma Static Hash.

**Other extracts (2):** Budder; Delta-9 THC Distillate.

**Vapes (3):** D9 Distillate Vapes; DMT Vape Cartridges; Jeeter-Style Live Resin Vape 1G Disposable.

**Edibles (3):** Dank Gummies; Haribo Gummies 1000MG; Haribo Gummies 800MG.

**Mushroom-related (4):** Monkey Business Shrooms; Redboy Classic Shrooms; Torque Albino Shrooms; The Good Shroom Chocolate Bar.

**Mixed / miscellaneous (3):** High THC Trim X Shake; TGT Divine Pick n Mix Shake; TGT Pick n Mix.

These names reflect a previous catalogue observation; **not proof of present inventory, legality, composition or authenticity**. The previous pages had inconsistent reported catalogue totals (76 vs 81).

### Leafly reference seeds (27 corresponding name references)

Links below are descriptive sources from research performed 2026-10-24. Classify the matching strength as stated; do not silently promote indirect references to exact matches.

| Inventory name | Source | Relationship |
| --- | --- | --- |
| Animal Runtz AA | https://www.leafly.com/brands/premium-seed-market/products/premium-seed-market-animal-runtz-feminized-seeds | Leafly seed-product listing, not independent cultivar verification |
| Black Truffle AA+ | https://www.leafly.com/strains/black-truffle | exact strain name |
| Cocoa Kush AA+ | https://www.leafly.com/strains/cocoa-kush | exact strain name |
| Cookie Dawg | https://www.leafly.com/strains/cookie-dawg | exact strain name |
| Dante's Inferno | https://www.leafly.com/strains/dantes-inferno | exact strain name |
| Frost Bite AA | https://www.leafly.com/strains/frostbite | spelling/spacing variant |
| Giraffe Pussy AAA | https://www.leafly.com/strains/giraffe-pussy | exact strain name; sparse Leafly reviews |
| Grape God AA+ | https://www.leafly.com/strains/grape-god | exact strain name |
| London Jelly AA | https://www.leafly.com/strains/london-jelly | exact strain name |
| Master Kush A | https://www.leafly.com/strains/master-kush | exact strain name |
| Original Bubblegum AA | https://www.leafly.com/strains/bubble-gum | possible related name; not confirmed identity |
| Papaya AA+ | https://www.leafly.com/strains/papaya | exact strain name |
| Purple Headband AA+ | https://www.leafly.com/strains/purple-headband | exact strain name |
| Purple Octane | https://www.leafly.com/strains/purple-octane | exact strain name |
| Rainbow Runtz AA+ | https://www.leafly.com/strains/rainbow-runtz | shared name with multiple reported lineages |
| Stardawg | https://www.leafly.com/strains/stardawg | exact strain name |
| Sundae Driver | https://www.leafly.com/strains/sundae-driver | exact strain name |
| SuperBoof AA+ | https://www.leafly.com/strains/super-boof | same strain, formatting variant |
| Tropicana Cookies AA+ | https://www.leafly.com/strains/tropicana-cookies | exact strain name |
| Vitamin Z | https://www.leafly.com/strains/vitamin-z | exact strain name; no reported reviews |
| Zkittlez AAA | https://www.leafly.com/news/strains-products/top-100-marijuana-strains | alias / The Original Z coverage in article |
| Zoap AA+ | https://www.leafly.com/strains/zoap | exact strain name |
| Zookies AA+ | https://www.leafly.com/strains/zookies | exact strain name |
| Zushi AA | https://www.leafly.com/strains/zushi | exact strain name |
| Cali Gold Cured Bubble Hash SuperBoof | https://www.leafly.com/strains/super-boof | named cultivar only; no hash-specific verification |
| Moroccan Triple Filtered Hash Grandaddy Purple | https://www.leafly.com/strains/granddaddy-purple | named cultivar only; no hash-specific verification |
| Purple Octane Static | https://www.leafly.com/strains/purple-octane | named cultivar only; no concentrate-specific verification |

All **49 other product names** must remain `no_reliable_match_established` until individually verified; a generic product class, marketing name or extract type is not sufficient to attach a cultivar lineage.

## Required behavior

1. **Do not build a purchasing catalogue.** Only maintain neutral descriptive cultivar references and research provenance. Never collect retailer login credentials, price/quantity offers, stock monitoring, order links or purchase recommendations.
2. **Model the evidence accurately:** `inventory_name`, `category`, `leafly_cultivar`, `normalized_description`, `source_url`, `fetched_at`, `match_type`, `match_confidence`, `source_type`, `limitations`, `revision_hash`. Descriptions should be original succinct paraphrases of source-documented genetics, aroma and flavour, and optionally explicitly *reader-reported* effects. Do not assert medically proven outcomes, potency or effects of a seller's actual products.
3. **Reuse existing infrastructure:** SourceEvent for provenance/revision, existing scheduler (optional weekly re-check of the *curated Leafly source pages only* if actually worthwhile), storage and retrieval abstractions. No competing vector or personal memory store.
4. **Safety:** Fetch only public Leafly reference pages, observing access constraints. Treat scraped HTML as untrusted. Use existing SSRF/redirect, resource caps, authorisation and secret-handling controls. Do not store or use any third-party seller credentials.
5. **Data quality:** Tag ambiguous genetics and low-review pages. Distinguish no match, exact name, spelling variant, shared name with conflicting lineages, related name, third-party seed-product listing and cultivar mentioned within a different product type. Never conflate any of these with lab-verified identity.
6. **Presentation:** Provide a read-only research export (CSV/XLSX through existing document affordances where applicable) with the original 76 names and per-row Leafly URL/match status/description. All missing descriptions must carry explicit `no reliable match`; never generate plausible-sounding filler.
7. **Refresh:** If scheduled, run bounded fetches only on the matched Leafly source URLs, preserving last valid data and showing timestamp/status. Never imply all 76 are verified because 27 references were checked.

## Acceptance

- Count invariant: 76 seed names; 27 source-reference rows at this first pass; 49 unmatched.
- Correct label distribution: 18 exact strain-name matches, 2 name variants, 1 ambiguous shared name, 1 related-name match, 1 alias in article, 1 seed-product listing, 3 named-cultivar-within-hash references.
- Original summaries have valid corresponding sources; direct quotes are not copied wholesale.
- Snapshot changes and staleness visible; source blockage does not erase the prior valid snapshot.
- No inferred THC testing, seller batch identity, inventory, availability or quantity-pricing data.
- Fixture tests for misidentification, similar cultivar names, unknowns, links, prompt injection, output sanitisation and idempotent refresh pass.
- Live lab query works through approved retrieval and survives app/service restart before task can be marked shipped.
- Observe Odysseus `AGENTS.md` shipping-first backlog priority, mandatory preflight and write lease, controlled PR/merge/deploy, and independent verifier. A task card or test-only result is not deployment evidence.

## Sequencing and status

This is a new **inbox** task, not implemented or deployed by its creation. The already-created user-facing XLSX is a local conversation artifact and should not be represented as committed to lab or GitHub. Keep separate from the Glasgow gig source's runtime and domain acceptance.
