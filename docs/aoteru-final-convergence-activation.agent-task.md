---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-23-aoteru-final-convergence-activation
title: "Aoteru final convergence and activation"
status: ready
priority: critical
task_type: bounded-convergence-controller
created_by: chatgpt
created_at: 2026-08-23T17:28:00+01:00
executor: claude-sonnet-5
execution_mode: finite-autonomous-convergence
resource_profile: adaptive
risk_level: medium
approval_required: false
source_traceability_required: true
requires_local_model: true
requires_remote_compute: true
requires_web: true
repo: tyecam1/odysseus
branch: dev
inputs:
  - docs/aoteru-autonomous-programme-state.md
  - docs/aoteru-long-horizon-autonomous-convergence.agent-task.md
  - docs/aoteru-estate-implementation-plan.md
  - docs/aoteru-estate-execution-contract.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-operating-handbook.md
  - config/estate.yaml
  - config/repositories.yaml
  - config/models.yaml
  - config/routing.yaml
outputs:
  - corrected finite programme state with active vs evidence-gated vs ready-for-host separated
  - production service verified on the current committed code
  - identity-safe interface/front-door acceptance test
  - genuinely checkout-free laptop bootstrap path
  - safe remote lease-acquisition path if it can reuse existing path/git-clean/lease authorities
  - sandbox-preserving Codex execution qualification or exact external blocker
  - governed cross-repo proof using real PhD/Misumi/S2-E1 repositories
  - remaining PhD and S2-E1 real-work routing validation
  - final full-suite and live-estate evidence
  - exact residual human/host activation commands only
---
# Aoteru final convergence and activation

## Mission

Perform one **finite closure pass** over the long-horizon Aoteru programme.
Do not restart the previous open-ended `/loop`, do not invent P13/P14-style
microphases, and do not continue engineering merely because optional features
remain.

The goal is now:

```text
close reachable-estate defects and product gaps
-> prove the controller/execution/repository path with real work
-> classify evidence-gated work honestly
-> reduce unavailable-host work to exact activation commands
-> stop developing and let real use generate routing evidence
```

Start by pulling `dev`, reading the current programme state, inspecting actual
HEAD/live state, and reconciling this task against code rather than assuming any
statement below is still true.

## Decisions already resolved

These are programme decisions, not questions to bounce back to the operator.
Change them only if new primary evidence makes them unsafe or impossible.

1. **Codex sandbox:** do **not** use
   `--dangerously-bypass-approvals-and-sandbox` as the production workaround for
   the old bubblewrap `--argv0` failure. Preserve Codex sandboxing. Inspect the
   installed Codex mechanism/version and upgrade to a current compatible release
   if possible without weakening isolation. Upstream current Codex contains an
   old-bubblewrap compatibility path; prefer fixing/updating tooling over
   disabling the sandbox. If this host cannot be upgraded safely from the
   current account, leave an exact one-command operator action and keep Codex
   truthful/degraded rather than bypassing protection.
2. **Codex-session memory ingest:** do **not** broadly ingest
   `~/.codex/sessions/`. It contains unrelated-project sessions. E is not kept
   active merely to build speculative adapters. A future adapter is permitted
   only as explicit per-project opt-in with repository/cwd allowlisting.
3. **Cancellation:** do **not** invent an asynchronous job/cancellation system
   solely to close J. The current execution path is synchronous. Mid-flight
   cancellation becomes a future requirement only when real long-running async
   jobs exist.
4. **Routing proposals:** do not generate speculative policy changes before
   sufficient production evidence. Preserve the evidence threshold and
   exploration-off invariant.
5. **Packaging:** `.msix` is not a programme completion criterion. Prefer a
   working one-command Windows/checkout-free bootstrap over packaging polish.
6. **Unavailable hosts:** glovebox/home/interface-PC live activation is
   event-triggered work. Do not design speculative hardware integrations while
   those hosts remain unavailable.

## Known audit corrections to verify and address

Treat these as high-priority hypotheses; verify them against current HEAD before
editing.

### A. Interface acceptance can still validate the wrong app

`scripts/interface_frontdoor_acceptance.py` was live-rerun correctly with an
explicit port-7001 URL after the programme discovered port 7000 belongs to the
wrong codebase, but the script itself still defaulted to `127.0.0.1:7000` and
accepted behaviour without proving application identity.

If still true:
- eliminate the stale 7000 default or resolve the test target from canonical
  configuration;
- require an identity/version check before an acceptance result can PASS;
- add regression tests proving a same-shaped wrong app cannot pass;
- rerun against the real Aoteru deployment.

