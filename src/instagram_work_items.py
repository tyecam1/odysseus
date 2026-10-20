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
import hashlib
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
_CONFIDENCES = frozenset({"none", "low", "medium", "high"})   # the outbox is data, never trusted text, in a public digest

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


def build_digest(
    domain: str, rows: list[dict[str, Any]], *, stamp: str, total_routed: int, batch: Optional[dict[str, Any]] = None
) -> str:
    """Aggregate markdown for one domain batch: counts, confidence and cue words only."""
    owner = OWNERS[domain]
    confidence = collections.Counter(
        r["confidence"] if isinstance(r.get("confidence"), str) and r["confidence"] in _CONFIDENCES else "unknown" for r in rows
    )
    batch = batch or {}
    batch_text = (
        f"- Source batch: outbox rows {batch['start'] + 1}-{batch['end']} of `{domain}.jsonl` (sha256 `{batch['sha256'][:16]}`); "
        f"{batch.get('invalid', 0)} unreadable, {batch.get('retracted', 0)} retraction and {batch.get('duplicates', 0)} duplicate rows "
        "excluded.\n"
        if {"start", "end", "sha256"} <= set(batch) else ""
    )
    cues = collections.Counter(
        reason.split(":", 1)[1] for r in rows for reason in r.get("reasons", [])
        if isinstance(reason, str) and _SAFE_REASON.match(reason) and reason.startswith(("phd:", "misumi:"))
    )
    cue_text = ", ".join(f"`{cue}` {count}" for cue, count in cues.most_common(12)) or "none recorded"
    conf_text = ", ".join(f"{count} {name}" for name, count in sorted(confidence.items()))
    if domain == "obsidian-phd":
        head = (
            f"---\ntitle: Instagram Saved - {len(rows)} new research leads ({stamp})\nartifact_type: review\nstatus: proposed\n"
            "review_only: true\ncanonical_edits: false\n" f"created: {stamp[:10]}\n"
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
        + batch_text +
        f"- Pointers: lab outbox `data/instagram/handoff/{domain}.jsonl` (mode 0600); retrieval via Odysseus "
        f"`search_instagram_items(domain=\"{domain}\")`.\n" + tail
    )


def _gh_binary() -> str:
    """The lab unit runs with NoNewPrivileges, which a snap-packaged gh cannot start under: point this at a plain binary."""
    return os.getenv("ODYSSEUS_GH_BIN") or "gh"


def _gh(args: list[str], *, stdin: Optional[str] = None) -> str:
    try:
        result = subprocess.run([_gh_binary(), *args], input=stdin, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"gh could not run ({type(exc).__name__})") from exc
    if result.returncode != 0:
        detail = " ".join((result.stderr or "").split())[:160]    # gh error text names the failed call, never credentials
        raise RuntimeError(f"gh {' '.join(args[:2])} failed ({result.returncode}): {detail}")
    return result.stdout


def _gh_ready() -> Optional[str]:
    """None when gh can run in this process (service sandbox included); otherwise a short reason."""
    try:
        _gh(["--version"])
    except RuntimeError as exc:
        return str(exc)
    return None


def publish_pull_request(
    domain: str, digest: str, *, stamp: str, batch_id: str = "", run: Callable[..., str] = _gh
) -> str:
    """Open a pull request holding the digest in the owner repository (branch + one new file; never merges).

    ``batch_id`` (outbox row range) is part of the branch, file and title, so two distinct batches can never share a PR even
    when they are generated within the same second, and one batch always maps to exactly one PR.
    """
    owner = OWNERS[domain]
    repo, base = owner["repo"], owner["base"]
    tag = stamp[:10] + "-" + stamp[11:19].replace(":", "") + (f"-{batch_id}" if batch_id else "")
    path = owner["path"].format(stamp=tag)
    branch = f"review/instagram-{domain}-{tag}"

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
        run(["api", "-X", "PUT", f"repos/{repo}/contents/{path}", "-f", f"message=docs(review): Instagram Saved {owner['label']} batch {stamp[:10]}{' ' + batch_id if batch_id else ''}",
             "-f", f"branch={branch}", "-f", "content=" + base64.b64encode(digest.encode("utf-8")).decode("ascii")])
    body = (
        "## Summary\nAutomatic aggregate digest of newly routed Instagram Saved items for owner review. Counts and cue words only; "
        "no permalinks or caption text. Opened by the Odysseus lab job; it never merges.\n\n## Linked Issue\nInstagram Saved ingestion "
        "directive (Odysseus docs/instagram-saved-primary-ingestion-directive-2026-10-17.md).\n\n## Type of Change\n- [x] Documentation / review material\n\n"
        "## Checklist\n- [x] I searched existing issues and PRs for this work\n- [x] One new file in the owner's review/inbox area\n\n"
        "## How to Test\n1. Open the new file and confirm it holds only counts and cue words.\n2. `git diff --stat` shows one added file.\n"
    )
    url = run(["pr", "create", "-R", repo, "--base", base, "--head", branch, "--title",
               f"docs(review): Instagram Saved {owner['label']} batch {stamp[:10]}{' ' + batch_id if batch_id else ''}", "--body", body]).strip()
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


