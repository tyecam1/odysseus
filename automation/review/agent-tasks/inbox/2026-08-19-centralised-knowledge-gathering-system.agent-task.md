---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-08-19-centralised-knowledge-gathering-system
title: "Build centralised knowledge gathering and agentic capability convergence system"
status: inbox
priority: medium
task_type: capability-convergence
created_by: migrated-from-obsidian-phd
updated_at: 2026-09-23T15:26:00+01:00
executor: ""
execution_mode: review-first
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_path: 10-inbox/2026-08-19-centralised-knowledge-gathering-system.md
notes: "Migrated as shared backend/cross-repository work. Original body preserved below; re-ground paths against live Odysseus state before execution."
---

# Build centralised knowledge gathering and agentic capability convergence system

## Goal

Create one low-overhead intake pipeline for useful external knowledge encountered during normal browsing, while also re-auditing and converging the wider agentic architecture around Odysseus.

The task is not merely to add new sources to an old Odysseus boundary. The current boundary was drawn before many later capabilities existed. Reconstruct the actual implemented capability graph first, identify functions that were implemented in the wrong subsystem or duplicated across subsystems, then assign each capability to one canonical owner and migrate/adapt accordingly.

The end state should make Odysseus the coherent central operating and absorption interface for relevant agentic capabilities without making it a second research authority, second task system, or second implementation stack.

## Core architectural rule

Do not preserve existing subsystem boundaries simply because code currently lives there.

For every relevant capability, determine:

`what is the capability -> what state does it consume -> what state does it produce -> who should own the responsibility -> where should implementation live -> how should other systems call it`

Where capability A was built in location B but belongs in location C, move or refactor it. Where C already contains a parallel implementation, select one canonical implementation and retire/redirect the other. Preserve provenance and compatibility only where useful.

## Phase 0: reconstruct the live capability graph

Treat `automation/docs/current-capabilities.md` and `automation/docs/capability_manifest.json` as implementation truth, but verify them against the live repository because they may themselves lag recent work.

Audit all material agentic capabilities developed since the Odysseus architecture/interface boundaries were frozen, including at minimum:

- task lifecycle, work-item and agent-task routing
- source acquisition and paper search
- Zotero acquisition, context, organisation and handoff
- PDF/document extraction and normalization
- staged paper ingest and authored-synthesis preservation
- evidence authority, integrity, citation and provenance checks
- literature/review intent and research-method controls
- vault lexical/semantic/hybrid retrieval and RAG sidecars
- memory/context mechanisms
- skills and skill registry/routing
- model/executor routing and remote compute
- recurring upkeep, heartbeat and routine reports
- supervision/meeting extraction and operational exports
- external object/import adapters and asset/gallery interfaces
- browser/MCP/tool integrations
- GitHub/PR/review-side implementation workflows
- research-question, DRM, evidence and synthesis support
- any newer research-writing, presentation, rigour, verification or review agents/skills that now form part of the research engine
- any capability not named above that materially gathers, transforms, retrieves, judges, routes, synthesises or acts on research knowledge/work

Produce a machine-readable capability map with, for every capability:

- canonical capability ID
- current implementation path(s)
- current interface(s)
- current state/input/output contracts
- current owner implied by architecture
- actual owner implied by implementation
- proposed canonical owner
- authority level
- dependencies
- duplicate/overlap relationships
- migration action: `keep | move | merge | wrap | deprecate | delete-after-migration`
- justification

## Boundary reconciliation

Explicitly compare the live capability graph against:

- `automation/docs/odysseus-central-interface-contract.md`
- `automation/review/architecture/odysseus-consolidated-system-design.md`
- `automation/config/odysseus_interface_sources.yaml`
- `automation/config/odysseus_actions.yaml`
- `automation/config/odysseus_skill_registry.yaml`
- current task lifecycle contracts
- current retrieval/evidence authority contracts

Classify each mismatch as one of:

- architecture stale, implementation sensible
- implementation misplaced, architecture still sensible
- duplicate implementations
- missing central interface
- wrong state/authority boundary
- obsolete capability
- undocumented capability

