"""Passive Linux USB connection-event adapter.

The adapter accepts pyudev-shaped objects without importing pyudev.  Tests and
other callers can therefore provide any iterable of mappings/objects carrying
``action``, ``device_type``/``DEVTYPE``, and udev properties.

An allowlist match authorises only the device identity.  It does not establish
data access, inspect a filesystem, start acquisition, or call a model.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from math import floor
from typing import Callable, Iterable, Iterator, Mapping, Optional, Protocol


LOGGER = logging.getLogger(__name__)
UDEV_USB_ACTIONS = frozenset({"add", "change", "remove"})


class DeviceState(str, Enum):
    """State vocabulary defined by the primary-ingestion directive."""

    DEVICE_DETECTED = "device_detected"
    DEVICE_AUTHORISED = "device_authorised"
    DATA_ACCESS_READY = "data_access_ready"
    EXPORT_DISCOVERED = "export_discovered"
    IMPORT_COMPLETE = "import_complete"
    ENRICHMENT_PENDING = "enrichment_pending"
    HANDOFF_COMPLETE = "handoff_complete"
    PENDING_EXPORT = "pending_export"
    NO_NEW_MATERIAL = "no_new_material"
    BLOCKED_ACCESS = "blocked_access"
    RETRYABLE_ERROR = "retryable_error"
    PERMANENT_SCHEMA_ERROR = "permanent_schema_error"


@dataclass(frozen=True)
class AllowedDevice:
    """One exact serial/model allowlist entry."""

    serial: str
    model: str

    def __post_init__(self) -> None:
        if not self.serial.strip() or not self.model.strip():
            raise ValueError("allowlist entries require non-empty serial and model")


@dataclass(frozen=True)
class DeviceConnectionEvent:
    """A structured, non-acquiring observation emitted by the adapter."""

    action: str
    state: DeviceState
    transitions: tuple[DeviceState, ...]
    host_id: str
    device_serial: Optional[str]
    device_model: Optional[str]
    observed_at: datetime
    timestamp_bucket: int
    idempotency_key: str
    authorised: bool
    reason: Optional[str] = None

    def as_dict(self) -> dict:
        value = asdict(self)
        value["state"] = self.state.value
        value["transitions"] = [state.value for state in self.transitions]
        value["observed_at"] = self.observed_at.isoformat()
        return value


class DeviceEventSource(Protocol):
    """Thin injectable source implemented by any iterable of udev-like events."""

    def __iter__(self) -> Iterator[object]: ...


EventSink = Callable[[DeviceConnectionEvent], None]
Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def timestamp_bucket(observed_at: datetime, window_seconds: int) -> int:
    """Return the stable epoch bucket used for debounce and event identity."""

    if window_seconds <= 0:
        raise ValueError("debounce window must be greater than zero")
    return floor(_normalized_timestamp(observed_at).timestamp() / window_seconds)


def make_idempotency_key(
    host_id: str,
    device_serial: str,
    observed_at: datetime,
    window_seconds: int,
) -> str:
    """Hash host, serial, and timestamp bucket into a SourceEvent-safe key."""

    if not host_id.strip():
        raise ValueError("host_id must be non-empty")
    bucket = timestamp_bucket(observed_at, window_seconds)
    identity = f"{host_id.strip()}\0{device_serial.strip()}\0{bucket}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _event_value(event: object, *names: str) -> Optional[str]:
    properties = getattr(event, "properties", None)
    if isinstance(event, Mapping):
        properties = event.get("properties", properties)

    for name in names:
        value = event.get(name) if isinstance(event, Mapping) else getattr(event, name, None)
        if value is None and isinstance(properties, Mapping):
            value = properties.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _default_sink(event: DeviceConnectionEvent) -> None:
    LOGGER.info("usb_device_event %s", json.dumps(event.as_dict(), sort_keys=True))


class DeviceEventAdapter:
    """Validate, debounce, and label passive Linux USB device observations."""

    def __init__(
        self,
        *,
        host_id: str,
        allowlist: Iterable[AllowedDevice],
        debounce_window_seconds: int = 5,
        event_sink: EventSink = _default_sink,
        clock: Clock = _utcnow,
    ) -> None:
        if not host_id.strip():
            raise ValueError("host_id must be non-empty")
        if debounce_window_seconds <= 0:
            raise ValueError("debounce window must be greater than zero")

        self.host_id = host_id.strip()
        self.debounce_window_seconds = debounce_window_seconds
        self._allowlist = {(item.serial.strip(), item.model.strip()) for item in allowlist}
        self._event_sink = event_sink
        self._clock = clock
        self._seen_keys: dict[str, int] = {}

    def consume(self, source: DeviceEventSource) -> Iterator[DeviceConnectionEvent]:
        """Yield accepted observations; duplicate/non-USB events yield nothing."""

        for raw_event in source:
            event = self.handle_event(raw_event)
            if event is not None:
                yield event

    def handle_event(self, raw_event: object) -> Optional[DeviceConnectionEvent]:
        action = _event_value(raw_event, "action", "ACTION")
        if action not in UDEV_USB_ACTIONS:
            return None

        subsystem = _event_value(raw_event, "subsystem", "SUBSYSTEM")
        device_type = _event_value(raw_event, "device_type", "DEVTYPE")
        if (subsystem is not None and subsystem != "usb") or (
            device_type is not None and device_type != "usb_device"
        ):
            return None

        serial = _event_value(raw_event, "ID_SERIAL_SHORT", "serial")
        model = _event_value(raw_event, "ID_MODEL", "model")
        observed_at = _normalized_timestamp(self._clock())
        bucket = timestamp_bucket(observed_at, self.debounce_window_seconds)
        key = make_idempotency_key(
            self.host_id,
            serial or "<missing-serial>",
            observed_at,
            self.debounce_window_seconds,
        )

        if key in self._seen_keys:
            return None
        self._seen_keys[key] = bucket
        self._seen_keys = {
            seen_key: seen_bucket
            for seen_key, seen_bucket in self._seen_keys.items()
            if seen_bucket >= bucket - 1
        }

        authorised = serial is not None and model is not None and (serial, model) in self._allowlist
        if authorised:
            state = DeviceState.DEVICE_AUTHORISED
            transitions = (DeviceState.DEVICE_DETECTED, DeviceState.DEVICE_AUTHORISED)
            reason = None
        else:
            state = DeviceState.BLOCKED_ACCESS
            transitions = (DeviceState.DEVICE_DETECTED, DeviceState.BLOCKED_ACCESS)
            reason = "device_identity_not_allowlisted"

        event = DeviceConnectionEvent(
            action=action,
            state=state,
            transitions=transitions,
            host_id=self.host_id,
            device_serial=serial,
            device_model=model,
            observed_at=observed_at,
            timestamp_bucket=bucket,
            idempotency_key=key,
            authorised=authorised,
            reason=reason,
        )
        self._event_sink(event)
        return event
