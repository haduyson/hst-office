# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Linux desktop keyring (Secret Service through libsecret-1, ctypes) for the AI API keys.

GNOME Keyring, KWallet 6 and KeePassXC all serve the Secret Service: the key is kept in the user's default
collection, encrypted by the keyring, attributes {"application": "hst-office-ai", "provider": <provider>}.
Without libsecret or a running Secret Service the store is unavailable and ai_keystore falls back. Local D-Bus only,
never the network.
"""
import ctypes
import ctypes.util

LABEL = "Kho khóa của hệ thống (Secret Service)"
SCHEMA_NAME = b"vn.hasontech.hstoffice.AI"
APPLICATION = b"hst-office-ai"
ATTRIBUTE_STRING = 0
SCHEMA_DONT_MATCH_NAME = 2


class _Attribute(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("type", ctypes.c_int)]


class _Schema(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("flags", ctypes.c_int), ("attributes", _Attribute * 32),
                ("reserved", ctypes.c_int)] + [("reserved%d" % n, ctypes.c_void_p) for n in range(1, 8)]


class _GError(ctypes.Structure):
    _fields_ = [("domain", ctypes.c_uint32), ("code", ctypes.c_int), ("message", ctypes.c_char_p)]


def _load():
    name = ctypes.util.find_library("secret-1") or "libsecret-1.so.0"
    lib = ctypes.CDLL(name)
    glib = ctypes.CDLL(ctypes.util.find_library("glib-2.0") or "libglib-2.0.so.0")
    lib.secret_password_store_sync.restype = ctypes.c_int
    lib.secret_password_lookup_sync.restype = ctypes.c_void_p
    lib.secret_password_clear_sync.restype = ctypes.c_int
    lib.secret_password_free.argtypes = [ctypes.c_void_p]
    lib.secret_password_free.restype = None
    glib.g_error_free.argtypes = [ctypes.POINTER(_GError)]
    glib.g_error_free.restype = None
    return lib, glib


class Store:
    label = LABEL

    def __init__(self):
        self.lib, self.glib = _load()
        attributes = (_Attribute * 32)()
        attributes[0] = _Attribute(b"application", ATTRIBUTE_STRING)
        attributes[1] = _Attribute(b"provider", ATTRIBUTE_STRING)
        self.schema = _Schema(name=SCHEMA_NAME, flags=SCHEMA_DONT_MATCH_NAME, attributes=attributes)

    def _check(self, error, what):
        if error:
            self.glib.g_error_free(error)
            raise OSError("libsecret %s failed" % what)

    def _attrs(self, provider):
        # variadic NULL-terminated attribute list of the libsecret *_sync calls
        return (ctypes.c_char_p(b"application"), ctypes.c_char_p(APPLICATION),
                ctypes.c_char_p(b"provider"), ctypes.c_char_p(provider.encode("ascii")), ctypes.c_void_p(None))

    def get(self, provider):
        error = ctypes.POINTER(_GError)()
        found = self.lib.secret_password_lookup_sync(ctypes.byref(self.schema), None, ctypes.byref(error),
                                                     *self._attrs(provider))
        self._check(error, "lookup")
        if not found:
            return None
        try:
            return ctypes.string_at(found).decode("utf-8")
        finally:
            self.lib.secret_password_free(found)

    def set(self, provider, key):
        error = ctypes.POINTER(_GError)()
        label = ("HST Office: khóa API " + provider).encode("utf-8")
        ok = self.lib.secret_password_store_sync(ctypes.byref(self.schema), None, ctypes.c_char_p(label),
                                                 ctypes.c_char_p(key.encode("utf-8")), None, ctypes.byref(error),
                                                 *self._attrs(provider))
        self._check(error, "store")
        if not ok:
            raise OSError("libsecret store failed")

    def delete(self, provider):
        error = ctypes.POINTER(_GError)()
        self.lib.secret_password_clear_sync(ctypes.byref(self.schema), None, ctypes.byref(error),
                                            *self._attrs(provider))
        self._check(error, "clear")
