"""Household GPU contention as an up-front admission signal (src/gpu_admission.py).

Everything here is simulated: no GPU, no nvidia-smi, no host is touched. These tests prove the admission LOGIC;
they qualify nothing. The real acceptance is a re-run of the ``local-fast`` canary on the physical RTX 3070
when it is free (docs/aoteru-multihost-execution-evidence.md).
"""

import socket
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import yaml

import src.estate_router as estate_router
from src import gpu_admission as ga

CFG = {"busy_util_pct": 60}
NOW = datetime(2026, 10, 2, 13, 0, 0, tzinfo=timezone.utc)


def reading(utils, *, used=4930.0, total=8192.0, age_s=2.0, available=True, error=None):
    return {
        "available": available,
        "error": error,
        "samples": [{"util_pct": float(u), "mem_used_mib": used, "mem_total_mib": total} for u in utils],
        "interval_s": 0.4,
        "taken_at": (NOW - timedelta(seconds=age_s)).isoformat(),
    }


def classify(r, *, in_flight=(), config=CFG):
    return ga.classify_gpu_load(r, in_flight=list(in_flight), config=config, now=NOW)


# ---- parsing ------------------------------------------------------------------------------------

def test_parse_the_exact_windows_output_seen_on_home():
    assert ga.parse_gpu_query("98, 4930, 8192\n") == [
        {"util_pct": 98.0, "mem_used_mib": 4930.0, "mem_total_mib": 8192.0}
    ]


def test_unreadable_fields_are_none_not_idle():
    # WDDM prints [N/A] for fields it cannot report. That must never become "0% utilisation".
    assert ga.parse_gpu_query("[N/A], [N/A], [N/A]\n") == [None]
    assert ga.parse_gpu_query("[Not Supported], 100, 8192") == [None]


def test_parse_keeps_gpu_index_positions_with_a_bad_line_in_the_middle():
    out = ga.parse_gpu_query("10, 100, 8192\ngarbage line\n20, 200, 8192\n")
    assert [g and g["util_pct"] for g in out] == [10.0, None, 20.0]


@pytest.mark.parametrize("line", ["101, 10, 8192", "-1, 10, 8192", "5, -1, 8192", "5, 10, 0", "1,2", "1,2,3,4"])
def test_out_of_range_or_malformed_lines_are_none(line):
    assert ga.parse_gpu_query(line) == [None]


def test_parse_empty_output():
    assert ga.parse_gpu_query("") == []
    assert ga.parse_gpu_query("\n\n") == []


# ---- sampling -----------------------------------------------------------------------------------

def fake_run(outputs, calls=None):
    it = iter(outputs)

    def run(cmd, **kwargs):
        if calls is not None:
            calls.append((list(cmd), kwargs))
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(returncode=item[0], stdout=item[1])

    return run


def test_sample_takes_n_readings_with_sleeps_between_them():
    sleeps, calls = [], []
    out = ga.sample_gpu(samples=3, interval_s=0.25, sleep=sleeps.append,
                        run=fake_run([(0, "97, 4900, 8192"), (0, "98, 4910, 8192"), (0, "99, 4920, 8192")], calls))
    assert out["available"] is True and out["error"] is None
    assert [s["util_pct"] for s in out["samples"]] == [97.0, 98.0, 99.0]
    assert sleeps == [0.25, 0.25]  # between readings, not before the first or after the last
    assert calls[0][0] == ga.NVIDIA_SMI_QUERY and "--query-gpu" in calls[0][0][1]


def test_sample_missing_binary_is_unavailable_not_free():
    out = ga.sample_gpu(samples=3, run=fake_run([FileNotFoundError("nvidia-smi")]), sleep=lambda s: None)
    assert out["available"] is False and out["samples"] == []
    assert "FileNotFoundError" in out["error"]


def test_sample_nonzero_exit_and_unreadable_gpu0_are_unavailable():
    out = ga.sample_gpu(samples=1, run=fake_run([(9, "")]), sleep=lambda s: None)
    assert out["available"] is False and "exited 9" in out["error"]
    out = ga.sample_gpu(samples=1, run=fake_run([(0, "[N/A], [N/A], [N/A]")]), sleep=lambda s: None)
    assert out["available"] is False and "GPU 0" in out["error"]


