#!/usr/bin/env python3
"""aoteru — laptop thin-client controller for an Odysseus/Aoteru estate
(Workstream B, docs/aoteru-long-horizon-autonomous-convergence.agent-task.md).

Deliberately a SINGLE FILE using only the Python standard library — no pip
install, no Odysseus checkout, no model weights, no database, no ChromaDB.
Everything it does is one HTTP call to a running Odysseus backend (the
lab host today; any future svc:aoteru front door later, unchanged) over
its existing REST surface (routes/estate_routing_routes.py,
/api/health, /api/ready). This file can be copied anywhere Python 3.8+
runs and used immediately.

    aoteru config set --url http://<lab-tailnet-name>:7001 --token ody_...
    aoteru status
    aoteru preflight "refactor the router" --repo odysseus
    aoteru route --capability code-fast
    aoteru ask "summarise the last 3 commits" --capability local-fast
    aoteru ask "refactor X" --repo odysseus --capability code-strong --allow-paid --implementation
    aoteru park-status
    aoteru heartbeat <repo-id>
    aoteru release <repo-id>

Config lives at ~/.aoteru/client.json (Windows: %USERPROFILE%\\.aoteru\\
client.json), created 0600 where the OS supports it. The token is never
printed by this script and is only ever sent as an Authorization: Bearer
header to the configured --url.

Minting a token: an operator with access to the Odysseus web UI (or an
admin's shell on the backend host) creates one scoped to `estate:read`
(status/route only) or `estate:execute` (also ask/run) via the existing
`POST /api/tokens` route (routes/api_token_routes.py) — this client does
not mint tokens itself, so a laptop never needs write access to the
backend's user database.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_DIR = Path.home() / ".aoteru"
CONFIG_PATH = CONFIG_DIR / "client.json"

# ask/auto/lab/home's --timeout default. The backend's own execution route
# watchdog (routes/estate_routing_routes.py's EXECUTION_ROUTE_TIMEOUT) waits
# up to 210s for the Codex worker's 180s bound to resolve before it returns
# a 504 - a client default below that can abandon a normal implementation
# call while the server is still legitimately working on it. Keep this
# strictly above the server watchdog (worker-owned bound < route watchdog <
# client timeout) so the client is always the last one to give up, not the
# first. An explicit --timeout still overrides this for callers who know
# they want something else.
_DEFAULT_EXECUTION_TIMEOUT = 240.0


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        # Best-effort on POSIX; Windows ACLs are a separate, later
        # concern (NTFS doesn't have POSIX mode bits) — the file still
        # lives under the user's own profile directory either way.
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _resolve_objective_text(value: str | None, objective_file: str | None, *, label: str = "objective") -> str:
    """Resolve the actual objective/task text regardless of transport.

    Windows argv quoting (via aoteru.cmd's `%*` batch expansion, and
    Windows command-line argument parsing more generally) corrupts a
    multiline or otherwise quote-heavy objective passed as a plain
    positional argument. --objective-file (any size, any content, never
    touches argv at all) and `-` as the positional value (read from
    stdin, same guarantee) both sidestep that entirely. Exactly one of
    positional-value / --objective-file / stdin must be used - supplying
    both a positional value and --objective-file is rejected outright
    rather than silently preferring one. Existing single-line positional
    usage is completely unaffected: a plain string value, with no
    --objective-file and no stdin marker, is returned exactly as before.
    """
    if objective_file is not None and value is not None:
        raise SystemExit(
            f"{label} was given both as a positional argument and --objective-file — provide exactly one"
        )
    if objective_file is not None:
        try:
            return Path(objective_file).read_text(encoding="utf-8")
        except OSError as e:
            raise SystemExit(f"cannot read --objective-file {objective_file!r}: {e}")
    if value == "-":
        # sys.stdin.buffer bypasses the console's locale-dependent text
        # codec entirely (relevant on Windows, where the default stdin
        # encoding depends on the active console codepage and is not
        # reliably UTF-8) - decoded explicitly as UTF-8 here instead, the
        # same encoding used for --objective-file and for the positional
        # argument's own bytes on any modern OS.
        return sys.stdin.buffer.read().decode("utf-8")
    if value is not None:
        return value
    raise SystemExit(
        f"{label} is required: pass it as a positional argument, use --objective-file <path>, "
        "or pass - as the positional argument to read from stdin"
    )


def _request(cfg: dict, method: str, path: str, body: dict | None = None, timeout: float = 30.0) -> dict:
    url = (cfg.get("url") or "").rstrip("/")
    if not url:
        raise SystemExit(
            "no backend configured — run: aoteru config set --url http://<host>:<port> --token ody_..."
        )
    token = cfg.get("token")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return {"status": resp.status, "body": json.loads(resp.read().decode("utf-8") or "{}")}
    except urllib.error.HTTPError as e:
        try:
            parsed = json.loads(e.read().decode("utf-8"))
        except Exception:
            parsed = {"detail": e.reason}
        return {"status": e.code, "body": parsed}
    except urllib.error.URLError as e:
        raise SystemExit(
            f"cannot reach {url} — is the backend up and is this host on the same "
            f"tailnet/network? ({e.reason})"
        )
    except TimeoutError:
        raise SystemExit(f"timed out waiting for {url}{path}")


def cmd_config(args: argparse.Namespace) -> int:
    cfg = _load_config()
    if args.config_action == "set":
        if args.url:
            cfg["url"] = args.url
        if args.token:
            cfg["token"] = args.token
        _save_config(cfg)
        print(f"saved {CONFIG_PATH} (url={cfg.get('url')!r}, token={'set' if cfg.get('token') else 'unset'})")
        return 0
    if args.config_action == "show":
        print(f"config file: {CONFIG_PATH}")
        print(f"url:   {cfg.get('url') or '(not set)'}")
        print(f"token: {'set (hidden)' if cfg.get('token') else '(not set)'}")
        return 0
    return 2


def cmd_status(args: argparse.Namespace) -> int:
    cfg = _load_config()
    health = _request(cfg, "GET", "/api/health")
    if health["status"] != 200:
        print(f"backend unreachable or unhealthy: status={health['status']} {health['body']}")
        return 1
    print(f"backend: reachable, status={health['body'].get('status')}")

    hosts = _request(cfg, "GET", "/api/estate/route/hosts")
    if hosts["status"] == 200:
        # `/api/estate/route/hosts` returns every host *considered*
        # (role lab/home), each tagged `eligible: bool` + `reason` — not
        # a pre-filtered eligible list. `id` was never a key in that
        # payload (the field is `host_id`), so this used to print
        # `None` for every row and, worse, printed considered-but-not-
        # eligible hosts (e.g. an unverified home) under the same
        # "eligible hosts" heading as truly eligible ones. Preserve
        # registered != reachable != verified != eligible instead of
        # promoting a host because it merely showed up here.
        considered = hosts["body"].get("hosts") or []
        eligible = [h for h in considered if h.get("eligible")]
        ineligible = [h for h in considered if not h.get("eligible")]
        print(f"eligible hosts: {len(eligible)}")
        for h in eligible:
            print(f"  - {h.get('host_id')} ({h.get('role')})")
        if ineligible:
            print(f"considered but not eligible: {len(ineligible)}")
            for h in ineligible:
                print(f"  - {h.get('host_id')} ({h.get('role')}): {h.get('reason')}")
    elif hosts["status"] in (401, 403):
        print("eligible hosts: (no/insufficient token — set one with `aoteru config set --token ...` "
              "scoped estate:read or estate:execute for full status)")
    else:
        print(f"eligible hosts: lookup failed, status={hosts['status']} {hosts['body']}")
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    cfg = _load_config()
    envelope = {
        "task_class": args.task_class,
        "repo": args.repo,
        "requirements": {"capabilities": [args.capability] if args.capability else []},
    }
    result = _request(cfg, "POST", "/api/estate/route", envelope)
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 else 1


def cmd_preflight(args: argparse.Namespace) -> int:
    """Obtain live delegation evidence before substantive work starts."""
    cfg = _load_config()
    objective = _resolve_objective_text(args.objective, args.objective_file)
    unit = {
        "task_class": args.task_class,
        "repo": args.repo,
        "capabilities": [args.capability] if args.capability else [],
        "objective": objective,
        "nondelegation_reason": args.nondelegation_reason,
    }
    if args.nondelegation_reason:
        unit["requested_route"] = "controller_retained"
    result = _request(cfg, "POST", "/api/estate/preflight", {"units": [unit]})
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs estate:read or estate:execute scope")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 and result["body"].get("ok", False) else 1


def cmd_park_status(args: argparse.Namespace) -> int:
    """Estate-wide active-lease view over HTTP
    (GET /api/estate/park/status) — the laptop-side equivalent of an
    operator's `agent status`, without needing a repo checkout."""
    cfg = _load_config()
    result = _request(cfg, "GET", "/api/estate/park/status")
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs estate:read or estate:execute scope")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 else 1


