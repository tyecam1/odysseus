# aoteru laptop thin client (Workstream B)

A single stdlib-only Python file (`aoteru.py`) that lets a laptop with **no
Odysseus checkout** talk to a running Odysseus backend (today: the lab
host; later: any `svc:aoteru` front door, unchanged). No pip install, no
model weights, no database, no ChromaDB — install (or just copy) the one
file and run it. **No local clone of this repository is ever required.**

## Operator bootstrap (one time)

### 1. Mint a token on the backend

From an already-authenticated session on the Odysseus web UI (or an
admin shell on the backend host), create an API token scoped
`estate:execute` (covers `status`/`route`/`ask`) or the narrower
`estate:read` (status/route only, no execution):

```
curl -s -X POST http://<backend>:<port>/api/tokens \
  -H "Cookie: <your session cookie>" \
  -F name=laptop-controller -F scopes=estate:execute
```

or via the web UI's token management page if one is wired to
`routes/api_token_routes.py`. The raw token (`ody_...`) is shown **once**
— copy it now.

### 2. Install the client on the laptop — genuinely checkout-free

**Recommended: `pipx` install straight from GitHub** — no clone, no
downloaded folder, nothing left on disk but the installed command
(pip/pipx does the fetch into a throwaway temp dir internally):

```
pipx install "git+https://github.com/tyecam1/odysseus.git@dev#subdirectory=companion/laptop_client"
# then every command below is `aoteru ...` instead of `python aoteru.py ...`
```

No `pipx`? The same URL works with plain `pip` in a venv:

```
python3 -m venv ~/.aoteru-client-venv
~/.aoteru-client-venv/bin/pip install "git+https://github.com/tyecam1/odysseus.git@dev#subdirectory=companion/laptop_client"
~/.aoteru-client-venv/bin/aoteru --help
```

Live-verified (2026-08-23): both commands above install cleanly into a
scratch venv with nothing pre-cloned, and only fetch
`companion/laptop_client/` (the client component) — not the worker/
runtime/database/model stack the rest of this repo needs.

**Single-file fallback** (no `pip`/`pipx`, or an environment that only
allows `curl`+`python3`):

```
curl -fsSL https://raw.githubusercontent.com/tyecam1/odysseus/dev/companion/laptop_client/aoteru.py -o aoteru.py
python3 aoteru.py --help
```

Also live-verified. Either path needs only a Python 3.8+ interpreter —
no separate download/copy step, no manual folder management.

`companion/laptop_client/pyproject.toml` adds zero third-party
dependencies either way (`aoteru.py` itself stays stdlib-only, verified
by `tests/test_laptop_client.py`'s AST import audit) — it only gives
`pip`/`pipx` an installable entry point for the two commands above. No
`.msix` (Windows Store) package exists — not a completion criterion
(docs/aoteru-final-convergence-activation.agent-task.md decision 5);
building one needs Windows-native packaging tooling (`MakeAppx.exe`)
this session's Linux shell cannot run or verify.

### 3. Configure it

```
aoteru config set --url http://<backend-tailnet-name>:<port> --token ody_...
```

(single-file fallback: `python aoteru.py config set ...`, same flags)

This writes `~/.aoteru/client.json` (Windows: `%USERPROFILE%\.aoteru\client.json`),
`chmod 600` where the OS supports it. The token is never printed by this
script again.

### 4. Smoke test

```
aoteru status
```

Expect `backend: reachable, status=healthy` and a list of eligible hosts.
If it instead says `cannot reach ...`, the laptop and backend aren't on
the same network/tailnet, or the backend is down — see
docs/aoteru-cold-reboot-checklist.md if it's the lab host.

## Everyday use

```
aoteru route --capability local-fast              # dry-run: what would this route to?
aoteru ask "summarise the last 3 commits" --capability local-fast
aoteru ask "refactor X" --capability code-strong --allow-paid   # opt in to paid escalation
aoteru park-status                                 # estate-wide active park-lease view
aoteru park <repo-id> --branch main                # acquire a lease on the backend host for a registered repo
aoteru heartbeat <repo-id>                          # renew the backend host's lease for a repo
aoteru release <repo-id>                            # release the backend host's lease for a repo
```

(single-file fallback: prefix each with `python `, e.g. `python aoteru.py route ...`)

`--allow-paid` only takes effect if the token has `estate:execute` scope
and the resolved local capability is unbound/unavailable — it never
forces paid execution when a qualified local route exists (same
economic-ladder rule as every other caller of
`src.estate_router.run_task`).

`heartbeat`/`release` act on whichever host is actually running the
backend process this client is pointed at (resolved server-side via
`src.estate_router.current_host_id()`) — a laptop cannot renew or
release a lease held on a *different* host through this surface; that
still requires that other host's own session/operator, same restriction
`scripts/agent`'s CLI already enforces.

## Windows

The script has no OS-specific code — `python aoteru.py ...` from
PowerShell or cmd.exe works identically once a Python 3.8+ interpreter is
on PATH (the Microsoft Store's `python` or python.org's installer both
work). A `.ps1`/`.bat` wrapper double-clickable from Explorer is a
reasonable follow-up once an operator has actually run this from a
Windows machine to confirm path/quoting behaviour — this session verified
the script only against Linux, since that's what this session's shell
access reaches (see docs/aoteru-autonomous-programme-state.md, workstream
B).

## What's deliberately NOT here yet

- `pipx install "git+https://github.com/tyecam1/odysseus.git@dev#subdirectory=companion/laptop_client"`
  is now the recommended, genuinely checkout-free install (live-verified
  2026-08-23 — nothing pre-cloned, only the client component fetched).
  No `.msix` — not a completion criterion for this programme (docs/aoteru-
  final-convergence-activation.agent-task.md decision 5); building one
  needs Windows-native packaging tooling this session's Linux shell
  cannot run or verify.
- No local job queue/async status polling — `ask` is a synchronous call
  that blocks until `/api/estate/run` returns, matching the backend's own
  current synchronous execution model (src/estate_router.py's
  `run_task()`).
- `park`/`park-status`/`heartbeat`/`release` are all here (backed by
  `POST /api/estate/park/{repo_id}`, `GET /api/estate/park/status`, and
  `POST /api/estate/park/{repo_id}/heartbeat|release`). `park` only
  takes a `repo_id` (+ optional `--branch`) — the backend resolves the
  real registered path via `src.estate_router.resolve_repo_path` and
  fails closed (409) on a dirty/unresolved worktree before ever
  acquiring a lease; no path is ever supplied by this client. `where`
  (listing the *current* repo's own lease from a checkout) still has no
  laptop-side analogue since a checkout-less client has no "current
  repo" — use `park-status` for the estate-wide view instead.
