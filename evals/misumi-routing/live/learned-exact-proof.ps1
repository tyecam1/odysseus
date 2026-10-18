<#
.SYNOPSIS
  Live proof (scratch :1420 instance of a v0.2 release, scratch stores): a learned routing revision keeps EXACT keyword_present
  semantics under routing contract v0.2. A durable instruction ("for cleaning questions use Jin from now on") is promoted; the exact cue
  applies (learned route, base route recorded), a stem-only match ("cleaned") does NOT fire it while v0.2 still routes that prompt to the
  base persona by stem, restart persistence holds, and rollback restores the v0.2 base route. Token from the user env, never printed.
#>
param([string]$Short = 'REPLACE_SHORT')
$ErrorActionPreference = 'Continue'
$token = [Environment]::GetEnvironmentVariable('ODYSSEUS_API_TOKEN', 'User')
if (-not $token) { Write-Error 'ODYSSEUS_API_TOKEN not present'; exit 2 }
$headers = @{ Authorization = "Bearer $token" }
$REL = "C:\Users\User\odysseus-releases\$Short"
$scratch = "C:\Users\User\odysseus-releases\learned-exact-$Short"
$t = 'http://127.0.0.1:1420/misumi'
$script:proc = $null
function Body($o) { $b = [Text.Encoding]::UTF8.GetBytes(($o | ConvertTo-Json -Compress -Depth 6)); return ,$b }
function Post([string]$uri, $payload) {
  try { $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body (Body $payload) -TimeoutSec 120
    return [pscustomobject]@{ status = [int]$r.StatusCode; json = ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json) } }
  catch { return [pscustomobject]@{ status = 0; json = $_.Exception.Message } }
}
function Auto([string]$prompt, [string]$sid, [bool]$persist = $false) {
  Post "$t/respond" @{ prompt = $prompt; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = 'auto'; session_id = $sid; persist_turn = $persist; retention_mode = 'off'; history_mode = 'off' }
}
function Show([string]$label, $r) { Write-Host ("$label " + (@{ persona = $r.json.persona; method = $r.json.routing.method; reasons = $r.json.routing.reasons; base = $r.json.routing.base_selected; learned = [bool]$r.json.routing.learned } | ConvertTo-Json -Compress)) }
function Start-Scratch {
  $env:MISUMI_ROUTING_STATE_ROOT = "$scratch\routing"; $env:MISUMI_PERSONA_STATE_ROOT = "$scratch\persona"
  $a = @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File', "$REL\scripts\windows\odysseus-host.ps1",
    '-Action','Run','-SourceRoot',$REL,'-DataRoot','C:\Users\User\odysseus-releases\sbs-data-8f7803acb2','-BindHost','127.0.0.1','-Port','1420',
    '-TaskName','Odysseus-Misumi-sbs','-HouseholdRoot','C:\Users\User\Documents\flat-knowledgebase','-ObsidianPhDRoot','C:\Users\User\Documents\PhD\notes',
    '-ModelHealthUrl','http://127.0.0.1:11434/api/tags','-InterfaceHealthUrl','http://192.168.4.37:8770/health',
    '-ModelUrl','http://127.0.0.1:11434/v1','-Model','qwen3:8b','-RestartDelaySeconds','10','-TranscriptRuntime')
  $script:proc = Start-Process powershell -ArgumentList $a -WindowStyle Hidden -PassThru
  foreach ($i in 1..30) { Start-Sleep -Seconds 2
    try { if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:1420/api/health' -TimeoutSec 3).StatusCode -eq 200) { return $true } } catch { } }
  return $false
}
function Stop-Scratch { if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null }; Start-Sleep -Seconds 3 }

if (Test-Path $scratch) { Remove-Item -Recurse -Force $scratch }
New-Item -ItemType Directory -Force -Path "$scratch\routing", "$scratch\persona" | Out-Null
if (-not (Start-Scratch)) { 'FATAL scratch instance never became healthy'; Stop-Scratch; exit 2 }
"scratch-up release=$Short (routing contract v0.2 is the default)"
Show 'L1-base-exact' (Auto 'Check the cleaning rota' 'l1')
Show 'L2-base-stem-only' (Auto 'Who cleaned the kitchen?' 'l2')
$d = Auto 'For cleaning questions, from now on use Jin.' 'l3' $true
Write-Host ("L3-durable-instruction " + (@{ note = $d.json.routing_adaptation } | ConvertTo-Json -Compress -Depth 6))
$revId = $d.json.routing_adaptation.promotion.revision_id
Show 'L4-exact-cue-fires-learned' (Auto 'Check the cleaning rota' 'l4')
Show 'L5-stem-only-does-NOT-fire' (Auto 'Who cleaned the kitchen?' 'l5')
Show 'L6-other-cue-unaffected' (Auto 'Diagnose this finance anomaly' 'l6')
'L7-restarting'; Stop-Scratch
if (-not (Start-Scratch)) { 'FATAL restart failed'; Stop-Scratch; exit 2 }
Show 'L8-after-restart-exact-cue' (Auto 'Check the cleaning rota' 'l8')
$rb = Post "$t/routing/revisions/$revId/rollback" @{ reason = 'learned-exact proof' }
"L9-rollback status=$($rb.status)"
Show 'L10-after-rollback' (Auto 'Check the cleaning rota' 'l10')
Show 'L11-after-rollback-stem-only' (Auto 'Who cleaned the kitchen?' 'l11')
Stop-Scratch
"DONE (household stores untouched)"
