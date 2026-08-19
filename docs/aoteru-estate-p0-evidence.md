---
title: Aoteru estate P0 evidence
status: compact-evidence
owner: odysseus
as_of: 2026-08-19
parent: docs/aoteru-estate-execution-contract.md
---

# P0 — freeze / inventory / backups / capability + upstream dedup audit

Compact durable record. Do not reread unless a dependency changes.

## Environment reality (binding scope note for later phases)

Single host available to this execution session: `dmem-HP-Z2-Tower-G9-Workstation-Desktop-PC`
(24 cores, 125 GiB RAM, 984G/`nvme0n1p5`, 668G free). No second PC, no phone, no
Tailscale/VPN account, no WhatsApp connector are reachable from this session.
`tyecam1/misumi` and `obsidian-PhD` are not cloned anywhere on this host
(searched `/home/agent` to depth 4 for `*misumi*`/`*obsidian-phd*`, `~/.ssh/config`
has no second-host entry). Treat P2 (private connectivity), P6 (mobile) and any
step requiring those two repos as genuinely human/infra-gated, not as missing work
on my part — flag with `BLOCKED` per contract when reached, do not fabricate.

## Repo inventory

| repo | path | remote | branch | HEAD | status |
|---|---|---|---|---|---|
| Aoteru target (canonical) | `/home/agent/projects/odysseus-aoteru` | `tyecam1/odysseus.git` | `dev` | `30bb17e` | clean, up to date with origin |
| Upstream lab (capability source) | `/home/agent/projects/odysseus` | `pewdiepie-archdaemon/odysseus.git` | `main` | (see `git log -1`) | clean, up to date with origin |
| `tyecam1/misumi` | — | — | — | — | **not present on this host** |
| `obsidian-PhD` | — | — | — | — | **not present on this host** |

Freeze gate: both present repos are clean/pushed. No dirty work to preserve.

## Backup + restore test (upstream live data)

- Snapshot: `odysseus/backups/odysseus-backup-20260819-170622.tar.gz`
  (1717 files, 1,593,481,204 → 183,887,341 bytes, ratio 0.115)
  sha256 `673a33ef1e869547ef16b920f6c88c6d2c5a233d143d0966e09392e3aa292771`
- `odysseus-backup verify`: `ok: true`, 1717 members, first `data/.app_key`, last `data/user_prefs.json`.
- Isolated restore test (scratch dir, real `data/` untouched): restore `ok: true`;
  restored `data/app.db` = 1,553,039,360 bytes (matches source); `data/.app_key` present;
  `PRAGMA integrity_check` = `ok`; 24 tables. Scratch dir removed after verification.
- Gate: **PASS**.

## Safety fix applied (P0, invariant: no secrets in Git)

`backups/` (the `odysseus-backup` snapshot output dir, contains the Fernet key +
tokens per `docs/backup-restore.md`) was **not** in `.gitignore` in either repo.
- Target (`odysseus-aoteru`): fixed, committed this phase.
- Upstream lab: same line added locally, left **uncommitted** — not this session's
  repo to commit/push to; protective only, does not change running behaviour.

## Capability ownership map (src/services/routes/mcp_servers/skills)

File-level diff, upstream vs target, `__pycache__`/gitignored cache noise excluded:
196 raw diff lines → after noise removal, upstream has exactly **one** extra file,
target has **123** extra files (new routes: `misumi_routes.py`,
`misumi_operator_runtime_routes.py`, `memory/`, `bbc_routes.py`, `research/`,
`gallery/`, `contacts/`, `history/`, `chatgpt_subscription_routes.py`,
`device_flow.py`, plus an expanded `hwfit` service).

| capability | existing implementation(s) | canonical owner | decision | evidence |
|---|---|---|---|---|
| Data backup/restore | `scripts/odysseus-backup` in both repos; target's `list` handler is a refactor (try/except stat, no duplicate `stat()` calls) of upstream's | target (`odysseus-aoteru`) | **KEEP** (target already ahead) | diff of `scripts/odysseus-backup` list-command; target has no functional gap |
| Agent tool surface | upstream: single `src/agent_tools.py` (140 lines); target: `src/agent_tools/` package (10 modules incl. `admin_tools.py`, `document_tools.py`, `filesystem_tools.py`, `session_tools.py`, `subprocess_tools.py`, `web_tools.py`, `bg_job_tools.py`) | target | **KEEP** (target is a superset expansion, not a fork-divergence) | `wc -l`/dir listing comparison |
| MCP shared helpers (`mcp_servers/_common.py`) | present upstream only (`truncate()`, timeout constants); grepped and **zero** upstream files import it | none — dead code upstream | **RETIRE** (upstream-side only; nothing to port) | `grep -l _common mcp_servers/*.py` in upstream matches only the file itself |
| Misumi persona/routing, memory routes, research, gallery, contacts, history, BBC, ChatGPT subscription, device flow | target only | target | **KEEP** (already estate-native; upstream has no equivalent) | file-diff list above |
| Misumi JSONL memory (`src/misumi_memory.py` per canonical plan §6.1) | not found in either repo's `src/`; no `*.jsonl` anywhere under either repo; no `misumi` string match in upstream `src/` at all | **does not exist yet on this host** | **NEW required** (plan §6.1 reuse target doesn't exist here — likely lives only in the separate `misumi` repo, which is absent) | `grep -ril misumi src/`, `find -iname '*.jsonl'` both empty upstream; target's `routes/misumi_routes.py` exists but is a routes layer, not the memory capsule model itself — needs direct inspection before P4 |

Net finding: in the directories audited, the Aoteru target is already the
capability-ahead repo. This phase found **no upstream feature requiring
port/wrap** and **no duplication to retire on the target side**. The one
open item is that plan §6.1's named reuse target (`src/misumi_memory.py`)
does not exist under this name in either repo present on this host — P4 must
locate the real capsule/open-loop implementation (likely `routes/misumi_routes.py`
+ backing store, or the absent `misumi` repo) before deciding reuse vs. new.

## Gate

- [x] reproducible inventory artifact (this file)
- [x] no unpreserved dirty work (both present repos clean/pushed)
- [x] restore test for current Odysseus data (PASS, see above)

**P0: PASS.**
