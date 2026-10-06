<#
.SYNOPSIS
  Application -11 benchmark: does lead + justified support catch a PLANTED conflict more often than the lead alone?
  Runs on a labelled side-by-side :1420 instance (scratch stores) of a release, real model, one condition per invocation:
    -Condition solo  -> MISUMI_CONSULT=0 (no support personas)
    -Condition team  -> MISUMI_CONSULT=1 (lead + justified supports along the lead's consult edges)
  Every task hides one inconsistency that is detectable from the prompt text alone. A run "catches" the conflict when the
  final reply matches the task's checker regex (a LENIENT PROXY applied identically to both conditions - it can score a
  reply that merely restates a keyword, and it cannot read nuance; counts are indicative, not a quality grade).
  Prompts avoid household-domain terms so BOTH conditions take the model path (domain terms become grounded lookups).
  Output: one JSON line per run plus a summary line. Token read from the user env, never printed.
#>
param(
  [string]$Short = 'REPLACE_SHORT',
  [ValidateSet('solo', 'team')][string]$Condition = 'team',
  [int]$N = 4
)
$ErrorActionPreference = 'Continue'
$token = [Environment]::GetEnvironmentVariable('ODYSSEUS_API_TOKEN', 'User')
if (-not $token) { Write-Error 'ODYSSEUS_API_TOKEN not present'; exit 2 }
$headers = @{ Authorization = "Bearer $token" }
$REL = "C:\Users\User\odysseus-releases\$Short"
$scratch = "C:\Users\User\odysseus-releases\team-bench-$Short-$Condition"
$script:proc = $null

$tasks = @(
  @{ id = 'budget'; lead = 'sanji'; support = 'l';
     prompt = "Plan Saturday's dinner for six. The bills this month leave only 20 pounds for it, and the lasagne I want to make needs about 45 pounds of ingredients.";
     checker = "exceed|over (the )?(budget|limit)|more than (the )?(20|twenty)|too (much|expensive|costly)|can'?t afford|cannot afford|not enough|beyond|doesn'?t fit|won'?t fit|shortfall|short by|cheaper|reduce (the )?cost|cut (the )?cost" },
  @{ id = 'allergy'; lead = 'misato'; support = 'sanji';
     prompt = "Plan the guest weekend with Sanji. One guest has a severe nut allergy, and I was going to serve the pesto made with pine nuts and walnuts on Friday.";
     checker = "allerg\w*.{0,80}(avoid|unsafe|danger|serious|substitut|swap|replace|instead|without|remove|nut-free)|(avoid|remove|replace|swap|skip|without|nut-free|substitut\w*).{0,60}(nut|walnut|pine)|can'?t use|cannot use|not safe|unsafe" },
  @{ id = 'payday'; lead = 'erwin'; support = 'l';
     prompt = "Review the plan to pay the quarterly bills on the 5th. My salary arrives on the 10th and the account will be close to empty before then.";
     checker = "overdraw\w*|overdraft|insufficient|not enough|(before|prior to).{0,40}(salary|payday|10th|paid)|wait until|after (the )?(10th|salary|payday)|move .{0,30}(date|payment)|cash ?flow|reschedul\w*" },
  @{ id = 'timing'; lead = 'jin'; support = 'misato';
     prompt = "Plan a listening evening with Misato. Guests arrive at 7, the speakers need a full hour of dusting and set-up first, and I only get home at 6:30.";
     checker = "not enough|insufficient|only (30|thirty)|30 min|half an hour|won'?t (be )?(enough|work|fit)|doesn'?t (leave|fit)|start earlier|too (tight|late|little)|clash|conflict|get help|ask .{0,20}help|reduce|trim|skip" },
  @{ id = 'rollout'; lead = 'lelouch'; support = 'erwin';
     prompt = "Ask Erwin to review the rollout plan. The migration finishes on Thursday, but the announcement email goes out on Wednesday promising the new system is already live.";
     checker = "conflict|mismatch|inconsisten\w*|ahead of|premature|too early|reschedul\w*|delay|move (the )?(email|announcement)|after (the )?(migration|thursday)|before (the )?(migration|it)|wait" }
)

