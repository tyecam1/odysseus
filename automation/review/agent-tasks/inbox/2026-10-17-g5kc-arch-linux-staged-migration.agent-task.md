---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-17-g5kc-arch-linux-staged-migration
title: "Gigabyte G5 KC: diagnose spare Mac SSD, procure storage, and migrate laptop to Arch Linux"
status: inbox
priority: medium
task_type: host-migration
created_by: chatgpt
created_at: 2026-10-17T17:00:00+01:00
executor: ""
execution_mode: gated-human-assisted
architecture: single
architecture_rationale: "One host migration with explicit physical and destructive gates. Delegate independent read-only SSD research and test verification, not competing installers or a new control plane."
single_agent_baseline: "A single implementation agent inventories the laptop, produces deterministic manifests and install configuration, pauses for each physical/data-destruction approval, then configures and verifies Arch after human bootstrapping."
execution_host: laptop
context_budget: high
coordination_reason: "An existing Odysseus/Aoteru laptop client and estate routing must remain usable. Migration is host-local; shared execution remains Odysseus-owned. Other machines must not be affected."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/agent-tasks/**
  - docs/**
  - companion/laptop_client/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/id_*"
  - config/estate.yaml
  - config/models.yaml
inputs:
  - docs/aoteru-repository-ownership-trajectory.md
  - docs/aoteru-laptop-activation-closeout.agent-task.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/aoteru-p13-laptop-reentry-evidence.md
outputs:
  - read-only hardware and SSD diagnosis with purchase/no-purchase decision
  - verified external backup and Windows rollback/recovery plan
  - reviewed Arch install configuration and post-install automation scripts
  - separately bootable Arch on a verified second drive
  - application, PhD/robotics and Odysseus-client restore/verification report
result_path: ""
review_report_path: ""
handoff_model: independent-human-gate-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Do not run a destructive installer overnight unattended. First diagnose Mac SSD and verify spare M.2 slot. This record is work intake, not installation approval. Do not create a second agent-task runtime. Avoid including laptop personal data, secrets or raw disk serial numbers in this public repository."
---

# G5 KC Arch Linux migration: staged, reversible work item

## Decision and objective

- **Operator decision:** Arch Linux as the target operating system; KDE Plasma as initial desktop.
- **Host:** Gigabyte G5 KC; known prior inventory: Intel Core i5-10500H, NVIDIA RTX 3060 Laptop GPU, Windows on an approximately 477 GB disk. Treat these as previously reported, not an up-to-date live attestation.
- **Storage design:** target a *second, independently bootable* internal M.2 2280 NVMe SSD; preserve Windows and its existing drive intact. No in-place conversion of the Windows system.
- **Immediate priority:** diagnose a spare SSD reportedly removed from a Mac. It was not detectable when previously tried; failure is **unconfirmed**. Do not purchase, repartition or discard it until connector, physical fit and enumeration have been assessed.
- **Purpose:** a stable native Arch workstation for research, coding, ROS 2 container workloads, Obsidian/Zotero, and the existing thin Aoteru/Odysseus client. Do not relocate Odysseus runtime, research authority or shared orchestration onto the laptop.
- **References:** Gigabyte G5 (RTX 30 Series) official specification lists two M.2 2280 slots, one NVMe PCIe/SATA and one NVMe PCIe, plus a 2.5-inch 7 mm SATA bay: https://www.gigabyte.com/us/Laptop/G5--RTX-30-Series/sp . These are model-family specifications; physical slot occupancy is not yet observed. Some older Apple SSDs have a proprietary connector; never infer failed silicon solely from non-enumeration in a PC.

## Operating and authority contract

1. Inspect the **live** Odysseus `dev` branch, this task, target machine, current repo instructions and eligible worker lanes. Run `aoteru preflight "<bounded operation>" --repo odysseus` or the canonical API equivalent before substantive routed work. If inaccessible, record the reason and continue only authorised read-only planning.
2. Never create a new scheduler, task queue, router, host identity or agent orchestration stack. Keep domain files in their existing canonical repos/storage. Follow Odysseus estate routing, credential, lease and execution controls.
3. Progress only through explicit gates. Agents may prepare, inspect, simulate, package, configure, verify and report autonomously *inside the currently approved gate*. They must not infer human consent to erase/repartition devices or relax security from an instruction to work overnight.
4. The human must physically approve case opening/drive insertion, firmware/boot changes, any action affecting encryption or Secure Boot, and the exact target disk and destructive write immediately before installation. A lost agent connection at reboot is expected and must not be disguised as a completed migration.
5. Keep detailed private machine inventory, identifiers, personal data, drive serial numbers, key material, recovery codes and absolute personal paths **out of Git**. Commit only sanitised receipts, non-secret manifests and reusable scripts. Preserve any needed sensitive evidence in the operator-approved secure local storage.
6. Do not touch lab Jetson, CPI devices, Windows home worker, interface PC, or other host deployments. Do not perform an unrequested firmware flash, account migration or security policy change.

## Phase 0: establish real machine and disk truth (read-only)

- Record current Windows edition, laptop model/SKU, CPU, GPU, RAM, UEFI mode, Secure Boot state, BitLocker/device-encryption state, partition layout, storage-controller mode (including Intel RST/VMD), disks, volumes and free space, installed device drivers, firmware, Wi-Fi/Bluetooth chipset, monitor setup, connected accessories and battery health.
- Cross-check Windows `Get-PhysicalDisk`, `Get-Disk` and `Get-Partition` against BIOS/UEFI storage listing. Read-only PowerShell examples:
  ```powershell
  Get-CimInstance Win32_ComputerSystem | Select Manufacturer,Model,TotalPhysicalMemory
  Get-Disk | Select Number,FriendlyName,BusType,Size,PartitionStyle,OperationalStatus
  Get-PhysicalDisk | Select FriendlyName,MediaType,BusType,HealthStatus,Size
  Get-Partition | Select DiskNumber,PartitionNumber,DriveLetter,Type,Size
  Confirm-SecureBootUEFI
  Get-BitLockerVolume | Select MountPoint,ProtectionStatus,VolumeStatus
  ```
- If any command requires elevation or errors, capture the failure without assuming the corresponding hardware/feature is absent.
- Inspect service manual, existing free slot, screw/standoff, existing M.2 key/length and thickness clearance (single/double sided, **no oversized heatsink**). Confirm that the second M.2 slot is physically empty before ordering.
- Snapshot critical user workflows: Obsidian vault Git state and untracked content; Zotero database and attachment storage; ROS 2 distributions/toolchains/containers; Python/Conda/venvs; CUDA/graphics; SSH/Tailscale; audio/music hardware and software; local work, games and licences; university VPN/Microsoft applications; backups. Classify native, containerised, web, Wine/VM, or must-retain-Windows. Identify blockers *before* operating-system selection is treated as irreversible.
- **Gate 0:** sign off a read-only, sanitised inventory; no changes to disk topology.

## Phase 1: diagnose spare Apple/Mac SSD (read-only by default)

1. Obtain a photograph of **both sides** showing connector and printed part/model number, plus length and any adapter, or an accurate transcription of these identifiers. Do not publish full serial numbers.
2. Identify whether the device is a standard M.2 2280 NVMe, M.2 SATA, Apple proprietary blade form, SATA, or some other module. Identify donor Mac generation only from actual label/connector evidence, not an assumption that all Mac SSDs are interchangeable.
3. If proprietary: select a *verified appropriate* Apple-to-PC adapter/enclosure only if the cost is justified; confirm direction of adapter, physical clearance and electrical protocol. A common PC M.2 slot or USB NVMe enclosure cannot read every Apple SSD unadapted.
4. If standard and mechanically compatible: test with power off and suitable ESD handling in the confirmed free slot, or with a known-good **protocol-matched** enclosure. Inspect BIOS enumeration and `Get-Disk` / Disk Management (or Linux live `lsblk -o NAME,SIZE,MODEL,TRAN` and `nvme list`) without initialising, formatting or writing to the device.
5. Distinguish: (a) device enumerates, filesystem merely not mountable in Windows, (b) incompatible connector/protocol/enclosure or adapter, (c) loose/contact/slot fault, (d) actual likely device failure. If enumerating, capture SMART/NVMe health read-only and check capacity. Testing another known-good device/adapter may be necessary to substantiate (d).
6. If ownership/data rights are unclear, don't attempt decryption or data recovery. Prior report says the content is not needed; still require explicit erase permission before repurposing.
7. **Gate 1:** one of `REUSE VERIFIED`, `ADAPTER TEST JUSTIFIED`, `BUY REPLACEMENT`, or `INCONCLUSIVE`, with evidence and lowest-cost next action. Never call the Mac SSD broken solely because Windows does not show a drive letter.

## Phase 2: storage procurement only if needed

- **Required:** standard internal M.2 2280 **NVMe PCIe** (PCIe 3.0 or backward-compatible 4.0), a bare drive without a tall/heavy heatsink; genuine vendor, warranty and return rights; sufficient capacity. Reject M.2 SATA-only for the NVMe-only slot, M.2 2230 unadapted, proprietary Apple blade, and 2.5-inch SATA if buying specifically for the free M.2 NVMe slot.
- **Capacity choice:** 1 TB sufficient for initial Arch + workstation tooling; consider 2 TB if local datasets, media, container images and dual-environment assets materially require it. Don't spend to chase advertised PCIe 4.0/5.0 peak sequential speeds where the laptop is the bottleneck.
- Compare real current UK retailer listings with **dated** prices, in-stock status, VAT/delivery and return terms, rather than relying on historical snippets. Consider sustained write, thermals, NAND endurance, reliability and value; note model substitutions/revisions.
- Illustrative candidates to re-price at purchase time: Lexar NM620 1 TB (PCIe 3.0), Kingston NV3 1 TB (budget Gen4), WD Black SN7100 1 TB, Crucial P310 2 TB **without heatsink**. Do not pre-authorise any purchase.
- **Gate 2:** operator selects budget and exact SSD model, seller, capacity and installed destination slot; record `purchased` only after actual order.

## Phase 3: preservation and rollback

- Create an independent, offline or external backup of every irreplaceable Windows file, including untracked/uncommitted repositories, Zotero `zotero.sqlite` + `storage`, Obsidian attachments/config, local secrets/keys transferred securely, MFA/recovery arrangements, project files and software licences. A Git remote alone is **not** a complete backup.
- Verify the backup by checksum/sample restore plus a whole critical-directory manifest; do not rely solely on a completed copy command. Record backup location privately, not Git.
- Save the BitLocker recovery key through an approved **private** channel if Windows encryption is enabled. Record current firmware settings. Prepare and test Windows recovery media and an Arch installer/rescue USB.
- Identify how to boot *either* drive independently via UEFI firmware boot menu. Prefer independent EFI System Partitions on separate physical drives, with clear identification of destination disk by model/capacity and verified serial prefix only in the private approval screen. Do not place Arch boot files on the Windows ESP without an explicit reason and approval.
- Prepare an operational rollback: choose Windows boot in UEFI, physically remove/disable Arch drive if necessary, restore firmware settings, and demonstrate Windows starts with files intact.
- **Gate 3:** verified restore sample, Windows recovery path, spare storage destination and explicit data-loss approval for the **new target drive only**. If any check fails, STOP.

## Phase 4: pre-build Arch configuration (non-destructive preparation)

- Use official current Arch installation guidance and pin a verified installer ISO/signature; propose guided `archinstall` config or equivalent reproducible declarative steps. Install **Arch Linux**, not an Arch derivative.
- Default desktop: KDE Plasma/Wayland; default network: NetworkManager. Choose one coherent bootloader route for an independent disk (prefer systemd-boot on UEFI after compatibility review). Disk: GPT with independent EFI partition and Linux system; choose filesystem/backup plan consciously, e.g. Btrfs + tested snapshots if this does not add unjustified maintenance, otherwise ext4 with verified backup/restore.
- Recommend full-disk LUKS2 encryption for personal/research files, but operator must explicitly approve encryption and securely retain recovery credentials. Never generate/store plaintext passphrases in a repository or runtime logs.
- Review hardware-specific paths: Intel/NVIDIA hybrid graphics, proprietary/open NVIDIA module compatibility with *current* Arch packages, DKMS/kernel matching, Secure Boot policy, display brightness and refresh, Wi-Fi, Bluetooth, webcam, audio, microphone, headphone jack, touchpad, keyboard backlight/fan/thermal controls, power management, external monitors, suspend/resume.
- Prepare a short verified first-boot install manifest with explicit dependencies and package sources; pin package choices to live Arch documentation, not historical guessed package names. AUR packages are optional, untrusted and separately reviewed. Set sensible update and recovery discipline for a rolling distro (e.g. linux-lts fallback, pacman caches and recovery media).
- Recreate research environment minimally: Git + SSH agent, Python/uv or venv, Docker/Podman only where warranted, ROS 2 **Jazzy Ubuntu 24.04 container** and **Humble Ubuntu 22.04 container** as needed rather than representing Arch as an officially supported binary target; GPU/USB/udev/RealSense pass-through tests; CUDA/containers only if a real workload needs them. Avoid disturbing Jetson/lab ROS nodes.
- Plan an independent thin Aoteru/Odysseus client using existing documented laptop-client and Tailscale route, not a local backend duplication. Confirm executable packaging, credentials and host identity implications of the OS change; keep private tokens off Git.
- **Gate 4:** independent review of generated installation and recovery plan including all destructive commands; obtain operator's exact-device authorisation.

## Phase 5: human-assisted installation, then bounded unattended configuration

1. Operator physically installs the verified SSD, inserts verified Arch boot USB and selects it in UEFI. Any firmware changes are explicitly reviewed.
2. Boot installer. **Pause immediately before partition/format** and show destination disk model, size and partition paths alongside preserved Windows disk details. A second independent confirmation of the **exact target device** is mandatory.
3. Installer formats **only the approved new target**. No erase, resize, reformat, `wipefs`, `dd`, `sgdisk --zap-all` or filesystem creation on the Windows disk. No automatic EFI change to Windows.
4. Finish base Arch installation, boot into the new system and verify Arch and Windows both boot independently.
5. After Linux networking and private agent credentials are authenticated manually, agent can execute bounded post-install configuration unattended **without sudo-all privileges**. Use privilege separation for package/configuration operations, a transaction log and explicit permit lists for changes. Stop for new escalations.
6. Observe/reconnect only via existing authorised channel. Do not treat the inevitable reboot disconnect as success or automatically retry the installer.
7. **Gate 5:** two-OS boot verification and no unintended Windows disk writes.

## Phase 6: verification, restoration, cutover

- Test desktop stability with RTX 3060/hybrid display, battery/AC power, suspend/resume cycles, external display, peripherals, camera, audio, Wi-Fi/Bluetooth, VPN, disk encryption recovery and package update/reboot.
- Restore personal/research work **from verified backup or authoritative remote** without losing untracked files. Verify Git/Obsidian/Zotero cross-platform sync and correct attachment/database locations; ensure no double-writer Zotero/Obsidian corruption.
- Run relevant ROS 2 container builds, camera discovery and **bounded** RealSense capture test if hardware present; confirm USB/udev permissions and NVIDIA GPU workloads; record remaining unsupported packages transparently.
- Reconnect the laptop Aoteru thin client to *existing* Odysseus estate only; test `aoteru status`, routing, bounded read-only ask and session state. Confirm that the OS transition did not inadvertently change authority or deploy a competing backend.
- Verify research/publication software compatibility, university access, backups, screen locking, package maintenance and rollback access. Record a small list of Windows-only applications and whether Windows remains a necessary fallback.
- **Acceptance:** Arch boots independently; all critical work recoverable and usable; Windows unchanged and bootable; critical device drivers operational; major workflows tested; backups functional; no secret published; issues tracked with owners; any known unmet criterion explicitly visible. No premature claim of a complete migration.

## Stop conditions and escalation

Stop immediately upon: unknown actual drive identity/slot, ambiguous Mac SSD connector/protocol, unverified backup, uncertain Windows encryption/recovery, installer targeting wrong disk, destructive permission not current, GPU/display instability without recovery path, bootloader changes to Windows ESP, or lost authorisation. Preserve logs privately; produce an exact one-action human handoff and continue only after approval.

Never promise that an unattended overnight installation can safely manage physical storage, UEFI prompts or reboots. Overnight automation starts only **after first successful Linux boot** and is limited to reviewed software setup/tests.

## Immediate next operator evidence

1. Photograph of the gifted Mac SSD **including its connector and model label** (serial masked).
2. Read-only Windows storage inventory/UEFI visibility for the Mac SSD, and confirmation of the free M.2 slot.
3. Whether the user prefers 1 TB or 2 TB *only after* determining that Mac SSD reuse is not practical.

## Closure record

Record phase/gate outcome, evidence date, host hardware summary without serial numbers, new drive make/model, exact installer method, source commits, validation commands/results, remaining blockers, rollback proof, and the operator's decisions. Store no sensitive inventory, keys or filesystem user data in this public repo. Change this task's status only when justified by actual gate evidence.
