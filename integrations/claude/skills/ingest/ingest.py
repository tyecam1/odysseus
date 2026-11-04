#!/usr/bin/env python3
"""Laptop controller for /ingest: gate check -> resumable transfer -> lab-side pipeline -> short report.

The laptop only transfers and queries. All parsing, model calls and storage happen on the registered lab host.
Usage: ingest.py ZIP [--synthetic] [--status IMPORT_ID] [--limit N]
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

LAB = "agent@dmem-hp-z2-tower-g9-workstation-desktop-pc.tail171792.ts.net"  # resolve via `am where` if this changes
REPO = "/home/agent/projects/odysseus-aoteru"
PY = f"{REPO}/venv/bin/python"
RUN = f"cd {REPO} && {PY} -m src.chatgpt_ingest"
SSH = ["ssh", "-o", "BatchMode=yes", LAB]


def ssh(cmd):
    r = subprocess.run(SSH + [cmd], capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()[-300:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip", nargs="?")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--status")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.status:
        print(ssh(f"{RUN} report --import-id {a.status}")[1]); return 0
    z = Path(a.zip)
    if not z.is_file():
        print(json.dumps({"ok": False, "error": "zip not found"})); return 1
    flag = " --synthetic" if a.synthetic else ""
    rc, out, err = ssh(f"{RUN} gate")
    gate = json.loads(out) if rc == 0 and out.startswith("{") else {"gate_a": False, "error": err or out}
    if not gate.get("gate_a") and not a.synthetic:
        print(json.dumps({"ok": False, "blocked": "Gate A (institutional lab-host privacy decision) not recorded; nothing transferred",
                          "record_at": gate.get("path")})); return 2
    h = hashlib.sha256()
    with z.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    import_id = h.hexdigest()[:12]
    inbox = f"/home/agent/data/ingestion/chatgpt-inbox"
    dest = f"{inbox}/{import_id}.zip"
    ssh(f"mkdir -p {inbox} && chmod 700 {inbox}")
    r = subprocess.run(["rsync", "-t", "--partial", "--chmod=F600", "-e", "ssh -o BatchMode=yes", str(z), f"{LAB}:{dest}"])
    if r.returncode != 0:
        print(json.dumps({"ok": False, "error": "transfer failed", "import_id": import_id})); return 1
    rc, remote_hash, _ = ssh(f"sha256sum {dest} | cut -c1-12")
    if remote_hash != import_id:
        print(json.dumps({"ok": False, "error": "hash mismatch after transfer"})); return 1
    lim = f" --limit {a.limit}" if a.limit else ""
    rc, out, err = ssh(f"{RUN} run --zip {dest} --import-id {import_id}{flag}{lim}")
    print(out or json.dumps({"ok": False, "error": err})); return rc


sys.exit(main())