def test_a_failure_part_way_discards_the_partial_picture():
    out = ga.sample_gpu(samples=3, run=fake_run([(0, "99, 1, 8192"), (0, "99, 1, 8192"), TimeoutError()]),
                        sleep=lambda s: None)
    assert out["available"] is False and out["samples"] == []


def test_sample_at_least_one_reading_even_if_asked_for_zero():
    out = ga.sample_gpu(samples=0, run=fake_run([(0, "50, 1, 8192")]), sleep=lambda s: None)
    assert out["available"] is True and len(out["samples"]) == 1


# ---- classification -----------------------------------------------------------------------------

def test_not_configured_is_disabled_and_never_withholds():
    for cfg in (None, "x", {"enabled": False, "busy_util_pct": 1}):
        assert classify(reading([100, 100, 100]), config=cfg)["state"] == "disabled"


def test_the_incident_is_busy_and_names_its_numbers():
    out = classify(reading([98, 98, 98], used=7800.0, total=8192.0))
    assert out["state"] == "busy"
    assert "98% utilisation sustained over 3 samples" in out["reason"]
    assert "7.6 of 8.0 GB VRAM used" in out["reason"]
    assert out["util_pct"] == 98.0 and out["sample_count"] == 3


def test_idle_gpu_is_free():
    assert classify(reading([2, 3, 1]))["state"] == "free"


def test_a_brief_spike_is_not_busy_every_sample_must_be():
    assert classify(reading([5, 99, 5]))["state"] == "free"
    assert classify(reading([99, 99, 40]))["state"] == "free"  # one low sample breaks "sustained"


def test_the_threshold_is_inclusive_and_configurable():
    assert classify(reading([60, 60, 60]))["state"] == "busy"
    assert classify(reading([59, 59, 59]))["state"] == "free"
    assert classify(reading([59, 59, 59]), config={"busy_util_pct": 50})["state"] == "busy"


def test_load_explained_by_estate_work_in_flight_is_not_household_contention():
    out = classify(reading([99, 99, 99]), in_flight=["exec-1"])
    assert out["state"] == "free" and "1 estate execution(s) in flight" in out["reason"]


def test_low_free_vram_can_make_a_host_busy_when_configured():
    r = reading([5, 5, 5], used=7600.0, total=8192.0)
    assert classify(r)["state"] == "free"  # no memory rule configured
    out = classify(r, config={"busy_util_pct": 60, "min_free_vram_mib": 2048})
    assert out["state"] == "busy" and "only 0.6 GB VRAM free (needs 2.0 GB)" in out["reason"]


@pytest.mark.parametrize("bad", [
    None,
    "not a dict",
    {"available": False, "error": "nvidia-smi unavailable: FileNotFoundError", "samples": []},
    {"available": True, "samples": []},
])
def test_no_usable_reading_is_unknown_never_free(bad):
    out = classify(bad)
    assert out["state"] == "unknown" and "not treated as free" in out["reason"]


def test_a_stale_or_untimestamped_or_future_reading_is_unknown():
    assert classify(reading([1, 1, 1], age_s=61.0))["state"] == "unknown"
    r = reading([1, 1, 1])
    r["taken_at"] = "not a time"
    assert classify(r)["state"] == "unknown"
    del r["taken_at"]
    assert classify(r)["state"] == "unknown"
    assert classify(reading([1, 1, 1], age_s=-600.0))["state"] == "unknown"  # clock skew


def test_stale_window_is_configurable():
    assert classify(reading([1, 1, 1], age_s=61.0), config={"busy_util_pct": 60, "max_reading_age_s": 120})["state"] == "free"


def test_classification_does_not_mutate_its_inputs():
    r, cfg, inflight = reading([98, 98, 98]), dict(CFG), ["a"]
    before = (repr(r), repr(cfg), repr(inflight))
    ga.classify_gpu_load(r, in_flight=inflight, config=cfg, now=NOW)
    assert (repr(r), repr(cfg), repr(inflight)) == before


# ---- router integration -------------------------------------------------------------------------

