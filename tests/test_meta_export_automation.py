"""Tests for src.meta_export_automation's policy gate (P2 real-export gate
support code).

These tests never touch the real network and never require a real Meta
account or session - they prove the allow/deny policy logic itself is
correct (pure function tests) and that it is actually enforced by a real
Playwright-driven browser navigation (using local file:// and local-HTTP-
server test pages, not instagram.com), independent of whatever the real
Meta UI currently looks like.
"""
import functools
import http.server
import textwrap
import threading
from pathlib import Path

import pytest

from src.meta_export_automation import (
    MetaAutomationPolicyViolation,
    MetaSessionExpired,
    _guard,
    _guarded_goto,
    _install_navigation_guard,
    _is_allowed_url,
    _looks_like_login_or_challenge,
)


@pytest.mark.parametrize("url", [
    "https://accountscenter.instagram.com/",
    "https://accountscenter.instagram.com/info_and_permissions/dyi/",
    "https://www.instagram.com/download/request/",
    "https://www.instagram.com/accounts/login/",
    "https://www.instagram.com/challenge/",
    "https://www.facebook.com/help/instagram/181231772500920",
    "https://www.facebook.com/accountscenter/info_and_permissions/",
])
def test_allowed_urls_pass(url):
    assert _is_allowed_url(url) is True


@pytest.mark.parametrize("url", [
    "https://www.instagram.com/p/AAA111/",  # a post - not export-workflow
    "https://www.instagram.com/direct/inbox/",  # DMs
    "https://www.instagram.com/create/style/",  # posting
    "https://www.instagram.com/accounts/edit/?some=thing",  # profile edit form
    "https://www.instagram.com/accounts/password/change/",  # credential change
    "https://www.instagram.com/accounts/two_factor_authentication/",  # security settings
    "https://www.instagram.com/accounts/remove/request/",  # account deletion
    "https://www.instagram.com/someoneelse/",  # arbitrary profile browsing
    "https://www.evil-instagram-lookalike.com/accounts/login/",  # wrong host entirely
    "https://www.facebook.com/",  # facebook.com root, not an allow-listed sub-path
    "https://accountscenter.facebook.com/",  # wrong subdomain
])
def test_disallowed_urls_fail(url):
    assert _is_allowed_url(url) is False


def test_deny_list_overrides_an_otherwise_matching_allow_prefix():
    """/accounts/edit/ (bare, transient) is allow-listed, but a real
    profile-edit form URL with a query string must still be denied - the
    deny-list is checked first and wins even against a prefix match."""
    assert _is_allowed_url("https://www.instagram.com/accounts/edit/") is True
    assert _is_allowed_url("https://www.instagram.com/accounts/edit/?step=name") is False


def test_guard_raises_for_disallowed_url():
    with pytest.raises(MetaAutomationPolicyViolation):
        _guard("https://www.instagram.com/direct/inbox/")


def test_guard_does_not_raise_for_allowed_url():
    _guard("https://accountscenter.instagram.com/")  # must not raise


def test_looks_like_login_or_challenge():
    assert _looks_like_login_or_challenge("https://www.instagram.com/accounts/login/") is True
    assert _looks_like_login_or_challenge("https://www.instagram.com/challenge/") is True
    assert _looks_like_login_or_challenge("https://www.instagram.com/two_factor/") is True
    assert _looks_like_login_or_challenge("https://accountscenter.instagram.com/") is False


class _FakePage:
    """Minimal stand-in for playwright's Page, just enough to exercise
    _guarded_goto's own logic without a real browser - the real-browser
    enforcement proof is the separate test below."""
    def __init__(self, resulting_url: str):
        self.url = None
        self._resulting_url = resulting_url

    def goto(self, url, wait_until=None):
        self.url = self._resulting_url


def test_guarded_goto_refuses_before_ever_navigating_to_a_disallowed_url():
    page = _FakePage(resulting_url="https://www.instagram.com/direct/inbox/")
    with pytest.raises(MetaAutomationPolicyViolation):
        _guarded_goto(page, "https://www.instagram.com/direct/inbox/")
    # never actually navigated - the guard fires on the requested URL
    # itself, before .goto() is ever called.
    assert page.url is None


