<#
.SYNOPSIS
  Application -08b live proofs on a labelled side-by-side :1420 instance with a SCRATCH routing-state
  root (household store on :420 is never touched). Token: user env, never printed.
  (a) silence/no-ratification does not promote, across a real process restart
  (b) contradictory evidence is handled and blocks promotion
  (c) reject path: terminal, re-reject refused, promote-after-reject refused, evidence preserved
#>
$ErrorActionPreference = 'Continue'
$token = [Environment]::GetEnvironmentVariable('ODYSSEUS_API_TOKEN', 'User')
if (-not $token) { Write-Error 'ODYSSEUS_API_TOKEN not present'; exit 2 }
$headers = @{ Authorization = "Bearer $token" }
$REL = 'C:\Users\User\odysseus-releases\ce8d353a8f'
$scratch = 'C:\Users\User\odysseus-releases\routing-scratch-08b'
$t = 'http://127.0.0.1:1420/misumi'
$script:proc = $null

function Body($o) { $b = [Text.Encoding]::UTF8.GetBytes(($o | ConvertTo-Json -Compress)); return ,$b }
function J($r) { [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json }
function Show([string]$label, $obj) { "$label " + ($obj | ConvertTo-Json -Compress -Depth 7) }
function Call([string]$method, [string]$uri, $payload) {
  try {
    if ($null -ne $payload) {
      $r = Invoke-WebRequest -UseBasicParsing -Method $method -Uri $uri -Headers $headers -ContentType 'application/json' -Body (Body $payload) -TimeoutSec 30
    } else {
      $r = Invoke-WebRequest -UseBasicParsing -Method $method -Uri $uri -Headers $headers -TimeoutSec 30
    }
    return [pscustomobject]@{ status = [int]$r.StatusCode; json = (J $r) }
  } catch {
    $code = 0; $detail = $_.Exception.Message
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $detail = $_.ErrorDetails.Message }
    return [pscustomobject]@{ status = $code; json = $detail }
  }
}
function Respond([string]$prompt, [string]$persona, [string]$sid, [bool]$persist) {
  $ret = if ($persist) { 'auto' } else { 'off' }
  Call 'POST' "$t/respond" @{ prompt = $prompt; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = $persona
    session_id = $sid; persist_turn = $persist; retention_mode = $ret; history_mode = $ret }
}
function Start-Scratch {
  $env:MISUMI_ROUTING_STATE_ROOT = $scratch
  $a = @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden',
    '-File', "$REL\scripts\windows\odysseus-host.ps1",
    '-Action','Run','-SourceRoot',$REL,'-DataRoot','C:\Users\User\odysseus-releases\sbs-data-8f7803acb2',
    '-BindHost','127.0.0.1','-Port','1420','-TaskName','Odysseus-Misumi-sbs',
    '-HouseholdRoot','C:\Users\User\Documents\flat-knowledgebase',
    '-ObsidianPhDRoot','C:\Users\User\Documents\PhD\notes',
    '-ModelHealthUrl','http://127.0.0.1:11434/api/tags',
    '-InterfaceHealthUrl','http://192.168.4.37:8770/health',
    '-ModelUrl','http://127.0.0.1:11434/v1','-Model','qwen3:8b',
    '-RestartDelaySeconds','10','-TranscriptRuntime')
  $script:proc = Start-Process powershell -ArgumentList $a -WindowStyle Hidden -PassThru
  foreach ($i in 1..25) {
    Start-Sleep -Seconds 2
    try { if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:1420/api/health' -TimeoutSec 3).StatusCode -eq 200) { return $true } } catch { }
  }
  return $false
}
function Stop-Scratch {
  if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null }
  Start-Sleep -Seconds 3
  $left = @(Get-NetTCPConnection -LocalPort 1420 -State Listen -ErrorAction SilentlyContinue)
  "scratch-stopped listeners=$($left.Count)"
}
function Seed-Corrections([string]$autoPrompt, [string]$corrFmt, [string]$persona, [string]$tag, [int]$n) {
  foreach ($s in 1..$n) {
    $sid = "$tag-$s"
    $null = Respond $autoPrompt 'auto' $sid $true
    $null = Respond ($corrFmt -f $s) $persona $sid $true
  }
}
function Cand-Summary($c) { [pscustomobject]@{ id = $c.candidate_id; cue = ($c.cue -join '+'); status = $c.status; awaiting = $c.awaiting; to = $c.proposed_persona; base = $c.base_persona; corr = $c.confidence.corrections } }

if (Test-Path $scratch) { Remove-Item -Recurse -Force $scratch }
New-Item -ItemType Directory -Force -Path $scratch | Out-Null
if (-not (Start-Scratch)) { "FATAL scratch instance never became healthy"; Stop-Scratch; exit 2 }
"scratch-up root=$scratch"

