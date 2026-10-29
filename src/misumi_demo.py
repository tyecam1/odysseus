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
import collections
import hashlib
import itertools
import html
import os
import unicodedata
import threading
import urllib.parse
import re
import socket
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.music_capability import Device, Item, MusicController, SimulatedMusicProvider
from src.music_runtime import MusicRuntime

from src.deployment_isolation import DOMAIN_ROOT_VARS, WRITABLE_VARS

SCHEMA = "misumi-demo-inspection-v1"
KINDS = ("observed", "simulated", "replay", "offline_evaluation", "shadow_proposal")
MODES = ("guest", "developer")
EXECUTIONS = ("live", "replay")
SYNTHETIC_MARKER = ".synthetic-household"
GUEST_ENV = "MISUMI_DEMO_GUEST"
REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "evals" / "misumi-demo" / "synthetic-household"
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


GUEST_SAFETY = {
    "conversation_history": "not stored", "learning_and_memory": "not written", "real_tool_provider": False, "microphone": "disabled",
    "private_data": "none (every reachable root verified synthetic)",
    "telemetry": "one operational event record per run is written to this session's own demonstration log until reset, eviction or restart; "
                 "the shared operational event log is not touched",
}
STATE_VARS = ("MISUMI_ROUTING_STATE_ROOT", "MISUMI_PERSONA_STATE_ROOT", "MISUMI_DIALOGUE_STATE_ROOT")
DATA_VAR = "ODYSSEUS_DATA_DIR"
_SCAN_LIMIT = 5000
MAX_SESSION_LOG_BYTES = 32768
MAX_SESSION_LOG_LINES = 50


def _real(path: Any) -> str:
    return os.path.normcase(os.path.realpath(os.path.expanduser(str(path))))


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives
        return False


def _marked(real_dir: str) -> bool:
    marker = Path(real_dir) / SYNTHETIC_MARKER
    return marker.is_file() and not marker.is_symlink() and marker.stat().st_size <= 1024


