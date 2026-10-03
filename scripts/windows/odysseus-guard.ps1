<#
  Household runtime guard: machine-start lifecycle for the canonical required services plus the smallest independent recovery.

  Canonical required services (and nothing else):
    - Odysseus runtime        http://127.0.0.1:420/api/health        scheduled task Odysseus-Misumi (supervised by odysseus-host.ps1)
    - Ollama (local models)   http://127.0.0.1:11434/api/tags        scheduled task Ollama-Misumi
  The legacy Misumi host agent (:4500) and its STT server (:4600) are NOT required by the durable transcript path and are
  deliberately outside this lifecycle.

  Actions
    Install             register Ollama-Misumi (machine start, S4U) and Odysseus-Guard (machine start + every 2 minutes, S4U).
                        Odysseus-Misumi itself is (re)registered by odysseus-host.ps1 -Action Install -BootStart.
    Watch               one pass: probe both services; after -FailuresBeforeRecovery consecutive failures recover the
                        corresponding scheduled task, verify health, and write evidence. Does nothing while maintenance is active.
    MaintenanceEnter    governed outage: write the maintenance flag (bounded, auto-expiring) and stop both services. The guard
                        will not restart them while the flag is active, so an intentional outage or test is not fought.
    MaintenanceRelease  remove the flag and run a Watch pass immediately so anything that is down comes back.
    Status              JSON: services, tasks, maintenance flag, recent evidence.
    Uninstall           remove Odysseus-Guard (Ollama-Misumi and Odysseus-Misumi are left in place).

  Crash recovery versus maintenance is a single deterministic rule: unexpected failure -> restart; a live maintenance flag -> stay stopped.
  No credential is stored, nothing runs as SYSTEM, no listener is added, and nothing here touches firewall or auth settings.
#>
param(
    [ValidateSet('Install', 'Uninstall', 'Watch', 'MaintenanceEnter', 'MaintenanceRelease', 'Status')]
    [string]$Action = 'Status',
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'Odysseus\Misumi'),
    [string]$OdysseusTaskName = 'Odysseus-Misumi',
    [string]$OllamaTaskName = 'Ollama-Misumi',
    [string]$GuardTaskName = 'Odysseus-Guard',
    [string]$OdysseusHealthUrl = 'http://127.0.0.1:420/api/health',
    [string]$OllamaHealthUrl = 'http://127.0.0.1:11434/api/tags',
    [string]$OllamaExe = (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'),
    [int]$FailuresBeforeRecovery = 2,
    [int]$RecoveryWaitSeconds = 90,
    [int]$MaxMaintenanceHours = 6,
    [double]$MaintenanceHours = 1,
    [string]$Reason = '',
    [string]$StateDir = '',
    # Test hooks: replace the real recovery action. Not used by the scheduled task.
    [string]$RecoverOdysseusCommand = '',
    [string]$RecoverOllamaCommand = '',
    [string]$StopOdysseusCommand = '',
    [string]$StopOllamaCommand = ''
)

$ErrorActionPreference = 'Stop'
if (-not $StateDir) { $StateDir = Join-Path $DataRoot 'guard' }
$statePath = Join-Path $StateDir 'state.json'
$flagPath = Join-Path $StateDir 'maintenance.json'
$evidencePath = Join-Path $StateDir 'guard.jsonl'
$statusPath = Join-Path $StateDir 'guard-status.json'
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Write-Evidence([string]$Kind, [string]$Service, [hashtable]$Data) {
    $row = [ordered]@{ ts = (Get-Date).ToString('o'); kind = $Kind; service = $Service }
    foreach ($k in $Data.Keys) { $row[$k] = $Data[$k] }
    if ((Test-Path $evidencePath) -and ((Get-Item $evidencePath).Length -gt 1MB)) {
        Move-Item -Force $evidencePath "$evidencePath.1"
    }
    Add-Content -Path $evidencePath -Value ($row | ConvertTo-Json -Compress) -Encoding UTF8
}

function Test-Healthy([string]$Url) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 6
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Read-State {
    if (Test-Path $statePath) { try { return Get-Content $statePath -Raw | ConvertFrom-Json } catch { } }
    [pscustomobject]@{ odysseus = 0; ollama = 0 }
}

function Get-MaintenanceFlag {
    if (-not (Test-Path $flagPath)) { return $null }
    try { $f = Get-Content $flagPath -Raw | ConvertFrom-Json } catch { Remove-Item $flagPath -Force; return $null }
    if ([datetime]$f.expires -le (Get-Date)) {
        Write-Evidence 'maintenance' '-' @{ event = 'expired'; reason = $f.reason; entered = $f.entered; expired = $f.expires }
        Remove-Item $flagPath -Force
        return $null
    }
    return $f
}

