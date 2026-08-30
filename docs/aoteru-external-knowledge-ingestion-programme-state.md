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
      whatsapp, ingest across tyecam1/odysseus: 0 hits at audit time.
      CORRECTED after P1: a SourceEvent model already existed in
      core/database.py from a prior P4 memory-provenance workstream —
      GitHub's code-search index was stale/lagging, not the repo. Lesson
      recorded here: GitHub code search is not reliable ground truth for
      this audit; direct file reads are. instagram/whatsapp/ingest-parsing
      code genuinely does not exist yet (confirmed by direct inspection of
      the P1 diff and core/database.py, not by search)."
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
  status: complete
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
      /home/agent/projects/odysseus-aoteru. Released after acceptance."
    - "Bounded worker packet dispatched (single mutable worker, no swarm)
      to a Claude implementation lane after the local code-fast lane was
      empirically confirmed non-agentic (single-shot text completion, no
      file-write tool) — recorded insufficient_capability escalation
      trigger, not a default choice."
    - "DISCOVERED CONSTRAINT: requesting isolation:remote on the worker
      did not actually run it in a remote cloud environment — it wrote to
      C:\\Users\\tyeca\\odysseus-work on this laptop, violating the
      operator's explicit no-local-checkout instruction. Detected this
      checkpoint by independently checking the reported file paths (not
      trusting the worker's self-report), the local checkout was removed
      immediately (git status confirmed everything was already committed
      and pushed to origin, nothing lost), and it is recorded here as a
      real product-behaviour boundary for this environment, not an
      assumption: isolation:remote cannot currently be trusted to avoid
      touching this laptop's disk, so future implementation-lane
      dispatches must verify/clean up the same way rather than assume
      isolation held."
    - "Independent foreman verification (not the worker's self-report):
      gh api compare dev...feat/external-ingest-source-event-p1 confirmed
      diff scope is exactly the 4 declared files (core/database.py +80-2,
      scripts/update_database.py +73-2, src/source_events.py +172 new,
      tests/test_source_events.py +148 new). Full patch read directly by
      the foreman: SourceEvent model extended additively (payload_ref,
      received_at, status, prior_content_hash, revision_count) rather
      than creating a colliding duplicate table — a pre-existing
      SourceEvent/source_events table from a prior P4 memory-provenance
      workstream was reused, consistent with the programme's
      no-duplicated-raw-source-authority invariant. Idempotency via a
      partial unique index on (source, external_id) (sqlite_where
      external_id IS NOT NULL, so legacy chat/import rows are
      unaffected). record_source_event() normalizes+sha256-hashes
      content, never persists raw content, raises
      SourceEventValidationError (ValueError subclass) on missing
      source/external_id/empty content. Tests read directly by the
      foreman: parametrized malformed-input cases, duplicate-identical
      no-op, multi-step revision trail (prior_content_hash/revision_count
      incrementing across 3 revisions), round-trip field preservation,
      and an explicit never-stores-raw-content assertion."
    - "pytest tests/test_source_events.py tests/test_update_database_script.py
      -q: 17 passed (worker-reported, cross-checked by the foreman reading
      the actual test file content and finding the assertions genuine and
      non-trivial, not placeholder tests)."
    - "PR opened for human review/merge:
      https://github.com/tyecam1/odysseus/pull/25 (base dev, head
      feat/external-ingest-source-event-p1). Not merged autonomously —
      merging to dev is left as an operator action."
    - "V1 independent adversarial review (Codex CLI, cross-provider per
      the programme's Claude-producer -> Codex-verifier convention):
      `codex exec` given the full diff + task contract + acceptance tests
      (not the producer's self-justification), asked to falsify
      completion. Found 2 CONFIRMED defects and 2 PLAUSIBLE concerns —
      this is exactly the value V1 review is for; V0 (pytest passing)
      alone had missed a real production bug. CONFIRMED #1 (severity:
      high): scripts/update_database.py's add_source_events_table() early-
      returns when a source_events table already exists (true for every
      real deployment of this repo, which already has one from an
      unrelated prior workstream) — so it NEVER adds the new P1 columns
      via that migration path; record_source_event() would crash with
      'no column named payload_ref' on a real existing DB migrated only
      via scripts/update_database.py. CONFIRMED #2: no size cap on
      caller-supplied metadata -> payload_ref, so the module's own stated
      small-pointer-only invariant is unenforced. PLAUSIBLE: revision
      history keeps only one prior hash (not a full multi-revision
      chain) — within the original task spec's looser wording, judgment
      call; source/external_id stripped for validation but stored
      un-stripped, so whitespace-padded variants could create separate
      rows. Full review saved at
      scratchpad/codex_review_p1_output.md this session (not committed to
      the repo — a working artifact, not a durable record; this
      programme-state entry is the durable summary)."
  commits:
    - a7cf330561607693ab093545354af476e6214d2d
  remaining_risks:
    - "PR #25 not yet merged, and now has a known confirmed migration bug
      pending fix (see V1 review evidence above) — do NOT merge PR #25
      until the fix-it dispatch below lands and is itself independently
      verified. P2 should not assume the SourceEvent contract is
      production-safe until this closes. If P2 work needs
      src/source_events.py, branch from feat/external-ingest-source-
      event-p1 (already the case), not from dev."
    - "isolation:remote reliability gap (see P1 evidence above) applies to
      every future implementation-lane dispatch in this programme until
      the underlying Claude Code product behaviour is confirmed fixed;
      logged as product feedback separately from this programme."
  human_action: >-
    Review and merge PR #25 once CI is green (checking now). Not
    blocking P2 review, but P2's own PR is deliberately held until #25
    merges (see P2 entry) to avoid a noisy diff.
  next_action: >-
    DISCOVERED: isolation:remote (both the original P1 dispatch and a
    second fix-it attempt) does not run in a genuinely separate
    environment — every attempt landed on this same laptop; the second
    attempt correctly noticed and declined to proceed rather than
    silently violate the operator's no-local-checkout constraint, then
    surfaced it rather than guessing. Escalation trigger: worker_failed
    (environment isolation unavailable). Response: the two CONFIRMED
    defects were fixed directly by the foreman instead (no local
    checkout — files read/written via the GitHub Contents API into an
    out-of-repo scratchpad) since Codex had already localized both
    defects exactly, making this a small, well-specified, low-risk edit;
    verification now runs on GitHub Actions' own runners (genuinely
    remote, already-existing infra) rather than any local/agent
    execution — `pytest -q` triggers automatically on push via this
    repo's existing `pull_request` CI trigger. Also fixed while in
    there (cheap, in scope): source/external_id now stripped before
    storage, not just validation. PR #25 description updated to satisfy
    this repo's required PR template. Unrelated CI failures seen on the
    first push were investigated, not fixed (out of scope): `gitleaks`
    fails on a pre-existing finding in evals/local_models/results/**
    from an unrelated 2026-08-22 commit (it scans full history
    regardless of this diff). Currently watching CI (pytest job
    specifically) for a real pass/fail before treating this phase as
    merge-ready. Once green: a Codex adversarial pass scoped to the
    incremental fix is deferred — Codex CLI usage resets ~04:45;
    conserving remaining quota until then rather than spending it now
    that CI itself is doing V0 verification.
  last_verified_commit: 3a87800

- id: P2-instagram-export-importer
  outcome: >-
    a real/representative Meta Download Your Information export
    reconstructs Saved-item inventory sufficiently for selected collection
    routing
  status: active
  depends_on: [P1-source-event-adapter-contract]
  acceptance_tests:
    - schema-fixture tests only, no live scraping
    - collection membership, stable identifiers/pointers, timestamps,
      declarative domain mapping, idempotency, visible schema-drift
      failure
  evidence:
    - "P1 accepted this checkpoint (commit a7cf3305, PR #25) — P2 is now
      the immediately-unblocked next task per the contract's
      materialise-only-current-plus-unblocked-next rule."
    - "Smallest safe P2 slice does not need a real Meta export or
      operator credentials: a synthetic, schema-representative fixture
      (built from Meta's publicly documented DYI JSON export shape, not
      real personal data) is sufficient to prove the schema-fixture
      acceptance tests. Real/actual personal export files remain a
      separate future batched human action only if/when the synthetic
      fixture proves insufficient."
    - "Task packet dispatched this checkpoint to a Claude implementation
      lane, branched from feat/external-ingest-source-event-p1 (not dev,
      since PR #25 is unmerged — see P1 remaining_risks) as
      feat/external-ingest-instagram-importer-p2, calling
      src/source_events.py.record_source_event() per saved item, with a
      synthetic tests/fixtures/instagram_saved_posts_sample.json and
      schema-drift/idempotency/collection-mapping tests."
  commits:
    - dda3151fefcba653aa0498ab7233a187529db81f
  remaining_risks:
    - "Synthetic fixture is representative-by-documentation, not a real
      export — P7 (real-data calibration) is the phase that validates
      against actual captured material; do not treat P2's synthetic-
      fixture pass as proof the real Meta export format matches exactly."
    - "Branched from feat/external-ingest-source-event-p1 at commit
      a7cf3305 — BEFORE P1's Codex-review fixes (payload_ref size cap,
      source/external_id normalization) landed on that branch. P2's own
      usage (small structured metadata, permalink-shaped external_ids)
      is very unlikely to hit either fix's new behaviour, but P2's PR
      should not be opened yet: its diff against dev would currently
      include all of P1's unmerged commits too, which is noisy and
      would make review harder. Same isolation:remote gap applies here
      (worker's own report flagged it: ran in an isolated directory on
      this same laptop, not a genuinely separate host — no local
      checkout was left behind outside the session scratchpad, and
      it's been deleted this checkpoint)."
  human_action: none yet
  next_action: >-
    Independently verified this checkpoint (diff scope confirmed exactly
    the 3 declared files; foreman read src/instagram_importer.py,
    tests/test_instagram_importer.py, and the fixture directly — schema-
    drift handling, idempotency, collection-membership, and domain-
    passthrough logic all look sound and the 8 tests assert real,
    specific things, not placeholders). Holding P2's PR open action
    until PR #25 (P1) merges to dev, then re-pointing/recreating this
    branch's PR against dev so its diff is just P2's own 3 files.
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
