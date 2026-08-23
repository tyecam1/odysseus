#!/usr/bin/env python3
"""interface_frontdoor_acceptance.py — rerunnable acceptance checks for
the Aoteru/Odysseus mobile/interface front-door (Workstream G/H,
docs/aoteru-long-horizon-autonomous-convergence.agent-task.md item 7:
"acceptance tests that can be rerun verbatim when the interface PC
returns").

The interface PC is a separate, currently-unreachable machine
(config/estate.yaml: `svc:aoteru` stays `endpoint: null` until it's live —
"do not stand up a lab-hosted stand-in and call it svc:aoteru"). This
script does not care which host it's pointed at: run it against the lab
test instance today (the honest current state), and the exact same
command against the real interface PC once it's live — same checks, no
rewrite needed. It never asserts the target IS svc:aoteru; it only checks
that whatever it's pointed at behaves like a correctly-configured
front-door instance would.

Complements (does not duplicate) scripts/cold_reboot_verify.py, which
checks systemd/DB/Ollama/Chroma/park-lease health — this script checks
the mobile/companion-facing product surface: the PWA manifest is served,
protected routes correctly reject unauthenticated requests (the private-
network-assumption invariant, checked at the HTTP layer rather than only
via `tailscale serve`), and the companion pairing surface exists.

Usage:
    venv/bin/python scripts/interface_frontdoor_acceptance.py [--url http://host:port] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Corrected 2026-08-23 (final convergence pass): this defaulted to port
# 7000 for the same reason cold_reboot_verify.py's own history warns
# about — port 7000 is `odysseus-upstream-lab` (a DIFFERENT app, no
# estate_routing_routes references), not this repo. A run against the
# wrong default previously produced a coincidentally-plausible 4/4 PASS
# (see docs/aoteru-autonomous-programme-state.md workstream B/H) because
# that app happens to expose similarly-shaped auth-gated routes. Default
# now matches cold_reboot_verify.py's own APP_URL (this repo's actual
# lab-deployed port) — still overridable via --url/env for testing a
# real future interface PC.
DEFAULT_URL = os.getenv("INTERFACE_ACCEPTANCE_URL", "http://127.0.0.1:7001")


class Result:
    def __init__(self, name: str, status: str, detail: str = ""):
        self.name = name
        self.status = status  # PASS | FAIL | SKIP


def _get(base_url: str, path: str, timeout: float = 4.0) -> int:
    req = urllib.request.Request(base_url + path, headers={"User-Agent": "interface-acceptance/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def _get_json(base_url: str, path: str, timeout: float = 4.0) -> tuple[int, dict | None]:
    req = urllib.request.Request(base_url + path, headers={"User-Agent": "interface-acceptance/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            try:
                return resp.status, json.loads(resp.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except urllib.error.URLError:
        return 0, None


def check_app_identity(base_url: str) -> Result:
    """The exact regression this script previously had no defence
    against: a same-shaped wrong app (port 7000, `odysseus-upstream-lab`
    — a different codebase entirely) can answer `/api/health` and even
    401/403 on estate/companion-shaped paths, and previously produced a
    coincidentally-plausible PASS. This check requires the target to
    report the exact APP_VERSION of THIS checkout before any PASS is
    possible — a version mismatch (or no /api/version at all) fails
    identity outright, regardless of what the other checks report."""
    from src.constants import APP_VERSION
    status, body = _get_json(base_url, "/api/version")
    if status != 200 or not isinstance(body, dict):
        return Result("app identity (/api/version)", "FAIL", f"status={status}, body={body}")
    remote_version = body.get("version")
    if remote_version != APP_VERSION:
        return Result(
            "app identity (/api/version)", "FAIL",
            f"remote reports version {remote_version!r}, this checkout is {APP_VERSION!r} — "
            "likely a different application, not this repo's deployment",
        )
    return Result("app identity (/api/version)", "PASS", f"version={remote_version}")


def check_health(base_url: str) -> Result:
    status = _get(base_url, "/api/health")
    if status == 200:
        return Result("liveness (/api/health)", "PASS", f"status={status}")
    return Result("liveness (/api/health)", "FAIL", f"status={status}")


def check_pwa_manifest(base_url: str) -> Result:
    status = _get(base_url, "/static/manifest.json")
    if status == 200:
        return Result("PWA manifest served", "PASS", f"status={status}")
    return Result("PWA manifest served", "FAIL", f"status={status}")


def check_protected_routes_reject_unauthenticated(base_url: str) -> Result:
    """The private-network assumption (H item 4) checked at the HTTP
    layer, not just via `tailscale serve` — a job-submission/companion
    route must reject an unauthenticated caller even if it were somehow
    exposed beyond the tailnet."""
    checks = {
        "/api/estate/route/hosts": _get(base_url, "/api/estate/route/hosts"),
        "/api/companion/ping": _get(base_url, "/api/companion/ping"),
    }
    unauthorized = {path: status for path, status in checks.items() if status in (401, 403)}
    if len(unauthorized) == len(checks):
        return Result("protected routes reject unauthenticated", "PASS", str(checks))
    return Result("protected routes reject unauthenticated", "FAIL",
                  f"expected 401/403 on all, got {checks}")


def check_login_page_reachable(base_url: str) -> Result:
    status = _get(base_url, "/login")
    if status == 200:
        return Result("login page reachable", "PASS", f"status={status}")
    return Result("login page reachable", "FAIL", f"status={status}")


def build_report(base_url: str) -> list[Result]:
    return [
        check_app_identity(base_url),
        check_health(base_url),
        check_pwa_manifest(base_url),
        check_protected_routes_reject_unauthenticated(base_url),
        check_login_page_reachable(base_url),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL,
                         help="front-door base URL to test (default: lab test instance)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = build_report(args.url)

    if args.json:
        print(json.dumps([{"name": r.name, "status": r.status} for r in results], indent=2))
    else:
        print(f"Interface front-door acceptance — {args.url}")
        width = max(len(r.name) for r in results)
        for r in results:
            print(f"  [{r.status:4}] {r.name.ljust(width)}")

    failed = [r for r in results if r.status == "FAIL"]
    print()
    if failed:
        print(f"ACCEPTANCE: FAIL ({len(failed)}/{len(results)} checks failed)")
        return 1
    print(f"ACCEPTANCE: PASS ({args.url} — never asserted to be canonical svc:aoteru by this script)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
