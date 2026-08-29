# P13 — laptop re-entry, home/interface convergence: evidence

Executed 2026-08-29, the **first-ever laptop-run session** (`desktop-7dj1hma`),
continuing the P12.7 re-entry checklists in
`docs/aoteru-p12-active-estate-convergence-evidence.md`. Not a new numbered
phase per that doc's own "not manufacturing a P13" close — recorded as an
addendum evidence file, same convention.

## Laptop→lab continuation gate (P12.1) — closed

`aoteru status` from the laptop succeeded against the live
`svc:odysseus-lab` tailnet URL: `backend: reachable, status=healthy`. This
is the real transport the estate-routing skill uses, proven end-to-end for
the first time from the correct end (P12.1 could only prove it from the lab
side).

## Laptop client bug found and fixed

`companion/laptop_client/aoteru.py`'s `cmd_status` read a nonexistent `id`
key from `/api/estate/route/hosts` (the field is `host_id`) and printed
every *considered* host under one "eligible hosts" heading regardless of
the `eligible` flag — so an unverified home host displayed identically to
the eligible lab worker. Backend eligibility (`eligible_hosts()`) was
always correct; this was a pure client display bug. Fixed, with a
regression test, commit `f4baa2c`.

## Home + interface re-entry (P12.7) — both live-confirmed

Hostname ambiguity resolved: `DESKTOP-IN7O23D` (letter O) is correct;
`DESKTOP-IN7023D` (digit 0) does not resolve at all (mDNS/DNS both fail).

Both hosts identified and inventoried over LAN SSH using pre-existing keys
from the operator's separate `flat-knowledgebase`/`homeBase` local project
(not built this session — discovered and reused, not duplicated), with SSH
host-key fingerprints matched against operator-supplied pins before
connecting:

| host | id | LAN | tailnet (after enrollment) | OS/hardware |
|---|---|---|---|---|
| home | `desktop-in7o23d` | `192.168.4.102` (`User`, key `homebase-agent`) | `100.105.34.37` | Windows 11 Pro, Ryzen 7 5800X, 32GB RAM, RTX 3070, ~2TB storage |
| interface | `interface-pc` (`DESKTOP-RIFPR07`) | `192.168.4.37` (`mutisy`, key `tyeca-laptop`) | `100.99.90.100` | Windows 10 Pro, 16GB RAM, matches 2026-06-12 `flat-knowledgebase` audit |

Both were installed with Tailscale this session (silent MSI over SSH) and
authorized (operator completed the interactive login for each). No
`serve`/`funnel` config on either — tailnet-only, no new public exposure.
Interface PC's C: drive was found at ~43MB free of 223GB (blocking the
install); operator cleared space live, install then succeeded.

`config/estate.yaml` updated with live identities/tailscale fields.
`interface-pc.verified` set `true` (safe — `interface` role is never
`execution_worker`-eligible regardless, `config/routing.yaml`). `home.verified`
deliberately left `false` — see residual risks below.

## Reconciliation: home's existing Odysseus/Misumi stack

Discovery: home already runs a full Odysseus-harness deployment (port 420,
live `/api/health` → 200), `misumi_agent.py` (4500), and an STT server
(4600) — governed by the operator's separate, pre-existing
`flat-knowledgebase`/`homeBase` repo and its own ratified
`docs/odysseus-contract.md`, not something built or known about by the
`tyecam1/odysseus` estate docs before this session.

Live-audited per the operator's explicit KEEP/WRAP/MOVE/RETIRE instruction:
that deployment (`odysseus-releases\e68288238b3c`) has **no**
`src/estate_router.py` and **no** `config/estate.yaml` — no "estate" string
anywhere in `app.py`, only the general personal-assistant route surface
(chat/calendar/email/cookbook/assistant/document/etc). Structurally
incapable of acting as a competing discovery/routing/lease authority.
**KEEP, untouched.** `svc:odysseus-home`'s `endpoint` stays `null` in
`config/estate.yaml` — that id names an estate-callable backend, which
this is not and isn't planned to become.

## Laptop routing-skill UX gap — closed (client + backend source)

The execution contract's required `auto`/`lab`/`home`/`where` modes were
missing. Two real bugs blocked them, both now fixed in source (commit
`b7ee3f2`):

1. `resolve_route()` has read `task["placement"]["requested_host"]` since
   it was written, but the HTTP `TaskEnvelope` never declared a
   `placement` field — pydantic v2 silently dropped it, so no HTTP caller
   could ever force `lab`/`home`. Added `TaskEnvelopePlacement`.
