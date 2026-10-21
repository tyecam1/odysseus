# B2 resilience drill - TTS failure and recovery (2026-10-06)

Target: a SCRATCH host-agent instance on port 4510 started from the canonical household clone (`host-agent/`, misumi main
lineage including the voice-profile abstraction); the production agent on :4500 was never addressed. Environment replicated
from the production launcher (`start-misumi-agent.ps1 -Tts`): Kokoro model and voices under
`C:\Users\User\odysseus\data\models\kokoro`, default voice `am_fenrir`, per-persona voices, qwen3:8b brain. Script:
`evals/misumi-resilience/drill-tts.ps1`. The first attempt used the clone's own (absent) model path and reported
`missing-kokoro-model` in every phase - a drill-environment error, not a finding; the corrected run follows.

| Phase | What was done | Observed |
| --- | --- | --- |
| D1 healthy | `/respond` persona sanji + `/tts` | text ok; `audio_url` present; voice `bm_lewis` (the profile binding); WAV 163,884 bytes fetched; `/tts` 200 in 1,898 ms |
| D2 broken | agent restarted with a missing Kokoro model path | `/respond` 200 with text in 620 ms, **no `audio_url`**; `tts_error=missing-kokoro-model` visible only in debug mode; `/tts` **503** `tts-unavailable` in 12 ms |
| D3 recovered | agent restarted with the good config (a real process restart) | audio again: voice `bm_lewis`, WAV 167,980 bytes, `/tts` 200 in 1,885 ms |

Findings:

1. The text-first design holds: a TTS outage never blocks or delays the text reply, and recovery needs only the restart.
2. **Gap (fixed in misumi PR #64):** a failed voice and a deliberately disabled voice looked identical to the box (no
   `audio_url`), and the kiosk swallowed a non-OK `/tts`, timeouts and network errors - a broken voice was silent to the
   household. The agent now reports `tts_status` (`ok` / `disabled` / `unavailable`, no error detail) and the kiosk labels the
   cases (`voice off` / `unavailable` / `timed out` / `unreachable`).
3. The production agent (:4500) was still running pre-profile code in memory (its `/health` lacked `voice_profiles`).
   host-agent changes take effect only after the agent is restarted via the launcher (`-Stop`, then start): the launcher's
   idempotence check only restarts on a TTS voice mismatch.

Not tested here (household-gated until the kiosk bridge returns): audibility, perceived latency in the room, speaker
correctness, output-device change, network-loss behaviour of the real kiosk.

## Raw output

```
D0-health {"has_voice_profiles":true,"provider":"kokoro","tts_enabled":true,"kokoro_model_configured":true}
D1-healthy {"tts_ms":1898,"tts_status":200,"respond_ms":5859,"audio_file_bytes":163884,"respond_audio_url":true,"respond_tts_error":null,"respond_status":200,"respond_has_text":true,"respond_voice":"bm_lewis","tts_detail":null}
agent-stopped listeners=0
D2-tts-broken {"tts_ms":12,"tts_status":503,"respond_ms":620,"audio_file_bytes":null,"respond_audio_url":false,"respond_tts_error":"missing-kokoro-model","respond_status":200,"respond_has_text":true,"respond_voice":null,"tts_detail":"{\"error\": \"tts-unavailable\"}"}
agent-stopped listeners=0
D3-recovered-after-restart {"tts_ms":1885,"tts_status":200,"respond_ms":3597,"audio_file_bytes":167980,"respond_audio_url":true,"respond_tts_error":null,"respond_status":200,"respond_has_text":true,"respond_voice":"bm_lewis","tts_detail":null}
agent-stopped listeners=0
DONE (production agent on :4500 untouched)
```
