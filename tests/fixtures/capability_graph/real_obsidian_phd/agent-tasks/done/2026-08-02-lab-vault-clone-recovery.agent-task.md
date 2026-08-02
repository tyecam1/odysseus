---
artifact_type: workflow
task_schema: agent-task/v2
task_id: 2026-08-02-lab-vault-clone-recovery
title: "Recover the lab-box vault clone from its stopped interactive rebase without losing the rescue snapshot"
status: done
priority: high
task_type: repo-hygiene-verification
created_by: claude
created_at: 2026-08-02T12:00:00+01:00
updated_at: 2026-08-02T12:25:00+01:00
executor: codex_subscription
execution_mode: handoff
architecture: single-plus-verifier
architecture_rationale: "One short sequential git recovery on shared mutable state (a single working clone). Not decomposable. Single-agent baseline is strong; a separate verifier re-derives the post-state independently because the action is authority-bearing (estate recovery)."
single_agent_baseline: "A single operator running four git commands recovers the clone; the risk is not difficulty but irreversibility, so verification, not parallelism, is the control."
execution_host: compute-box
context_budget: small
coordination_reason: "Verifier is a different model re-deriving reachability of the rescue snapshot after the abort; it does not share the implementation context."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V1_LLM_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: claude/lab-vault-clone-recovery-20260802
allowed_paths:
  - automation/review/estate/**
  - automation/review/agent-tasks/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 12-log/**
  - 10-inbox/**
  - 11-projects/**
inputs:
  - automation/review/architecture/2026-07-27-estate-recovery-disposition.md
outputs:
  - automation/review/estate/2026-08-02-lab-vault-clone-recovery.md
result_path: automation/review/estate/2026-08-02-lab-vault-clone-recovery.md
review_report_path: automation/review/estate/2026-08-02-lab-vault-clone-recovery.md
handoff_model: claude_codex_review_package
supersedes: []
duplicates: []
notes: "execution_mode is handoff, not implementation: allowed_paths are entirely under automation/review/, so the implementation write-scope class (which would require V2_HUMAN_VERIFIED) does not apply. This resolves the round-2 governance objection. Recovery is an authority-bearing action under automation/docs/dual-agreement-protocol.md. Branch deletion, force-push and history rewrite remain human-only and are explicitly out of scope. rescue/vault-conflict-20260727 must not be deleted, moved or force-updated."
---
# Recover the lab-box vault clone from its stopped interactive rebase

## Measured pre-state (recorded 2026-08-02 from the lab host)

Host: `dmem-HP-Z2-Tower-G9-Workstation-Desktop-PC` (Tailscale `100.75.149.126`).
Clone: `/home/agent/projects/vault`.

| Fact | Value |
|---|---|
| `HEAD` | `893fabc3c7224436ffd11d0f5e401776aa6529c9` (detached) |
| `.git/rebase-merge` | present (`.git/rebase-apply` absent) |
| `rebase-merge/head-name` | `refs/heads/main` |
| `rebase-merge/onto` | `8fadae32327fad7f94a0affeac528a82477bed0c` |
| `rebase-merge/orig-head` | `5c82082bc1b9fda5fbb76fad3b235e91ae2d349b` |
| `rebase-merge/msgnum` / `end` | `1` / `1` |
| `rebase-merge/done` | 1 line |
| `git-rebase-todo` | empty (no remaining steps) |
| working tree | clean: 0 porcelain lines, 0 untracked (`-uall`) |
| `git stash list` | empty |
| local branch `rescue/vault-conflict-20260727` | exists |
| `git ls-remote --heads origin rescue/vault-conflict-20260727` | `893fabc3c7224436ffd11d0f5e401776aa6529c9` |

Interpretation: the interactive rebase applied its only commit and stopped;
`HEAD` sits at the post-pick commit, which is byte-identical to the rescue
branch tip both locally and on `origin`. No uncommitted or untracked data
exists in the clone, so the rebase state holds no unowned content.

## Goal

Return `/home/agent/projects/vault` to a clean, non-rebasing state on a named
branch, while `rescue/vault-conflict-20260727` remains reachable from `origin`
at `893fabc3c`.

## AMENDMENT 1 (2026-08-02, after Sol adjudication round 1 returned DISAGREE)

Sol's mandatory pre-checks were executed read-only. They falsified this
packet's own plan. `git rebase --abort` is **withdrawn**.

### What the pre-checks found

| Check | Result |
|---|---|
| `git --version` / origin | `git@github.com:tyecam1/obsidian-PhD.git`, no lock files, no concurrent git process |
| `maintenance.auto` / `gc.auto` / `gc.reflogExpire` | all unset (defaults) |
| `rebase-merge/patch` | **0 bytes** |
| `autostash`, `refs-to-delete`, `rewritten-list` | **all absent** |
| `git-rebase-todo` | empty; `done` = `pick 5c82082bc track files` (1/1) |
| `git stash list` | 0 entries |
| ignored paths (7) | `.venv/`, four `__pycache__/`, `automation/config/settings.local.ini`, `automation/logs/`, `automation/state/` — **none tracked** in `5c82082bc` or `cde901a6`, so no restore collision |
| `assume-unchanged` / `skip-worktree` / sparse-checkout | none / unset |
| submodules | none |
| other operation state | no `sequencer`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, `BISECT_LOG` |
| linked worktrees | 3 — `vault` (this one, detached), `vault-routine-acceptance` (`codex/prepare-claude-workflows`), `vault-runtime` (`runtime/compute-box`). **`main` is not checked out anywhere.** |
| commit objects | `893fabc3c`, `5c82082bc`, `8fadae32` all readable |

### The falsifier

`refs/heads/main` is at **`cde901a6`** ("Create annual review supervision
summary…", 2026-04-21), **not** at the rebase's `orig-head` `5c82082bc`
("track files", 2026-04-16).

`main`'s reflog shows why:

```
cde901a6 main@{2026-04-22 17:32:47 +0100}: branch: Reset to origin/main
5c82082b main@{2026-04-16 18:23:26 +0100}: commit: track files
```

`main` was deliberately reset to `origin/main` on 2026-04-22 **while this
rebase was already stopped**. `5c82082bc` is not an ancestor of `cde901a6`;
`git rev-list --count 893fabc3c..cde901a6` = **50**.

`git rebase --abort` restores the original branch to `orig-head`. It would
therefore move `refs/heads/main` **backwards by 50 commits**, from `cde901a6`
to `5c82082bc`, undoing a deliberate April reset and leaving those 50 commits
locally reachable only through the reflog. That is a destructive branch move,
not a recovery. Sol's section-4 objection — "step 5 can pass while the clone is
still broken" — is confirmed concretely: the packet's own step 5 asserted
`HEAD == 5c82082bc` and `branch == main` as *success*, which is precisely the
damaged state.

### Revised action

`git rebase --quit` clears the rebase state and leaves `HEAD` where it is,
**without** restoring the original branch ref. Applied here it:

- removes `.git/rebase-merge`;
- leaves `HEAD` detached at `893fabc3c`, which equals both the local and the
  remote `rescue/vault-conflict-20260727` tip;
- leaves `refs/heads/main` untouched at `cde901a6`.

Then checking out `rescue/vault-conflict-20260727` attaches `HEAD` to a named
branch at the same commit, so the clone ends on a branch rather than detached,
with zero ref movement anywhere.

### Preserved rollback inputs (Sol amendment 3)

Captured on the host before any mutation:

- `/home/agent/rescue-snapshots/vault-rebase-merge-20260802.tar.gz`
  sha256 `b5f91fd9fff4e3a040a1670d3cb162fd8fafcfe84fcd85ff7eb63f24c27997a1`
  (all 15 `rebase-merge` files, byte-for-byte)
- `/home/agent/rescue-snapshots/vault-refs-20260802.txt` (109 refs)
- `/home/agent/rescue-snapshots/vault-reflog-all-20260802.txt` (695 lines)


## AMENDMENT 2 (2026-08-02, after Sol adjudication round 2 returned DISAGREE)

Round 2 accepted that `--quit` protects `main`, but produced four valid
counterexamples. All four are addressed below. **The `git checkout` step is
withdrawn.**

### A2.1 Host Git version bound

`git version 2.34.1`. All implementation claims below are asserted against
that version, on `/home/agent/projects/vault`, `--git-common-dir` = `.git`.

### A2.2 The checkout is withdrawn (round-2 section 3 and 7)

Sol's section 7 is accepted: `git rebase --quit` **alone** is the minimal
sufficient recovery. Adding `git checkout rescue/vault-conflict-20260727`
would have:

- run `post_checkout_hook()`, which is executable local configuration outside
  the same-tree protection;
- attached `HEAD` to the preservation branch, so any later commit in this
  clone would silently advance the rescue ref;
- added a `HEAD` reflog entry and a worktree/index traversal for zero benefit,
  since `HEAD` is already at the target OID.

Detached `HEAD` at `893fabc3c` is the **preferred** end state while this clone
is quarantined. The packet's original goal wording ("on a named branch") is
superseded: the requirement is *non-rebasing and clean*, not *attached*.

Hook state was nevertheless attested and is clean: `core.hooksPath` unset,
effective hooks dir `.git/hooks` contains **only `.sample` files**,
`remote.origin.pushurl` unset, `remote.origin.url`
`git@github.com:tyecam1/obsidian-PhD.git`.

### A2.3 Complete, restore-tested rollback input (round-2 section 5)

The three earlier artifacts were evidence, not a restorable backup. Replaced by
a byte-preserving snapshot of the **entire** git directory plus a verified
object bundle, both created with no concurrent git process and no lock file:

| Artifact | Size | sha256 |
|---|---:|---|
| `/home/agent/rescue-snapshots/vault-gitdir-complete-20260802.tar.gz` | 531,883,066 | `0a4c622e494e1d80fde57a2b7fa8dfbe1b1b6c4f147e0f29cf635b2c6d798a1a` |
| `/home/agent/rescue-snapshots/vault-atrisk-commits-20260802.bundle` | 452,795,553 | `fa21740472468cc139657b5e60d519ab0892894b9f1925804021b46802409ef1` |

The tar covers `HEAD`, `index`, all pseudorefs (`ORIG_HEAD`, `REBASE_HEAD`),
`config`, hooks, raw reflog files, the object database, and the linked-worktree
administrative state — the exact list round 2 said was missing.

`git bundle verify` reports **"The bundle records a complete history"**.

**The restore was tested, not asserted.** Cloning the bundle into a fresh
scratch directory recovered every at-risk commit with matching trees:

```
893fabc3c: RESTORED OK      5c82082bc: RESTORED OK
cde901a6b: RESTORED OK      8fadae323: RESTORED OK
tree(893fabc3c) restored=4ca67c98acd01aecaad87f2dc656c7d656d3249f source=4ca67c98acd01aecaad87f2dc656c7d656d3249f
tree(5c82082bc) restored=04b85664f3c2b3076fea45990904dd2017078974 source=04b85664f3c2b3076fea45990904dd2017078974
```

Restore procedure: extract the tar over an empty directory to reconstitute the
clone's git directory exactly, or `git clone --bare <bundle>` and fetch the
required refs into a fresh clone.

### A2.4 `5c82082bc` reachability after `--quit` (not raised by Sol; found here)

Once `.git/rebase-merge` is removed, `5c82082bc` ("track files", the only
commit that was ever local-only) is no longer referenced by rebase
administrative data. It remains referenced by `ORIG_HEAD` and `REBASE_HEAD`
and by the reflog, and its content survives as the replayed commit inside
`893fabc3c`.

Consequence: **`REBASE_HEAD` must not be deleted.** It is load-bearing for
`5c82082bc`. Round-2 section 4 correctly observed that `--quit` leaves
`REBASE_HEAD` behind; that residue is *protective* here, and is classified as
intended residual state rather than cleaned up. `5c82082bc` is additionally
preserved in both snapshot artifacts above.

## Required procedure (as amended twice)

Run under exclusive access. Stop and report on any mismatch — do not repair.

1. **Immediately before the command**, re-attest: no `pgrep git`; no
   `.git/*.lock`; `.git/rebase-merge` present; `.git/rebase-merge/autostash`,
   `refs-to-delete` and `rewritten-list` all **absent**;
   `git status --porcelain -uall` empty; `git rev-parse HEAD` = `893fabc3c`;
   `git rev-parse refs/heads/main` = `cde901a6`;
   `git rev-parse refs/heads/rescue/vault-conflict-20260727` = `893fabc3c`.
2. Record the pre-state inventory: `HEAD` file contents, `ORIG_HEAD`,
   `REBASE_HEAD`, presence of `AUTO_MERGE` / `MERGE_MSG`,
   `git rev-parse --git-path hooks`, `git config --get core.hooksPath`,
   `remote.origin.url`, `remote.origin.pushurl`, and the ignored-path list.
3. Confirm both snapshot artifacts exist with the sha256 values in A2.3.
4. `git ls-remote --heads origin rescue/vault-conflict-20260727` == `893fabc3c`.
5. **`git -c maintenance.auto=false rebase --quit`** — the only mutating
   command. Record exit status and output verbatim. No checkout. No
   `update-ref`. No branch creation.
6. Post-state re-attestation, all required:
   - `.git/rebase-merge` and `.git/rebase-apply` both **absent**;
   - no `.git/sequencer`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`,
     `BISECT_LOG`, `AUTO_MERGE`, `MERGE_MSG`;
   - `git status --porcelain -uall` **empty**;
   - `git rev-parse HEAD` == `893fabc3c`, `HEAD` still **detached**;
   - `git rev-parse refs/heads/main` == **`cde901a6`** (unchanged);
   - `git rev-parse refs/heads/rescue/vault-conflict-20260727` == `893fabc3c`;
   - `ORIG_HEAD` and `REBASE_HEAD` both still == `5c82082bc` (**expected to
     survive**, per A2.4);
   - hooks path, `remote.origin.url` and `remote.origin.pushurl` **byte-identical
     to step 2**;
   - ignored-path list byte-identical to step 2;
   - `git fsck --no-progress` reports no new corruption relative to the
     pre-state run;
   - `git ls-remote --heads origin rescue/vault-conflict-20260727` == `893fabc3c`.
7. Classify residual state explicitly, repair nothing:
   - `HEAD` detached at `893fabc3c` — intended;
   - `REBASE_HEAD`/`ORIG_HEAD` at `5c82082bc` — intended, protective;
   - local `main` at `cde901a6`, ~3 months behind `origin/main` (`38baba5d`);
   - local `refs/remotes/origin/main` stale at `009438d2`;
   - `data.incoming-*` Zotero snapshots and the stale
     `/home/agent/projects/data` mirror — out of scope, separate task.
8. Write the result file with every command and its exact output.

## Acceptance (as amended)

- clone is no longer mid-rebase;
- `refs/heads/main` did **not** move;
- `rescue/vault-conflict-20260727` resolves on `origin` to `893fabc3c` after
  the action;
- no hook ran, no remote write occurred, no ref was created or deleted;
- a restore-tested snapshot existed before the mutation;
- residual state classified, not silently repaired.

## AMENDMENT 3 (2026-08-02, after Sol adjudication round 3 returned DISAGREE)

Round 3 confirmed the Git 2.34.1 semantics but raised three objections. All
three are answered by measurement, not argument.

### A3.1 The `REBASE_HEAD` claim in A2.4 is withdrawn as stated

Round 3 is correct. `REBASE_HEAD` and `ORIG_HEAD` are top-level pseudoref names
outside `refs/*`. Being resolvable by `git rev-parse` is **not** the same as
being a durable GC root — Git's pruning roots are `HEAD`, `refs/*`, reflogs,
the index, and explicitly supplied heads.

Corrected statement:

- `5c82082bc` is **not** durably protected inside the live clone by any
  `refs/*` entry. Its in-clone survival rests on the `main` reflog entry, which
  expires.
- `893fabc3c` preserves the *tree result* of the replay. It does not preserve
  `5c82082bc`'s identity, parents, or history.
- `5c82082bc`'s dependable recovery inputs are the two retained external
  artifacts, both now restore-tested (A3.3).
- Leaving `REBASE_HEAD` in place is simply the correct Git 2.34.1 outcome of
  `--quit`. It is **not** deleted because deleting it is an unnecessary ref
  mutation, not because it protects anything.

### A3.2 All-ref inventory and executable-transport attestation

Round 3's counterexample — a `core.sshCommand` wrapper mutating a local ref
while `ls-remote` still returns the expected OID — is closed by attesting the
transport surface and by comparing **all** refs, not selected ones.

Attested on the host, 2026-08-02:

| Setting | Value |
|---|---|
| `core.sshCommand` | unset |
| `GIT_SSH_COMMAND` / `GIT_SSH` | unset |
| `core.gitProxy` | unset |
| `protocol.ext.allow` | unset |
| `url.*` rewrites | none |
| `remote.*` beyond `url`/`fetch` | none |
| `credential.*` | none |
| `alias.*` | none |
| `core.fsmonitor` | unset |
| `~/.gitconfig` | contains only `[user] email` |
| `core.hooksPath` | unset; `.git/hooks` holds only `.sample` files |

Baseline all-ref inventory captured:

- `/home/agent/rescue-snapshots/vault-allrefs-pre-20260802.txt`
  — 109 refs, `git for-each-ref --format="%(objectname) %(refname)" | sort`,
  sha256 `d3f215f9e1ab23a7e2279531e26f12f7f59a01b89428fadf1570d9c26ac9281d`

The post-state check now diffs the **complete sorted ref list** against this
file, after the final `ls-remote`, and requires byte identity.

### A3.3 The gitdir tar is now restore-tested, not merely hashed

Round 3 was right that cloning the bundle tests the bundle, not the tar. The
tar was therefore extracted into a scratch directory on the host and compared
against the live git directory.

First extraction (without `-p`) showed a real, honest difference: **permission
bits only** — source `664`/`775` versus restored `644`/`755` — because `tar x`
applies the extracting user's umask unless `-p` is given. File set and content
were already identical.

Re-extracted with `tar xzpf`:

```
files: src=5777 res=5777
MODE+SIZE+PATH with tar -p: IDENTICAL
CONTENT HASHES: IDENTICAL (5777 files)
rebase state reconstructs: YES
```

Reconstruction of the stopped rebase from the restored git directory was
demonstrated, not asserted:

```
HEAD                893fabc3c7224436ffd11d0f5e401776aa6529c9
rebase-merge        present
head-name           refs/heads/main
orig-head           5c82082bc1b9fda5fbb76fad3b235e91ae2d349b
done                pick 5c82082bc1b9fda5fbb76fad3b235e91ae2d349b track files
refs/heads/main     cde901a6b7ea03f43264908dcdd3bb9daa24eaea
rescue ref          893fabc3c7224436ffd11d0f5e401776aa6529c9
ORIG_HEAD           5c82082bc1b9fda5fbb76fad3b235e91ae2d349b
REBASE_HEAD         5c82082bc1b9fda5fbb76fad3b235e91ae2d349b
index               readable, 6112 tracked paths
5c82082bc           present
```

**Restore procedure (now tested): `tar xzpf` — the `-p` is required.**

Scope of the rollback claim, stated narrowly: these inputs are sufficient to
reverse **`git rebase --quit` alone**, which touches neither the working tree
nor any `refs/*` entry. They are *not* a full-clone backup — ignored working
tree content (`.venv/`, `__pycache__/`, `automation/config/settings.local.ini`,
`automation/logs/`, `automation/state/`) is outside the tar. That is acceptable
only because `--quit` cannot touch the working tree.

### A3.4 Exit status is a gate, not a record

Round 3's note is adopted: a non-zero exit from `--quit` can leave partial
administrative cleanup. **Exit 0 is mandatory.** On any non-zero exit, stop,
change nothing further, and report.

### A3.5 The `--quit` procedure, superseding step 5 of AMENDMENT 2

Steps 1-4 of AMENDMENT 2 stand, plus:

- 1a. Re-attest the transport table in A3.2 immediately before acting.
- 1b. Re-capture the all-ref inventory and require sha256
  `d3f215f9e1ab23a7e2279531e26f12f7f59a01b89428fadf1570d9c26ac9281d`.

Step 5 unchanged: `git -c maintenance.auto=false rebase --quit`, **exit 0
required**.

Step 6 gains, after the final `ls-remote`:

- re-capture `git for-each-ref --format="%(objectname) %(refname)" | sort` and
  require it byte-identical to the A3.2 baseline;
- re-attest the full transport table byte-identical to A3.2.

Step 7 adds to the residual classification: `REBASE_HEAD`/`ORIG_HEAD` at
`5c82082bc` are the expected Git 2.34.1 outcome and are **not** durable
protection (A3.1).

### A3.6 Rejected alternative, recorded

Round 3 offered a lower-effect option: atomically renaming `.git/rebase-merge`
to a quarantine path, preserving every administrative byte and avoiding
`save_autostash()` and `sequencer_remove_state()` entirely.

**Rejected.** It is unsupported manual git-directory surgery. `rebase --quit`
is the supported porcelain for exactly this state, its Git 2.34.1 behaviour is
now established, and the administrative bytes it removes are already preserved
in a restore-tested tar. Trading a supported command for filesystem surgery to
protect bytes that are already backed up is the wrong trade.
