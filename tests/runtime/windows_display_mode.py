# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: the primary display's resolution, for running the ribbon checks at several screen sizes.

  python windows_display_mode.py list            the modes the display offers (width x height, 32 bit)
  python windows_display_mode.py set 1600 900    switch to that mode for this session (not saved in the registry)
  python windows_display_mode.py get             the current mode

Pair it with r1auto/scaling.py for the display scaling. Exit status 1 when the display has no such mode or the
switch is refused; the display is never left in a mode that was not asked for."""
import ctypes
import sys
from ctypes import wintypes

ENUM_CURRENT_SETTINGS = -1
DM_PELSWIDTH, DM_PELSHEIGHT = 0x80000, 0x100000
DISP_CHANGE_SUCCESSFUL = 0


class DEVMODEW(ctypes.Structure):
    _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD), ("dmDriverExtra", wintypes.WORD),
                ("dmFields", wintypes.DWORD), ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG),
                ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
                ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
                ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short), ("dmFormName", wintypes.WCHAR * 32),
                ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD), ("dmPelsWidth", wintypes.DWORD),
                ("dmPelsHeight", wintypes.DWORD), ("dmDisplayFlags", wintypes.DWORD),
                ("dmDisplayFrequency", wintypes.DWORD), ("dmICMMethod", wintypes.DWORD),
                ("dmICMIntent", wintypes.DWORD), ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
                ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
                ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]


def _mode(index):
    mode = DEVMODEW()
    mode.dmSize = ctypes.sizeof(DEVMODEW)
    return mode if ctypes.windll.user32.EnumDisplaySettingsW(None, index, ctypes.byref(mode)) else None


def modes():
    """Sorted distinct (width, height) of the primary display's 32-bit modes."""
    found, index = set(), 0
    while (mode := _mode(index)) is not None:
        if mode.dmBitsPerPel == 32:
            found.add((mode.dmPelsWidth, mode.dmPelsHeight))
        index += 1
    return sorted(found)


def current():
    mode = _mode(ENUM_CURRENT_SETTINGS)
    return (mode.dmPelsWidth, mode.dmPelsHeight) if mode else None


def set_mode(width, height):
    """Switch the primary display to width x height for this session; raises when it has no such mode."""
    if (width, height) not in modes():
        raise RuntimeError(f"the display has no {width}x{height} mode: {modes()}")
    mode = _mode(ENUM_CURRENT_SETTINGS)
    mode.dmPelsWidth, mode.dmPelsHeight = width, height
    mode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT
    result = ctypes.windll.user32.ChangeDisplaySettingsExW(None, ctypes.byref(mode), None, 0, None)
    if result != DISP_CHANGE_SUCCESSFUL or current() != (width, height):
        raise RuntimeError(f"switching to {width}x{height} failed ({result}); now {current()}")
    return current()


def main(argv):
    if argv[:1] == ["list"]:
        print(" ".join(f"{w}x{h}" for w, h in modes()))
    elif argv[:1] == ["get"]:
        print("%dx%d" % current())
    elif argv[:1] == ["set"] and len(argv) == 3:
        print("%dx%d" % set_mode(int(argv[1]), int(argv[2])))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except RuntimeError as error:
        print(error)
        sys.exit(1)
