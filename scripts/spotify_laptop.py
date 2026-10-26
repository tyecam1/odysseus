"""Authorise and exercise Spotify from the OWNER'S LAPTOP (owner decision 2026-10-26): OAuth 2.0 PKCE in the laptop's own browser.

Run it in the laptop's interactive terminal; the owner completes the actual Spotify login and consent. Nothing here asks for a password, a client
secret or a token (a PKCE app has no secret), nothing is sent to chat, and tokens never leave this machine: they are stored under
~/.misumi-spotify/token.bin protected with Windows DPAPI (this user only). It does not touch the kiosk, the lab or the Odysseus home runtime.

    python spotify_laptop.py setup        # one time: register the loopback redirect on a Spotify app, save its (public) client id
    python spotify_laptop.py authorise    # opens the official Spotify consent page in this laptop's browser
    python spotify_laptop.py status       # read-only: account + plan, playback state
    python spotify_laptop.py devices      # read-only: available devices
    python spotify_laptop.py pause|resume|next|play "title"|volume 30 [--device NAME]    # explicit playback commands (through the governed controller)
    python spotify_laptop.py revoke       # forget the local tokens (also remove the app under spotify.com/account/apps)

Layout on the laptop (no repository checkout is needed): this file next to a src/ folder holding music_capability.py and spotify_binding.py.
"""

import argparse
import ctypes
import hmac
import html
import http.server
import json
import os
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from src import spotify_binding as sb  # noqa: E402
from src.music_capability import MusicController, ProviderError  # noqa: E402

HOME = os.path.join(os.path.expanduser("~"), ".misumi-spotify")
CONFIG_PATH = os.path.join(HOME, "config.json")
TOKEN_PATH = os.path.join(HOME, "token.bin")
DEFAULT_PORT = 18475
DASHBOARD_URL = "https://developer.spotify.com/dashboard"
WAIT_S = 300


# --------------------------------------------------------------------------------------------------------------------- DPAPI
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


_ENTROPY = b"misumi-spotify-v1"


def dpapi_protect(data: bytes) -> bytes:
    """Encrypt for the current Windows user only."""
    source, keep1 = _blob(data)
    entropy, keep2 = _blob(_ENTROPY)
    out = _Blob()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), "misumi-spotify", ctypes.byref(entropy), None, None, 0, ctypes.byref(out)):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def dpapi_unprotect(blob: bytes) -> bytes:
    source, keep1 = _blob(blob)
    entropy, keep2 = _blob(_ENTROPY)
    out = _Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0, ctypes.byref(out)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


# --------------------------------------------------------------------------------------------------------------------- config
def load_config(path=CONFIG_PATH):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    client = data.get("client_id") if isinstance(data, dict) else None
    port = data.get("port", DEFAULT_PORT) if isinstance(data, dict) else None
    if not isinstance(client, str) or not client.isalnum() or not isinstance(port, int) or isinstance(port, bool):
        return None
    return {"client_id": client, "port": port}


def save_config(client_id, port=DEFAULT_PORT, path=CONFIG_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"client_id": client_id, "port": port}, fh)       # the client id of a PKCE app is public, not a secret


def redirect_uri(port):
    return "http://127.0.0.1:%d/callback" % port


# --------------------------------------------------------------------------------------------------------------------- loopback callback
_PAGE = "<!doctype html><meta charset=utf-8><title>Misumi</title><body style='font:16px sans-serif;margin:3em'><h2>%s</h2><p>You can close this tab.</p>"


