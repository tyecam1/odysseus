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
    aoteru route --capability code-fast
    aoteru ask "summarise the last 3 commits" --capability local-fast
    aoteru ask "refactor X" --capability code-strong --allow-paid
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
        eligible = hosts["body"].get("hosts") or []
        print(f"eligible hosts: {len(eligible)}")
        for h in eligible:
            print(f"  - {h.get('id')} ({h.get('role')})")
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
    envelope = {
        "task_class": args.task_class,
        "repo": args.repo,
        "requirements": {"capabilities": [args.capability] if args.capability else []},
        "objective": args.objective,
        "allow_paid_escalation": bool(args.allow_paid),
    }
    result = _request(cfg, "POST", "/api/estate/run", envelope, timeout=args.timeout)
    if result["status"] in (401, 403):
        print(f"denied: {result['body']} — token needs the estate:execute scope for `ask`")
        return 1
    print(json.dumps(result["body"], indent=2))
    return 0 if result["status"] == 200 and result["body"].get("ok", True) else 1


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

    sub.add_parser("park-status", help="estate-wide active park-lease view")

    p_park = sub.add_parser("park", help="acquire a lease on the backend host for a registered repo")
    p_park.add_argument("repo_id")
    p_park.add_argument("--branch", default=None)

    p_heartbeat = sub.add_parser("heartbeat", help="renew the backend host's active lease for a repo")
    p_heartbeat.add_argument("repo_id")

    p_release = sub.add_parser("release", help="release the backend host's active lease for a repo")
    p_release.add_argument("repo_id")

    p_ask = sub.add_parser("ask", help="route and execute an objective")
    p_ask.add_argument("objective")
    p_ask.add_argument("--task-class", default="unclassified")
    p_ask.add_argument("--repo", default=None)
    p_ask.add_argument("--capability", default=None)
    p_ask.add_argument("--allow-paid", action="store_true",
                        help="opt in to paid (Codex) escalation if local capability is unbound/unavailable")
    p_ask.add_argument("--timeout", type=float, default=120.0)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "config": cmd_config,
        "status": cmd_status,
        "route": cmd_route,
        "ask": cmd_ask,
        "park-status": cmd_park_status,
        "park": cmd_park,
        "heartbeat": cmd_heartbeat,
        "release": cmd_release,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
