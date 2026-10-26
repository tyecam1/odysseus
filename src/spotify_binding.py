"""Spotify binding for the provider-agnostic ``music.*`` contract (src/music_capability.py): OAuth 2.0 PKCE, token custody, a real provider.

Design 2026-10-16, owner decision 2026-10-26: the owner authorises Spotify interactively in their OWN laptop browser; nothing is authorised on
the kiosk, the lab or a headless browser, and no password, client secret or token is ever typed into chat. This module has no network of its own
and no credential defaults: HTTP, the clock and the token store are injected, so every rule below is testable with fakes and nothing here can
reach Spotify until a caller supplies a real transport.

* PKCE (S256) with a one-shot, expiring ``AuthSession`` bound to a random ``state``; the loopback redirect must be ``http://127.0.0.1|[::1]:PORT/callback``.
* The granted scopes must equal the three playback scopes exactly: an extra (write-to-library, playlist, ...) scope is refused and nothing is stored.
* ``TokenManager`` refreshes before expiry, rotates a rotated refresh token, and on ``invalid_grant`` clears the store and reports ``auth``.
  Tokens never appear in reprs, exceptions or traces.
* ``SpotifyProvider`` implements ``MusicProvider``. Reads only ever issue GET; writes are PUT/POST with explicit device ids; failures become
  typed ``ProviderError`` codes (auth, forbidden, rate_limited, offline, no_device, not_found, unexpected). Idempotency by request id stays in
  ``MusicController``; the provider never retries a write.
* ``FileTokenStore`` refuses to run without protect/unprotect callables (DPAPI on the laptop), so plaintext tokens on disk are not an option.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.music_capability import Device, Item, NowPlaying, ProviderError

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
SCOPES = ("user-read-playback-state", "user-read-currently-playing", "user-modify-playback-state")
SESSION_TTL_S = 600
REFRESH_SKEW_S = 60
LOCK_WAIT_S = 30
HTTP_TIMEOUT_S = 15
MAX_RESPONSE_BYTES = 1 << 20
_SEARCH_TYPES = {"track", "album", "playlist", "artist"}
_CONTEXT_KINDS = {"album", "playlist", "artist", "show"}

Http = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, Dict[str, str], bytes]]


class BindingError(Exception):
    """An authorisation problem with a short machine code (state-mismatch, replayed, expired, scope-mismatch, denied, exchange-failed, ...)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# --------------------------------------------------------------------------------------------------------------------- HTTP seam
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # a redirect would carry the bearer token elsewhere
        return None


def urllib_http(method: str, url: str, headers: Dict[str, str], body: Optional[bytes], timeout: float) -> Tuple[int, Dict[str, str], bytes]:
    """The real transport: https to Spotify only, redirects never followed, response capped. Returns (status, lower-cased headers, body)."""
    if not url.startswith(("https://accounts.spotify.com/", "https://api.spotify.com/")):
        raise ProviderError("unexpected", "refusing a non-Spotify url")
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
    except urllib.error.HTTPError as exc:
        data = b""
        try:
            data = exc.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
        except Exception:  # noqa: BLE001
            pass
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, data
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError("offline", type(exc).__name__) from None


# --------------------------------------------------------------------------------------------------------------------- PKCE
def new_verifier() -> str:
    """A 64-character PKCE code verifier (RFC 7636: 43-128 unreserved characters)."""
    return secrets.token_urlsafe(48)[:64]


