"""Provider-scoped quota parsing, cooldowns, and fallback selection.

Quota state is deliberately independent from worker/launcher availability:
an exhausted provider does not make its host unhealthy, and an unavailable
fallback never changes the preferred provider's cooldown.
"""
from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional


_QUOTA_MARKERS = ("usage limit", "rate limit", "quota exceeded")
_RETRY_AT = re.compile(
    r"try\s+again\s+at\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?:\s*(?P<meridiem>[ap](?:\.?m\.?)?))?",
    re.IGNORECASE,
)
_DEFAULT_QUOTA_RETRY = timedelta(minutes=30)


class ProviderUnavailable(RuntimeError):
    """No provider in the bounded preferred/fallback chain is available."""


def parse_quota_retry(error_text: str, now: datetime) -> Optional[timedelta]:
    """Return the retry delay encoded by a quota error.

    Only explicit quota markers qualify. A quota message without a usable
    ``try again at H:MM [AM|PM]`` timestamp receives a conservative 30-minute
    cooldown. A parsed time earlier than ``now`` is the next day's occurrence.
    """
    text = str(error_text or "")
    lowered = text.lower()
    if not any(marker in lowered for marker in _QUOTA_MARKERS):
        return None

    match = _RETRY_AT.search(text)
    if match is None:
        return _DEFAULT_QUOTA_RETRY

    try:
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        meridiem = (match.group("meridiem") or "").lower().replace(".", "")
        if minute > 59:
            raise ValueError("minute out of range")
        if meridiem:
            if not 1 <= hour <= 12:
                raise ValueError("12-hour clock hour out of range")
            hour = hour % 12 + (12 if meridiem == "pm" else 0)
        elif not 0 <= hour <= 23:
            raise ValueError("24-hour clock hour out of range")
        retry_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (TypeError, ValueError):
        return _DEFAULT_QUOTA_RETRY

    if retry_at < now:
        retry_at += timedelta(days=1)
    return retry_at - now


class ProviderCooldown:
    """Thread-safe in-memory provider cooldown registry."""

    def __init__(self, time_fn: Optional[Callable[[], datetime]] = None, *,
                 now: Optional[Callable[[], datetime]] = None):
        if time_fn is not None and now is not None:
            raise TypeError("pass either time_fn or now, not both")
        self._time_fn = time_fn or now or datetime.now
        self._until: dict[str, datetime] = {}
        self._lock = threading.RLock()

    def set(self, provider: str, until: datetime | timedelta, *,
            now: Optional[datetime] = None) -> datetime:
        """Set ``provider`` cooling until an absolute time or for a delay."""
        current = now or self._time_fn()
        expires_at = current + until if isinstance(until, timedelta) else until
        if not isinstance(expires_at, datetime):
            raise TypeError("until must be a datetime or timedelta")
        with self._lock:
            self._until[provider] = expires_at
        return expires_at

    def active(self, provider: str, now: Optional[datetime] = None) -> bool:
        current = now or self._time_fn()
        with self._lock:
            until = self._until.get(provider)
            if until is None:
                return False
            if current >= until:
                self._until.pop(provider, None)
                return False
            return True

    def remaining(self, provider: str, now: Optional[datetime] = None) -> timedelta:
        current = now or self._time_fn()
        with self._lock:
            until = self._until.get(provider)
            if until is None or current >= until:
                if until is not None:
                    self._until.pop(provider, None)
                return timedelta(0)
            return until - current

    def expires_at(self, provider: str, now: Optional[datetime] = None) -> Optional[datetime]:
        """Return active reset evidence without exposing mutable state."""
        current = now or self._time_fn()
        with self._lock:
            until = self._until.get(provider)
            if until is None or current >= until:
                if until is not None:
                    self._until.pop(provider, None)
                return None
            return until


def resolve_provider(preferred: str, fallback: str, cooldown: ProviderCooldown,
                     now: datetime) -> str:
    """Select the preferred provider unless it is cooling, then fallback."""
    if not cooldown.active(preferred, now):
        return preferred
    if not cooldown.active(fallback, now):
        return fallback
    raise ProviderUnavailable(
        f"providers {preferred!r} and {fallback!r} are both cooling"
    )