function Body($o) { $b = [Text.Encoding]::UTF8.GetBytes(($o | ConvertTo-Json -Compress -Depth 6)); return ,$b }
function J($r) { [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json }
function Call([string]$method, [string]$uri, $payload) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Method $method -Uri $uri -Headers $headers -ContentType 'application/json' -Body (Body $payload) -TimeoutSec 180
    return [pscustomobject]@{ status = [int]$r.StatusCode; json = (J $r) }
  } catch {
    $detail = $_.Exception.Message
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $detail = $_.ErrorDetails.Message }
    return [pscustomobject]@{ status = 0; json = $detail }
  }
}
function Start-Scratch {
  $env:MISUMI_ROUTING_STATE_ROOT = "$scratch\routing"
  $env:MISUMI_PERSONA_STATE_ROOT = "$scratch\persona"
  $env:MISUMI_CONSULT = $(if ($Condition -eq 'team') { '1' } else { '0' })
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
  foreach ($i in 1..30) {
    Start-Sleep -Seconds 2
    try { if ((Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:1420/api/health' -TimeoutSec 3).StatusCode -eq 200) { return $true } } catch { }
  }
  return $false
}
function Stop-Scratch {
  if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null }
  Start-Sleep -Seconds 3
}

if (Test-Path $scratch) { Remove-Item -Recurse -Force $scratch }
New-Item -ItemType Directory -Force -Path "$scratch\routing", "$scratch\persona" | Out-Null
if (-not (Start-Scratch)) { "FATAL scratch instance never became healthy"; Stop-Scratch; exit 2 }
"bench-up release=$Short condition=$Condition n=$N"
$caught = @{}; $ran = @{}; $teamRuns = 0; $supportOk = 0; $supportRisk = 0; $lat = @()
foreach ($task in $tasks) {
  $caught[$task.id] = 0; $ran[$task.id] = 0
  foreach ($i in 1..$N) {
    $began = Get-Date
    $r = Call 'POST' 'http://127.0.0.1:1420/misumi/respond' @{ prompt = $task.prompt; intent = 'reply'; state = 'idle'; mood = 'focused'
      persona = $task.lead; session_id = "bench-$($task.id)-$i"; persist_turn = $false; retention_mode = 'off'; history_mode = 'off' }
    $ms = [int]((Get-Date) - $began).TotalMilliseconds
    $text = [string]$r.json.text
    $hit = ($r.status -eq 200) -and ($text -match "(?is)$($task.checker)")
    $ran[$task.id] += 1; if ($hit) { $caught[$task.id] += 1 }
    $team = $r.json.team
    $sup = $null; $risk = $null
    if ($team) { $teamRuns++; $sup = @($team.supports | ForEach-Object { "$($_.persona):$($_.status)" }) -join ','
      foreach ($s in $team.supports) { if ($s.status -eq 'ok') { $supportOk++ }; if ($s.raised_risk) { $supportRisk++ } } }
    $lat += $ms
    (@{ task = $task.id; run = $i; condition = $Condition; status = $r.status; source = $r.json.source; caught = $hit; ms = $ms
        team = $sup; words = ($text -split '\s+' | Where-Object { $_ }).Count; reply = ($text.Substring(0, [Math]::Min(420, $text.Length))) } | ConvertTo-Json -Compress)
  }
}
$total = ($caught.Values | Measure-Object -Sum).Sum; $all = ($ran.Values | Measure-Object -Sum).Sum
(@{ summary = $true; condition = $Condition; caught = $total; of = $all; by_task = $caught; team_runs = $teamRuns
    support_ok = $supportOk; support_raised_risk = $supportRisk; median_ms = ($lat | Sort-Object)[[int]($lat.Count / 2)] } | ConvertTo-Json -Compress)
Stop-Scratch
"DONE"