def challenge_for(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def redirect_uri_ok(uri: Any) -> bool:
    """Spotify accepts loopback IP literals (not "localhost"). The page must be exactly http://127.0.0.1|[::1]:PORT/callback."""
    if not isinstance(uri, str):
        return False
    try:
        parts = urllib.parse.urlsplit(uri)
        port = parts.port
    except ValueError:
        return False
    return (parts.scheme == "http" and parts.hostname in ("127.0.0.1", "::1") and port is not None and 1024 <= port <= 65535
            and parts.path == "/callback" and not parts.query and not parts.fragment and not parts.username)


@dataclass
class TokenRecord:
    access_token: str
    refresh_token: str
    expires_at: float
    scope: str
    user_id: str = ""

    def __repr__(self) -> str:  # never print secrets
        return f"TokenRecord(user_id={self.user_id!r}, expires_at={self.expires_at}, scope={self.scope!r}, tokens=<redacted>)"

    def to_json(self) -> Dict[str, Any]:
        return {"access_token": self.access_token, "refresh_token": self.refresh_token, "expires_at": self.expires_at,
                "scope": self.scope, "user_id": self.user_id}

    @classmethod
    def from_json(cls, data: Any) -> Optional["TokenRecord"]:
        if not isinstance(data, dict):
            return None
        try:
            record = cls(str(data["access_token"]), str(data["refresh_token"]), float(data["expires_at"]), str(data["scope"]),
                         str(data.get("user_id") or ""))
        except (KeyError, TypeError, ValueError):
            return None
        return record if record.access_token and record.refresh_token else None


# --------------------------------------------------------------------------------------------------------------------- token stores
class MemoryTokenStore:
    def __init__(self) -> None:
        self._record: Optional[TokenRecord] = None
        self._lock = threading.Lock()
        self._exclusive = threading.RLock()

    @contextlib.contextmanager
    def exclusive(self):
        """One refresh/revoke at a time across every manager sharing this store."""
        with self._exclusive:
            yield

    def load(self) -> Optional[TokenRecord]:
        with self._lock:
            return self._record

    def save(self, record: TokenRecord) -> None:
        with self._lock:
            self._record = record

    def clear(self) -> None:
        with self._lock:
            self._record = None


def _lock_file(handle, wait_s: float) -> None:
    """Take an exclusive OS lock on `handle`, polling until `wait_s`; raises ProviderError("offline") if it stays contended."""
    deadline = time.monotonic() + wait_s
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise ProviderError("offline", "token store busy") from None
            time.sleep(0.05)


def _unlock_file(handle) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


class FileTokenStore:
    """Token custody in one file, always passed through caller-supplied ``protect``/``unprotect`` (Windows DPAPI on the laptop).

    There is deliberately no plaintext default. A missing, unreadable or tampered file loads as "not connected" rather than raising."""

    def __init__(self, path: str, protect: Callable[[bytes], bytes], unprotect: Callable[[bytes], bytes]):
        if not callable(protect) or not callable(unprotect):
            raise ValueError("FileTokenStore needs protect and unprotect callables")
        self.path, self._protect, self._unprotect = path, protect, unprotect
        self._lock = threading.Lock()
        self._exclusive = threading.RLock()

    @contextlib.contextmanager
    def exclusive(self):
        """One refresh/revoke at a time across threads AND processes (an OS lock on a sibling lock file).

        Acquisition is bounded (LOCK_WAIT_S, longer than one HTTP call) and non-blocking-polled on both platforms, because msvcrt's blocking
        lock gives up after about ten seconds with a bare OSError; contention that outlasts the bound is a typed "offline" error."""
        if not self._exclusive.acquire(timeout=LOCK_WAIT_S):
            raise ProviderError("offline", "token store busy")
        try:
            directory = os.path.dirname(os.path.abspath(self.path))
            os.makedirs(directory, exist_ok=True)
            with open(self.path + ".lock", "a+b") as handle:
                _lock_file(handle, LOCK_WAIT_S)
                try:
                    yield
                finally:
                    _unlock_file(handle)
        finally:
            self._exclusive.release()

    def load(self) -> Optional[TokenRecord]:
        with self._lock:
            try:
                with open(self.path, "rb") as fh:
                    return TokenRecord.from_json(json.loads(self._unprotect(fh.read()).decode("utf-8")))
            except (OSError, ValueError, UnicodeDecodeError):
                return None
            except Exception:  # noqa: BLE001 - an unprotect failure (another user, a corrupt blob) is "not connected"
                return None

    def save(self, record: TokenRecord) -> None:
        blob = self._protect(json.dumps(record.to_json()).encode("utf-8"))
        with self._lock:
            directory = os.path.dirname(os.path.abspath(self.path))
            os.makedirs(directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, prefix=".spotify-", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(blob)
                try:
                    os.chmod(tmp, 0o600)
                except OSError:
                    pass
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise

    def clear(self) -> None:
        with self._lock:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass


# --------------------------------------------------------------------------------------------------------------------- authorisation
def _form(fields: Dict[str, str]) -> bytes:
    return urllib.parse.urlencode(fields).encode("ascii")


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8")) if body else None
    except (ValueError, UnicodeDecodeError):
        return None


class AuthSession:
    """One interactive authorisation: PKCE verifier + random state, single use, expires. Public client: no client secret exists or is needed."""

    def __init__(self, client_id: str, redirect_uri: str, *, clock: Callable[[], float] = time.monotonic):
        if not isinstance(client_id, str) or not client_id.strip() or not all(c.isalnum() for c in client_id.strip()):
            raise ValueError("a Spotify client id is a plain alphanumeric string")
        if not redirect_uri_ok(redirect_uri):
            raise ValueError("redirect uri must be http://127.0.0.1:PORT/callback (or [::1])")
        self.client_id, self.redirect_uri, self._clock = client_id.strip(), redirect_uri, clock
        self._verifier, self.state = new_verifier(), secrets.token_urlsafe(24)
        self._started, self._used = clock(), False
        self._lock = threading.Lock()

    def authorize_url(self) -> str:
        return AUTH_URL + "?" + urllib.parse.urlencode({
            "response_type": "code", "client_id": self.client_id, "redirect_uri": self.redirect_uri, "scope": " ".join(SCOPES),
            "state": self.state, "code_challenge_method": "S256", "code_challenge": challenge_for(self._verifier), "show_dialog": "true"})

    def complete(self, query: Dict[str, str], http: Http, *, now: Callable[[], float] = time.time) -> TokenRecord:
        """Validate the callback and exchange the code. Raises BindingError; nothing is stored here (the caller stores the verified record)."""
        with self._lock:
            if self._used:
                raise BindingError("replayed")
            self._used = True                       # one attempt, whatever happens next: a failed exchange needs a fresh session
        if self._clock() - self._started > SESSION_TTL_S:
            raise BindingError("expired")
        state = query.get("state")
        if not isinstance(state, str) or not hmac.compare_digest(state.encode("utf-8"), self.state.encode("utf-8")):
            raise BindingError("state-mismatch")
        if query.get("error"):
            raise BindingError("denied")
        code = query.get("code")
        if not isinstance(code, str) or not code or len(code) > 2048:
            raise BindingError("no-code")
        try:
            status, _, body = http("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, _form({
                "grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri, "client_id": self.client_id,
                "code_verifier": self._verifier}), HTTP_TIMEOUT_S)
        except ProviderError:
            raise BindingError("exchange-failed") from None
        data = _json(body)
        if status != 200 or not isinstance(data, dict) or not data.get("access_token") or not data.get("refresh_token"):
            raise BindingError("exchange-failed")
        granted = set(str(data.get("scope", "")).split())
        if granted != set(SCOPES):                  # missing playback scopes, or ANY extra scope: refuse and keep nothing
            raise BindingError("scope-mismatch")
        try:
            expires_in = float(data.get("expires_in", 0))
        except (TypeError, ValueError):
            raise BindingError("exchange-failed") from None
        return TokenRecord(str(data["access_token"]), str(data["refresh_token"]), now() + max(0.0, expires_in), " ".join(sorted(granted)))


