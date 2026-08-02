# Repository Rules For Automation Agents

## Mission
Support this PhD vault as a controlled DRM research system for industrial human-robot collaboration, CPI process targeting, evidence traceability, and publication support.

## Canonical ontology boundaries
- Valid library-side artifact types: `paper`, `annotations`, `evidence`, `workflow`
- Valid active DRM artifact types: `problematisation`, `reference-node`, `reference-link`, `impact-node`, `impact-link`, `kpi`, `success-criteria`, `research-question`, `standard-raw`, `standard-rollup`
- Legacy lookup-only DRM token: `factor`
- Canonical ontology meaning is defined by `00-dashboards/artifact-types.md`
- Canonical annotation colour meaning is defined by `00-dashboards/zotero-colour-key.md`

## Canonical locations and aliases
- Active live directories: `03-concept/problematisations`, `03-concept/referenceNodes`, `03-concept/referenceLinks`, `03-concept/impactNodes`, `03-concept/impactLinks`, `03-concept/successCriteria`, `03-concept/kpiPacks`
- Legacy aliases remain resolvable: `03-concept/problematizations`, `03-concept/ref-nodes`, `03-concept/ref-links`, `03-concept/impact-nodes`, `03-concept/impact-links`, `03-concept/success-criteria`, `03-concept/kpi`
- Factor material is sourced from `03-concept/superseded/factors` plus current YAML references and remains legacy lookup context only in v1
- Canonical log root: `12-log`; `log/` and `log/daily` are non-canonical legacy roots and must not be treated as operator defaults

## Naming and note conventions
- Reuse live frontmatter shapes from existing notes before inventing new keys
- Prefer citekey or stable slug filenames
- Keep one note to one artifact type
- Keep evidence atomic and directly traceable
- Mirror canonical vault paths under `automation/review/<canonical-relative-path>`
- Move replaced staged drafts into `automation/review/superseded/...`

## Non-negotiable integration rules
- Preserve review-only defaults and fail-closed behavior
- Do not write directly into canonical ontology folders in normal runs
- Do not create a parallel ontology namespace
- Preserve explicit evidence-authority metadata so audited annotations stay distinct from extraction-derived support material
- Do not emit new canonical or staged proposal targets of type `factor`
- Do not rename, merge, split, supersede, or delete ontology notes automatically
- Do not mutate Zotero PDFs unless explicitly asked to run the approved apply worker or the legacy highlighter path
- Keep one review-only approval handoff for overnight annotation proposals: approval manifests may mark items apply-ready for a later worker, but they must not apply highlights, imply live PDF mutation, or collapse machine-generated provenance into human-audited provenance
- Keep one explicit post-approval apply worker: it may consume only approved annotation manifests, mutate only the governed target PDF path already named in the manifest, use exact requested-page application only, and write apply audit records plus updated apply status back to review
- Keep one explicit post-apply vault ingest worker: it may consume only a matching approved annotation manifest plus successful apply audit, write only to bounded canonical library annotation/evidence families, and preserve explicit approved-machine-applied provenance instead of collapsing into human-audited annotation semantics
- Keep one acquisition handoff contract: acquisition manifests expose review-only `review_handoff` data and only matched usable PDFs may feed ingest
- Keep one retrieval abstraction: lexical, semantic, and hybrid modes live in the shared vault-context layer with lexical fallback
- Keep overnight worker proposal drafting on the existing worker spine: the committed settings surface now prefers model-backed drafting, deterministic remains the explicit fallback and benchmark, and neither mode may substitute for governed queue admission
- Keep one tracing contract: optional observability writes stay under `automation/logs/observability/**` and must use sanitized payload summaries
- Keep MCP as a thin wrapper over bounded core modules only; it must not become a second business-logic stack
- Keep autolab runs isolated to candidate worktrees and review artifacts; autolab must never merge, promote, or widen permissions automatically

## Human-gated actions
- new canonical `problematisation` notes
- new canonical `impact-node` notes
- any ontology rename, merge, split, or supersede action
- strong causal-link promotion
- promotion from `automation/review` to canonical folders
- any direct invocation of the Zotero PDF highlighter against a real paper
- any approved apply worker run against a real paper without an explicit approved annotation manifest
- any approved annotation vault-ingest run that lacks an explicit approved manifest plus successful apply audit for the same paper
- any live Zotero reorganisation (`zotero-library-audit --apply-manifest ... --execute`): requires an approved reorganisation manifest, `[zotero_organization] apply_enabled = true`, the `APPLY-ZOTERO-REORG` confirmation token, and resolvable `[zotero]` Web API credentials; it is disabled by default, dry-run unless `--execute`, and never runs on an unattended schedule
- deletion of unmerged branches, force-pushes, or history rewrites of remote refs
- pushes to any branch other than the task's own working branch
- PR merge, unless explicitly delegated for the named PR. A per-PR named dual-agreement record (per `automation/docs/dual-agreement-protocol.md`), made under the operator's standing delegation of 2026-07-27, constitutes explicit delegation for the named PR — but only for automation-surface PRs whose diffs are confined to `automation/**`, `Scripts/**`, `.claude/**`, `.agents/**`, and docs/config surfaces. Research-integrity and canonical surfaces (evidence, trust tiers, canonical ontology, Zotero, external publication) stay human-only. This delegated acceptance is a distinct class, explicitly not `V2_HUMAN_VERIFIED`, and always carries a machine-delegated provenance label. The operator can revoke the standing delegation with one line, which immediately restores the prior human-only PR-merge gate.
- external publication or submission of research material
- raw research data ingestion into the vault or git
- broad cleanup or mass moves without an approved migration ledger

## Promotion rules
1. Validate staged files first.
2. Review duplicate-risk hits against existing vault context.
3. Confirm frontmatter, sections, and canonical target path.
4. Approve promotion explicitly outside v1 automation defaults.
5. When promotion eventually happens, move replaced canonical notes into sibling `superseded/` folders for traceability.

## CPI and research-fit discipline
- Prioritise industrial relevance, generalisability, feasibility of data capture, and alignment with current PhD direction
- Treat CPI process scoring as a review aid, not an auto-selection mechanism
- Keep problematisation, originality, rigour, and significance visible in proposal rationale

## Architecture control surface
Before changing automation behavior, review:
- `automation/README.md`
- `automation/docs/full-system-plan.md`
- `automation/docs/current-capabilities.md`
- `automation/docs/capability_manifest.json`
- `automation/docs/agent-boundaries.md`

Treat these as the working architecture, capability, and permission contract for future automation tasks.

## Capability truth maintenance
- Any capability-affecting change must update `automation/docs/capability_manifest.json`.
- Any capability-affecting change must update `automation/docs/current-capabilities.md` in the same PR/change, not later.
- `automation/docs/full-system-plan.md` is the target-architecture document; do not use it to imply that planned behavior is already implemented.
- Capability docs must keep `implemented`, `partial`, `blocked`, and `planned` distinct.
- Run `python -m unittest Scripts.automation.tests.test_capability_truth_contracts` when changing capability-affecting code or docs.