@pytest.fixture
def routed(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "estate.yaml").write_text(yaml.safe_dump({
        "hosts": [
            {"id": "test-lab", "hostname": "THIS-HOST", "role": "lab", "identity_verified": True,
             "worker": {"enabled": True, "transport": "local", "qualified_executors": ["local"]}},
            {"id": "test-home", "hostname": "OTHER-HOST", "role": "home", "identity_verified": True,
             "worker": {"enabled": True, "transport": "ssh", "qualified_executors": ["local"],
                        "gpu_admission": {"busy_util_pct": 60}}},
        ],
    }))
    (config_dir / "models.yaml").write_text(yaml.safe_dump({
        "capabilities": [
            {"alias": "local-fast", "binding": "test-model-fast",
             "qualified_hosts": {"test-lab": {"evidence": "t"}, "test-home": {"evidence": "t"}}},
        ],
    }))
    monkeypatch.setattr(estate_router, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(socket, "gethostname", lambda: "THIS-HOST")
    import src.estate_worker_client as client

    health = {"gpu_load": reading([2, 2, 2]), "in_flight": []}
    seen = {"health_calls": []}

    def fake_health(host_id, *, deadline_s=20.0):
        seen["health_calls"].append(host_id)
        return dict(health)

    monkeypatch.setattr(client, "worker_health", fake_health)
    monkeypatch.setattr(client, "worker_inventory", lambda host_id, models=None, *, deadline_s=30.0: {
        "models": [{"name": "test-model-fast", "digest": "x"}]})
    # classify against the same clock the readings were built with
    real = ga.classify_gpu_load
    monkeypatch.setattr(ga, "classify_gpu_load", lambda r, *, in_flight, config, now=None: real(r, in_flight=in_flight, config=config, now=NOW))
    return SimpleNamespace(health=health, seen=seen, client=client)


def test_busy_home_withholds_local_inference_up_front_with_a_named_reason(routed):
    routed.health["gpu_load"] = reading([98, 98, 98], used=7800.0)
    out = estate_router.resolve_alias("local-fast", "test-home")
    assert out["resolved"] is False
    assert out["reason"].startswith("withheld")
    assert "household GPU busy" in out["reason"] and "98%" in out["reason"]
    assert out["gpu_admission"]["state"] == "busy"
    assert out["concrete_model"] == "test-model-fast"


def test_a_busy_home_never_reroutes_by_itself(routed):
    # The refusal names the host that was asked; it does not return another host's resolution.
    routed.health["gpu_load"] = reading([98, 98, 98])
    out = estate_router.resolve_alias("local-fast", "test-home")
    assert out["resolved"] is False and "test-lab" not in str(out)
    assert routed.seen["health_calls"] == ["test-home"]


def test_free_home_resolves_and_reports_the_admission_state(routed):
    out = estate_router.resolve_alias("local-fast", "test-home")
    assert out["resolved"] is True and out["gpu_admission"]["state"] == "free"


def test_unknown_reading_does_not_withhold_but_is_reported_as_unknown(routed):
    routed.health["gpu_load"] = {"available": False, "error": "nvidia-smi unavailable: FileNotFoundError", "samples": []}
    out = estate_router.resolve_alias("local-fast", "test-home")
    assert out["resolved"] is True and out["gpu_admission"]["state"] == "unknown"


def test_a_worker_that_reports_no_gpu_load_field_is_unknown_not_free(routed):
    routed.health.pop("gpu_load")
    out = estate_router.resolve_alias("local-fast", "test-home")
    assert out["resolved"] is True and out["gpu_admission"]["state"] == "unknown"


def test_busy_gpu_with_estate_work_in_flight_is_admitted(routed):
    routed.health["gpu_load"] = reading([99, 99, 99])
    routed.health["in_flight"] = ["exec-1"]
    out = estate_router.resolve_alias("local-fast", "test-home")
    assert out["resolved"] is True and out["gpu_admission"]["state"] == "free"


def test_lab_without_the_block_is_completely_unchanged(routed):
    routed.health["gpu_load"] = reading([99, 99, 99])
    out = estate_router.resolve_alias("local-fast", "test-lab")
    assert out == {"alias": "local-fast", "resolved": True, "concrete_model": "test-model-fast", "evidence": "t"}
    assert routed.seen["health_calls"] == []  # no admission health round trip for an unconfigured host


def test_enabled_false_withdraws_admission_for_a_host(routed, tmp_path):
    estate = tmp_path / "config" / "estate.yaml"
    data = yaml.safe_load(estate.read_text())
    data["hosts"][1]["worker"]["gpu_admission"] = {"enabled": False, "busy_util_pct": 1}
    estate.write_text(yaml.safe_dump(data))
    routed.health["gpu_load"] = reading([99, 99, 99])
    out = estate_router.resolve_alias("local-fast", "test-home")
    assert out["resolved"] is True and "gpu_admission" not in out


def test_unreachable_worker_is_unknown_and_does_not_raise(routed, monkeypatch):
    from src.estate_worker_client import WorkerTransportError

    calls = {"n": 0}

    def boom(host_id, *, deadline_s=20.0):
        calls["n"] += 1
        raise WorkerTransportError("timeout", "no answer")

    monkeypatch.setattr(routed.client, "worker_health", boom)
    out = estate_router.gpu_admission_for_host("test-home")
    assert out["state"] == "unknown" and "worker unreachable" in out["reason"]


def test_host_config_lookup(routed):
    assert estate_router.host_gpu_admission_config("test-home") == {"busy_util_pct": 60}
    assert estate_router.host_gpu_admission_config("test-lab") is None
    assert estate_router.host_gpu_admission_config("nope") is None
    assert estate_router.host_gpu_admission_config(None) is None


def test_the_shipped_registry_opts_home_in_and_lab_out():
    # Real config/estate.yaml: home is configured, lab is not; and nothing here changes qualification.
    from pathlib import Path
    real = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "estate.yaml").read_text())
    by_id = {h["id"]: h for h in real["hosts"]}
    assert by_id["desktop-in7o23d"]["worker"]["gpu_admission"] == {"busy_util_pct": 60}
    assert "gpu_admission" not in (by_id["hz2-workstation"].get("worker") or {})
    assert by_id["desktop-in7o23d"]["worker"]["qualified_executors"] == ["deterministic"]