def test_guarded_goto_catches_a_redirect_landing_somewhere_disallowed():
    """The requested URL is allowed, but the page redirects somewhere that
    is not - must still fail closed, checked against the ACTUAL resulting
    URL, not just the one requested."""
    page = _FakePage(resulting_url="https://www.instagram.com/accounts/password/change/")
    with pytest.raises(MetaAutomationPolicyViolation):
        _guarded_goto(page, "https://accountscenter.instagram.com/")


def test_guarded_goto_raises_session_expired_on_login_redirect():
    page = _FakePage(resulting_url="https://www.instagram.com/accounts/login/")
    with pytest.raises(MetaSessionExpired) as exc_info:
        _guarded_goto(page, "https://accountscenter.instagram.com/")
    assert "Re-authenticate" in str(exc_info.value)


def test_guarded_goto_allows_login_redirect_when_not_expecting_authentication():
    page = _FakePage(resulting_url="https://www.instagram.com/accounts/login/")
    _guarded_goto(page, "https://www.instagram.com/accounts/login/", expect_authenticated=False)
    assert page.url == "https://www.instagram.com/accounts/login/"


@pytest.fixture
def real_browser_page():
    playwright_module = pytest.importorskip("playwright.sync_api")
    with playwright_module.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment without a browser installed
            pytest.skip(f"no Playwright-managed browser available: {exc}")
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


def test_guarded_goto_actually_blocks_real_navigation_via_a_real_browser(real_browser_page, tmp_path):
    """End-to-end proof (not just logic-level): a real Playwright page is
    never told to navigate anywhere once the URL fails the gate. Uses a
    local file:// test page, never the real network or real Meta - proves
    enforcement independent of instagram.com's actual current UI."""
    test_page = tmp_path / "fake_direct_inbox.html"
    test_page.write_text(textwrap.dedent("""
        <html><body><h1>fake page, never actually reached</h1></body></html>
    """), encoding="utf-8")

    real_browser_page.goto("about:blank")
    with pytest.raises(MetaAutomationPolicyViolation):
        _guarded_goto(real_browser_page, "https://www.instagram.com/direct/inbox/")
    # the real page never navigated away from about:blank - the file:// URL
    # standing in here proves the point structurally even though the guard
    # never lets .goto() run for the disallowed instagram.com URL itself.
    assert real_browser_page.url == "about:blank"


# --- network-request-boundary interceptor (_install_navigation_guard) ---
#
# Everything above tests the pre/post-navigation checks around this
# module's own page.goto() calls. The tests below prove the separate,
# stronger guard: a page.route() handler that evaluates every MAIN-FRAME
# navigation request - including one triggered by a click inside the page,
# not by this module's own code - before the browser is ever allowed to
# complete it. A local HTTP server (never the real network or real Meta)
# serves the test pages; a custom `is_allowed` predicate (anything not
# under "/disallowed/" on this server) stands in for the real Meta
# allow/deny policy so the tests don't depend on instagram.com's current
# UI or need real network access - _is_allowed_url's own logic is already
# covered by the pure-function tests above.


