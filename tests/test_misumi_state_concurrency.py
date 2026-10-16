"""Round-5 repair (independent Opus review of PR #123, M4): adaptation state is safe across PROCESSES and fails CLOSED.

Reported: candidates.json was read-modify-written under a per-instance threading.Lock with a non-atomic write_text, so four
processes x 40 record_evidence calls lost candidates and produced corrupt JSON and corrupt JSONL lines; and a decode error was
treated as "empty", so the next write wiped every candidate, including rejections.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from src.misumi_persona_state import PersonaStateStore
from src.misumi_routing_adaptation import RoutingAdaptationStore
from tests.test_misumi_durable_authority import _ratify_brief, _turn, estate  # noqa: F401  (route fixture with bearer shim)
from tests.test_misumi_ratification_dialogue import _isolated_seed_root  # noqa: F401  (autouse seed root)

REPO = Path(__file__).resolve().parents[1]
PROCS, PER_PROC = 4, 40

_WORKER = textwrap.dedent("""
    import sys
    kind, root, idx, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    if kind == "style":
        from src.misumi_persona_state import PersonaStateStore
        dims = [("response_depth", "brief"), ("technical_depth", "plain"), ("structure", "bullets"), ("intervention_style", "reactive")]
        store = PersonaStateStore(root)
        dim, val = dims[idx % len(dims)]
        for i in range(n):
            store.record_evidence(type="correction", persona=f"p{idx}", dimension=dim, value=val, prompt="too long",
                                  signal="too long", owner=f"o{idx}", session_id=f"s{idx}-{i}")
    else:
        from src.misumi_routing_adaptation import RoutingAdaptationStore
        store = RoutingAdaptationStore(root)
        for i in range(n):
            store.record_evidence(type="temporary_choice", cue=[f"cue{idx}"], previous_persona="misato", proposed_persona="jin",
                                  prompt="switch", owner=f"o{idx}", session_id=f"s{idx}-{i}")
