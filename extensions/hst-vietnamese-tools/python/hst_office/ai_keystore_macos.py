# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""macOS login keychain (Security.framework generic passwords through ctypes) for the AI API keys.

One item per provider: service "HST Office AI", account = provider. The keychain encrypts it with the user's login
keychain and lets only HST Office read it without asking. Local only, never the network.
"""
import ctypes
import ctypes.util

LABEL = "Chuỗi khóa (Keychain) của macOS"
SERVICE = b"HST Office AI"
ERR_NOT_FOUND = -25300


def _load():
    sec = ctypes.CDLL(ctypes.util.find_library("Security") or "/System/Library/Frameworks/Security.framework/Security")
    cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation")
                     or "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    u32, ptr = ctypes.c_uint32, ctypes.c_void_p
    sec.SecKeychainFindGenericPassword.argtypes = [ptr, u32, ctypes.c_char_p, u32, ctypes.c_char_p,
                                                   ctypes.POINTER(u32), ctypes.POINTER(ptr), ctypes.POINTER(ptr)]
    sec.SecKeychainAddGenericPassword.argtypes = [ptr, u32, ctypes.c_char_p, u32, ctypes.c_char_p, u32,
                                                  ctypes.c_char_p, ctypes.POINTER(ptr)]
    sec.SecKeychainItemModifyAttributesAndData.argtypes = [ptr, ptr, u32, ctypes.c_char_p]
    sec.SecKeychainItemDelete.argtypes = [ptr]
    sec.SecKeychainItemFreeContent.argtypes = [ptr, ptr]
    for name in ("SecKeychainFindGenericPassword", "SecKeychainAddGenericPassword",
                 "SecKeychainItemModifyAttributesAndData", "SecKeychainItemDelete", "SecKeychainItemFreeContent"):
        getattr(sec, name).restype = ctypes.c_int32
    cf.CFRelease.argtypes = [ptr]
    cf.CFRelease.restype = None
    return sec, cf


class Store:
    label = LABEL

    def __init__(self):
        self.sec, self.cf = _load()

    def _find(self, provider, want_data):
        account = provider.encode("ascii")
        length, data, item = ctypes.c_uint32(), ctypes.c_void_p(), ctypes.c_void_p()
        status = self.sec.SecKeychainFindGenericPassword(
            None, len(SERVICE), SERVICE, len(account), account,
            ctypes.byref(length) if want_data else None, ctypes.byref(data) if want_data else None, ctypes.byref(item))
        if status == ERR_NOT_FOUND:
            return None, None
        if status:
            raise OSError("SecKeychainFindGenericPassword %d" % status)
        value = None
        if want_data:
            try:
                value = ctypes.string_at(data, length.value).decode("utf-8")
            finally:
                self.sec.SecKeychainItemFreeContent(None, data)
        return item, value

    def get(self, provider):
        item, value = self._find(provider, True)
        if item:
            self.cf.CFRelease(item)
        return value

    def set(self, provider, key):
        secret, account = key.encode("utf-8"), provider.encode("ascii")
        item, _ = self._find(provider, False)
        if item:
            try:
                status = self.sec.SecKeychainItemModifyAttributesAndData(item, None, len(secret), secret)
            finally:
                self.cf.CFRelease(item)
        else:
            status = self.sec.SecKeychainAddGenericPassword(None, len(SERVICE), SERVICE, len(account), account,
                                                            len(secret), secret, None)
        if status:
            raise OSError("keychain write %d" % status)

    def delete(self, provider):
        item, _ = self._find(provider, False)
        if not item:
            return
        try:
            status = self.sec.SecKeychainItemDelete(item)
        finally:
            self.cf.CFRelease(item)
        if status:
            raise OSError("SecKeychainItemDelete %d" % status)
