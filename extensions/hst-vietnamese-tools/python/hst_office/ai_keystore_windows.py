# SPDX-License-Identifier: AGPL-3.0-only
"""Windows Credential Manager (advapi32 CredWriteW/CredReadW/CredDeleteW through ctypes) for the AI API keys.

One generic credential per provider, target "HSTOffice/AI/<provider>", persisted for this Windows user on this
machine (CRED_PERSIST_LOCAL_MACHINE: protected by the user's logon, not roamed). Local only, never the network.
"""
import ctypes
from ctypes import wintypes

LABEL = "Trình quản lý thông tin xác thực Windows"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR), ("LastWritten", _FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]


def _api():
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIAL), wintypes.DWORD]
    advapi.CredWriteW.restype = wintypes.BOOL
    advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))]
    advapi.CredReadW.restype = wintypes.BOOL
    advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi.CredDeleteW.restype = wintypes.BOOL
    advapi.CredFree.argtypes = [ctypes.c_void_p]
    advapi.CredFree.restype = None
    return advapi


def _target(provider):
    return "HSTOffice/AI/" + provider


class Store:
    label = LABEL

    def __init__(self):
        self.api = _api()

    def get(self, provider):
        found = ctypes.POINTER(_CREDENTIAL)()
        if not self.api.CredReadW(_target(provider), CRED_TYPE_GENERIC, 0, ctypes.byref(found)):
            if ctypes.get_last_error() == ERROR_NOT_FOUND:
                return None
            raise OSError("CredReadW failed")
        try:
            cred = found.contents
            return ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize).decode("utf-8")
        finally:
            self.api.CredFree(found)

    def set(self, provider, key):
        blob = key.encode("utf-8")
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        cred = _CREDENTIAL(Type=CRED_TYPE_GENERIC, TargetName=_target(provider), Comment="HST Office: Trợ lý AI",
                           CredentialBlobSize=len(blob), CredentialBlob=buffer, Persist=CRED_PERSIST_LOCAL_MACHINE,
                           UserName="api-key")
        if not self.api.CredWriteW(ctypes.byref(cred), 0):
            raise OSError("CredWriteW failed")

    def delete(self, provider):
        if not self.api.CredDeleteW(_target(provider), CRED_TYPE_GENERIC, 0) \
                and ctypes.get_last_error() != ERROR_NOT_FOUND:
            raise OSError("CredDeleteW failed")
