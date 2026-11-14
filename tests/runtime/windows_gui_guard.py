# SPDX-License-Identifier: AGPL-3.0-only
"""The one gate every real key (and click) of the Windows harnesses passes: input goes only to a verified HST Office
window, never to the desktop, the taskbar or a system dialog.

Real input (SendInput) lands in whatever window has the focus. A key meant for an office dialog that had already
closed reached the empty desktop instead (Alt+F4 there opens "Shut Down Windows", Enter confirms it: a test PC was
powered off that way). So before each key the foreground window is re-read and must be a VCL window (class SAL*) of
an office process (soffice.bin) the harness started itself (register_owner); otherwise BlockedInput is raised and nothing is sent. Alt+F4 and the Windows keys
are refused outright; windows are closed with WM_CLOSE to their own HWND instead.

Pure logic over a small `api` object, so the rules run under unit tests with a fake on any platform; the real api
(ctypes, user32/kernel32) is created on first use on Windows only.
"""
import ntpath
import time

OUR_IMAGES = frozenset({"soffice.bin"})
SHELL_CLASSES = frozenset({
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "#32770", "#32768", "DV2ControlHost",
    "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow", "MultitaskingViewFrame", "TaskSwitcherWnd",
    "XamlExplorerHostIslandWindow", "ForegroundStaging", "LockScreenBackstopFrame"})
VK_MENU, VK_F4 = 0x12, 0x73
ALT_KEYS = frozenset({VK_MENU, 0xA4, 0xA5})
NEVER = frozenset({0x5B, 0x5C, 0x5D, 0x5F})  # left/right Windows key, Apps (context menu), Sleep
WM_CLOSE = 0x0010


class BlockedInput(RuntimeError):
    """A key or click was refused (nothing was sent): the window that would receive it is not ours."""


def refusal(hwnd, api):
    """Why input to `hwnd` must not be sent, or None when it is a window of HST Office."""
    if not hwnd:
        return "no foreground window (desktop switching, locked or a window just closed)"
    if hwnd in (api.shell_window(), api.desktop_window()):
        return "the desktop (hwnd %#x)" % hwnd
    name = api.class_name(hwnd)
    if name in SHELL_CLASSES:
        return "a shell or system window (class %r, %r)" % (name, api.title(hwnd))
    if not name.startswith("SAL"):
        return "not an HST Office window (class %r, %r)" % (name, api.title(hwnd))
    pid = api.pid(hwnd)
    image = ntpath.basename(api.image(pid) or "").lower()
    if image not in OUR_IMAGES:
        return "a SAL window of another program (%r)" % image
    if _OWNERS and not any(owner.owns(pid) for owner in _OWNERS):
        return "a window of an office this harness did not start (pid %s, %r)" % (pid, api.title(hwnd))
    return None


_OWNERS = []


def register_owner(owner):
    """Allow input only into windows of processes `owner.owns(pid)` accepts (WinOffice registers its profile's
    soffice.bin on start). With owners registered, any other soffice window is refused like a foreign one."""
    if owner not in _OWNERS:
        _OWNERS.append(owner)


def unregister_owner(owner):
    if owner in _OWNERS:
        _OWNERS.remove(owner)


def is_ours(hwnd, api=None):
    api = api or win32()
    return refusal(hwnd, api) is None


def check_foreground(target=None, api=None):
    """The current foreground HWND when it is an HST Office window (of `target`'s process when given), else raise
    BlockedInput. Call immediately before each key."""
    api = api or win32()
    hwnd = api.foreground()
    why = refusal(hwnd, api)
    if why is None and target and api.pid(hwnd) != api.pid(target):
        why = "a window of another office process (pid %s, target pid %s)" % (api.pid(hwnd), api.pid(target))
    if why:
        raise BlockedInput("key not sent: the foreground window is " + why)
    return hwnd


def check_point(x, y, api=None):
    """The top-level HWND under screen pixel (x, y) when it is ours, else raise BlockedInput (a click is not sent)."""
    api = api or win32()
    root = api.root(api.window_from_point(x, y))
    why = refusal(root, api)
    if why:
        raise BlockedInput("click at (%d, %d) not sent: the window there is %s" % (x, y, why))
    return root


def check_chord(vks):
    """Refuse key combinations that act on Windows itself rather than on a window: Alt+F4, the Windows keys."""
    vks = set(vks)
    if VK_F4 in vks and vks & ALT_KEYS:
        raise BlockedInput("Alt+F4 is never sent: close a window with WM_CLOSE to its HWND")
    if vks & NEVER:
        raise BlockedInput("Windows/Apps/Sleep keys are never sent (%s)" % sorted(hex(v) for v in vks & NEVER))


def bring_to_front(hwnd, press_alt, api=None):
    """Make `hwnd` the foreground window without sending a key to anything but an HST Office window.

    SetForegroundWindow is refused to a process that did not produce the last input. Tries, in order: the plain
    call, the call with this thread's input attached to the foreground thread, and only when the current foreground
    window is itself ours, an Alt press (`press_alt`, the documented unlock) before the call. Returns whether `hwnd`
    is now in front."""
    api = api or win32()
    if api.foreground() == hwnd:
        return True
    api.show(hwnd)
    for attempt in ("plain", "attach", "alt"):
        if attempt == "attach":
            front = api.foreground()
            if front:
                api.attach(api.thread_of(front), True)
            api.bring_to_top(hwnd)
        if attempt == "alt":
            if refusal(api.foreground(), api) is not None:
                break  # never press a key into the desktop or a foreign window
            press_alt()
        api.set_foreground(hwnd)
        if attempt == "attach" and front:
            api.attach(api.thread_of(front), False)
        api.sleep(0.4)
        if api.foreground() == hwnd:
            return True
    return False


def close_window(hwnd, api=None):
    """Post WM_CLOSE (the title bar X: a dialog cancels) to `hwnd` when it is ours; True when posted."""
    api = api or win32()
    if refusal(hwnd, api) is not None:
        return False
    return bool(api.post(hwnd, WM_CLOSE))


_API = []


def win32():
    """The real api (ctypes), created once; Windows only."""
    if not _API:
        from windows_gui_win32 import Win32
        _API.append(Win32())
    return _API[0]


def wait_gone(hwnd, timeout=5.0, api=None):
    """True once `hwnd` is destroyed or hidden, polled until `timeout` seconds."""
    api = api or win32()
    deadline = time.time() + timeout
    while api.alive(hwnd):
        if time.time() > deadline:
            return False
        api.sleep(0.2)
    return True
