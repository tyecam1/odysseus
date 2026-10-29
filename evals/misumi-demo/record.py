#!/usr/bin/env python3
"""Capture recordings for replay: run each catalogued scenario LIVE in developer mode against a running disposable instance and store the
inspection exactly as returned (minus the Phase B input row), with the time it was recorded. Replay later shows it as a replay, never as live.

    MISUMI_DEMO_URL=http://127.0.0.1:18431 MISUMI_DEMO_TOKEN=ody_... python evals/misumi-demo/record.py [--out DIR]

Recordings are evidence: an existing file is never overwritten (delete it deliberately to re-record). The instance must be a synthetic
household instance so nothing private can enter a recording; the host name is dropped.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import misumi_demo  # noqa: E402  (the same validator the replay path uses)

HERE = Path(__file__).resolve().parent
SCENARIOS = ("food-stock", "evidence-anomaly", "music-simulated")


def call(base, token, scenario):
    request = urllib.request.Request(base.rstrip("/") + "/misumi/demo/run", method="POST",
                                     data=json.dumps({"scenario_id": scenario, "mode": "developer"}).encode(),
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def verified_synthetic(base, token):
    """The instance must report verified synthetic provenance (guest-ready roots) and the marker of the shipped fixture."""
    request = urllib.request.Request(base.rstrip("/") + "/misumi/demo/scenarios", headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(request, timeout=30) as response:
        listing = json.loads(response.read().decode("utf-8"))
    stamp = listing.get("provenance") or {}
    return (bool(stamp.get("synthetic_verified")) and stamp.get("marker") == misumi_demo.marker_fingerprint()
            and stamp.get("fixture_sha256") == misumi_demo.fixture_digest() and bool(listing["modes"]["guest"]["available"]))


def source_revision():
    """The commit of THIS checkout (the code that defines the scenarios and the fixture); refused when the tree is not at a clean commit."""
    root = Path(__file__).resolve().parents[2]
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "src", "routes", "config", "evals/misumi-demo/synthetic-household"],
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        sys.exit("refusing to record from a checkout with uncommitted changes to the demonstration code or fixture")
    return head


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "recordings")
    args = ap.parse_args(argv)
    base, token = os.environ.get("MISUMI_DEMO_URL", ""), os.environ.get("MISUMI_DEMO_TOKEN", "")
    if not base or not token:
        sys.exit("set MISUMI_DEMO_URL and MISUMI_DEMO_TOKEN")
    if not verified_synthetic(base, token):
        sys.exit("refusing to record: the instance does not report verified synthetic provenance")
    revision = source_revision()
    args.out.mkdir(parents=True, exist_ok=True)
    for scenario in SCENARIOS:
        target = args.out / f"{scenario}.json"
        if target.exists():
            print("kept existing recording", target.name)
            continue
        record = call(base, token, scenario)
        record.pop("phase_b_input", None)
        record["observed"]["binding"]["host"] = None
        record["capture"] = {"recorder": "evals/misumi-demo/record.py", "source_revision": revision, "fixture_sha256": misumi_demo.fixture_digest()}
        record["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ok, reason = misumi_demo.validate_recording(record, scenario)
        if not ok:
            sys.exit(f"refusing to save {scenario}: {reason}")
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print("recorded", target.name, record["observed"]["execution"]["kind"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
