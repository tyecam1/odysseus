# Misumi/Odysseus operational closeout - evidence (2026-10-06)

Authority: the user's standing operational-closeout instruction of 2026-10-06. Hard boundaries respected: no credential, physical observation, model review, restore or judgement was fabricated. `null` marks evidence that does not exist. Runtime identifiers are resolved live (see "Reading live state") and are not frozen here.

## Reading live state (do not trust this file for identifiers)

- Home production release: the `Odysseus-Misumi` scheduled task action on the home host (its `-SourceRoot`). Rollback: the previous release directories kept under `C:\Users\User\odysseus-releases`.
- Lab: `git -C /home/agent/projects/odysseus-aoteru rev-parse HEAD`; rollback material in `/home/agent/.aoteru/rollback-lab-d2fc0bac32-20261006/` (head, `app.db` online backup with `integrity_check` ok, settings, auth.json, `.env` copy, service state).
- Branch heads: GitHub.

## 1. Lab deployment (B5) - complete

| Step | Evidence |
| --- | --- |
| Baseline | Lab checkout `dev` at `d2fc0bac32`, clean, 171 commits behind `origin/dev`, 0 ahead. `odysseus-aoteru-lab.service` (system unit, `User=agent`, binds 127.0.0.1:7001) active; legacy `odysseus.service` (:7000, a different checkout) also running and untouched. Sudo: password required, EXCEPT `NOPASSWD` for `systemctl start/stop/restart odysseus-aoteru-lab.service`. |
| Rollback | Snapshot above; deploy is a fast-forward so `git reset --hard d2fc0bac32` + restart restores the old code (data stores were not migrated by hand). |
| Verification before | Fresh `git archive` of `origin/dev` tested with the lab venv. |
| Deploy | `git merge --ff-only origin/dev`; `sudo -n systemctl restart odysseus-aoteru-lab.service` (`RESTART_OK`, no password needed). `requirements.txt` unchanged; `requirements-optional.txt` +3 lines not installed (optional). |
| Runtime proof | `/api/health` healthy 3 s after restart, `NRestarts=0`, journal shows startup complete and four built-in MCP servers connected. `aoteru status` from the laptop: backend healthy, **eligible hosts 2: hz2-workstation (lab) and desktop-in7o23d (home)** (home was ineligible before: `verified: false` in the stale config). |
| Routing | `reasoning-strong` -> local `nemotron-3.5-lightning:30b-a3b` (ok). `code-strong` -> `alias code-strong not qualified on hz2-workstation` (binding null; `paid_provider: codex`). `sol` and `glm` -> `unknown alias`. |
| Regression | Full suite on the target tree: **6015 passed, 24 skipped, 1 deselected, 0 failed** (5 min 41 s). The deselected test (`test_bbc_adapters.py::test_real_checkout_roadmap_fixture_is_ingested_read_only`) needs a real git checkout; a `git archive` tree has none. |
| Residual drift | `/home/agent/projects/odysseus` (:7000) is an older, separate UI instance; 12 stale worktrees under `~/aoteru-worktrees`; a failed user unit `drm-remote-upkeep.service`. Not touched; recorded. Lab `sudo` still needs a password for everything else (credential-bound), so lab OS-level hardening was not attempted. |

## 2. Model lanes

- **Sol** = `codex exec` with `gpt-5.6-sol`, read-only, through a ChatGPT login (the 2026-09/10 reviews used exactly this). Lab: codex-cli 0.155.1 authenticated. Laptop: codex-cli 0.156.1 authenticated. Both: `ERROR: You've hit your usage limit ... try again at 7:57 PM` (2026-10-06 BST) for `gpt-5.6-sol` and `gpt-6-sol`. Classification: **model-lane-unavailable** (external quota). No credit purchase was made (financial action). A one-shot watcher is scheduled for 19:59 BST. **No Sol review has taken place.**
- **GLM**: no alias, binding, API key, launcher or Claude-CLI env override exists on the lab or the laptop (`~/.claude/settings.json` has an empty `env`). PR #38 (candidate GLM paid worker) is still a draft. **model-lane-unavailable.** `reasoning-strong` is local Nemotron and is advisory only.
- **Opus**: not attempted (see queue D4).

## 3. Memory policy v0.2 (B6) - complete

