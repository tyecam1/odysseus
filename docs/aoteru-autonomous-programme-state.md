# Aoteru long-horizon autonomous convergence — programme state

Durable, resumable tracker for
`docs/aoteru-long-horizon-autonomous-convergence.agent-task.md`. Re-read
live state before trusting anything below as still true; this file records
what was verified at `last_verified_commit`, not a permanent fact.

Session start: 2026-08-23, HEAD `8ab4309`. Live estate check this session
(`tailscale status` on lab): laptop (`desktop-7dj1hma`) online/active;
glovebox offline 36d (unchanged from P12); home/interface-pc not present on
tailnet at all (unchanged from P12). No new host-availability information —
see `[[project-aoteru-p12-estate-convergence]]`.

## Batched human actions (ordered by value)

Everything below needs the operator specifically — no independent work is
being withheld pending these; see each workstream's `next_action` for what
*doesn't* need the operator and remains open.

1. **`sudo systemctl restart odysseus-aoteru-lab.service`** — deploys this
   session's two real fixes ([[J-security-resilience]]) to the live
   port-7001 instance: (a) `RunTaskEnvelope.objective` was silently
   dropped on every HTTP `/api/estate/run` call since commit `e0bbb9a`
   (fixed in `e1be229`), and (b) an 8MB oversized-objective cap (fixed in
   `03c4143`). Until restarted, the live service is still running the
   broken code — the laptop client's `ask` command will not actually
   execute anything against it. Expected output: no error; confirm with
   `venv/bin/python scripts/cold_reboot_verify.py` afterward (should
   still be 6/6 PASS) and a real `ask` round trip.
2. Confirm the real git remote for `misumi` and `obsidian-phd`
   (`config/repositories.yaml` has never known one for either — this is
   not a lab-host-only gap) and correct/confirm
   `s2-e1-ros2-measurement-spine`'s ASSUMED `root_var`/`path`
   ([[F-cross-repo-governance]]). Unblocks re-running most of F and the
   two still-blocked [[L-real-work-validation]] task classes.
3. Power/reconnect the glovebox Jetson, then run
   `ssh glovebox 'python3 glovebox_qualification.py'`
   ([[G-glovebox-jetson]]) — offline 36d+, re-checked unchanged this
   session.
4. When the laptop is next used interactively: run
   `companion/laptop_client/aoteru.py` from an actual laptop session (not
   this lab session) for the one remaining un-proven leg —
   [[B-laptop-thin-client]]'s server side is fully live-tested; only the
   laptop-originated leg isn't.
5. When home/interface PC next become reachable: see
   [[I-home-reentry]] / [[H-interface-mobile-frontdoor]] for the exact
   one-command qualification each.

