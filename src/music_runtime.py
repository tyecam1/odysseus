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

import json
import logging
import os
import re
import threading
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

    # ------------------------------------------------------------------ state
    def configured(self) -> bool:
        try:
            return _client_id(self.directory) is not None and (self.directory / "token.bin").is_file()
        except OSError:
            return False

    def _build(self) -> Optional[MusicController]:
        with self._lock:
            if self._controller is not None:
                return self._controller
            client = _client_id(self.directory)
            if client is None or not (self.directory / "token.bin").is_file():
                return None
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

    def _target_device(self):
        """The device a volume change will act on: the active one, or the only one; None when it cannot be told."""
        devices = self._provider.devices() if self._provider else []
        active = [d for d in devices if d.active]
        return active[0] if active else (devices[0] if len(devices) == 1 else None)

    def _run(self, controller: MusicController, command: MusicCommand, request_id: str) -> Dict[str, Any]:
        rid = "music-" + re.sub(r"[^A-Za-z0-9._:-]", "", request_id)[:48]
        action, kwargs = command.action, {}
        if action in ("play", "queue"):
            kwargs = {"query": command.query, "kind": command.kind}
        elif action == "volume":
            volume = command.volume
            if volume is None:                             # relative: act on the device we can actually read the level of
                target = self._target_device()
                if target is None or target.volume is None:
                    return {"status": "clarify", "data": {}, "trace": {},
                            "text": "I can't tell how loud it is right now. Say a number, like volume 30."}
                volume = max(0, min(100, target.volume + command.volume_delta))
                kwargs = {"volume": volume, "device": target.name}
            else:
                kwargs = {"volume": volume}
        result: MusicResult = controller.handle(action, request_id=rid, explicit_command=True, guest=False, **kwargs)
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