def _read_outbox(outbox: Path) -> list[str]:
    """Complete (newline-terminated) outbox lines only: a torn final write is left for the next run, never counted or lost."""
    text = outbox.read_bytes().decode("utf-8", errors="replace")
    complete = text[: text.rfind("\n") + 1]
    return complete.splitlines()


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
    blocked = _gh_ready() if publish is publish_pull_request else None
    if blocked:                                # say so once per run; do not touch state, so nothing is lost or half-handed-over
        logger.warning("Instagram work items: publishing is enabled but unavailable: %s", blocked)
    for domain in OWNERS:
        outbox = out / f"{domain}.jsonl"
        try:
            lines = _read_outbox(outbox)
        except FileNotFoundError:
            outcome[domain] = "no_outbox"
            continue
        entry = state.get(domain, {})
        done = int(entry.get("handed_over", 0))
        if done > len(lines):                 # outbox shorter than the recorded offset: rotated or truncated, never guess
            logger.warning("Instagram work items: %s outbox has %d rows but %d were handed over", domain, len(lines), done)
            outcome[domain] = "outbox_shorter_than_state"
            continue
        pending = entry.get("pending") if isinstance(entry.get("pending"), dict) else None
        end = min(len(lines), done + MAX_ROWS_PER_BATCH)
        stamp = now_stamp
        if pending:                       # a publish that failed part-way is retried with the SAME batch, stamp and branch
            end, stamp = min(int(pending.get("end", end)), len(lines)), str(pending.get("stamp", now_stamp))
        # Replay the window in order: a pointer counts once however often it was written (at-least-once appends), and one
        # withdrawn by a later retraction in the same window is not a new lead at all.
        active: dict[str, dict[str, Any]] = {}
        invalid = retracted = duplicates = 0
        for index, line in enumerate(lines[done:end]):
            if not line.strip():
                continue                      # a blank line carries nothing and loses nothing
            try:
                value = json.loads(line)
            except ValueError:
                invalid += 1
                continue
            if not isinstance(value, dict):
                invalid += 1
                continue
            identity = str(value.get("permalink") or f"row{index}")
            if value.get("retracted"):
                retracted += 1
                active.pop(identity, None)
            else:
                duplicates += identity in active
                active[identity] = value
        rows = list(active.values())
        if len(rows) < limit:
            outcome[domain] = f"pending_{len(rows)}"
            continue
        if blocked:
            outcome[domain] = "publish_unavailable"
            continue
        batch = {"start": done, "end": end, "invalid": invalid, "retracted": retracted, "duplicates": duplicates,
                 "sha256": hashlib.sha256("\n".join(lines[done:end]).encode("utf-8")).hexdigest()}
        batch_id = f"rows{done + 1}-{end}"
        digest = build_digest(domain, rows, stamp=stamp, total_routed=end, batch=batch)
        local = out / "digests"
        local.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = local / f"{domain}-{stamp.replace(':', '')}-{batch_id}.md"
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(digest)
        record = {"handed_over": end, "last_batch": stamp, "last_range": [done, end], "last_batch_sha256": batch["sha256"]}
        if publish is None:  # default: the digest is the hand-over (local, aggregate only); an executor or the owner picks it up
            state[domain] = {**record, "last_url": ""}
            _save_state(state_path, state)
            outcome[domain] = "digest_written"
            continue
        state[domain] = {**entry, "pending": {"stamp": stamp, "end": end}}   # recorded BEFORE any remote write
        _save_state(state_path, state)
        try:
            url = publish(domain, digest, stamp=stamp, batch_id=batch_id)
        except Exception as exc:  # retried on the next run with the same batch; handed_over does not advance
            logger.warning("Instagram work-item publish failed for %s: %s", domain, str(exc)[:240])
            outcome[domain] = "publish_failed"
            continue
        state[domain] = {**record, "last_url": url}
        _save_state(state_path, state)
        outcome[domain] = "published"
    return outcome
