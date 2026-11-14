# SPDX-License-Identifier: AGPL-3.0-only
"""Every composed frame of the primary screen through DXGI Desktop Duplication (Windows, pure ctypes COM).

GDI reads of the screen DC cost one compositor readback each (about 30 per second for the whole screen, about one per
second for many small patches); Desktop Duplication hands over each frame the compositor presents (up to the refresh
rate, a new one only when the screen changed). DxgiPatches.grab() waits for the next presented frame (or returns the
last one after 100 ms without a change) and samples the same patch grid as screen_patches_win.Patches, so the
classification of screen_patches_win applies unchanged.
"""
import ctypes
from ctypes import wintypes

import screen_patches_win as sp

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # physical pixels, as the duplicated surface has them
except (AttributeError, OSError):
    pass

HRESULT = ctypes.c_long
WAIT_TIMEOUT = -2005270489  # DXGI_ERROR_WAIT_TIMEOUT 0x887A0027


class GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text):
        a, b, c, d, e = text.split("-")
        return cls(int(a, 16), int(b, 16), int(c, 16), (ctypes.c_ubyte * 8)(*bytes.fromhex(d + e)))


IID_DXGI_DEVICE1 = GUID.parse("77db970f-6276-48ba-ba28-070143b4392c")
IID_DXGI_OUTPUT1 = GUID.parse("00cddea8-939b-4b83-a340-a685226666cc")
IID_TEXTURE2D = GUID.parse("6f15aaf2-d208-4e89-9ab4-489535d34f9c")


def call(obj, index, *args, restype=HRESULT):
    """Call vtable slot `index` of COM object `obj` (a c_void_p) with ctypes `args`."""
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    types = [ctypes.c_void_p if type(a).__name__ == "CArgObject" else type(a) for a in args]  # byref(): a pointer
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *types)
    return proto(vtable[index])(obj, *args)


def check(hr, what):
    if hr < 0:
        raise OSError("%s failed: 0x%08X" % (what, hr & 0xFFFFFFFF))


def release(obj):
    if obj:
        call(obj, 2, restype=ctypes.c_ulong)


class TextureDesc(ctypes.Structure):
    _fields_ = [("Width", wintypes.UINT), ("Height", wintypes.UINT), ("MipLevels", wintypes.UINT),
                ("ArraySize", wintypes.UINT), ("Format", wintypes.UINT), ("SampleCount", wintypes.UINT),
                ("SampleQuality", wintypes.UINT), ("Usage", wintypes.UINT), ("BindFlags", wintypes.UINT),
                ("CPUAccessFlags", wintypes.UINT), ("MiscFlags", wintypes.UINT)]


class Mapped(ctypes.Structure):
    _fields_ = [("pData", ctypes.c_void_p), ("RowPitch", wintypes.UINT), ("DepthPitch", wintypes.UINT)]


class DxgiPatches(sp.Patches):
    """screen_patches_win.Patches whose grab() samples the frames Desktop Duplication delivers."""

    def __init__(self, rect, cols=5, rows=4, size=16):
        super().__init__(rect, cols, rows, size)
        self.device, self.context, level = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_uint()
        check(ctypes.windll.d3d11.D3D11CreateDevice(None, 1, None, 0, None, 0, 7, ctypes.byref(self.device),
                                                     ctypes.byref(level), ctypes.byref(self.context)), "D3D11CreateDevice")
        dxgi, adapter, output, output1 = (ctypes.c_void_p() for _ in range(4))
        check(call(self.device, 0, ctypes.byref(IID_DXGI_DEVICE1), ctypes.byref(dxgi)), "QI IDXGIDevice1")
        check(call(dxgi, 7, ctypes.byref(adapter)), "GetAdapter")
        check(call(adapter, 7, wintypes.UINT(0), ctypes.byref(output)), "EnumOutputs")
        check(call(output, 0, ctypes.byref(IID_DXGI_OUTPUT1), ctypes.byref(output1)), "QI IDXGIOutput1")
        self.dup = ctypes.c_void_p()
        check(call(output1, 22, self.device, ctypes.byref(self.dup)), "DuplicateOutput")
        for obj in (output1, output, adapter, dxgi):
            release(obj)
        self.staging, self.last, self.presented, self.skipped = None, None, 0, 0

    def _staging_for(self, texture):
        if self.staging is None:
            desc = TextureDesc()
            call(texture, 10, ctypes.byref(desc), restype=None)
            desc.MipLevels, desc.ArraySize, desc.SampleCount, desc.SampleQuality = 1, 1, 1, 0
            desc.Usage, desc.BindFlags, desc.CPUAccessFlags, desc.MiscFlags = 3, 0, 0x20000, 0  # STAGING, CPU read
            self.staging = ctypes.c_void_p()
            check(call(self.device, 5, ctypes.byref(desc), ctypes.c_void_p(), ctypes.byref(self.staging)),
                  "CreateTexture2D")
        return self.staging

    def grab(self):
        info, resource = (ctypes.c_ubyte * 64)(), ctypes.c_void_p()
        hr = call(self.dup, 8, wintypes.UINT(100), ctypes.byref(info), ctypes.byref(resource))
        if hr == WAIT_TIMEOUT:  # nothing new presented: the last picture (GDI before the first presented frame)
            return self.last if self.last is not None else super().grab()
        check(hr, "AcquireNextFrame")
        self.skipped += max(int.from_bytes(bytes(info[16:20]), "little") - 1, 0)  # presents merged into this frame
        if not int.from_bytes(bytes(info[:8]), "little"):  # LastPresentTime 0: only the mouse pointer moved
            release(resource)
            call(self.dup, 14)
            return self.last if self.last is not None else super().grab()
        try:
            texture = ctypes.c_void_p()
            check(call(resource, 0, ctypes.byref(IID_TEXTURE2D), ctypes.byref(texture)), "QI ID3D11Texture2D")
            staging = self._staging_for(texture)
            call(self.context, 47, staging, texture, restype=None)  # CopyResource
            release(texture)
        finally:
            release(resource)
            call(self.dup, 14)  # ReleaseFrame
        mapped = Mapped()
        check(call(self.context, 14, staging, wintypes.UINT(0), wintypes.UINT(1), wintypes.UINT(0),
                   ctypes.byref(mapped)), "Map")
        try:
            rows = []
            for y in range(self.size):
                rows.append(b"".join(ctypes.string_at(mapped.pData + (py + y) * mapped.RowPitch + px * 4, self.size * 4)
                                     for px, py in self.points))
            self.last = b"".join(rows)
        finally:
            call(self.context, 15, staging, wintypes.UINT(0), restype=None)  # Unmap
        self.presented += 1
        return self.last

    def close(self):
        for obj in (self.staging, self.dup, self.context, self.device):
            release(obj)
        super().close()
