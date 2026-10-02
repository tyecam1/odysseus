# Backup & Restore

Odysseus keeps all of your state in the `data/` directory — the SQLite database
(`app.db`), the Fernet encryption key (`data/.app_key`), the vault, memory, RAG
indexes, personal documents, and uploads. The `scripts/odysseus-backup` tool
snapshots that directory into a single gzip tarball and restores it later.

Snapshots are safe to take while the app is running: SQLite databases are copied
through SQLite's own `.backup` API rather than a raw file copy, so an in-flight
write can't corrupt the snapshot.

> **A snapshot contains your secrets.** The tarball includes the Fernet
> encryption key (`data/.app_key`), the vault, sessions, and any stored
> provider/API tokens — so treat it like a password. Store backups somewhere
> private, never commit them to Git, and prefer an encrypted destination when
> copying them offsite.

## Which directory is backed up

The tool snapshots and restores the runtime's own data directory: `ODYSSEUS_DATA_DIR` when that variable is set (the
variable `src/constants.py` reads, and the one the Windows household deployment sets through
`odysseus-host.ps1 -DataRoot`), otherwise `data/` in the repository. The tarball layout is always `data/...`, whatever
the directory is called, so a tarball from one layout restores into the other. Run the tool with the same environment the
app runs with: a snapshot taken without `ODYSSEUS_DATA_DIR` on a host that sets it would capture the checkout's own
`data/` instead of the live data.
## Quick start

Run the tool from the repository root:

```bash
# Create a snapshot → backups/odysseus-backup-<YYYYMMDD-HHMMSS>.tar.gz
./scripts/odysseus-backup snapshot

# List existing snapshots (most recent first)
./scripts/odysseus-backup list

# Check a tarball's integrity without extracting it
./scripts/odysseus-backup verify backups/odysseus-backup-20260101-120000.tar.gz

# Restore (destructive — see the warning below)
./scripts/odysseus-backup restore backups/odysseus-backup-20260101-120000.tar.gz --yes
```

The script depends only on the Python standard library, so any `python3` on your
`PATH` will run it — you don't need the app's virtualenv active.

Every command prints a JSON result. Add `--pretty` for indented output.

## Commands

### `snapshot`

Writes a `tar.gz` of `data/` to `backups/<timestamp>.tar.gz`.

| Flag | Effect |
| --- | --- |
| `--out PATH` | Write to a specific path instead of the default `backups/` location. Must be **outside** `data/`. |
| `--include-research` | Include `data/deep_research/` (skipped by default — research runs are large). |
| `--include-attachments` | Include `data/mail-attachments/` (skipped by default — cached IMAP extractions, re-derivable). |

By default the snapshot includes everything under `data/` **except**
`deep_research/` and `mail-attachments/`. Personal uploads and documents are
included.

```bash
# Snapshot straight to a mounted NAS path
./scripts/odysseus-backup snapshot --out /mnt/nas/odysseus-$(date +%F).tar.gz

# Full snapshot including research runs and mail attachments
./scripts/odysseus-backup snapshot --include-research --include-attachments
```

### `list`

Lists the tarballs in `backups/`, most recent first, with size and modification
time.

### `verify PATH`

Opens the tarball read-only and walks every member to confirm it is intact and
safe to restore. Nothing is extracted. Use this before relying on an old backup
or after copying one across machines.

### `restore PATH --yes`

Overwrites `data/` from a tarball.

> **Restore is destructive.** It replaces the current `data/` directory. `--yes`
> is required so a mistyped command can't wipe your live state.

Restore is not a blind delete: before extracting, the tool **renames your current
`data/` to `data.before-restore-<timestamp>`** next to it (in the repository root for the default layout; beside the directory as
`<name>.before-restore-<timestamp>` when `ODYSSEUS_DATA_DIR` names another one). If a restore
turns out to be wrong, your previous state is still there — delete the
restored `data/` and rename the stashed directory back. The restore path is also
validated entry-by-entry: archives containing absolute paths, `..` segments,
symlinks, or anything outside `data/` are rejected.

## Scheduling offsite backups

The tarball output composes cleanly with cron and any copy tool. For example, a
nightly snapshot copied offsite:

```cron
0 3 * * *  cd /path/to/odysseus && ./scripts/odysseus-backup snapshot --out "/mnt/nas/odysseus-$(date +\%F).tar.gz"
```

Swap the `--out` target for `scp`, `rclone`, `s3cmd`, or similar to push the
snapshot to remote storage.

## Docker vs native installs

The tool reads `data/` and writes `backups/` relative to the repository root, so
where you run it matters:

- **Native installs** — run it from the repo root as shown above. `data/` and
  `backups/` are both in the repo directory.
- **Docker** — `docker-compose.yml` bind-mounts the host's `./data` to
  `/app/data`, so the live data is also present on the host. **Run the tool on
  the host** from the repo root; the snapshot reads the bind-mounted `./data` and
  writes to `./backups` on the host. Running it *inside* the container is not
  recommended, because `backups/` is not a mounted volume and the tarball would
  be lost when the container is recreated.

> **ChromaDB caveat (Docker only).** In the Docker setup, ChromaDB stores its
> vectors in a separate Compose-managed volume (declared as `chromadb-data`),
> **not** under `./data`. `odysseus-backup` therefore does not capture the Docker
> ChromaDB store. Back it up separately if you need it. Compose prefixes the
> volume with the project name, so find the real name first
> (`docker volume ls | grep chromadb`), then archive it — for example:
>
> ```bash
> docker run --rm -v <project>_chromadb-data:/data -v "$PWD":/backup \
>   alpine tar czf /backup/chromadb.tar.gz -C /data .
> ```
>
> On native installs ChromaDB lives at `data/chroma/` and is included in the
> snapshot normally.

## Windows scheduled task (household host)

`scripts/windows/odysseus-backup-task.ps1` runs the tool on a schedule on Windows. It chooses **no destination and no
key**: both are parameters, and with neither the run is a local, same-disk snapshot.

| `-Action` | Effect |
| --- | --- |
| `Run` | Snapshot (the tool verifies it and writes the manifest), optionally copy to `-DestinationDir` and re-check the sha256 there, prune staging and destination, write `backup-status.json`. Exits 1 and records the error on any failure. |
| `Install` | Register a daily task (default 02:30) that runs `Run` with the same parameters. Supports `-WhatIf`. Registers nothing unless asked. |
| `Uninstall` | Remove the task; backups stay. |
| `Status` | Print `backup-status.json`; exit 2 if the last run failed or is older than `-MaxAgeHours` (default 36), so a monitor can alert on it. |

Guard rails: copying to `-DestinationDir` without `-RecipientsFile` (age encryption) is refused unless
`-AllowUnencryptedDestination` is passed, because a snapshot contains household speech and the Fernet key; every copy is
re-checked against the manifest sha256; `cache`, `tts_cache`, `stt-tmp` and `models` are excluded unless
`-IncludeRebuildable`. The task runs as the current user with S4U logon (no stored password, no network credentials), so a
UNC destination needs a task you register yourself with a credential. The household runbook, including the open decisions
(destination, key custody, cadence) and the restore drill, is `docs/operations/backup-restore.md` in the Misumi repository.