class _ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture
def local_test_server(tmp_path):
    """A tiny local HTTP server (127.0.0.1, OS-assigned port) serving
    files from `tmp_path`. Yields (base_url, docroot)."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = _ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", tmp_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _not_disallowed(url: str) -> bool:
    return "/disallowed/" not in url


@pytest.fixture
def real_browser_context():
    """Like real_browser_page, but exposes the BrowserContext too, since
    popup handling (_on_new_page) is registered at the context level."""
    playwright_module = pytest.importorskip("playwright.sync_api")
    with playwright_module.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment without a browser installed
            pytest.skip(f"no Playwright-managed browser available: {exc}")
        context = browser.new_context()
        page = context.new_page()
        try:
            yield context, page
        finally:
            browser.close()


def test_click_triggered_navigation_to_disallowed_url_is_blocked_before_it_succeeds(
    real_browser_context, local_test_server,
):
    """Requirement A: the guard fires for a navigation the page's own JS/
    link triggers via a click - not just one this module's code initiated
    with page.goto()."""
    context, page = real_browser_context
    base_url, docroot = local_test_server

    (docroot / "index.html").write_text(
        '<html><body><a id="link" href="/disallowed/target.html">go</a></body></html>',
        encoding="utf-8",
    )
    (docroot / "disallowed").mkdir()
    (docroot / "disallowed" / "target.html").write_text(
        "<html><body>should never be reached</body></html>", encoding="utf-8",
    )

    state = _install_navigation_guard(context, page, is_allowed=_not_disallowed)
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    page.click("#link")

    # give any (aborted) navigation attempt a moment to resolve, then prove
    # the disallowed target was never reached. Aborting a main-frame
    # navigation request is a hard failure for the browser's in-flight
    # navigation - Chromium leaves the page on an internal chrome-error://
    # page rather than silently staying put - but the one thing that must
    # never happen either way is the disallowed document actually loading.
    page.wait_for_timeout(500)
    assert "/disallowed/target.html" not in page.url
    assert any("/disallowed/target.html" in u for u in state.blocked_urls)


def test_disallowed_popup_cannot_escape_the_policy(real_browser_context, local_test_server):
    """Requirement B: a click that opens target="_blank" (a new page in the
    same browser context) must not be able to reach a disallowed URL just
    because it landed on a different page object than the one the guard
    was originally installed on."""
    context, page = real_browser_context
    base_url, docroot = local_test_server

    (docroot / "index.html").write_text(
        '<html><body><a id="popup_link" target="_blank" '
        'href="/disallowed/popup_target.html">open</a></body></html>',
        encoding="utf-8",
    )
    (docroot / "disallowed").mkdir()
    (docroot / "disallowed" / "popup_target.html").write_text(
        "<html><body>should never be reached</body></html>", encoding="utf-8",
    )

    state = _install_navigation_guard(context, page, is_allowed=_not_disallowed)
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")

    with context.expect_page() as popup_info:
        page.click("#popup_link")
    popup = popup_info.value
    popup.wait_for_timeout(500)

    assert "/disallowed/popup_target.html" not in popup.url
    assert any("/disallowed/popup_target.html" in u for u in state.blocked_urls)
    popup.close()


def test_allowed_navigation_still_renders_with_its_subresources(real_browser_context, local_test_server):
    """Requirement C: the guard must not accidentally block scripts/CSS/
    XHR just because they are not top-level navigations - an allowed page
    must still render exactly as it would unguarded."""
    context, page = real_browser_context
    base_url, docroot = local_test_server

    (docroot / "index.html").write_text(textwrap.dedent("""
        <html>
        <head><link rel="stylesheet" href="/style.css"></head>
        <body>
            <div id="marker">not-loaded</div>
            <script src="/script.js"></script>
        </body>
        </html>
    """), encoding="utf-8")
    (docroot / "style.css").write_text("#marker { color: rgb(1, 2, 3); }", encoding="utf-8")
    (docroot / "data.json").write_text('{"ok": true}', encoding="utf-8")
    (docroot / "script.js").write_text(textwrap.dedent("""
        fetch('/data.json')
            .then(r => r.json())
            .then(d => { document.getElementById('marker').textContent = d.ok ? 'xhr-loaded' : 'xhr-failed'; });
    """), encoding="utf-8")

    state = _install_navigation_guard(context, page, is_allowed=_not_disallowed)
    page.goto(f"{base_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_function("document.getElementById('marker').textContent !== 'not-loaded'", timeout=5000)

    assert page.url == f"{base_url}/index.html"
    assert page.locator("#marker").text_content() == "xhr-loaded"  # script.js ran and its fetch()/XHR succeeded
    assert page.eval_on_selector("#marker", "el => getComputedStyle(el).color") == "rgb(1, 2, 3)"  # style.css applied
    assert not state.blocked_urls  # nothing on this allowed page was ever blocked
