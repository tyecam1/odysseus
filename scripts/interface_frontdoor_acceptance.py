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

DEFAULT_URL = os.getenv("INTERFACE_ACCEPTANCE_URL", "http://127.0.0.1:7000")


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
