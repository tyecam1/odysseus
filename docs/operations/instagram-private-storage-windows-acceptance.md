# Instagram private storage on Windows: acceptance evidence (#178)

Recorded 2026-10-27 on the home host (`DESKTOP-IN7O23D`, Windows, release `f5b032cdc05e`). Synthetic canaries only; no private export was read or written. Module under test: `src/private_state_io.py`.

## Automated tests on the real host
`tests/test_instagram_native_storage.py` in the release venv: 16 passed, 9 skipped. Every skip is POSIX-only (permissions, symlinks, `O_NOFOLLOW`); every Windows-specific test ran and passed (native acquisition state and append logs, shared-root and shared-file rejection without ACL rewrite, directories Python creates, cross-process lock timeout/recovery, identity change between check and open).

## Synthetic canary probe (9 of 9)
In a throwaway directory under the user's temp folder, then removed: a normal private directory and file are accepted; a junction as the directory is refused; a junction as an ANCESTOR of the state file is refused (`check_private_path` walks every parent for reparse points); reading through an ancestor junction is refused (`PrivateStorageRefused`); writing through an ancestor junction is refused and creates nothing in the junction target; a file symlink is refused; an Everyone read grant on a directory is refused and the ACL is not rewritten.

## Real directory permissions (metadata only)
`...\AppData\Local\Odysseus\Misumi\instagram` has inheritance disabled; owner Administrators; grants: OWNER RIGHTS full, SYSTEM full, Administrators full, the service account Modify. No ancestor (`C:\Users\User`, `AppData`, `Local`, `Odysseus`, `Misumi`) is a reparse point. Every ancestor grants rights only to SYSTEM, Administrators and the service account (plus a traverse-only AppContainer entry on `C:\Users\User`).

## Residual ancestor-rename / junction race
The review's residual (Sol, #182): a principal that can rename an ancestor could substitute a junction after the check. Renaming or deleting an ancestor needs delete rights on it or delete-child rights on its parent. On this host only SYSTEM, Administrators and the service account have them, and each of those can already read the private data. The race therefore needs a principal already inside the trust boundary and adds no new reach. Conclusion: directory-handle anchoring is not required for the current deployment and threat model. Limitation recorded: the check-then-use window remains, so any change that grants a lower-privileged principal rights on an ancestor (a shared parent, another account in the profile path, a relocated data root) must re-open this and implement handle anchoring first.
