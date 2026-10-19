"""Unit coverage for provider quota parsing and cooldown selection."""
from datetime import datetime, timedelta, timezone
from threading import Thread

import pytest

from src.estate_provider_quota import (
    ProviderCooldown,
    ProviderUnavailable,
    parse_quota_retry,
    resolve_provider,
)


NOW = datetime(2026, 10, 19, 10, 15)


def test_parse_usage_limit_with_24_hour_reset():
    assert parse_quota_retry("Usage limit reached; try again at 11:45", NOW) == timedelta(minutes=90)


def test_parse_rate_limit_case_insensitively():
    assert parse_quota_retry("RATE LIMIT. TRY AGAIN AT 10:20", NOW) == timedelta(minutes=5)


def test_parse_quota_exceeded_with_pm_reset():
    assert parse_quota_retry("quota exceeded; try again at 1:05 PM", NOW) == timedelta(hours=2, minutes=50)


def test_parse_midnight_in_12_hour_clock():
    assert parse_quota_retry("usage limit, try again at 12:30 AM", NOW) == timedelta(hours=14, minutes=15)


def test_parse_noon_in_12_hour_clock():
    assert parse_quota_retry("usage limit, try again at 12:30 PM", NOW) == timedelta(hours=2, minutes=15)


def test_parse_same_day_past_rolls_to_tomorrow():
    assert parse_quota_retry("usage limit; try again at 9:30", NOW) == timedelta(hours=23, minutes=15)


def test_parse_exact_reset_time_is_zero():
    assert parse_quota_retry("usage limit; try again at 10:15", NOW) == timedelta(0)


def test_parse_preserves_timezone_awareness():
    now = datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc)
    assert parse_quota_retry("quota exceeded, try again at 12:15 AM", now) == timedelta(minutes=45)


def test_unparseable_quota_uses_default_30_minutes():
    assert parse_quota_retry("usage limit reached; retry later", NOW) == timedelta(minutes=30)


def test_invalid_quota_timestamp_uses_default_30_minutes():
    assert parse_quota_retry("rate limit; try again at 25:99", NOW) == timedelta(minutes=30)


@pytest.mark.parametrize("message", [
    "request timed out after 180 seconds",
    "connection refused by upstream",
    "authentication failed: invalid token",
])
def test_non_quota_errors_return_none(message):
    assert parse_quota_retry(message, NOW) is None


def test_cooldown_is_inactive_when_unset():
    cooldown = ProviderCooldown(lambda: NOW)
    assert cooldown.active("codex") is False
    assert cooldown.remaining("codex") == timedelta(0)


def test_cooldown_set_accepts_absolute_expiry():
    cooldown = ProviderCooldown(lambda: NOW)
    until = NOW + timedelta(minutes=20)
    assert cooldown.set("codex", until) == until
    assert cooldown.active("codex") is True
    assert cooldown.remaining("codex") == timedelta(minutes=20)


def test_cooldown_boundary_now_equals_until_is_inactive():
    cooldown = ProviderCooldown(lambda: NOW)
    cooldown.set("codex", NOW)
    assert cooldown.active("codex") is False
    assert cooldown.expires_at("codex") is None


def test_resolve_provider_keeps_preferred_when_available():
    assert resolve_provider("codex", "glm", ProviderCooldown(lambda: NOW), NOW) == "codex"


def test_resolve_provider_switches_to_fallback_while_preferred_cools():
    cooldown = ProviderCooldown(lambda: NOW)
    cooldown.set("codex", timedelta(minutes=30))
    assert resolve_provider("codex", "glm", cooldown, NOW) == "glm"


def test_resolve_provider_raises_when_both_are_cooling():
    cooldown = ProviderCooldown(lambda: NOW)
    cooldown.set("codex", timedelta(minutes=30))
    cooldown.set("glm", timedelta(minutes=5))
    with pytest.raises(ProviderUnavailable):
        resolve_provider("codex", "glm", cooldown, NOW)


def test_cooldown_thread_safety_smoke_maintains_invariants():
    cooldown = ProviderCooldown(lambda: NOW)

    def exercise(index):
        for offset in range(100):
            cooldown.set("codex", NOW + timedelta(seconds=index + offset + 1))
            assert cooldown.remaining("codex", NOW) >= timedelta(0)
            assert isinstance(cooldown.active("codex", NOW), bool)

    threads = [Thread(target=exercise, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert cooldown.remaining("codex", NOW) >= timedelta(0)
