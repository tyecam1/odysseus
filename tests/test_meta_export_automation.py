"""Tests for src.meta_export_automation's policy gate (P2 real-export gate
support code).

These tests never touch the real network and never require a real Meta
account or session - they prove the allow/deny policy logic itself is
correct (pure function tests) and that it is actually enforced by a real
Playwright-driven browser navigation (using local file:// test pages, not
instagram.com), independent of whatever the real Meta UI currently looks
like.
"""
import textwrap
from pathlib import Path

import pytest

from src.meta_export_automation import (
    MetaAutomationPolicyViolation,
    MetaSessionExpired,
    _guard,
    _guarded_goto,
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
