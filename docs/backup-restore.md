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

# Check a tarball's integrity without extracting it (--deep also reads every member back and
# integrity-checks every SQLite database inside it)
./scripts/odysseus-backup verify backups/odysseus-backup-20260101-120000.tar.gz --deep

# Keep 7 daily / 4 weekly / 12 monthly snapshots (a dry run until --yes)
./scripts/odysseus-backup prune --dir backups

# Restore (destructive — see the warning below)
./scripts/odysseus-backup restore backups/odysseus-backup-20260101-120000.tar.gz --yes
```

The script depends only on the Python standard library, so any `python3` on your
`PATH` will run it — you don't need the app's virtualenv active. Encryption
(`--encrypt-recipients`) is the one optional exception: it calls the external
[`age`](https://github.com/FiloSottile/age) binary, and fails closed if it is missing.

Every command prints a JSON result. Add `--pretty` for indented output.

## Commands

### `snapshot`

Writes a `tar.gz` of `data/` to `backups/<timestamp>.tar.gz`.

| Flag | Effect |
| --- | --- |
| `--out PATH` | Write to a specific path instead of the default `backups/` location. Must be **outside** `data/`. |
| `--include-research` | Include `data/deep_research/` (skipped by default — research runs are large). |
| `--include-attachments` | Include `data/mail-attachments/` (skipped by default — cached IMAP extractions, re-derivable). |
| `--exclude NAME` | Skip a top-level `data/` directory by name, or a path prefix such as `skills/cache`. Repeatable. A bare name matches only the top level, so a nested folder that merely shares the name is kept. |
| `--exclude-rebuildable` | Skip the directories that are re-created on demand and are never the only copy of anything: `cache`, `tts_cache`, `stt-tmp`, `models`. Vector and RAG indexes are deliberately **not** in this list: exclude them yourself (`--exclude chroma`) once a rebuild from the canonical sources has been proven. |
| `--encrypt-recipients FILE` | Encrypt with `age -R FILE` and write `<name>.tar.gz.age`. The plaintext tarball is built in a temporary directory and never exists at the output path. Fails closed (writes nothing) if `age` is not installed or the file is missing. |

By default the snapshot includes everything under `data/` **except**
`deep_research/` and `mail-attachments/`. Personal uploads and documents are
included.

```bash
# Snapshot straight to a mounted NAS path
./scripts/odysseus-backup snapshot --out /mnt/nas/odysseus-$(date +%F).tar.gz

