"""Private local files for sensitive job state; no ACL assumptions on Windows.

Windows paths must already inherit a private DACL. We validate, never rewrite
an existing root/parent's ACL. An unsupported ACL fails closed. POSIX keeps
0700 directories, 0600 files and O_NOFOLLOW opens.
"""

from __future__ import annotations

import errno
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_OWNER_PLACEHOLDERS = frozenset({"S-1-3-4", "S-1-3-0"})  # OWNER RIGHTS, CREATOR OWNER


def _windows_private(path: Path, fd: int | None = None) -> None:
    """Inspect the real security descriptor (including inherited grants)."""
    import ctypes as c
    from ctypes import wintypes as w

    adv = c.WinDLL("advapi32", use_last_error=True)
    kernel = c.WinDLL("kernel32", use_last_error=True)
    ptr = c.c_void_p
    adv.GetNamedSecurityInfoW.argtypes = [w.LPWSTR, w.DWORD, w.DWORD, c.POINTER(ptr), ptr,
                                         c.POINTER(ptr), ptr, c.POINTER(ptr)]
    adv.GetNamedSecurityInfoW.restype = w.DWORD
    adv.GetSecurityInfo.argtypes = [w.HANDLE, w.DWORD, w.DWORD, c.POINTER(ptr), ptr,
                                    c.POINTER(ptr), ptr, c.POINTER(ptr)]
    adv.GetSecurityInfo.restype = w.DWORD
    adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)]
    adv.OpenProcessToken.restype = w.BOOL
    adv.GetTokenInformation.argtypes = [w.HANDLE, c.c_int, ptr, w.DWORD, c.POINTER(w.DWORD)]
    adv.GetTokenInformation.restype = w.BOOL
    adv.ConvertSidToStringSidW.argtypes = [ptr, c.POINTER(ptr)]
    adv.ConvertSidToStringSidW.restype = w.BOOL
    adv.GetAce.argtypes = [ptr, w.DWORD, c.POINTER(ptr)]
    adv.GetAce.restype = w.BOOL
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.LocalFree.argtypes = [ptr]
    kernel.LocalFree.restype = ptr

    def check(ok):
        if not ok:
            raise c.WinError(c.get_last_error())

    def sid_text(sid):
        result = ptr()
        check(adv.ConvertSidToStringSidW(sid, c.byref(result)))
        try:
            return c.wstring_at(result)
        finally:
            kernel.LocalFree(result)

    token = w.HANDLE()
    check(adv.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, c.byref(token)))  # TOKEN_QUERY
    try:
        size = w.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, c.byref(size))  # TokenUser
        buffer = c.create_string_buffer(size.value)
        check(adv.GetTokenInformation(token, 1, buffer, size, c.byref(size)))
        user = sid_text(c.cast(buffer, c.POINTER(ptr))[0])
    finally:
        kernel.CloseHandle(token)

    owner, dacl, descriptor = ptr(), ptr(), ptr()
    args = (1, 0x00000001 | 0x00000004, c.byref(owner), None,
            c.byref(dacl), None, c.byref(descriptor))  # SE_FILE_OBJECT, OWNER | DACL
    if fd is None:
        error = adv.GetNamedSecurityInfoW(str(path), *args)
    else:
        import msvcrt

        error = adv.GetSecurityInfo(msvcrt.get_osfhandle(fd), *args)
    if error:
        raise c.WinError(error)
    try:
        trusted = {user, "S-1-5-18", "S-1-5-32-544"}  # user, SYSTEM, Administrators
        if not owner or sid_text(owner) not in trusted or not dacl:
            raise PermissionError(f"private storage requires a trusted owner and DACL: {path}")

        class ACL(c.Structure):
            _fields_ = [("revision", w.BYTE), ("reserved", w.BYTE), ("size", w.WORD),
                        ("count", w.WORD), ("reserved2", w.WORD)]

        for index in range(c.cast(dacl, c.POINTER(ACL)).contents.count):
            ace = ptr()
            check(adv.GetAce(dacl, index, c.byref(ace)))
            ace_type = c.cast(ace, c.POINTER(w.BYTE))[0]
            if ace_type == 1:  # ACCESS_DENIED_ACE cannot disclose state
                continue
            # Only ordinary allow/deny ACEs are supported. Unknown/callback/
            # object grants must not accidentally bypass the privacy check.
            if ace_type != 0:
                raise PermissionError(f"unsupported private storage ACL: {path}")
            mask = c.cast(ace.value + 4, c.POINTER(w.DWORD))[0]
            # OWNER RIGHTS (S-1-3-4) and CREATOR OWNER (S-1-3-0) name "whoever owns this object". CPython's mkdir(mode=0o700) writes an OWNER RIGHTS
            # allow ACE into the protected DACL it creates, so without this a directory created here was rejected by its own validator. They are
            # exactly as private as the owner, which was verified above to be the user, SYSTEM or Administrators.
            if mask and sid_text(ace.value + 8) not in trusted | _OWNER_PLACEHOLDERS:
                raise PermissionError(f"private storage grants access outside user/SYSTEM/Administrators: {path}")
    finally:
        kernel.LocalFree(descriptor)