### B. Cross-repo F is not blocked on repository identity

The following canonical GitHub repositories are confirmed and should be written
into `config/repositories.yaml` where the registry still has `remote: null` or an
assumed remote:

- `https://github.com/tyecam1/obsidian-PhD.git`
- `https://github.com/tyecam1/misumi.git`
- `https://github.com/tyecam1/s2-e1-ros2-measurement-spine.git`

Do not ask the operator to re-confirm these identities. The remaining things to
prove are host-local private-repo authentication, a safe clone/root location,
and the governance path itself.

Use existing Git/GitHub credentials if already present. Never print/store tokens
in repo evidence. If private clone/auth genuinely cannot be established from the
lab account, record the exact credential/bootstrap gate; do not fabricate a
clone.

For root/path values, discover actual host state first. Do not silently convert
an assumed `PHD_ROOT` layout into a permanent truth. A controlled read-only clone
under an appropriate existing projects area is acceptable for governance and
real-work validation if it does not redefine the domain repo's canonical
location.

### C. Laptop installation is not yet truly checkout-free

The thin client itself is checkout-free, but a documented command of the form
`pipx install /path/to/this/checkout/...` is not a complete remote bootstrap for
a laptop that intentionally has no Odysseus checkout.

Deliver the smallest reproducible one-command bootstrap/update path that installs
only the client component and no worker/runtime/database/model stack. Prefer a
GitHub/raw/package-based route if it is supportable from the existing repository.
Keep the single-file fallback. Do not build `.msix` merely for completeness.

### D. Remote `park` is still a real controller gap

`park-status`, heartbeat and release exist over HTTP; acquisition stayed CLI-only
because repo-path resolution and git-clean verification were coupled to
`scripts/agent`.

If a bounded refactor can reuse/extract those exact existing authorities without
creating a second path resolver/git-clean/lease authority, expose safe remote
lease acquisition and add it to the thin client. Required semantics:
- registered repo only;
- resolved real path/worktree only;
- fail closed on missing/unresolved/dirty repo;
- preserve stale-reclaim/live-conflict semantics;
- scope-gate mutation;
- no arbitrary path supplied by remote caller.

If doing this safely would require a disproportionate redesign, leave it as a
clearly justified residual gap instead of weakening parking authority.

## Closure sequence

Work in this order unless live evidence makes a later item the only executable
one.

### 1. Production deploy verification

The previous session committed a restored `RunTaskEnvelope.objective` and an
oversized-objective guard but could not restart `odysseus-aoteru-lab.service`
without interactive sudo.

Check whether the operator has already restarted it. Confirm:
- live service is this repository/application, not the historical port-7000 app;
- deployed commit/version contains the objective fix and size guard;
- `scripts/cold_reboot_verify.py` remains green;
- a real authenticated `/api/estate/run` or laptop-client `ask` round trip
  carries a non-empty objective through to execution.

If the service is still stale, do not work around systemd. Record the exact
restart gate and continue independent items.

### 2. Correct programme-state semantics

Update `docs/aoteru-autonomous-programme-state.md` so `active` means a material
current engineering gap, not "anything imaginable remains".

Target classification, subject to verification:
- A: complete.
- B: active until checkout-free bootstrap + material controller gaps are closed;
  laptop-origin smoke can then be ready-for-operator.
- C: active only while sandbox-preserving Codex execution is not qualified; a
  dormant Claude adapter is not required if no real provider/runtime exists.
- D: operational/evidence-gated once evaluator is sound; not active merely
  because insufficient production volume exists.
- E: complete-current-estate; future home promotion remains ready-for-host.
- F: eligible/active, not blocked on repository identity; only real clone/auth or
  host-path gates may block it.
- G: ready-for-host once non-live qualification/bootstrap is sufficient; avoid
  speculative Jetson work until live qualification.
- H: active only for concrete front-door/controller integration defects.
- I: ready-for-host.
- J: complete once current synchronous resilience surface is verified; async
  cancellation is a future trigger, not a closure gap.
- K: complete.
- L: active until the real PhD/S2-E1 tasks unlocked by F are run; unavailable-host
  validation may remain a truthful blocked proof.

### 3. Front-door and laptop-controller closure

Implement and verify A/C/D above where warranted.

Also wire the mobile/PWA surface to the existing park-status endpoint if the
current frontend has a small clear integration point. Reuse server authority; do
not create a second lease/status implementation.

Produce exactly one recommended laptop bootstrap command and a compact smoke
sequence for the operator. Do not require a source checkout.

