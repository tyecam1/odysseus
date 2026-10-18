"""Every tracked path must be valid on Windows (the supported household host), so a plain ``git clone`` of dev checks out there.

History: until 2026-10-02 the local-model benchmark wrote artefact directories named after raw model identifiers such as
``qwen3:8b``; 159 tracked files sat under 12 directories containing ``:``, so ``git clone`` failed on Windows and every household
release needed a hand-built sparse checkout. The producer now uses ``safe_path_component`` and the files were renamed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INVALID_CHARS = re.compile(r'[<>:"|?*\\\x00-\x1f]')
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def windows_problem(path: str) -> str | None:
    """Return why ``path`` (a repo-relative, forward-slash path) cannot exist on Windows, or None."""
    for part in path.split("/"):
        if INVALID_CHARS.search(part):
            return f"{part!r} contains a character Windows forbids"
        if part != part.rstrip(" ."):
            return f"{part!r} ends with a dot or space"
        if part.split(".")[0].upper() in RESERVED:
            return f"{part!r} is a reserved device name"
    return None


def _tracked_paths() -> list[str]:
    result = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=False)
    if result.returncode != 0:  # not a git checkout (for example an archive tree): walk the files instead
        return [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if ".git" not in p.parts and "venv" not in p.parts]
    return [p for p in result.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


def test_the_checker_flags_the_known_bad_shapes():
    assert windows_problem("evals/results/artifacts/run-1/qwen3:8b/x.json")
    assert windows_problem("a/b?.md")
    assert windows_problem("a/trailing./x")
    assert windows_problem("docs/aux.md")
    assert windows_problem("docs/NUL")
    assert windows_problem("evals/results/artifacts/run-1/qwen3_8b/x.json") is None
    assert windows_problem("docs/auxiliary.md") is None


def test_no_tracked_path_is_invalid_on_windows():
    problems = {path: why for path in _tracked_paths() if (why := windows_problem(path))}
    assert not problems, "paths that cannot be checked out on Windows:\n" + "\n".join(f"  {p}: {w}" for p, w in sorted(problems.items())[:20])
