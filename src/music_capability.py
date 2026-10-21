"""Provider-agnostic ``music.*`` capability contract and its governance (Jin music, design 2026-10-16).

Jin is the music-oriented *voice*; the playback command is a governed capability that any authorised worker may fulfil. This
module is the contract and the rules, with no network and no credentials:

* ``MusicProvider`` - what a provider binding (Spotify later, a simulation now) must offer.
* ``MusicController`` - the governance in front of any provider: read actions can never reach a write method; every write needs an
  explicit user command from a non-guest caller; devices and ambiguous requests are resolved or clarified, never guessed; one
  request id causes at most one provider write; volume is bounded; provider failures become truthful results with an honest
  suggestion; traces carry no tokens and no listening history.
* ``SimulatedMusicProvider`` - an in-memory provider for tests, guest-safe demos and drills; every result it produces says it is a
  simulation.

Nothing here is a scheduler, a second tool router or a credential store. A real Spotify binding (OAuth PKCE, token vault, scopes
``user-read-playback-state`` / ``user-read-currently-playing`` / ``user-modify-playback-state``) is a separate, gated increment.
"""

from __future__ import annotations

import re
import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple

READ_ACTIONS = frozenset({"search", "devices", "now_playing"})
WRITE_ACTIONS = frozenset({"play", "pause", "resume", "next", "queue", "volume"})
ALL_ACTIONS = READ_ACTIONS | WRITE_ACTIONS
DEFAULT_MAX_VOLUME = 80  # percent; a higher request is refused, never clamped silently
MAX_OPTIONS = 3  # choices offered when asking the user to disambiguate
MAX_DEVICES_LISTED = 5
_REMEMBERED_REQUESTS = 4096  # write request ids remembered per controller; when full, new writes are refused, never evicted
_URI = re.compile(r"spotify:(?:track|album|playlist|artist|episode|show):[A-Za-z0-9]{1,64}")
_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,64}")  # ids are opaque and short; anything else is refused, so traces can never carry free text


class ProviderError(Exception):
    """A provider failure with a typed code: auth, forbidden, rate_limited, offline, no_device, not_found."""

    def __init__(self, code: str, message: str = "", retry_after: Optional[int] = None):
        super().__init__(message or code)
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class Item:
    uri: str
    title: str
    artist: str = ""
    kind: str = "track"


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    active: bool = False
    volume: Optional[int] = None


@dataclass(frozen=True)
class NowPlaying:
    item: Optional[Item]
    playing: bool
    device_id: Optional[str] = None


class MusicProvider(Protocol):
    name: str
    simulated: bool

    def search(self, query: str, kind: str) -> List[Item]: ...
    def devices(self) -> List[Device]: ...
    def now_playing(self) -> Optional[NowPlaying]: ...
    def play(self, uri: str, device_id: str) -> None: ...
    def pause(self, device_id: str) -> None: ...
    def resume(self, device_id: str) -> None: ...
    def next(self, device_id: str) -> None: ...
    def queue(self, uri: str, device_id: str) -> None: ...
    def set_volume(self, percent: int, device_id: str) -> None: ...


@dataclass(frozen=True)
class MusicResult:
    """The outcome of one request. ``status``: done / done_unconfirmed / clarify / refused / not_found / error."""

    action: str
    status: str
    message: str
    simulated: bool = False
    data: Dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""
    trace: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in ("done", "done_unconfirmed")


def _say(provider: MusicProvider, text: str) -> str:
    return f"[simulation] {text}" if getattr(provider, "simulated", False) else text


