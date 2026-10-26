"""Music in the Misumi respond path: Jin's governed ``music.*`` capability backed by Spotify, with the token held on the home runtime.

The pieces already exist: ``music_commands`` (deterministic request parser), ``music_capability.MusicController`` (read/write governance, device
resolution, idempotency, bounded volume, truthful results) and ``spotify_binding`` (PKCE tokens and the Spotify provider). This module only wires them:

* the token lives in ``<data>/spotify/token.bin`` protected with Windows DPAPI (``scripts/spotify_import_token.py`` writes it; nothing else does) and the public
  PKCE client id in ``<data>/spotify/client.json``; without both, music is "not connected" and nothing is attempted;
* a request is handled only when it parses as a music command AND it is plainly about music (the routed lead is Jin, Spotify is named, or it is a bare transport/
  read command such as "pause" or "what's playing"); a play/queue request routed to another persona, or any other talk, continues down the ordinary path;
* the spoken answer is the controller's truthful result (never "playing" unless read back), in Jin's voice.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.music_capability import DEFAULT_MAX_VOLUME, MusicController, MusicResult
from src.music_commands import MusicCommand, parse_music_command
from src.spotify_binding import FileTokenStore, SpotifyProvider, TokenManager, urllib_http

logger = logging.getLogger(__name__)

MUSIC_PERSONA = "jin"
_SPOTIFY_NAMED = re.compile(r"\bspotify\b", re.I)
_MUSICAL_WORDS = re.compile(r"\b(?:music|song|songs|track|tracks|tune|tunes|playlist|album|record|spotify)\b", re.I)
_READS = frozenset({"now_playing", "devices"})
_BY_ARTIST = re.compile(r"\bby\s+\S+", re.I)


def music_dir(data_dir: Any) -> Path:
    return Path(data_dir) / "spotify"


def _client_id(directory: Path) -> Optional[str]:
    try:
        data = json.loads((directory / "client.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    client = data.get("client_id") if isinstance(data, dict) else None
    return client if isinstance(client, str) and client.isalnum() else None


def _default_protection() -> tuple:
    from src import windows_dpapi
    scope = os.environ.get("MISUMI_SPOTIFY_DPAPI_SCOPE", "user")
    return (lambda b: windows_dpapi.protect(b, scope)), (lambda b: windows_dpapi.unprotect(b, scope))


class MusicRuntime:
    """Lazily builds the controller; ``configured`` is False (and every call a typed "not connected") until the token and client id are present."""

    def __init__(self, data_dir: Any, *, http: Optional[Callable] = None,
                 protection: Optional[tuple] = None, max_volume: int = DEFAULT_MAX_VOLUME):
        self.directory = music_dir(data_dir)
        self._http = http
        self._protection = protection
        self._max_volume = max_volume
        self._lock = threading.Lock()
        self._controller: Optional[MusicController] = None
        self._provider: Optional[SpotifyProvider] = None
        self._built_for: Optional[str] = None                          # the client id the cached controller was built with
        self._results: "OrderedDict[str, tuple]" = OrderedDict()       # completed writes by request id, so a retry returns the first answer

    # ------------------------------------------------------------------ state
    def configured(self) -> bool:
        try:
            return _client_id(self.directory) is not None and (self.directory / "token.bin").is_file()
        except OSError:
            return False

    def _build(self) -> Optional[MusicController]:
        with self._lock:
            client = _client_id(self.directory)
            if self._controller is not None and client == self._built_for:
                return self._controller
            # a new credential pair was installed (a different client id): the cached controller would submit the new refresh token with the old client
            self._controller = self._provider = None
            self._results.clear()
            if client is None or not (self.directory / "token.bin").is_file():
                return None
            self._built_for = client
            protect, unprotect = self._protection or _default_protection()
            http = self._http or urllib_http
            store = FileTokenStore(str(self.directory / "token.bin"), protect, unprotect)
            self._provider = SpotifyProvider(TokenManager(client, store, http), http)
            self._controller = MusicController(self._provider, max_volume=self._max_volume)
            return self._controller

    # ------------------------------------------------------------------ requests
    def wants(self, command: Optional[MusicCommand], prompt: str, lead: str) -> bool:
        """Is this turn plainly a music request for Jin's capability (rather than talk that happens to contain "play" or "pause")?"""
        if command is None:
            return False
        if lead == MUSIC_PERSONA or _SPOTIFY_NAMED.search(prompt) or _MUSICAL_WORDS.search(prompt):
            return True
        if command.action in ("play", "queue"):
            return bool(_BY_ARTIST.search(prompt))             # "play Blue by Joni Mitchell"; a bare "play something" is not enough
        if command.action == "volume":
            return False                                        # "turn it down" could be the TV: needs Jin, Spotify or a musical word
        return len(prompt.split()) <= 3                         # a bare "pause", "skip", "what's playing"

    def handle(self, command: MusicCommand, request_id: str, allow_writes: bool = False) -> Dict[str, Any]:
        """Run one command (blocking; call from a worker thread). Returns {"text", "status", "data", "trace"}; never raises.
        Changing playback needs ``allow_writes`` (the caller's execute authority); reading it does not."""
        if command.action not in _READS and not allow_writes:
            return {"status": "refused", "data": {}, "trace": {}, "text": "This connection isn't allowed to change playback."}
        controller = self._build()
        if controller is None:
            return {"status": "not_connected", "data": {}, "trace": {},
                    "text": "Spotify isn't connected on this system yet, so I can't play anything. The owner has to authorise it first."}
        try:
            return self._run(controller, command, request_id)
        except Exception as exc:  # noqa: BLE001 - a bug here must become an honest sentence, never a failed turn
            logger.warning("music turn failed: %s", type(exc).__name__, exc_info=True)
            return {"status": "error", "data": {}, "trace": {}, "text": "The music service failed on that request; nothing was changed."}

    def _device_config(self) -> Dict[str, Any]:
        """Optional <data>/spotify/devices.json: {"default": "<device name>", "aliases": {"laptop": "<device name>", ...}}. Absent or damaged = empty."""
        try:
            data = json.loads((self.directory / "devices.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _resolve_device_hint(self, hint: str):
        """The Spotify device a spoken hint names: a configured alias, or an EXACT (case-insensitive) device name. Never a substring:
        "play Sex on Fire" must not be able to select a device called FireTVStick."""
        devices = self._provider.devices() if self._provider else []
        wanted = hint.strip().lower()
        raw = self._device_config().get("aliases")
        aliases = {str(k).strip().lower(): v.strip().lower() for k, v in raw.items() if isinstance(v, str) and v.strip()} if isinstance(raw, dict) else {}
        target = aliases.get(wanted, wanted)
        matches = [d for d in devices if d.name.lower() == target]
        return matches[0] if len(matches) == 1 else None

    def _literal_title_exists(self, text: str, kind: str):
        """Is the WHOLE phrase exactly a result's title or "title by artist"? The matching phrase, "" for no, or None when Spotify could not be asked (uncertain: the caller must stop).
        Nothing is split or trimmed first, but a bare trailing "please" is tried both ways ("Sex on Fire please")."""
        candidates = {re.sub(r"\s+", " ", text).strip().casefold()}
        candidates.add(re.sub(r"\s+please$", "", re.sub(r"\s+", " ", text).strip(), flags=re.I).casefold())
        asked = [text] + ([re.sub(r"\s+please$", "", text.strip(), flags=re.I)] if re.search(r"\s+please$", text.strip(), re.I) else [])
        try:
            for query in asked:
                for item in (self._provider.search(query, kind) if self._provider else []):
                    title = re.sub(r"\s+", " ", item.title).strip().casefold()
                    both = re.sub(r"\s+", " ", "%s by %s" % (item.title, item.artist)).strip().casefold()
                    if title in candidates or both in candidates:
                        return query                                  # the phrase (with or without the trailing "please") that IS a title
        except Exception:  # noqa: BLE001 - uncertainty is not "no": the write must not go ahead on a guess
            return None
        return ""

    def _title_and_artist_match(self, query: str, kind: str) -> str:
        """For "<title> by <artist>": the URI of the ONE result whose artist contains the artist and whose title is (or starts with, ignoring punctuation and
        a trailing "(Rip)"-style suffix) the title. "" when there is no such single result, so the controller asks instead of guessing."""
        parts = re.split(r"\s+by\s+", query, maxsplit=1, flags=re.I)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip() or self._provider is None:
            return ""
        flat = lambda v: re.sub(r"[^a-z0-9]", "", v.casefold())      # noqa: E731
        title, artist = flat(parts[0]), flat(parts[1])
        try:
            found = [i for i in self._provider.search(query, kind)
                     if artist and artist in flat(i.artist) and title and flat(i.title).startswith(title)]
        except Exception:  # noqa: BLE001
            return ""
        uris = {i.uri for i in found}
        return next(iter(uris)) if len(uris) == 1 else ""

    def _idle_default_device(self):
        """The configured default device when it is present exactly once. Whether it may be used (only when nothing is active) is decided by the
        controller against ITS OWN device read, via the "idle-id:" reference, so a device becoming active in between is never overridden."""
        default = self._device_config().get("default")
        if not isinstance(default, str) or not default.strip():
            return None
        devices = self._provider.devices() if self._provider else []
        matches = [d for d in devices if d.name.lower() == default.strip().lower()]
        return matches[0] if len(matches) == 1 else None

    def _target_device(self):
        """The device a volume change will act on: the active one, or the only one; None when it cannot be told."""
        devices = self._provider.devices() if self._provider else []
        active = [d for d in devices if d.active]
        return active[0] if active else (devices[0] if len(devices) == 1 else None)

    def _run(self, controller: MusicController, command: MusicCommand, request_id: str) -> Dict[str, Any]:
        key = request_id if re.fullmatch(r"[A-Za-z0-9._:-]{1,56}", request_id or "") else hashlib.sha256((request_id or "").encode("utf-8")).hexdigest()[:56]
        rid = "music-" + key                                         # never truncated: two distinct keys can never share a controller id
        is_write = command.action not in _READS
        fingerprint = (command.action, command.query, command.kind, command.volume, command.volume_delta, command.device_hint, command.query_with_hint, command.fallback_query)
        if is_write:
            with self._lock:
                seen = self._results.get(rid)
            if seen is not None and seen[0] == fingerprint:           # a retry: answer from the first run BEFORE resolving anything relative
                return seen[1]
        result = self._execute(controller, command, rid)
        if is_write and result["status"] not in ("error", "not_connected"):
            with self._lock:
                self._results[rid] = (fingerprint, result)
                while len(self._results) > 256:
                    self._results.popitem(last=False)
        return result

    def _execute(self, controller: MusicController, command: MusicCommand, rid: str) -> Dict[str, Any]:
        action, kwargs = command.action, {}
        device_ref = ""                                               # "id:<spotify id>" once WE chose the device: exact, immune to name prefixes
        if command.device_hint:
            found = self._resolve_device_hint(command.device_hint)
            literal = (self._literal_title_exists(command.query_with_hint, command.kind)
                       if action in ("play", "queue") and command.query_with_hint else False)
            if literal is None:                                       # Spotify could not be asked whether the phrase is a title: stop, do not guess
                return {"status": "clarify", "data": {}, "trace": {},
                        "text": "I couldn't check that with Spotify just now, so I haven't played anything. Try again in a moment."}
            if found is not None and literal:                         # the whole phrase is a real title AND its tail names a device: never guess which
                return {"status": "clarify", "data": {}, "trace": {},
                        "text": "Did you mean the track %s, or %s on %s? Say which." % (command.query_with_hint, command.query, found.name)}
            if found is not None:
                device_ref = "id:" + found.id
            elif literal:
                command = MusicCommand(action, query=literal, kind=command.kind)                             # a real title ending "on ..."
            else:                                                     # an unresolved explicit target is never guessed at or played to the active device
                return {"status": "clarify", "data": {}, "trace": {}, "text": "I don't know a device called %s." % command.device_hint}
        if not device_ref and action in ("play", "queue", "resume"):
            idle = self._idle_default_device()
            device_ref = "idle-id:" + idle.id if idle is not None else ""
        if action in ("play", "queue"):
            query = command.query
            if command.fallback_query and self._provider is not None:       # "play Blue please": the literal wins if it exists, else drop the "please"
                try:
                    if not self._provider.search(query, command.kind):
                        query = command.fallback_query
                except Exception:  # noqa: BLE001 - the controller will report the real failure on its own search
                    pass
            kwargs = {"query": query, "kind": command.kind}
        elif action == "volume":
            volume = command.volume
            if volume is None:                             # relative: act on the device we can actually read the level of
                target = self._target_device()
                if target is None or target.volume is None:
                    return {"status": "clarify", "data": {}, "trace": {},
                            "text": "I can't tell how loud it is right now. Say a number, like volume 30."}
                volume = max(0, min(100, target.volume + command.volume_delta))
                kwargs = {"volume": volume, "device": "id:" + target.id}
            else:
                kwargs = {"volume": volume}
        if device_ref and "device" not in kwargs:
            kwargs["device"] = device_ref
        result: MusicResult = controller.handle(action, request_id=rid, explicit_command=True, guest=False, **kwargs)
        if result.status == "clarify" and action in ("play", "queue") and kwargs.get("query") and re.search(r"\sby\s", kwargs["query"], re.I):
            # "<title> by <artist>" that the search left ambiguous only because of noise or a "(Rip)"-style suffix: if exactly ONE result matches both the
            # artist and the title, that is what was asked for. Two matches (or none) stay a question.
            exact = self._title_and_artist_match(kwargs["query"], command.kind)
            if exact:
                retry = {"uri": exact, "kind": command.kind}
                if kwargs.get("device"):
                    retry["device"] = kwargs["device"]
                result = controller.handle(action, request_id=rid + "-u", explicit_command=True, guest=False, **retry)
        return {"status": result.status, "data": result.data, "trace": result.trace, "text": _speak(result)}


def _speak(result: MusicResult) -> str:
    text = result.message
    options = result.data.get("options") if isinstance(result.data, dict) else None
    if result.status == "clarify" and options:
        listed = "; ".join(_option(o) for o in options[:3])
        text = "%s %s. Say which one." % (text, listed)
    elif result.status == "done" and result.data.get("results"):
        listed = "; ".join("%s%s" % (o.get("title", ""), (" by " + o["artist"]) if o.get("artist") else "") for o in result.data["results"][:3])
        text = "%s %s" % (text, listed)
    elif result.data.get("devices") is not None:
        names = ", ".join(d.get("name", "") + (" (active)" if d.get("active") else "") for d in result.data["devices"])
        text = "%s %s" % (text, names)
    if result.suggestion and result.status in ("error", "not_found"):
        text = "%s %s" % (text, result.suggestion)
    return text


def _option(option: Any) -> str:
    if isinstance(option, dict):
        return "%s%s" % (option.get("title", ""), (" by " + option["artist"]) if option.get("artist") else "")
    return str(option)


def music_reply(runtime: MusicRuntime, prompt: str, lead: str, request_id: str, allow_writes: bool = False) -> Optional[Dict[str, Any]]:
    """Blocking helper for the respond route: the music answer for this turn, or None when the turn is not a music request."""
    command = parse_music_command(prompt)
    if not runtime.wants(command, prompt, lead):
        return None
    return runtime.handle(command, request_id, allow_writes)