def check_private_path(path: Path) -> None:
    """Refuse links/reparse points; on Windows also require a private DACL."""
    path = path.absolute()
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise PermissionError(f"private storage refuses symlink/reparse path: {path}")
    if os.name == "nt":
        _windows_private(path)


def private_dir(path: Path) -> None:
    path = path.absolute()
    if not path.exists():
        # Validate before creating anything on Windows: mode=0700 does not
        # protect a new directory that inherits a shared parent's DACL.
        if os.name == "nt":
            private_dir(path.parent)
        path.mkdir(parents=os.name != "nt", mode=0o700, exist_ok=True)
    check_private_path(path)
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    if os.name != "nt":
        path.chmod(0o700)
        if stat.S_IMODE(path.stat().st_mode) != 0o700:
            raise PermissionError(f"could not establish private directory: {path}")


@contextmanager
def private_file(path: Path, flags: int) -> Iterator[int]:
    """Open and validate before any sensitive I/O, closing on every failure."""
    private_dir(path.parent)
    if path.exists() or path.is_symlink():
        check_private_path(path)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    try:
        if os.name == "nt":
            _windows_private(path, fd)
        elif os.fstat(fd).st_uid != os.geteuid():
            raise PrivateStorageRefused(f"private state file must be owned by this user: {path}")
        elif hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        else:
            path.chmod(0o600)
        yield fd
    finally:
        os.close(fd)


class PrivateStorageRefused(PermissionError):
    """A privacy/link refusal (symlink, reparse point, wrong owner or permissions, broad ACL). It is NOT corruption: callers must not "recover" it."""


def read_private_bytes(path: Path) -> bytes:
    """Read a private state file, validating the object actually opened (not a pathname that could be swapped after a check).

    Raises FileNotFoundError when absent and PrivateStorageRefused for any privacy or link problem. The final component is refused if it is a
    symlink or reparse point (O_NOFOLLOW on POSIX, an lstat check on Windows) and the opened object must be the very object that was checked.
    POSIX also requires the opened file to be owned by this user, and Windows validates the handle's owner and DACL,
    so a file substituted by another principal through a renamed ancestor is refused rather than consumed."""
    path = Path(path)
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        raise
    if stat.S_ISLNK(before.st_mode) or getattr(before, "st_file_attributes", 0) & 0x400:
        raise PrivateStorageRefused(f"private storage refuses a symlink/reparse state file: {path}")
    try:
        check_private_path(path.parent)
    except PermissionError as exc:
        raise PrivateStorageRefused(str(exc)) from exc
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if getattr(exc, "errno", None) == errno.ELOOP:
            raise PrivateStorageRefused(f"private storage refuses a symlink state file: {path}") from exc
        raise
    try:
        opened = os.fstat(fd)
        if not os.path.samestat(before, opened):
            raise PrivateStorageRefused(f"private state file changed between check and open: {path}")
        if os.name == "nt":
            try:
                _windows_private(path, fd)
            except PermissionError as exc:
                raise PrivateStorageRefused(str(exc)) from exc
        elif opened.st_uid != os.geteuid():
            raise PrivateStorageRefused(f"private state file must be owned by this user: {path}")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(fd)
