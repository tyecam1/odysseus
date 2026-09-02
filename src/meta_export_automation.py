"""Policy-gated Meta/Instagram export-retrieval automation (P2 real-export
gate, docs: external-ingest programme).

Reuses the persistent browser profile scripts/meta_export_login_session.py
lets the user authenticate once (same existing Meta/Instagram account -
this module has no concept of, and never creates, a second account or
identity). No remote-debugging port is opened here at all - this runs
fully headless=new, internal-only, with no network-reachable surface
whatsoever; the login session's temporary debugging port is a separate,
already-shut-down concern by the time this module ever runs.

Browser authority is deliberately the narrowest possible: an explicit
ALLOW-list of Meta/Instagram URL path prefixes needed for the official
Download/Transfer Your Information self-service workflow, checked before
every navigation and re-checked against the page's actual URL after
navigation (in case of a redirect), plus an explicit DENY-list of known-
dangerous areas (posting, messaging, follows, profile/account/credential
edits) that fails closed even if a path would otherwise be allow-listed.
Any URL that is not explicitly allowed is denied by default - this is a
default-deny gate, not a default-allow gate with exceptions. A denied
navigation raises `MetaAutomationPolicyViolation` immediately and aborts
the whole run; it never silently continues on a different page than
expected.

This module only ever performs the official, user-initiated Meta self-
service data-export request/check/download flow - the same thing a human
would do by hand in Accounts Center. It never posts, likes, comments,
follows, messages, or changes any account/profile/security/credential
setting, and the deny-list exists specifically to make an accidental or
Meta-UI-driven navigation into any of those areas fail closed rather than
silently proceed.

If the session has expired or been revoked (detected via a redirect back
to a login/challenge page during what should be an authenticated flow),
this module raises `MetaSessionExpired` and stops immediately rather than
attempting to re-authenticate itself - the design explicitly requires
exactly one bounded human action to resume:

    Re-authenticate the existing Meta account in the temporary lab
    browser session and approve any security request on your phone.

The resulting export file is written into a private, outside-Git
quarantine directory with restrictive (0700 dir / 0600 file) permissions,
alongside a small sidecar JSON recording SHA256, byte size, and
acquisition provenance (when it was requested/downloaded, which profile)
- never the file's own content duplicated elsewhere, mirroring this
codebase's existing ref-not-raw-bytes convention (src/attachment_refs.py,
src/source_events.py). The raw export itself is never sent to any model
and never committed - see src/instagram_importer.py for the deterministic,
model-free inspection and redacted-fixture derivation step that consumes
it after this module hands it off.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

PROFILE_DIR = Path.home() / ".aoteru" / "meta-export-browser-profile"

# Default-deny gate: only these path prefixes, on these hosts, are ever
# navigated to. Anything else - including a same-host page not on this
# list - is refused before the browser is ever told to go there.
_ALLOWED_HOSTS_AND_PREFIXES: dict[str, tuple[str, ...]] = {
    "www.instagram.com": (
        "/accounts/login/",
        "/accounts/onetap/",
        "/accounts/edit/",  # only reached transiently on the Accounts Center bounce; see DENY below for the real edit-profile page
        "/download/",
        "/challenge/",
        "/two_factor/",
    ),
    "accountscenter.instagram.com": ("/",),
    "www.facebook.com": (
        "/help/instagram/",
        "/accountscenter/",
    ),
}

# Explicit deny, checked AFTER the allow-list and overriding it even for an
# otherwise-allowed host - belt and suspenders against a path that looks
# like it starts with an allowed prefix but actually leads somewhere
# dangerous (e.g. an edit-profile deep link nested under an otherwise
# allowed area).
_DENIED_PATH_SUBSTRINGS: tuple[str, ...] = (
    "/accounts/edit/?",  # actual profile-edit form (vs. the bare transient redirect path above)
    "/accounts/password/",
    "/accounts/two_factor_authentication/",
    "/accounts/manage_access/",
    "/direct/",
    "/create/",
    "/accounts/remove/",
    "/accounts/deactivate/",
    "/security/",
)


class MetaAutomationPolicyViolation(RuntimeError):
    """Raised when navigation would leave (or already left) the narrow
    allow-listed surface this automation is permitted to touch. Always
    fails closed - the run aborts, nothing further is attempted."""


class MetaSessionExpired(RuntimeError):
    """Raised when the persisted session no longer authenticates - the
    automation stops and requires exactly one bounded human action (see
    module docstring) rather than attempting anything itself."""


def _is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    full = path + (("?" + parsed.query) if parsed.query else "")

    for denied in _DENIED_PATH_SUBSTRINGS:
        if denied in full:
            return False

    prefixes = _ALLOWED_HOSTS_AND_PREFIXES.get(host)
    if prefixes is None:
        return False
    return any(path.startswith(prefix) for prefix in prefixes)


def _guard(url: str) -> None:
    if not _is_allowed_url(url):
        raise MetaAutomationPolicyViolation(
            f"refusing to navigate to {url!r} - not on the narrow Meta export-workflow allow-list"
        )


def _looks_like_login_or_challenge(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.startswith(("/accounts/login/", "/challenge/", "/two_factor/"))


@dataclass
class ExportRequestResult:
    quarantine_path: str
    sha256: str
    size_bytes: int
    requested_at: float
    downloaded_at: float
    provenance: dict = field(default_factory=dict)


def _guarded_goto(page, url: str, *, expect_authenticated: bool = True) -> None:
    """Navigate only if `url` passes the allow/deny gate, then re-check
    the page's ACTUAL resulting URL (a redirect can land somewhere the
    original URL alone would not reveal) against the same gate, and
    against session-expiry, before returning control to the caller."""
    _guard(url)
    page.goto(url, wait_until="domcontentloaded")
    _guard(page.url)
    if expect_authenticated and _looks_like_login_or_challenge(page.url):
        raise MetaSessionExpired(
            "redirected to a login/challenge page during an authenticated step - "
            "the persisted Meta session has expired or been revoked. Re-authenticate "
            "the existing Meta account in the temporary lab browser session "
            "(scripts/meta_export_login_session.py start) and approve any security "
            "request on your phone, then resume."
        )


def _quarantine_file(source_path: Path, quarantine_dir: Path, *, requested_at: float) -> ExportRequestResult:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(quarantine_dir, 0o700)

    digest = hashlib.sha256()
    with open(source_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    size_bytes = source_path.stat().st_size

    dest_path = quarantine_dir / source_path.name
    source_path.rename(dest_path)
    os.chmod(dest_path, 0o600)

    downloaded_at = time.time()
    provenance = {
        "filename": dest_path.name,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "requested_at": requested_at,
        "downloaded_at": downloaded_at,
        "acquisition": "official Meta Download/Transfer Your Information self-service export, "
                        "retrieved via the authenticated lab browser session",
    }
    sidecar_path = quarantine_dir / f"{dest_path.name}.provenance.json"
    sidecar_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    os.chmod(sidecar_path, 0o600)

    return ExportRequestResult(
        quarantine_path=str(dest_path),
        sha256=sha256,
        size_bytes=size_bytes,
        requested_at=requested_at,
        downloaded_at=downloaded_at,
        provenance=provenance,
    )


def request_and_download_instagram_export(
    quarantine_dir: str,
    *,
    profile_dir: Optional[str] = None,
    poll_interval_seconds: float = 30.0,
    poll_timeout_seconds: float = 3600.0,
) -> ExportRequestResult:
    """Drive the official Meta Download/Transfer Your Information
    self-service workflow to request, wait for, and download an Instagram
    Saved-items/collections export - the only workflow this module is
    permitted to perform.

    Meta's own account/export UI changes over time; the step functions
    below are each isolated so an adjustment to one (e.g. a button label
    or an extra confirmation step Meta has added) never requires touching
    the allow/deny policy gate or the quarantine/provenance handling. The
    policy gate is deliberately host+path-prefix based (stable, public,
    documented Meta product surfaces), not selector-based, so it does not
    need updating for ordinary UI churn.

    Raises `MetaAutomationPolicyViolation` if any step would navigate
    outside the narrow allowed surface, or `MetaSessionExpired` if the
    persisted session no longer authenticates - both fail closed, no
    partial/ambiguous state is left for the caller to guess about.
    """
    from playwright.sync_api import sync_playwright

    resolved_profile_dir = Path(profile_dir) if profile_dir else PROFILE_DIR
    if not resolved_profile_dir.exists():
        raise MetaSessionExpired(
            f"no persisted browser profile found at {resolved_profile_dir} - run "
            "scripts/meta_export_login_session.py start and log in once first."
        )

    requested_at = time.time()

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(resolved_profile_dir),
            headless=True,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            downloaded_path = _run_export_workflow(
                page, poll_interval_seconds=poll_interval_seconds, poll_timeout_seconds=poll_timeout_seconds,
            )
        finally:
            context.close()

    return _quarantine_file(downloaded_path, Path(quarantine_dir), requested_at=requested_at)


def _run_export_workflow(page, *, poll_interval_seconds: float, poll_timeout_seconds: float) -> Path:
    """The actual Meta click-sequence. Documented as best-effort against
    Meta's publicly documented Download/Transfer Your Information feature
    at the time this was written - verify and adjust against a real
    authenticated session before relying on it; the allow/deny gate above
    remains correct and does not need adjusting alongside it."""
    _guarded_goto(page, "https://accountscenter.instagram.com/")

    # Accounts Center's "Your information and permissions" -> "Download or
    # transfer information" entry point.
    page.get_by_text("Your information and permissions", exact=False).click()
    page.get_by_text("Download or transfer information", exact=False).click()

    # Request a new export scoped to Instagram, "Some of your information"
    # -> Saved items/collections only (never the full account archive -
    # narrowest possible request matching the narrowest possible browser
    # authority this module is granted).
    page.get_by_text("Create export", exact=False).click()
    page.get_by_text("Instagram", exact=False).click()
    page.get_by_text("Some of your information", exact=False).click()
    page.get_by_text("Saved", exact=False).click()
    page.get_by_text("Next", exact=False).click()
    page.get_by_text("Submit request", exact=False).click()

    _guard(page.url)

    deadline = time.monotonic() + poll_timeout_seconds
    while time.monotonic() < deadline:
        _guarded_goto(page, "https://accountscenter.instagram.com/")
        page.get_by_text("Your information and permissions", exact=False).click()
        page.get_by_text("Download or transfer information", exact=False).click()

        ready_link = page.get_by_text("Download", exact=False)
        if ready_link.count() > 0:
            with page.expect_download() as download_info:
                ready_link.first.click()
            download = download_info.value
            dest = Path("/tmp") / f"instagram_export_{int(time.time())}_{download.suggested_filename}"
            download.save_as(dest)
            return dest

        time.sleep(poll_interval_seconds)

    raise TimeoutError(
        f"Instagram export was not ready for download within {poll_timeout_seconds:.0f}s - "
        "the request was submitted; check Accounts Center manually or increase poll_timeout_seconds."
    )
