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
  status: active
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    remaining: operator-run live smoke test from an actual laptop (not
    proven from this lab-only session — see companion/laptop_client/README.md
    "what's deliberately not here yet"); pipx/msix packaging; a park HTTP
    route specifically (needs repo-path resolution + git-clean check
    ported off scripts/agent, deliberately deferred — see evidence);
    Windows-specific .ps1/.bat wrapper.
  evidence:
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
  last_verified_commit: fcd511b

- id: C-execution-plane
  outcome: deterministic/local/Codex/Claude execution as one mature governed lane
  status: active
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    remaining: exercise execute_codex on representative nontrivial bounded
    tasks (repo reconnaissance, schema output, one deterministic-repair
    loop) with recorded provider/latency/retry/cost-proxy telemetry —
    re-attempt once the bwrap/codex sandbox defect below is resolved
    (operator decision, see evidence) or on a host where it doesn't
    reproduce; a provider-neutral Claude executor adapter (dormant, no
    `claude` binary on this host).
  evidence:
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
  status: active
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
  last_verified_commit: <pending this checkpoint's commit>

- id: E-memory-broker
  outcome: source-linked memory broker ready for future home-primary promotion
  status: active
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    remaining: incremental ingest adapters (claude-code-sessions,
    chatgpt-export, codex-artifacts, repo-pointers — all still `planned`
    per `agent status`'s memory_sources, correctly not filled cosmetically);
    wiring `memory_outbox.replay()` into an actual scheduled/CLI entry
    point once a real home target exists to replay into.
  evidence:
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
  status: blocked
  priority: medium
  depends_on: []
  blocker: >-
    misumi and obsidian-phd have no known git remote (`remote: null` — not
    a lab-host-only gap, this registry has never had one for either) and
    no clone exists on any host this session can reach; s2-e1-ros2-
    measurement-spine was entirely unregistered until this session (now
    added, with an ASSUMED not confirmed root_var/path — see evidence).
    None of items 2-6 (source-pointer handoff, repo-specific instruction
    loading, parking a real repo, one representative real task) can be
    honestly exercised without operator-confirmed remotes/paths or an
    actual clone reachable from a session. Never fabricated by mutating
    or inventing access to PhD/robotics work to manufacture a demo.
  next_action: >-
    operator: confirm the real git remote for misumi and obsidian-phd (this
    registry has genuinely never known them), and confirm/correct the
    ASSUMED root_var=PHD_ROOT + path for s2-e1-ros2-measurement-spine.
    Once any one of the three is clone-reachable from a session (lab or
    laptop, once PHD_ROOT/HOUSEHOLD_ROOT are set in that host's
    ~/.aoteru/config.local.json), re-run this workstream's items 1-6
    against it for real.
  evidence:
    - "Live-confirmed via `agent status` on lab (2026-08-23): only
      `odysseus` and `odysseus-upstream-lab` resolve on this host; `misumi`
      and `obsidian-phd` correctly report 'unresolved: HOUSEHOLD_ROOT/
      PHD_ROOT not set' — truthful failure, not a guess, matching the
      registry's own stated contract. This IS the correct proof of item 1's
      'read-only resolution... fails truthfully' half, just not the
      'succeeds and returns real content' half, since no clone exists."
    - "Added config/repositories.yaml's missing s2-e1-ros2-measurement-spine
      entry (previously absent entirely, unlike misumi/obsidian-phd which
      at least had a `remote: null` placeholder) — remote taken from the
      task doc's explicit naming (tyecam1/s2-e1-ros2-measurement-spine,
      treated as confirmed); root_var/path are marked ASSUMED (inferred
      from obsidian-phd's PHD_ROOT convention, not live-verified) so a
      human correction is unambiguous rather than silently trusted."
    - "Item 4 (parking/lease/heartbeat/reclaim on a safe fixture) is
      already covered independent of any real cross-repo clone —
      tests/test_agent_cli_parking_lease.py exercises the full
      stale-reclaim/live-conflict lifecycle against a disposable fixture,
      confirmed still passing (5/5) this session. Not re-done here; this
      is a note that it was already satisfied, not a new gap."
  last_verified_commit: <pending this checkpoint's commit>

- id: G-glovebox-jetson
  outcome: deployable experiment-edge bootstrap; live qualification when reachable
  status: blocked
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
  status: active
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    remaining: wiring the mobile/companion frontend to actually call the
    new GET /api/estate/park/status route (the route exists, is tested
    and live-verified server-side; no frontend caller uses it yet — the
    laptop CLI now does, the mobile PWA doesn't); operator: run
    `scripts/interface_frontdoor_acceptance.py --url <interface PC URL>`
    once it's live — same command, no rewrite needed; then follow
    docs/aoteru-interface-pc-deployment.md's registration steps.
  evidence:
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
  last_verified_commit: ebcbfe6

- id: I-home-reentry
  outcome: bounded home-PC re-entry/migration procedure, not a redesign
  status: active
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
  status: active
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    remaining: the only J audit item left without at least one
    live-verified test is timeout/cancel/retry state transitions
    specifically for a *long-running* task's mid-flight cancel signal
    (retry-on-transient-failure is already tested — see C's evidence —
    but run_task()/execute_local() are synchronous with no cancel
    endpoint at all today; testing 'cancel' honestly requires either
    building one or explicitly recording that none exists yet, not
    fabricating a test against a mechanism that isn't there). operator:
    `sudo systemctl
    restart odysseus-aoteru-lab.service` to deploy this session's
    RunTaskEnvelope.objective fix and its oversized-objective guard to the
    live port-7001 instance — this session could not restart it (no
    non-interactive sudo), correctly treated as a stop-gate per GO.md
    rather than worked around.
  evidence:
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
  last_verified_commit: 01de50b

- id: K-operator-experience
  outcome: converged agent status / diagnostics / handbook
  status: active
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    remaining: logs/result pointers surface (deferred — no job-result
    store to point at yet beyond RoutingDecision ids).
  evidence:
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
  last_verified_commit: a967110

- id: L-real-work-validation
  outcome: representative end-to-end tasks across local/paid/multimodal/experiment-priority/blocked-host
  status: active
  priority: high
  depends_on: [B, C, D, E, F]
  blocker: >-
    PhD evidence/retrieval and S2-E1 ROS/log tasks specifically (as
    opposed to the generic unavailable-host case, which WAS run) still
    need a reachable clone — same F blocker, not re-litigated here.
  next_action: >-
    remaining: re-run the two blocked task classes for real once F's
    clone/remote gap is resolved by the operator; a repo-reconnaissance
    task against tyecam1/s2-e1-ros2-measurement-spine specifically (ROS/
    log interpretation) once reachable.
  evidence:
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
      host task that produces a durable truthful block' item."
  last_verified_commit: <pending this checkpoint's commit>
```

## Notes for the next session/turn

- This programme is intentionally multi-session in scope (11 workstreams,
  several requiring unavailable hardware). Do not treat one session's
  checkpoint as programme completion; keep working down eligible
  workstreams in priority order (A done; B/C/J next as highest-value
  currently-unblocked work) rather than re-deriving this file from
  scratch.
- G and I are genuinely host-blocked per live 2026-08-23 evidence, not
  under-worked; their non-live deliverables (packages, scripts, docs) are
  still open independent work and should not wait for the host.