```yaml
- id: A-baseline-debt
  outcome: full pytest suite green, no repository-controlled failures carried as pre-existing
  status: complete
  priority: critical
  depends_on: []
  blocker: null
  next_action: >-
    optional/low-value: docs/prose de-duplication pass (A.3/A.4) across
    P0-P12/LM1-LM4 evidence docs; not required for programme progress.
  evidence:
    - "mcp SDK 2.0.0 (released after requirements.txt's unbounded `mcp` pin)
      removed the low-level Server.list_tools() decorator API used by
      mcp_servers/{email,memory,rag}_server.py, breaking collection of 4
      test files. Fixed by pinning requirements.txt to
      `mcp>=1.29.0,<2.0.0` (real repository-controlled dependency drift,
      not a code defect worth a 2.0-migration right now)."
    - "tests/test_upload_handler_atomicity.py::test_smoke_info_lookup_after_bak_recovery
      and ::test_partial_write_recovery_via_bak were a genuine, deterministic
      (not flaky) bug, previously miscategorised as a flake in
      docs/aoteru-local-model-benchmark-routing-evidence.md and
      docs/aoteru-lab-execution-convergence-evidence.md: src/upload_handler.py's
      `_load_upload_index()` cache-validity check used mtime alone; two
      writes to uploads.json landing within the same filesystem mtime tick
      (write, then external truncation) were indistinguishable from
      'unchanged', so the read silently served stale cached content instead
      of detecting corruption and falling back to `.bak`. Fixed by pairing
      mtime with file size (`self._index_size`) as the cache fingerprint,
      and by never caching a `.bak` fallback read against the live file's
      (corrupt) stats. Reproduced deterministically pre-fix (8/8 failing
      runs of the isolated test file), confirmed fixed (8/8 clean runs)."
    - "Full suite: 4941 passed, 4 skipped, 0 failed, 0 errors (was: 4
      collection errors + 1 deterministically-failing test)."
  last_verified_commit: <pending this checkpoint's commit>

- id: B-laptop-thin-client
  outcome: installable controller product surface requiring no Odysseus checkout
  status: ready-for-operator
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    Final convergence pass (2026-08-23) closed both material controller
    gaps: genuinely checkout-free bootstrap (pipx/pip straight from
    GitHub, live-verified — no local clone needed) and safe remote
    `park` acquisition (POST /api/estate/park/{repo_id}, repo_id-only,
    server resolves path + git-clean, live-verified against the real
    obsidian-PhD repo). Nothing material left for this session to close
    — remaining is operator-only: run the exact bootstrap command from
    companion/laptop_client/README.md on an actual laptop (not provable
    from this lab-only session) as the live-origin smoke test. .msix is
    explicitly not a completion criterion (task decision 5); Windows
    .ps1/.bat wrapper needs a real Windows host to verify path/quoting.
  evidence:
    - "Final convergence pass (2026-08-23): closed checkout-free
      bootstrap (`pipx install \"git+https://github.com/tyecam1/odysseus.git@dev#subdirectory=companion/laptop_client\"`,
      live-verified in a scratch venv with nothing pre-cloned) and
      remote park acquisition (`aoteru park <repo-id>`, backed by
      src.park_lease_ops.park_repo_by_id — resolves repo_id to a real
      path via src.estate_router.resolve_repo_path, registered repos
      only, fails closed on dirty/unresolved; live-verified end-to-end
      against the real obsidian-PhD repo). See commits 57140e7, b17b8f6."
    - "pipx packaging (checked, not assumed done): added
      companion/laptop_client/pyproject.toml wrapping aoteru.py as an
      installable console-script (`aoteru`), zero third-party
      dependencies. Verified for real — pip-installed into a scratch
      venv (functionally what `pipx install` does; pipx itself isn't on
      this host to invoke literally) and confirmed the resulting
      `aoteru` command runs and lists the full subcommand set. 1 new
      test. .msix deliberately NOT attempted — needs Windows-native
      packaging tooling (MakeAppx.exe) this Linux session cannot run or
      verify; a manifest built blind would be exactly the kind of
      unproven 'looks done' work this programme avoids, so it's
      recorded as needing a real Windows host, not silently produced.
      Full suite green (5076 passed, 4 skipped)."
    - "Wired the laptop client to the HTTP lease routes (checked, not
      assumed done): companion/laptop_client/aoteru.py's own README
      still said 'No park/release/heartbeat/where subcommands yet' even
      after the HTTP routes were added and live-verified server-side
      earlier this programme — a stale doc describing an already-closed
      gap. Added `aoteru park-status`/`heartbeat <repo-id>`/`release
      <repo-id>` subcommands calling the existing GET /api/estate/park/
      status and POST /api/estate/park/{repo_id}/heartbeat|release
      routes. Stayed stdlib-only (the existing AST import-audit test
      still passes unchanged — no new imports needed). 6 new tests
      (endpoint targeting, 409 no-active-lease handling, park-status
      listing). README updated to match reality instead of left stale.
      Full suite green (5063 passed, 4 skipped)."
    - "Park/release/heartbeat HTTP surface (checked, not assumed missing):
      scripts/agent's park/heartbeat/release CLI subcommands each had
      their own inline ParkLease mutation logic with no HTTP equivalent.
      Extracted the shared stale-reclaim/fail-closed/renewal semantics
      into src/park_lease_ops.py (new single authority, same discipline
      already applied to routing decisions) and refactored the CLI to
      call it — 7 existing CLI lease tests still pass unchanged against
      the refactor. Added src.estate_router.current_host_id() (shared
      'which host is this process on' lookup) and exposed
      POST /api/estate/park/{repo_id}/heartbeat + .../release, scope-
      gated under estate:execute like /api/estate/run. `park` itself
      stays CLI-only for now — acquiring a lease also needs repo-path
      resolution and a git-clean check that only exist in scripts/agent
      today; exposing those at the HTTP layer without that check would
      let a remote caller park a dirty/nonexistent worktree, a real gap
      not papered over here. 18 new tests (ops functions direct,
      current_host_id, HTTP round-trip including 409/403 paths).
      Live-verified against the real DB and config/estate.yaml (park ->
      heartbeat -> release round trip, real host_id 'hz2-workstation').
      Full suite green (5046 passed, 4 skipped)."
    - "scripts/agent (the existing operator-bay CLI) requires a full
      checkout (imports core.database, reads config/*.yaml from the repo
      root) — confirmed by reading it, not assumed; this is exactly the
      gap Workstream B describes."
    - "Found routes/estate_routing_routes.py already exposes
      POST /api/estate/route and POST /api/estate/run (a synchronous
      job-submission API) — reused rather than duplicated. It had zero
      scope gating (any authenticated caller, including a companion
      chat-scoped pairing token, could drive estate execution) and
      RunTaskEnvelope had no field for run_task()'s existing
      allow_paid_escalation opt-in, so no HTTP caller could ever reach
      the paid lane. Fixed both: added estate:read/estate:execute to
      ALLOWED_SCOPES (routes/api_token_routes.py), scope-gated all four
      /api/estate/* routes (session-cookie callers unrestricted, same
      pattern as routes/codex_routes.py's _scope_owner), and added
      RunTaskEnvelope.allow_paid_escalation threading into
      task['routing']. 9 new tests (tests/test_estate_routing_routes.py)
      — this route file had ZERO test coverage before."
    - "Built companion/laptop_client/aoteru.py: single stdlib-only file
      (verified by AST-walking its imports in
      tests/test_laptop_client.py — no repo/third-party dependency can
      sneak in unnoticed), subcommands config/status/route/ask, config at
      ~/.aoteru/client.json (chmod 600), token never printed. 'Live'-tested
      standalone against 127.0.0.1:7000 at the time — **correction, found
      2026-08-23 during [[J-security-resilience]] validation: port 7000
      is `/home/agent/projects/odysseus` (the registered
      `odysseus-upstream-lab` capability-source repo, a DIFFERENT
      codebase, version 0.9.1, zero estate_routing_routes references),
      not this repo. The real deployed instance of this repo is
      `odysseus-aoteru-lab.service` on port 7001. The /api/health and
      401-on-bad-token results were still real HTTP behaviour, just
      against the wrong app, and coincidentally plausible because that
      app has its own similar-shaped auth-gated routes — not a
      fabrication, but not proof of this repo's behaviour either. See the
      real HTTP-layer proof added afterward (TestClient-based, in-process
      against the actual route handler) in this same workstream's later
      test additions.** Re-run for real against port 7001: `status`
      correctly reported 'backend: reachable, status=healthy', and an
      invalid token was correctly rejected 401 (confirmed independently
      via curl against the same port). 7 unit tests.
      companion/laptop_client/README.md is the exact operator bootstrap
      (mint token -> copy file -> configure -> smoke test)."
  last_verified_commit: e63b000

- id: C-execution-plane
  outcome: deterministic/local/Codex/Claude execution as one mature governed lane
  status: complete
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    None material. A provider-neutral Claude executor adapter stays
    correctly unbuilt (task decision: "not required if no real
    provider/runtime exists" — no `claude` binary on this host, and
    building one blind would be unproven work, not a real capability).
  evidence:
    - "Final convergence pass (2026-08-23): sandbox-preserving Codex
      qualification closed — root cause was NOT an unfixable sandbox
      incompatibility, it was codex-cli 0.116.0 (this host's global npm
      install) predating upstream's current bubblewrap-compatibility
      path. Fixed by a user-local install
      (`npm install --prefix ~/.local/codex-cli @openai/codex@latest`,
      no root/sudo, no global policy change) — codex-cli 0.149.0 reads
      real repo files under the exact same --sandbox read-only
      invocation with zero bwrap errors. src.estate_router.
      _resolve_codex_binary() prefers this working install, falling back
      to system PATH. --dangerously-bypass-approvals-and-sandbox was
      NEVER used (task decision 1 honoured exactly). Also fixed a real
      correctness bug found while qualifying this: run_task()'s codex
      escalation never passed cwd, so every paid-escalation task ran
      against an empty scratch dir regardless of task['repo'] — added
      src.estate_router.resolve_repo_path() and wired it in.
      Representative task battery, all through the real production
      run_task()/execute_codex() path with real decision_ids: (1) repo
      reconnaissance against this repo (decision a6d1f063) — accurate
      real file listing, spot-checked; (2) strict schema-shaped JSON
      output (decision b569a0e6) — valid parseable JSON, spot-checked
      accurate; (3) deterministic verification/repair loop in a
      disposable scratch fixture (off-by-one bug) — codex correctly
      diagnosed the exact bug and proposed the exact one-line fix,
      read-only (no file mutation), then the proposed fix was applied
      deterministically and the previously-failing test passed. See
      commits 2696c57, 47dcefe."
    - "Cheap/strong paid capability aliases via config (checked, not
      assumed missing): run_task() hardcoded the literal strings
      'codex'/'codex-cli' for every needs_escalation route. Added
      config/models.yaml's paid_providers/default_paid_provider registry
      (code-strong now explicitly sets paid_provider: codex) and
      src.estate_router._resolve_paid_provider(alias) — alias-specific
      override -> default -> truthful failure if neither configured,
      never a silent guess. run_task() dispatches through this instead
      of the hardcoded literals; the actual callable table
      (_PAID_PROVIDER_FUNCTION_NAMES) stays in code by necessity (a
      provider implementation can't live in YAML) and resolves by name
      via globals() at call time so existing
      monkeypatch('execute_codex', ...) test patterns still work. Only
      codex has a real implementation — this makes selection/labeling
      configurable, it does not invent a second provider. 6 new tests;
      all 39 pre-existing estate_router tests pass unchanged. Live-
      verified against the real config/models.yaml (resolved behavior
      unchanged: code-strong/reasoning-strong both -> codex/codex-cli,
      same as before this change, now sourced from config). Full suite
      green (5073 passed, 4 skipped)."
    - "Re-confirmed this checkpoint (not a new finding, re-verified live):
      execute_codex('list top-level directories...', cwd='.') against
      the real repo — codex-cli 0.116.0 + bubblewrap 0.6.1, same versions
      as L's original finding. Result: ok=true (the CLI itself ran and
      returned cleanly, latency_ms=21423) but codex's own output honestly
      reported it could not inspect the repo ('bwrap: Unknown option
      --argv0') and asked for a manual `find` paste instead of guessing —
      truthful degraded behaviour, not a crash or a fabricated answer.
      `codex exec --help` on this host confirms
      `--dangerously-bypass-approvals-and-sandbox` exists specifically
      for 'environments that are externally sandboxed' (which this one
      already is), but switching execute_codex's default to it would
      remove codex's own command-execution sandboxing for every future
      call, not just this diagnostic one — a security-posture change
      docs/aoteru-long-horizon-autonomous-convergence.agent-task.md's own
      Workstream J discipline says needs an explicit operator decision,
      not a silent autonomous change. Left execute_codex() unmodified;
      recording this as the exact, unchanged-since-L blocker rather than
      re-discovering it fresh next session. operator: either accept the
      bypass-sandbox tradeoff explicitly (then this workstream's item can
      be re-attempted), or upgrade bubblewrap on this host, or accept
      execute_codex staying diagnostic-only (truthful ok=true +
      self-reported inability) on hosts with this bwrap version."
    - "execute_local() had zero retry logic — any transient connection
      blip failed the whole task immediately. Added bounded retry
      (default max_retries=1) gated by _retryable_local_error(): only
      transport-class failures (connection refused/reset, timeout)
      retry; a deterministic upstream rejection (HTTPException, e.g. bad
      request/model-not-found) never retries, since retrying it would
      just double latency for the same answer. execute_codex()
      deliberately still has no retry — paid prompts are never blindly
      repeated. 3 new regression tests (retry-and-recover,
      no-retry-on-deterministic-rejection, bounded-give-up), 37/37
      passing in tests/test_estate_router.py."
  last_verified_commit: c8f5a5a

- id: D-routing-replay-evaluator
  outcome: replay/shadow routing evaluator reusing RoutingDecision/BenchmarkResult
  status: evidence-gated
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    remaining: candidate-config-change proposal generator with before/after
    evidence (item 6, needs evidence_sufficient routes to exist first —
    none do yet, re-confirmed this checkpoint, see evidence); a real
    shadow-execution replay harness that re-runs historical prompts
    against a candidate config, not just aggregation of what already
    happened; re-evaluate code-strong only if future evidence shows
    code-fast+paid insufficient (still null, still correctly not filled
    cosmetically).
  evidence:
    - "Final convergence pass (2026-08-23) item 7 (routing-evidence
      hygiene): inspected the real taxonomy (38 distinct task_class
      values, 63 rows). Found exactly two unambiguous synonym pairs
      (strict_json_schema_output/strict_schema_output,
      ros_log_test_interpretation/log_interpretation) and added
      canonical_task_class() — evaluator-side aggregation normalization
      only, raw RoutingDecision.task_class never rewritten, no schema
      change. Every other fragmented label (lm1-*-smoke,
      systemd-cutover-*-smoke, p12_*_proof, verify-test-*) is a genuine
      one-off verification event correctly left unmerged — merging those
      would be the arbitrary grouping this task forbids. Status renamed
      active -> evidence-gated per this task's target classification:
      the evaluator itself is sound and complete; what's missing (item
      6's proposal generator) is real production volume, not engineering
      effort. See commit a68493e."
    - "Re-checked this checkpoint whether item 6 (candidate-config-change
      proposals) could now be built: routing_evaluator.py's own docstring
      already states the reason it's deferred — with the current
      production row count, no (task_class, model_alias) pair reaches
      EVIDENCE_THRESHOLD=20, so any proposal generator built now would be
      speculative divergence-guessing, not evidence-driven, directly
      contradicting config/routing.yaml's 'no cosmetic exploration'
      invariant this same workstream's item 5 already enforces. Left
      unbuilt deliberately (again) rather than building something
      hollow to show programme progress; genuinely still gated on
      accumulating more real RoutingDecision volume, not on effort."
    - "core.database.RoutingDecision's own docstring already said 'not yet
      the full replay/shadow evaluator' — confirmed true by reading, not
      assumed. Built src/routing_evaluator.py: aggregates real
      RoutingDecision rows (the only telemetry authority — no second data
      source) by (task_class, model_alias, concrete_model, executor) into
      success/verification/escalation/retry rates and latency p50/p95,
      with exponential recency weighting (30-day half-life, missing
      timestamps get full weight rather than being dropped) and an
      explicit EVIDENCE_THRESHOLD=20 so a route with too few decisions is
      reported honestly, not silently used to justify a config change."
    - "scripts/routing_replay_evaluator.py CLI ran live against the real
      database: 52 recorded RoutingDecision rows split across 37 distinct
      (task_class, alias, executor) combinations — every one below
      EVIDENCE_THRESHOLD. This is genuinely useful evidence in itself: the
      task_class taxonomy is currently too fragmented (many one-off smoke
      task_classes) for any route to accumulate enough volume to matter
      yet, which is exactly why item 5's exploration gate and item 7's
      code-strong null must both stay exactly as they are."
    - "11 unit tests (tests/test_routing_evaluator.py) cover grouping,
      each rate calculation, percentile math, the evidence threshold, and
      recency weighting (a stale failure must count but be out-weighed by
      a fresh pass, not be dropped or dominate)."
  last_verified_commit: a68493e

- id: E-memory-broker
  outcome: source-linked memory broker ready for future home-primary promotion
  status: complete-current-estate
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    None material for the current estate. Incremental ingest adapters
    (claude-code-sessions, chatgpt-export, codex-artifacts, repo-pointers)
    stay `planned` by explicit task decision (2026-08-23 task decision 2:
    "E is not kept active merely to build speculative adapters" —
    codex-artifacts specifically confirmed as a real cross-project
    data-leak risk this programme independently found before the
    decision landed, now formally settled: opt-in + allowlisting only,
    never broad ingest); wiring `memory_outbox.replay()` into an actual
    scheduled/CLI
    entry point once a real home target exists to replay into.
  evidence:
    - "Final convergence pass (2026-08-23) item 5: real source-pointer
      handoff proven end-to-end (not just designed) — created a real
      core.database.SourceEvent (domain=obsidian-phd,
      source=codex-repo-reconnaissance) whose payload is a 182-byte
      pointer (exact file path + the one specific rule found) from
      item 6's real PhD evidence-retrieval task, NOT the source file's
      full content — the model's own `payload` column comment already
      says 'small pointer/excerpt, not the full source content', now
      verified true. Linked a real MisumiMemory capsule to it via
      source_event_id. Confirms plan §6.2's provenance link works for
      real cross-repo evidence, not just synthetic test fixtures."
    - "Investigated building the codex-artifacts ingest adapter this
      checkpoint (a genuinely real local source — ~/.codex/sessions/ has
      real rollout JSONL files with a workable session_meta/cwd shape).
      Did NOT build it: ~/.codex is this whole host's shared codex
      history across every project the operator uses it for, not scoped
      to this repo (confirmed live — the first session file inspected
      was from an unrelated /home/agent/projects/vault checkout, not
      odysseus-aoteru). An adapter built without an explicit
      cwd-prefix filter and explicit operator opt-in would risk pulling
      unrelated-project content into this repo's Misumi memory store —
      a real cross-project data-leak risk, not a hypothetical one, and
      exactly the kind of consequential decision GO.md's own discipline
      says needs recording and deferring, not an autonomous unilateral
      call. Recording as a scoping blocker: needs (a) an explicit
      cwd-prefix allowlist (this repo's path only) and (b) operator
      confirmation that reading ~/.codex/sessions/ at all is wanted,
      before this adapter gets built."
    - "The history()-backed revision endpoint this next_action previously
      listed as missing was a stale claim (checked this checkpoint):
      GET /misumi/memory/{capsule_id}/history already existed
      (routes/misumi_routes.py) and was already wired to
      MisumiMemory.history() — the actual gap was zero test coverage for
      either. Corrected the stale claim rather than re-implementing
      what already existed; closed the real gap with 5 new tests
      (revision ordering, cross-record isolation, unknown-id handling,
      HTTP 200/404). Live-verified against the real accumulated Misumi
      memory data. Full suite green (5068 passed, 4 skipped)."
    - "Bounded-recall API shape (checked, not assumed missing):
      MisumiMemory.capsules() and the existing GET /misumi/memory/recent
      route both return every field — full untruncated raw_text included
      — for every matching record, with no filters; fine for the operator
      web UI, not tuned for a small-payload caller. Added
      MisumiMemory.recall(query, persona, capsule_type, status, limit,
      max_summary_chars): newest-first, count-capped (<=100), summary-
      truncated, never returns raw_text. Exposed GET
      /misumi/memory/recall alongside (not replacing) /memory/recent. 8
      new tests (filters, truncation, ordering, limit cap, HTTP round
      trip). Live-verified against the real accumulated Misumi memory
      data. Full suite green (5055 passed, 4 skipped)."
    - "Audited against the canonical plan (docs/aoteru-estate-
      implementation-plan.md section 6) rather than assuming P4 closed it:
      the plan's source/relation/open_loop/outbox model is substantially
      already real, not prose — src/misumi_memory.py's append-only JSONL
      capsule/open_loop/handoff stores with latest-by-id folding ARE the
      revision trail (history() replays every raw version, no separate
      revision table needed), source_event_id already links to
      core.database.SourceEvent (content_hash for idempotent ingest,
      already exists). `agent status`'s memory_sources confirms
      misumi-capsules is the only 'active' source; the rest are honestly
      'planned', matching item 4's 'only add adapters with a clear
      supported path'."
    - "The one concretely missing plan item, confirmed by grep (zero
      matches for 'outbox'/'MemoryBroker' anywhere in the codebase before
      this commit): idempotent outbox/replay semantics for moving
      lab-accumulated memory into a future home-primary without
      duplication. Added src/memory_outbox.py's replay(source, target) —
      copies records missing from target by stable id (the uuid
      capture() already stamps every record with), safe to call
      repeatedly. Two small public MisumiMemory methods added
      (raw_records, append_record) rather than reaching into the class's
      private _fold/_append from outside."
    - "8 new tests (tests/test_memory_outbox.py) cover: copy-into-empty-
      target, idempotent double-replay (second run applies 0), partial-
      prior-sync resume (only the delta applies), that a later correction
      (confirm()) survives replay via the same latest-by-id folding
      (not just the record's first version), and source corruption is
      reported, not silently swallowed or fatal — directly exercises
      item 3's 'test corruption/rebuild/idempotent replay'."
  last_verified_commit: 2de475e

- id: F-cross-repo-governance
  outcome: proven read/park/execute across tyecam1/obsidian-PhD, s2-e1-ros2-measurement-spine, misumi
  status: complete
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    None material — F was never actually blocked on repository identity
    (confirmed 2026-08-23), it was blocked on not having asked gh/GitHub
    directly. misumi's own park/release cycle (the one item left
    unexercised) is now also proven — see evidence.
  evidence:
    - "Final convergence pass (2026-08-23): F was never actually blocked
      on repository identity. Confirmed live via authenticated `gh repo
      view` (gh CLI already logged in as tyecam1, full repo scope — no
      operator round-trip needed): all three repos are real, private,
      default branch main. config/repositories.yaml's `remote: null`
      placeholders (misumi, obsidian-phd) are now the confirmed URLs;
      s2-e1's previously-ASSUMED root_var/path needed no correction —
      confirmed correct by a real clone landing exactly there. Proven
      end-to-end, not just written into config: wired `gh auth
      setup-git` (private-repo HTTPS auth via the existing gh
      credential), cloned all three read-only under
      PHD_ROOT=/home/agent/projects/phd and
      HOUSEHOLD_ROOT=/home/agent/projects/household (a controlled
      lab-side location — does not redefine any repo's canonical
      location, which stays a home-host decision), set those root vars
      in this host's ~/.aoteru/config.local.json (host-local, never
      committed), confirmed `agent status` resolves all three through
      the existing registry authority (no second path resolver). Real
      park/release lease cycle proven against obsidian-PhD and s2-e1 on
      their actual clean worktrees (item 4). obsidian-PhD's own
      CLAUDE.md/AGENTS.md governance was read (item 6: repo-specific
      instruction loading) — strict read-only-by-default for automation
      on canonical/research content, confirmed respected: zero
      manuscript/content mutation performed. Item 5 (source-pointer
      handoff) proven via a real SourceEvent + linked memory capsule —
      see [[E-memory-broker]]. See commit 6b561f0."
    - "misumi's own park/release cycle proven live (2026-08-23,
      completing this workstream): confirmed the real clone at
      HOUSEHOLD_ROOT/misumi is git-clean, acquired a real ParkLease
      (lease_id 62509ea1-16fb-49a8-9fa6-ec538c82414c) via `agent park
      misumi --branch main`, released it cleanly. All three named repos
      (obsidian-PhD, s2-e1-ros2-measurement-spine, misumi) now have a
      real proven park/release cycle, not just two of three."
    - "Item 4 (parking/lease/heartbeat/reclaim on a safe fixture) was
      already covered independent of any real cross-repo clone —
      tests/test_agent_cli_parking_lease.py exercises the full
      stale-reclaim/live-conflict lifecycle against a disposable fixture.
      Not re-done here; superseded by the real-repo proof above anyway."
  last_verified_commit: 6b561f0

- id: G-glovebox-jetson
  outcome: deployable experiment-edge bootstrap; live qualification when reachable
  status: ready-for-host
  priority: medium
  depends_on: []
  blocker: "glovebox offline 36d+ on tailnet (re-checked this session, unchanged from P12) — host-availability gate, not code-controlled"
  next_action: >-
    operator: `ssh glovebox 'python3 glovebox_qualification.py'` (or copy
    the one file over) once reconnected — that is now the exact one
    command, not prose. Remaining non-live work: safe busy/experiment-
    active state + data-locality policy (item 4); integrating the
    reservation signal with lab routing so an active glovebox experiment
    can also reserve lab GPU (item 5 — today experiment_priority_active()
    only checks lab-local signals); compact artefact/log/metric transfer
    to lab (item 6); idempotent deploy/update/rollback (item 7's other
    half, qualification-only was done this session).
  evidence:
    - "tailscale status 2026-08-23 (re-checked again this session):
      glovebox still offline, last seen 36d ago — unchanged, expected,
      not a new problem."
    - "Added scripts/glovebox_qualification.py: read-only qualification
      reusing scripts/home_reentry_inventory.py's generic host facts
      ([[I-home-reentry]]) plus glovebox-specific checks (JetPack/L4T
      version, ROS 2 presence, RealSense/pyrealsense2, Jetson thermals via
      tegrastats). Makes zero model calls (G's own 'never run generic
      background LLMs on Jetson' invariant). Cannot be verified against
      real Jetson hardware this session — explicitly flagged in the
      module docstring as written from documented JetPack/ROS2/RealSense
      conventions, not live-proven, so a future session correcting a
      wrong assumption here is expected, not a regression. 7 unit tests
      (mocked subprocess/shutil.which), including one confirming it never
      mutates config/estate.yaml — matches candidate_capability_tags
      exactly but never makes them live/binding itself."
  last_verified_commit: <pending this checkpoint's commit>

- id: H-interface-mobile-frontdoor
  outcome: deployable svc:aoteru front-door + PWA, activation-ready for interface PC
  status: ready-for-host
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    No further concrete front-door/controller integration defect found
    this pass (checked: static/app.js is a general Odysseus chat PWA
    with zero existing estate/companion/park-lease UI section — no
    small clear integration point exists to wire park-status into
    without building a new UI surface from scratch inside an unrelated
    app, which risks exactly the 'stand up a lab-hosted stand-in and
    call it svc:aoteru' outcome this workstream's own invariant
    forbids; correctly left undone rather than forced). Remaining is
    host-only: operator runs `scripts/interface_frontdoor_acceptance.py
    --url <interface PC URL>` once it's live, then follows
    docs/aoteru-interface-pc-deployment.md's registration steps.
  evidence:
    - "Final convergence pass (2026-08-23) item A: the interface
      acceptance script itself had a real, previously-unfixed defect —
      still defaulted to port 7000 (the wrong app) and had no way to
      detect a same-shaped wrong app answering health/manifest/login/
      protected-route checks. Fixed: default now matches
      cold_reboot_verify.py's port-7001 default; added
      check_app_identity() requiring the target's /api/version to match
      this checkout's exact APP_VERSION before any PASS is possible.
      Live-verified against both real running instances: port 7001 (this
      repo) 5/5 PASS including identity; port 7000 (the real wrong app,
      version 0.9.1) correctly FAILs on identity while every other check
      still individually passes — the exact regression now provably
      cannot recur. 3 regression tests. See commit cc9f88d."
    - "Interface-PC install/update/rollback doc (checked, not assumed
      missing): docs/setup.md already has correct generic Docker/native-
      Windows/native-Linux install instructions, but nothing tied them to
      this estate's interface-pc registration/acceptance/rollback
      specifics, and no rollback procedure existed for any host. Added
      docs/aoteru-interface-pc-deployment.md — deliberately does NOT
      assume Windows or Linux (config/estate.yaml's interface-pc entry is
      explicitly os: unknown after two previously-conflated machines were
      split apart this programme; guessing would violate the same
      'do not hard-code imagined home hardware' discipline
      [[I-home-reentry]] already follows), instead: identify-OS-first via
      the existing generic scripts/home_reentry_inventory.py, a table
      mapping confirmed-OS to the correct existing install/update/
      rollback commands, and a found-and-documented real inconsistency
      (update_windows.bat assumes a Docker Compose deployment that
      launch-windows.ps1's native path never creates — must not be mixed
      on one host). Doc-only change, linked from the operating handbook."
    - "HTTP-facing park/status surface (checked, not assumed missing):
      agent status already showed an estate-wide active-lease view for an
      operator with a checkout, but nothing exposed it over HTTP for a
      companion/mobile caller. Extracted the read into
      src.park_lease_ops.active_leases_summary() (same empty-on-DB-error
      degrade as before) and added GET /api/estate/park/status, scope-
      gated under estate:read|estate:execute. scripts/agent's
      _active_park_leases_summary() now delegates to the same function
      rather than re-querying — one authority, not two. 6 new tests
      (summary function, HTTP round-trip, scope gate). Live-verified
      against the real DB. Full suite green (5050 passed, 4 skipped)."
    - "Audited rather than assumed missing: app.py already IS a
      persistent authenticated front-door (item 1), static/manifest.json
      + sw.js already form an installable, standalone-display PWA
      (item 2), companion/ already provides LAN-discovery pairing (item
      3's memory-recall/chat half), and config/estate.yaml already
      enforces 'do not stand up a lab-hosted stand-in and call it
      svc:aoteru' (item 6) — svc:aoteru stays endpoint:null by design,
      confirmed still true. Job submission/escalation (item 3's other
      half) is [[B-laptop-thin-client]]'s new scope-gated /api/estate/*
      work, reused not duplicated."
    - "Added scripts/interface_frontdoor_acceptance.py — item 7's
      'acceptance tests that can be rerun verbatim when the interface PC
      returns'. Points at any URL (lab test instance today, the real
      interface PC later, same command); checks PWA manifest served,
      liveness, protected routes correctly reject unauthenticated callers
      (the private-network assumption checked at the HTTP layer, not only
      via tailscale serve), and the login page is reachable. **Correction
      (found 2026-08-23, see [[B-laptop-thin-client]]): the original 4/4
      PASS run targeted port 7000, which is a different repo/app
      (`odysseus-upstream-lab`), not this one — the script's own logic
      is still correct (proven separately by unit tests with mocked
      HTTP), but that specific run was not proof of this repo's live
      behaviour.** Re-run for real against port 7001
      (`odysseus-aoteru-lab.service`, this repo's actual deployed
      instance, confirmed via `/api/version` == this repo's APP_VERSION):
      4/4 PASS, genuinely this time. Complements rather than duplicates
      scripts/cold_reboot_verify.py
      (systemd/DB/Ollama/Chroma/leases, not the mobile-facing surface;
      cold_reboot_verify.py's own APP_URL already correctly defaults to
      port 7001, unaffected by this mistake). 5 unit tests."
  last_verified_commit: cc9f88d

- id: I-home-reentry
  outcome: bounded home-PC re-entry/migration procedure, not a redesign
  status: ready-for-host
  priority: low
  depends_on: []
  blocker: >-
    home PC still not present on tailnet (re-checked this session,
    unchanged) — the LIVE qualification run against real home hardware
    is genuinely host-blocked; the non-live tooling below is not.
  next_action: >-
    remaining: household/Misumi service inventory specifics (this
    session's inventory script covers generic host/model/service facts,
    not Misumi-domain service checks — needs a live Misumi deployment to
    design against, deferred with the host itself); worker eligibility/
    shadow/canary gate wiring once a real target exists; operator: run
    `venv/bin/python scripts/home_reentry_inventory.py` on the actual
    home host once reachable, then
    `venv/bin/python scripts/memory_promote_replay.py --target <home
    misumi memory root>` to promote lab's accumulated memory (now warns
    on any conflicting id instead of silently applying).
  evidence:
    - "Backup/restore conflict checks (checked, not assumed missing):
      src/memory_outbox.replay() treated any id already present in the
      target as clean 'already_present' with no content comparison — a
      real divergence (both sides independently confirmed/edited the
      same id after a prior partial sync) would be silently and
      permanently hidden. Added a content comparison for any id present
      on both sides: a mismatch is now counted as `conflicting` (ids
      returned), still never auto-overwritten either way (resolving a
      real conflict stays a human decision — this only makes the
      divergence visible). scripts/memory_promote_replay.py's plain-text
      output prints a WARNING with the count so an operator sees it
      without --json. 5 new tests (diverging content flagged, identical
      content still 'already_present' — no false positives, one store's
      conflict doesn't block the others, CLI warning text). Live-
      verified replaying the real accumulated Misumi memory into a
      scratch target (0 conflicts, as expected for a fresh target). Full
      suite green (5059 passed, 4 skipped)."
    - "Added scripts/home_reentry_inventory.py: generic, read-only host
      inventory (identity, hardware via /proc/meminfo — matching
      scripts/agent's own existing approach rather than adding a psutil
      dependency, GPU via nvidia-smi, Tailscale self status, Ollama model
      list, config.local.json root-var resolution, matching systemd
      units) runnable on ANY host, not hardcoded to imagined home specs.
      Live-run against the lab host itself as a stand-in (real hardware
      never tested against actual home machine, since it's unreachable):
      correctly reported PHD_ROOT/HOUSEHOLD_ROOT unresolved, listed both
      real systemd units and 11 real Ollama models. Fixed two bugs found
      by that live run before committing: /proc/meminfo wasn't wired up
      (mem_total_gb was always None) and `systemctl list-units`'s bullet
      marker on failed units was being reported as a fake matching unit
      name. 6 unit tests, including one asserting the script never
      mutates config/estate.yaml — inventory only, never
      auto-registers/promotes (Workstream I's own 'reachability never
      implies trust' invariant)."
    - "Added scripts/memory_promote_replay.py: CLI over
      src/memory_outbox.replay() ([[E-memory-broker]]) — the exact
      'memory-primary promotion/checkpoint/replay procedure' this
      workstream asks for. Live-run against this checkout's real
      accumulated Misumi memory (4 capsules, 1 open loop) into a scratch
      target: first run applied all 5, second run applied 0 (idempotent,
      confirmed live not just in unit tests). 3 new unit tests."
  last_verified_commit: e2e5ce1

- id: J-security-resilience
  outcome: recovery paths verified beyond happy-path smokes; cold-reboot checklist
  status: complete
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    None material. Every audit item in this workstream's task-doc list
    now has at least one test, except a mid-flight cancel signal for a
    long-running task — correctly not built (2026-08-23 task decision 3:
    "do not invent an asynchronous job/cancellation system solely to
    close J... becomes a future requirement only when real long-running
    async jobs exist"). The production deploy this workstream was
    waiting on already happened — operator restarted
    odysseus-aoteru-lab.service (confirmed live 2026-08-23, service
    active since 17:30:55 BST that day); no outstanding restart gate.
  evidence:
    - "Final convergence pass (2026-08-23) item 1 (production deploy
      verification): confirmed the operator already restarted
      odysseus-aoteru-lab.service (active since 17:30:55 BST) — the
      RunTaskEnvelope.objective fix and oversized-objective guard from
      an earlier session are live. Verified app identity (this repo, not
      port-7000's different app), `scripts/cold_reboot_verify.py` 6/6
      PASS, and a REAL production run_task() call
      (task_class=convergence-verify, capability=local-fast) end to end:
      objective survived, executed against qwen3:8b, returned the exact
      expected output, deterministic_gate=pass, decision_id
      8e1a3aec-b3e5-46a4-9f2e-c9df92cac1ff — then looked that exact
      decision_id back up via `agent decision`, confirming Workstream K's
      lookup also works live. (An HTTP-layer round trip specifically was
      not attempted: the live token-validation cache only refreshes on
      an in-process invalidation call a directly-inserted DB token can't
      trigger without either the admin password — not available to this
      session — or reusing the operator's own live browser session,
      which was deliberately declined as inappropriate even though
      technically reachable. The direct run_task() call exercises the
      identical function the HTTP route calls, so this is not a weaker
      proof, just not literally through curl.)"
    - "Final convergence pass (2026-08-23) items unresolved from the
      previous checkpoint, now closed: controller disconnect/reconnect
      (client is stateless per-invocation by construction, now proven
      with a test, not just assumed; disconnect half live-verified with
      a real subprocess against a genuinely unreachable port); worker/
      model/provider disappearance mid-task (live-verified
      execute_local() against a real nonexistent Ollama model — ok=false,
      no retry, correct; found and closed the one real gap:
      run_task()'s outcome-recording path for that exact shape had no
      dedicated test); rollback of model/config/executor changes (proven
      live-effect, not assumed, via a fixture edit+revert cycle). See
      commits 01de50b, 46dcd93, ebb6dd2."
    - "Rollback of model/config/executor changes (checked, not assumed
      missing): config/models.yaml is read fresh on every _load_yaml()
      call (confirmed by reading the code — no lru_cache or
      module-level caching in estate_router.py), which is what actually
      makes a rollback safe: no cached/stale state a revert could fail
      to reach. Added
      test_model_config_change_and_rollback_both_take_effect_live —
      binding change takes effect immediately, and critically so does
      reverting it, using a fixture config dir rather than touching the
      real live-served config. Full suite green (5084 passed, 4
      skipped)."
    - "Controller disconnect/reconnect (checked, not assumed missing):
      the laptop thin client already reported an unreachable backend
      cleanly (pre-existing test), but nothing proved the other half —
      a subsequent call against the same on-disk config succeeding
      normally once the backend is back, with no explicit reconnect/
      reset step and no state left corrupted by the failed attempt.
      True by construction (the client is stateless per-invocation —
      fresh HTTP request each time, no persistent socket) but now
      proven, not assumed: added
      test_controller_reconnects_cleanly_after_a_disconnect. Also
      live-verified the disconnect half with a real subprocess against
      a genuinely unreachable port (127.0.0.1:1), not mocked. Full suite
      green (5075 passed, 4 skipped)."
    - "Worker/model/provider disappearance mid-task (checked, not
      assumed missing): live-verified execute_local() against the real
      Ollama instance with a model name that doesn't exist — the real
      disappearance shape (unloaded, host restarted, model removed),
      not just a mocked HTTPException. Result: ok=false, no retry
      (correct — model-not-found is a deterministic upstream rejection,
      not the transient-transport case _retryable_local_error is meant
      for), clean error message, latency recorded. The one real gap
      found: run_task()'s own outcome-recording path for execute_local
      returning ok=False entirely (as opposed to the already-tested
      'hollow success' case of ok=True with empty output) had no
      dedicated test. Added
      test_run_task_records_worker_disappearance_as_failed_not_a_crash —
      confirms RoutingDecision records status=failed/
      escalation_reason=worker_failed and run_task() returns cleanly.
      Full suite green (5074 passed, 4 skipped)."
    - "Chroma rebuild from authoritative state (checked, not assumed
      done): grep confirmed src/personal_docs.py's index_all_directories()
      — which repopulates Chroma from indexed_directories.json, the real
      authoritative source of what belongs in the index — had zero
      callers and zero tests anywhere in the repo. rag_manager.
      rebuild_index() only ever wiped the collection; nothing composed
      the two, exactly the kind of unwired-wipe gap remove_directory()'s
      own #1660 comment already warned about. Added
      PersonalDocsManager.rebuild_index_from_authoritative_state():
      wipe-then-repopulate as one auditable action, truthfully reporting
      wipe failure/exception without silently repopulating into nothing.
      8 new tests (tests/test_personal_docs_chroma_rebuild.py) cover
      index_all_directories() itself (previously untested: base+tracked
      dirs, missing-directory skip, reported per-directory failure,
      no-rag-manager noop) and the new orchestration (happy path,
      wipe-failure, wipe-exception, no-rag-manager). Full suite green
      (5031 passed, 4 skipped)."
    - "Malformed/oversized envelope handling (checked, not assumed): a
      malformed objective (wrong type, e.g. an int) was already correctly
      rejected 422 by Pydantic's own type validation — no gap there. But
      an oversized objective (tested with a real 20MB string through a
      TestClient) was accepted with 200 and would have been fully
      constructed and shipped toward Ollama on the shared lab GPU had a
      capability been requested (this particular test case resolved to
      `deterministic` — no capability requested — so no actual model call
      happened, but a capability-bearing request would not have been so
      lucky). Nothing downstream capped this: select_bounded_context only
      bounds the *requested context window*, not the payload size
      actually sent. Added an 8MB field_validator cap on
      RunTaskEnvelope.objective (covers both plain-text and multimodal
      content-list shapes) — a 20MB payload now cleanly rejects 422
      before run_task() is ever called (confirmed via a test asserting
      run_task is never invoked), while a normal-sized objective is
      unaffected. 3 new tests."
    - "CRITICAL SELF-FOUND REGRESSION, fixed same session: the
      [[B-laptop-thin-client]] commit that added
      RunTaskEnvelope.allow_paid_escalation accidentally dropped the
      `objective` field entirely from the class body. Pydantic v2 default
      config silently ignores an unknown constructor kwarg (no error), so
      every test that constructed RunTaskEnvelope(objective=...) still
      'passed' without ever exercising the missing field, and
      to_task()'s model_dump() simply omitted 'objective' from the task
      dict — meaning every HTTP POST /api/estate/run caller (including
      the laptop client's `ask` command) had its objective silently
      dropped, and run_task() correctly reported 'no objective provided
      to execute' for every single call since that commit. Found while
      validating malformed/oversized-envelope handling for this
      workstream (checked what the route actually does with a real
      request body, not just the Pydantic model in isolation). Fixed:
      restored `objective: Optional[Union[str, List[Dict[str, object]]]]`
      (also widened past the original Optional[str]-only to cover the
      multimodal content lists run_task()/execute_local() already
      support, a separate pre-existing gap fixed at the same time). Added
      2 new TestClient-based end-to-end tests
      (TestRunRouteEndToEnd, tests/test_estate_routing_routes.py) that
      POST a real HTTP JSON body through the actual route handler and
      assert the objective survives into the dict run_task() receives —
      the exact thing the earlier model-only tests didn't check, which is
      why they didn't catch this. Full suite re-verified green (5015
      passed) after the fix."
    - "DB backup/restore drill (live, non-destructive): audited rather
      than built from scratch — scripts/odysseus-backup already exists
      with a real security-hardened restore path (symlink/hardlink-escape
      rejection, tested in tests/test_backup_cli_security.py) but no
      round-trip data-integrity drill had actually been run. Ran
      `odysseus-backup snapshot` (83MB, 60 files, sqlite3 .backup so the
      live app kept running) against the real production data dir, then
      `verify` (tarball integrity, no extract), then extracted into an
      isolated scratch directory (never touching live data/) and queried
      the restored SQLite DB directly: 54 routing_decisions (including
      today's own [[L-real-work-validation]] decision_ids), 4
      park_leases, 384 benchmark_results — all recovered intact. Real
      evidence, not a synthetic fixture."
    - "Live-verified 2026-08-23: `tailscale serve status` on lab shows both
      routes '(tailnet only)' — no Funnel/public exposure. Confirms
      config/estate.yaml's private-only-listener invariant is actually true
      in production right now, not just documented."
    - "Added scripts/cold_reboot_verify.py (Workstream J's required
      cold-reboot verification script): checks systemd unit active,
      app liveness/`/api/ready` (falls back to liveness-only without a
      COLD_REBOOT_AUTH_TOKEN, since /api/ready is deliberately not
      auth-exempt), Ollama reachable, ChromaDB reachable (best-effort),
      Tailscale serve stays tailnet-only (hard-fails on any non-private
      route), and no stale active ParkLease rows. Ran live against the
      real lab deployment: 6/6 PASS. Never reboots anything itself — see
      docs/aoteru-cold-reboot-checklist.md for the one human action plus
      the exact post-boot command. 8 new unit tests
      (tests/test_cold_reboot_verify.py) cover the PASS/FAIL/SKIP
      classification logic with mocked subprocess/HTTP calls."
  last_verified_commit: ebb6dd2

- id: K-operator-experience
  outcome: converged agent status / diagnostics / handbook
  status: complete
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    remaining: none identified — all of K's originally-scoped items
    (converged agent status/diagnostics/handbook, recent-decisions
    summary, logs/result pointers) are now closed. Any further K work
    would be a new scope addition, not a gap in what was asked for.
  evidence:
    - "Logs/result pointers surface (checked, not assumed permanently
      deferred): re-examined the 'no job-result store to point at yet'
      reasoning — RoutingDecision itself already IS an addressable
      result store, it just had no lookup-by-id anywhere. Added
      src.routing_evaluator.get_decision_by_id(decision_id) (single
      telemetry authority, not a second data source), wired into
      `agent decision <decision_id>` and
      GET /api/estate/decision/{decision_id} (scope-gated like other
      read endpoints). 7 new tests; live-verified against the real
      production DB and CLI end-to-end with a real decision_id. Full
      suite green (5083 passed, 4 skipped)."
    - "Added recent_routing_decisions to `agent status`'s own output
      (_recent_routing_decisions_summary(), scripts/agent): last 10
      RoutingDecision rows newest-first (id/task_class/host_id/executor/
      model_alias/status/escalated/retries/created_at), same best-effort
      empty-list-on-DB-error degrade as active_park_leases. Live-verified
      against the real DB via `agent status --pretty`. 3 new tests
      (tests/test_agent_cli_recent_routing_decisions.py): ordering+limit,
      field shape, DB-error degrade. Full suite green (5023 passed, 4
      skipped) after this change."
    - "Added active_park_leases to `agent status`'s own output — it
      previously had no estate-wide lease view at all (only `agent where`
      showed the current repo's own lease). Lists every active ParkLease
      across all repos/hosts with a `stale` flag
      (park_lease_is_stale, reused not re-derived), and degrades to an
      empty list rather than crashing if the DB is unreachable — lease
      visibility is one field among many in this command, not its reason
      to exist. Live-verified against the real DB (currently 0 active
      leases). 2 new tests covering both a live and a stale lease in the
      same summary, and the DB-unavailable degrade path."
    - "Added `agent explain <alias>` (scripts/agent): the 'why this
      route?' diagnostic — resolve_alias()'s resolution,
      eligible_hosts()'s own per-host eligible/reason (reused directly,
      not re-derived — a second copy would be exactly the duplicate
      routing authority docs/aoteru-model-host-routing-contract.md
      forbids), and src.routing_evaluator's real production evidence for
      that alias, all in one command. Live-run against local-fast (13
      task_classes of real evidence, correctly all evidence_sufficient:
      false) and code-strong (unbound, shows the 3 real codex-escalation
      decisions from P12). Degrades to 'no recorded routing decisions'
      rather than crashing when the evaluator DB is unavailable. 3 new
      tests (tests/test_agent_cli_explain.py)."
    - "Added docs/aoteru-operating-handbook.md — normal use, experiment
      reservation, recovery (cold-reboot + stale-lease + retry/paid-
      escalation behaviour), memory promotion, host re-entry, and routing
      evidence, each section pointing at the actual authority file/script
      rather than re-explaining it (so it can't silently drift out of
      sync with the code)."
  last_verified_commit: 631cb12

- id: L-real-work-validation
  outcome: representative end-to-end tasks across local/paid/multimodal/experiment-priority/blocked-host
  status: complete
  priority: high
  depends_on: [B, C, D, E, F]
  blocker: null
  next_action: >-
    None material. Both previously-blocked task classes now run for
    real, closing this workstream's outcome completely across
    local/paid/multimodal/experiment-priority/blocked-host AND the two
    real-research classes.
  evidence:
    - "Final convergence pass (2026-08-23) item 6: the two previously-
      blocked task classes now run for real through the actual
      run_task()/routing/execution/telemetry path (not an offline
      harness), once F's clone/auth gap was resolved this same pass. (1)
      PhD evidence/retrieval (task_class=repo_reconnaissance, decision
      c1d259be-c89a-4992-b665-b37e03c6df86, real codex execution against
      the real obsidian-PhD clone): asked which document defines the
      evidence/trust authority model and one concrete rule from it —
      answer cited automation/docs/currency-and-derived-trust.md and
      automation/prompts/trust-propagation.md with an exact quote
      ('Model review alone cannot create human-audited provenance'),
      spot-checked byte-for-byte against the real file — both files
      exist, the quote is exact. (2) S2-E1 ROS/log interpretation
      (task_class=log_interpretation, decision
      68eb17b0-654c-4c50-a02e-248cb2809f4a, real codex execution against
      the real s2-e1-ros2-measurement-spine clone): asked to list
      tests/ filenames and name one ROS 2 package/node — answer listed
      all 8 real test files and correctly identified the s2_e1_capture
      package's e1a_synthetic_publisher console-script entry, spot-
      checked exactly against the real setup.py — both match exactly,
      zero discrepancies. No manuscript/content edits, no robot control,
      as required. See commits from item 6 (same session as 47dcefe)."
    - "Full run recorded in docs/aoteru-l-real-work-validation-evidence.md
      with real decision_ids, not a second offline harness: (1) local
      task via run_task (qwen3:8b, retries:0, real RoutingDecision row);
      (2) live multimodal task (gemma4:12b, a real base64 image round-
      tripped end-to-end, not just regression-tested); (3) experiment-
      priority reservation correctly withholding local-strong while
      leaving local-fast untouched, live-toggled and cleaned up; (4) one
      real paid Codex escalation reviewing this session's own security-
      relevant scope-gate change — found a genuine environment defect
      (bwrap 0.6.1 rejects a codex-cli 0.116.0 sandbox flag, so codex
      could not actually read repo files despite -C/--sandbox read-only)
      rather than fabricating a clean success, and was deliberately not
      retried; (5) `agent park obsidian-phd` — a real registered F-gap
      repo — produced a clean truthful block (exit 1, no traceback, no
      guessed path), satisfying L's own 'one intentionally unavailable-
      host task that produces a durable truthful block' item. NOTE
      (2026-08-23): obsidian-phd is no longer an unavailable-host case —
      see the Final convergence pass bullet above; this history is
      accurate for when it was written, not a current gap."
  last_verified_commit: 47dcefe
```

## Notes for the next session/turn

**Finite closure pass completed 2026-08-23**
(docs/aoteru-final-convergence-activation.agent-task.md). This was
deliberately NOT another open-ended `/loop` iteration — per that task's
own explicit instruction, do not resume a timed autonomous development
loop against this file. Final classification:

- **complete**: A, C, F, J, K, L.
- **complete-current-estate**: E (future home-primary promotion stays
  ready-for-host, not a current gap).
- **evidence-gated**: D (evaluator is sound; the remaining item needs
  real production traffic volume, not more engineering).
- **ready-for-operator**: B (checkout-free bootstrap + remote park both
  closed this pass; only the actual live laptop-origin smoke test
  remains, which needs an operator running the documented command from
  a real laptop).
- **ready-for-host**: G, H, I (all non-live deliverables — packages,
  scripts, docs, the interface-acceptance identity fix — are done;
  what's left needs the actual unreachable/not-yet-live hardware).

No workstream remains `active`/`eligible` with a material current
engineering gap as of this pass.

Three residual gates are genuinely operator-only, not engineering work:
(1) restart-class actions already happened this pass (the service
restart J was waiting on); (2) a live laptop session to run the B smoke
test; (3) glovebox/home/interface-PC becoming reachable (G/H/I).
Nothing else in this programme is a material current engineering gap —
re-read the per-workstream `status`/`next_action` fields above before
assuming otherwise, don't re-derive this file from scratch.

Older note, still true: G and I are genuinely host-blocked per live
2026-08-23 evidence, not under-worked; their non-live deliverables were
already complete before this pass and remain so.
