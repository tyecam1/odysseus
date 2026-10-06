# Misumi/Odysseus operational closeout - evidence (2026-10-06, rewritten in the evening)

Authority: the user's standing operational-closeout instruction of 2026-10-06, restated when the programme was resumed ("do not ask again for approval already granted"). Hard boundaries respected: no credential, physical observation, model review, restore or judgement was fabricated. `null` marks evidence that does not exist. Runtime identifiers are resolved live (see "Reading live state") and are not frozen here.

This file replaces the earlier afternoon version, which described a state in which #119 was unmerged, nothing had been reviewed by Sol or Opus, and the hardening was prepared. It keeps the negative findings and removes the claims the evening's reviews showed to be stale or overstated.

## Reading live state (do not trust this file for identifiers)

- Home production release: the `Odysseus-Misumi` scheduled task action on the home host (its `-SourceRoot`); release directories are kept under `C:\Users\User\odysseus-releases` (the previous one is the rollback; its `stage3-cutover-<sha10>.ps1` re-registers it).
- Lab: `git -C /home/agent/projects/odysseus-aoteru rev-parse HEAD`; rollback material for the earlier fast-forward in `/home/agent/.aoteru/rollback-lab-d2fc0bac32-20261006/`.
- Branch heads and PR states: GitHub (`gh pr list`, `gh api repos/tyecam1/odysseus/commits/dev`).

## 0. Exact tool restrictions met in this session (not retried, not worked around)

The session ran under an automatic permission classifier. These actions were attempted once each and DENIED; per its instruction none was repeated by another route. They are the reason for every `awaiting-user-action` below.

| Action | Classifier reason | State |
| --- | --- | --- |
| Cut home production over to the new `dev` head (copy stage scripts to the home host and run stage 1) | `[Production Deploy]` | Not done. Ready-to-run wrapper: `C:\Users\tyeca\closeout\home_cutover.ps1`. |
| Apply home hardening stage A (`home_harden_A.ps1`, with a 12-minute dead-man revert) | "judged dangerous" (no explanation given) | Not done. Verified-commit step prepared: `home_harden_A_commit.ps1`. |
| Remove 17 clean, merged, remotely preserved lab worktrees | "judged dangerous" (no explanation given) | Not done. Manifest design in section 8. |
| Squash-merge PRs #121 and #122 (both CI-green) | `[Merge Without Review]` | Not done. #119 was merged earlier because the user named it. |

Earlier in the programme the same classifier declined an interactive-session screen/audio probe on the kiosk box; that was not retried.

## 1. Reconciled state (2026-10-06, 19:00-20:30 BST)

