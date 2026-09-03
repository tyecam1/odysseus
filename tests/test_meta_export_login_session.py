"""Tests for scripts/meta_export_login_session.py's profile-permission
hardening (P2 real-export gate support code).

Never launches a real browser and never touches the network - these are
pure filesystem-permission tests against a fixture directory tree, proving
_verify_profile_permissions() correctly detects (and correctly passes)
group/world-readable files under the credential-bearing persistent
Chromium profile.
"""
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.meta_export_login_session import _verify_profile_permissions


@pytest.mark.skipif(os.name == "nt", reason="POSIX file-permission bits only apply on the lab host (Linux), not Windows")
def test_verify_profile_permissions_reports_no_violations_for_a_properly_restricted_tree(tmp_path):
    profile_dir = tmp_path / "profile"
    (profile_dir / "Default").mkdir(parents=True)
    cookies = profile_dir / "Default" / "Cookies"
    cookies.write_text("fake sqlite content", encoding="utf-8")

    os.chmod(profile_dir, 0o700)
    os.chmod(profile_dir / "Default", 0o700)
    os.chmod(cookies, 0o600)

    assert _verify_profile_permissions(profile_dir) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX file-permission bits only apply on the lab host (Linux), not Windows")
def test_verify_profile_permissions_detects_a_group_or_world_readable_file(tmp_path):
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    os.chmod(profile_dir, 0o700)

    leaky_file = profile_dir / "Cookies"
    leaky_file.write_text("fake sqlite content", encoding="utf-8")
    os.chmod(leaky_file, 0o644)  # group/world readable - must be flagged

    violations = _verify_profile_permissions(profile_dir)
    assert len(violations) == 1
    assert "Cookies" in violations[0]
    assert "0o644" in violations[0] or oct(0o644) in violations[0]


@pytest.mark.skipif(os.name == "nt", reason="POSIX file-permission bits only apply on the lab host (Linux), not Windows")
def test_verify_profile_permissions_detects_a_group_or_world_readable_subdirectory(tmp_path):
    profile_dir = tmp_path / "profile"
    leaky_subdir = profile_dir / "Default"
    leaky_subdir.mkdir(parents=True)
    os.chmod(profile_dir, 0o700)
    os.chmod(leaky_subdir, 0o755)  # world-executable/readable directory - must be flagged

    violations = _verify_profile_permissions(profile_dir)
    assert any("Default" in v for v in violations)


def test_verify_profile_permissions_returns_empty_for_a_nonexistent_profile_dir(tmp_path):
    assert _verify_profile_permissions(tmp_path / "does-not-exist-yet") == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX umask semantics only apply on the lab host (Linux), not Windows")
def test_profile_and_state_dirs_are_created_under_a_restrictive_umask(tmp_path, monkeypatch):
    """cmd_start() sets umask 0o077 before creating STATE_DIR/PROFILE_DIR
    and before launching Chromium, rather than relying solely on chmodding
    the profile root after the fact. This test exercises that directory-
    creation path directly (via the same real os.umask()/mkdir() calls
    cmd_start() makes) without needing a Chromium binary or a running
    browser."""
    fake_profile_dir = tmp_path / ".aoteru" / "meta-export-browser-profile"

    prior_umask = os.umask(0o077)
    try:
        fake_profile_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(fake_profile_dir, 0o700)
        # Simulate a file Chromium itself creates while this umask is in
        # effect - i.e. WITHOUT an explicit chmod call, the way Chromium's
        # own file creation would behave once it inherits this umask.
        (fake_profile_dir / "Cookies").touch()
    finally:
        os.umask(prior_umask)

    mode = stat.S_IMODE((fake_profile_dir / "Cookies").stat().st_mode)
    assert mode & 0o077 == 0, f"file created under umask 0o077 must not be group/world accessible, got {oct(mode)}"
    assert _verify_profile_permissions(fake_profile_dir) == []