function Get-OdysseusWrapper {
    # Follow whatever release the Odysseus-Misumi task currently points at, so a new release needs no change here.
    $t = Get-ScheduledTask -TaskName $OdysseusTaskName -ErrorAction SilentlyContinue
    if (-not $t) { return $null }
    $args1 = [string]$t.Actions[0].Arguments
    if ($args1 -match '-File\s+"([^"]+odysseus-host\.ps1)"') { return $Matches[1] }
    return $null
}

function Invoke-OdysseusHost([string]$HostAction) {
    $ErrorActionPreference = 'Continue'   # native stderr must not become a terminating error under the script-wide Stop preference
    $wrapper = Get-OdysseusWrapper
    if (-not $wrapper) { throw "cannot find the odysseus-host.ps1 behind task $OdysseusTaskName" }
    $t = Get-ScheduledTask -TaskName $OdysseusTaskName
    $a = [string]$t.Actions[0].Arguments
    $source = if ($a -match '-SourceRoot\s+"([^"]+)"') { $Matches[1] } else { Split-Path (Split-Path $wrapper) }
    $data = if ($a -match '-DataRoot\s+"([^"]+)"') { $Matches[1] } else { $DataRoot }
    $port = if ($a -match '-Port\s+(\d+)') { $Matches[1] } else { '420' }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $wrapper -Action $HostAction -SourceRoot $source -DataRoot $data -Port $port -TaskName $OdysseusTaskName 2>&1 | Out-Null
}

function Recover-Odysseus {
    if ($RecoverOdysseusCommand) { Invoke-Expression $RecoverOdysseusCommand; return }
    Invoke-OdysseusHost 'Restart'
}

function Recover-Ollama {
    if ($RecoverOllamaCommand) { Invoke-Expression $RecoverOllamaCommand; return }
    Stop-ScheduledTask -TaskName $OllamaTaskName -ErrorAction SilentlyContinue
    Get-Process -Name 'ollama', 'ollama app' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $OllamaExe } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName $OllamaTaskName
}

function Stop-Odysseus {
    if ($StopOdysseusCommand) { Invoke-Expression $StopOdysseusCommand; return }
    Invoke-OdysseusHost 'Stop'
}

function Stop-Ollama {
    if ($StopOllamaCommand) { Invoke-Expression $StopOllamaCommand; return }
    Stop-ScheduledTask -TaskName $OllamaTaskName -ErrorAction SilentlyContinue
    Get-Process -Name 'ollama', 'ollama app' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $OllamaExe } | Stop-Process -Force -ErrorAction SilentlyContinue
}

function Invoke-Watch {
    $flag = Get-MaintenanceFlag
    $state = Read-State
    $services = @(
        @{ name = 'odysseus'; url = $OdysseusHealthUrl; recover = { Recover-Odysseus } },
        @{ name = 'ollama'; url = $OllamaHealthUrl; recover = { Recover-Ollama } }
    )
    $summary = [ordered]@{ ts = (Get-Date).ToString('o'); maintenance = [bool]$flag; services = [ordered]@{} }
    foreach ($s in $services) {
        $ok = Test-Healthy $s.url
        $prev = [int]$state.($s.name)
        if ($ok) {
            if ($prev -ge $FailuresBeforeRecovery) { Write-Evidence 'observed' $s.name @{ event = 'healthy-again'; after_failures = $prev } }
            $state.($s.name) = 0
            $summary.services[$s.name] = 'healthy'
            continue
        }
        if ($flag) {
            Write-Evidence 'suppressed' $s.name @{ reason = $flag.reason; maintenance_expires = $flag.expires }
            $summary.services[$s.name] = 'down (maintenance: not recovered)'
            continue
        }
        $n = $prev + 1
        $state.($s.name) = $n
        if ($n -lt $FailuresBeforeRecovery) { $summary.services[$s.name] = "unhealthy ($n of $FailuresBeforeRecovery)"; continue }
        $started = Get-Date
        $err = ''
        try { & $s.recover } catch { $err = $_.Exception.Message }
        $deadline = (Get-Date).AddSeconds($RecoveryWaitSeconds)
        $after = $false
        while ((Get-Date) -lt $deadline) { if (Test-Healthy $s.url) { $after = $true; break }; Start-Sleep -Seconds 3 }
        Write-Evidence 'recovery' $s.name @{ failures = $n; healthy_after = $after; seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 1); error = $err }
        if ($after) { $state.($s.name) = 0; $summary.services[$s.name] = 'recovered' } else { $summary.services[$s.name] = 'RECOVERY FAILED' }
    }
    ($state | ConvertTo-Json -Compress) | Set-Content -Path $statePath -Encoding UTF8
    ($summary | ConvertTo-Json -Depth 4) | Set-Content -Path $statusPath -Encoding UTF8
    $summary
}

