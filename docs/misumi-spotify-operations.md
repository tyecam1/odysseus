# Jin's Spotify capability: operation, guarantees and limits

Status 2026-10-27. Code: `src/music_commands.py` (parser), `src/music_runtime.py` (wiring), `src/music_capability.py` (governed controller), `src/spotify_binding.py` (PKCE, provider), `routes/misumi_routes.py` (`/misumi/respond` hook). Live acceptance of the combined behaviour is **not yet recorded** (see "Acceptance").

## Who may change playback
Writes (play, queue, pause, resume, skip, volume) need BOTH the `misumi:execute` API scope AND a request `origin` of `typed` or `voice_addressed`. The kiosk asserts the origin: push-to-talk and wake-word commands are `voice_addressed`; speech the speech responder answered without a wake word (the 25 s engaged window, "always" mode, a TV, a guest) is `voice_unaddressed`. A missing or unaddressed origin is refused with a spoken explanation; reads ("what's playing", "list my devices") still work. A request id refused for its origin stays refused if replayed as `typed`.
Limits: there is no speaker identification. A wake word spoken by a TV or a guest is an addressed request. Household consent to capture is not playback authority; hardware mute remains the privacy control. API callers (Dispatch, curl) must send `origin: "typed"`.

## What "done" means
- `done`: the read-back shows the requested state on the TARGET device (play/pause/resume, volume level). Skip is `done` only when the player shows on the target device. Queue has no read-back; it is `done` unless the player is reported on a different device.
- `done_unconfirmed`: sent, but the read-back is missing, lagging or on another device. It says so.
- `unknown_outcome`: a write was submitted and no answer proves whether it happened (lost response, exception after dispatch). The reply says it cannot tell and has not tried again. The request id is remembered, so a retry returns the same answer and never repeats the write.
- `error`: a typed refusal (auth, rate limit, no device, not found) or a failure before anything was sent; only these may say nothing changed.
Writes are never repeated automatically (not after a 401, 429 or 5xx). Reads make at most two extra attempts on a transient failure, inside a 30 s turn budget.

## Idempotency: the actual guarantee
Within ONE running process, one controller instance and the same request id, concurrent and repeated identical requests make at most one provider write; the same id with a different command is refused. This memory is in-process only. It is lost on a service restart, a rebuilt controller (a new client id), or if another worker serves the retry, and a client that sends no `request_id` gets a fresh one per attempt. Therefore this is **not durable at-most-once**. A durable ledger shared across workers is a known follow-up (Sol F4).

## Credentials
Token: `<data>/spotify/token.bin`, Windows DPAPI user scope, on the home service account only; `client.json` (public PKCE client id) and `devices.json` (default and aliases) beside it. Refresh is serialised by a cross-process lock with atomic replacement; `invalid_grant` clears the local token. Never keep a second copy (refresh-token rotation conflicts). To end the grant: remove the app at spotify.com/account/apps, then delete `token.bin`. To reconnect: authorise in the owner's laptop browser (`scripts/spotify_laptop.py`), then import with `scripts/spotify_import_token.py`.

## Deploy order and rollback
Deploy the Misumi box change that sends `origin` FIRST, then the Odysseus release. Roll back with the governed deploy scripts' previous release; `MISUMI_MUSIC=0` switches the capability off without a rollback.

## Known limitations (Sol review, gpt-6-sol, 2026-10-26)
- F4 no durable idempotency ledger (above).
- F5 a title ending in "on <device name or alias>" can be read as a device instruction when the search's first results do not show the exact title.
- F6 "could you play please" parses as a resume; "can you play music?" is treated as a request.
- F7 the idle-default device is chosen before the write; a device becoming active in that window can still be switched.
- F9 the token and client id are replaced separately on import, so a request during an account change can pair a new token with the old client id.
- F10 the 30 s turn budget is not enforced during token-lock wait and refresh.

## Acceptance
Done live (2026-10-26): play a precise track by artist on the laptop, pause, resume (read-back confirmed). Owed on the home host: the full matrix (ambiguous title, skip, queue, now playing, TV by name, absent device, bounded volume, repeated request id, expired token and transient failure by simulation, guest and unaddressed rejection, "play" in non-musical talk).
