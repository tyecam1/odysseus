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
Download/Transfer Your Information self-service workflow, plus an explicit
DENY-list of known-dangerous areas (posting, messaging, follows, profile/
account/credential edits) that fails closed even if a path would otherwise
be allow-listed. Any URL that is not explicitly allowed is denied by
default - this is a default-deny gate, not a default-allow gate with
exceptions.

The policy is enforced at the network-request boundary, not only around
this module's own `page.goto()` calls: `_install_navigation_guard()`
installs a `context.route()` handler that evaluates every MAIN-FRAME
navigation request (including one triggered by Meta's own UI via a click
this module did not initiate as a `goto`, and including a redirect chain)
against the same allow/deny policy before the browser is ever allowed to
complete it - a disallowed request is `route.abort()`-ed, not merely
detected after the fact. Ordinary subresources (scripts, CSS, images, XHR)
and iframe navigations are left untouched (`route.continue_()`
unconditionally) so an allowed page still renders normally; only a
top-level document-navigation request is evaluated. Because the route is
registered at the BROWSER-CONTEXT level rather than per-page, it already
covers every page/popup the context creates - including one opened after
this call, by a click with `target="_blank"` or `window.open()` - from the
moment that page exists, with no race window where a brand-new page's
first navigation could complete before a handler gets attached to it. No
click can escape this authority by opening a new target. The
pre-navigation `_guard(url)` call and the post-navigation
`_guard(page.url)` re-check (in case of a redirect) remain in place as
defence-in-depth on top of the network-layer guard, not as the only line
of defence.

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


@dataclass
class _NavigationGuardState:
    """Shared across a page and every popup/new page opened from it, so a
    violation is recorded regardless of which target it happened on."""
    blocked_urls: list = field(default_factory=list)


def _install_navigation_guard(context, page, *, is_allowed=_is_allowed_url) -> "_NavigationGuardState":
    """Enforce the allow/deny policy at the Playwright network-request
    boundary rather than only around this module's own `page.goto()`
    calls. A `context.route()` handler evaluates every MAIN-FRAME
    navigation request - including one Meta's own UI triggers via a click
    this module never called `goto` for, and including each hop of a
    redirect chain - before the browser is allowed to complete it; a
    disallowed request is `route.abort()`-ed outright. Ordinary
    subresources (scripts, CSS, images, XHR) and iframe navigations always
    `route.continue_()` unconditionally, so an allowed page still renders
    normally.

    Registered at the BROWSER-CONTEXT level (not per-page) deliberately:
    Playwright applies a context-level route to every page that belongs to
    the context, including one created after this call (a popup opened by
    `target="_blank"` or `window.open()`), from the moment that page
    exists - there is no race window in which a brand-new page's first
    navigation could complete before a per-page handler got attached to
    it, which a naive `page.route()`-per-popup approach would have. `is_
    allowed` is overridable purely so tests can point the guard at a local
    fixture origin instead of the real Meta allow-list; production callers
    always use the default.
    """
    state = _NavigationGuardState()

    def _route_handler(route):
        request = route.request
        if request.is_navigation_request():
            try:
                is_main_frame = request.frame == request.frame.page.main_frame
            except Exception:
                # The very first navigation request of a brand-new page
                # (e.g. a popup just opened via target="_blank" or
                # window.open()) has no Frame object yet - Playwright
                # raises accessing request.frame in that case. A new
                # page's first navigation is necessarily its own main
                # frame (it cannot be a sub-frame of a page that doesn't
                # exist yet), so treat it as one rather than letting it
                # fall through unguarded.
                is_main_frame = True
            if is_main_frame and not is_allowed(request.url):
                state.blocked_urls.append(request.url)
                route.abort()
                return
        route.continue_()

    context.route("**/*", _route_handler)
    # Lets _guarded_goto() below notice a mid-navigation (e.g. redirect)
    # block on the specific page it was called with, without a separate
    # lookup table.
    page._nav_guard_state = state
    return state


def _guarded_goto(page, url: str, *, expect_authenticated: bool = True) -> None:
    """Navigate only if `url` passes the allow/deny gate, then re-check
    the page's ACTUAL resulting URL (a redirect can land somewhere the
    original URL alone would not reveal) against the same gate, and
    against session-expiry, before returning control to the caller. If
    `_install_navigation_guard()` has been installed on `page`, a redirect
    that the network-layer guard already aborted mid-navigation is
    reported as a clean `MetaAutomationPolicyViolation` instead of a raw
    Playwright navigation error."""
    _guard(url)
    state = getattr(page, "_nav_guard_state", None)
    blocked_before = len(state.blocked_urls) if state is not None else 0
    try:
        page.goto(url, wait_until="domcontentloaded")
    except Exception:
        if state is not None and len(state.blocked_urls) > blocked_before:
            raise MetaAutomationPolicyViolation(
                f"navigation to {url!r} was blocked at the network-request boundary "
                f"(redirected to a disallowed target: {state.blocked_urls[blocked_before:]})"
            )
        raise
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
            _install_navigation_guard(context, page)
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
