<#
.SYNOPSIS
  Application -08b(d)/-12 live proof: conversational ratification on a labelled side-by-side :1420 instance of a release
  with SCRATCH routing + persona-state stores (household stores untouched). Real model, real HTTP, user env token (never printed).
  A: offer -> bare "yes" -> style applied (user_instruction authority, cites the offer) -> "undo that" -> gone.
  B: routing candidate offered -> "no" -> rejected, route unchanged.
  C: silence / moving on / embedded yes / "later" never promote.
#>
param([string]$Short = 'REPLACE_SHORT')
$ErrorActionPreference = 'Continue'
$token = [Environment]::GetEnvironmentVariable('ODYSSEUS_API_TOKEN', 'User')
if (-not $token) { Write-Error 'ODYSSEUS_API_TOKEN not present'; exit 2 }
$headers = @{ Authorization = "Bearer $token" }
$REL = "C:\Users\User\odysseus-releases\$Short"
$scratch = "C:\Users\User\odysseus-releases\dialogue-scratch-12-$Short"
$t = 'http://127.0.0.1:1420/misumi'
$script:proc = $null

function Body($o) { $b = [Text.Encoding]::UTF8.GetBytes(($o | ConvertTo-Json -Compress -Depth 6)); return ,$b }
function J($r) { [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json }
function Show([string]$label, $obj) { Write-Host ("$label " + ($obj | ConvertTo-Json -Compress -Depth 7)) }
function Call([string]$method, [string]$uri, $payload) {
  try {
    if ($null -ne $payload) { $r = Invoke-WebRequest -UseBasicParsing -Method $method -Uri $uri -Headers $headers -ContentType 'application/json' -Body (Body $payload) -TimeoutSec 120 }
    else { $r = Invoke-WebRequest -UseBasicParsing -Method $method -Uri $uri -Headers $headers -TimeoutSec 60 }
    return [pscustomobject]@{ status = [int]$r.StatusCode; json = (J $r) }
  } catch {
    $detail = $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $detail = $_.ErrorDetails.Message }
    return [pscustomobject]@{ status = 0; json = $detail }
  }
}
function Say([string]$prompt, [string]$persona, [string]$sid, [bool]$persist = $true) {
  Call 'POST' "$t/respond" @{ prompt = $prompt; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = $persona
    session_id = $sid; persist_turn = $persist; retention_mode = 'off'; history_mode = 'off' }
}
function Brief($r) { @{ status = $r.status; source = $r.json.source; persona = $r.json.persona; offer = $r.json.ratification_offer; ratification = $r.json.ratification
    persona_state = $r.json.persona_state; text = ([string]$r.json.text).Substring(0, [Math]::Min(260, ([string]$r.json.text).Length)) } }
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
function Stop-Scratch { if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null }; Start-Sleep -Seconds 3
  "scratch-stopped listeners=$(@(Get-NetTCPConnection -LocalPort 1420 -State Listen -ErrorAction SilentlyContinue).Count)" }
function State { $x = (Call 'GET' "$t/persona-state" $null).json; $y = (Call 'GET' "$t/routing/candidates" $null).json
  @{ persona_state_active = @($x.active_revisions | ForEach-Object { "$($_.persona)/$($_.dimension)=$($_.value) auth=$($_.authorisation.type)" })
     persona_state_candidates = @($x.candidates | ForEach-Object { "$($_.persona)/$($_.dimension)=$($_.proposed_value):$($_.status)/$($_.awaiting)" })
     routing_active = @($y.active_revisions | ForEach-Object { "$($_.cue -join '+')->$($_.persona) auth=$($_.authorisation.type)" })
     routing_candidates = @($y.candidates | ForEach-Object { "$($_.cue -join '+')->$($_.proposed_persona):$($_.status)/$($_.awaiting)" }) } }

if (Test-Path $scratch) { Remove-Item -Recurse -Force $scratch }
New-Item -ItemType Directory -Force -Path "$scratch\routing", "$scratch\persona" | Out-Null
if (-not (Start-Scratch)) { "FATAL scratch instance never became healthy"; Stop-Scratch; exit 2 }
"scratch-up release=$Short"

# ---------- A: offer -> yes -> applied -> undo ----------
$r1 = Say 'That was too long.' 'misato' 'a-1'; Show 'A1-first-correction' (Brief $r1)
$r2 = Say 'That was too long.' 'misato' 'a-2'; Show 'A2-second-correction' (Brief $r2)
$r3 = Say 'That was too long.' 'misato' 'a-3'; Show 'A3-third-correction-offer-appended' (Brief $r3)
Show 'A3b-state-before-answer' (State)
$yes = Say 'yes' 'misato' 'a-3'; Show 'A4-yes' (Brief $yes)
Show 'A4b-state-after-yes' (State)
$after = Say 'Explain how a rainbow forms.' 'misato' 'a-4' $false; Show 'A5-style-applied' (Brief $after)
$undo = Say 'undo that' 'misato' 'a-3'; Show 'A6-undo' (Brief $undo)
Show 'A6b-state-after-undo' (State)
$gone = Say 'Explain how a rainbow forms.' 'misato' 'a-4' $false; Show 'A7-style-gone' (Brief $gone)

# ---------- B: routing candidate offered -> no ----------
$o = $null
foreach ($s in 1..3) { $null = Say 'Check the cleaning rota' 'auto' "b-$s"; $o = Say "no, ask Jin about the cleaning rota ($s)" 'jin' "b-$s" }
Show 'B1-routing-offer-on-the-turn-that-made-it-eligible' (Brief $o)
$no = Say 'no' 'auto' 'b-3'; Show 'B2-no' (Brief $no)
Show 'B2b-state' (State)
$route = Say 'Check the cleaning rota' 'auto' 'b-after' $false; Show 'B3-route-unchanged' @{ persona = $route.json.persona; method = $route.json.routing.method }

# ---------- C: silence never promotes ----------
foreach ($s in 1..3) { $null = Say 'That was too technical.' 'misato' "c-$s" }
Show 'C1-offer-pending' @{ state = (State).persona_state_candidates }
$moved = Say 'What is a good name for a cat?' 'misato' 'c-3'; Show 'C2-moved-on' (Brief $moved)
$late = Say 'yes' 'misato' 'c-3'; Show 'C3-late-yes-ratifies-nothing' (Brief $late)
Show 'C3b-state' (State)
$emb = Say 'yes but keep the answers long' 'misato' 'c-9'; Show 'C4-embedded-yes' (Brief $emb)
Show 'C4b-state' (State)

Stop-Scratch
"DONE (household stores untouched)"
