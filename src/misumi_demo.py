"""Evaluation-linked Misumi demonstration: a labelled VIEW over the existing execution path and trace (no second schema, router or queue).

``/misumi/demo/run`` (routes/misumi_routes.py) executes a catalogued scenario through the SAME code as ordinary use: the same
``/respond`` handler (household resolution, model, consultation) or, for music, the same ``music_reply`` parser and ``MusicController``
governance with a ``SimulatedMusicProvider`` in place of Spotify. This module only (a) holds the scenario catalogue, (b) guards guest
mode, (c) provides the simulated music runtime and (d) projects what the existing handlers already returned and logged into one
inspection record in which every section says what KIND of evidence it is. It never executes anything itself.

Evidence kinds, which are never merged:

* ``observed``            what this run actually did (route, execution, model/backend, consultations, latency, sources, tool result)
* ``simulated``           a tool operation answered by an in-memory simulation; no real account or device was touched
* ``replay``              a previously recorded run, shown as recorded and never re-labelled live
* ``offline_evaluation``  a pre-registered offline result about a class of requests; not a measurement of this run
* ``shadow_proposal``     what an experimental allocation policy WOULD propose; it did not run, holds no permission and has no live effect

Every quantity is ``measured`` or ``unavailable`` with the reason; nothing is estimated, filled or inferred. Guest mode is fail-closed:
catalogue prompts only, a household root that carries the synthetic marker, no persistence, no real tool provider.
"""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.music_capability import Device, Item, MusicController, SimulatedMusicProvider
from src.music_runtime import MusicRuntime

SCHEMA = "misumi-demo-inspection-v1"
KINDS = ("observed", "simulated", "replay", "offline_evaluation", "shadow_proposal")
MODES = ("guest", "developer")
EXECUTIONS = ("live", "replay")
SYNTHETIC_MARKER = ".synthetic-household"
GUEST_ENV = "MISUMI_DEMO_GUEST"
REPO = Path(__file__).resolve().parent.parent
SCENARIOS_FILE = REPO / "config" / "misumi_demo_scenarios.json"
RECORDINGS_DIR = REPO / "evals" / "misumi-demo" / "recordings"
MAX_TEXT = 1200


