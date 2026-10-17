"""Synthetic-only tests for the passive USB device-event adapter.

No test in this module connects to udev or accesses a real device.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.device_events import (
    AllowedDevice,
    DeviceEventAdapter,
    DeviceState,
    make_idempotency_key,
)


SYNTHETIC_TIME = datetime(2026, 10, 17, 12, 0, 2, tzinfo=timezone.utc)
ALLOWLIST = [AllowedDevice(serial="GRAPHENE-001", model="Pixel_9")]


class RecordingSink:
    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(event)

    def __call__(self, event):
        """Let each regression exercise the pre-repair callable-sink path."""

        self.events.append(event.as_dict())


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
        sink = RecordingSink()
        adapter = DeviceEventAdapter(
            host_id="test-host",
            allowlist=ALLOWLIST,
            event_sink=sink,
            clock=lambda: SYNTHETIC_TIME,
        )

        event = adapter.handle_event(synthetic_udev_event(serial=serial, model=model))

        assert event is not None
        assert event.authorised is False
        assert event.state is DeviceState.BLOCKED_ACCESS
        assert event.transitions == (DeviceState.DEVICE_DETECTED, DeviceState.BLOCKED_ACCESS)
        assert sink.events == [event.as_dict()]


def test_synthetic_duplicate_connection_storm_is_debounced():
    sink = RecordingSink()
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        debounce_window_seconds=10,
        event_sink=sink,
        clock=lambda: SYNTHETIC_TIME,
    )

    first = adapter.handle_event(synthetic_udev_event(action="add"))
    duplicate = adapter.handle_event(synthetic_udev_event(action="add"))

    assert first is not None
    assert duplicate is None
    assert sink.events == [first.as_dict()]


def test_synthetic_elapsed_debounce_crosses_epoch_bucket_boundary():
    first_time = SYNTHETIC_TIME + timedelta(seconds=7, milliseconds=900)
    moments = iter(
        (
            first_time,
            first_time + timedelta(milliseconds=200),
            first_time + timedelta(seconds=10),
        )
    )
    sink = RecordingSink()
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        debounce_window_seconds=10,
        event_sink=sink,
        clock=lambda: next(moments),
    )

    first = adapter.handle_event(synthetic_udev_event())
    across_boundary = adapter.handle_event(synthetic_udev_event())
    after_window = adapter.handle_event(synthetic_udev_event())

    assert first is not None
    assert across_boundary is None
    assert after_window is not None
    assert sink.events == [first.as_dict(), after_window.as_dict()]


def test_synthetic_idempotency_key_includes_action_and_full_identity():
    first = make_idempotency_key(
        "test-host", "add", "GRAPHENE-001", "Pixel_9", SYNTHETIC_TIME
    )

    assert first != make_idempotency_key(
        "test-host", "remove", "GRAPHENE-001", "Pixel_9", SYNTHETIC_TIME
    )
    assert first != make_idempotency_key(
        "test-host", "add", "GRAPHENE-001", "Wrong_Model", SYNTHETIC_TIME
    )
    assert first != make_idempotency_key(
        "other-host", "add", "GRAPHENE-001", "Pixel_9", SYNTHETIC_TIME
    )
    assert first != make_idempotency_key(
        "test-host", "add", "OTHER-SERIAL", "Pixel_9", SYNTHETIC_TIME
    )


def test_synthetic_usb_provenance_fails_closed_when_markers_are_missing():
    sink = RecordingSink()
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        event_sink=sink,
        clock=lambda: SYNTHETIC_TIME,
    )
    raw_event = synthetic_udev_event()
    del raw_event["subsystem"]
    del raw_event["device_type"]

    assert adapter.handle_event(raw_event) is None
    assert sink.events == []


def test_synthetic_rejected_identity_does_not_consume_debounce_state():
    sink = RecordingSink()
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        event_sink=sink,
        clock=lambda: SYNTHETIC_TIME,
    )

    rejected = adapter.handle_event(synthetic_udev_event(model="Wrong_Model"))
    repeated_rejection = adapter.handle_event(synthetic_udev_event(model="Wrong_Model"))
    authorised = adapter.handle_event(synthetic_udev_event())

    assert rejected is not None and rejected.authorised is False
    assert repeated_rejection is not None and repeated_rejection.authorised is False
    assert authorised is not None and authorised.authorised is True
    assert sink.events == [
        rejected.as_dict(),
        repeated_rejection.as_dict(),
        authorised.as_dict(),
    ]


def test_synthetic_state_vocabulary_and_authorisation_labelling():
    expected_labels = {
        "device_detected",
        "device_authorised",
        "device_removed",
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
    sink = RecordingSink()
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        event_sink=sink,
        clock=lambda: SYNTHETIC_TIME,
    )

    removed = adapter.handle_event(synthetic_udev_event(action="remove"))
    added = adapter.handle_event(synthetic_udev_event(action="add"))

    assert {state.value for state in DeviceState} == expected_labels
    assert removed is not None
    assert removed.state is DeviceState.DEVICE_REMOVED
    assert removed.transitions == (DeviceState.DEVICE_REMOVED,)
    assert DeviceState.DEVICE_AUTHORISED not in removed.transitions
    assert added is not None
    assert added.state is DeviceState.DEVICE_AUTHORISED
    assert [event["action"] for event in sink.events] == ["remove", "add"]


def test_synthetic_detection_performs_no_acquisition_or_model_work():
    class SyntheticSource:
        def __iter__(self):
            yield synthetic_udev_event()

        def acquire(self):  # pragma: no cover - a call would fail the test
            raise AssertionError("passive adapter must not acquire device data")

    class PassiveSink:
        def __init__(self):
            self.events = []

        def emit(self, event):
            assert isinstance(event, dict)
            assert event["state"] == "device_authorised"
            assert event["transitions"] == ["device_detected", "device_authorised"]
            self.events.append(event)

        def acquire(self):  # pragma: no cover - a call would fail the test
            raise AssertionError("adapter must call only the sink emit contract")

        def infer(self):  # pragma: no cover - a call would fail the test
            raise AssertionError("adapter must not invoke model work")

    sink = PassiveSink()
    adapter = DeviceEventAdapter(
        host_id="test-host",
        allowlist=ALLOWLIST,
        event_sink=sink,
        clock=lambda: SYNTHETIC_TIME,
    )

    events = list(adapter.consume(SyntheticSource()))

    assert sink.events == [events[0].as_dict()]
    assert events[0].state is DeviceState.DEVICE_AUTHORISED
    assert DeviceState.DATA_ACCESS_READY not in events[0].transitions
    assert DeviceState.EXPORT_DISCOVERED not in events[0].transitions


def test_synthetic_sink_rejects_unrestricted_callables():
    with pytest.raises(TypeError, match="event_sink must implement emit"):
        DeviceEventAdapter(
            host_id="test-host",
            allowlist=ALLOWLIST,
            event_sink=lambda event: None,
            clock=lambda: SYNTHETIC_TIME,
        )


def test_synthetic_sink_rejects_non_callable_emit_attribute():
    class InvalidSink:
        emit = "not-callable"

    with pytest.raises(TypeError, match="event_sink must implement emit"):
        DeviceEventAdapter(
            host_id="test-host",
            allowlist=ALLOWLIST,
            event_sink=InvalidSink(),
            clock=lambda: SYNTHETIC_TIME,
        )