Do not assume Odysseus should absorb implementation indiscriminately. Odysseus should own coordination, discovery, dispatch, cross-capability state visibility and absorption orchestration where appropriate. Domain logic should remain in a single reusable capability module and be called by Odysseus rather than copied into it.

## Knowledge gathering inputs

Support, where technically and legally feasible:

- Instagram saved posts and collections/folders
- LinkedIn saved posts and folders
- browser bookmarks
- URLs pasted directly into the vault or intake command
- useful links contained inside captured posts/pages
- ordinary web pages, PDFs, papers, repositories, videos and other research-relevant linked resources

Prefer official export/API mechanisms where available. Do not design around brittle authenticated scraping if a lower-maintenance route exists.

## Knowledge pipeline

`capture -> acquire -> normalise -> deduplicate -> assess -> route -> expose to Odysseus -> absorb/synthesise through governed capability interfaces`

For each item:

1. Preserve the original URL, source platform, capture date and available author/date metadata.
2. Acquire the useful content and recursively inspect worthwhile outbound links without uncontrolled crawling.
3. Convert useful material to Markdown while preserving provenance and separating quoted/source material from generated summary or interpretation.
4. Detect duplicates against existing vault material, canonical URLs, identifiers and previously captured sources.
5. Classify relevance to the PhD, current substudy/research question, and likely artifact destination.
6. Route high-confidence items automatically. Route ambiguous items to a single review inbox rather than inventing taxonomy.
7. Expose new material through the same central capability/state model used by Odysseus.
8. Let Odysseus invoke the appropriate existing research capabilities for later absorption, rather than implementing separate bespoke synthesis logic for social/bookmark intake.

## Information model

Use existing vault conventions before adding schema. At minimum, captured notes should retain:

- `artifact_type`
- source type/platform
- canonical URL
- original author/account where available
- original publication date where available
- capture/ingestion date
- provenance/acquisition method
- relevant project/substudy/RQ links where justified
- processing state
- absorption state
- evidential/trust class

Do not treat social posts, bookmarks or scraped pages as equivalent to peer-reviewed evidence. Preserve source class and evidential status explicitly.

## Routing

Inspect the live vault before implementation and reuse its canonical locations and front matter. Likely destinations include literature/reference material, standards, methods, research-question evidence, experiment/design inputs, work items, and a general research inbox. Do not create parallel folder hierarchies merely to mirror Instagram or LinkedIn collections.

Platform folders/collections are capture metadata, not the primary knowledge taxonomy.

## Odysseus target role

After convergence, Odysseus should provide one coherent interface over relevant agentic capabilities. It should be able to discover what capabilities exist, inspect their status, invoke them through governed contracts, and track resulting state without duplicating their business logic.

Relevant examples include:

- acquire/retrieve a source
- extract/normalise content
- query vault/Zotero context
- assess provenance/trust/evidence status
- deduplicate and route
- identify relationships to RQs/DRM/project state
- request literature/review analysis
- request verification/rigour passes
- request synthesis/absorption
- create or route follow-up work through the canonical task lifecycle
- expose review artefacts and approval requirements

The exact set must come from the live capability audit, not this illustrative list.

Odysseus remains non-authoritative for research truth. The vault remains research knowledge authority; the canonical task lifecycle remains work authority; approval remains human/PR/decision-record gated; implementation truth remains the capability registry plus code.

## Capability ownership rules

- one canonical implementation per capability
- one canonical state owner per state class
- one task lifecycle
- one research-knowledge authority
- one evidence/trust ladder
- one retrieval abstraction, with optional subordinate backends
- one skill registry
- one governed external-mutation surface
- no platform-specific downstream knowledge silos
- no second hidden orchestration brain

A wrapper/interface may exist in Odysseus, but duplicate domain logic may not.

## Interfaces

Aim for the smallest durable set of capture interfaces:

- a URL-drop interface for links pasted manually
- browser bookmark import/sync
- Instagram saved-content import
- LinkedIn saved-content import

Where direct platform synchronisation is unreliable or prohibited, support periodic account-data export ingestion instead. Document the trade-off rather than hiding it.

