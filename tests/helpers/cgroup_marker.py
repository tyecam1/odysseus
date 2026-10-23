"""Side-effect-free cgroup marker helpers shared by estate tests."""

import time


def _wait_for_cgroup_marker(marker, timeout=10):
    """Return a complete ``0::<path>`` cgroup marker once it is written.

    The shell creates the redirect target before ``cat`` writes it, so
    existence alone is not enough. A partial write can also contain only
    ``0::``; wait for a non-empty path and the terminating newline.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            text = marker.read_text()
        except FileNotFoundError:
            text = ""
        _, sep, rest = text.partition("::")
        if sep and rest.strip() and text.endswith("\n"):
            return rest.strip()
        time.sleep(0.05)
    raise AssertionError(f"cgroup marker never held a complete line: {marker}")
