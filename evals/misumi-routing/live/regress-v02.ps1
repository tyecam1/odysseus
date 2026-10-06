<#
.SYNOPSIS
  Real-path routing regression for contract v0.2 (ratified 2026-10-06) and its v0.1 kill switch.
  Sends the 12 deterministic fixtures and every labelled corpus prompt (dev, held-out v1, held-out v2) through a DEPLOYED
  /misumi/respond with persona=auto and compares the routed lead with the pinned expectation computed from the live manifest
  (regress-items.json: expect_v02 / expect_v01). Follow-up rows send their prior prompt first in the same session (persisted, so a
  v0.2 carry is possible) and require the prior turn to have routed to the labelled prior_lead.
  -Target prod    the production instance on :420. Household stores are only READ: every request uses retention/history off, and
                  the routing and persona-state stores are compared before and after.
  -Target scratch a labelled :1420 instance of -Short with scratch stores; -Algorithm v0.1 starts it with the kill switch.
  Token from the host user env, never printed.
#>
param(
  [ValidateSet('prod', 'scratch')][string]$Target = 'prod',
  [ValidateSet('v0.2', 'v0.1')][string]$Algorithm = 'v0.2',
  [string]$Short = 'REPLACE_SHORT',
  [string]$ItemsPath = 'C:\Users\User\regress-items.json'
)
$ErrorActionPreference = 'Continue'
$token = [Environment]::GetEnvironmentVariable('ODYSSEUS_API_TOKEN', 'User')
if (-not $token) { Write-Error 'ODYSSEUS_API_TOKEN not present'; exit 2 }
$headers = @{ Authorization = "Bearer $token" }
$port = if ($Target -eq 'prod') { 420 } else { 1420 }
$base = "http://127.0.0.1:$port/misumi"
$script:proc = $null
$REL = "C:\Users\User\odysseus-releases\$Short"
$scratch = "C:\Users\User\odysseus-releases\regress-scratch-$Short-$($Algorithm.Replace('.', ''))"

function Body($o) { $b = [Text.Encoding]::UTF8.GetBytes(($o | ConvertTo-Json -Compress -Depth 6)); return ,$b }
function Post([string]$uri, $payload) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body (Body $payload) -TimeoutSec 120
    return [pscustomobject]@{ status = [int]$r.StatusCode; json = ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json) }
  } catch { return [pscustomobject]@{ status = 0; json = $_.Exception.Message } }
}
function Get-Json([string]$uri) {
  try { $r = Invoke-WebRequest -UseBasicParsing -Uri $uri -Headers $headers -TimeoutSec 30; return ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json) } catch { return $null }
}
function Store-State {
  $ps = Get-Json "$base/persona-state"; $rc = Get-Json "$base/routing/candidates"
  return "persona_state candidates=$(@($ps.candidates).Count) active=$(@($ps.active_revisions).Count); routing candidates=$(@($rc.candidates).Count) active=$(@($rc.active_revisions).Count)"
}
function Start-Scratch {
  $env:MISUMI_ROUTING_STATE_ROOT = "$scratch\routing"; $env:MISUMI_PERSONA_STATE_ROOT = "$scratch\persona"
  if ($Algorithm -eq 'v0.1') { $env:MISUMI_ROUTING_ALGORITHM = 'v0.1' } else { Remove-Item Env:MISUMI_ROUTING_ALGORITHM -ErrorAction SilentlyContinue }
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

if ($Target -eq 'scratch') {
  if (Test-Path $scratch) { Remove-Item -Recurse -Force $scratch }
  New-Item -ItemType Directory -Force -Path "$scratch\routing", "$scratch\persona" | Out-Null
  if (-not (Start-Scratch)) { 'FATAL scratch instance never became healthy'; if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null }; exit 2 }
}
"regress target=$Target algorithm=$Algorithm port=$port short=$Short"
"stores before: $(Store-State)"
$rows = Get-Content $ItemsPath -Raw | ConvertFrom-Json
$expectField = if ($Algorithm -eq 'v0.1') { 'expect_v01' } else { 'expect_v02' }
$wantMethod = if ($Algorithm -eq 'v0.1') { 'routing-contract-v0.1' } else { 'routing-contract-v0.2' }
$total = 0; $match = 0; $methodBad = 0; $skipped = 0; $bySplit = @{}
foreach ($row in $rows) {
  $sid = "regress-$($row.id)-$([guid]::NewGuid().ToString('N').Substring(0,5))"
  $persist = $false
  if ($row.prior_prompt) {
    $persist = $true
    $pre = Post "$base/respond" @{ prompt = $row.prior_prompt; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = 'auto'; session_id = $sid; persist_turn = $true; retention_mode = 'off'; history_mode = 'off' }
    if ($pre.json.persona -ne $row.prior_lead) { "SKIP $($row.id): prior turn routed to '$($pre.json.persona)', labelled prior lead is '$($row.prior_lead)'"; $skipped++; continue }
  }
  $r = Post "$base/respond" @{ prompt = $row.prompt; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = 'auto'; session_id = $sid; persist_turn = $persist; retention_mode = 'off'; history_mode = 'off' }
  $total++
  if (-not $bySplit.ContainsKey($row.split)) { $bySplit[$row.split] = @{ n = 0; ok = 0 } }
  $bySplit[$row.split].n++
  $want = $row.$expectField
  $ok = ($r.status -eq 200) -and ($r.json.persona -eq $want) -and ($r.json.persona_source -eq 'auto')
  $mOk = ($r.json.routing.method -eq $wantMethod)
  if (-not $mOk) { $methodBad++ }
  if ($ok) { $match++; $bySplit[$row.split].ok++ } else { "MISMATCH $($row.id) [$($row.split)] want=$want got=$($r.json.persona) status=$($r.status) | $($row.prompt)" }
  if ($Algorithm -eq 'v0.1' -and ($r.json.routing.PSObject.Properties.Name -contains 'algorithm')) { "KILL-SWITCH LEAK $($row.id): v0.2 field present under v0.1" }
}
"stores after:  $(Store-State)"
$splits = ($bySplit.Keys | Sort-Object | ForEach-Object { "$_=$($bySplit[$_].ok)/$($bySplit[$_].n)" }) -join ' '
"RESULT algorithm=$Algorithm target=$Target matched=$match/$total skipped=$skipped wrong_method_string=$methodBad  [$splits]"
if ($script:proc) { taskkill /T /F /PID $script:proc.Id | Out-Null; Start-Sleep -Seconds 3 }
"DONE"