class TokenManager:
    """Hands out a valid access token, refreshing under a lock. A dead refresh token clears the store: the account must be reconnected."""

    def __init__(self, client_id: str, store, http: Http, *, now: Callable[[], float] = time.time):
        self.client_id, self.store, self.http, self._now = client_id, store, http, now
        self._lock = threading.Lock()

    def connected(self) -> bool:
        return self.store.load() is not None

    def access_token(self, *, force_refresh: bool = False, rejected: str = "") -> str:
        """A valid access token. `rejected` is the token Spotify just answered 401 for: if the store already holds a different, still-valid
        token (another caller refreshed meanwhile), that one is returned and no second refresh is made."""
        record = self.store.load()
        if record is None:
            raise ProviderError("auth", "not connected")
        if rejected and record.access_token != rejected and record.expires_at - self._now() > REFRESH_SKEW_S:
            return record.access_token
        if force_refresh or record.expires_at - self._now() <= REFRESH_SKEW_S:
            record = self._refresh(record, force_refresh)
        return record.access_token

    def _refresh(self, stale: TokenRecord, force: bool) -> TokenRecord:
        """Refresh under the store's exclusive section, as compare-and-swap on the record this caller saw: whoever got the lock first
        refreshes; everyone else reloads and uses that result instead of refreshing again (and, when Spotify rotates the refresh token,
        instead of replaying a spent one, which would read as invalid_grant). The access token changes on every refresh even when the
        refresh token does not, so it is the generation marker."""
        with self.store.exclusive():
            record = self.store.load()
            if record is None:
                raise ProviderError("auth", "not connected")          # revoked while this call was waiting
            if record.access_token != stale.access_token and record.expires_at - self._now() > REFRESH_SKEW_S:
                return record                                          # another manager already refreshed
            status, headers, body = self.http("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, _form({
                "grant_type": "refresh_token", "refresh_token": record.refresh_token, "client_id": self.client_id}), HTTP_TIMEOUT_S)
            data = _json(body)
            if status in (400, 401) and isinstance(data, dict) and data.get("error") in ("invalid_grant", "invalid_client"):
                self.store.clear()                                     # still the same refresh token (we hold the lock): it really is dead
                raise ProviderError("auth", "refresh token rejected")
            if status == 429:
                raise ProviderError("rate_limited", retry_after=_retry_after(headers))
            if status != 200 or not isinstance(data, dict) or not data.get("access_token"):
                raise ProviderError("offline" if status >= 500 else "unexpected", f"refresh status {status}")
            try:
                expires_in = float(data.get("expires_in", 0))
            except (TypeError, ValueError):
                raise ProviderError("unexpected", "bad expires_in") from None
            granted = str(data.get("scope", "")) or record.scope
            if set(granted.split()) != set(SCOPES):
                self.store.clear()
                raise ProviderError("auth", "scope changed")
            fresh = TokenRecord(str(data["access_token"]), str(data.get("refresh_token") or record.refresh_token),
                                self._now() + max(0.0, expires_in), " ".join(sorted(set(granted.split()))), record.user_id)
            self.store.save(fresh)
            return fresh

    def revoke(self) -> None:
        """Forget the tokens locally, ordered after any refresh in flight (a refresh can never resurrect revoked credentials).
        Spotify has no PKCE revoke endpoint: also remove the app under Account > Apps to end the grant there."""
        with self.store.exclusive():
            self.store.clear()