# Full snapshot including research runs and mail attachments
./scripts/odysseus-backup snapshot --include-research --include-attachments
```

#### Self-verification and the manifest

A snapshot is not reported as written until it has been read back: every member is read (so truncation and CRC damage
surface) and every SQLite database in it gets `PRAGMA integrity_check`. A snapshot that fails is **deleted** and the
command exits non-zero, so a damaged file can never sit in `backups/` looking like a good one. A real SQLite database is
copied with SQLite's `.backup` API only: if that fails (for example `database is locked`) the snapshot fails rather than
falling back to a raw byte copy, which for a live database can be torn. A stray non-SQLite `*.db` file is copied as bytes.

Beside each snapshot the tool writes `<snapshot>.manifest.json`: the archive's sha256 and size, the host and data
directory it came from, what was excluded, whether it is encrypted (with the plaintext sha256), and for every database its
integrity result and **per-table row counts**. A restore drill can therefore prove parity against the manifest instead of
against memory. `list` hides manifests; `prune` removes them with their snapshot.

### `list`

Lists the tarballs in `backups/`, most recent first, with size and modification
time.

### `verify PATH`

Opens the tarball read-only and walks every member to confirm it is intact and
safe to restore. Nothing is extracted. Use this before relying on an old backup
or after copying one across machines. If a manifest sits beside the archive its
sha256 is checked, and a mismatch (corruption, or modification since it was
written) is refused.

| Flag | Effect |
| --- | --- |
| `--deep` | Also read every member back and integrity-check every SQLite database, reporting each one. |
| `--decrypt-identity FILE` | For a `.age` archive, decrypt it (via `age -d -i FILE`) to a temporary file to verify its contents. Without `--deep` an encrypted archive is only checked against its manifest checksum, and the output says so. |

### `restore PATH --yes`

Overwrites `data/` from a tarball.

> **Restore is destructive.** It replaces the current `data/` directory. `--yes`
> is required so a mistyped command can't wipe your live state.

The archive is verified **before** `data/` is touched: members, checksum against its manifest, and every database's
integrity. A restore of a damaged archive is refused with nothing changed (no stash is even made). Pass
`--decrypt-identity FILE` for a `.age` archive. If extraction itself fails part-way, the error names where the intact
previous data is.

Restore is not a blind delete: before extracting, the tool **renames your current
`data/` to `data.before-restore-<timestamp>`** next to it (in the repository root for the default layout; beside the directory as
`<name>.before-restore-<timestamp>` when `ODYSSEUS_DATA_DIR` names another one). If a restore
turns out to be wrong, your previous state is still there — delete the
restored `data/` and rename the stashed directory back. The restore path is also
validated entry-by-entry: archives containing absolute paths, `..` segments,
symlinks, or anything outside `data/` are rejected.

### `prune --dir DIR`

Keeps the newest snapshot of each of the last `--keep-daily` days (default 7), `--keep-weekly` ISO weeks (4) and
`--keep-monthly` months (12), and deletes the rest together with their manifests. `--all` deletes **every** snapshot (the newest too; see "Deleting data and backups"). Only files named exactly
`odysseus-backup-YYYYMMDD-HHMMSS.tar.gz[.age]` are ever considered; anything else in the directory is left alone. The
newest snapshot is always kept, even with every count set to 0. It is a **dry run** (it prints `would_delete`) unless
`--yes` is passed. Deleting a backup is permanent, and a deletion made on the live system reaches backups only when they
age out of this schedule.

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
| `Invalidate` | Honour a deletion: delete **every** snapshot and manifest in `-StagingDir` and `-DestinationDir`, then take and verify a fresh snapshot. Supports `-WhatIf`. |
| `Uninstall` | Remove the task; backups stay. |
| `Status` | Print `backup-status.json`; exit 2 if the last run failed or is older than `-MaxAgeHours` (default 36), so a monitor can alert on it. |

Guard rails: the destination must not be a **fixed disk on this host** (that is not disaster recovery; refused unless
`-AllowLocalDestination`); `-RecipientsFile` must hold **public** recipients only (a file containing an `AGE-SECRET-KEY` is
refused by the task and by the tool); copying to `-DestinationDir` without `-RecipientsFile` (age encryption) is refused unless
`-AllowUnencryptedDestination` is passed, because a snapshot contains household speech and the Fernet key; every copy is
re-checked against the manifest sha256; `cache`, `tts_cache`, `stt-tmp` and `models` are excluded unless
`-IncludeRebuildable`. The task runs as the current user with S4U logon (no stored password, no network credentials), so a
UNC destination needs a task you register yourself with a credential. The household runbook, including the open decisions
(destination, key custody, cadence) and the restore drill, is `docs/operations/backup-restore.md` in the Misumi repository.

## Deleting data and backups

A deletion of live data is not complete while older backups still hold it. The simple mechanism, appropriate while the data is
small:

1. delete from the live archive (for transcripts: `POST /misumi/transcript/delete`, see `docs/misumi-durable-transcript-runtime.md`);
2. invalidate the backups that can contain it: `odysseus-backup prune --dir DIR --all --yes` (dry run without `--yes`), or the
   Windows task's `-Action Invalidate` (staging and destination);
3. take and verify a fresh encrypted snapshot (`Invalidate` does this after deleting).

Until that has been done, state honestly that a live deletion **remains recoverable from older encrypted backups** until they
age out of the retention schedule. Invalidation deletes every snapshot at the destination, so the destination is briefly
without a verified snapshot (seconds to minutes, until the fresh one is written and verified): run it deliberately, not from a
schedule.

## Key custody

The age **private identity** is generated by the operator and never by this host. It is held in a personal password manager
(primary) and an offline recovery copy kept separately, and is never stored in Git, on the home host beside the snapshots, or at
the backup destination. The host holds only the public recipient file. Both the tool and the Windows task refuse a recipients
file containing an `AGE-SECRET-KEY`. A restore drill must decrypt using only the offline copy.