def cmd_park(args: argparse.Namespace) -> int:
    """Acquire a ParkLease on the backend host over HTTP
    (POST /api/estate/park/{repo_id}) — the laptop-side equivalent of
    `agent park`. Only a repo_id is ever sent; the backend resolves the
    real registered path and checks it's git-clean server-side (no path
    this client supplies is ever trusted)."""
    cfg = _load_config()
    path = f"/api/estate/park/{args.repo_id}"
    if args.branch:
        import urllib.parse
        path += "?" + urllib.parse.urlencode({"branch": args.branch})
    result = _request(cfg, "POST", path)
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs the estate:execute scope for `park`")
        return 1
    if result["status"] == 404:
        print(f"not registered: {result['body']}")
        return 1
    if result["status"] == 409:
        print(f"cannot park: {result['body']}")
        return 1
    if result["status"] == 503:
        print(f"backend host not registered: {result['body']}")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 else 1


def cmd_heartbeat(args: argparse.Namespace) -> int:
    """Renew the caller's active ParkLease over HTTP
    (POST /api/estate/park/{repo_id}/heartbeat) — the laptop-side
    equivalent of `agent heartbeat`. Only renews the lease the backend
    host itself already holds; it cannot renew a lease on a host it
    isn't (see routes/estate_routing_routes.py's park_heartbeat)."""
    cfg = _load_config()
    result = _request(cfg, "POST", f"/api/estate/park/{args.repo_id}/heartbeat")
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs the estate:execute scope for `heartbeat`")
        return 1
    if result["status"] == 409:
        print(f"no active lease to renew: {result['body']}")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 else 1


