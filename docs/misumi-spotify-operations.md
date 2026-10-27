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

Deployed and verified 2026-10-27: Odysseus home runtime on release `f5b032cdc05e` (#189, #190, #192, plus the unrelated #191 research fix that was on dev), health 200, previous releases retained for rollback; Misumi interface box on `cd4217877e96` (sends `origin`, `/agent` pinned to the configured upstream).

Live matrix on the home runtime (in-process harness under the service account; statuses and ids only), 16 of 19 as expected:

- Passed: device and now-playing reads; "play a game of chess" and a conversation mentioning a song ignored; an unaddressed command and a write with no origin refused with no provider write; an unaddressed read allowed; an unknown device named gives a clarification and no write; an ambiguous title ("Blue") asks which one; pause, resume, skip and queue; a repeated request id made exactly one provider write; volume above the safe limit refused.
- Not as expected, and why:
  1. "play ... on the laptop": **unavailable test condition**. The laptop's Spotify app was not open, so the device was not listed; the clarification and absence of a write is the correct behaviour.
  2. "volume 25" and 3. the final "pause": **device/provider restriction**. Spotify answered 403 for the Pixel 8 (a phone refuses remote volume changes, and a pause when already paused). The message wrongly blamed the account plan; reworded in #192.
  None was an implementation failure. Writes with no device go to the ACTIVE device, which was the phone; that is by design.
- Found and fixed by this run: `now_playing` read an endpoint that never names the device, so after #189's exact-device rule every confirmation read as `done_unconfirmed` (#192 reads `/me/player`, and an active player with no item still reports its device).

**Pending (not run): the post-#192 confirmation on a real player.** At the last check (2026-10-27) Spotify listed only an idle Fire TV Stick; no laptop or phone player was available, and no substitute was used. Resumption trigger: the Spotify app is open on the laptop. Then run once: record the target device id and playback state; one addressed command; expect `done` with that device and exactly one provider write; pause and resume once with `done` for each; restore the original state. Until that is recorded, "real, correctly addressed playback with target-device read-back on #192" is NOT evidenced, and the music work item stays open.
