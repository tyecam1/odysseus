<#
.SYNOPSIS
  Scheduled, verified, optionally encrypted backup of the Odysseus household data root on Windows.

.DESCRIPTION
  Wraps scripts/odysseus-backup (see docs/backup-restore.md). Nothing here chooses a destination or a key: both are
  parameters, and with neither the run is a local, same-disk snapshot.

    -IncludeRebuildable  Also back up cache, tts_cache, stt-tmp and models (excluded by default).
    -Action Run        Take one snapshot now: snapshot (the tool verifies it and writes a manifest), optionally copy to
                       -DestinationDir and re-check its sha256 there, prune, and write backup-status.json.
    -Action Install    Register a daily scheduled task that runs `-Action Run` with the same parameters.
                       Supports -WhatIf. Nothing is registered unless you ask for it.
    -Action Uninstall  Remove that scheduled task. Backups are left in place.
    -Action Invalidate Honour an explicit deletion: delete EVERY snapshot and manifest in -StagingDir and -DestinationDir,
                       then take and verify a fresh snapshot (run it after the deletion has been made in the live archive).
                       Supports -WhatIf. A deletion made in the live archive stays recoverable from older snapshots until
                       this is run or they age out.
    -Action Status     Print backup-status.json. Exits 2 if the last run failed or is older than -MaxAgeHours.

  Safety rules enforced here:
    * A snapshot contains household speech AND the Fernet key. Copying to -DestinationDir without -RecipientsFile
      (encryption) is refused unless -AllowUnencryptedDestination is passed explicitly.
    * The final destination must not be a fixed disk on this host (that is not disaster recovery): a local fixed volume is
      refused unless -AllowLocalDestination is passed. UNC paths and removable media are accepted.
    * -RecipientsFile must hold only PUBLIC recipients: a file containing an AGE-SECRET-KEY is refused. The age private
      identity must live in a password manager and an offline copy, never on this host, in Git or at the destination.
    * Encrypted snapshots are built by the tool in a temporary directory; plaintext never exists at the output path.
    * Every copy is re-checked against the manifest sha256 before it counts.
    * A failed run exits non-zero and records the error; it never reports success.

  The task runs as the current user with S4U logon (no stored password, no network credentials). A UNC destination
  needs credentials this logon type does not have, so use a local or removable volume, or register the task yourself with
  a stored credential.

.EXAMPLE
  # Local staging only, today, for a one-off check:
  .\odysseus-backup-task.ps1 -Action Run -SourceRoot C:\Users\User\odysseus-releases\<sha> -StagingDir E:\backups\odysseus

.EXAMPLE
  # See what Install would register, without registering it:
  .\odysseus-backup-task.ps1 -Action Install -SourceRoot ... -StagingDir ... -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Run', 'Install', 'Uninstall', 'Status', 'Invalidate')][string]$Action,
    [string]$SourceRoot,
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'Odysseus\Misumi'),
    [string]$StagingDir,
    [string]$DestinationDir,
    [string]$RecipientsFile,
    [switch]$AllowUnencryptedDestination,
    [switch]$AllowLocalDestination,
    [string]$Python,
    [switch]$IncludeRebuildable,
    [int]$KeepDaily = 7,
    [int]$KeepWeekly = 4,
    [int]$KeepMonthly = 12,
    [string]$TaskName = 'Odysseus-Backup',
    [string]$At = '02:30',
    [int]$MaxAgeHours = 36
)

$ErrorActionPreference = 'Stop'

function Get-StatusPath { Join-Path $StagingDir 'backup-status.json' }

function Write-Status([hashtable]$Status) {
    New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null
    $json = $Status | ConvertTo-Json -Depth 6
    $tmp = (Get-StatusPath) + '.tmp'
    [IO.File]::WriteAllText($tmp, $json, (New-Object Text.UTF8Encoding $false))
    Move-Item -Force -LiteralPath $tmp -Destination (Get-StatusPath)
}

function Resolve-Python {
    if ($Python) { return $Python }
    $venv = Join-Path $SourceRoot 'venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venv) { return $venv }
    return 'python'
}

function Invoke-Tool([string[]]$ToolArgs) {
    $py = Resolve-Python
    $tool = Join-Path $SourceRoot 'scripts\odysseus-backup'
    # stdout carries the tool's JSON result; stderr is kept apart so a warning can never corrupt it.
    $errFile = [IO.Path]::GetTempFileName()
    try {
        $output = & $py $tool @ToolArgs 2> $errFile
        $code = $LASTEXITCODE
        $stderr = (Get-Content -LiteralPath $errFile -Raw -ErrorAction SilentlyContinue)
    }
    finally { Remove-Item -LiteralPath $errFile -Force -ErrorAction SilentlyContinue }
    $text = ($output | ForEach-Object { "$_" }) -join "`n"
    if ($code -ne 0) { throw "odysseus-backup $($ToolArgs[0]) failed (exit ${code}): $($stderr.Trim()) $text".Trim() }
    return $text
}