def cmd_release(args: argparse.Namespace) -> int:
    """Release the caller's active ParkLease over HTTP
    (POST /api/estate/park/{repo_id}/release) — the laptop-side
    equivalent of `agent release`."""
    cfg = _load_config()
    result = _request(cfg, "POST", f"/api/estate/park/{args.repo_id}/release")
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs the estate:execute scope for `release`")
        return 1
    if result["status"] == 409:
        print(f"no active lease to release: {result['body']}")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 else 1


def cmd_ask(args: argparse.Namespace) -> int:
    cfg = _load_config()
    objective = _resolve_objective_text(args.objective, args.objective_file)
    envelope = {
        "task_class": args.task_class,
        "repo": args.repo,
        "requirements": {"capabilities": [args.capability] if args.capability else []},
        "objective": objective,
        "allow_paid_escalation": bool(args.allow_paid),
    }
    if args.implementation:
        envelope["mode"] = "implementation"
    result = _request(cfg, "POST", "/api/estate/run", envelope, timeout=args.timeout)
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs the estate:execute scope for `ask`")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 and result["body"].get("ok", True) else 1


def cmd_dispatch(args: argparse.Namespace) -> int:
    """Shared body of `auto`/`lab`/`home` (execution contract's "Laptop
    Claude routing skill — required UX"). Sends the estate's real
    canonical envelope shape, `placement.requested_host` included, so
    `lab`/`home` genuinely narrow eligibility server-side (fails
    truthfully via `resolve_route` if the requested host isn't eligible)
    rather than this client silently re-implementing routing/eligibility
    logic — that would be exactly the second routing authority the
    contract forbids. Executes over `/api/estate/run`: an LLM-completion
    route against a resolved local/paid model, NOT a native interactive
    Claude Code session launched on that remote host — that separate
    remote-dispatch feature doesn't exist on the backend yet (see
    `scripts/agent`'s `agent claude`, which fails the same way truthfully
    rather than pretending)."""
    cfg = _load_config()
    task = _resolve_objective_text(args.task, args.objective_file, label="task")
    envelope = {
        "task_class": args.task_class,
        "repo": args.repo,
        "requirements": {"capabilities": [args.capability] if args.capability else []},
        "placement": {"requested_host": args.command},
        "objective": task,
        "allow_paid_escalation": bool(args.allow_paid),
    }
    if args.implementation:
        envelope["mode"] = "implementation"
    result = _request(cfg, "POST", "/api/estate/run", envelope, timeout=args.timeout)
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs the estate:execute scope for `{args.command}`")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 and result["body"].get("ok", True) else 1


