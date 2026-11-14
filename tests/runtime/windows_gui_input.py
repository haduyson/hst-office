# SPDX-License-Identifier: AGPL-3.0-only
"""Real mouse and keyboard input (SendInput) for the Windows GUI checks, gated by windows_gui_guard: every key is
sent only after the foreground window has been re-read and found to be an HST Office window, every click only when
the window under the pointer is one. Pointer moves alone are not gated (hovering cannot act on anything)."""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

import windows_gui_guard as guard
from windows_gui_win32 import user32, window_rect

HERE = os.path.dirname(os.path.abspath(__file__))
SHOT_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts", "windows", "capture-screenshot.ps1")

try:
    user32.SetProcessDPIAware()  # screen pixels for SetCursorPos and GetWindowRect alike
except AttributeError:
    pass


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _KeyInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput), ("ki", _KeyInput), ("pad", ctypes.c_byte * 32)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


_MOVE, _ABSOLUTE, _LEFTDOWN, _LEFTUP, _KEYUP = 0x0001, 0x8000, 0x0002, 0x0004, 0x0002
VK = {"tab": 0x09, "enter": 0x0D, "escape": 0x1B, "space": 0x20, "down": 0x28, "up": 0x26}


def _send(*inputs):
    array = (_Input * len(inputs))(*inputs)
    return user32.SendInput(len(inputs), array, ctypes.sizeof(_Input))


def _mouse(flags, x=0, y=0):
    item = _Input(type=0)
    item.u.mi = _MouseInput(x, y, 0, flags, 0, 0)
    return item


def _key(vk, flags):
    item = _Input(type=1)
    item.u.ki = _KeyInput(vk, 0, flags, 0, 0)
    return item


def mouse_move(x, y, steps=8, pause=0.02):
    """Move the pointer to screen pixel (x, y) in small steps, as a hand does (each step is a WM_MOUSEMOVE)."""
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    start = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(start))
    for step in range(1, steps + 1):
        px = start.x + (x - start.x) * step // steps
        py = start.y + (y - start.y) * step // steps
        _send(_mouse(_MOVE | _ABSOLUTE, px * 65535 // (width - 1), py * 65535 // (height - 1)))
        time.sleep(pause)
    here = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(here))
    return here.x, here.y


def click(x, y):
    """Left click at screen pixel (x, y); BlockedInput (nothing pressed) when the window there is not ours."""
    mouse_move(x, y)
    guard.check_point(x, y)
    _send(_mouse(_LEFTDOWN), _mouse(_LEFTUP))
    time.sleep(0.3)


def drag(start, end, steps=10):
    """Press the left button at screen pixel `start`, move to `end` in `steps` moves and release, as a hand does."""
    mouse_move(*start)
    guard.check_point(*start)
    _send(_mouse(_LEFTDOWN))
    time.sleep(0.1)
    mouse_move(*end, steps=steps, pause=0.05)
    _send(_mouse(_LEFTUP))
    time.sleep(0.3)


def chord(*vks, target=None, front=True):
    """Press the virtual keys `vks` together (in order) and release them (in reverse) as one SendInput call. With
    `target` (an HWND of ours) it is brought to the front first unless `front` is False. Immediately before sending,
    the foreground window is re-checked (an HST Office window, of `target`'s process when given); BlockedInput is
    raised instead of sending when it is not. Alt+F4 and the Windows keys are always refused."""
    guard.check_chord(vks)
    if target and front:
        _bring_target(target)
    guard.check_foreground(target)
    return _send(*([_key(vk, 0) for vk in vks] + [_key(vk, _KEYUP) for vk in reversed(vks)]))


def key_press(vk, target=None, front=True):
    chord(vk, target=target, front=front)
    time.sleep(0.25)


def keys(*names, target=None, front=True):
    """Press the named keys (VK) one after another. With `target` it is brought to the front once, first (unless
    `front` is False: a check whose open popup must keep the focus). Before every key the foreground window is
    re-checked; on a foreign one BlockedInput is raised and the key and the rest are not sent."""
    if target and front:
        _bring_target(target)
    for name in names:
        key_press(VK[name], target, front=False)


def _press_alt():
    chord(guard.VK_MENU)


def _bring_target(target):
    if not guard.is_ours(target):
        raise BlockedInput("key not sent: target %#x is not an HST Office window" % target)
    foreground(target)  # a refusal is caught by the foreground check that follows


BlockedInput = guard.BlockedInput


def foreground(hwnd):
    """Bring `hwnd` (an HST Office window) to the front; False, with nothing sent, for any other window."""
    if not hwnd or not guard.is_ours(hwnd):
        return False
    return guard.bring_to_front(hwnd, _press_alt)


def activate(hwnd):
    """Make `hwnd` the active window as a user does: a real click on its title bar (only if it is ours)."""
    if not hwnd or not guard.is_ours(hwnd):
        return False
    left, top, right, _bottom = window_rect(hwnd)
    click(left + min(80, (right - left) // 3), top + 12)
    time.sleep(0.4)
    return user32.GetForegroundWindow() == hwnd


def screenshot(path, cursor=True):
    """Full-screen PNG, the pointer drawn in unless `cursor` is False; never raises (a missing shot must not hide the
    check result)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SHOT_SCRIPT, "-Path", path]
                   + (["-WithCursor"] if cursor else []), timeout=60, check=False)
    return path
