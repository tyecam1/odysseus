<#
.SYNOPSIS
  B2 resilience drill: TTS failure and recovery on a SCRATCH host-agent instance (port 4510), never the production agent
  on :4500. Phases: healthy -> forced TTS failure (Kokoro model path missing) -> recovery after a real process
  restart with the good config. Reports what the box would see (audio_url present/absent, /tts status, latency) and that
  the text reply survives a TTS outage. Audibility is NOT tested (household-gated). No tokens are used or printed.
#>
param([string]$AgentDir = 'C:\Users\User\Documents\flat-knowledgebase\host-agent')
$ErrorActionPreference = 'Continue'
$port = 4510
$audio = 'C:\Users\User\odysseus-releases\drill-tts-audio'
$py = 'C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe'
$script:proc = $null

function Start-Agent([string]$label, [hashtable]$extraEnv) {
  $env:MISUMI_TTS_ENABLED = 'true'; $env:MISUMI_TTS_PROVIDER = 'kokoro'; $env:MISUMI_TTS_AUDIO_DIR = $audio; $env:MISUMI_TTS_DEBUG = 'true'
  # the production launcher's TTS environment (start-misumi-agent.ps1 -Tts)
  $env:MISUMI_TTS_MAX_CHARS = '900'; $env:MISUMI_TTS_VOICE = 'am_fenrir'; $env:MISUMI_TTS_FORMAT = 'wav'
  $env:MISUMI_TTS_KOKORO_MODEL = 'C:\Users\User\odysseus\data\models\kokoro\kokoro-v1.0.onnx'
  $env:MISUMI_TTS_KOKORO_VOICES = 'C:\Users\User\odysseus\data\models\kokoro\voices-v1.0.bin'
  $env:MISUMI_LLM = 'ollama'; $env:MISUMI_OLLAMA_URL = 'http://127.0.0.1:11434'; $env:MISUMI_MODEL = 'qwen3:8b'
  foreach ($k in $extraEnv.Keys) { Set-Item "Env:$k" $extraEnv[$k] }
  $script:proc = Start-Process -FilePath $py -ArgumentList @('.\misumi_agent.py', '--host', '127.0.0.1', '--port', "$port") -WorkingDirectory $AgentDir -WindowStyle Hidden -PassThru
  foreach ($i in 1..20) {
    Start-Sleep -Seconds 1
    try { $h = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/health" -TimeoutSec 3; if ($h.StatusCode -eq 200) { return $true } } catch { }
  }
  return $false
}
function Stop-Agent {
  if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null }
  Start-Sleep -Seconds 2
  "agent-stopped listeners=$(@(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).Count)"
}
function PostJson([string]$route, $payload) {
  $began = Get-Date
  try {
    $b = [Text.Encoding]::UTF8.GetBytes(($payload | ConvertTo-Json -Compress))
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "http://127.0.0.1:$port$route" -ContentType 'application/json' -Body $b -TimeoutSec 90
    return [pscustomobject]@{ status = [int]$r.StatusCode; json = ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json); ms = [int]((Get-Date) - $began).TotalMilliseconds }
  } catch {
    $code = 0; if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    $detail = $_.Exception.Message; if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $detail = $_.ErrorDetails.Message }
    return [pscustomobject]@{ status = $code; json = $detail; ms = [int]((Get-Date) - $began).TotalMilliseconds }
  }
}
function Phase([string]$name) {
  $reply = PostJson '/respond' @{ intent = 'reply'; state = 'idle'; mood = 'focused'; persona = 'sanji'; prompt = 'Say hello in one short sentence.' }
  $tts = PostJson '/tts' @{ text = 'Hello from the drill.'; persona = 'sanji' }
  $audioBytes = $null
  $url = $reply.json.audio_url; if (-not $url) { $url = $tts.json.audio_url }
  if ($url) {
    try { $a = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:$port" + ([uri]$url).AbsolutePath) -TimeoutSec 20; $audioBytes = $a.RawContentLength } catch { $audioBytes = "fetch-failed: $($_.Exception.Message)" }
  }
  Write-Host ("$name " + (@{
    respond_status = $reply.status; respond_has_text = [bool]$reply.json.text; respond_audio_url = [bool]$reply.json.audio_url
    respond_voice = $reply.json.voice; respond_tts_error = $reply.json.tts_error; respond_ms = $reply.ms
    tts_status = $tts.status; tts_ms = $tts.ms; tts_detail = $(if ($tts.status -ne 200) { $tts.json } else { $null })
    audio_file_bytes = $audioBytes } | ConvertTo-Json -Compress))
}

if (Test-Path $audio) { Remove-Item -Recurse -Force $audio }
New-Item -ItemType Directory -Force -Path $audio | Out-Null

if (-not (Start-Agent 'healthy' @{})) { 'FATAL healthy agent did not start'; Stop-Agent; exit 2 }
$h = (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/health" -TimeoutSec 5).Content | ConvertFrom-Json
Write-Host ("D0-health " + (@{ tts_enabled = $h.tts.enabled; provider = $h.tts.provider; kokoro_model_configured = $h.tts.kokoro_model_configured; has_voice_profiles = [bool]$h.tts.voice_profiles } | ConvertTo-Json -Compress))
Phase 'D1-healthy'
Stop-Agent

if (-not (Start-Agent 'broken' @{ MISUMI_TTS_KOKORO_MODEL = 'C:\no\such\kokoro.onnx' })) { 'FATAL broken agent did not start'; Stop-Agent; exit 2 }
Phase 'D2-tts-broken'
Stop-Agent

if (-not (Start-Agent 'recovered' @{})) { 'FATAL recovered agent did not start'; Stop-Agent; exit 2 }
Phase 'D3-recovered-after-restart'
Stop-Agent
"DONE (production agent on :4500 untouched)"