Ratified in misumi PR #66 (merge commit resolved from GitHub). The four conditions were checked against the text and recorded in the policy's "Ratification record": within scope, no materially new sensitive collection, authority boundaries preserved, internally coherent; the checker's needles are unchanged. The five named gaps stay named. Rollback: revert the PR; no runtime behaviour depends on the status label. Misumi has no CI workflows, so the only automated check is `scripts/memory_policy_check.py`, which was not run in this session (null).

## 4. Backup and restore (B4)

Design per `docs/operations/backup-restore.md`; tool and task script from the production release.

| Step | Evidence |
| --- | --- |
| `age` | `FiloSottile.age` 1.3.2 via winget on the laptop; the same `age.exe` (sha256 `2821A4ED...F45F0`, identical both ends) copied to `C:\Program Files\age` on home and added to machine PATH. |
| Keypair | Generated on the laptop, never on home. Private identity: `C:\Users\tyeca\.aoteru-secrets\misumi-backup.age-identity.txt` (ACL: the user only; outside every synced folder; never printed or committed). Public recipient `age18fy86whgslfg4uh0wl4lk9gn5adu4dxuyrg8fn2kyjjadew0mcyq4q80cj` is the only thing on home (`C:\Users\User\.aoteru\misumi-backup.recipients.txt`; the tool refuses a file containing a secret key). |
| Backup | Data root 375 MB; snapshot 4.59 MB, 81 members, three SQLite databases `integrity_check` ok; took ~3 s. Staging `E:\backups\odysseus` (separate physical volume); destination folder under home OneDrive. |
| Unattended | Task `Odysseus-Backup` registered (daily 02:30, S4U, as the host user) and run once by the scheduler: `LastTaskResult=0`, snapshot verified, `Status` exit 0. Next run 2026-10-07 02:30. |
| Failure drill | Run with a missing recipients file and a scratch staging dir: exit 1, status file `ok:false`, `Status` exits 2 with `LAST RUN FAILED: -RecipientsFile not found`. |
| Key custody | The ciphertext was fetched to the laptop and `verify --deep --decrypt-identity` passed using ONLY the laptop's identity (81 members, manifest checked, three databases ok). |
| Restore | `restore ... --yes` into an isolated scratch directory in 0.8 s, 81 files; `integrity_check` ok; 220 transcript rows (all `persisted`, owner `tye`, retention policy `permanent`); the `UNIQUE(owner,domain,event_id)` constraint rejects a duplicate on a throwaway copy; `.app_key` present (44 bytes). Fernet decryption of stored fields: **not demonstrated** (no `gAAAAA`-prefixed values found; null). |
| Restored app path | The restored data directory was copied to a scratch dir on home and served by the production release on 127.0.0.1:4599 with a scratch-only token minted for owner `tye` in the COPY: `/misumi/health` 200 after 11 s; `/misumi/transcript` returned events with `retention_mode=permanent`; the export route returned 200 rows. Scratch instance stopped and removed. |
| Finding | The export returned 200 of 220 rows: `export_events` called `query_events`, which clamps to 200 per call, although `EXPORT_MAX_LIMIT` is 1000. Fix with regression tests in odysseus PR #119 (new tests fail without the fix, 73 related tests pass with it). The deployed production release still has the truncation until #119 is released. |
| Off-site | **Not achieved.** Home's OneDrive client is not running (only `OneDrive.Sync.Service`; `LastSignInTime` and engine logs date from 2025-08), so files placed in `C:\Users\User\OneDrive\MisumiBackups` are not uploaded; the task's `copied_to_destination: true` proves a local copy only. Signing in is credential-bound. Interim: the newest encrypted snapshot was copied to the laptop's working OneDrive (same personal account) and its sha256 matches the tool's report. Arrival in the cloud was not independently confirmed (null). |
| Not yet proven | Seven consecutive unattended runs (time); the `Invalidate` deletion drill and provider-side purge; the user's offline copy of the identity. The identity currently exists in ONE place. |
| Tool bug | `odysseus-backup-task.ps1 -Action Install` uses `$env:USERDOMAIN`, which is `WORKGROUP` in an SSH session, so `Register-ScheduledTask` fails with "No mapping between account names and security IDs". Worked around by setting the domain from `whoami`; the script should use `[Security.Principal.WindowsIdentity]::GetCurrent().Name`. |

## 5. Kiosk / interface box (B1)

