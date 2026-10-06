<#
.SYNOPSIS
  -11 evaluation v2, step 1 (collection). Pre-registration: evals/misumi-team/eval-v2/PREREGISTRATION.md.
  Starts a labelled :1420 scratch instance of -Short (scratch stores; production untouched) in one condition, then sends every task's
  CONFLICT and CLEAN prompt -N times, interleaved in a fixed-seed shuffled order, through /misumi/respond (persist off) and appends one
  JSON object per reply to -OutFile. No judging happens here. Token from the host user env, never printed.
    -Condition solo -> MISUMI_CONSULT=0      -Condition team -> MISUMI_CONSULT=1
#>
param(
  [string]$Short = 'REPLACE_SHORT',
  [ValidateSet('solo', 'team')][string]$Condition = 'team',
  [int]$N = 12,
  [string]$TasksPath = 'C:\Users\User\eval-v2-tasks.json',
  [string]$OutFile = ''
)
$ErrorActionPreference = 'Continue'
$token = [Environment]::GetEnvironmentVariable('ODYSSEUS_API_TOKEN', 'User')
if (-not $token) { Write-Error 'ODYSSEUS_API_TOKEN not present'; exit 2 }
$headers = @{ Authorization = "Bearer $token" }
if (-not $OutFile) { $OutFile = "C:\Users\User\eval-v2-$Condition.jsonl" }
$REL = "C:\Users\User\odysseus-releases\$Short"
$scratch = "C:\Users\User\odysseus-releases\evalv2-$Short-$Condition"
$script:proc = $null

function Body($o) { $b = [Text.Encoding]::UTF8.GetBytes(($o | ConvertTo-Json -Compress -Depth 6)); return ,$b }
function Post([string]$uri, $payload) {
  $began = Get-Date
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body (Body $payload) -TimeoutSec 180
    return [pscustomobject]@{ status = [int]$r.StatusCode; json = ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json); ms = [int]((Get-Date) - $began).TotalMilliseconds }
  } catch { return [pscustomobject]@{ status = 0; json = $null; ms = [int]((Get-Date) - $began).TotalMilliseconds } }
}
function Start-Scratch {
  $env:MISUMI_ROUTING_STATE_ROOT = "$scratch\routing"; $env:MISUMI_PERSONA_STATE_ROOT = "$scratch\persona"
  $env:MISUMI_CONSULT = $(if ($Condition -eq 'team') { '1' } else { '0' })
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

if (Test-Path $scratch) { Remove-Item -Recurse -Force $scratch }
New-Item -ItemType Directory -Force -Path "$scratch\routing", "$scratch\persona" | Out-Null
if (Test-Path $OutFile) { Remove-Item -Force $OutFile }
if (-not (Start-Scratch)) { 'FATAL scratch instance never became healthy'; if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null }; exit 2 }
$tasks = Get-Content $TasksPath -Raw | ConvertFrom-Json
$jobs = @()
foreach ($run in 1..$N) { foreach ($t in $tasks) { foreach ($kind in 'conflict', 'clean') { $jobs += [pscustomobject]@{ task = $t; kind = $kind; run = $run } } } }
$rng = New-Object System.Random 20261006
$jobs = $jobs | Sort-Object { $rng.Next() }
"collect release=$Short condition=$Condition n=$N jobs=$($jobs.Count) out=$OutFile"
$done = 0
foreach ($j in $jobs) {
  $prompt = if ($j.kind -eq 'conflict') { $j.task.conflict } else { $j.task.clean }
  $r = Post 'http://127.0.0.1:1420/misumi/respond' @{ prompt = $prompt; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = $j.task.lead
    session_id = "evalv2-$($j.task.id)-$($j.kind)-$($j.run)"; persist_turn = $false; retention_mode = 'off'; history_mode = 'off' }
  $team = $r.json.team
  $supports = @()
  if ($team) { foreach ($s in $team.supports) { $supports += @{ persona = $s.persona; kind = $s.kind; status = $s.status; raised_risk = [bool]$s.raised_risk; latency_ms = $s.latency_ms } } }
  $row = @{ condition = $Condition; task = $j.task.id; kind = $j.kind; run = $j.run; lead = $j.task.lead; support = $j.task.support
            http = $r.status; source = $r.json.source; ms = $r.ms; team_decision = $(if ($team) { $team.decision } else { $null }); supports = $supports
            reply = [string]$r.json.text }
  ($row | ConvertTo-Json -Compress -Depth 6) | Add-Content -Path $OutFile -Encoding UTF8
  $done++
  if ($done % 24 -eq 0) { "progress $done/$($jobs.Count)" }
}
if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null; Start-Sleep -Seconds 3 }
"DONE $done rows -> $OutFile"
