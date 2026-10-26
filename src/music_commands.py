"""Deterministic parser from a spoken/typed music request to a ``music.*`` action (no model, no network).

Only an imperative or a direct question about playback is a music command: "play X", "pause", "skip", "what's playing", "turn it down", "queue X".
Anything else returns None and the turn continues down the ordinary Misumi path, so household talk that merely mentions a song is never executed.
Reads (``now_playing``, ``devices``) are harmless; writes still pass the ``MusicController`` governance (explicit command, device, volume bound).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

MAX_PROMPT_CHARS = 240
MAX_QUERY_CHARS = 120
VOLUME_STEP = 15

_POLITE = re.compile(r"^(?:(?:hey|ok|okay|right|so|now)[,\s]+)*(?:(?:please|can you|could you|would you|will you|i(?:'d| would) like you to|go ahead and)[,\s]+)*", re.I)
_TAIL = re.compile(r"[\s,.!?]*(?:please|thanks|thank you|for me)?[\s,.!?]*$", re.I)
_SERVICE = re.compile(r"\s+(?:on|in|using|with|through|via)\s+(?:the\s+)?spotify\b", re.I)
_PLAY = re.compile(r"^(?:play|put on|stick on|throw on|start playing|start)\s+(?P<q>.+)$", re.I)
_QUEUE = re.compile(r"^(?:queue(?: up)?|add)\s+(?P<q>.+?)(?:\s+to\s+(?:the\s+|my\s+)?(?:queue|up next))?$", re.I)
_RESUME = re.compile(r"^(?:play|resume|continue|unpause|keep (?:playing|going)|carry on|play (?:it|the music|music) (?:again)?|start (?:the )?music)$", re.I)
_PAUSE = re.compile(r"^(?:pause(?: (?:it|the music|music|this|the song|the track))?|stop (?:the )?(?:music|playing|playback|song|track)|stop (?:it|this))$", re.I)
_NEXT = re.compile(r"^(?:skip(?: (?:it|this|this song|this track|the song|the track))?|next(?: (?:song|track|one))?|play (?:the )?next (?:song|track|one))$", re.I)
_NOW = re.compile(r"^(?:what(?:'s| is| song is| track is)?\s+(?:this|that)?\s*(?:song|track)?\s*(?:playing|on)?(?: right now| now)?|what(?:'s| is) playing(?: right now| now)?|what song is (?:this|playing)|what(?:'s| is) this (?:song|track)|who(?:'s| is) this by|what am i listening to)$", re.I)
_DEVICES = re.compile(r"^(?:(?:list|show|what|which)\s+(?:are\s+)?(?:the\s+|my\s+)?(?:spotify\s+)?(?:devices|speakers)(?:\s+(?:are\s+)?(?:available|there))?|what can (?:you|we) play (?:on|through))$", re.I)
_VOLUME_SET = re.compile(r"^(?:set\s+)?(?:the\s+)?volume\s+(?:to\s+)?(?P<n>\d{1,3})\s*(?:%|percent)?$", re.I)
_VOLUME_REL = re.compile(r"^(?:turn|bring|put|set|make)\s+(?:it|the\s+(?:music|volume|sound)|this)\s+(?P<d>up|down)(?:\s+a\s+(?:bit|little|touch))?$|^(?P<d2>louder|quieter|softer)$|^turn\s+(?P<d3>up|down)\s+the\s+(?:music|volume)$", re.I)
_KIND = re.compile(r"^(?:the\s+)?(?P<k>album|playlist|artist|band)\s+(?P<q>.+)$", re.I)
_NOT_MUSIC = re.compile(r"^(?:(?:a|the|some|another) )?(?:game|games|match|round|hand|cards|chess|hide and seek|fetch)\b|\bwith (?:me|us|him|her|them|the (?:kids|dog|cat))$", re.I)
_LEADING_THE = re.compile(r"^(?:the\s+(?:song|track|tune)\s+)", re.I)


@dataclass(frozen=True)
class MusicCommand:
    action: str                 # a music_capability action: play, pause, resume, next, queue, volume, search, devices, now_playing
    query: str = ""
    kind: str = "track"
    volume_delta: int = 0       # for relative volume; the runtime turns it into an absolute percent
    volume: Optional[int] = None


def parse_music_command(text: str) -> Optional[MusicCommand]:
    """The music request in ``text``, or None when it is not one. Never raises."""
    if not isinstance(text, str):
        return None
    work = " ".join(text.split())
    if not work or len(work) > MAX_PROMPT_CHARS:
        return None
    work = _POLITE.sub("", work, count=1).strip()
    work = _SERVICE.sub("", work)
    work = _TAIL.sub("", work).strip()
    if not work:
        return None
    if _RESUME.match(work):
        return MusicCommand("resume")
    if _PAUSE.match(work):
        return MusicCommand("pause")
    if _NEXT.match(work):
        return MusicCommand("next")
    if _NOW.match(work):
        return MusicCommand("now_playing")
    if _DEVICES.match(work):
        return MusicCommand("devices")
    match = _VOLUME_SET.match(work)
    if match:
        return MusicCommand("volume", volume=int(match.group("n")))
    match = _VOLUME_REL.match(work)
    if match:
        direction = (match.group("d") or match.group("d3") or "").lower() or ("up" if match.group("d2").lower() == "louder" else "down")
        return MusicCommand("volume", volume_delta=VOLUME_STEP if direction == "up" else -VOLUME_STEP)
    match = _QUEUE.match(work)
    if match and not _PLAY.match(work):
        return _target("queue", match.group("q"))
    match = _PLAY.match(work)
    if match:
        return _target("play", match.group("q"))
    return None


def _target(action: str, raw: str) -> Optional[MusicCommand]:
    query = _TAIL.sub("", raw).strip().strip("\"'“”‘’")
    kind = "track"
    match = _KIND.match(query)
    if match:
        kind = {"band": "artist"}.get(match.group("k").lower(), match.group("k").lower())
        query = match.group("q").strip()
    query = _LEADING_THE.sub("", query).strip()
    if not query:
        return MusicCommand("resume") if action == "play" else None
    if re.fullmatch(r"(?:it|that|this|(?:the )?music|some music)", query, re.I):
        return MusicCommand("resume") if action == "play" else None
    if len(query) > MAX_QUERY_CHARS or re.fullmatch(r"(?:something|anything|whatever)", query, re.I):
        return None
    if _NOT_MUSIC.search(query):                  # "play a game of chess", "play cards with me": the verb is not about music
        return None
    return MusicCommand(action, query=query, kind=kind)