2. `agent claude where` (session mapping) only ever existed as a local DB
   read in `scripts/agent`, unreachable from a checkout-free client. Added
   `src.estate_router.active_logical_sessions()` +
   `GET /api/estate/sessions`.

`companion/laptop_client/aoteru.py` gained `auto`/`lab`/`home` (POST
`/api/estate/run` with `placement.requested_host`), `where` (GET
`/api/estate/sessions`), and `sync` (installs
`~/.claude/skills/aoteru-estate-routing/SKILL.md`, checkout-free — done,
installed on this laptop). Both modes execute via the estate's
LLM-completion routing path, **not** a native interactive Claude Code
session on the remote host — that launch mechanism still doesn't exist
(`scripts/agent`'s `agent claude` fails the same way, truthfully, when
dispatch would need a real remote launch).

**Not yet live**: pushing to `dev` only updates source. The running
`svc:odysseus-lab` process needs its own pull+restart to actually serve
`/api/estate/sessions` or honor `placement.requested_host` — not done this
session (no lab shell access this pass, see residual risks). `aoteru
where` currently 404s against the live backend until that deploy happens.

## PhD routing proof (section 7 of the operator's task) — not reached

Blocked on the same lab-deploy gap: proving a bounded PhD-repo read/analysis
task routed from the laptop through `auto`/`lab` needs the just-pushed
backend changes actually running on lab, which this session could not
deploy. Genuine next step, not silently skipped.

## Residual risks, ranked by impact

1. **Backend routing-skill changes (`src/estate_router.py`,
   `routes/estate_routing_routes.py`) are pushed but not pytest-verified
   from this session.** No Odysseus checkout/dependency environment exists
   on the laptop by design, and laptop→lab SSH is blocked by tailnet ACL
   policy (see below), so `tests/test_estate_router.py` could not be run
   against these changes. They are additive (new field with a default, new
   functions, new route) and were syntax-checked + hand-traced against the
   existing contracts, but need a real `pytest` run on a host with the
   actual checkout before being trusted. `companion/laptop_client`'s own
   suite (23/23) *was* run for real.
2. **Laptop→lab SSH is blocked by Tailscale ACL policy**, not
   connectivity — `tailscale: tailnet policy does not permit you to SSH as
   user "tyeca"`. The HTTP path (what `aoteru`/the routing skill actually
   use) works fine; this only blocks a direct SSH session or deploying the
   above backend change from the laptop. Policy change is an admin-console
   action, not attempted this session.
3. **Home benchmark qualification (P12.7 item 4) not done.** Identity is
   now live-confirmed, but `home.verified` deliberately stays `false` in
   `config/estate.yaml` — flipping it is the only gate `eligible_hosts()`
   has today, and it would grant execution-worker eligibility immediately
   with zero benchmark evidence. `eligible_hosts()` has no separate
   benchmark gate; this is a real code gap between the P12.7 process
   intent and what's structurally enforced — worth a dedicated fix before
   home ever becomes a routing candidate.
4. **Tailnet auto-approval not configured.** Operator asked for future
   work: enable Tailscale auto-approvers (or reusable pre-authorized keys)
   so new-device logins don't need manual browser approval each time. Not
   done this session — it's a tailnet-wide ACL/admin-console policy
   change, out of scope for an autonomous pass without explicit scoping of
   which device classes to auto-approve.
5. **Interface PC's C: drive is still nearly full** (operator freed a
   small amount to unblock the Tailscale install; more clearing was
   deferred by the operator to later).
6. **Glovebox Jetson** — out of scope this pass, unchanged from P12
   (offline).

## Next-phase recommendation

Not manufacturing further phase numbers, per this project's own established
convention. Two concrete triggers for a follow-up pass: (1) laptop→lab SSH
policy fixed or a lab-side deploy of `b7ee3f2` happens some other way, which
unblocks `where`/`lab`/`home` end-to-end and the PhD routing proof; (2)
home benchmark evidence gathered (reusing the existing `evals/local_models/`
LM1–LM4 harness pattern), which is the only thing standing between the
current honest `verified: false` and real worker eligibility for home.

## Addendum 2026-08-29 (same day, follow-on session): lab deploy + laptop routing closed, PhD gate blocked on external Codex quota

Continuation of this file's own residual-risk items 1 and 2, and the
"PhD routing proof — not reached" section above. Re-verified live, not
assumed from this file's own prior claims.

