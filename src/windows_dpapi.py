"""Windows DPAPI protect/unprotect for small secrets (the Spotify token file). Windows only; every other platform raises OSError.

Scope ``user`` (default) ties the blob to the Windows account that wrote it; scope ``machine`` lets any process on this machine decrypt (needed only if
a service logon cannot load the user's profile). The entropy is a fixed application label, not a secret.
"""

from __future__ import annotations

import os

_ENTROPY = b"misumi-spotify-v1"
CRYPTPROTECT_LOCAL_MACHINE = 0x4
CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _unavailable() -> OSError:
    return OSError("Windows DPAPI is not available on this platform")


def _blob(ctypes, data: bytes):
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data, len(data))
    return Blob, Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _call(function_name: str, data: bytes, flags: int) -> bytes:
    if os.name != "nt":
        raise _unavailable()
    import ctypes

    Blob, source, keep_source = _blob(ctypes, data)
    _, entropy, keep_entropy = _blob(ctypes, _ENTROPY)
    out = Blob()
    crypt32 = ctypes.windll.crypt32
    if function_name == "protect":
        ok = crypt32.CryptProtectData(ctypes.byref(source), "misumi-spotify", ctypes.byref(entropy), None, None, flags, ctypes.byref(out))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, ctypes.byref(entropy), None, None, flags, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI %s failed (error %d)" % (function_name, ctypes.GetLastError()))
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def scope_flags(scope: str = "user") -> int:
    if scope not in ("user", "machine"):
        raise ValueError("DPAPI scope must be 'user' or 'machine'")
    return CRYPTPROTECT_UI_FORBIDDEN | (CRYPTPROTECT_LOCAL_MACHINE if scope == "machine" else 0)


def protect(data: bytes, scope: str = "user") -> bytes:
    return _call("protect", data, scope_flags(scope))


def unprotect(blob: bytes, scope: str = "user") -> bytes:
    # a machine-scope blob decrypts with the same flag set; user-scope ignores the machine bit
    return _call("unprotect", blob, CRYPTPROTECT_UI_FORBIDDEN)