function Test-RecipientsPublic([string]$Path) {
    if (-not $Path) { return }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "-RecipientsFile not found: $Path" }
    if ((Get-Content -LiteralPath $Path -Raw) -match 'AGE-SECRET-KEY-') {
        throw "-RecipientsFile contains an AGE-SECRET-KEY. Only public recipients may be kept on this host; keep the private identity in a password manager and an offline copy."
    }
}

function Test-DestinationAllowed {
    if (-not $DestinationDir) { return }
    if (-not $RecipientsFile -and -not $AllowUnencryptedDestination) {
        throw 'Refusing to use -DestinationDir without -RecipientsFile (encryption). A snapshot contains household speech and the Fernet key.'
    }
    $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($DestinationDir))
    if ($root -match '^[A-Za-z]:\\$') {
        $disk = Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='" + $root.Substring(0, 2) + "'")
        if ($disk -and $disk.DriveType -eq 3 -and -not $AllowLocalDestination) {
            throw "-DestinationDir $DestinationDir is a fixed disk on this host, which is not disaster recovery. Use removable media or a network or off-site destination, or pass -AllowLocalDestination to accept that explicitly."
        }
    }
}

function Get-RunArgs([bool]$Quote = $true) {
    # $Quote: embed literal quotes (for the scheduled task's command-line string); off for a native-call splat.
    $q = if ($Quote) { '"' } else { '' }
    $a = @('-SourceRoot', "$q$SourceRoot$q", '-DataRoot', "$q$DataRoot$q", '-StagingDir', "$q$StagingDir$q",
        '-KeepDaily', $KeepDaily, '-KeepWeekly', $KeepWeekly, '-KeepMonthly', $KeepMonthly)
    if ($IncludeRebuildable) { $a += '-IncludeRebuildable' }
    if ($DestinationDir) { $a += @('-DestinationDir', "$q$DestinationDir$q") }
    if ($RecipientsFile) { $a += @('-RecipientsFile', "$q$RecipientsFile$q") }
    if ($AllowUnencryptedDestination) { $a += '-AllowUnencryptedDestination' }
    if ($AllowLocalDestination) { $a += '-AllowLocalDestination' }
    if ($Python) { $a += @('-Python', "$q$Python$q") }
    return $a
}

function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

function Require([string]$Name, $Value) {
    if (-not $Value) { throw "-$Name is required for -Action $Action" }
}

