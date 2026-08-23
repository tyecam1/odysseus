# aoteru laptop thin client (Workstream B)

A single stdlib-only Python file (`aoteru.py`) that lets a laptop with **no
Odysseus checkout** talk to a running Odysseus backend (today: the lab
host; later: any `svc:aoteru` front door, unchanged). No pip install, no
model weights, no database, no ChromaDB — copy the one file and run it.

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

### 2. Get the client file onto the laptop

Copy `companion/laptop_client/aoteru.py` from this repo to the laptop by
whatever channel you already trust (scp, a shared drive, pasting it) —
this repo does not publish a hosted download URL for it. Anywhere on
`PATH` or a fixed folder works; it needs only a Python 3.8+ interpreter.

**Or, with `pipx` installed** (puts an `aoteru` command on `PATH`, no
manual folder/PATH management):

```
pipx install /path/to/this/checkout/companion/laptop_client
# then every command below is `aoteru ...` instead of `python aoteru.py ...`
```

`companion/laptop_client/pyproject.toml` wraps the same single file — it
adds zero third-party dependencies (`aoteru.py` itself stays stdlib-only,
verified by `tests/test_laptop_client.py`'s AST import audit); this only
gives `pipx`/`pip` an installable entry point. No `.msix` (Windows Store)
package exists yet — building one needs Windows-native packaging tooling
(`MakeAppx.exe`) this session's Linux shell cannot run or verify; a
future session on an actual Windows host is the right place to add it,
not a build produced blind.

### 3. Configure it

```
python aoteru.py config set --url http://<backend-tailnet-name>:<port> --token ody_...
```

This writes `~/.aoteru/client.json` (Windows: `%USERPROFILE%\.aoteru\client.json`),
`chmod 600` where the OS supports it. The token is never printed by this
script again.

### 4. Smoke test

```
python aoteru.py status
```

Expect `backend: reachable, status=healthy` and a list of eligible hosts.
If it instead says `cannot reach ...`, the laptop and backend aren't on
the same network/tailnet, or the backend is down — see
docs/aoteru-cold-reboot-checklist.md if it's the lab host.

## Everyday use

```
python aoteru.py route --capability local-fast              # dry-run: what would this route to?
python aoteru.py ask "summarise the last 3 commits" --capability local-fast
python aoteru.py ask "refactor X" --capability code-strong --allow-paid   # opt in to paid escalation
python aoteru.py park-status                                 # estate-wide active park-lease view
python aoteru.py heartbeat <repo-id>                          # renew the backend host's lease for a repo
python aoteru.py release <repo-id>                            # release the backend host's lease for a repo
```

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

- No installer/uninstaller package (pipx/msix) — the one-file-copy path
  above is the minimum that satisfies "no checkout required" and is
  fully testable from this session; packaging it further is real but
  lower-value work once the laptop-side round trip has actually been run
  once by the operator.
- No local job queue/async status polling — `ask` is a synchronous call
  that blocks until `/api/estate/run` returns, matching the backend's own
  current synchronous execution model (src/estate_router.py's
  `run_task()`).
- `park-status`/`heartbeat`/`release` are now here (backed by
  `GET /api/estate/park/status` and `POST /api/estate/park/{repo_id}/
  heartbeat|release`). No `park`/`where` subcommand yet — acquiring a
  lease needs repo-path resolution and a git-clean check that only exist
  in `scripts/agent` today; exposing `park` at the HTTP layer without
  that check would let a remote caller park a dirty/nonexistent
  worktree, so it deliberately stays CLI-only for now. `where` (listing
  the *current* repo's own lease from a checkout) has no laptop-side
  analogue since a checkout-less client has no "current repo" — use
  `park-status` for the estate-wide view instead.