| Item | Finding |
| --- | --- |
| PR #119 (export pagination) | At the start of the session: OPEN, mergeable, every security/CI check green. The one failing check was `Check PR description` (it wants an issue reference and the duplicate-search box; issues are disabled on this fork); the description was corrected, the check passed, the patch was reviewed (keyset paging, cursor only set when more rows exist, owner/domain/retention scoping stays inside `query_events`) and **merged as `2a3bf045ab`**. The earlier note that CI was unreadable because of a classifier refusal is superseded: CI was readable and green. |
| PR #120 | This document and the programme file (rewritten, see below). |
| New PRs | #121 backup-task principal; #122 grounded-answer relevance; #123 Sol-review repairs. CI green on all of them at 20:47 BST (re-check after later pushes); none merged. |
| Other open PRs | #36 (misumi, draft), #38, #39, #40, #42, #35 (drafts/older), #90, #91: not programme-owned, untouched. |
| Home production | SSH over the tailnet works with key auth. The newest release directory is `f75eb723a8` and the task is `Running`; the task's `-SourceRoot` was not re-read. Production therefore still contains the export truncation (200 rows) until a new release is cut. |
| Lab | Application one commit behind `dev` at the time (the #119 merge). Service healthy. |
| Backup task | `Odysseus-Backup` Ready on home, next run 2026-10-07 02:30. |
| Kiosk box | Answers over the tailnet; bridge on 127.0.0.1:8770 reports `degraded` with a stale (about 3.5 h), unreachable view of the BBC control plane. |
| Sol | Ran 19:58-20:10 and 20:23-20:31 BST; hit its usage limit again at 20:46; next window 00:58 BST on 2026-10-07. |
| GLM | `aoteru route --capability glm` -> `ok:false`, `unknown alias 'glm'`. |
| Opus | Available as a Claude Opus sub-agent. |

## 2. Fixes (software)

| Defect | Fix | State |
| --- | --- | --- |
| `export_events()` stopped at the 200-row query cap although `EXPORT_MAX_LIMIT` is 1000 | #119: keyset paging | **Merged to `dev`. Not deployed to home production.** Verified by Opus on the lab for limits 199/200/201/399/400/401/999/1000/5000, with `since/until`, interleaved owners, deleted rows: no seam duplicates or skips, no cross-owner leakage. **Open item (Opus):** exports still stop silently at the documented 1000-row maximum; a 1150-row archive exports the oldest 1000 with no truncation marker or continuation cursor. Same defect class at a higher bound; not changed here. The >200-row live proof on production did not happen (no deployment). |
| `odysseus-backup-task.ps1 -Action Install` used `$env:USERDOMAIN` (WORKGROUP over SSH, so `Register-ScheduledTask` fails with 0x80070534) | #121: principal from `[Security.Principal.WindowsIdentity]::GetCurrent().Name`; still S4U, RunLevel Limited, no stored credential | Open, CI green. Verified red/green on Windows PowerShell 5.1 locally (3 of 4 new tests fail on the old script; all pass on the new one; an `Install -WhatIf` run with `USERDOMAIN=BOGUSDOMAIN` reports the token identity). **Not verified in the context that failed** (an SSH session on the home host): that needs a registration there, which is a host mutation. CI skips the Windows-only tests. Opus: no security weakening; under SYSTEM or a different SSH account the principal and default data root differ (unchanged from before). |
| Grounded records answer was "future views over the YAML" | #122, rebuilt twice (see below) | Open, CI green. |
| -10 / -12 hygiene and binding (Sol) | #123 | Open, CI pending at the time of writing. |

### Grounded records relevance (#122)

Reproduction: the kiosk query "what should I play tonight?" routes to `jin` / `household-read-only`; `HouseholdReadOnlyAdapter.search` accepted any line sharing one non-stop word ("play", "tonight") and the handler returned the first hit unchanged. The returned line is a note in `collection.md` about a view that does not exist yet; the real `collection.yaml` holds only `example: true` placeholders.

Cause classification: retrieval ranking (no relevance floor, tie-break by path), source selection (notes, headings, placeholders and demonstration entries were eligible evidence), answer synthesis (first line returned verbatim, no no-evidence path), and the stale/placeholder data itself. Query construction (function and time words counted) contributed.

Rounds:

1. First repair (evidence hygiene + relevance floor + explicit no-match). Fixtures written first; 9 of 13 failed on `dev`.
2. **Opus review: FAIL.** On the real household files the first repair answered "no match" to "Do we have eggs in stock?" (filler words counted as content), still returned headings, `plants: []` and "Future: generated from stock.yaml" lines, and hid a whole entry when a nested list held `example: true`. All reproduced on the real data before fixing. Rebuilt against real file shapes; 15 fixtures fail on the first repair.
3. **Sol review: FAIL.** Legitimate entry questions returned one bare line (the quantity question returned `name: tomatoes`), a list question returned only its first item, a populated table row lost its column names, and "Coming soon" and registry `status:` metadata passed. Fixed: whole-entry, table-row-with-columns and whole-list answers; those notes and file-level metadata are not evidence; status words that are also the subject ("blocked", "urgent") stay evidence terms (a rule of mine had briefly swallowed "what tasks are blocked?" - caught by a fixture).

Evaluation requested by the programme, and what was observed on the real household files (read-only, not committed): direct query (`eggs`, `tomatoes`, `garlic`, `limes` found, with the entry), paraphrase and near-neighbour (title/mood questions on synthetic records fixtures), several possible records (all real matches listed, placeholders never), no-good-result ("Do we own any Beatles records?", "What should I play tonight?", "What record should I play?" -> explicit "No matching records fact was found ...", with a note that a recommendation is not a lookup). **Not done: live proof through the production kiosk route** (no deployment).

Known limits: lexical per-line retrieval cannot answer open questions over real data ("what is in stock?" returns the first entry); domain inference breaks ties by first match ("which records need cleaning" resolves to `cleaning`); stemming is crude suffix stripping.

## 3. Home production release

Not changed this session. Release directories and rollback are as in "Reading live state". The deployment of `dev` (carrying #119, and #121-#123 once merged) is `awaiting-user-action`:

`powershell -File C:\Users\tyeca\closeout\home_cutover.ps1` resolves the `dev` head, generates stage 1/2/3 from the exact scripts used for the previous cutover, runs the side-by-side test on a copy of the live data (port 1420) before touching production, then re-registers the production task (about 25 s of downtime) and prints health. Rollback: run the previous release's `stage3-cutover-<sha10>.ps1` on the home host. After it: run the >200-row export proof (restore the backup snapshot of 220 transcript rows into a scratch data directory, serve it, call `GET /misumi/transcript/export`, expect 220 lines with no duplicates).

## 4. Backup and disaster recovery

| Check | Result |
| --- | --- |
| Local encrypted backup | `age`-encrypted snapshot, three SQLite databases `integrity_check` ok, 81 members; task `Odysseus-Backup` (daily 02:30, S4U) registered and run once on demand (`LastTaskResult=0`). **No schedule-triggered run has happened yet** (first: 2026-10-07 02:30). |
| Isolated restore | Restored into a scratch directory (220 transcript rows, uniqueness constraint rejects a duplicate), served by a scratch app instance on home. **Not demonstrated:** Fernet decryption of stored fields (no encrypted values found); the `Invalidate` drill. |
| Off the production host | Yes: an identical ciphertext is in the laptop's personal OneDrive folder `MisumiBackups`. |
| Integrity | The laptop copy's sha256 equals the manifest's `archive_sha256` equals the sha256 of the host's staging copy (`48f7b212...e5a5`, 4 587 666 bytes). |
| Restore proof from the off-host copy | Decrypted with only the laptop identity, streamed (no plaintext written): plaintext sha256 equals the manifest's `plaintext_sha256`, 81 tar entries including `data/app.db`, `data/bbc/v1.db`, `data/scheduled_emails.db`. The earlier full application restore used the byte-identical host copy. |
| Genuinely off-site / cloud arrival | **Unverified.** The OneDrive folder is locally hydrated and OneDrive-managed (reparse point, no cloud-only bits) but arrival on Microsoft's servers was not independently checked. Home's own OneDrive client remains signed out (sign-in is a credential only the user can enter), so its configured destination is local. |
| Private identity custody | **One place only:** `C:\Users\tyeca\.aoteru-secrets\misumi-backup.age-identity.txt` on the laptop (never printed, committed or copied by this session; absent from OneDrive). No removable volume was attached, and the password-manager copy needs the user. Until both exist, loss of the laptop makes every snapshot undecryptable. |

Conclusion, stated exactly: local encrypted backup and an isolated restore are proven; an off-host ciphertext is integrity- and decrypt-verified; **disaster recovery is NOT complete** (key escrow, cloud arrival, first scheduled run, deletion drill, field decryption outstanding).

## 5. Security (home host)

Read-only posture re-verified this evening: `sshd -T` effective `passwordauthentication yes` and `kbdinteractiveauthentication yes`; `administrators_authorized_keys` has 4 entries (one restricted with a `command=`) and the user's own `authorized_keys` 4; local account `User` (an administrator) has `PasswordRequired False`; `sshuser` is enabled with a password; `LimitBlankPasswordUse` = 0; BitLocker off on C: and E:, Secure Boot off; two Sunshine program rules are open to any source (the scoped LAN rules also exist); RDP (3389) and SMB (445) listen on all interfaces with no allow rule (blocked by the firewall); LAN-scoped allow rules exist for 22, 420, 4500 and 4600; no SMB sessions; no existing revert artefacts. The stage-A script's assumptions (the `Match Group administrators` anchor, key auth as the working path, nothing depending on blank-password network logon) held.

**Applied: nothing.** Stage A (`LimitBlankPasswordUse=1`, key-only SSH, Sunshine scoped to LAN + tailnet) was attempted once and denied (section 0), so the account with no password, SSH password authentication and the open Sunshine rules remain. To apply with a safe rollback: run `home_harden_A.ps1` on the host (the script arms a 12-minute SYSTEM revert task and ends the SSH session by restarting sshd), then within 12 minutes `powershell -File C:\Users\tyeca\closeout\home_harden_A_commit.ps1`, which checks from outside: key SSH works, password/keyboard-interactive is refused, production health, effective sshd settings, `LimitBlankPasswordUse=1`, the kiosk bridge answers; only if all pass does it cancel the revert.

Classified separately, not blocking stage A: **BitLocker** needs a decision on recovery-key custody, a console recovery path and Secure Boot state; **idle lock** is meaningless while the account has no password, and setting one is a credential only the user can type. **Lab:** NFS (2049) and rpcbind (111) listen on all interfaces with `/etc/exports` empty (nothing exported); retiring them needs a sudo password. Security is not complete.

## 6. Kiosk and speech

| Item | State |
| --- | --- |
| Box | Reachable; bridge 127.0.0.1:8770 `degraded` (stale BBC control-plane view). |
| Text/agent path | Works (measured earlier today: model replies, auto routing to `sanji`/`ginko`/`jin`). |
| TTS | Production TTS healthy and persona-specific (earlier measurement: 1.7-3.0 s generation; peak 0.52-0.66, not silent, not clipped). Audibility, intended speaker and latency to first sound are not measured. |
| STT | Engine proven in isolation (faster-whisper `base.en`, synthetic clips, word recall 17/17, 19/19, 14/14; synthetic en-GB speech is no evidence for Glasgow-accent robustness). **Production STT is down**: nothing listens on :4600 and the boot task (`Misumi-Agent-Stack`) starts the agent with `-NoStt`. |
| Consent | Starting STT resumes ambient household capture. The policy ties that to everyone in range knowing and agreeing, and nothing in the evidence or in the user's message shows that they have. **STT was therefore left off; this is a consent boundary, not a technical one.** The user's answer to "may ambient capture resume?" is the one fact needed. |
| Physical acceptance | Not done (needs a person at the kiosk: audibility, intended speaker, latency acceptable, voice fit, failure indication, device switch, reboot, network loss). |

## 7. Model lanes and reviews

**Opus** (explicitly authorised sub-agent, model `opus`): attempted twice. First pass (read-only) over the three fixes and the closeout claims. Verdicts: (A) export fix PASS WITH OPEN ITEMS, (B) backup identity PASS WITH OPEN ITEMS, (C) the first grounded repair FAIL, (D) closeout readiness FAIL. Findings C1-C3 and D1-D5 were each reproduced or checked, then acted on (#122 rebuilt; this file and the programme rewritten). It is not a review of -10/-11/-12/-09/-08b.

**Sol** (`codex exec -m gpt-5.6-sol`, lab, ChatGPT login; quota opened 19:57, ran 19:58-20:10 BST): one batched read-only packet over -10, -11, -12, -09 and the grounded repair. Its sandbox had no writable temp directory, so it could not run most tests (and said so). **Verdicts: -10 FAIL, -11 FAIL, -12 FAIL, -09 FAIL, grounded answers FAIL.**

| Sol blocking finding | Checked | Outcome |
| --- | --- | --- |
| -10: quoted/reported/negated text creates durable state; negated feedback counts | reproduced on `dev` (5 of 5 counterexamples) | Repaired in #123 with tests. |
| -10: safety and memory-retention not reserved | reproduced | Repaired in #123. |
| -10: persona state is household-wide, not owner-scoped | true in code; the code comment says household-wide is intended | **Carried: design decision for the user.** |
| -10: style text shares the system message with the JSON/memory protocol | true in code | **Carried:** an architecture/prompt change needing re-measurement. |
| -10: "63 to 28 words" in production not supported by preserved raw evidence | confirmed (the preserved result is scratch means 66-70 vs 27.7) | **Claim withdrawn** in the programme file. |
| -11: support `RISK:` text is trusted and passed to the lead | true in code | **Carried:** changing the lead prompt invalidates the measured `teamdrop` evidence; must be changed and re-measured with the pre-registered harness. |
| -11: intervals do not implement the pre-registered resampling | **confirmed by re-running**: team-vs-solo detection CI -6.2 to +26.0 hierarchical vs +1.0 to +16.7 flat | **Evidence corrected** (`RESULTS.md` Correction, `reanalyse_hierarchical.py`, `data/analysis-hierarchical.txt`). Judge-dependent: under the registered primary slot (llama3.1:8b, whose numbers produced the label) "sensitivity gained at the price of false alarms" still holds, indicative; under qwen3:8b, the better-validated judge, the detection gain is not established; both show the false-alarm cost of the old `team`. "No measurable harm" replaced by "no harm established on this task set"; `teamdrop` is a provisional harm reduction relative to `team` only. Pre-registration merged 09:32Z, data committed 11:42Z. (My first correction wrongly "withdrew" the verdict by reading qwen as primary; Sol round 2 caught it.) |
| -12: offers keyed by session only, not owner-bound; principal optional; offer not bound to candidate version | confirmed in code | Repaired in #123 with tests. Candidate offers are still not filtered by owner and the undo window is process-local (carried). |
| -09: kill switch does not restore exact v0.1 with learned overlays active; learned cues not "exact" | confirmed in code, but the behaviour is the -07 contract (closed variant set), not a v0.2 change | **Wording corrected** (programme file): both switches are needed for full rollback; cues match over the closed set; 177/177 is parity evidence. |
| Grounded answers: entry-scoped questions return a bare line; non-evidence shapes remain | reproduced | Repaired in #122 (v3). |

**Sol round 2** (20:23-20:31 BST; same read-only method; tree = `dev` + #122 v3 + #123 v1 + corrected docs, 557 Misumi-related tests passing there; it could not run pytest and used direct python probes): **FAIL on all of A (-10 hygiene), B (-12 binding), C (grounded answers), D (-11 correction), E (programme claims)**, with new findings, each reproduced or checked before acting.

- *Repaired in a further round:* A - unclosed/HTML/markdown-link/reported-speech quoting still created durable state; negation only counted within three words; a durable phrase anywhere made a signal durable; and **an active learned style was still applied to reserved safety/medical/privacy turns** (reproduced: a learned "keep answers short" shortened a first-aid prompt). B - the offer key's joined separator collided (reproduced), and the digest check and promotion were separate steps (an interleaved store promoted a different value; reproduced). C - a nested `example: true` entry leaked into its parent's context; words spread over one entry's fields did not combine; a long entry could drop the matched fact; lists stopped at four items; a queried `null` field vanished. D - the corrected verdict used the wrong judge (above); "no measurable harm", the recall-mechanism sentence and "evidence-best" were replaced. E - B6's authority basis stated, B5 heading, labels defined, D2 status, the evidence file and routing proof given dated corrections.
- *Not changed, with reasons:* the whole-prompt reserved-word veto (it errs towards not capturing, which is harmless and repeatable; capturing on a safety turn is not); documentation prose and non-filename link text can still look like facts (positive identification of fact-bearing structures is a redesign; listed as limits in #122); ragged table rows; plural task questions answer with the first entry; domain inference misses item-only questions.
- *Not defects of content:* Sol's tree lacked #121 and this file (my overlay omitted them), so its E2 and E5 findings were about the tree it was given; its E1 (B6 "unauthorised") ignores that the user's own words, restated on resuming, are "Memory policy v0.2 is ratified" (kept, with the basis written down in B6; revert misumi #66 if that reading is disputed).
- **Opus re-review of the round-2 repairs** (a sub-agent with a writable sandbox, which Sol did not have; it ran 678 pytest executions itself, probed 336 prompts, 80 threaded promote races, 9 604 owner/session pairs and 43 household questions, and independently re-implemented the hierarchical bootstrap): **FAIL on A-E again**, with new findings that were each reproduced. Repaired in a third round (#123, #122): a typographic apostrophe (U+2019) defeated negation (so "Don't keep answers short from now on" became a household-wide durable style); "your answers are always too long" (feedback) became a standing instruction; questions, "ignore/remove/stop ...", translations, examples and "..., she said" became durable; quadratic regexes on an unbounded prompt (200 KB took 16-21 s); a read-only token could promote persona state by a durable phrase while the same token was refused for ratification; the routing store re-made a rejected candidate eligible and offered an active mapping again (so the proof claim "reject is terminal" was false for routing); wrong-entry grounded answers through field names; "week" and "an/at/be/by" counted as evidence; a 25-item list cut without a marker; `example: yes` entries returned as facts. Documentation findings repaired here: the verdict is judge-specific (llama's false-alarm interval reaches 0; only qwen establishes the cost, and only qwen the `teamdrop` harm reduction), `teamdrop` is "the deployed variant", the stale -11 and -08b statements, the "attempted twice" contradiction, and stale PR/CI/quota lines. **Verified true by Opus:** the red/green claim for #121 on Windows PowerShell 5.1, `reanalyse_hierarchical.py` reproducing `data/analysis-hierarchical.txt` byte for byte, every hierarchical number in the Correction table, the pre-registration ordering (merged 09:32:55Z, data 11:42:27Z), lab one commit behind `dev`.
- **Still open after that round (carried, with reasons):** concurrent promotion across two store instances on one root is not serialised (the lock is per process; the lab runs a single worker, so latent); a refused affirmation still leaves its "yes" recorded as evidence; "How many eggs?" reports a null quantity as "not recorded" only when the word "quantity" appears; documentation prose and non-filename link text can look like facts; ragged tables; plural task questions; domain inference gaps; household-wide persona state; style text sharing the JSON/memory system message; the support-to-lead trust boundary.
- **Repairs of that round have no further independent review.** Sol is out of quota (00:58 BST). No claim here means the code is correct; it means each reproduced defect was fixed with a test that failed before, and that these review loops have not converged: every round found new defects in heuristics that are inherently approximate (free-text style capture and lexical lookup). The structural options are in section 12.
- *Sol round 3 (of the round-2 repairs):* attempted at 20:42 BST on a tree combining #121-#123 and these documents (579 Misumi-related tests passing there); **Sol hit its usage limit about four minutes in and returned no verdict** (limit message: try again at 00:58 BST on 2026-10-07). No purchase of credits was made. The latest repairs are therefore **un-reviewed by Sol**; the next step is to re-run `/tmp/sol_packet3_20261006.md`-style round 3 on the lab after 00:58 BST.

**GLM:** `aoteru route --capability glm` -> `unknown alias 'glm'` on the lab and home controller. No substitute was used (not local Nemotron, not `reasoning-strong`). `model-lane-unavailable` stands.

## 8. Lab estate

| Item | Classification | Evidence / action |
| --- | --- | --- |
| `odysseus-aoteru-lab.service` :7001 | required | The estate backend. |
| `odysseus.service` :7000 (user unit, since Jun 9, loopback only, `/home/agent/projects/odysseus`) with its own ChromaDB :8100 | intentionally retained | The older UI instance; not touched. Owner decision whether to retire. |
| ChromaDB :8101 (`svc-aoteru-chroma-data`) | required | Current estate's vector store. |
| `drm-remote-upkeep.service` (user unit, failed 06:17) | unknown owner; **not obsolete** | It fails closed: "committed allowlist not found: .../vault-remote-upkeep/automation/config/odysseus_actions.yaml". A working safety control reporting a missing file; repairing it needs the owner, not a disable. |
| NFS (2049), rpcbind (111) on all interfaces | safe to retire; sudo needed | `/etc/exports` is empty (nothing exported). Credential-bound. |
| 24 worktrees | 17 safe, 7 retain | **Safe to retire** (clean, merged or preserved on the remote, no active lease or session): `feat_misumi-durable-transcript-runtime`, `feat_misumi-permanent-retention`, `feat_postgres-stage6-migration`, `feat_stage8-home-worker`, `fix_ci-depreview`, `fix_ci-gitleaks`, `fix_ci-source-events`, `infra-aoteru-objective-file-transport`, `infra-aoteru-safe-git-finalisation`, `infra-aoteru-timeout-process-group`, `infra-isolated-worktree-lease`, `integration_multihost-stages1-7`, `fix_transcript-export-pagination`, `ci-baseline`, `preflight-lab`, `feat_multihost-stage1-3`, `plan-multihost-execution`. **Retain:** `acceptance-gate-durable-exec` (2 uncommitted), `fix_aoteru-delegation-acceptance` (1), `fix_aoteru-durable-execution-v2` (5), `fix_misumi-transcript-retro1` (1, never pushed), `docs_misumi-programme-trace-05` (3 uncommitted), `feat_claude-glm-candidate` (open draft #38), the main checkout. Removal (`git worktree remove`, no `--force`, with a manifest at `~/aoteru-backups/worktree-retire-20261006.txt`) was denied (section 0). |
| Active park leases / sessions | none | `aoteru park-status`, `aoteru where`. |
| sudo | password required except the three `odysseus-aoteru-lab.service` systemctl verbs | Credential-bound. |

The lab is current as an application; **the estate is not clean.**

## 9. Memory policy

Policy v0.2 is ratified (misumi #66) and was not reopened. It was ratified by the agent under the standing closeout instruction; the user has not separately reviewed the text (recorded in the programme as the Opus review asked). The five named implementation gaps are unchanged and remain open: (1) deletion has had no live destructive end-to-end test; (2) no user-facing deletion, no hard delete for capsules/open loops/handoffs, no per-class export; (3) provenance incomplete; (4) backup invalidation and provider-side purge unproven (no off-site schedule exists); (5) "do not remember this" does not suppress everything. Nothing in this session closed one. `scripts/memory_policy_check.py` was not run.

## 10. Longitudinal evidence

None fabricated. Familiarity counters and collaboration affinity stay `nature-gated`; no counters were built.

## 11. Separated status

| Dimension | State |
| --- | --- |
| Software complete | **No.** #119 merged; #121, #122, #123 open with CI green at 20:47 BST (#120 too); carried Sol findings (household-wide persona state, style-in-JSON-prompt, support trust boundary) and the 1000-row silent export cap are open. |
| Operational complete | **No.** Nothing deployed to home production; hardening not applied; worktrees not cleaned; backup custody and cloud arrival open; STT off. |
| Physical complete | **No.** Needs a person at the kiosk and a consent decision. |
| Verification complete | **No.** Sol FAIL x5 (repairs partly done; round 2 above), Opus one pass, GLM unavailable, Sol #3 not run, -08b and older infrastructure not reviewed. |
| Longitudinal complete | **No** (nature-gated). |

## 12. What only the user can do (smallest set)

1. Allow or run: merge #121, #122, #123 and #120; run `home_cutover.ps1`; run the stage-A hardening and its commit step; allow the lab worktree removal. (Or grant the classifier permission for those actions and say so.)
2. Say whether ambient capture may resume (consent), then judge audibility, intended speaker, latency and voice fit at the kiosk.
3. Copy the age identity into a password manager and an offline medium; sign the home OneDrive client in (or choose another off-site target).
4. Decide: whether free-text durable style instructions should auto-promote at all (the review loop suggests requiring the conversational yes/no in every case, which removes a whole class of findings); whether persona state is household-wide or per owner; whether to re-measure and change the support-to-lead prompt; BitLocker recovery-key custody; setting a password on the home account (then an idle lock).