def marker_fingerprint() -> str:
    """Short hash of the shipped synthetic-household marker; a recording must carry it to be replayable."""
    try:
        return hashlib.sha256((FIXTURE / SYNTHETIC_MARKER).read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def verify_synthetic(household_root: Optional[Path], environ: Optional[Mapping[str, str]] = None) -> Tuple[bool, str]:
    """Every root this instance can read or write must be synthetic: the household and any other configured source root, the data
    directory and the state stores. Diagnostics name variables, never paths."""
    env = os.environ if environ is None else environ
    if household_root is None or not Path(household_root).is_dir():
        return False, "guest mode needs a configured synthetic household root"
    root = _real(household_root)
    if not _marked(root):
        return False, f"the household root is not marked synthetic (no {SYNTHETIC_MARKER}); refusing to serve a guest from it"
    approved = fixture_digest()
    if not approved or tree_digest(Path(root)) != approved:
        return False, "the household root's content is not the approved synthetic fixture (a marker alone is not enough)"
    for var in DOMAIN_ROOT_VARS["misumi"]:
        value = str(env.get(var, "")).strip()
        if value and not (_inside(_real(value), root) or _marked(_real(value))):
            return False, f"{var} reaches content that is not marked synthetic"
    for var in DOMAIN_ROOT_VARS["phd"]:
        if str(env.get(var, "")).strip():
            return False, f"{var} is set; a guest instance must not be able to reach research content"
    data = str(env.get(DATA_VAR, "")).strip()
    if not data or not Path(data).is_dir() or not _marked(_real(data)):
        return False, f"{DATA_VAR} must name an explicit data directory marked synthetic"
    data_real = _real(data)
    for var in STATE_VARS:
        if not str(env.get(var, "")).strip():
            return False, f"{var} must be set so no operational state store is shared"
    for var in WRITABLE_VARS:
        value = str(env.get(var, "")).strip()
        if value and not _inside(_real(value), data_real):
            return False, f"{var} is outside the synthetic data directory"
    if str(env.get("MISUMI_MUSIC", "1")).strip() != "0":
        return False, "MISUMI_MUSIC=0 is required: the real music runtime must be off on a guest instance"
    seen = 0
    for folder, names, files in os.walk(root, followlinks=False):
        for name in names + files:
            seen += 1
            full = os.path.join(folder, name)
            if seen > _SCAN_LIMIT:
                return False, "the synthetic household is larger than a demonstration fixture"
            if os.path.islink(full) and not _inside(_real(full), root):
                return False, "a link inside the household root leaves it"
    return True, "synthetic household, data directory and state stores verified"


def guest_ready(household_root: Optional[Path], environ: Optional[Mapping[str, str]] = None) -> Tuple[bool, str]:
    """Guest mode runs only on an instance explicitly started for it, and only after verify_synthetic passes on the effective roots."""
    env = os.environ if environ is None else environ
    if str(env.get(GUEST_ENV, "")).strip() != "1":
        return False, f"guest mode is off on this instance ({GUEST_ENV}=1 is not set)"
    return verify_synthetic(household_root, env)


def tree_digest(root: Path) -> str:
    """Content digest of a directory tree: every regular file's relative path, size and sha256, in sorted order. Links are not followed."""
    outer = hashlib.sha256()
    entries = []
    for folder, names, files in os.walk(str(root), followlinks=False):
        names.sort()
        for name in files:
            full = Path(folder) / name
            if full.is_symlink() or not full.is_file():
                continue
            entries.append((full.relative_to(root).as_posix(), full))
            if len(entries) > _SCAN_LIMIT:
                return ""
    for rel, full in sorted(entries):
        outer.update(f"{rel}\0{full.stat().st_size}\0{hashlib.sha256(full.read_bytes()).hexdigest()}\n".encode("utf-8"))
    return outer.hexdigest()


def fixture_digest() -> str:
    """The digest of the approved synthetic fixture shipped in this repository."""
    return tree_digest(FIXTURE) if FIXTURE.is_dir() else ""


def provenance_stamp(verified: bool, household_root: Optional[Path] = None) -> Dict[str, Any]:
    """What this instance can attest about itself: the root checks passed, the marker, and the content digest of the household root it is
    serving. This is evidence from a trusted capture workflow, not proof against deliberately constructed data and not an OS sandbox."""
    digest = tree_digest(Path(household_root)) if verified and household_root is not None else None
    return {"synthetic_verified": bool(verified), "marker": marker_fingerprint(), "fixture_sha256": digest or None,
            "checked": "household and source roots, data directory, state stores, links, music runtime, research roots"}


class _Entry:
    __slots__ = ("generation", "music", "active", "gone", "music_lock")

    def __init__(self, generation: int) -> None:
        self.generation, self.music, self.active, self.gone = generation, None, 0, False
        self.music_lock = threading.Lock()   # one music command at a time within a session


class DemoLease:
    """One run's hold on a session: the event file it writes (named for the session generation it began in) and, for music, the session's runtime.
    After the run, ``DemoSessions.finish`` removes the file if a reset or eviction happened meanwhile, so neither can leave residue behind."""

    def __init__(self, sessions: "DemoSessions", key: str, entry: _Entry, generation: int, path: Path) -> None:
        self.sessions, self.key, self.entry, self.generation, self.path = sessions, key, entry, generation, path

    @property
    def music_lock(self) -> threading.Lock:
        return self.entry.music_lock

    def runtime(self) -> "SimulatedMusicRuntime":
        with self.sessions._lock:
            if self.entry.generation == self.generation and not self.entry.gone:
                if self.entry.music is None:
                    self.entry.music = SimulatedMusicRuntime()
                return self.entry.music
        return SimulatedMusicRuntime()   # the session was reset or evicted mid-run: this run gets a private throwaway, never shared state


class DemoSessions:
    """Per-session demonstration state keyed by (caller, session id): an event log file and a simulated music runtime.

    Every run takes a lease (``begin``) and returns it (``finish``). Nothing here is shared with the operational event log or any household or
    session store. Reset gives the session a new generation, so only its own files go and an in-flight run's later writes are removed when it
    ends. At most ``limit`` sessions exist; the least recently used idle one is evicted with its files. Files left by an earlier process are
    removed at start-up (this directory only).
    """

    def __init__(self, directory: Path, limit: int = 32) -> None:
        self.directory, self.limit = Path(directory), limit
        self._entries: "collections.OrderedDict[str, _Entry]" = collections.OrderedDict()
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._writers: Dict[Path, int] = {}     # live leases per log file
        if self.directory.is_dir():
            for stale in self.directory.glob("*.jsonl"):
                stale.unlink()

    @staticmethod
    def key(owner: Optional[str], session_id: Optional[str]) -> str:
        return hashlib.sha256(f"{owner or ''}\0{session_id or ''}".encode("utf-8")).hexdigest()[:24]

    def _path(self, key: str, generation: int) -> Path:
        return self.directory / f"{key}-{generation}.jsonl"

    def _evict(self) -> None:
        for key in list(self._entries):
            if len(self._entries) <= self.limit:
                return
            entry = self._entries[key]
            if entry.active == 0:
                del self._entries[key]
                entry.gone = True
                self._path(key, entry.generation).unlink(missing_ok=True)

    def begin(self, key: str) -> DemoLease:
        with self._lock:
            entry = self._entries.pop(key, None) or _Entry(next(self._counter))
            self._entries[key] = entry
            entry.active += 1
            path = self._path(key, entry.generation)
            self._writers[path] = self._writers.get(path, 0) + 1
            self._evict()
            return DemoLease(self, key, entry, entry.generation, path)

    def _trim(self, path: Path) -> None:
        """A session's log keeps only its most recent records (bounded storage); the shared operational log is never trimmed."""
        try:
            if path.is_file() and path.stat().st_size > 0:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                if len(lines) > MAX_SESSION_LOG_LINES or path.stat().st_size > MAX_SESSION_LOG_BYTES:
                    kept = lines[-MAX_SESSION_LOG_LINES:]
                    while kept and sum(len(line.encode("utf-8")) + 1 for line in kept) > MAX_SESSION_LOG_BYTES:
                        kept.pop(0)
                    tmp = path.with_name(path.name + ".tmp")
                    tmp.write_text("".join(line + "\n" for line in kept), encoding="utf-8", newline="\n")
                    os.replace(tmp, path)
        except OSError:
            pass

    def finish(self, lease: DemoLease) -> None:
        with self._lock:
            left = self._writers.get(lease.path, 1) - 1      # another live lease may still be appending to this file: a read-modify-write now could drop its records
            if left > 0:
                self._writers[lease.path] = left
            else:
                self._writers.pop(lease.path, None)
                self._trim(lease.path)
            lease.entry.active = max(0, lease.entry.active - 1)
            if lease.entry.gone or lease.entry.generation != lease.generation:
                lease.path.unlink(missing_ok=True)
            self._evict()

    def reset(self, key: str) -> int:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return 0
            old = self._path(key, entry.generation)
            cleared = len(old.read_text(encoding="utf-8", errors="replace").splitlines()) if old.is_file() else 0
            old.unlink(missing_ok=True)
            entry.generation, entry.music = next(self._counter), None
            return cleared

    def session_files(self) -> List[Path]:
        return sorted(self.directory.glob("*.jsonl")) if self.directory.is_dir() else []


_PRIVATE_LOOKING = re.compile(
    r"(?:[A-Za-z]:\\|/home/|/Users/|/etc/|/var/|/tmp/|~/|\.ts\.net|\bBearer\s|\body_[A-Za-z0-9]{6,}|BEGIN [A-Z ]*KEY|"
    r"(?<![\w.+-])[\w.+-]+@[\w-]+\.[\w.]+|\b\d{1,3}(?:\.\d{1,3}){3}\b|(?i:(?:password|passwd|secret|api[_-]?key|token)\s*[:=])|"
    r"\bsk-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[0-9A-Z]{16}\b|\bxox[baprs]-[A-Za-z0-9-]{10,}|\beyJ[A-Za-z0-9_-]{10,}\.|"
    r"\b[A-Za-z0-9]{40,}\b|"
    # an endpoint in any guest-visible text: URL, localhost, name:port, bracketed IPv6, or a host-like domain
    # (anchored at token starts so scanning stays linear on a 60 KB string)
    r"(?i:://|\blocalhost\b|\[[0-9a-f:.]{2,}\]|(?<![a-z0-9_])(?:[0-9a-f]{0,4}:){1,7}:[0-9a-f]{0,4}(?![a-z0-9_])))")


_COLON_LIKE = str.maketrans({"\u2236": ":", "\ua789": ":", "\u0589": ":"})


# Host:port and host-like names, in any script. A label is any run of characters that is not whitespace or a prose/URL delimiter (so combining marks,
# CJK, Devanagari etc. count); anchored at token starts so scanning stays linear on a 60 KB string.
_LBL = r"[^\s:;,!?()<>\[\]{}\x22\x27/\\|@#$%^&*+=~`]"
_LBL_NOT_NUM = r"[^\d.\s:;,!?()<>\[\]{}\x22\x27/\\|@#$%^&*+=~`]"
_LBL_NO_DOT = r"[^.\s:;,!?()<>\[\]{}\x22\x27/\\|@#$%^&*+=~`]"
_ENDPOINT = re.compile(
    r"(?i:(?<!" + _LBL + r")(?!\d{4}-\d{2}-\d{2}t\d{2}:)(?=[\d.]*" + _LBL_NOT_NUM + r")" + _LBL + r"+:\d+(?!\w)"      # host:port (not 10:30, not an ISO time)
    r"|(?<!" + _LBL + r")" + _LBL_NO_DOT + r"+(?:\." + _LBL_NO_DOT + r"+)*\.(?:com|org|net|io|ai|dev|local|lan|internal|home|test|example|arpa)(?!" + _LBL_NO_DOT + r"))")


def _decoded(text: str) -> str:
    """The text as a reader would decode it. Every transform (NFKC for full-width forms, removal of invisible format characters, colon look-alikes,
    HTML entities, percent-decoding) is applied in one loop to a fixed point, because each can expose input for another."""
    for _ in range(32):
        step = "".join(ch for ch in unicodedata.normalize("NFKC", text) if unicodedata.category(ch) != "Cf").translate(_COLON_LIKE)
        step = urllib.parse.unquote(html.unescape(step))
        if step == text:
            return text
        text = step
    return None                      # still changing after 32 rounds: nobody writes ordinary text this way


def _looks_private(text: str) -> bool:
    if _PRIVATE_LOOKING.search(text) or _ENDPOINT.search(text):
        return True
    decoded = _decoded(text)
    return decoded is None or _PRIVATE_LOOKING.search(decoded) is not None or _ENDPOINT.search(decoded) is not None


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def fixture_files() -> frozenset:
    return frozenset(p.relative_to(FIXTURE).as_posix() for p in FIXTURE.rglob("*") if p.is_file() and p.name != SYNTHETIC_MARKER)


_STAMP_KEYS = frozenset({"synthetic_verified", "marker", "fixture_sha256", "checked"})
_CAPTURE_KEYS = frozenset({"recorder", "source_revision", "fixture_sha256", "attempts"})
_RECORDING_KEYS = frozenset({"schema", "mode", "execution", "labels", "scenario", "request", "observed", "guest_safety", "offline_evaluations",
                             "shadow_proposal", "provenance", "evidence_review", "capture", "recorded_at"})


# Allowlists, not blacklists: a guest only ever sees a binding label the runtime itself emits. A lexical check cannot tell a host from a name,
# so the shapes below are the ones the recorder produces; anything else makes the recording unreplayable (fail closed) until it is reviewed.
_BACKEND = re.compile(r"household-read-only|model endpoint /(?:[A-Za-z0-9_.-]{1,40}(?:/[A-Za-z0-9_.-]{1,40}){0,3})?")
_MODEL = re.compile(r"(?:gemma|llama|qwen|mistral|phi|gpt|deepseek|granite)[A-Za-z0-9_-]{0,30}(?:\.\d{1,3}){0,3}(?::(?!\d+$)[A-Za-z0-9_-]{1,24})?")
_TOOL = re.compile(r"(?:music|household|records|food|research|evidence|finance|plants|cleaning)\.[a-z_*]{1,30}(?::[a-z_]{1,20})?")
_MODEL_NOTES = frozenset({"no model was used for this answer"})


def safe_label(value: Any, pattern: "re.Pattern[str]") -> Optional[str]:
    """A binding label shown to a guest: a short plain name, never a URL, host or port."""
    return value if isinstance(value, str) and pattern.fullmatch(value) and "//" not in value else None


def _binding_labels_ok(binding: Mapping[str, Any]) -> bool:
    tools = binding.get("tools", [])
    return ((binding.get("backend") is None or safe_label(binding["backend"], _BACKEND) is not None)
            and (binding.get("model") is None or safe_label(binding["model"], _MODEL) is not None)
            and (binding.get("model_note") is None or binding["model_note"] in _MODEL_NOTES)
            and isinstance(tools, list) and all(safe_label(tool, _TOOL) is not None for tool in tools))


def guest_binding(binding: Mapping[str, Any]) -> Dict[str, Any]:
    """The only binding fields a guest can be shown, each rebuilt from an allowlisted shape."""
    return {"backend": safe_label(binding.get("backend"), _BACKEND), "model": safe_label(binding.get("model"), _MODEL), "host": None,
            "model_note": binding.get("model_note") if binding.get("model_note") in _MODEL_NOTES else None,
            "tools": [tool for tool in binding.get("tools", []) if safe_label(tool, _TOOL)] if isinstance(binding.get("tools"), list) else []}


def validate_recording(data: Any, scenario_id: str) -> Tuple[bool, str]:
    """Fail closed: any shape the checks below did not anticipate is a rejection, never an exception."""
    try:
        return _validate_recording(data, scenario_id)
    except (TypeError, AttributeError, KeyError, ValueError, RecursionError):
        return False, "malformed recording"


def _validate_recording(data: Any, scenario_id: str) -> Tuple[bool, str]:
    """A recording is replayable only if it is a developer live inspection of this scenario, carries the synthetic provenance stamp for the
    shipped fixture, names only sources that exist in that fixture, and contains nothing that looks like a host, path, address or credential."""
    if not (isinstance(data, dict) and data.get("schema") == SCHEMA and isinstance(data.get("observed"), dict)
            and isinstance(data.get("scenario"), dict) and data["scenario"].get("id") == scenario_id and isinstance(data.get("request"), dict)
            and isinstance((data["observed"].get("binding")), dict) and isinstance(data.get("labels"), dict)):
        return False, "malformed recording"
    if data.get("mode") != "developer" or data.get("execution") != "live" or data["labels"].get("live") is not True:
        return False, "not a live developer inspection"
    stamp = data.get("provenance")
    if not (isinstance(stamp, dict) and stamp.get("synthetic_verified") is True and stamp.get("marker") and stamp.get("marker") == marker_fingerprint()):
        return False, "no verified synthetic provenance for the shipped fixture"
    approved = fixture_digest()
    if not approved or stamp.get("fixture_sha256") != approved:
        return False, "the household the recording was captured from is not the approved synthetic fixture (content digest differs)"
    if not (isinstance(stamp.get("checked"), str) and stamp["checked"].strip()):
        return False, "provenance lacks its check record"
    capture = data.get("capture")
    attempts = capture.get("attempts") if isinstance(capture, dict) else None
    if not (isinstance(attempts, int) and not isinstance(attempts, bool) and 1 <= attempts <= 3):
        return False, "no capture record from the recording workflow (fixture digest, recorder, source revision)"
    if not (isinstance(capture, dict) and capture.get("fixture_sha256") == approved and capture.get("recorder") == "evals/misumi-demo/record.py"
            and re.fullmatch(r"[0-9a-f]{40}", str(capture.get("source_revision", "")))):
        return False, "no capture record from the recording workflow (fixture digest, recorder, source revision)"
    binding = data["observed"]["binding"]
    if binding.get("host") is not None:
        return False, "recording names a host"
    if set(data["observed"]) - set(_GUEST_OBSERVED) or set(binding) - set(_GUEST_BINDING):
        return False, "recording has fields outside the recording contract"
    if not _binding_labels_ok(binding):
        return False, "recording names an endpoint"
    allowed = fixture_files()
    sources = data["observed"].get("sources")
    if not isinstance(sources, list) or any(not isinstance(s, str) or s not in allowed for s in sources):
        return False, "recording names a source outside the synthetic fixture"
    review = data.get("evidence_review")
    if review is not None and (not isinstance(review, dict) or not isinstance(review.get("records", []), list) or any(not isinstance(r, dict) or r.get("source") not in allowed for r in review.get("records", []))):
        return False, "evidence review names a source outside the synthetic fixture"
    encoded = json.dumps(data, ensure_ascii=False)
    if len(encoded) > 65536:
        return False, "recording is larger than a demonstration record"
    if set(data) - _RECORDING_KEYS or set(stamp) - _STAMP_KEYS or set(capture) - _CAPTURE_KEYS:
        return False, "recording has fields outside the recording contract"
    scanned = {key: value for key, value in data.items() if key not in ("provenance", "capture")}
    scanned["provenance"] = {k: v for k, v in stamp.items() if k not in ("marker", "fixture_sha256")}   # the digests are hex by design; every other field is scanned
    scanned["capture"] = {k: v for k, v in capture.items() if k not in ("fixture_sha256", "source_revision")}
    for text in _strings(scanned):
        # scan the text as written and as a reader would decode it (full-width forms, percent-encoding)
        if _looks_private(text):
            return False, "recording contains private-looking content"
    return True, "ok"


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


def _backend_label(value: Any, guest: bool) -> Optional[str]:
    """The backend as logged, except that a guest is never shown a model endpoint's host or port (the path alone says which API ran)."""
    text = _clip(value, 80)
    if guest and "://" in text:
        return "model endpoint " + (urllib.parse.urlparse(text).path or "/")
    return text or None


def build_inspection(scenario: Mapping[str, Any], *, mode: str, execution: str, prompt: str, prompt_source: str,
                     preview: Optional[Mapping[str, Any]], response: Optional[Mapping[str, Any]], event: Optional[Mapping[str, Any]],
                     shadow: Optional[Mapping[str, Any]] = None, host: Optional[str] = None, error: Optional[str] = None,
                     recorded_at: Optional[str] = None, provenance: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
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
            "model": _clip(event.get("model"), 80) or None, "backend": _backend_label(event.get("backend"), guest),
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
        "provenance": dict(provenance) if provenance else provenance_stamp(False),
        "observed": observed,
        "guest_safety": dict(GUEST_SAFETY) if guest else None,
        "offline_evaluations": [] if guest else _evaluations(scenario),
        "shadow_proposal": None if (guest or not shadow) else {
            "kind": "shadow_proposal", "live_effect": "none", "status": "experimental; did NOT meet its pre-registered promotion criteria",
            "note": "this is what the candidate would propose; it did not run, was not applied and holds no permission",
            "proposal": dict(shadow),
        },
    }
    return record


def evidence_review(scenario: Mapping[str, Any], household_root: Optional[Path]) -> Optional[Dict[str, Any]]:
    """A deterministic review of the exact records a scenario is about: the lines are read straight from the synthetic fixture files (no model),
    quoted with file and line, followed by the catalogue's assessment of what they do and do not establish and what evidence is missing.
    Only files that exist in the approved fixture are read, and only ever from a root that already passed verify_synthetic."""
    spec = scenario.get("evidence_review")
    if not isinstance(spec, Mapping) or household_root is None:
        return None
    root, allowed, found = _real(household_root), fixture_files(), []
    for item in spec.get("records", []):
        rel = str(item.get("path", ""))
        full = Path(root) / rel
        if rel not in allowed or not full.is_file() or not _inside(_real(full), root):
            continue
        lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, text in enumerate(lines, 1):
            if not re.search(item["match"], text, re.IGNORECASE):
                continue
            if item.get("after") and not any(re.search(item["after"], previous, re.IGNORECASE) for previous in lines[max(0, number - 4):number - 1]):
                continue   # the line only counts under its item
            found.append({"role": _clip(item.get("role"), 80), "source": rel, "line": number, "text": _clip(text.strip(), 160)})
            break
    complete = len(found) == len(spec.get("records", []))
    return {"kind": "observed", "what": "the records were read directly from the household files; no model was used",
            "records": found, "complete": complete,
            "assessment": spec.get("assessment") if complete else "unavailable",
            "why": spec.get("why") if complete else "an expected record was not found in the household files",
            "needed": [str(n)[:200] for n in spec.get("needed", [])][:4] if complete else []}


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


def _no_duplicate_keys(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key in recording")
    return dict(pairs)


def load_recording(scenario_id: str) -> Optional[Dict[str, Any]]:
    """A recording is a developer-mode inspection captured from a real live run (see evals/misumi-demo/record.py), never edited or overwritten.
    Only a recording that passes validate_recording is ever replayed."""
    path = RECORDINGS_DIR / f"{scenario_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (OSError, ValueError):
        return None
    return data if validate_recording(data, scenario_id)[0] else None


_GUEST_TOP = ("schema", "mode", "execution", "labels", "scenario", "request", "observed", "guest_safety", "offline_evaluations", "shadow_proposal", "provenance", "evidence_review")
_GUEST_OBSERVED = ("kind", "recorded_at", "lead", "execution", "binding", "consultations", "verification", "sources", "text", "error", "measurements")
_GUEST_BINDING = ("model", "backend", "host", "tools", "model_note")


def replay_from_recording(recording: Mapping[str, Any], *, mode: str) -> Dict[str, Any]:
    """Re-present a recording AS a replay: never live, never re-executed, no provider or model called. A guest replay is rebuilt from an allowlist
    of fields, so a developer-only or unexpected field in a recording cannot reach a guest."""
    full = json.loads(json.dumps(recording))
    out = {key: full[key] for key in _GUEST_TOP if key in full}
    out["execution"], out["mode"] = "replay", mode
    out["labels"].update(live=False, replayed=True, household_data="synthetic (as recorded on a synthetic instance)")
    out["observed"]["kind"] = "replay"
    out["observed"]["recorded_at"] = recording.get("recorded_at") or out["observed"].get("recorded_at")
    if mode == "guest":
        out["observed"] = {key: out["observed"][key] for key in _GUEST_OBSERVED if key in out["observed"]}
        out["observed"]["binding"] = guest_binding(out["observed"]["binding"])
        out["observed"]["sources"] = []
        out["shadow_proposal"], out["offline_evaluations"] = None, []
        out["provenance"] = {key: out["provenance"].get(key) for key in ("synthetic_verified", "marker", "fixture_sha256")}
        out["labels"].update(shadow_present=False, household_data="synthetic")
        out["guest_safety"] = dict(GUEST_SAFETY)
    return out
