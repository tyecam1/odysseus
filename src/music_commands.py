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
_TAIL = re.compile(r"(?:,\s*please|,\s*thanks?|,\s*thank you|\s+for me)?[\s,.!?]*$", re.I)
_TAIL_PLEASE = re.compile(r"(?:\s+please)?[\s,.!?]*$", re.I)           # a bare trailing "please", only after a polite opening
_SERVICE = re.compile(r"\s+(?:on|in|using|with|through|via)\s+(?:the\s+)?spotify\b", re.I)
_PLAY = re.compile(r"^(?:play|put on|stick on|throw on|start playing)\s+(?P<q>.+)$", re.I)
_QUEUE = re.compile(r"^(?:queue(?: up)?\s+(?P<q>.+)|add\s+(?P<q2>.+?)\s+to\s+(?:the\s+|my\s+)?(?:queue|up next))$", re.I)
_RESUME = re.compile(r"^(?:play|resume|unpause|play (?:it|the music|music)(?: again)?|start (?:the )?music|keep (?:the )?music (?:playing|going))$", re.I)
_PAUSE = re.compile(r"^(?:pause(?: (?:it|the music|music|this|the song|the track))?|stop (?:the )?(?:music|playing|playback|song|track))$", re.I)
_NEXT = re.compile(r"^(?:skip(?: (?:this|this song|this track|the song|the track))?|next(?: (?:song|track))|play (?:the )?next (?:song|track))$", re.I)
_NOW = re.compile(r"^(?:what(?:'s| is) playing(?: right now| now)?|what(?:'s| is) this (?:song|track)|what (?:song|track) is (?:this|playing)|who(?:'s| is) this (?:song |track )?by|what am i listening to)$", re.I)
_DEVICES = re.compile(r"^(?:(?:list|show|what|which)\s+(?:are\s+)?(?:the\s+|my\s+)?(?:spotify\s+)?(?:devices|speakers)(?:\s+(?:are\s+)?(?:available|there))?|what can (?:you|we) play (?:on|through))$", re.I)
_VOLUME_SET = re.compile(r"^(?:set\s+)?(?:the\s+)?volume\s+(?:to\s+)?(?P<n>\d{1,3})\s*(?:%|percent)?$", re.I)
_VOLUME_REL = re.compile(r"^(?:turn|bring|put|set|make)\s+(?:it|the\s+(?:music|volume|sound)|this)\s+(?P<d>up|down)(?:\s+a\s+(?:bit|little|touch))?$|^(?P<d2>louder|quieter|softer)$|^turn\s+(?P<d3>up|down)\s+the\s+(?:music|volume)$", re.I)
_KIND = re.compile(r"^(?:the\s+)?(?P<k>album|playlist|artist|band)\s+(?P<q>.+)$", re.I)
_NOT_MUSIC = re.compile(r"^(?:(?:a|the|some|another) )?(?:game|games|match|round|hand|cards|chess|hide and seek|fetch)\b|\bwith (?:me|us|him|her|them|the (?:kids|dog|cat))$", re.I)
_ON_DEVICE = re.compile(r"\s+on\s+(?:the\s+|my\s+)?(?P<d>[A-Za-z0-9' _-]{2,40})$", re.I)
_LEADING_THE = re.compile(r"^(?:the\s+(?:song|track|tune)\s+)", re.I)


@dataclass(frozen=True)
class MusicCommand:
    action: str                 # a music_capability action: play, pause, resume, next, queue, volume, search, devices, now_playing
    query: str = ""
    kind: str = "track"
    volume_delta: int = 0       # for relative volume; the runtime turns it into an absolute percent
    volume: Optional[int] = None
    fallback_query: str = ""    # the query without a trailing bare "please", tried only if the literal query finds nothing
    device_hint: str = ""       # "on the laptop": a hint only; the runtime keeps it as a device if one matches, else it stays part of the query
    query_with_hint: str = ""   # the query INCLUDING the trailing "on <hint>" (a title may end that way: "Stand on Me")