### 4. Sandbox-preserving Codex qualification

Inspect installation source, current version and bubblewrap compatibility.
Attempt a safe upgrade to current Codex if allowed from this account and verify
version afterward. Never silently modify global security policy.

Then execute representative bounded tasks through the real Odysseus paid lane:
- repository reconnaissance;
- strict/schema-shaped output;
- one small deterministic verification/repair loop in a safe fixture/scratch
  worktree.

Record routing decision ids, executor/provider/version, wall latency,
retry/escalation and deterministic verification outcome. A task that cannot read
its repo is a failed qualification, even if the CLI process exits zero.

If safe upgrade is externally blocked, preserve the truthful failure and leave
one exact operator upgrade action. Do not weaken sandboxing to make tests pass.

### 5. Governed cross-repo convergence (F)

Using the confirmed remotes, establish the smallest safe lab-side read path to
all reachable repos. Verify instruction/authority loading rather than merely
cloning files.

At minimum prove for `obsidian-PhD` and `s2-e1-ros2-measurement-spine`:
- real repository identity and default branch;
- clean/read-only resolution through the Odysseus registry/authority surface;
- parking/lease semantics on a clean worktree where safe, followed by release;
- source-pointer handoff without copying whole transcripts;
- correct repo-specific instruction loading before any mutation.

`misumi` should receive the same proof if reachable without creating unnecessary
work; its presence must not block PhD/S2-E1 closure.

Never mutate research content merely to manufacture a demonstration. Use
read-only representative work or a disposable fixture/branch when a mutation is
needed to test governance.

### 6. Finish L with real research-shaped work

Run through the actual `run_task`/routing/execution/telemetry path, not an offline
harness:

1. **PhD evidence/retrieval task** against `tyecam1/obsidian-PhD`: bounded
   reconnaissance/evidence retrieval using real repo content and source pointers;
   no manuscript/content edits required.
2. **S2-E1 ROS/log interpretation task** against
   `tyecam1/s2-e1-ros2-measurement-spine`: bounded repository/log/test
   interpretation grounded in real project content; no robot control.

Use stable task-class names aligned with the existing benchmark taxonomy where
possible. Record decision ids and verification evidence.

### 7. Routing-evidence hygiene

Inspect the current 52+ RoutingDecision taxonomy fragmentation. Do not rewrite
historical rows destructively.

If a small, principled canonical-class/family field or evaluator-side
normalization can map smoke/canary variants into the stable benchmark task
classes while preserving the raw task_class, implement and test it. The goal is
to let future real use accumulate meaningful evidence rather than dozens of
one-off labels.

If the mapping would be arbitrary or require broad schema redesign, document the
specific fragmentation and leave D evidence-gated. Do not lower
`EVIDENCE_THRESHOLD` just to make proposals appear.

### 8. Final verification and stop

Run:
- focused tests for every changed surface;
- full test suite;
- live service/front-door acceptance against the correct app identity;
- `agent status --pretty`;
- representative `agent explain` and `agent decision <id>`;
- Tailscale Serve/public-exposure check;
- active/stale lease check;
- real local execution after all routing changes;
- real paid execution only if Codex qualification is safely restored.

Commit cohesive checkpoints and push `dev`.

Then perform one independent convergence audit. Stop when all **currently
reachable core functionality** is either complete or has one narrow external
activation gate. Do not keep a timed heartbeat running after this task.

## Explicit non-goals

Do not:
- initialise LM5 or resume model discovery;
- change qualified local-model aliases without new evidence;
- add broad `~/.codex/sessions` ingestion;
- build `.msix` for cosmetic completeness;
- invent a Claude executor without a real runtime/use case;
- build async cancellation solely to close J;
- lower routing evidence thresholds;
- store raw sensitive prompts merely to enable replay;
- turn the Jetson into a generic LLM worker;
- make home/interface/glovebox reachability imply trust;
- expose model/MCP/shell/control ports publicly;
- use Codex sandbox bypass to make the paid lane look green;
- continue autonomous feature hunting once this closure task's stop condition is met.

## Final report

Return a compact report containing:
1. commits pushed;
2. core capabilities newly closed;
3. real production/research task evidence and decision ids;
4. test/live verification results;
5. residual gates split into **operator-now**, **host-return**, and
   **evidence-accumulation**;
6. the exact one-command laptop bootstrap/smoke procedure;
7. a clear statement that the finite convergence task is complete and no timed
   development loop should continue, if that conclusion is supported.
