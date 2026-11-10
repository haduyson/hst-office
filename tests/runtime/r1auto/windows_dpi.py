# SPDX-License-Identifier: AGPL-3.0-only
"""Set the primary display's real scale on Windows without the Settings app or a sign-out (tooling Python).

The Settings route timed out on every runner (r1-auto Windows runs 42475460387, 42744370109, 42748674627 at 150%).
DisplayConfigGetDeviceInfo/SetDeviceInfo with the DPI-scale request types (-3 get, -4 set; the method of the
SetDPI tool) take a step relative to the monitor's recommended scale and apply at once."""
import ctypes
from ctypes import wintypes

STEPS = (100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500)


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class Header(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int32), ("size", wintypes.UINT), ("adapterId", LUID), ("id", wintypes.UINT)]


class Get(ctypes.Structure):
    _fields_ = [("header", Header), ("minScaleRel", ctypes.c_int32), ("curScaleRel", ctypes.c_int32),
                ("maxScaleRel", ctypes.c_int32)]


class Set(ctypes.Structure):
    _fields_ = [("header", Header), ("scaleRel", ctypes.c_int32)]


def primary_source():
    """(adapterId, sourceId) of the first active path: the runner has one display."""
    user32 = ctypes.windll.user32
    paths, modes = wintypes.UINT(), wintypes.UINT()
    if user32.GetDisplayConfigBufferSizes(2, ctypes.byref(paths), ctypes.byref(modes)):  # QDC_ONLY_ACTIVE_PATHS
        raise OSError("GetDisplayConfigBufferSizes")
    path_buffer = (ctypes.c_byte * (72 * paths.value))()  # DISPLAYCONFIG_PATH_INFO is 72 bytes
    mode_buffer = (ctypes.c_byte * (64 * modes.value))()  # DISPLAYCONFIG_MODE_INFO is 64 bytes
    if user32.QueryDisplayConfig(2, ctypes.byref(paths), path_buffer, ctypes.byref(modes), mode_buffer, None):
        raise OSError("QueryDisplayConfig")
    adapter = LUID.from_buffer(path_buffer, 0)  # sourceInfo.adapterId
    source = wintypes.UINT.from_buffer(path_buffer, 8).value  # sourceInfo.id
    return LUID(adapter.LowPart, adapter.HighPart), source


def set_scale(percent):
    user32 = ctypes.windll.user32
    adapter, source = primary_source()
    get = Get(Header(-3, ctypes.sizeof(Get), adapter, source))
    if user32.DisplayConfigGetDeviceInfo(ctypes.byref(get)):
        raise OSError("DisplayConfigGetDeviceInfo DPI")
    recommended = STEPS.index(100) - get.minScaleRel  # minScaleRel is the 100% step relative to recommended
    wanted = STEPS.index(int(percent)) - recommended
    if not get.minScaleRel <= wanted <= get.maxScaleRel:
        raise ValueError(f"{percent}% ngoài dải của màn hình ({get.minScaleRel}..{get.maxScaleRel})")
    request = Set(Header(-4, ctypes.sizeof(Set), adapter, source), wanted)
    if user32.DisplayConfigSetDeviceInfo(ctypes.byref(request)):
        raise OSError("DisplayConfigSetDeviceInfo DPI")
    return dict(relative=wanted, range=(get.minScaleRel, get.maxScaleRel))
