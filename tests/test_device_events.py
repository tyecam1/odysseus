"""Synthetic-only tests for the passive USB device-event adapter.

No test in this module connects to udev or accesses a real device.
"""

from datetime import datetime, timedelta, timezone

from src.device_events import (
    AllowedDevice,
    DeviceEventAdapter,
    DeviceState,
    make_idempotency_key,
)


SYNTHETIC_TIME = datetime(2026, 10, 17, 12, 0, 2, tzinfo=timezone.utc)
ALLOWLIST = [AllowedDevice(serial="GRAPHENE-001", model="Pixel_9")]


def synthetic_udev_event(*, serial="GRAPHENE-001", model="Pixel_9", action="add"):
    return {
        "action": action,
        "subsystem": "usb",
        "device_type": "usb_device",
        "properties": {"ID_SERIAL_SHORT": serial, "ID_MODEL": model},
        "synthetic": "true",
    }


def test_synthetic_unknown_device_is_rejected_with_blocked_access():
    for serial, model in (("UNKNOWN-999", "Pixel_9"), ("GRAPHENE-001", "Wrong_Model")):
        emitted = []
        adapter = DeviceEventAdapter(
            host_id="test-host",
            allowlist=ALLOWLIST,
            event_sink=emitted.append,
            clock=lambda: SYNTHETIC_TIME,
        )

        event = adapter.handle_event(synthetic_udev_event(serial=serial, model=model))

        assert event is not None
        assert event.authorised is False
        assert event.state is DeviceState.BLOCKED_ACCESS
        assert event.transitions == (DeviceState.DEVICE_DETECTED, DeviceState.BLOCKED_ACCESS)
        assert emitted == [event]


def test_synthetic_duplicate_connection_storm_is_debounced():
    emitted = []
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        debounce_window_seconds=10,
        event_sink=emitted.append,
        clock=lambda: SYNTHETIC_TIME,
    )

    first = adapter.handle_event(synthetic_udev_event(action="add"))
    duplicate = adapter.handle_event(synthetic_udev_event(action="change"))

    assert first is not None
    assert duplicate is None
    assert emitted == [first]


def test_synthetic_idempotency_key_is_stable_within_timestamp_bucket():
    first = make_idempotency_key("test-host", "GRAPHENE-001", SYNTHETIC_TIME, 10)
    same_bucket = make_idempotency_key(
        "test-host", "GRAPHENE-001", SYNTHETIC_TIME + timedelta(seconds=7), 10
    )
    next_bucket = make_idempotency_key(
        "test-host", "GRAPHENE-001", SYNTHETIC_TIME + timedelta(seconds=8), 10
    )

    assert first == same_bucket
    assert first != next_bucket
    assert first != make_idempotency_key("other-host", "GRAPHENE-001", SYNTHETIC_TIME, 10)
    assert first != make_idempotency_key("test-host", "OTHER-SERIAL", SYNTHETIC_TIME, 10)


def test_synthetic_state_vocabulary_and_authorisation_labelling():
    expected_labels = {
        "device_detected",
        "device_authorised",
        "data_access_ready",
        "export_discovered",
        "import_complete",
        "enrichment_pending",
        "handoff_complete",
        "pending_export",
        "no_new_material",
        "blocked_access",
        "retryable_error",
        "permanent_schema_error",
    }
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        event_sink=lambda event: None,
        clock=lambda: SYNTHETIC_TIME,
    )

    event = adapter.handle_event(synthetic_udev_event(action="remove"))

    assert {state.value for state in DeviceState} == expected_labels
    assert event is not None
    assert event.state is DeviceState.DEVICE_AUTHORISED
    assert event.transitions == (DeviceState.DEVICE_DETECTED, DeviceState.DEVICE_AUTHORISED)
    assert event.action == "remove"


def test_synthetic_detection_performs_no_acquisition_or_model_work():
    class SyntheticSource:
        def __iter__(self):
            yield synthetic_udev_event()

        def acquire(self):  # pragma: no cover - a call would fail the test
            raise AssertionError("passive adapter must not acquire device data")

    emitted = []
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        event_sink=emitted.append,
        clock=lambda: SYNTHETIC_TIME,
    )

    events = list(adapter.consume(SyntheticSource()))

    assert events == emitted
    assert events[0].state is DeviceState.DEVICE_AUTHORISED
    assert DeviceState.DATA_ACCESS_READY not in events[0].transitions
    assert DeviceState.EXPORT_DISCOVERED not in events[0].transitions