switch ($Action) {
    'Watch' {
        $r = Invoke-Watch
        $r | ConvertTo-Json -Depth 4
        if (@($r.services.Values | Where-Object { $_ -eq 'RECOVERY FAILED' }).Count -gt 0) { exit 2 }
    }
    'MaintenanceEnter' {
        if (-not $Reason) { throw 'MaintenanceEnter needs -Reason (what is being done and why)' }
        $hours = [math]::Min([math]::Max($MaintenanceHours, 0.05), $MaxMaintenanceHours)
        $entered = Get-Date
        $flag = [ordered]@{ reason = $Reason; entered = $entered.ToString('o'); expires = $entered.AddHours($hours).ToString('o'); by = $env:USERNAME }
        ($flag | ConvertTo-Json) | Set-Content -Path $flagPath -Encoding UTF8
        Write-Evidence 'maintenance' '-' @{ event = 'entered'; reason = $Reason; expires = $flag.expires }
        Stop-Odysseus
        Stop-Ollama
        "Maintenance active until $($flag.expires): $Reason. Odysseus and Ollama stopped; the guard will not restart them. Release with -Action MaintenanceRelease."
    }
    'MaintenanceRelease' {
        $had = Test-Path $flagPath
        if ($had) { Remove-Item $flagPath -Force }
        Write-Evidence 'maintenance' '-' @{ event = 'released'; had_flag = $had }
        # Services that are down come back through the normal path straight away (no failure count to wait for).
        $state = [pscustomobject]@{ odysseus = $FailuresBeforeRecovery; ollama = $FailuresBeforeRecovery }
        ($state | ConvertTo-Json -Compress) | Set-Content -Path $statePath -Encoding UTF8
        (Invoke-Watch) | ConvertTo-Json -Depth 4
    }
    'Status' {
        $flag = Get-MaintenanceFlag
        $tasks = foreach ($n in $OdysseusTaskName, $OllamaTaskName, $GuardTaskName) {
            $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
            if ($t) { $i = Get-ScheduledTaskInfo -TaskName $n; [ordered]@{ name = $n; state = [string]$t.State; logon = [string]$t.Principal.LogonType; triggers = (@($t.Triggers | ForEach-Object { $_.CimClass.CimClassName -replace 'MSFT_Task|Trigger', '' }) -join ','); last_run = $i.LastRunTime; last_result = $i.LastTaskResult } }
            else { [ordered]@{ name = $n; state = 'not-installed' } }
        }
        [ordered]@{
            odysseus_healthy = (Test-Healthy $OdysseusHealthUrl)
            ollama_healthy = (Test-Healthy $OllamaHealthUrl)
            maintenance = $flag
            failure_counts = (Read-State)
            tasks = @($tasks)
            recent_evidence = @(if (Test-Path $evidencePath) { Get-Content $evidencePath -Tail 8 })
        } | ConvertTo-Json -Depth 5
    }
    'Install' {
        if (-not (Test-Path -LiteralPath $OllamaExe)) { throw "Ollama executable not found at $OllamaExe" }
        $scriptPath = $MyInvocation.MyCommand.Path
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
        # Ollama: serve in the foreground so the task supervises it (no untracked child), bound to loopback as before.
        $ollamaAction = New-ScheduledTaskAction -Execute $OllamaExe -Argument 'serve'
        $startup = New-ScheduledTaskTrigger -AtStartup; $startup.Delay = 'PT30S'
        $logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $ollamaSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit (New-TimeSpan -Days 3650) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $OllamaTaskName -Action $ollamaAction -Trigger @($startup, $logon) -Principal $principal `
            -Settings $ollamaSettings -Description 'Ollama local model server (machine-start, non-interactive)' -Force | Out-Null
        # Guard: a short, bounded pass every two minutes; also one pass shortly after machine start.
        $guardArgs = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Action Watch -DataRoot "{1}"' -f $scriptPath, $DataRoot)
        $guardAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $guardArgs
        $gStartup = New-ScheduledTaskTrigger -AtStartup; $gStartup.Delay = 'PT2M'
        $gRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)
        $guardSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
            -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $GuardTaskName -Action $guardAction -Trigger @($gStartup, $gRepeat) -Principal $principal `
            -Settings $guardSettings -Description 'Watches Odysseus and Ollama; recovers unexpected failure, honours the maintenance flag' -Force | Out-Null
        "Installed $OllamaTaskName (machine start, S4U) and $GuardTaskName (machine start + every 2 minutes, S4U). Odysseus-Misumi is installed by odysseus-host.ps1 -Action Install -BootStart."
    }
    'Uninstall' {
        Unregister-ScheduledTask -TaskName $GuardTaskName -Confirm:$false -ErrorAction SilentlyContinue
        "Removed $GuardTaskName. $OllamaTaskName and $OdysseusTaskName are unchanged."
    }
}
