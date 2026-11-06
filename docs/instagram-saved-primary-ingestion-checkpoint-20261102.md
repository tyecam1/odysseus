---
title: Instagram Saved primary ingestion - continuation checkpoint
status: active-checkpoint
created: 2026-11-02
updated: 2026-11-06
owner: odysseus
directive: docs/instagram-saved-primary-ingestion-directive-2026-10-17.md
---

# Working-memory checkpoint (directive section 11 payload)

- **last_checked_git_sha**: `cbf7d43` (origin/dev = deployed lab backend checkout, clean)
- **directive_version**: 2026-10-17 (unmodified; no objective or safety-contract change proposed)
- **acquisition_mode**: Meta Download-Your-Information export via policy-gated Playwright, weekly + on start, from the **lab** backend (`odysseus-aoteru-lab.service`, port 7001). Host choice per owner (2026-10-27): router-decided by load, currently lab. Headed opt-in `ODYSSEUS_META_EXPORT_HEADED=1` (with DISPLAY/XAUTHORITY in lab `.env`) so the acquisition browser runs on the lab's physical display.
- **source_gate**: operator auth for the existing Meta/Instagram account (never agent-held).
- **device_gate**: none active (GrapheneOS opportunistic trigger not yet wired).
- **stage_state**:
  - export job: `needs_operator_auth`, cycle `2ff08513ea07…`, retry_count 0, correctly gated (state machine never touches Meta UI without acknowledgement).
  - import job: hourly, green (`failed: 0`, corpus 1,772 items, unchanged).
  - handoff/semantic: green, zero routed (no new sources yet).
- **recent_source_ids_or_hashes**: none new — no export has been acquired yet; corpus unchanged at 1,772 items.
- **test_and_codex_evidence**:
  - PRs merged (CI green, Sol/gpt-6-sol APPROVE unless noted): #178 (Windows state-persist fix — the actual blocker behind WinError 32), #183 (launcher Windows Chromium discovery; 2 Sol rounds), #187 (deterministic-execution + quota-aware routing proposal doc; Sol corrections incorporated), #188 (Windows-safe pid liveness; 3 Sol rounds), #196 (opt-in headed acquisition browser).
  - Live evidence: export job persists state and gates correctly on Windows (home, 2026-10-26) and lab; headed automation visible on lab display; bounce mechanism produces precise operator gates.
- **open_risks**:
  1. **Session revocation pattern (3x confirmed 2026-10-28/29)**: login succeeds, cookies persist ~3 minutes, the first automated authenticated navigation triggers server-side revocation (login redirect; sessionid wiped). Manual Chrome sees the same logout — this is Instagram account security, not local code. Repeated unattended retries risk account flagging.
  2. `closefd=False` / `os.kill(pid,0)`-class Windows-isms may exist elsewhere in the repo (three found and fixed so far).
  3. aoteru `deterministic` executor is route-complete-only (`executed: false`); quota exhaustion is not detected pre-launch (proposal #187, implementation pending).
- **next_executable_packet**: single coordinated attempt with the owner **physically at the lab monitor**: (1) headed login + phone approval; (2) immediately acknowledge gate and trigger one export cycle; (3) owner approves the mid-flow challenge live in the automation window; (4) then unattended through awaiting_email -> downloading -> validating -> imported, each state observed before claiming operational. Pre-check from the owner's phone: Security > Login activity (confirm lab logins, remove unfamiliar) and confirm any Instagram security emails.
- **precise_operator_gate_if_any**: owner presence at the lab monitor for login + live mid-flow challenge approval; account-trust review from their phone. No agent may hold credentials or approve challenges.
- **budget_summary**: laptop-coordinator sessions 2026-10-26..11-02; no paid-model spend beyond Sol review packets (5, all small); lab/home execution is local compute; zero Meta API or export spend.

## Continuation rule

Per directive section 11: read the directive, reconcile with live repo/worker state, proceed to the earliest unsatisfied dependency-ready gate. The earliest unsatisfied gate is the operator auth handshake above; everything downstream is automated and deployed.
