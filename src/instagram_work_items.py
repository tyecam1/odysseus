"""Owner work items for routed Instagram Saved items (directive stage 6, governed handoff).

After each handoff run, when enough NEW items have been routed to a domain, this module writes one aggregate digest and
(unless switched off) opens a pull request in the owning repository so that owner can review and merge it under its own
rules.  It never merges, never pushes to a default branch, and never writes outside the owner's review/inbox area.

Privacy: a digest holds only counts, confidence and fixed-vocabulary cue words.  Permalinks, caption text and payloads
never leave the lab (the Odysseus repository is public).  State advances only after a digest is durably handed over, so a
failed publish is retried by the next scheduled run and a successful one is never repeated.
"""

from __future__ import annotations

import base64
import collections
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

try:  # POSIX only; the lab is Linux
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

STATE_NAME = "work-items-state.json"
LOCK_NAME = ".work-items.lock"
MAX_ROWS_PER_BATCH = 5000   # a growing outbox is consumed in bounded batches, oldest first
DEFAULT_THRESHOLD = 25
_SAFE_REASON = re.compile(r"^(?:phd|misumi):[a-z0-9 ]{1,30}$")

# domain -> (owner repo, base branch, review path template, outbox file)
OWNERS: dict[str, dict[str, str]] = {
    "obsidian-phd": {
        "repo": "tyecam1/obsidian-PhD", "base": "main", "label": "research leads",
        "path": "automation/review/instagram-saved-research-leads-{stamp}.md",
    },
    "misumi": {
        "repo": "tyecam1/misumi", "base": "main", "label": "personal reference cues",
        "path": "agent-tasks/inbox/{stamp}-instagram-saved-reference-cues.md",
    },
}


def _threshold() -> int:
    try:
        value = int(os.getenv("ODYSSEUS_INSTAGRAM_WORKITEM_THRESHOLD", ""))
    except ValueError:
        return DEFAULT_THRESHOLD
    return value if value > 0 else DEFAULT_THRESHOLD


def _publishing_enabled() -> bool:
    """Opening owner-repo pull requests is an explicit operator opt-in (=1); the default only writes local digests."""
    return os.getenv("ODYSSEUS_INSTAGRAM_WORKITEM_PUBLISH", "0") == "1" and "PYTEST_CURRENT_TEST" not in os.environ


def build_digest(domain: str, rows: list[dict[str, Any]], *, stamp: str, total_routed: int) -> str:
    """Aggregate markdown for one domain batch: counts, confidence and cue words only."""
    owner = OWNERS[domain]
    confidence = collections.Counter(str(r.get("confidence") or "unknown") for r in rows)
    cues = collections.Counter(
        reason.split(":", 1)[1] for r in rows for reason in r.get("reasons", [])
        if isinstance(reason, str) and _SAFE_REASON.match(reason) and reason.startswith(("phd:", "misumi:"))
    )
    cue_text = ", ".join(f"`{cue}` {count}" for cue, count in cues.most_common(12)) or "none recorded"
    conf_text = ", ".join(f"{count} {name}" for name, count in sorted(confidence.items()))
    if domain == "obsidian-phd":
        head = (
            f"---\ntitle: Instagram Saved - {len(rows)} new research leads ({stamp})\nstatus: proposed\ncreated: {stamp[:10]}\n"
            "owner: obsidian-phd\norigin: odysseus instagram_saved_import + instagram_handoff (deterministic, no model)\n"
            "evidence_ceiling: lead_only_metadata\npromotion: human-gated (nothing here is canonical)\n---\n\n"
            f"# Instagram Saved: {len(rows)} new research-lead candidates (review area only)\n\n"
            "Leads or inspirations, never scholarly sources. Nothing here changes canonical notes.\n\n"
        )
        tail = (
            "\n## Proposed review actions (owner decides)\n1. Sample the medium-confidence leads first.\n"
            "2. Mark each `useful lead / not relevant / unclear`; create normal intake items under the vault's own rules.\n"
            "3. If precision is poor, ask Odysseus to retune the classifier (it owns the cue lists).\n"
        )
    else:
        head = (
            f"---\ntitle: Instagram Saved - {len(rows)} new personal reference cues ({stamp})\nowner_target: codex\npriority: low\n"
            f"status: open\ncreated: {stamp[:10]}\nupdated: {stamp[:10]}\ndisposition: review_request\n---\n\n"
            f"# Instagram Saved: {len(rows)} new personal reference cues\n\n"
            "Being saved does not mean liked, bought, listened to, owned or accepted.\n\n"
        )
        tail = (
            "\n## Constraints\nAny persona or recommender adaptation must be modest, reversible and provenance-linked; "
            "no memory fact per item; consolidate into existing concepts.\n\n"
            "## Acceptance\nA short decision recorded here, or an explicit \"no action\".\n"
        )
    return (
        head
        + f"## Batch summary (aggregate only; no permalinks or caption text)\n- New items routed to {owner['label']}: **{len(rows)}** "
        f"({conf_text}); routed to this domain so far: {total_routed}.\n- Cue words: {cue_text}.\n"
        f"- Pointers: lab outbox `data/instagram/handoff/{domain}.jsonl` (mode 0600); retrieval via Odysseus "
        f"`search_instagram_items(domain=\"{domain}\")`.\n" + tail
    )


def _gh(args: list[str], *, stdin: Optional[str] = None) -> str:
    result = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed ({result.returncode})")
    return result.stdout


