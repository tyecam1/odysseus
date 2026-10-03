#!/usr/bin/env python3
"""Publish a local directory tree to a GitHub branch as ONE commit, through the Git Data API (no local checkout of the repo).

Why this exists: the long-horizon programme repeatedly lost time to shell and API transport mistakes (a BOM in a path list, nested
quoting, JSON bodies on stdin, forgotten deletions). This does the file, encoding and exit-code handling once.

    python scripts/publish_tree.py REPO BASE_BRANCH NEW_BRANCH LOCAL_ROOT MESSAGE_FILE --prefix PATH [--prefix PATH ...] [--dry-run]

* Only paths that start with a ``--prefix`` are considered, so unrelated drift between LOCAL_ROOT and the base is never published.
* A file is added or changed when its git blob sha differs from the base tree; a base file under a prefix that is missing locally
  is deleted (so a move is expressed by having the new file and not the old one). ``__pycache__`` is never touched.
* Bodies are sent with ``gh api --input <file>`` (never stdin), contents as base64 blobs, so there is no encoding or quoting layer.
* It creates the branch (or, when NEW_BRANCH equals BASE_BRANCH, fast-forwards that branch) and the commit only; opening and merging the pull request stays with the caller (``gh pr create``).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ATTRIBUTION = "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
DEFAULT_MAX_DELETES = 25


def blob_sha(data: bytes) -> str:
    """The git blob id of ``data`` (what ``git hash-object`` prints)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _wanted(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def plan(remote: dict[str, dict], local: dict[str, bytes], prefixes: list[str]) -> list[tuple[str, str]]:
    """Return ``[(action, path)]`` with action in ``new``, ``update``, ``delete`` (sorted, deterministic).

    ``remote`` maps path -> ``{"sha": ..., "mode": ...}``; ``local`` maps path -> bytes.
    """
    actions: list[tuple[str, str]] = []
    for path in sorted(local):
        if not _wanted(path, prefixes) or "__pycache__" in path:
            continue
        existing = remote.get(path)
        if existing is None:
            actions.append(("new", path))
        elif existing["sha"] != blob_sha(local[path]):
            actions.append(("update", path))
    for path in sorted(remote):
        if _wanted(path, prefixes) and path not in local and "__pycache__" not in path:
            actions.append(("delete", path))
    return actions


def too_many_deletes(actions: list[tuple[str, str]], limit: int) -> int:
    """How many deletions the plan holds when it exceeds ``limit`` (else 0). A directory prefix with an incomplete local tree turns every
    file you did not bring into a deletion; this catches that before anything is published."""
    deletes = sum(1 for action, _ in actions if action == "delete")
    return deletes if deletes > limit else 0


def _gh(method: str, path: str, body: dict | None = None) -> dict:
    command = ["gh", "api", "-X", method, path]
    temp = None
    if body is not None:
        temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(body, temp)
        temp.close()
        command += ["--input", temp.name]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    finally:
        if temp:
            os.unlink(temp.name)
    if result.returncode != 0:
        raise SystemExit(f"gh api {method} {path} failed: {result.stderr.strip()[:400]}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _read_local(root: Path, prefixes: list[str]) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d not in (".git", "__pycache__")]
        for name in files:
            full = Path(directory) / name
            rel = full.relative_to(root).as_posix()
            if _wanted(rel, prefixes):
                found[rel] = full.read_bytes()
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo")
    parser.add_argument("base_branch")
    parser.add_argument("new_branch")
    parser.add_argument("local_root")
    parser.add_argument("message_file")
    parser.add_argument("--prefix", action="append", required=True, help="path or directory prefix to publish (repeatable)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-deletes", type=int, default=DEFAULT_MAX_DELETES,
                        help=f"refuse a plan with more deletions than this (default {DEFAULT_MAX_DELETES}); raise it only for a deliberate bulk delete")
    args = parser.parse_args(argv)

    base = _gh("GET", f"repos/{args.repo}/branches/{args.base_branch}")
    base_sha, base_tree = base["commit"]["sha"], base["commit"]["commit"]["tree"]["sha"]
    tree = _gh("GET", f"repos/{args.repo}/git/trees/{base_tree}?recursive=1")
    if tree.get("truncated"):
        raise SystemExit("base tree listing is truncated; refusing to compute a diff")
    remote = {e["path"]: e for e in tree["tree"] if e["type"] == "blob"}
    local = _read_local(Path(args.local_root), args.prefix)

    actions = plan(remote, local, args.prefix)
    for action, path in actions:
        print(f"{action:<6} {path}")
    excess = too_many_deletes(actions, args.max_deletes)
    if excess:
        raise SystemExit(f"refusing to publish: the plan deletes {excess} files (limit {args.max_deletes}). A --prefix that covers a directory "
                         "you did not fully bring locally deletes everything else in it; use exact file prefixes, or pass --max-deletes for a deliberate bulk delete.")
    if args.dry_run or not actions:
        print("dry run" if args.dry_run else "nothing to publish")
        return 0

    entries = []
    for action, path in actions:
        if action == "delete":
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            continue
        blob = _gh("POST", f"repos/{args.repo}/git/blobs", {"content": base64.b64encode(local[path]).decode(), "encoding": "base64"})
        mode = remote[path]["mode"] if path in remote else "100644"
        entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
    new_tree = _gh("POST", f"repos/{args.repo}/git/trees", {"base_tree": base_tree, "tree": entries})
    message = Path(args.message_file).read_text(encoding="utf-8").rstrip() + "\n\n" + ATTRIBUTION
    commit = _gh("POST", f"repos/{args.repo}/git/commits", {"message": message, "tree": new_tree["sha"], "parents": [base_sha]})
    if args.new_branch == args.base_branch:  # commit onto an existing branch (fast-forward only, never forced)
        _gh("PATCH", f"repos/{args.repo}/git/refs/heads/{args.new_branch}", {"sha": commit["sha"], "force": False})
    else:
        _gh("POST", f"repos/{args.repo}/git/refs", {"ref": f"refs/heads/{args.new_branch}", "sha": commit["sha"]})
    print(f"branch {args.new_branch} -> {commit['sha'][:8]} (base {base_sha[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