def wait_for_callback(port, timeout=WAIT_S, started=None, expected_state=None):
    """Listen on 127.0.0.1:PORT only and return the query of the first GET /callback that has a correct Host header AND (when given) the
    expected `state`. A forged or stray request gets a 400 and the listener keeps waiting, so it cannot cancel the real authorisation.

    The page shown never echoes the query. Accepted sockets time out after 5 s, so a half-sent request cannot hold the listener past its
    deadline. Raises OSError if the port cannot be bound (so the caller never opens consent with nobody listening) and TimeoutError if nothing
    valid arrives in `timeout` seconds."""
    result, ready = {}, threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        timeout = 5                            # per accepted connection

        def log_message(self, *args):          # no request logging: the query holds the authorisation code
            pass

        def do_GET(self):
            parts = urllib.parse.urlsplit(self.path)
            if parts.path != "/callback" or self.headers.get("Host") not in ("127.0.0.1:%d" % port, "[::1]:%d" % port):
                self.send_response(404)
                self.end_headers()
                return
            query = dict(urllib.parse.parse_qsl(parts.query))
            if expected_state is not None and not hmac.compare_digest(str(query.get("state", "")).encode("utf-8"), expected_state.encode("utf-8")):
                self.send_response(400)
                self.end_headers()
                return
            result.update(query)
            body = (_PAGE % html.escape("Spotify authorisation received")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            ready.set()

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 1.0
    if started is not None:
        started.set()
    deadline = time.monotonic() + timeout
    try:
        while not ready.is_set() and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not ready.is_set():
        raise TimeoutError("no authorisation arrived")
    return result


# --------------------------------------------------------------------------------------------------------------------- commands
def make_store():
    return sb.FileTokenStore(TOKEN_PATH, dpapi_protect, dpapi_unprotect)


def make_provider(cfg, store=None, http=None):
    http = http or sb.urllib_http                     # resolved per call, so a test (or a different transport) is honoured
    manager = sb.TokenManager(cfg["client_id"], store or make_store(), http)
    return sb.SpotifyProvider(manager, http), manager


def cmd_setup(args, out=print):
    port = args.port
    uri = redirect_uri(port)
    out("One-time Spotify app setup (about two minutes, in your own browser):")
    out("  1. The Spotify developer dashboard opens next. Log in and choose 'Create app'.")
    out("  2. Any name. Redirect URI (copied to your clipboard, paste it exactly): " + uri)
    out("  3. Tick 'Web API', save, then open the app's Settings and copy the Client ID (a public id, not a secret).")
    try:
        os.system("echo|set /p=%s|clip" % uri)
    except Exception:  # noqa: BLE001
        pass
    webbrowser.open(DASHBOARD_URL)
    client = (args.client_id or input("Paste the Client ID here (not the Client Secret): ")).strip()
    if not client.isalnum() or len(client) < 16:
        out("That does not look like a Spotify client id (letters and digits only). Nothing saved.")
        return 2
    save_config(client, port)
    out("Saved. Next: python spotify_laptop.py authorise")
    return 0


def cmd_authorise(args, out=print):
    cfg = load_config()
    if not cfg:
        out("Run 'setup' first.")
        return 2
    session = sb.AuthSession(cfg["client_id"], redirect_uri(cfg["port"]))
    started = threading.Event()
    holder = {}

    def listen():
        try:
            holder["query"] = wait_for_callback(cfg["port"], started=started, expected_state=session.state)
        except Exception as exc:  # noqa: BLE001
            holder["error"] = exc
            started.set()                       # wake the caller: it checks for the error before opening consent

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()
    if not started.wait(5) or "error" in holder:
        out("Cannot listen on 127.0.0.1:%d (%s); consent was NOT opened. Close whatever uses the port, or re-run setup with --port." % (
            cfg["port"], type(holder.get("error", OSError())).__name__))
        return 1
    out("Opening the official Spotify consent page in this browser. Log in and approve; I never see your password.")
    webbrowser.open(session.authorize_url())
    thread.join(WAIT_S + 10)
    if "query" not in holder:
        out("No authorisation received (" + type(holder.get("error", TimeoutError())).__name__ + "). Nothing stored.")
        return 1
    try:
        record = session.complete(holder["query"], sb.urllib_http)
    except sb.BindingError as exc:
        out("Authorisation refused: " + exc.code + ". Nothing stored.")
        return 1
    scratch = sb.MemoryTokenStore()
    scratch.save(record)
    provider, _ = make_provider(cfg, scratch)
    try:
        account = provider.account()                      # account verification before anything is kept
    except ProviderError as exc:
        out("Authorised, but the account could not be verified (" + exc.code + "). Nothing stored.")
        return 1
    record.user_id = account["id"]
    make_store().save(record)
    out("Authorised and verified: Spotify account %s... (plan: %s), scopes: %s." % (account["id"][:3], account["product"] or "unknown", ", ".join(sb.SCOPES)))
    out("NOT yet counted as connected: run 'status', 'devices', then one explicit command ('pause' or 'resume') to pass the live acceptance.")
    if account["product"] != "premium":
        out("Note: playback control needs Spotify Premium; read-only status will work, commands will be refused.")
    return 0


def _provider_or_exit(out):
    cfg = load_config()
    if not cfg:
        out("Run 'setup' first.")
        return None
    provider, manager = make_provider(cfg)
    if not manager.connected():
        out("Not connected. Run 'authorise'.")
        return None
    return provider


def cmd_status(args, out=print):
    provider = _provider_or_exit(out)
    if not provider:
        return 2
    try:
        account = provider.account()
        out("Account %s... plan %s" % (account["id"][:3], account["product"] or "unknown"))
        now = provider.now_playing()
        out("Nothing playing." if now is None or now.item is None else "%s: %s%s" % (
            "Playing" if now.playing else "Paused", now.item.title, " by " + now.item.artist if now.item.artist else ""))
    except ProviderError as exc:
        out("Spotify error: " + exc.code)
        return 1
    return 0


def cmd_devices(args, out=print):
    provider = _provider_or_exit(out)
    if not provider:
        return 2
    try:
        devices = provider.devices()
    except ProviderError as exc:
        out("Spotify error: " + exc.code)
        return 1
    out("%d device(s)" % len(devices))
    for device in devices:
        out("  %s%s" % (device.name, "  (active)" if device.active else ""))
    return 0


def cmd_command(args, out=print):
    provider = _provider_or_exit(out)
    if not provider:
        return 2
    action = {"volume": "volume"}.get(args.command, args.command)
    kwargs = {"device": args.device or ""}
    if action == "play":
        kwargs["query"] = " ".join(args.rest)
    elif action == "volume":
        kwargs["volume"] = int(args.rest[0]) if args.rest and args.rest[0].isdigit() else None
    result = MusicController(provider).handle(action, request_id="laptop-" + uuid.uuid4().hex[:12], explicit_command=True, **kwargs)
    out("%s: %s" % (result.status, result.message))
    if result.suggestion:
        out("  " + result.suggestion)
    return 0 if result.ok else 1


def cmd_revoke(args, out=print):
    make_store().clear()
    out("Local tokens removed. To end the grant at Spotify, remove the app at https://www.spotify.com/account/apps/.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--client-id", default="")
    for name in ("authorise", "status", "devices", "revoke"):
        sub.add_parser(name)
    for name in ("pause", "resume", "next", "play", "volume"):
        c = sub.add_parser(name)
        c.add_argument("rest", nargs="*")
        c.add_argument("--device", default="")
    args = ap.parse_args(argv)
    table = {"setup": cmd_setup, "authorise": cmd_authorise, "status": cmd_status, "devices": cmd_devices, "revoke": cmd_revoke}
    return table.get(args.command, cmd_command)(args)


if __name__ == "__main__":
    sys.exit(main())
