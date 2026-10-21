# Advanced G5 KC storage diagnosis, strictly read-only; no driver installation, rescan, reset or reboot.
# PCI VEN/DEV codes are model identifiers, not unique hardware serial numbers.
# Run locally on the Windows laptop; review output before sharing beyond the machine.
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
function Safe-Read {
  param([scriptblock]$Query)
  try { @(& $Query) } catch { @([pscustomobject]@{ ErrorType = $_.Exception.GetType().Name }) }
}
$allPCI = Safe-Read {
  Get-CimInstance Win32_PnPEntity |
    Where-Object { $_.PNPDeviceID -like 'PCI\*' } |
    ForEach-Object {
      $hw = $_.PNPDeviceID
      [pscustomobject]@{
        Name = $_.Name
        Class = $_.PNPClass
        Status = $_.Status
        ProblemCode = $_.ConfigManagerErrorCode
        PCIModelId = if ($hw -match 'VEN_([0-9A-Fa-f]{4})&DEV_([0-9A-Fa-f]{4})') {
          ('VEN_{0}&DEV_{1}' -f $matches[1],$matches[2])
        } else { 'unknown' }
      }
    } | Sort-Object Class,Name
}
$report=[ordered]@{
  collected_utc = (Get-Date).ToUniversalTime().ToString('o')
  mode = 'read-only; no physical slot / NVMe protocol attestation'
  pci_devices = $allPCI
  present_storage_devices = Safe-Read {
    Get-PnpDevice -PresentOnly |
      Where-Object { $_.Class -in @('DiskDrive','SCSIAdapter','HDC','StorageController') -or $_.FriendlyName -match '(?i)NVMe|NVM Express|Rapid Storage|RAID|SATA Controller' } |
      Select-Object Class,FriendlyName,Status
  }
  problematic_present_devices = Safe-Read {
    Get-CimInstance Win32_PnPEntity |
      Where-Object { $_.ConfigManagerErrorCode -ne 0 -and $_.Present } |
      Select-Object Name,PNPClass,Status,ConfigManagerErrorCode
  }
  storage_driver_versions = Safe-Read {
    Get-CimInstance Win32_PnPSignedDriver |
      Where-Object {
        $_.DeviceClass -in @('SCSIAdapter','HDC','DiskDrive','StorageController') -or
        $_.DeviceName -match '(?i)NVMe|NVM Express|Rapid Storage|RAID|SATA|Storage Controller'
      } |
      Select-Object DeviceName,DeviceClass,DriverProviderName,DriverVersion,InfName
  }
  disk_models = Safe-Read {
    Get-CimInstance Win32_DiskDrive | Select-Object Index,Model,InterfaceType,Size,Status
  }
}
$report | ConvertTo-Json -Depth 7
# If no PCI device representing a second SSD is found, Windows cannot prove whether it is dead,
# SATA-in-NVMe-only, proprietary/incompatible, unseated, firmware-hidden or hardware-faulted.