def parse_music_command(text: str) -> Optional[MusicCommand]:
    """The music request in ``text``, or None when it is not one. Never raises."""
    command = _parse(text)
    if command is None:
        return None
    if command.action in ("play", "queue") and command.query:
        match = _ON_DEVICE.search(command.query)
        if match and match.start() > 0:
            hint = re.sub(r"\s+please$", "", match.group("d").strip(), flags=re.I)
            stripped = command.query[:match.start()].strip()
            if not hint or re.fullmatch(r"(?:something|anything|whatever|some music|music)", stripped, re.I):
                return None                                        # "play something on the tv" names no music
            return MusicCommand(command.action, query=stripped, kind=command.kind, fallback_query=command.fallback_query,
                                device_hint=hint, query_with_hint=command.query)
    return command


def _parse(text: str) -> Optional[MusicCommand]:
    if not isinstance(text, str):
        return None
    work = " ".join(text.split())
    if not work or len(work) > MAX_PROMPT_CHARS:
        return None
    opening = _POLITE.match(work).group(0)
    polite_open = bool(re.search(r"please|can you|could you|would you|will you", opening, re.I))
    work = _POLITE.sub("", work, count=1).strip()
    had_service = bool(_SERVICE.search(work))             # "play Please on Spotify" names a title; a bare "play please" is politeness
    work = _SERVICE.sub("", work)
    # Trailing politeness is stripped ONCE. ", please" / ", thanks" / "for me" always; a bare " please" only after a polite opening
    # ("could you play Blue please"), because "play Please Please Please" and "play Thank You" are titles.
    trimmed = _TAIL.sub("", work).strip()
    if polite_open:
        trimmed = _TAIL_PLEASE.sub("", trimmed).strip()
    work = work.strip(" \t,.!?") if trimmed.lower() in ("play", "queue", "add") else trimmed
    if not work:
        return None
    bare = _TAIL_PLEASE.sub("", work).strip()          # a command with no title in it can lose a trailing "please" safely
    device_match = _ON_DEVICE.search(bare)
    if device_match and device_match.start() > 0:
        head = bare[:device_match.start()].strip()
        hint = device_match.group("d").strip()
        for pattern, action in ((_RESUME, "resume"), (_PAUSE, "pause"), (_NEXT, "next")):
            if pattern.match(head):
                return MusicCommand(action, device_hint=hint)
    if had_service and bare.lower() in ("play", "queue", "add"):
        bare = work                                    # "play Please on Spotify": nothing but "please" is left, so it is the title
    if _RESUME.match(bare):
        return MusicCommand("resume")
    if _PAUSE.match(bare):
        return MusicCommand("pause")
    if _NEXT.match(bare):
        return MusicCommand("next")
    if _NOW.match(bare):
        return MusicCommand("now_playing")
    if _DEVICES.match(bare):
        return MusicCommand("devices")
    work_with_please = work
    match = _VOLUME_SET.match(work)
    if match:
        return MusicCommand("volume", volume=int(match.group("n")))
    match = _VOLUME_REL.match(bare)
    if match:
        direction = (match.group("d") or match.group("d3") or "").lower() or ("up" if match.group("d2").lower() == "louder" else "down")
        return MusicCommand("volume", volume_delta=VOLUME_STEP if direction == "up" else -VOLUME_STEP)
    match = _QUEUE.match(work)
    if match and not _PLAY.match(work):
        return _with_fallback(_target("queue", match.group("q") or match.group("q2")), bare, work_with_please, _QUEUE, "queue")
    match = _PLAY.match(work)
    if match:
        return _with_fallback(_target("play", match.group("q")), bare, work_with_please, _PLAY, "play")
    return None


def _with_fallback(command, bare, work, pattern, action):
    """Keep the literal query (a title may end in "please"); remember the version without a bare trailing "please" for when the literal finds nothing."""
    if command is None or command.action != action or bare == work:
        return command
    match = pattern.match(bare)
    if not match:
        return command
    alt = _target(action, match.group("q") if "q" in pattern.groupindex and match.group("q") else (match.groupdict().get("q2") or ""))
    if alt is not None and alt.query and alt.query != command.query:
        return MusicCommand(command.action, query=command.query, kind=command.kind, fallback_query=alt.query)
    return command


def _target(action: str, raw: str) -> Optional[MusicCommand]:
    query = raw.strip().strip(" \t,.!?").strip("\"'“”‘’")      # politeness was already handled once, on the whole sentence
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