def load_scenarios(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    data = json.loads(Path(path or SCENARIOS_FILE).read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    seen = set()
    for item in scenarios:
        if item["id"] in seen or not item.get("prompt") or item.get("kind") not in {"respond", "music"}:
            raise ValueError(f"bad scenario {item.get('id')!r}")
        seen.add(item["id"])
    return scenarios


def public_scenario(item: Mapping[str, Any]) -> Dict[str, Any]:
    """What a client may see before running: the catalogue entry without internals."""
    return {key: item[key] for key in ("id", "title", "summary", "prompt", "expect_lead", "simulated_tools") if key in item}


def guest_ready(household_root: Optional[Path], environ: Optional[Mapping[str, str]] = None) -> Tuple[bool, str]:
    """Guest mode runs only on an instance explicitly started for it whose household root is visibly synthetic."""
    env = os.environ if environ is None else environ
    if str(env.get(GUEST_ENV, "")).strip() != "1":
        return False, f"guest mode is off on this instance ({GUEST_ENV}=1 is not set)"
    if household_root is None or not Path(household_root).is_dir():
        return False, "guest mode needs a configured synthetic household root"
    if not (Path(household_root) / SYNTHETIC_MARKER).is_file():
        return False, f"the household root is not marked synthetic (no {SYNTHETIC_MARKER}); refusing to serve a guest from it"
    return True, "synthetic household root"


class _DemoProvider(SimulatedMusicProvider):
    def begin_turn(self) -> None:  # the Spotify provider budgets one turn; a simulation has nothing to budget
        return None

    def search(self, query: str, kind: str):
        """Answers the same query shapes the real runtime sends: field filters (track:"x" artist:"y"), "<title> by <artist>", or plain words."""
        self._log("search", query, kind)
        self._check()
        text = query.lower()
        fields = dict(re.findall(r'(track|album|artist):"([^"]+)"', text))
        if fields:
            return [i for i in self.catalogue if all(v in (i.artist if k == "artist" else i.title).lower() for k, v in fields.items())]
        parts = re.split(r"\s+by\s+", text, maxsplit=1)
        if len(parts) == 2:
            return [i for i in self.catalogue if parts[0].strip() in i.title.lower() and parts[1].strip() in i.artist.lower()]
        words = re.findall(r"\w+", text)
        return [i for i in self.catalogue if all(w in f"{i.title} {i.artist}".lower() for w in words)]


class SimulatedMusicRuntime(MusicRuntime):
    """The real ``MusicRuntime`` parser/governance over an in-memory provider. ``simulated`` results say so; no token, account or device exists."""

    simulated = True

    def __init__(self) -> None:
        super().__init__(Path(tempfile.gettempdir()) / "misumi-demo-no-spotify")
        self.sim = _DemoProvider(
            catalogue=[Item("spotify:track:sim0001", "Kind of Blue", "Miles Davis"), Item("spotify:track:sim0002", "Pastel Blues", "Nina Simone"),
                       Item("spotify:track:sim0003", "Waltz for Debby", "Bill Evans")],
            devices=[Device("dev-kitchen", "Kitchen speaker", True, 40), Device("dev-lounge", "Lounge speaker", False, 30)])
        self._provider = self.sim
        self._controller = MusicController(self.sim, max_volume=self._max_volume)

    def configured(self) -> bool:
        return True

    def _build(self):
        return self._controller


def measured(value: Any, unit: Optional[str] = None, source: str = "") -> Dict[str, Any]:
    return {"status": "measured", "value": value, "unit": unit, "source": source}


def unavailable(reason: str) -> Dict[str, Any]:
    return {"status": "unavailable", "reason": reason}


def _clip(value: Any, limit: int = 200) -> str:
    return " ".join(str(value if value is not None else "").split())[:limit]


def execution_kind(response: Mapping[str, Any]) -> Tuple[str, str]:
    """(kind, plain reason) of how this turn was answered, from the response the handler produced."""
    source = response.get("source")
    team = response.get("team") or {}
    if source == "music":
        return "deterministic", "a music command is parsed and run by the music controller, not written by a model"
    if source == "household-read-only":
        return "deterministic", "answered from an exact synthetic household record, without a model"
    if source == "model" and team.get("decision") == "team":
        return "collaborative", "the lead was supported by a consulted specialist: " + ", ".join(team.get("reasons") or ["justified support"])
    if source == "model":
        return "solo", "one model-written reply from the lead persona; no support was justified"
    return "degraded", "no model reply was produced; this is the household fallback, not a model answer"


def _consultations(response: Mapping[str, Any]) -> List[Dict[str, Any]]:
    team = response.get("team") or {}
    out = []
    for support in team.get("supports") or []:
        if not isinstance(support, Mapping):
            continue
        out.append({
            "persona": _clip(support.get("persona"), 24), "kind": _clip(support.get("kind"), 12),
            "task_role": _clip((support.get("assignment") or {}).get("task_role"), 16),
            "status": _clip(support.get("status"), 24),
            "raised_risk": bool(support.get("raised_risk")) if "raised_risk" in support else None,
            "latency_ms": measured(support["latency_ms"], "ms", "consultation timer") if isinstance(support.get("latency_ms"), (int, float)) else unavailable("not recorded"),
            "contribution_chars": support.get("contribution_chars"),
            "improved_the_result": unavailable("not measured: needs a matched comparison (Phase B)"),
        })
    return out


def build_inspection(scenario: Mapping[str, Any], *, mode: str, execution: str, prompt: str, prompt_source: str,
                     preview: Optional[Mapping[str, Any]], response: Optional[Mapping[str, Any]], event: Optional[Mapping[str, Any]],
                     shadow: Optional[Mapping[str, Any]] = None, host: Optional[str] = None, error: Optional[str] = None,
                     recorded_at: Optional[str] = None) -> Dict[str, Any]:
    """One inspection record. ``preview`` is the route-explain result, ``response`` the /respond (or music) response, ``event`` its logged event."""
    if mode not in MODES or execution not in EXECUTIONS:
        raise ValueError("unknown mode or execution")
    live = execution == "live"
    response = response or {}
    event = event or {}
    kind, why = execution_kind(response) if response else ("none", error or "nothing ran")
    music = response.get("music") if isinstance(response.get("music"), Mapping) else None
    simulated = bool(music and music.get("simulated"))
    routing = response.get("routing") or (preview or {}).get("lead") or {}
    reasons = [_clip(r, 120) for r in (routing.get("reasons") or [])][:6]
    latency = event.get("latency_ms")
    guest = mode == "guest"
    observed = {
        "kind": "replay" if not live else ("simulated" if simulated else "observed"),
        "recorded_at": recorded_at,
        "lead": {"persona": _clip(response.get("persona") or (preview or {}).get("lead", {}).get("persona"), 24),
                 "router_choice": _clip(((preview or {}).get("lead") or {}).get("persona") or routing.get("selected"), 24) or None,
                 "source": _clip(response.get("persona_source"), 12), "method": _clip(routing.get("method"), 40), "reasons": reasons},
        "execution": {"kind": kind, "why": why, "source": _clip(response.get("source"), 24), "outcome": _clip(event.get("outcome"), 40)},
        "binding": {
            "model": _clip(event.get("model"), 80) or None, "backend": _clip(event.get("backend"), 40) or None,
            "host": None if guest else (host or socket.gethostname()),
            "tools": list(dict.fromkeys([_clip(t, 60) for t in (event.get("selected_tools") or [])] + ([f"music.*:{_clip(music.get('provider'), 20)}"] if music else []))),
            "model_note": "no model was used for this answer" if kind == "deterministic" else None,
        },
        "consultations": _consultations(response),
        "verification": (
            {"status": "performed", "what": "the music controller reads playback state back before saying it succeeded",
             "result": _clip(music.get("status"), 40)} if music else
            {"status": "grounded", "what": "answer taken from exact household records", "records": len(response.get("sources") or [])}
            if response.get("source") == "household-read-only" else
            {"status": "unavailable", "reason": "this path records no independent verification of a model-written answer"}),
        "sources": [] if guest else [_clip(s.get("path") if isinstance(s, Mapping) else s, 120) for s in (response.get("sources") or [])][:8],
        "text": _clip(response.get("text"), MAX_TEXT),
        "error": _clip(error, 200) or None,
        "measurements": {
            "latency": measured(latency, "ms", "request timer") if isinstance(latency, (int, float)) else unavailable("no event recorded"),
            "model_calls": unavailable("not instrumented on this path; consultations recorded: %d" % len(_consultations(response))),
            "tokens": unavailable("the model backend returns no token count to this path"),
            "paid_cost": unavailable("not instrumented"),
            "tool_operations": measured(1, "count", "music command executed by the controller") if music else measured(0, "count", "no tool ran"),
            "retries_rework_human_correction": unavailable("not instrumented"),
        },
    }
    record: Dict[str, Any] = {
        "schema": SCHEMA, "mode": mode, "execution": execution,
        "labels": {"live": live, "replayed": not live, "simulated_tools": simulated, "shadow_present": bool(shadow) and not guest,
                   "household_data": "synthetic" if guest else "as configured on this instance"},
        "scenario": {"id": scenario["id"], "title": scenario["title"]},
        "request": {"prompt": _clip(prompt, 400), "prompt_source": prompt_source},
        "observed": observed,
        "guest_safety": {"persisted": False, "real_tool_provider": False, "microphone": "disabled", "private_data": "none (synthetic root)"} if guest else None,
        "offline_evaluations": [] if guest else _evaluations(scenario),
        "shadow_proposal": None if (guest or not shadow) else {
            "kind": "shadow_proposal", "live_effect": "none", "status": "experimental; did NOT meet its pre-registered promotion criteria",
            "note": "this is what the candidate would propose; it did not run, was not applied and holds no permission",
            "proposal": dict(shadow),
        },
    }
    return record


def _evaluations(scenario: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [{"kind": "offline_evaluation", "title": e["title"], "path": e["path"], "headline": e["headline"],
             "is_this_run": False, "exists": (REPO / e["path"]).is_file()} for e in scenario.get("evaluations", [])]


def phase_b_row(record: Mapping[str, Any]) -> Dict[str, Any]:
    """An input row for the future Phase B evaluation: the measured facts of this run and EMPTY judgement fields. Nothing is filled in."""
    obs = record["observed"]
    return {
        "schema": "misumi-phase-b-input-v1", "scenario_id": record["scenario"]["id"], "execution": record["execution"],
        "kind": obs["kind"], "lead": obs["lead"]["persona"], "execution_kind": obs["execution"]["kind"],
        "measured": {k: v for k, v in obs["measurements"].items() if v.get("status") == "measured"},
        "unavailable": sorted(k for k, v in obs["measurements"].items() if v.get("status") == "unavailable"),
        "to_be_judged": {"answer_correctness": None, "specialist_contribution": None, "character_fidelity": None,
                         "human_correction": None, "judge": None, "judge_family": None},
    }


def load_recording(scenario_id: str) -> Optional[Dict[str, Any]]:
    """A recording is a developer-mode inspection captured from a real live run (see evals/misumi-demo/record.py), never edited or overwritten."""
    path = RECORDINGS_DIR / f"{scenario_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    ok = (isinstance(data, dict) and data.get("schema") == SCHEMA and isinstance(data.get("observed"), dict)
          and (data.get("scenario") or {}).get("id") == scenario_id and isinstance(data.get("request"), dict))
    return data if ok else None


def replay_from_recording(recording: Mapping[str, Any], *, mode: str) -> Dict[str, Any]:
    """Re-present a recording AS a replay: never live, never re-executed. Guest mode drops the developer-only parts exactly as a live guest run does."""
    out = json.loads(json.dumps(recording))
    out["execution"], out["mode"] = "replay", mode
    out.pop("phase_b_input", None)
    out["labels"].update(live=False, replayed=True, household_data="synthetic (as recorded on a synthetic instance)")
    out["observed"]["kind"] = "replay"
    out["observed"]["recorded_at"] = recording.get("recorded_at") or out["observed"].get("recorded_at")
    if mode == "guest":
        out["observed"]["binding"]["host"] = None
        out["observed"]["sources"] = []
        out["shadow_proposal"], out["offline_evaluations"] = None, []
        out["labels"].update(shadow_present=False, household_data="synthetic")
        out["guest_safety"] = {"persisted": False, "real_tool_provider": False, "microphone": "disabled", "private_data": "none (synthetic root)"}
    return out