For internal agentic capabilities, define or normalize one registry-driven invocation contract so Odysseus can discover and call capabilities without hard-coded path-specific knowledge.

## Automation requirements

- idempotent reruns
- deterministic filenames and stable source identifiers
- canonical-URL and content-level deduplication
- bounded recursive link extraction
- retry/failure logging
- no silent data loss
- dry-run mode
- tests using fixtures rather than live accounts
- secrets/credentials excluded from the repository
- rate limits and platform terms respected
- human review only where classification, authority or evidential interpretation is genuinely ambiguous
- capability ownership and authority machine-checkable where practical
- migration preserves existing accepted research content
- deprecated interfaces fail visibly or provide bounded compatibility shims

## Implementation sequence

1. Inventory every implemented agentic capability and verify `current-capabilities.md` / `capability_manifest.json` against code.
2. Build the live capability/dependency/authority graph.
3. Compare that graph against current Odysseus architecture, registries and contracts.
4. Produce a convergence decision table showing `keep/move/merge/wrap/deprecate` for each relevant capability.
5. Update the reference architecture and registries to reflect the justified target ownership model before large code movement.
6. Refactor misplaced/duplicated capabilities toward one canonical implementation and stable interfaces.
7. Make Odysseus discover and invoke the converged capabilities through registry/contracts rather than copies.
8. Specify the canonical external-knowledge capture schema and absorption handoff/state model.
9. Implement URL-drop ingestion as the reference path.
10. Add bookmark ingestion.
11. Add Instagram and LinkedIn through the lowest-maintenance compliant mechanism available.
12. Add recursive useful-link extraction with strict depth/domain/volume bounds.
13. Reuse the converged capability graph for routing, retrieval, evidence checks, synthesis and follow-up work.
14. Backfill a small representative sample from each source and inspect the resulting vault state.
15. Run architecture/conformance tests proving there is no duplicate authority or shadow workflow.
16. Document one minimal operator workflow and remove redundant/manual paths.

## Required outputs

- live capability inventory
- capability dependency/authority graph
- stale-boundary/misplacement report
- convergence decision table
- revised Odysseus reference architecture/interface contract where required
- updated capability/source/action/skill registries where required
- migration/deprecation map
- centralised knowledge gathering implementation
- tests proving authority and ownership invariants
- concise operator documentation

## Acceptance criteria

- Every material agentic capability has one explicit canonical owner and implementation path.
- Every capability developed after the old Odysseus boundary was drawn has been assessed for inclusion/interface/migration.
- No capability remains in a location merely because it was historically implemented there when another subsystem is its justified owner.
- Duplicate implementations are merged or one is explicitly deprecated.
- Odysseus can enumerate and invoke relevant capabilities through governed interfaces without copying their domain logic.
- Existing research authority, evidence authority and task-lifecycle invariants remain intact unless an explicit reviewed migration replaces them.
- One command/workflow can ingest a pasted URL into a provenance-preserving Markdown artifact and route or queue it correctly.
- Bookmarks and saved social content enter the same canonical pipeline without source-specific downstream structures.
- Re-ingesting the same source does not create duplicate knowledge artifacts.
- Captured external material is distinguishable from peer-reviewed/validated evidence.
- Useful outbound links can be captured without uncontrolled crawling.
- Ambiguous routing produces one review item, not silent guesses or duplicate notes.
- Every successfully captured item has an explicit absorption state.
- Odysseus can enumerate unabsorbed items without platform-specific logic.
- Credentials and authenticated session data never enter Git history.
- Automated tests cover normalisation, deduplication, routing, capability ownership, authority invariants and absorption handoff behaviour.
- The operator does not need to know which historical subsystem currently contains a capability in order to use it.

## Non-goals

- building a general-purpose web crawler
- mirroring entire social-media accounts
- treating popularity or a saved post as evidence quality
- automatically promoting gathered material into established research conclusions
- maintaining separate permanent knowledge systems for each source platform
- making Odysseus a second vault, second queue, second evidence authority or monolithic implementation dump
- preserving obsolete architectural boundaries for compatibility alone
