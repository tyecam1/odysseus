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
  status: eligible
  priority: high
  depends_on: []
  blocker: null
  next_action: >-
    audit scripts/agent + companion/ for what already exists as a thin
    client vs what still runs from a full checkout; design the smallest
    packaged surface (pipx/uv script or single-file bootstrap); this
    session has not yet started implementation.
  evidence: []
  last_verified_commit: null

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
  status: eligible
  priority: medium
  depends_on: []
  blocker: null
  next_action: locate existing routing-contract/evaluator code and gap-check against LM1-LM4 corpus.
  evidence: []
  last_verified_commit: null

- id: E-memory-broker
  outcome: source-linked memory broker ready for future home-primary promotion
  status: eligible
  priority: medium
  depends_on: []
  blocker: null
  next_action: audit current memory service against the canonical plan's source-trace/outbox/idempotency requirements.
  evidence: []
  last_verified_commit: null

- id: F-cross-repo-governance
  outcome: proven read/park/execute across tyecam1/obsidian-PhD, s2-e1-ros2-measurement-spine, misumi
  status: eligible
  priority: medium
  depends_on: []
  blocker: null
  next_action: inventory config/repositories.yaml registrations and reachability before any cross-repo action.
  evidence: []
  last_verified_commit: null

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
  status: blocked
  priority: low
  depends_on: []
  blocker: "home PC not present on tailnet — host-availability gate"
  next_action: "prepare inventory/promotion/benchmark tooling now (does not require home to be live); operator action required only for the actual re-entry session."
  evidence: []
  last_verified_commit: null

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