def cmd_where(args: argparse.Namespace) -> int:
    """Estate-wide active `LogicalSession` view over HTTP
    (GET /api/estate/sessions) — the laptop-side equivalent of
    `agent claude where`, without needing a repo checkout."""
    cfg = _load_config()
    result = _request(cfg, "GET", "/api/estate/sessions")
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs estate:read or estate:execute scope")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 else 1


def _estate_routing_skill_md() -> str:
    return (
        "---\n"
        "name: aoteru-estate-routing\n"
        "description: Route a task to an Aoteru estate worker (lab/home) "
        "via `aoteru auto|lab|home \"<task>\"`, preflight substantial work, or list active sessions "
        "via `aoteru where`. Use when the user wants work executed on a "
        "specific estate machine instead of locally — works from any "
        "repo/session on this laptop, no local Odysseus checkout needed.\n"
        "---\n\n"
        "Checkout-free wrapper over the laptop's `aoteru` client "
        "(companion/laptop_client/aoteru.py, pipx-installed as `aoteru`) "
        "— never a second router or authority. It only talks to the "
        "estate's Odysseus backend over HTTP; never hardcode a hostname, "
        "path, repo map, model name, or credential here — always resolve "
        "through the live `aoteru` command's own output.\n\n"
        "- `aoteru preflight \"<task>\" [--repo <id>]` — obtain live "
        "host/Codex/alias evidence and the required delegation lane before work starts.\n"
        "- `aoteru auto \"<task>\" [--repo <id>] [--capability <alias>]` "
        "— resolve the best available host from live estate state and "
        "execute.\n"
        "- `aoteru lab \"<task>\" [...]` — force routing to the lab "
        "worker; fails truthfully (does not silently fall back elsewhere) "
        "if lab isn't eligible.\n"
        "- `aoteru home \"<task>\" [...]` — force routing to the home "
        "worker; fails truthfully when home is unavailable or not yet "
        "eligible (e.g. not benchmark-qualified) — report that plainly, "
        "never invent a result.\n"
        "- `aoteru where` — list active logical estate sessions.\n\n"
        "This executes via the estate's model-routing backend "
        "(LLM completion against a resolved local/paid model), not a "
        "native interactive Claude Code session launched on that remote "
        "host — that separate remote-dispatch feature does not exist on "
        "the backend yet; say so plainly if a task genuinely needs it "
        "rather than treating this as equivalent.\n\n"
        "Read the JSON the command prints. On `\"ok\": false` or a "
        "nonzero exit, report the exact error — do not retry silently and "
        "do not fabricate a successful outcome.\n\n"
        "Once inside a resolved repo/worktree, that repo's own "
        "CLAUDE.md/AGENTS.md and rules take precedence over this skill's "
        "own convenience.\n"
    )