def _text(value: Any) -> str:
    """A caller-supplied value as text; an object whose __str__ raises is empty text, never an exception."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:  # noqa: BLE001
        return ""


def _volume_key(value: Any) -> str:
    try:
        return f"{type(value).__name__}:{value!r}"[:80]
    except Exception:  # noqa: BLE001
        return type(value).__name__


class MusicController:
    def __init__(self, provider: MusicProvider, *, max_volume: int = DEFAULT_MAX_VOLUME):
        self.provider = provider
        self.max_volume = max(0, min(100, int(max_volume)))
        self._seen: Dict[str, Tuple[tuple, MusicResult]] = {}
        # at-most-once per request id: a short lock guards only the bookkeeping; the provider call itself runs with NO lock held,
        # so a slow provider cannot block unrelated requests and a provider calling back into the controller cannot deadlock
        self._lock = threading.Lock()
        self._inflight: Dict[str, Tuple[tuple, threading.Event, int]] = {}
        self._wait_seconds = 15.0

    # ------------------------------------------------------------------ entry point
    def handle(self, action: str, *, request_id: str, explicit_command: bool = False, guest: bool = False,
               query: str = "", kind: str = "track", device: str = "", uri: str = "", volume: Any = None) -> MusicResult:
        """Run one ``music.<action>`` request. Never raises: every failure, including unprintable inputs, is a typed result."""
        try:
            action = action.strip().lower() if isinstance(action, str) else ""
            rid = request_id.strip() if isinstance(request_id, str) else ""
            rid = rid if _REQUEST_ID.fullmatch(rid) else ""
            if action not in ALL_ACTIONS:
                return self._result(action, "refused", "That is not a music action I support.", rid)
            if action in READ_ACTIONS:
                return self._read(action, rid, _text(query), _text(kind) or "track")
            # permission is decided BEFORE any remembered answer is returned: a guest replaying the owner's id learns nothing.
            # Exact booleans only: a truthy "yes" or a missing guest flag (None) is not authority.
            if guest is not False:
                return self._result(action, "refused", "Guests cannot control the owner's music account.", rid)
            if explicit_command is not True:
                return self._result(action, "refused", "Playback changes need an explicit command from the owner.", rid)
            if not rid:
                return self._result(action, "refused", "A write needs a request id of 1-64 letters, digits or . _ : - so it can never run twice.", "")
            fingerprint = (action, _text(query), _text(kind), _text(device), _text(uri), _volume_key(volume))
            event = None
            with self._lock:
                if rid in self._seen:
                    stored_fingerprint, stored = self._seen[rid]
                    if stored_fingerprint != fingerprint:
                        return self._result(action, "refused", "That request id was already used for a different command.", rid)
                    return stored  # a duplicate command: the same answer, no second provider call
                if rid in self._inflight:
                    running_fingerprint, running_event, owner = self._inflight[rid]
                    if running_fingerprint != fingerprint:
                        return self._result(action, "refused", "That request id was already used for a different command.", rid)
                    if owner == threading.get_ident():  # a provider calling back into the controller with the SAME id
                        return self._result(action, "refused", "That command is already running.", rid)
                    event = running_event
                elif len(self._seen) + len(self._inflight) >= _REMEMBERED_REQUESTS:
                    return self._result(action, "refused", "Too many playback changes this session; start a new session to continue.", rid)
                else:
                    self._inflight[rid] = (fingerprint, threading.Event(), threading.get_ident())
            if event is not None:  # the same command is running on another thread: wait for ITS answer, never run it twice
                event.wait(self._wait_seconds)
                with self._lock:
                    if rid in self._seen and self._seen[rid][0] == fingerprint:
                        return self._seen[rid][1]
                return self._result(action, "refused", "That command is still running; try again shortly.", rid)
            result = None
            try:
                result = self._write(action, rid, _text(query), _text(kind) or "track", _text(device), _text(uri), volume)
            except ProviderError as exc:
                result = self._failure(action, exc, rid)
            except Exception:  # noqa: BLE001 - a provider binding bug is a typed result; the id stays burnt (it may have reached the provider)
                result = self._failure(action, ProviderError("unexpected"), rid)
            finally:  # the reservation is ALWAYS released and waiters are woken, even if something worse than an Exception escapes
                with self._lock:
                    running = self._inflight.pop(rid, None)
                    if result is not None and result.status in ("done", "done_unconfirmed", "error"):
                        self._seen[rid] = (fingerprint, result)
                if running is not None:
                    running[1].set()
            return result
        except ProviderError as exc:
            return self._failure(str(action) if isinstance(action, str) else "", exc, "")
        except Exception:  # noqa: BLE001 - last resort: still a typed result, never an exception
            return self._failure(action if isinstance(action, str) else "", ProviderError("unexpected"), "")

    # ------------------------------------------------------------------ reads (never touch a write method)
    def _read(self, action: str, request_id: str, query: str, kind: str) -> MusicResult:
        try:
            if action == "devices":
                devices = self.provider.devices()
                data = {"devices": [{"id": d.id, "name": d.name, "active": d.active} for d in devices[:MAX_DEVICES_LISTED]],
                        "omitted": max(0, len(devices) - MAX_DEVICES_LISTED)}
                return self._result(action, "done", _say(self.provider, f"{len(devices)} device(s) available."), request_id, data)
            if action == "search":
                if not str(query or "").strip():
                    return self._result(action, "refused", "Search needs something to look for.", request_id)
                found = self.provider.search(str(query).strip(), kind)
                data = {"results": [self._item(i) for i in found[:MAX_OPTIONS]], "omitted": max(0, len(found) - MAX_OPTIONS)}
                return self._result(action, "done" if found else "not_found",
                                    _say(self.provider, f"{len(found)} match(es)." if found else "Nothing matched."), request_id, data)
            now = self.provider.now_playing()
            if now is None or now.item is None:
                return self._result(action, "done", _say(self.provider, "Nothing is playing."), request_id,
                                    {"playing": False})
            state = "Playing" if now.playing else "Paused"
            return self._result(action, "done", _say(self.provider, f"{state}: {now.item.title}" + (
                f" by {now.item.artist}" if now.item.artist else "") + "."), request_id,
                {"playing": now.playing, "item": self._item(now.item), "device_id": now.device_id})
        except ProviderError as exc:
            return self._failure(action, exc, request_id)

    # ------------------------------------------------------------------ writes
    def _write(self, action: str, request_id: str, query: str, kind: str, device: str, uri: str, volume: Any) -> MusicResult:
        volume_value: Optional[int] = None
        if action == "volume":
            if isinstance(volume, bool) or not isinstance(volume, int) or not 0 <= volume <= 100:
                return self._result(action, "refused", "Volume must be a whole number from 0 to 100.", request_id)
            volume_value = volume
            if volume_value > self.max_volume:
                return self._result(action, "refused", f"That is above the safe limit of {self.max_volume}%.", request_id)
        try:
            chosen = self._resolve_device(device)
            if isinstance(chosen, MusicResult):
                return self._with(chosen, action, request_id)
            target = ""
            if action in ("play", "queue"):
                resolved = self._resolve_item(action, query, kind, uri, request_id)
                if isinstance(resolved, MusicResult):
                    return resolved
                target = resolved.uri
            self._dispatch(action, chosen.id, target, volume_value)
            return self._confirm(action, chosen, target, request_id)
        except ProviderError as exc:
            return self._failure(action, exc, request_id)

    def _dispatch(self, action: str, device_id: str, target: str, volume: Optional[int]) -> None:
        if action == "play":
            self.provider.play(target, device_id)
        elif action == "queue":
            self.provider.queue(target, device_id)
        elif action == "pause":
            self.provider.pause(device_id)
        elif action == "resume":
            self.provider.resume(device_id)
        elif action == "next":
            self.provider.next(device_id)
        elif action == "volume":
            self.provider.set_volume(int(volume), device_id)

    def _confirm(self, action: str, device: Device, target: str, request_id: str) -> MusicResult:
        """Report the ACTUAL state where it can be read back; say so when it cannot."""
        try:
            now = self.provider.now_playing()
        except Exception:  # noqa: BLE001 - the write already happened; an unreadable state is reported as unconfirmed
            now = None
        confirmed = {
            "play": lambda n: bool(n and n.playing and n.item and n.item.uri == target),
            "pause": lambda n: bool(n and not n.playing),
            "resume": lambda n: bool(n and n.playing),
        }.get(action)
        ok = True if confirmed is None else bool(confirmed(now))
        verb = {"play": "Playing", "queue": "Queued", "pause": "Paused", "resume": "Resumed", "next": "Skipped",
                "volume": "Volume set"}[action]
        status = "done" if ok else "done_unconfirmed"
        text = f"{verb} on {device.name}." if ok else f"{verb} on {device.name}, but I could not confirm the player's state."
        return self._result(action, status, _say(self.provider, text), request_id, {"device_id": device.id})

    # ------------------------------------------------------------------ resolution
    def _resolve_device(self, wanted: str):
        devices = self.provider.devices()
        if not devices:
            raise ProviderError("no_device", "no playback device is available")
        name = str(wanted or "").strip().lower()
        if name:
            exact = [d for d in devices if d.name.lower() == name]
            partial = exact or [d for d in devices if d.name.lower().startswith(name)]
            if len(partial) == 1:
                return partial[0]
            if not partial:
                return MusicResult("", "clarify", _say(self.provider, f"I can't find a device called {wanted!r}."),
                                   getattr(self.provider, "simulated", False), {"options": self._names(devices)})
            return MusicResult("", "clarify", _say(self.provider, "More than one device matches."),
                               getattr(self.provider, "simulated", False), {"options": self._names(partial)})
        active = [d for d in devices if d.active]
        if len(active) == 1:
            return active[0]
        if len(devices) == 1:
            return devices[0]
        return MusicResult("", "clarify", _say(self.provider, "Which device should I use?"),
                           getattr(self.provider, "simulated", False), {"options": self._names(devices)})

    def _resolve_item(self, action: str, query: str, kind: str, uri: str, request_id: str):
        if uri:
            if not _URI.fullmatch(str(uri)):
                return self._result(action, "refused", "That is not a valid music link.", request_id)
            return Item(uri=str(uri), title=str(uri))
        text = str(query or "").strip()
        if not text:
            return self._result(action, "refused", f"{action.capitalize()} needs a track, artist or playlist.", request_id)
        found = self.provider.search(text, kind)
        if not found:
            return self._result(action, "not_found", _say(self.provider, f"I couldn't find {text!r}."), request_id,
                                suggestion="Try the artist and title, or ask me to search first.")
        exact = [i for i in found if i.title.lower() == text.lower()]
        pick = exact if len(exact) == 1 else (found if len(found) == 1 else [])
        if pick:
            return pick[0]
        return self._result(action, "clarify", _say(self.provider, "Which one did you mean?"), request_id,
                            {"options": [self._item(i) for i in (exact or found)[:MAX_OPTIONS]]})

    # ------------------------------------------------------------------ results
    def _failure(self, action: str, exc: ProviderError, request_id: str) -> MusicResult:
        text, suggestion = {
            "auth": ("The music account needs to be reconnected.", "Ask the owner to reconnect the music account."),
            "forbidden": ("This account is not allowed to do that.", "Check that the account has an eligible plan and scopes."),
            "rate_limited": ("The music service asked me to slow down.", "Try again shortly."),
            "offline": ("I can't reach the music service.", "Try again when the connection is back."),
            "no_device": ("No playback device is available.", "Open the music app on a speaker and try again."),
            "not_found": ("The music service could not find that.", "Try different words."),
            "unexpected": ("Something went wrong with the music service.", "Try again; if it keeps happening, tell the owner."),
        }.get(exc.code, ("The music service failed.", "Try again later."))
        data = {"retry_after": exc.retry_after} if exc.retry_after else {}
        return self._result(action, "error", _say(self.provider, text), request_id, data, suggestion, code=exc.code)

    def _result(self, action: str, status: str, message: str, request_id: str, data: Optional[Dict[str, Any]] = None,
                suggestion: str = "", code: str = "") -> MusicResult:
        trace = {"action": action, "provider": getattr(self.provider, "name", "unknown"), "request_id": request_id,
                 "outcome": status}
        if code:
            trace["error"] = code
        return MusicResult(action, status, message, bool(getattr(self.provider, "simulated", False)), dict(data or {}),
                           suggestion, trace)

    def _with(self, partial: MusicResult, action: str, request_id: str) -> MusicResult:
        return self._result(action, partial.status, partial.message, request_id, partial.data)

    @staticmethod
    def _item(item: Item) -> Dict[str, str]:
        return {"uri": item.uri, "title": item.title, "artist": item.artist, "kind": item.kind}

    @staticmethod
    def _names(devices: List[Device]) -> List[str]:
        return [d.name for d in devices[:MAX_DEVICES_LISTED]]


class SimulatedMusicProvider:
    """In-memory provider for tests, drills and guest-safe demos. It records every call and can inject failures."""

    name = "simulation"
    simulated = True

    def __init__(self, catalogue: Optional[List[Item]] = None, devices: Optional[List[Device]] = None):
        self.catalogue = list(catalogue if catalogue is not None else [
            Item("spotify:track:sim0001", "Kind of Blue", "Miles Davis"),
            Item("spotify:track:sim0002", "Pastel Blues", "Nina Simone"),
            Item("spotify:track:sim0003", "Waltz for Debby", "Bill Evans"),
        ])
        self._devices = list(devices if devices is not None else [Device("dev-kitchen", "Kitchen speaker", True, 40)])
        self.state = NowPlaying(None, False, None)
        self.queued: List[str] = []
        self.volume: Dict[str, int] = {d.id: (d.volume or 0) for d in self._devices}
        self.calls: List[Tuple[str, tuple]] = []
        self._failures: List[ProviderError] = []

    def fail_next(self, code: str, retry_after: Optional[int] = None) -> None:
        self._failures.append(ProviderError(code, retry_after=retry_after))

    def _check(self) -> None:
        if self._failures:
            raise self._failures.pop(0)

    def _log(self, name: str, *args) -> None:
        self.calls.append((name, args))

    def search(self, query: str, kind: str) -> List[Item]:
        self._log("search", query, kind)
        self._check()
        words = [w for w in re.findall(r"\w+", query.lower()) if w]
        return [i for i in self.catalogue if all(w in f"{i.title} {i.artist}".lower() for w in words)]

    def devices(self) -> List[Device]:
        self._log("devices")
        self._check()
        return list(self._devices)

    def now_playing(self) -> Optional[NowPlaying]:
        self._log("now_playing")
        self._check()
        return self.state

    def play(self, uri: str, device_id: str) -> None:
        self._log("play", uri, device_id)
        self._check()
        item = next((i for i in self.catalogue if i.uri == uri), Item(uri, uri))
        self.state = NowPlaying(item, True, device_id)

    def pause(self, device_id: str) -> None:
        self._log("pause", device_id)
        self._check()
        self.state = NowPlaying(self.state.item, False, device_id)

    def resume(self, device_id: str) -> None:
        self._log("resume", device_id)
        self._check()
        self.state = NowPlaying(self.state.item, self.state.item is not None, device_id)

    def next(self, device_id: str) -> None:
        self._log("next", device_id)
        self._check()
        items = self.catalogue
        index = next((n for n, i in enumerate(items) if self.state.item and i.uri == self.state.item.uri), -1)
        self.state = NowPlaying(items[(index + 1) % len(items)], True, device_id)

    def queue(self, uri: str, device_id: str) -> None:
        self._log("queue", uri, device_id)
        self._check()
        self.queued.append(uri)

    def set_volume(self, percent: int, device_id: str) -> None:
        self._log("set_volume", percent, device_id)
        self._check()
        self.volume[device_id] = percent

    def writes(self) -> List[str]:
        return [name for name, _ in self.calls if name in {"play", "pause", "resume", "next", "queue", "set_volume"}]