def _rows(data: Any, *path: str) -> List[Any]:
    """data[path0][path1]... as a list, or [] for any shape that is not exactly that (a hostile or damaged body never raises)."""
    for key in path:
        data = data.get(key) if isinstance(data, dict) else None
    return data if isinstance(data, list) else []


def _retry_after(headers: Dict[str, str]) -> Optional[int]:
    try:
        value = int(float(headers.get("retry-after", "")))
    except (TypeError, ValueError):
        return None
    return max(1, min(value, 3600))


# --------------------------------------------------------------------------------------------------------------------- the provider
class SpotifyProvider:
    """``MusicProvider`` over the Spotify Web API. No simulation flag: ``simulated`` is False, so results never say "[simulation]"."""

    name = "spotify"
    simulated = False

    def __init__(self, tokens: TokenManager, http: Http, *, expected_user_id: str = ""):
        self.tokens, self.http, self.expected_user_id = tokens, http, expected_user_id

    # ---- plumbing
    def _call(self, method: str, path: str, query: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None,
              *, _retried: bool = False, _rejected: str = "") -> Tuple[int, Any]:
        url = API_URL + path + ("?" + urllib.parse.urlencode({k: v for k, v in (query or {}).items() if v not in (None, "")}) if query else "")
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        token = self.tokens.access_token(force_refresh=_retried, rejected=_rejected)
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        try:
            status, response_headers, raw = self.http(method, url, headers, payload, HTTP_TIMEOUT_S)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak a transport exception (it could name a header)
            raise ProviderError("offline", type(exc).__name__) from None
        if status == 401 and not _retried:
            if method == "GET":
                return self._call(method, path, query, body, _retried=True, _rejected=token)   # reads: one (coalesced) refresh, one replay
            self.tokens.access_token(force_refresh=True, rejected=token)        # writes are NEVER replayed: refresh for the next request only
            raise ProviderError("auth", "unauthorised")
        data = _json(raw)
        if status in (200, 201, 202, 204):
            return status, data
        reason = ""
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            reason = str(data["error"].get("reason", ""))
        if status == 401:
            raise ProviderError("auth", "unauthorised")
        if status == 403:
            raise ProviderError("forbidden", reason or "forbidden")
        if status == 404:
            raise ProviderError("no_device" if reason == "NO_ACTIVE_DEVICE" or path.startswith("/me/player") else "not_found", reason or "not found")
        if status == 429:
            raise ProviderError("rate_limited", retry_after=_retry_after(response_headers))
        raise ProviderError("offline" if status >= 500 else "unexpected", f"status {status}")

    def account(self) -> Dict[str, str]:
        """Account verification: the Spotify user id and plan. If an expected id was configured, a different account is refused."""
        _, data = self._call("GET", "/me")
        if not isinstance(data, dict) or not data.get("id"):
            raise ProviderError("unexpected", "no account")
        user = {"id": str(data["id"]), "product": str(data.get("product", ""))}
        if self.expected_user_id and user["id"] != self.expected_user_id:
            raise ProviderError("forbidden", "a different Spotify account is connected")
        return user

    # ---- reads (GET only)
    def search(self, query: str, kind: str) -> List[Item]:
        kind = kind if kind in _SEARCH_TYPES else "track"
        _, data = self._call("GET", "/search", {"q": query, "type": kind, "limit": 5})
        rows = _rows(data, kind + "s", "items")
        out: List[Item] = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("uri") or not row.get("name"):
                continue
            artists = row.get("artists") or ([{"name": row.get("owner", {}).get("display_name", "")}] if kind == "playlist" else [])
            artist = ", ".join(str(a.get("name", "")) for a in artists if isinstance(a, dict) and a.get("name"))[:120]
            item = Item(str(row["uri"]), str(row["name"])[:160], artist, kind)
            if kind == "track" and any(o.title.casefold() == item.title.casefold() and o.artist.casefold() == item.artist.casefold() for o in out):
                continue                           # a track listed twice (single and album) is one choice; playlists/albums/artists with equal names are not merged
            out.append(item)
        return out

    def devices(self) -> List[Device]:
        _, data = self._call("GET", "/me/player/devices")
        rows = _rows(data, "devices")
        return [Device(str(d["id"]), str(d.get("name", ""))[:80], bool(d.get("is_active")), d.get("volume_percent") if isinstance(d.get("volume_percent"), int) else None)
                for d in rows if isinstance(d, dict) and d.get("id")]

    def now_playing(self) -> Optional[NowPlaying]:
        status, data = self._call("GET", "/me/player/currently-playing", {"additional_types": "track"})
        if status == 204 or not isinstance(data, dict) or not isinstance(data.get("item"), dict):
            return None
        item = data["item"]
        artists = ", ".join(str(a.get("name", "")) for a in item.get("artists") or [] if isinstance(a, dict) and a.get("name"))[:120]
        return NowPlaying(Item(str(item.get("uri", "")), str(item.get("name", ""))[:160], artists, str(item.get("type", "track"))),
                          bool(data.get("is_playing")), (data.get("device") or {}).get("id") if isinstance(data.get("device"), dict) else None)

    # ---- writes (PUT/POST, always with an explicit device)
    def play(self, uri: str, device_id: str) -> None:
        kind = uri.split(":")[1] if uri.count(":") == 2 else ""
        body = {"context_uri": uri} if kind in _CONTEXT_KINDS else {"uris": [uri]}
        self._call("PUT", "/me/player/play", {"device_id": device_id}, body)

    def pause(self, device_id: str) -> None:
        self._call("PUT", "/me/player/pause", {"device_id": device_id})

    def resume(self, device_id: str) -> None:
        self._call("PUT", "/me/player/play", {"device_id": device_id})

    def next(self, device_id: str) -> None:
        self._call("POST", "/me/player/next", {"device_id": device_id})

    def queue(self, uri: str, device_id: str) -> None:
        self._call("POST", "/me/player/queue", {"uri": uri, "device_id": device_id})

    def set_volume(self, percent: int, device_id: str) -> None:
        self._call("PUT", "/me/player/volume", {"volume_percent": int(percent), "device_id": device_id})
