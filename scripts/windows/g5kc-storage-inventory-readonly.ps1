# G5 KC storage diagnosis, non-destructive. No elevation, reboot, refresh, disk writes or network.
# Does not emit disk serials, PnP instance IDs, account names or credentials.
# Run from Windows PowerShell 5.1+; errors in optional inspections are reported, not concealed.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Safe-Read {
    param([scriptblock]$Run)
    try { return @(& $Run) }
    catch { return @([pscustomobject]@{ error = $_.Exception.GetType().Name }) }
}

$report = [ordered]@{
    collected_utc = (Get-Date).ToUniversalTime().ToString('o')
    scope = 'read-only Windows storage enumeration; no physical-slot attestation'
    laptop = Safe-Read {
        Get-CimInstance Win32_ComputerSystem |
            Select-Object Manufacturer, Model, TotalPhysicalMemory
    }
    motherboard = Safe-Read {
        Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product
    }
    bios_version = Safe-Read {
        Get-CimInstance Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion, ReleaseDate
    }
    current_disks = Safe-Read {
        Get-Disk |
            Select-Object Number, FriendlyName, BusType, Size, PartitionStyle, OperationalStatus, HealthStatus, IsOffline
    }
    physical_disks = Safe-Read {
        Get-PhysicalDisk |
            Select-Object FriendlyName, MediaType, BusType, HealthStatus, Size
    }
    disk_devices_cim = Safe-Read {
        Get-CimInstance Win32_DiskDrive |
            Select-Object Index, Model, InterfaceType, Size, Status
    }
    partitions = Safe-Read {
        Get-Partition |
            Select-Object DiskNumber, PartitionNumber, DriveLetter, Type, GptType, Size
    }
    disk_pnp_present = Safe-Read {
        Get-PnpDevice -PresentOnly -Class DiskDrive |
            Select-Object Class, FriendlyName, Status
    }
    disk_pnp_including_historical = Safe-Read {
        Get-PnpDevice -Class DiskDrive |
            Select-Object Class, FriendlyName, Status
    }
    storage_controllers = Safe-Read {
        Get-PnpDevice -PresentOnly |
            Where-Object {
                $_.Class -in @('SCSIAdapter','HDC','StorageController','SDHost','SDClass') -or
                $_.FriendlyName -match 'NVMe|NVM Express|Intel.*RST|Intel.*Rapid Storage|SATA AHCI|SD Host'
            } |
            Select-Object Class, FriendlyName, Status
    }
    storage_related_recent_system_events = Safe-Read {
        Get-WinEvent -FilterHashtable @{
            LogName='System'
            StartTime=(Get-Date).AddDays(-30)
            Id=@(7,11,15,51,55,129,153,154,157,219,225)
        } -MaxEvents 80 |
            Where-Object {
                $_.ProviderName -match 'disk|stor|nvme|raid|iaStor|partmgr|Kernel-PnP'
            } |
            Select-Object TimeCreated, ProviderName, Id, LevelDisplayName
    }
}
$report | ConvertTo-Json -Depth 6
# An absent second disk is NOT proof of a dead SSD; it may not be electrically enumerating.