# ---------- (a) silence does not promote, across restart ----------
Seed-Corrections 'Check the cleaning rota' 'no, ask Jin about the cleaning rota ({0})' 'jin' 'sil' 3
$c1 = (Call 'GET' "$t/routing/candidates" $null).json.candidates | Where-Object { $_.base_persona -eq 'misato' -and $_.proposed_persona -eq 'jin' } | Select-Object -First 1
Show 'A1-eligible-before-restart' (Cand-Summary $c1)
$ev1 = (Call 'GET' "$t/routing/candidates" $null).json
"A1-active-revisions-before=$(@($ev1.active_revisions).Count)"
"A2-restarting"; Stop-Scratch | Out-Null
if (-not (Start-Scratch)) { "FATAL scratch restart unhealthy"; Stop-Scratch; exit 2 }
# unrelated + related traffic with NO ratification act
$null = Respond 'What should we have for dinner?' 'auto' 'sil-x' $false
$route = Respond 'Check the cleaning rota' 'auto' 'sil-y' $false
Show 'A3-route-after-restart-no-ratification' @{ persona = $route.json.persona; source = $route.json.persona_source; method = $route.json.routing.method; reasons = $route.json.routing.reasons }
$after = (Call 'GET' "$t/routing/candidates" $null).json
$c1b = $after.candidates | Where-Object { $_.candidate_id -eq $c1.candidate_id }
Show 'A4-candidate-after-restart' (Cand-Summary $c1b)
"A4-active-revisions-after=$(@($after.active_revisions).Count)"

# ---------- (b) contradictory evidence ----------
Seed-Corrections 'Suggest records for listening' 'no, ask Misato about the records for listening ({0})' 'misato' 'con' 3
$cb = (Call 'GET' "$t/routing/candidates" $null).json.candidates | Where-Object { $_.base_persona -eq 'jin' -and $_.proposed_persona -eq 'misato' } | Select-Object -First 1
Show 'B1-eligible' (Cand-Summary $cb)
$null = Respond 'Suggest records for listening' 'auto' 'con-z' $true
$null = Respond 'no, ask Erwin about the records for listening' 'erwin' 'con-z' $true
$cb2 = (Call 'GET' "$t/routing/candidates" $null).json.candidates | Where-Object { $_.candidate_id -eq $cb.candidate_id }
Show 'B2-after-contradiction' (Cand-Summary $cb2)
"B2-contradicting-count=$(@($cb2.contradicting_evidence).Count)"
$pr = Call 'POST' "$t/routing/candidates/$($cb.candidate_id)/promote" @{ reason = 'attempt on contradicted candidate' }
Show 'B3-promote-contradicted' @{ status = $pr.status; detail = $pr.json }

# ---------- (c) reject path ----------
Seed-Corrections 'Plan plant watering around pests' 'no, ask Sanji about the plant watering pests ({0})' 'sanji' 'rej' 3
$cc = (Call 'GET' "$t/routing/candidates" $null).json.candidates | Where-Object { $_.base_persona -eq 'ginko' -and $_.proposed_persona -eq 'sanji' } | Select-Object -First 1
Show 'C1-eligible' (Cand-Summary $cc)
$evBefore = @((Call 'GET' "$t/routing/candidates" $null).json.candidates | Where-Object { $_.candidate_id -eq $cc.candidate_id }).supporting_evidence.Count
$rj = Call 'POST' "$t/routing/candidates/$($cc.candidate_id)/reject" @{ reason = 'operator rejects (scratch proof)' }
Show 'C2-reject' @{ status = $rj.status; json = $rj.json }
$rj2 = Call 'POST' "$t/routing/candidates/$($cc.candidate_id)/reject" @{ reason = 'second reject' }
Show 'C3-reject-again' @{ status = $rj2.status; detail = $rj2.json }
$pj = Call 'POST' "$t/routing/candidates/$($cc.candidate_id)/promote" @{ reason = 'promote after reject' }
Show 'C4-promote-after-reject' @{ status = $pj.status; detail = $pj.json }
$ccAfter = (Call 'GET' "$t/routing/candidates" $null).json.candidates | Where-Object { $_.candidate_id -eq $cc.candidate_id }
Show 'C5-candidate-after' (Cand-Summary $ccAfter)
"C5-supporting-evidence before=$evBefore after=$(@($ccAfter.supporting_evidence).Count)"
$rt = Respond 'Plan plant watering around pests' 'auto' 'rej-final' $false
Show 'C6-route-after-reject' @{ persona = $rt.json.persona; method = $rt.json.routing.method }

Stop-Scratch
"DONE (household store on :420 untouched)"