Not physically unavailable: the box (DESKTOP-RIFPR07) answered over the tailnet, booted 2026-10-01, console session active, Edge running. The old "unreachable 192.168.4.37:8770" was the bridge binding **127.0.0.1** by design (the TLS PWA listener is :8771).

| Measurement | Result |
| --- | --- |
| Bridge | `/health` status ok, `bbc_control_plane` reachable and healthy (briefly `degraded` on first read). |
| Real prompt path (box bridge `/agent` -> production `/misumi/respond`, incognito: `persist_turn=false`, `retention_mode=off`, `history_mode=off`) | aoteru model reply 10.9 s (cold); `auto` food prompt -> **sanji**, model, 4.4 s; garden -> **ginko**, model, 2.7 s; records -> **jin**, `household-read-only`, 0.3 s. Support/handover/team fields not exercised. |
| Content defect | The records answer was an irrelevant retrieved line ("future views over the YAML") rather than an answer; grounded-path relevance is a finding, not fixed. |
| TTS (host agent :4500 `/tts`) | sanji `bm_lewis` 3.0 s (6.0 s of audio), ginko `bm_fable` 2.0 s, aoteru `bm_george` 1.7 s (4.1 s); fetch 70-100 ms; 24 kHz mono; peak 0.52-0.66, RMS 0.066-0.091, silent-window fraction 0.12-0.23 (not silent, not clipped). |
| STT engine (isolated loopback instance, :4601, kiosk untouched) | faster-whisper `base.en` CPU: word recall 17/17, 19/19, 14/14 on the synthetic TTS clips, 0.45-1.8 s each. Synthetic en-GB speech is NOT evidence for Glasgow-accent robustness (null). |
| **Spoken input is down** | Nothing listens on :4600 (the kiosk's `sttUrl`); the box's `/sttinfo` says `available:false`. Last transcript persisted 2026-10-04 11:32; the host rebooted 2026-10-04 12:19 and the registered `Misumi-Agent-Stack` task starts the agent with `-Tts -NoStt`. Starting STT resumes ambient household capture (ratified default, but conditioned on everyone in range knowing and agreeing), so it was not started. |
| Not measured (null) | End-of-speech to first audible sound, intended speaker, perceived volume/intelligibility, audible failure indication, output-device switch, box reboot, network loss as seen by the box. A screen/audio probe in the box's interactive session was declined by the tool-permission classifier and was not retried. |
| Smallest human questions | (1) May STT/ambient capture resume now (yes/no)? (2) With TTS played from the kiosk: is it clearly audible, and from the intended speaker (yes/no)? |

## 6. Security (B3) - baseline only; nothing applied

Home host baseline (read-only): BitLocker off on C: and E: (TPM present and ready; Secure Boot off); host user is an administrator with **no password** and `LimitBlankPasswordUse=0` (the account can log on over the network with a blank password if a service accepts it); no idle lock; `sshd` effective `passwordauthentication yes` and `kbdinteractiveauthentication yes` (an enabled admin account `sshuser` with a password, last logon 2026-06-12); `sshd` key list has 3 keys; RDP (3389) and SMB (445) listen on all interfaces but no allow rule exists, so Windows Firewall blocks them (only LAN-scoped allow rules for 22, 420, 4500, 7077); Sunshine has two program rules open to any source; Defender on, SMB1 off, patched to KB5129195 (2026-09-15). The production app listens on :420, the host agent on :4500.

Prepared (NOT applied; a tool-permission classifier declined it) in `C:\Users\tyeca\closeout\home_harden_A.ps1` on the laptop: LimitBlankPasswordUse=1, key-only SSH, Sunshine rules scoped to LAN + tailnet, with a 12-minute dead-man revert task. Not prepared on purpose: idle lock (meaningless while the account has no password; setting a password is a credential the user must type), BitLocker (needs the user's decision on recovery-key custody and a possible console recovery after a firmware change). Lab hardening needs a sudo password (credential-bound); the lab also exposes NFS (2049) and rpcbind (111) on all interfaces, to be checked against its firewall by someone with sudo.

## 7. Not done, and why

Sol, GLM and Opus reviews of -10/-11/-12/-09/-08b; -09b reassessment (its precondition, a GLM/Sol design review, is unmet; the correct state is still deferred); kiosk acceptance judgement; home hardening; off-site backup sign-in; PR #119 merge (its CI result could not be read: the classifier declined the check, and the merge was left for the user).
