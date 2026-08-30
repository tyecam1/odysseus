# Aoteru external knowledge ingestion — programme state

Durable, resumable tracker for
`docs/aoteru-external-knowledge-ingestion-programme.md` (PR #24). Re-read
live estate/repository state before trusting anything below as still true;
this file records what was verified at `last_verified_commit`, not a
permanent fact. Follows the existing convention in
`docs/aoteru-autonomous-programme-state.md`.

Session start: 2026-08-30, laptop controller session (checkout-free,
`companion/laptop_client/aoteru.py`). Live estate check this session:
`aoteru status` — backend reachable/healthy, 1 eligible host
(`hz2-workstation`, lab); `desktop-in7o23d` (home) present but not
verified (`config/estate.yaml verified: false`), consistent with prior
programme-state records — not treated as a routing candidate.
`aoteru park-status` — no active park leases estate-wide at session start.

## Batched human actions

None yet. No credentials, exports, or governance decisions have been
required to reach the current checkpoint. P2 (Instagram export importer)
and P5/P6 (WhatsApp) will need real or representative export files and,
for P6, real Meta/WhatsApp Business credentials — batched when reached,
not before.

```yaml
- id: P0-live-reconciliation-bootstrap
  outcome: programme can be resumed reliably from live estate truth
  status: complete
  depends_on: []
  acceptance_tests:
    - estate truth recorded (aoteru status / route / park-status outputs)
    - no duplicate architecture identified (grep of odysseus for
      SourceEvent/instagram/whatsapp/ingest returned zero hits pre-P1)
    - exact P1 task packet defined
  evidence:
    - "aoteru status: backend healthy, eligible hosts=[hz2-workstation
      (lab)]; desktop-in7o23d (home) not verified, excluded — matches
      docs/aoteru-autonomous-programme-state.md's existing home-ineligible
      record, no drift."
    - "aoteru park-status at session start: active_park_leases: []."
    - "GitHub code search (default branch dev) for SourceEvent, instagram,
      whatsapp, ingest across tyecam1/odysseus: 0 hits — P1-P6 are
      genuinely greenfield, no duplicate/parallel implementation exists to
      reconcile against."
    - "config/repositories.yaml already registers odysseus (canonical),
      misumi (authority misumi, remote confirmed), obsidian-phd (authority
      obsidian-phd, remote confirmed) — no new repository-registry work
      needed for P1-P3's authority boundaries."
    - "Existing conventions identified for reuse rather than reinvention:
      src/attachment_refs.py (stable ref + sha256 checksum instead of
      inline raw bytes — the pattern P1's SourceEvent payload_ref must
      follow); core/database.py is the canonical SQLAlchemy model module
      (src/database.py only re-exports it); scripts/update_database.py is
      the existing additive-migration convention (no Alembic); this
      programme-state file itself follows docs/aoteru-autonomous-
      programme-state.md's existing YAML-block convention rather than
      inventing a second state format."
    - "aoteru lab dispatch (code-fast/ornith:9b) empirically confirmed to
      be a single-shot text completion against RunTaskEnvelope.objective,
      not an agentic file-editing session — a real bounded P1 objective
      returned only a one-line text reply ('I'll start by exploring...')
      with no repository mutation. This matches the aoteru-estate-routing
      skill's documented caveat and is recorded here as a measured
      capability boundary, not an assumption: implementation-shaped work
      for this programme requires the Claude/Codex paid lane (or a real
      agentic session run from an actual repo checkout on the lab host via
      scripts/agent claude auto, which this checkout-free laptop session
      cannot invoke directly), while single-shot review/classification/
      synthesis-shaped work remains a valid use of the free local lane."
  commits: []
  remaining_risks:
    - "local-fast/code-fast lanes via aoteru ask/lab/auto cannot perform
      real implementation (see evidence above) — every implementation-
      shaped task in this programme will need either a Claude/Codex paid
      lane dispatch or genuine lab-host-originated agent execution; budget
      max_paid_calls accordingly per task rather than assuming the free
      lane can absorb it."
  human_action: none
  next_action: P1 dispatched this session — see P1 entry below.
  last_verified_commit: 3a87800

- id: P1-source-event-adapter-contract
  outcome: one bounded adapter contract emits existing Odysseus SourceEvent
    idempotently
  status: active
  depends_on: [P0-live-reconciliation-bootstrap]
  acceptance_tests:
    - same logical import twice does not duplicate
    - content revision is detectable
    - malformed input fails visibly
    - provenance survives downstream processing (round-trip read)
    - large/raw payloads are not unnecessarily stored in SQLite
    - secrets/raw private material are not committed
    - pytest tests/test_source_events.py -q passes
    - pytest tests/test_update_database_script.py -q still passes
    - git diff --stat scoped to core/database.py, scripts/update_database.py,
      src/source_events.py, tests/test_source_events.py only
  evidence:
    - "Repo lease acquired via aoteru park odysseus --branch
      feat/external-ingest-source-event-p1 -> lease_id
      20d4db50-d475-453b-b2b4-56f106dbbee8, host hz2-workstation, worktree
      /home/agent/projects/odysseus-aoteru."
    - "Bounded worker packet dispatched (single mutable worker, no swarm)
      to a Claude implementation lane (remote isolated environment) after
      the local code-fast lane was confirmed non-agentic (see P0
      evidence) — this is the recorded insufficient_capability escalation
      trigger, not a default choice."
  commits: []
  remaining_risks:
    - "Worker result not yet inspected this checkpoint; V0 deterministic
      verification (pytest + ast parse + diff-scope check) still to be
      run by the foreman against the actual returned diff before this
      phase can move to complete."
  human_action: none
  next_action: >-
    On worker completion: run V0 deterministic verification against the
    real branch state (not the worker's self-report), then either accept
    + release the park lease + update this record with commit SHA, or
    revise/re-scope/escalate per the worker packet's forbidden_actions and
    the programme contract's stop conditions.
  last_verified_commit: 3a87800

- id: P2-instagram-export-importer
  outcome: >-
    a real/representative Meta Download Your Information export
    reconstructs Saved-item inventory sufficiently for selected collection
    routing
  status: pending
  depends_on: [P1-source-event-adapter-contract]
  acceptance_tests:
    - schema-fixture tests only, no live scraping
    - collection membership, stable identifiers/pointers, timestamps,
      declarative domain mapping, idempotency, visible schema-drift
      failure
  evidence: []
  commits: []
  remaining_risks:
    - "Needs a representative Meta DYI export fixture — not yet a batched
      human action since P1 is not complete and no fixture has been
      requested yet; will be batched when P2 is materialised."
  human_action: none yet
  next_action: >-
    Do not materialise beyond this phase specification until P1 is
    complete and verified — per contract, materialise only the current
    task and immediately unblocked next tasks.
  last_verified_commit: 3a87800

- id: P3-P10
  outcome: see docs/aoteru-external-knowledge-ingestion-programme.md phase
    specifications
  status: pending
  depends_on: [P2-instagram-export-importer]
  acceptance_tests: []
  evidence: []
  commits: []
  remaining_risks: []
  human_action: none yet
  next_action: kept as phase specification only; not materialised
  last_verified_commit: 3a87800
```