""")


def _hammer(kind, root):
    # The subject here is lost or corrupt writes, not latency: give lock waits generous room under a 4-process pile-up.
    env = dict(os.environ, PYTHONPATH=str(REPO), MISUMI_STATE_LOCK_TIMEOUT_S="60")
    procs = [subprocess.Popen([sys.executable, "-c", _WORKER, kind, str(root), str(i), str(PER_PROC)], cwd=str(REPO), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(PROCS)]
    for proc in procs:
        out, err = proc.communicate(timeout=300)
        assert proc.returncode == 0, err.decode("utf-8", "replace")[-2000:]


@pytest.mark.parametrize("kind", ["style", "routing"])
def test_many_processes_writing_at_once_lose_nothing_and_corrupt_nothing(tmp_path, kind):
    root = tmp_path / kind
    _hammer(kind, root)
    lines = (root / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == PROCS * PER_PROC
    evidence = [json.loads(line) for line in lines]           # every line is one whole JSON record
    assert len({row["evidence_id"] for row in evidence}) == PROCS * PER_PROC
    candidates = json.loads((root / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    assert len(candidates) == PROCS
    folded = sum(len(c["supporting_evidence"]) + len(c["contradicting_evidence"]) for c in candidates.values())
    assert folded == PROCS * PER_PROC
    assert not [p for p in root.iterdir() if p.name.endswith(".tmp")]   # atomic writes leave no temp files behind


def _rejected_candidate(store):
    for i in range(3):
        store.record_evidence(type="correction", persona="misato", dimension="response_depth", value="brief",
                              prompt="That was too long", session_id=f"s{i}", owner="alice")
    candidate = store.get_candidate("misato", "response_depth")
    store.reject(candidate["candidate_id"], "declined")
    return candidate["candidate_id"]


@pytest.mark.parametrize("damage", [b"{\"candidates\": {", b"\x00\x00garbage", b"[1, 2, 3]\n"])
def test_a_corrupt_candidates_file_is_quarantined_and_never_read_as_empty(tmp_path, damage):
    from src.misumi_state_io import StateCorruptError

    store = PersonaStateStore(tmp_path / "s")
    _rejected_candidate(store)
    original = store.candidates_path.read_bytes()
    store.candidates_path.write_bytes(damage)
    with pytest.raises(StateCorruptError):
        store.record_evidence(type="correction", persona="misato", dimension="response_depth", value="brief",
                              prompt="That was too long", session_id="s9", owner="alice")
    quarantined = list((tmp_path / "s" / "quarantine").iterdir())
    assert [p.read_bytes() for p in quarantined] == [damage]          # the damaged bytes are preserved for repair
    assert (tmp_path / "s" / "STATE_CORRUPT.json").exists()
    for call in (store.all_candidates, store.active_revisions, lambda: store.list_evidence()):
        with pytest.raises(StateCorruptError):                          # every later read refuses too: nothing is "empty"
            call()
    assert b"rejected" in original and not store.candidates_path.exists()   # no "empty" file was written over the rejection


@pytest.mark.parametrize("damage", [b"{not json}\n", b"{\"evidence_id\": \"x\"", b"[]\n"])
def test_a_corrupt_log_line_fails_closed_for_capture_and_promotion(tmp_path, damage):
    from src.misumi_state_io import StateCorruptError

    store = RoutingAdaptationStore(tmp_path / "r")
    outcome_root = tmp_path / "r"
    store.record_evidence(type="temporary_choice", cue=["compost"], previous_persona="misato", proposed_persona="jin",
                          prompt="switch", session_id="s", owner="alice")
    with (outcome_root / "evidence.jsonl").open("ab") as handle:
        handle.write(damage)
    with pytest.raises(StateCorruptError):
        store.record_evidence(type="temporary_choice", cue=["compost"], previous_persona="misato", proposed_persona="jin",
                              prompt="switch", session_id="s", owner="alice")
    candidate = None
    with pytest.raises(StateCorruptError):
        candidate = store.get_candidate(["compost"])
    assert candidate is None
    with pytest.raises(StateCorruptError):
        store.promote("aff-anything", authorisation={"type": "operator_ratification", "principal": "op"})
    assert store.apply_learned_overlays("compost bin", "misato", []) == ("misato", None)   # learned routing withheld


def test_the_route_withholds_learned_style_and_capture_when_the_store_is_quarantined(estate, tmp_path):
    _ratify_brief(estate)
    revisions = tmp_path / "persona-state" / "revisions.jsonl"
    revisions.write_bytes(revisions.read_bytes() + b"{broken\n")
    reply = _turn(estate, "Explain how a rainbow forms", session="q1")
    assert estate["calls"][-1]["style"] == {} and not (reply.get("persona_state") or {}).get("applied")
    reply = _turn(estate, "From now on use bullet points", session="q2")
    assert "ratification_offer" not in reply
    inspect = estate["client"].get("/misumi/persona-state", headers={"x-test-token": "ex", "x-test-owner": "op"})
    assert inspect.status_code == 503


def test_a_document_is_replaced_atomically_so_a_failed_replace_leaves_the_previous_one_intact(tmp_path, monkeypatch):
    import src.misumi_state_io as state_io

    store = PersonaStateStore(tmp_path / "s")
    _rejected_candidate(store)
    before = store.candidates_path.read_bytes()

    def failing_replace(src, dst):
        raise PermissionError("simulated crash at the rename")

    monkeypatch.setattr(state_io.os, "replace", failing_replace)
    monkeypatch.setattr(state_io.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        store.record_evidence(type="correction", persona="jin", dimension="structure", value="bullets",
                              prompt="use a list", session_id="s", owner="alice")
    assert store.candidates_path.read_bytes() == before
    assert not [p for p in (tmp_path / "s").iterdir() if p.name.endswith(".tmp")]
