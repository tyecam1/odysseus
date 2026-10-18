<#
.SYNOPSIS
  B2 resilience drill: model/network loss and recovery on SCRATCH instances only (Odysseus :1420 of a release; host agent
  :4510 from the canonical clone). The model endpoint is pointed at a dead local port to simulate loss of the model
  backend, then restored. Production (:420, :4500) is never addressed. Token from the user env, never printed.
  Phases (Odysseus): healthy model reply -> model lost: open-ended reply must DEGRADE with an honest message, a household-
  grounded request must still be answered from files, a justified team must not hang -> restored after a real restart.
  Phases (agent): brain lost -> /respond must fall back to the scripted line quickly (source=scripted), then recover.
#>
param([string]$Short = 'REPLACE_SHORT', [string]$AgentDir = 'C:\Users\User\Documents\flat-knowledgebase\host-agent')
$ErrorActionPreference = 'Continue'
$token = [Environment]::GetEnvironmentVariable('ODYSSEUS_API_TOKEN', 'User')
if (-not $token) { Write-Error 'ODYSSEUS_API_TOKEN not present'; exit 2 }
$headers = @{ Authorization = "Bearer $token" }
$REL = "C:\Users\User\odysseus-releases\$Short"
$scratch = "C:\Users\User\odysseus-releases\modelloss-scratch-$Short"
$py = 'C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe'
$script:proc = $null; $script:agent = $null
$DEAD = 'http://127.0.0.1:11999/v1'

