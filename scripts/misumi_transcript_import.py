#!/usr/bin/env python3
"""Import completed interface-box ambient day files into the durable transcript store.

Compatibility stage A of docs/misumi-durable-transcript-runtime.md. Reads
``ambient-YYYY-MM-DD.jsonl`` files (as pulled by the home ``MisumiTranscriptPull``
task) and posts their lines to ``POST /misumi/transcript/import``. Safe to re-run:
the server derives a deterministic event id per record, so nothing is duplicated,
and records older than the owner's retention window are skipped by the server.

Only COMPLETED days are sent: today's file is still being written and is skipped.
Nothing is deleted from the source directory.

    python scripts/misumi_transcript_import.py --dir E:\\AI\\misumi-transcripts \\
        --base-url http://127.0.0.1:420 --token-env ODYSSEUS_API_TOKEN
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CHUNK = 1000
PREFIX, SUFFIX = "ambient-", ".jsonl"


def completed_day_files(directory: Path, today: datetime.date):
    for path in sorted(directory.glob(f"{PREFIX}*{SUFFIX}")):
        stamp = path.name[len(PREFIX):-len(SUFFIX)]
        try:
            day = datetime.date.fromisoformat(stamp)
        except ValueError:
            continue
        if day < today:
            yield day, path


def post(base_url: str, token: str, lines: list[str]) -> dict:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/misumi/transcript/import",
        data=json.dumps({"lines": lines, "box_id": "interface-box"}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", required=True, help="directory holding ambient-YYYY-MM-DD.jsonl")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token-env", default="ODYSSEUS_API_TOKEN")
    parser.add_argument("--dry-run", action="store_true", help="list files and line counts only")
    args = parser.parse_args(argv)

    token = os.environ.get(args.token_env, "").strip()
    if not token and not args.dry_run:
        print(f"error: set {args.token_env}", file=sys.stderr)
        return 2
    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"error: {directory} is not a directory", file=sys.stderr)
        return 2

    today = datetime.datetime.now(datetime.timezone.utc).date()
    totals: dict[str, int] = {}
    for day, path in completed_day_files(directory, today):
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.dry_run:
            print(f"{path.name}: {len(lines)} windows (dry run)")
            continue
        for start in range(0, len(lines), CHUNK):
            try:
                counts = post(args.base_url, token, lines[start:start + CHUNK])
            except urllib.error.HTTPError as exc:
                print(f"{path.name}: HTTP {exc.code}: {exc.read(300).decode('utf-8', 'replace')}", file=sys.stderr)
                return 1
            except OSError as exc:
                print(f"{path.name}: {exc}", file=sys.stderr)
                return 1
            for key, value in counts.items():
                totals[key] = totals.get(key, 0) + int(value)
        print(f"{path.name}: sent {len(lines)} windows")
    if not args.dry_run:
        print("totals:", json.dumps(totals, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