def cmd_sync(args: argparse.Namespace) -> int:
    """Installs/refreshes the checkout-free `aoteru-estate-routing` skill
    (execution contract: "one user-scoped, Odysseus-owned Claude skill
    ... installed by `agent sync`" — this is that installer's laptop-side,
    checkout-free equivalent; `scripts/agent`'s `agent sync` remains the
    lab-side installer for hosts that do have a checkout)."""
    skill_dir = Path.home() / ".claude" / "skills" / "aoteru-estate-routing"
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = _estate_routing_skill_md()
    (skill_dir / "SKILL.md").write_text(content)
    print(json.dumps({"ok": True, "written": str(skill_dir / "SKILL.md")}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aoteru", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_config = sub.add_parser("config", help="view/set backend URL and token")
    config_sub = p_config.add_subparsers(dest="config_action", required=True)
    p_set = config_sub.add_parser("set", help="set url and/or token")
    p_set.add_argument("--url", help="backend base URL, e.g. http://hz2-workstation:7001")
    p_set.add_argument("--token", help="bearer API token minted for this laptop (estate:read or estate:execute scope)")
    config_sub.add_parser("show", help="show current config (token hidden)")

    sub.add_parser("status", help="check backend reachability and eligible hosts")

    p_route = sub.add_parser("route", help="resolve a route without executing (dry run)")
    p_route.add_argument("--task-class", default="unclassified")
    p_route.add_argument("--repo", default=None)
    p_route.add_argument("--capability", default=None, help="capability alias, e.g. local-fast, code-strong")

    p_preflight = sub.add_parser("preflight", help="classify task delegation from live estate evidence")
    p_preflight.add_argument(
        "objective", nargs="?", default=None,
        help="the objective text, or - to read it from stdin (see --objective-file for multiline/quote-heavy text)",
    )
    p_preflight.add_argument(
        "--objective-file", default=None,
        help="read the objective from this file instead of the positional argument - the robust transport "
             "for multiline or quote-heavy text, immune to shell/argv quoting (including aoteru.cmd on Windows)",
    )
    p_preflight.add_argument("--task-class", default="unclassified")
    p_preflight.add_argument("--repo", default=None)
    p_preflight.add_argument("--capability", default=None)
    p_preflight.add_argument(
        "--nondelegation-reason", default=None,
        help="fixed reason code, or 'other: ...', when explicitly retaining the unit",
    )

    sub.add_parser("park-status", help="estate-wide active park-lease view")

    p_park = sub.add_parser("park", help="acquire a lease on the backend host for a registered repo")
    p_park.add_argument("repo_id")
    p_park.add_argument("--branch", default=None)

    p_heartbeat = sub.add_parser("heartbeat", help="renew the backend host's active lease for a repo")
    p_heartbeat.add_argument("repo_id")

    p_release = sub.add_parser("release", help="release the backend host's active lease for a repo")
    p_release.add_argument("repo_id")

    p_ask = sub.add_parser("ask", help="route and execute an objective")
    p_ask.add_argument(
        "objective", nargs="?", default=None,
        help="the objective text, or - to read it from stdin (see --objective-file for multiline/quote-heavy text)",
    )
    p_ask.add_argument(
        "--objective-file", default=None,
        help="read the objective from this file instead of the positional argument - the robust transport "
             "for multiline or quote-heavy text, immune to shell/argv quoting (including aoteru.cmd on Windows)",
    )
    p_ask.add_argument("--task-class", default="unclassified")
    p_ask.add_argument("--repo", default=None)
    p_ask.add_argument("--capability", default=None)
    p_ask.add_argument("--allow-paid", action="store_true",
                        help="opt in to paid (Codex) escalation if local capability is unbound/unavailable")
    p_ask.add_argument("--implementation", action="store_true",
                       help="request lease-gated Codex workspace-write (requires --repo and --allow-paid)")
    p_ask.add_argument("--timeout", type=float, default=_DEFAULT_EXECUTION_TIMEOUT)

    for mode, mode_help in (
        ("auto", "resolve + execute a task on the best available estate host"),
        ("lab", "resolve + execute a task, forced to the lab worker"),
        ("home", "resolve + execute a task, forced to the home worker"),
    ):
        p_mode = sub.add_parser(mode, help=mode_help)
        p_mode.add_argument(
            "task", nargs="?", default=None,
            help="the task text, or - to read it from stdin (see --objective-file for multiline/quote-heavy text)",
        )
        p_mode.add_argument(
            "--objective-file", default=None,
            help="read the task from this file instead of the positional argument - the robust transport "
                 "for multiline or quote-heavy text, immune to shell/argv quoting (including aoteru.cmd on Windows)",
        )
        p_mode.add_argument("--task-class", default="unclassified")
        p_mode.add_argument("--repo", default=None)
        p_mode.add_argument("--capability", default=None)
        p_mode.add_argument("--allow-paid", action="store_true",
                             help="opt in to paid (Codex) escalation if local capability is unbound/unavailable")
        p_mode.add_argument("--implementation", action="store_true",
                            help="request lease-gated Codex workspace-write (requires --repo and --allow-paid)")
        p_mode.add_argument("--timeout", type=float, default=_DEFAULT_EXECUTION_TIMEOUT)

    sub.add_parser("where", help="list active logical estate sessions")

    sub.add_parser("sync", help="install/refresh the aoteru-estate-routing Claude skill")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "config": cmd_config,
        "status": cmd_status,
        "route": cmd_route,
        "preflight": cmd_preflight,
        "ask": cmd_ask,
        "park-status": cmd_park_status,
        "park": cmd_park,
        "heartbeat": cmd_heartbeat,
        "release": cmd_release,
        "auto": cmd_dispatch,
        "lab": cmd_dispatch,
        "home": cmd_dispatch,
        "where": cmd_where,
        "sync": cmd_sync,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
