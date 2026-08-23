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
    "what's deliberately not here yet"); pipx/msix packaging; a
    park/release/heartbeat HTTP surface so the client can cover those
    scripts/agent subcommands too; Windows-specific .ps1/.bat wrapper.
  evidence:
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
      ~/.aoteru/client.json (chmod 600), token never printed. Live-tested
      standalone (copied outside the repo, HOME redirected) against the
      real running dev instance on 127.0.0.1:7000: /api/health round-trip
      succeeded, and an invalid token was correctly rejected 401 by the
      live auth middleware (confirmed independently via curl). 7 new
      unit tests. companion/laptop_client/README.md is the exact operator
      bootstrap (mint token -> copy file -> configure -> smoke test)."
  last_verified_commit: <pending this checkpoint's commit>

- id: C-execution-plane
  outcome: deterministic/local/Codex/Claude execution as one mature governed lane
  status: active
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    remaining: exercise execute_codex on representative nontrivial bounded
    tasks (repo reconnaissance, schema output, one deterministic-repair
    loop) with recorded provider/latency/retry/cost-proxy telemetry; a
    provider-neutral Claude executor adapter (dormant, no `claude` binary
    on this host); cheap/strong paid capability aliases via config, not
    hardcoded names.
  evidence:
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
  last_verified_commit: <pending this checkpoint's commit>

- id: D-routing-replay-evaluator
  outcome: replay/shadow routing evaluator reusing RoutingDecision/BenchmarkResult
  status: active
  priority: medium
  depends_on: []
  blocker: null
  next_action: >-
    remaining: candidate-config-change proposal generator with before/after
    evidence (item 6, needs evidence_sufficient routes to exist first —
    none do yet, live-confirmed); a real shadow-execution replay harness
    that re-runs historical prompts against a candidate config, not just
    aggregation of what already happened; re-evaluate code-strong only if
    future evidence shows code-fast+paid insufficient (still null, still
    correctly not filled cosmetically).
  evidence:
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
    bounded-recall API shape explicitly tuned for laptop/mobile payload
    size (Workstream K/H will need this); a queryable `history()`-backed
    revision endpoint (the data already supports it, no route exposes it
    yet); wiring `memory_outbox.replay()` into an actual scheduled/CLI
    entry point once a real home target exists to replay into.
  evidence:
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
  last_verified_commit: <pending this checkpoint's commit>

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
  next_action: "operator: power/reconnect glovebox; then re-run live inventory + read-only qualification. Deployable-package prep (non-live parts) remains open independent work."
  evidence: ["tailscale status 2026-08-23: glovebox offline, last seen 36d ago"]
  last_verified_commit: null

- id: H-interface-mobile-frontdoor
  outcome: deployable svc:aoteru front-door + PWA, activation-ready for interface PC
  status: eligible
  priority: medium
  depends_on: []
  blocker: null
  next_action: build/test as deployable artefacts against a lab test instance only; never relabel as canonical svc:aoteru.
  evidence: []
  last_verified_commit: null

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
    shadow/canary gate wiring once a real target exists; backup/restore
    conflict checks; operator: run
    `venv/bin/python scripts/home_reentry_inventory.py` on the actual
    home host once reachable, then
    `venv/bin/python scripts/memory_promote_replay.py --target <home
    misumi memory root>` to promote lab's accumulated memory.
  evidence:
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
  last_verified_commit: <pending this checkpoint's commit>

- id: J-security-resilience
  outcome: recovery paths verified beyond happy-path smokes; cold-reboot checklist
  status: active
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    remaining: DB backup/restore drill, Chroma rebuild-from-authoritative-state
    test, worker/model/provider disappearance mid-task, stale LogicalSession/
    job reconciliation, auth/token scope audit, malformed/oversized
    multimodal envelope handling.
  evidence:
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
  last_verified_commit: <pending this checkpoint's commit>

- id: K-operator-experience
  outcome: converged agent status / diagnostics / handbook
  status: eligible
  priority: medium
  depends_on: []
  blocker: null
  next_action: not yet started this session; likely sequenced after B/C/E produce real surfaces to expose.
  evidence: []
  last_verified_commit: null

- id: L-real-work-validation
  outcome: representative end-to-end tasks across local/paid/multimodal/experiment-priority/blocked-host
  status: eligible
  priority: high
  depends_on: [B, C, D, E, F]
  blocker: null
  next_action: run only once the underlying workstreams have real surfaces to validate; premature now.
  evidence: []
  last_verified_commit: null
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
