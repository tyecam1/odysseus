$ErrorActionPreference = 'Continue'
$token = [Environment]::GetEnvironmentVariable('ODYSSEUS_API_TOKEN', 'User')
if (-not $token) { Write-Error 'ODYSSEUS_API_TOKEN not present'; exit 2 }
$headers = @{ Authorization = "Bearer $token" }
function Body($o) { $b = [Text.Encoding]::UTF8.GetBytes(($o | ConvertTo-Json -Compress -Depth 6)); return ,$b }
function Get-Json([string]$u) {
  try { $r = Invoke-WebRequest -UseBasicParsing -Uri $u -Headers $headers -TimeoutSec 30; return [pscustomobject]@{ status = [int]$r.StatusCode; json = ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json) } }
  catch { return [pscustomobject]@{ status = 0; json = $_.Exception.Message } }
}
"== release / health"
(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'uvicorn app:app --host 0.0.0.0 --port 420' } | Select-Object -First 1).CommandLine
(Get-Json 'http://127.0.0.1:420/misumi/health').json | ConvertTo-Json -Compress
"== household stores on production are READ-ONLY here"
$ps = Get-Json 'http://127.0.0.1:420/misumi/persona-state'
"persona-state: status=$($ps.status) candidates=$(@($ps.json.candidates).Count) active=$(@($ps.json.active_revisions).Count)"
$rc = Get-Json 'http://127.0.0.1:420/misumi/routing/candidates'
"routing: status=$($rc.status) candidates=$(@($rc.json.candidates).Count) active=$(@($rc.json.active_revisions).Count)  (the two -07 demo candidates from before are expected)"
"== 12 deterministic routing fixtures through the deployed /misumi/respond (persist off, retention off)"
$fixtures = @(
  @('Review priorities and risk for next month','erwin'), @('Draft the implementation workflow','lelouch'), @('Check the cleaning rota','misato'),
  @('Archive this transcript as evidence','kurisu'), @('Diagnose this finance anomaly','l'), @('Plan plant watering around pests','ginko'),
  @('Make meals from food stock','sanji'), @('Suggest records for listening','jin'), @('Close this urgent stalled task','ichigo'),
  @('Propose evolution experiments','giorno'), @('Please help me think this through','aoteru'), @('Set a Level 5 food standard','aoteru'))
$pass = 0
foreach ($f in $fixtures) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:420/misumi/respond' -Headers $headers -ContentType 'application/json' -TimeoutSec 90 `
      -Body (Body @{ prompt = $f[0]; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = 'auto'; session_id = 'prod-check'; persist_turn = $false; retention_mode = 'off'; history_mode = 'off' })
    $j = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json
    $ok = ($j.persona -eq $f[1]) -and ($j.persona_source -eq 'auto') -and ($j.routing.method -eq 'routing-contract-v0.1')
    if ($ok) { $pass++ }
    "{0} -> {1} method={2} {3}" -f $f[0], $j.persona, $j.routing.method, $(if ($ok) { 'PASS' } else { "FAIL (wanted $($f[1]))" })
  } catch { "$($f[0]) -> ERROR $($_.Exception.Message)" }
}
"fixtures: $pass/12"
"== a turn request on the deployed path (persist off: shapes this turn only, nothing stored)"
try {
  $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:420/misumi/respond' -Headers $headers -ContentType 'application/json' -TimeoutSec 90 `
    -Body (Body @{ prompt = 'Explain how a rainbow forms. Keep it shorter please.'; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = 'misato'; session_id = 'prod-check'; persist_turn = $false; retention_mode = 'off'; history_mode = 'off' })
  $j = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json
  "source=$($j.source) words=$(($j.text -split '\s+' | Where-Object { $_ }).Count) persona_state=$($j.persona_state | ConvertTo-Json -Compress -Depth 5)"
} catch { "turn request failed: $($_.Exception.Message)" }
$ps2 = Get-Json 'http://127.0.0.1:420/misumi/persona-state'
"persona-state store after: candidates=$(@($ps2.json.candidates).Count) active=$(@($ps2.json.active_revisions).Count) (must still be 0 / 0)"
"== a justified team on the deployed path (persist off)"
try {
  $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:420/misumi/respond' -Headers $headers -ContentType 'application/json' -TimeoutSec 120 `
    -Body (Body @{ prompt = 'Plan the guest weekend with Sanji and keep it simple.'; intent = 'reply'; state = 'idle'; mood = 'focused'; persona = 'misato'; session_id = 'prod-check'; persist_turn = $false; retention_mode = 'off'; history_mode = 'off' })
  $j = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json
  "source=$($j.source) team=$($j.team | ConvertTo-Json -Compress -Depth 6)"
} catch { "team probe failed: $($_.Exception.Message)" }