switch ($Action) {

    'Status' {
        Require 'StagingDir' $StagingDir
        $path = Get-StatusPath
        if (-not (Test-Path -LiteralPath $path)) { Write-Output "NO STATUS FILE at ${path}: no backup has run here."; exit 2 }
        $status = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        $age = [int](((Get-Date).ToUniversalTime() - [datetime]::Parse($status.finished_utc).ToUniversalTime()).TotalHours)
        Write-Output ($status | ConvertTo-Json -Depth 6)
        if (-not $status.ok) { Write-Output "LAST RUN FAILED: $($status.error)"; exit 2 }
        if ($age -gt $MaxAgeHours) { Write-Output "STALE: the last successful run finished $age hours ago (limit $MaxAgeHours)."; exit 2 }
        exit 0
    }

    'Uninstall' {
        if ($PSCmdlet.ShouldProcess($TaskName, 'Unregister scheduled task')) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            Write-Output "Unregistered $TaskName. Existing backups were left in place."
        }
    }

    'Install' {
        Require 'SourceRoot' $SourceRoot
        Require 'StagingDir' $StagingDir
        Test-RecipientsPublic $RecipientsFile
        Test-DestinationAllowed
        $self = $MyInvocation.MyCommand.Path
        $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$self`"", '-Action', 'Run') + (Get-RunArgs)
        $taskAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ($argList -join ' ')
        $trigger = New-ScheduledTaskTrigger -Daily -At $At
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Hours 1) -AllowStartIfOnBatteries
        Write-Output "Task:      $TaskName (daily at $At, as $env:USERDOMAIN\$env:USERNAME, S4U)"
        Write-Output "Command:   powershell.exe $($argList -join ' ')"
        Write-Output "Staging:   $StagingDir"
        Write-Output ("Copy to:   " + $(if ($DestinationDir) { $DestinationDir } else { '(none: local staging only)' }))
        Write-Output ("Encrypted: " + $(if ($RecipientsFile) { "yes (age, recipients $RecipientsFile)" } else { 'NO (plaintext snapshots contain the Fernet key)' }))
        if ($PSCmdlet.ShouldProcess($TaskName, 'Register scheduled task')) {
            Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $trigger -Principal $principal `
                -Settings $settings -Description 'Verified backup of the Odysseus household data root (docs/backup-restore.md)' | Out-Null
            Write-Output "Registered $TaskName."
        }
    }

    'Invalidate' {
        Require 'SourceRoot' $SourceRoot
        Require 'StagingDir' $StagingDir
        Test-RecipientsPublic $RecipientsFile
        Test-DestinationAllowed
        $dirs = @(@($StagingDir, $DestinationDir) | Where-Object { $_ })
        foreach ($dir in $dirs) {
            $preview = (Invoke-Tool @('prune', '--dir', $dir, '--all')) | ConvertFrom-Json
            Write-Output ("{0}: {1} snapshot(s) would be deleted" -f $dir, @($preview.would_delete).Count)
        }
        if ($PSCmdlet.ShouldProcess(($dirs -join ', '), 'Delete every snapshot and take a fresh verified one')) {
            foreach ($dir in $dirs) {
                $done = (Invoke-Tool @('prune', '--dir', $dir, '--all', '--yes')) | ConvertFrom-Json
                Write-Output ("{0}: deleted {1}" -f $dir, @($done.deleted).Count)
            }
            $self = $MyInvocation.MyCommand.Path
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $self -Action Run @(Get-RunArgs $false)
            exit $LASTEXITCODE
        }
    }

    'Run' {
        Require 'SourceRoot' $SourceRoot
        Require 'StagingDir' $StagingDir
        $started = (Get-Date).ToUniversalTime()
        $status = [ordered]@{
            ok = $false; started_utc = $started.ToString('o'); finished_utc = $null; host = $env:COMPUTERNAME
            data_root = $DataRoot; staging_dir = $StagingDir; destination_dir = $DestinationDir
            encrypted = [bool]$RecipientsFile; snapshot = $null; sha256 = $null; databases = $null
            copied_to_destination = $false; pruned = $null; error = $null
        }
        try {
            Test-RecipientsPublic $RecipientsFile
            Test-DestinationAllowed
            if (-not (Test-Path -LiteralPath $DataRoot -PathType Container)) { throw "DataRoot not found: $DataRoot" }
            if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot 'scripts\odysseus-backup'))) { throw "scripts\odysseus-backup not found under $SourceRoot" }
            New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null
            $env:ODYSSEUS_DATA_DIR = $DataRoot

            $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
            $out = Join-Path $StagingDir "odysseus-backup-$stamp.tar.gz"
            $snapArgs = @('snapshot', '--out', $out)
            if (-not $IncludeRebuildable) { $snapArgs += '--exclude-rebuildable' }
            if ($RecipientsFile) { $snapArgs += @('--encrypt-recipients', $RecipientsFile) }
            $result = (Invoke-Tool $snapArgs) | ConvertFrom-Json
            if (-not $result.ok -or -not $result.verified) { throw "the tool did not report a verified snapshot: $($result | ConvertTo-Json -Compress)" }
            $status.snapshot = $result.path
            $status.sha256 = $result.sha256
            $status.databases = $result.databases

            # The archive on disk must still match the manifest the tool wrote.
            $null = Invoke-Tool @('verify', $result.path)

            if ($DestinationDir) {
                New-Item -ItemType Directory -Force -Path $DestinationDir | Out-Null
                foreach ($file in @($result.path, $result.manifest)) {
                    Copy-Item -LiteralPath $file -Destination $DestinationDir -Force
                }
                $copied = Join-Path $DestinationDir (Split-Path -Leaf $result.path)
                if ((Get-Sha256 $copied) -ne $result.sha256) { throw "the copy at $copied does not match the snapshot's sha256" }
                $null = Invoke-Tool @('verify', $copied)
                $status.copied_to_destination = $true
            }

            $pruneArgs = @('--keep-daily', $KeepDaily, '--keep-weekly', $KeepWeekly, '--keep-monthly', $KeepMonthly, '--yes')
            $pruned = @()
            foreach ($dir in @(@($StagingDir, $DestinationDir) | Where-Object { $_ })) {
                $p = (Invoke-Tool (@('prune', '--dir', $dir) + $pruneArgs)) | ConvertFrom-Json
                $pruned += @{ dir = $dir; deleted = @($p.deleted) }
            }
            $status.pruned = $pruned
            $status.ok = $true
        }
        catch {
            $status.error = $_.Exception.Message
        }
        finally {
            $status.finished_utc = (Get-Date).ToUniversalTime().ToString('o')
            try { Write-Status $status } catch { [Console]::Error.WriteLine("could not write the status file: $($_.Exception.Message)") }
        }
        if ($status.ok) { Write-Output ($status | ConvertTo-Json -Depth 6); exit 0 }
        [Console]::Error.WriteLine("BACKUP FAILED: $($status.error)")
        exit 1
    }
}