**Tailscale ACL**: operator updated tailnet policy. `ssh tyeca@...`
still rejected (`tailnet policy does not permit you to SSH as user
"tyeca"`) — the grant was for user `agent`, which is also the
correct account: the systemd unit and lab checkout are `User=agent`
already, per `docs/aoteru-lab-first-operator-guide.md`. `ssh
agent@dmem-hp-z2-tower-g9-workstation-desktop-pc.tail171792.ts.net`
succeeds.

**Backend deploy**: lab checkout fast-forwarded `44dcdc7` -> `3228f35`
(clean tree, `git merge-base --is-ancestor` confirmed before pulling).
`tests/test_estate_router.py` + `tests/test_laptop_client.py`: 78/78
passed (the pytest run residual-risk item 1 above asked for). Neighbouring
regression sweep (`-k 'estate or routing or session or placement or park
or lease'`): 368 passed, 1 failed
(`test_session_list_owner_scope.py::test_list_sessions_excludes_other_users_sessions`);
re-run alone: 2/2 passed — an order-dependent flake unrelated to this
change, not a regression, not weakened or touched.

`sudo systemctl restart` needed an interactive password unavailable to
the automated session; the operator ran the restart directly. Verified
after: `systemctl is-active`/`is-enabled` both healthy, `MainPID`
changed (fresh process), `GET /api/health` -> 200, deployed
`git log -1` -> `3228f35`.

**Laptop routing re-proof against the deployed backend** (this file's
"PhD routing proof — not reached" trigger #1): `aoteru where` now
returns `{"active_sessions": []}` instead of 404 -
`GET /api/estate/sessions` is live. `aoteru status`/`route` still
show lab eligible, home correctly considered-but-ineligible. Forced-host
placement is truthful both ways: `aoteru lab "..." --capability
local-fast` executed for real on `hz2-workstation`/`qwen3:8b`
(exact echoed output, `deterministic_gate: pass`); `aoteru home
"..."` was correctly refused (`requested host 'home' is not
eligible`) — home was not made eligible just to pass this check, matching
this file's own residual-risk item 3 (still open, untouched this pass).

**PhD end-to-end gate — genuine architecture finding, not a repo-access
bug**: `execute_local`/the "local" executor path has no filesystem
grounding at all — `task["repo"]` is used only for host eligibility
(`eligible_hosts(repo_id)`) and, separately, only inside the paid-Codex
escalation branch (`resolve_repo_path` -> `cwd`). A capability that
resolves to a bound local model (`local-fast`/`local-strong`) can
never read the routed repo, by current design — confirmed live: a bounded
read-only backlog question sent via `--capability local-strong`
executed (`executed: true`) but returned empty output with
`deterministic_gate: fail`, because the model was never given any file
content to work from. Real repo-grounded execution only exists on the
evidence-triggered paid-escalation path, reached here via
`--capability code-strong` (the one alias with `binding: null` in
`config/models.yaml`) + `--allow-paid`. That correctly escalated to
`executor: codex`, reached the lab's real
`obsidian-phd` checkout (`${PHD_ROOT}/obsidian-PhD`, content spot-
checked identical to the operator's own laptop checkout of
`10-inbox/backlog.md`), and failed truthfully and specifically:
`codex exec exited 1` with Codex's own usage-limit error, reset time
"5:45 PM" (lab-local `Europe/London`, confirmed `date` ->
`16:10:20 BST` at the time of the attempt, i.e. reset ~17:45 BST). Not a
repo-access failure, not fabricated, no file touched, no lease taken.

**Resume exactly here** (operator decision: stop and record rather than
wait ~95 minutes) — after 17:45 BST, from the laptop, re-run the identical
command that failed on quota, no other change:

```
aoteru lab "Read only the file 10-inbox/backlog.md and the S2-E1 work item it points to in this repository. Report exactly three things and nothing else: (1) the work item's title, (2) its status field, (3) the immediate next unchecked physical gate item (the first unchecked checkbox) from its execution ladder. Do not modify any file." --repo obsidian-phd --capability code-strong --allow-paid --timeout 180
```

Expected deterministic pass: output names title "S2-E1 physical
acquisition and static metrology vertical slice", status `paused`, and
next gate "Rebuild from the Git-provenance fix and retain replacement
E1a/E1b reports with the exact commit and `git_dirty: false`" (verified
directly against `10-inbox/s2-e1-perception-experiment-hardware-and-
measurement-setup.md` on the laptop's own checkout this same session,
independent of the routed answer). That match is this gate's deterministic
success condition.

No other residual-risk item above was touched this pass; items 3-6 remain
exactly as this file already described them.