# ---- worker health -----------------------------------------------------------------------------

@pytest.fixture
def worker(monkeypatch):
    from src import estate_worker

    monkeypatch.setattr(estate_worker, "_ollama_inventory", lambda: (True, [], None))
    monkeypatch.setattr(estate_worker, "_write_prerequisites", lambda: {})
    monkeypatch.setattr(estate_worker, "_in_flight_execution_ids", lambda: [])
    monkeypatch.setattr(estate_router, "_codex_available", lambda: (False, "none"))
    monkeypatch.setattr(estate_router, "experiment_priority_active", lambda: (False, "idle"))
    monkeypatch.setattr(estate_router, "current_host_id", lambda: "h")
    return estate_worker


def test_health_samples_the_gpu_only_for_an_opted_in_host(worker, monkeypatch):
    sampled = []
    monkeypatch.setattr(ga, "sample_gpu", lambda **k: sampled.append(1) or {"available": True, "samples": [1]})
    monkeypatch.setattr(estate_router, "host_gpu_admission_config", lambda h: {"busy_util_pct": 60})
    assert worker._verb_health({})["gpu_load"] == {"available": True, "samples": [1]}
    assert sampled == [1]


def test_health_does_not_sample_an_unconfigured_or_disabled_host(worker, monkeypatch):
    def boom(**k):
        raise AssertionError("must not sample")

    monkeypatch.setattr(ga, "sample_gpu", boom)
    monkeypatch.setattr(estate_router, "host_gpu_admission_config", lambda h: None)
    assert worker._verb_health({})["gpu_load"] is None
    monkeypatch.setattr(estate_router, "host_gpu_admission_config", lambda h: {"enabled": False})
    assert worker._verb_health({})["gpu_load"] is None


def test_health_still_reports_the_existing_gpu_yield_signal(worker, monkeypatch):
    monkeypatch.setattr(estate_router, "host_gpu_admission_config", lambda h: None)
    out = worker._verb_health({})
    assert out["gpu_yield"] == {"active": False, "reason": "idle"} and out["in_flight"] == []


# ---- the qualification canary ------------------------------------------------------------------

