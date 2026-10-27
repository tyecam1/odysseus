#!/usr/bin/env python3
"""Disposable two-instance deployment-isolation acceptance (synthetic data only).

Starts a Misumi-domain and a PhD-domain Odysseus on distinct loopback ports with independent temporary
data roots, source roots, identities and internal tokens, then exercises the real startup and HTTP paths in
both directions. Inputs are the Misumi `fixtures/deployment-isolation` tree (misumi.parameters.psd1,
phd.parameters.psd1, <domain>/source/canary.txt). Nothing outside the temporary root is read or written, no
live household path is touched, and only the processes this script started are stopped.

    python scripts/deployment_isolation_acceptance.py --fixtures PATH [--report out.json]
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from src.deployment_isolation import bind_credential  # noqa: E402
DOMAINS = ("misumi", "phd")
ROOT_VAR = {"misumi": "MISUMI_HOUSEHOLD_ROOT", "phd": "BBC_OBSIDIAN_PHD_ROOT"}
PASS_ENV = ("PATH", "SYSTEMROOT", "LANG", "LC_ALL")
results = []
SHARED_RAW_TOKEN = secrets.token_hex(16)


def check(name, ok, detail=""):
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    return ok


def tree_digest(root, skip=()):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file() and not any(s in p.parts for s in skip):
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def tree_contains(root, needles):
    found = set()
    for p in Path(root).rglob("*"):
        if p.is_file() and p.stat().st_size < 64 * 1024 * 1024:
            data = p.read_bytes()
            found.update(n for n in needles if n.encode() in data)
    return found


def http(port, method, path, *, form=None, body=None, headers=None, timeout=15):
    data, hdrs = None, dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except OSError as e:
        return 0, type(e).__name__


class Instance:
    def __init__(self, tmp, fixtures, domain):
        self.domain = domain
        self.port = int(re.search(r"Port\s*=\s*(\d+)", (fixtures / f"{domain}.parameters.psd1").read_text()).group(1))
        self.base = tmp / domain
        shutil.copytree(fixtures / domain, self.base, dirs_exist_ok=True)
        self.source = self.base / "source"
        self.data = self.base / "data"
        self.data.mkdir(parents=True, exist_ok=True)
        self.canary = (self.source / "canary.txt").read_text().split()[0]
        self.token = SHARED_RAW_TOKEN  # deliberately the SAME inherited value in both instances
        self.proc = None
        self.log = tmp / f"{domain}.log"

    def env(self, **over):
        env = {k: os.environ[k] for k in PASS_ENV if k in os.environ}
        env.update(
            HOME=str(self.base / "home"), PYTHONPATH=str(REPO),
            ODYSSEUS_DEPLOYMENT_ISOLATION="required", ODYSSEUS_DEPLOYMENT_ID=f"{self.domain}-acceptance",
            ODYSSEUS_DEPLOYMENT_DOMAIN=self.domain, ODYSSEUS_DATA_DIR=str(self.data),
            ODYSSEUS_INTERNAL_TOKEN=self.token, AUTH_ENABLED="true", LOCALHOST_BYPASS="false",
            APP_BIND="127.0.0.1", APP_PORT=str(self.port), **{ROOT_VAR[self.domain]: str(self.source)},
        )
        env.update(over)
        return {k: v for k, v in env.items() if v is not None}

    def start(self):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=str(REPO), env=self.env(), stdout=open(self.log, "wb"), stderr=subprocess.STDOUT)
        for _ in range(90):
            if self.proc.poll() is not None:
                return False
            if http(self.port, "GET", "/api/health", timeout=2)[0] == 200:
                return True
            time.sleep(1)
        return False

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    @property
    def auth(self):
        # The instance derives its internal credential from the env value bound to its identity and data root.
        return {"X-Odysseus-Internal-Token": bind_credential(self.token, f"{self.domain}-acceptance", str(self.data.resolve()))}


def refused_start(tmp, inst, name, expect_code, **env_over):
    """A configuration that must fail startup: non-zero exit, stable code, no private data in output."""
    p = subprocess.run([sys.executable, "-c", "import src.constants"], cwd=str(REPO), env=inst.env(**env_over),
                       capture_output=True, text=True, timeout=60)
    out = p.stdout + p.stderr
    leaks = [s for s in (str(tmp), *(d.canary for d in (A, B))) if s in out]
    check(f"startup refused: {name}", p.returncode == 78 and expect_code in out and not leaks,
          f"exit={p.returncode} code_seen={expect_code in out} leaks={len(leaks)}")


def main():
    global A, B
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", required=True, type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="odysseus-isolation-acceptance-")).resolve()
    insts = {}
    try:
        insts = {d: Instance(tmp, args.fixtures.resolve(), d) for d in DOMAINS}
        A, B = insts["misumi"], insts["phd"]
        source_digest = {d: tree_digest(i.source) for d, i in insts.items()}

        # 1. Both valid deployments start independently on their own ports.
        for i in insts.values():
            check(f"{i.domain}: starts and reports healthy", i.start(), f"log={i.log.name}")
        for i in insts.values():
            marker = i.data / ".odysseus-deployment.json"
            check(f"{i.domain}: marker binds data root to its own identity",
                  marker.exists() and json.loads(marker.read_text())["deployment_id"] == f"{i.domain}-acceptance")

        # 2-4. Both directions: nothing created in one is visible from the other.
        for x, y in ((A, B), (B, A)):
            tag = f"{x.domain}->{y.domain}"
            code, body = http(x.port, "POST", "/api/session", form={"name": f"ACC-SESSION-{x.domain}", "skip_validation": "true"}, headers=x.auth)
            sid = json.loads(body).get("id") if code == 200 else None
            check(f"{tag}: session created on source instance", sid, f"http={code}")
            code, listing = http(y.port, "GET", "/api/sessions", headers=y.auth)
            check(f"{tag}: other instance cannot enumerate the session", code == 200 and f"ACC-SESSION-{x.domain}" not in listing and (sid or "?") not in listing, f"http={code}")
            code, got = http(y.port, "GET", f"/api/session/{sid}", headers=y.auth)
            check(f"{tag}: other instance cannot fetch the session by id", f"ACC-SESSION-{x.domain}" not in got, f"http={code}")
            http(x.port, "POST", "/api/memory/add", body={"text": f"{x.canary} household fact"}, headers=x.auth)
            code, mem = http(x.port, "GET", "/api/memory", headers=x.auth)
            code, made = http(x.port, "POST", "/api/tasks", body={"name": f"ACC-TASK-{x.domain}", "prompt": "synthetic", "task_type": "scheduled", "schedule": "daily", "scheduled_time": "09:00"}, headers=x.auth)
            check(f"{tag}: scheduled task created on source instance", code in (200, 201), f"http={code}")
            code, tasks = http(y.port, "GET", "/api/tasks", headers=y.auth)
            check(f"{tag}: other instance cannot see or run that schedule", code == 200 and f"ACC-TASK-{x.domain}" not in tasks, f"http={code}")
            check(f"{tag}: memory present on source instance", code == 200 and x.canary in mem, f"http={code}")
            for path in ("/api/memory", "/api/memory/timeline"):
                code, other = http(y.port, "GET", path, headers=y.auth)
                check(f"{tag}: other instance memory {path} has none of it", x.canary not in other, f"http={code}")
            code, other = http(y.port, "POST", "/api/memory/search", form={"query": "household fact"}, headers=y.auth)  # query must not contain the canary: it may be echoed
            check(f"{tag}: other instance memory search finds nothing", x.canary not in other, f"http={code}")
            code, repos = http(y.port, "GET", "/api/bbc/v1/repositories", headers=y.auth)
            check(f"{tag}: other instance source enumeration omits foreign root and canary",
                  x.canary not in repos and str(x.source) not in repos, f"http={code}")

        # 3 (credentials). Both instances were given the SAME raw env token; each still accepts only its own bound credential.
        for x, y in ((A, B), (B, A)):
            tag = f"{x.domain}->{y.domain}"
            own = http(x.port, "GET", "/api/tokens", headers=x.auth)[0]
            crossed = http(y.port, "GET", "/api/tokens", headers=x.auth)
            raw_try = http(y.port, "GET", "/api/tokens", headers={"X-Odysseus-Internal-Token": x.token})
            check(f"{tag}: the shared raw env value itself is not a credential", raw_try[0] in (401, 403), f"http={raw_try[0]}")
            check(f"{tag}: crossed internal credential rejected", own == 200 and crossed[0] in (401, 403) and x.token not in crossed[1],
                  f"own={own} crossed={crossed[0]}")

        # 5-6. Overlap, aliasing and missing configuration fail startup, in both directions.
        for x, y in ((A, B), (B, A)):
            tag = f"{y.domain} configured against {x.domain}"
            refused_start(tmp, y, f"{tag}: equal data root", "marker_mismatch", ODYSSEUS_DATA_DIR=str(x.data))
            refused_start(tmp, y, f"{tag}: nested data root", "nested_data_root",
                          ODYSSEUS_DATA_DIR=str(x.data / "nested"))
            refused_start(tmp, y, f"{tag}: source root inside data root", "source_root_in_data_root",
                          **{ROOT_VAR[y.domain]: str(y.data)})
            refused_start(tmp, y, f"{tag}: inherited opposite-domain root", "opposite_domain_root_inherited",
                          **{ROOT_VAR[x.domain]: str(x.source)})
            link = tmp / f"alias-to-{x.domain}"
            if not link.exists():
                os.symlink(x.data, link, target_is_directory=True)
            refused_start(tmp, y, f"{tag}: symlink alias of the other data root", "path_alias", ODYSSEUS_DATA_DIR=str(link))
            refused_start(tmp, y, f"{tag}: traversal path", "path_alias",
                          ODYSSEUS_DATA_DIR=str(y.data / ".." / x.domain / "data"))
            writable = x.data / "mail"
            refused_start(tmp, y, f"{tag}: writable path in the other data root", "writable_outside_data_root",
                          ODYSSEUS_MAIL_ATTACHMENTS_DIR=str(writable))
        for key, code in (("ODYSSEUS_DATA_DIR", "missing_data_root"), ("ODYSSEUS_DEPLOYMENT_ID", "missing_identity"),
                          ("ODYSSEUS_DEPLOYMENT_DOMAIN", "missing_identity")):
            for i in insts.values():
                refused_start(tmp, i, f"{i.domain}: {key} missing", code, **{key: None})
        # Deliberately shared credential across the pair is caught by the pair check before either starts.
        shared = {i.domain: {k: v for k, v in i.env().items() if k.startswith(("ODYSSEUS_", "APP_", "MISUMI_", "BBC_"))} for i in insts.values()}
        files = []
        for d, env in shared.items():
            f = tmp / f"pair-{d}.json"
            f.write_text(json.dumps(env))
            files.append(str(f))
        p = subprocess.run([sys.executable, "-m", "src.deployment_isolation", "check", *files], cwd=str(REPO),
                           env={**{k: os.environ[k] for k in PASS_ENV if k in os.environ}, "PYTHONPATH": str(REPO)},
                           capture_output=True, text=True, timeout=60)
        check("pair check: shared internal credential refused without echoing it",
              p.returncode == 78 and "credential_collision" in p.stderr and A.token not in p.stderr + p.stdout)

        # 7. Neither instance modified the other's files; refused starts changed nothing.
        for i in insts.values():
            check(f"{i.domain}: source tree byte-identical after all cases", tree_digest(i.source) == source_digest[i.domain])
        for x, y in ((A, B), (B, A)):
            seen = tree_contains(y.data, [x.canary, f"ACC-SESSION-{x.domain}"])
            check(f"{x.domain}->{y.domain}: nothing from the source domain landed in the other data root", not seen, f"{len(seen)} marker(s)")
        for i in insts.values():
            check(f"{i.domain}: still healthy and marker intact after the refused starts",
                  http(i.port, "GET", "/api/health", timeout=5)[0] == 200 and (i.data / ".odysseus-deployment.json").exists())

        # 8. Restart persistence: marker re-verified, own state still present, still separate.
        for i in insts.values():
            i.stop()
        for i in insts.values():
            check(f"{i.domain}: restarts with the same identity", i.start())
        for x, y in ((A, B), (B, A)):
            code, mem = http(x.port, "GET", "/api/memory", headers=x.auth)
            code2, other = http(y.port, "GET", "/api/memory", headers=y.auth)
            check(f"{x.domain}->{y.domain}: after restart own memory persists, other still empty of it",
                  x.canary in mem and x.canary not in other, f"http={code}/{code2}")
    finally:
        for i in insts.values():
            i.stop()
        for i in insts.values():
            time.sleep(0)
        # Remove only the directory this run created (verified by prefix and parent).
        if tmp.name.startswith("odysseus-isolation-acceptance-") and tmp.parent == Path(tempfile.gettempdir()).resolve():
            logs = {i.domain: i.log.read_text(errors="replace")[-400:] for i in insts.values() if i.log.exists()}
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            logs = {}
    failed = [r for r in results if not r["ok"]]
    summary = {"total": len(results), "failed": len(failed), "results": results,
               "commit": subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()}
    if args.report:
        args.report.write_text(json.dumps(summary, indent=2))
    print(f"\n{summary['total'] - summary['failed']}/{summary['total']} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
