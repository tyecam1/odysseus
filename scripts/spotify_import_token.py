"""Install the owner's Spotify authorisation on the home runtime (owner-approved custody: home vault, 2026-10-26).

Reads ONE JSON document from stdin (the laptop helper pipes it over SSH; it is never put in an argument, a file or a log):
    {"client_id": "...", "access_token": "...", "refresh_token": "...", "expires_at": 1234567890.0, "scope": "...", "user_id": "..."}
and writes the public client id to <dir>/client.json and the tokens to <dir>/token.bin protected with Windows DPAPI. Output is a one-line,
secret-free summary. The scopes must be exactly the three playback scopes; anything else is refused and nothing is written.

    python scripts/spotify_import_token.py --dir C:\\path\\to\\data\\spotify [--scope user|machine]
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import spotify_binding as sb  # noqa: E402


def parse_payload(raw: str):
    try:
        data = json.loads(raw)
    except ValueError:
        raise SystemExit("import refused: stdin is not JSON")
    if not isinstance(data, dict):
        raise SystemExit("import refused: expected a JSON object")
    client = data.get("client_id")
    if not isinstance(client, str) or not client.isalnum() or len(client) < 16:
        raise SystemExit("import refused: bad client id")
    record = sb.TokenRecord.from_json(data)
    if record is None:
        raise SystemExit("import refused: token fields missing or malformed")
    if set(record.scope.split()) != set(sb.SCOPES):
        raise SystemExit("import refused: scopes must be exactly the three playback scopes")
    return client, record


def install(directory: str, client: str, record, protect, unprotect) -> None:
    os.makedirs(directory, exist_ok=True)
    sb.FileTokenStore(os.path.join(directory, "token.bin"), protect, unprotect).save(record)
    tmp = os.path.join(directory, "client.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"client_id": client}, fh)                   # the client id of a PKCE app is public
    os.replace(tmp, os.path.join(directory, "client.json"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", required=True)
    ap.add_argument("--scope", choices=("user", "machine"), default="user", help="DPAPI scope: the service account (user) or this machine")
    args = ap.parse_args(argv)
    client, record = parse_payload(sys.stdin.read())
    from src import windows_dpapi
    protect = lambda b: windows_dpapi.protect(b, args.scope)       # noqa: E731
    unprotect = lambda b: windows_dpapi.unprotect(b, args.scope)   # noqa: E731
    install(args.dir, client, record, protect, unprotect)
    check = sb.FileTokenStore(os.path.join(args.dir, "token.bin"), protect, unprotect).load()
    if check is None or check.refresh_token != record.refresh_token:
        raise SystemExit("import failed: the stored token does not read back")
    print("imported: account %s..., scopes ok, access token valid for %d s, dpapi scope %s" % (
        (record.user_id or "?")[:3], max(0, int(record.expires_at - time.time())), args.scope))
    return 0


if __name__ == "__main__":
    sys.exit(main())
