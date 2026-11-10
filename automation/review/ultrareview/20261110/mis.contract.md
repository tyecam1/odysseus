# Ultrareview contract - Misumi interface as a harness (2026-11-10)

This file is the reviewer's brief. It is part of a synthetic review branch and is never merged.

## How this diff was built
- `ultra/20261110-integ` = `main` plus normal merges of the open PRs (#107, #106, #104, #92; documentation only).
- The PR base rewinds the interface source files to their 2026-10-01 state, so the diff shows six weeks of merged interface work (PRs #58 to #105). Everything else in the repository is at its current state and is available as context.
- Tests and stylesheets are deliberately outside the diff to fit the size limit. Tests sit beside the sources (`interface-box/test_*.py`, `interface-box/test_*.mjs`, `scripts/test_*.py`). Read and run them; report behaviour they do not cover. `interface-box/bbc-route-b.css` is not under review.

## What this system is
Misumi is a household voice and screen interface running on a small kiosk box. `interface-box/server.py` serves the UI and proxies to the Odysseus backend on another host (`/agent`, route-explain, demo, transcripts). `misumi.html`, `bbc-route-b.js` and `bbc-pixel.js` are the kiosk UI. The `*-core.js` modules hold pure logic for capture, voice-activity segmentation, speech response, text-to-speech queueing, companions, the demonstration panel and the route inspector. Personas route requests to capabilities defined in `config/`. The owner's aim is for this interface to become the single front end for every Odysseus and research capability, plugged in like a harness rather than extended one endpoint at a time.

## Review priorities, in order
1. **Proxy and trust boundary in `server.py`.** The bearer token must only ever reach the configured upstream; check redirect handling, host pinning, header forwarding, path joining, request origin labelling (room speech must not gain owner privileges), error bodies that echo secrets, and timeouts on every upstream call.
2. **Voice pipeline correctness.** Capture, pre-roll, segmentation, speech-to-text hallucination filtering, sentence chunking and the TTS queue: lost or duplicated utterances, races between overlapping replies, queue starvation, state that survives a persona change, behaviour when the backend or TTS is slow or down. The microphone privacy control is a hardware mute; software state must never be presented as the privacy guarantee.
3. **Retention and deletion.** `transcript_bridge.py` and `forget_ambient.py`: text is retained indefinitely by owner decision, deletion must be complete and verifiable, writes must be atomic, and nothing may be written outside the configured store.
4. **Harness readiness.** Identify where a new backend capability currently requires edits in several places (server proxy route, HTML, `bbc-route-b.js`, persona config). Propose the smallest single registration point: one capability descriptor that drives proxying, UI panel and persona routing. Flag hard-coded endpoints, duplicated fetch and error handling, and duplicated state between the JS modules.
5. **UI function and usability defects.** Keyboard and focus handling (deck focus trap, drawer, window switcher), panels that overlap or cannot be dismissed, state lost on reload, service-worker caching that serves a stale UI after deploy, unhandled promise rejections, listeners or timers that leak in a kiosk that runs for weeks.
6. **Routing parity.** `scripts/route_dry_run.py` and `config/personas.yaml` against the backend routing contract: inputs where the dry run and the live route can disagree.

## Out of scope
Visual styling, art assets, documentation wording, and files outside the diff except as context.

## Reporting
For each finding give file and line, a concrete failing input or sequence, and the smallest fix. Mark consolidation findings separately from bugs. Prefer a few verified high-impact findings over many speculative ones.