def publish_pull_request(domain: str, digest: str, *, stamp: str, run: Callable[..., str] = _gh) -> str:
    """Open a pull request holding the digest in the owner repository (branch + one new file; never merges)."""
    owner = OWNERS[domain]
    repo, base = owner["repo"], owner["base"]
    path = owner["path"].format(stamp=stamp[:10] + "-" + stamp[11:19].replace(":", ""))
    branch = f"review/instagram-{domain}-{stamp[:10]}-{stamp[11:19].replace(':', '')}"

    def exists(args: list[str]) -> bool:
        try:
            return bool(run(args).strip())
        except RuntimeError:
            return False

    # Re-runs after a partial success reuse what already exists (same stamp -> same branch, path and PR): no duplicates.
    existing_pr = run(["pr", "list", "-R", repo, "--head", branch, "--state", "all", "--json", "url", "--jq", ".[0].url"]).strip()
    if existing_pr:
        return existing_pr
    if not exists(["api", f"repos/{repo}/git/ref/heads/{branch}", "--jq", ".object.sha"]):
        base_sha = run(["api", f"repos/{repo}/git/ref/heads/{base}", "--jq", ".object.sha"]).strip()
        run(["api", "-X", "POST", f"repos/{repo}/git/refs", "-f", f"ref=refs/heads/{branch}", "-f", f"sha={base_sha}"])
    if not exists(["api", f"repos/{repo}/contents/{path}?ref={branch}", "--jq", ".sha"]):
        run(["api", "-X", "PUT", f"repos/{repo}/contents/{path}", "-f", f"message=docs(review): Instagram Saved {owner['label']} batch {stamp[:10]}",
             "-f", f"branch={branch}", "-f", "content=" + base64.b64encode(digest.encode("utf-8")).decode("ascii")])
    body = (
        "## Summary\nAutomatic aggregate digest of newly routed Instagram Saved items for owner review. Counts and cue words only; "
        "no permalinks or caption text. Opened by the Odysseus lab job; it never merges.\n\n## Linked Issue\nInstagram Saved ingestion "
        "directive (Odysseus docs/instagram-saved-primary-ingestion-directive-2026-10-17.md).\n\n## Type of Change\n- [x] Documentation / review material\n\n"
        "## Checklist\n- [x] I searched existing issues and PRs for this work\n- [x] One new file in the owner's review/inbox area\n\n"
        "## How to Test\n1. Open the new file and confirm it holds only counts and cue words.\n2. `git diff --stat` shows one added file.\n"
    )
    url = run(["pr", "create", "-R", repo, "--base", base, "--head", branch, "--title",
               f"docs(review): Instagram Saved {owner['label']} batch {stamp[:10]}", "--body", body]).strip()
    return url.splitlines()[-1] if url else ""


def _load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(state, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def run_instagram_work_items(
    handoff_dir: str | os.PathLike[str],
    *,
    publisher: Optional[Callable[..., str]] = None,
    threshold: Optional[int] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Hand a digest to each owner whose outbox gained at least ``threshold`` new items; return per-domain outcomes."""
    out = Path(handoff_dir)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = open(out / LOCK_NAME, "a")
    try:
        if fcntl is not None:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return {"skipped": "another_run_in_progress"}   # concurrent run (service + one-shot): never double-generate
        return _run_locked(out, publisher=publisher, threshold=threshold, now=now)
    finally:
        lock.close()


def _run_locked(out: Path, *, publisher, threshold, now) -> dict[str, Any]:
    limit = threshold if threshold is not None else _threshold()
    now_stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    state_path = out / STATE_NAME
    state = _load_state(state_path)
    publish = publisher if publisher is not None else (publish_pull_request if _publishing_enabled() else None)
    outcome: dict[str, Any] = {}
    for domain in OWNERS:
        outbox = out / f"{domain}.jsonl"
        try:
            lines = [line for line in outbox.read_text(encoding="utf-8").splitlines() if line.strip()]
        except FileNotFoundError:
            outcome[domain] = "no_outbox"
            continue
        entry = state.get(domain, {})
        done = int(entry.get("handed_over", 0))
        pending = entry.get("pending") if isinstance(entry.get("pending"), dict) else None
        end = min(len(lines), done + MAX_ROWS_PER_BATCH)
        stamp = now_stamp
        if pending:                       # a publish that failed part-way is retried with the SAME batch, stamp and branch
            end, stamp = min(int(pending.get("end", end)), len(lines)), str(pending.get("stamp", now_stamp))
        rows: list[dict[str, Any]] = []
        for line in lines[done:end]:
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        if len(rows) < limit:
            outcome[domain] = f"pending_{len(rows)}"
            continue
        digest = build_digest(domain, rows, stamp=stamp, total_routed=end)
        local = out / "digests"
        local.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = local / f"{domain}-{stamp.replace(':', '')}.md"
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(digest)
        if publish is None:  # default: the digest is the hand-over (local, aggregate only); an executor or the owner picks it up
            state[domain] = {"handed_over": end, "last_batch": stamp, "last_url": ""}
            _save_state(state_path, state)
            outcome[domain] = "digest_written"
            continue
        state[domain] = {**entry, "pending": {"stamp": stamp, "end": end}}   # recorded BEFORE any remote write
        _save_state(state_path, state)
        try:
            url = publish(domain, digest, stamp=stamp)
        except Exception as exc:  # retried on the next run with the same batch; handed_over does not advance
            logger.warning("Instagram work-item publish failed for %s: %s", domain, type(exc).__name__)
            outcome[domain] = "publish_failed"
            continue
        state[domain] = {"handed_over": end, "last_batch": stamp, "last_url": url}
        _save_state(state_path, state)
        outcome[domain] = "published"
    return outcome