function Body($o) { $b = [Text.Encoding]::UTF8.GetBytes(($o | ConvertTo-Json -Compress -Depth 6)); return ,$b }
function Post([string]$uri, $payload, [bool]$auth) {
  $began = Get-Date
  try {
    $h = @{}; if ($auth) { $h = $headers }
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $uri -Headers $h -ContentType 'application/json' -Body (Body $payload) -TimeoutSec 120
    return [pscustomobject]@{ status = [int]$r.StatusCode; json = ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json); ms = [int]((Get-Date) - $began).TotalMilliseconds }
  } catch {
    $d = $_.Exception.Message; if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $d = $_.ErrorDetails.Message }
    return [pscustomobject]@{ status = 0; json = $d; ms = [int]((Get-Date) - $began).TotalMilliseconds }
  }
}
function Start-Odysseus([string]$modelUrl) {
  $env:MISUMI_ROUTING_STATE_ROOT = "$scratch\routing"; $env:MISUMI_PERSONA_STATE_ROOT = "$scratch\persona"
  $a = @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File', "$REL\scripts\windows\odysseus-host.ps1",
    '-Action','Run','-SourceRoot',$REL,'-DataRoot','C:\Users\User\odysseus-releases\sbs-data-8f7803acb2','-BindHost','127.0.0.1','-Port','1420',
    '-TaskName','Odysseus-Misumi-sbs','-HouseholdRoot','C:\Users\User\Documents\flat-knowledgebase','-ObsidianPhDRoot','C:\Users\User\Documents\PhD\notes',
    '-ModelHealthUrl','http://127.0.0.1:11434/api/tags','-InterfaceHealthUrl','http://192.168.4.37:8770/health',
    '-ModelUrl',$modelUrl,'-Model','qwen3:8b','-RestartDelaySeconds','10','-TranscriptRuntime')
  $script:proc = Start-Process powershell -ArgumentList $a -WindowStyle Hidden -PassThru
  foreach ($i in 1..30) { Start-Sleep -Seconds 2
    try { if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:1420/api/health' -TimeoutSec 3).StatusCode -eq 200) { return $true } } catch { } }
  return $false
}
function Stop-Odysseus { if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null }; Start-Sleep -Seconds 3 }
function Ody([string]$persona, [string]$prompt) {
  Post 'http://127.0.0.1:1420/misumi/respond' @{ prompt = $prompt; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = $persona
    session_id = "loss-$([guid]::NewGuid().ToString('N').Substring(0,6))"; persist_turn = $false; retention_mode = 'off'; history_mode = 'off' } $true
}
function OdyPhase([string]$name) {
  $open = Ody 'misato' 'Explain how a rainbow forms.'
  $grounded = Ody 'misato' 'Check the cleaning rota'
  $team = Ody 'sanji' 'Plan the guest weekend with Misato and keep it simple.'
  Write-Host ("$name " + (@{
    open_ended = @{ status = $open.status; source = $open.json.source; ms = $open.ms; text = ([string]$open.json.text).Substring(0, [Math]::Min(110, ([string]$open.json.text).Length)) }
    household_grounded = @{ status = $grounded.status; source = $grounded.json.source; ms = $grounded.ms }
    justified_team = @{ status = $team.status; source = $team.json.source; ms = $team.ms; team = $team.json.team.decision; supports = @($team.json.team.supports | ForEach-Object { "$($_.persona):$($_.status)" }) }
  } | ConvertTo-Json -Compress -Depth 6))
}
function Start-Agent([string]$ollama) {
  $env:MISUMI_LLM = 'ollama'; $env:MISUMI_OLLAMA_URL = $ollama; $env:MISUMI_MODEL = 'qwen3:8b'
  $env:MISUMI_TTS_ENABLED = 'false'
  $script:agent = Start-Process -FilePath $py -ArgumentList @('.\misumi_agent.py', '--host', '127.0.0.1', '--port', '4510') -WorkingDirectory $AgentDir -WindowStyle Hidden -PassThru
  foreach ($i in 1..20) { Start-Sleep -Seconds 1
    try { if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:4510/health' -TimeoutSec 3).StatusCode -eq 200) { return $true } } catch { } }
  return $false
}
function Stop-Agent { if ($script:agent) { taskkill /T /F /PID $script:agent.Id | Out-Null }; Start-Sleep -Seconds 2 }
function AgentPhase([string]$name) {
  $r = Post 'http://127.0.0.1:4510/respond' @{ intent = 'reply'; state = 'idle'; mood = 'focused'; persona = 'jin'; prompt = 'Say hello in one short sentence.' } $false
  Write-Host ("$name " + (@{ status = $r.status; source = $r.json.source; ms = $r.ms; has_text = [bool]$r.json.text; text = ([string]$r.json.text).Substring(0, [Math]::Min(100, ([string]$r.json.text).Length)) } | ConvertTo-Json -Compress))
}

if (Test-Path $scratch) { Remove-Item -Recurse -Force $scratch }
New-Item -ItemType Directory -Force -Path "$scratch\routing", "$scratch\persona" | Out-Null

# ---- Odysseus
if (-not (Start-Odysseus 'http://127.0.0.1:11434/v1')) { 'FATAL healthy odysseus did not start'; Stop-Odysseus; exit 2 }
OdyPhase 'M1-model-healthy'
Stop-Odysseus
if (-not (Start-Odysseus $DEAD)) { 'FATAL odysseus (model lost) did not start'; Stop-Odysseus; exit 2 }
OdyPhase 'M2-model-lost'
Stop-Odysseus
if (-not (Start-Odysseus 'http://127.0.0.1:11434/v1')) { 'FATAL recovered odysseus did not start'; Stop-Odysseus; exit 2 }
OdyPhase 'M3-model-restored-after-restart'
Stop-Odysseus

# ---- host agent
if (-not (Start-Agent 'http://127.0.0.1:11434')) { 'FATAL healthy agent did not start'; Stop-Agent; exit 2 }
AgentPhase 'A1-brain-healthy'
Stop-Agent
if (-not (Start-Agent 'http://127.0.0.1:11999')) { 'FATAL agent (brain lost) did not start'; Stop-Agent; exit 2 }
AgentPhase 'A2-brain-lost'
Stop-Agent
if (-not (Start-Agent 'http://127.0.0.1:11434')) { 'FATAL recovered agent did not start'; Stop-Agent; exit 2 }
AgentPhase 'A3-brain-restored-after-restart'
Stop-Agent
"DONE (production :420 and :4500 untouched)"
