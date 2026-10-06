# Production cutover to release b51db41f9a and real-path proof (2026-10-06)

Staged path as in earlier applications: stage 1 (fresh clone from `tyecam1/odysseus`, pinned venv), stage 2 (side-by-side on
`:1420`, production untouched: health 200, misumi health 200, `/api/ready` 401 without a token, port 1420 released, `:420`
still up), stage 3 (re-install the scheduled task `Odysseus-Misumi` at the new release, stop, start; health 200 after ~6 s,
one listener on `:420`, task Running). Rollback: re-run the install for the previous release `ce8d353a8f` (stage scripts and
logs `stage[123]-b51db41f9a.log` are on the host).

The release carries odysseus #99-#108: persona-state adaptation (#103), team formation (#104, #107), conversational
ratification (#105), the durable-instruction fix (#102), the -09 evidence (no runtime change) and the measured `brief`
wording (#108). The persona-state and team features have kill switches (`MISUMI_PERSONA_STATE=0`, `MISUMI_CONSULT=0`).

The host agent (`:4500`) was then restarted through its launcher (`-Stop`, then `-Tts -NoStt`) so it loads the
voice-profile and `tts_status` code: before, `/health` lacked `voice_profiles`; after, it lists the 12 profiles, Kokoro is
configured, `/tts` for sanji synthesised `bm_lewis`, and `/respond` reports `tts_status: ok`. One non-fatal quirk: the launcher's
own `git pull` cannot authenticate over SSH (the clone was already current; the auto-pull task owns updates).

Real-path proof on the DEPLOYED `:420` (script `prod-check.ps1`, token from the host user env, never printed; persistence and
retention off, so the household stores were not mutated): all 12 deterministic routing fixtures pass through
`/misumi/respond` (`persona_source: auto`, `routing-contract-v0.1`); a turn request ("keep it shorter please") applied
(`persona_state.effective: true`, 25 words) and left the persona-state store at 0 candidates / 0 active; a justified team formed
(misato lead, sanji named support, status ok, 1.45 s, explicit handover); the routing store still holds exactly the two earlier
`-07` demo candidates and no active revisions.

## Raw output - agent restart

```
== before
has voice_profiles: False; tts enabled: True
6f0795a Merge pull request #64 from tyecam1/programme/b2-tts-degraded-state
== stop
stopped agent pid 29388
== start (as the Misumi-Agent-Stack task does)
ssh : powershell : fatal: could not read Username for 'https://github.com': No such file or directory
At line:4 char:1
+ ssh @h User@100.105.34.37 'powershell -NoProfile -ExecutionPolicy Byp ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (powershell : fa...le or directory:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
At C:\Users\User\restart-agent.ps1:10 char:1
+ powershell -NoProfile -ExecutionPolicy Bypass -File $launcher -Tts -N ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (fatal: could no...le or directory:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
agent spawn rc=0 pid=7340
agent healthy: {"status":"ok","node":"misumi-agent","version":"MisumiAgent/0.8","host":"DESKTOP-IN7O23D","brain":{"backend":"ollama","model":"qwen3:8b"},"tts":{"enabled":true,"provider":"kokoro","voice":"am_fenrir","format":"wav","audio_dir":"C:\\Users\\User\\odysseus\\data\\audio","kokoro_model_configured":true,"piper_model_configured":false,"persona_voices":{"aoteru":"bm_george","lelouch":"am_onyx","kurisu":"af_kore","misato":"af_nova","jin":"am_echo","erwin":"bm_daniel","l":"am_puck","ginko":"bm_fable","sanji":"bm_lewis","ichigo":"am_adam","giorno":"am_liam","kino":"af_sky"},"voice_profiles":{"aoteru":{"register":"low","pace":1.0,"character":"mature, distinctive British lead"},"lelouch":{"register":"low","pace":1.0,"character":"controlled command voice"},"kurisu":{"register":"mid","pace":1.0,"character":"precise, analytical"},"misato":{"register":"mid","pace":1.0,"character":"warmer caretaker energy"},"jin":{"register":"mid","pace":1.0,"character":"calm selector, record-shop tone"},"erwin":{"register":"low","pace":1.0,"character":"authoritative field-commander tone"},"l":{"register":"mid","pace":1.0,"character":"dry, unusual, slightly off-centre"},"ginko":{"register":"mid","pace":1.0,"character":"quiet narrator, naturalist"},"sanji":{"register":"mid","pace":1.0,"character":"warm chef, a little theatrical"},"ichigo":{"register":"mid","pace":1.0,"character":"direct guardian voice"},"giorno":{"register":"mid","pace":1.0,"character":"smooth creative voice"},"kino":{"register":"mid","pace":1.0,"character":"calm, neutral traveler voice"}},"endpoint":"/tts","max_chars":900},"personas":["aoteru","erwin","ginko","giorno","ichigo","jin","kino","kurisu","l","lelouch","misato","sanji"],"capabilities":{"available":true,"groups":[{"id":"household-data-tools","owner":"lelouch","status":"ratified"},{"id":"shopping-list","owner":"sanji","status":"ratified"},{"id":"records-collector","owner":"jin","status":"ratified"},{"id":"weather-collector","owner":"ginko","status":"ratified"},{"id":"recurring-runner","owner":"aoteru","status":"ratified"},{"id":"persona-evolution","owner":"giorno","status":"ratified"},{"id":"host-operations","owner":"lelouch","status":"ratified"},{"id":"fcc-sandbox-control","owner":"lelouch","status":"ratified"},{"id":"model-routing-diagnostics","owner":"erwin","status":"ratified"},{"id":"repository-validation","owner":"kurisu","status":"ratified"},{"id":"host-agent-runtime","owner":"lelouch","status":"ratified"},{"id":"interface-runtime","owner":"lelouch","status":"ratified"},{"id":"interface-assets-and-validation","owner":"aoteru","status":"ratified"},{"id":"planner","owner":"lelouch","status":"ratified"},{"id":"memory-index","owner":"kurisu","status":"ratified"},{"id":"memory-policy-and-context-checks","owner":"kurisu","status":"ratified"},{"id":"consolidation","owner":"kurisu","status":"ratified"},{"id":"finance-forecast","owner":"l","status":"ratified"},{"id":"house-style","owner":"aoteru","status":"ratified"},{"id":"skill-packaging","owner":"kurisu","status":"ratified"},{"id":"vault-bridge","owner":"kino","status":"ratified"},{"id":"profile-ingest","owner":"kino","status":"ratified"}],"summary":{"total":22,"ratified":22}},"head_persona":"aoteru","default_persona":"aoteru"}
== after
status=ok version=MisumiAgent/0.8 tts_enabled=True provider=kokoro kokoro_configured=True has_voice_profiles=True
== tts probe (writes one small audio file)
tts status=200 voice=bm_lewis provider=kokoro has_audio_url=True
== respond probe (tts_status field)
respond status=200 source=scripted tts_status=ok voice=am_echo
```

## Raw output - production check

```
== release / health
"C:\Users\User\odysseus-releases\b51db41f9a\venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 420
{"status":"ok","node":"odysseus-misumi","source":"odysseus","phase":"A","auth_required_for_actions":true,"household_reachable":true}
== household stores on production are READ-ONLY here
persona-state: status=200 candidates=0 active=0
routing: status=200 candidates=2 active=0  (the two -07 demo candidates from before are expected)
== 12 deterministic routing fixtures through the deployed /misumi/respond (persist off, retention off)
Review priorities and risk for next month -> erwin method=routing-contract-v0.1 PASS
Draft the implementation workflow -> lelouch method=routing-contract-v0.1 PASS
Check the cleaning rota -> misato method=routing-contract-v0.1 PASS
Archive this transcript as evidence -> kurisu method=routing-contract-v0.1 PASS
Diagnose this finance anomaly -> l method=routing-contract-v0.1 PASS
Plan plant watering around pests -> ginko method=routing-contract-v0.1 PASS
Make meals from food stock -> sanji method=routing-contract-v0.1 PASS
Suggest records for listening -> jin method=routing-contract-v0.1 PASS
Close this urgent stalled task -> ichigo method=routing-contract-v0.1 PASS
Propose evolution experiments -> giorno method=routing-contract-v0.1 PASS
Please help me think this through -> aoteru method=routing-contract-v0.1 PASS
Set a Level 5 food standard -> aoteru method=routing-contract-v0.1 PASS
fixtures: 12/12
== a turn request on the deployed path (persist off: shapes this turn only, nothing stored)
source=model words=25 persona_state={"applied":[{"dimension":"response_depth","value":"brief","source":"turn_request","matched":"shorter"}],"effective":true,"captured":null}
persona-state store after: candidates=0 active=0 (must still be 0 / 0)
== a justified team on the deployed path (persist off)
source=model team={"lead":"misato","decision":"team","reasons":[],"excluded":[],"supports":[{"persona":"sanji","kind":"named","evidence":{"named_at":28,"intents":[]},"edge":true,"status":"ok","raised_risk":false,"latency_ms":1452,"contribution_chars":369}],"handovers":[{"from":"misato","to":"sanji","returned_to":"misato","purpose":"analyse from the chef perspective"}]}
```