@pytest.fixture
def canary():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "run_lm4_production_canary.py"
    spec = importlib.util.spec_from_file_location("lm4_canary_for_admission_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canary_gate_is_a_no_op_on_an_unconfigured_host(canary, monkeypatch):
    monkeypatch.setattr(estate_router, "host_gpu_admission_config", lambda h: None)
    assert canary._worker_gpu_gate("hz2-workstation")["state"] == "disabled"


def test_canary_gate_classifies_fresh_worker_health(canary, monkeypatch):
    import src.estate_worker_client as client

    monkeypatch.setattr(estate_router, "host_gpu_admission_config", lambda h: CFG)
    monkeypatch.setattr(client, "call_worker", lambda host, verb, payload, **k: {
        "result": {"gpu_load": reading([98, 98, 98]), "in_flight": []}})
    real = ga.classify_gpu_load
    monkeypatch.setattr(ga, "classify_gpu_load", lambda r, *, in_flight, config, now=None: real(r, in_flight=in_flight, config=config, now=NOW))
    assert canary._worker_gpu_gate("desktop-in7o23d")["state"] == "busy"


def run_canary_main(canary, monkeypatch, tmp_path, *, gates, results):
    """Drive canary.main() for one alias/one task with a scripted gate and scripted task results."""
    gate_iter, result_iter, ran = iter(gates), iter(results), []
    monkeypatch.setattr(canary, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(canary, "CANARY_PLAN", {"local-fast": ["t1"]})
    monkeypatch.setattr(canary, "load_json", lambda p: {"corpus_id": "c", "tasks": [{"task_id": "t1"}]})
    monkeypatch.setattr(canary, "_worker_gpu_gate", lambda host: next(gate_iter))

    def fake_run(host, alias, task, corpus_id, retries=0):
        ran.append(retries)
        return dict(next(result_iter))

    monkeypatch.setattr(canary, "run_text_task_on_worker", fake_run)
    return ran


def test_busy_gpu_means_not_run_not_a_failed_benchmark(canary, monkeypatch, tmp_path, capsys):
    ran = run_canary_main(canary, monkeypatch, tmp_path, gates=[{"state": "busy", "reason": "household GPU busy: 98%"}], results=[])
    with pytest.raises(SystemExit) as exc:
        canary.main(["--worker-host", "desktop-in7o23d", "--aliases", "local-fast"])
    assert exc.value.code == 3
    out = capsys.readouterr().out
    assert "NOT RUN" in out and "INCONCLUSIVE" in out and "{'pass': 0, 'fail': 0, 'error': 0, 'not_run': 1}" in out
    assert ran == []  # the model was never called
    rec = (tmp_path / "results").glob("*.jsonl").__next__().read_text()
    assert '"status": "not_run"' in rec and '"status": "fail"' not in rec


def test_a_failure_while_the_gpu_became_busy_is_inconclusive_and_not_repeated(canary, monkeypatch, tmp_path, capsys):
    ran = run_canary_main(
        canary, monkeypatch, tmp_path,
        gates=[{"state": "free"}, {"state": "busy", "reason": "household GPU busy: 97%"}],
        results=[{"status": "fail", "task_id": "t1", "reason": "timed out"}],
    )
    with pytest.raises(SystemExit) as exc:
        canary.main(["--worker-host", "desktop-in7o23d", "--aliases", "local-fast"])
    assert exc.value.code == 3
    assert ran == [0]  # one attempt, no repeat counted against the model
    assert "'inconclusive': 1" in capsys.readouterr().out


def test_a_genuine_failure_on_a_free_gpu_is_still_repeated_and_recorded_as_a_failure(canary, monkeypatch, tmp_path, capsys):
    ran = run_canary_main(
        canary, monkeypatch, tmp_path,
        gates=[{"state": "free"}, {"state": "free"}],
        results=[{"status": "fail", "task_id": "t1"}, {"status": "fail", "task_id": "t1"}],
    )
    canary.main(["--worker-host", "desktop-in7o23d", "--aliases", "local-fast"])  # no SystemExit: a real verdict
    assert ran == [0, 1]
    assert "'fail': 1" in capsys.readouterr().out


def test_a_pass_on_a_free_gpu_is_unchanged(canary, monkeypatch, tmp_path, capsys):
    ran = run_canary_main(canary, monkeypatch, tmp_path, gates=[{"state": "free"}], results=[{"status": "pass", "task_id": "t1"}])
    canary.main(["--worker-host", "desktop-in7o23d", "--aliases", "local-fast"])
    assert ran == [0] and "'pass': 1" in capsys.readouterr().out
