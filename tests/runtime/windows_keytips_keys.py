# SPDX-License-Identifier: AGPL-3.0-only
"""Key helpers of check-windows-keytips-office-parity.py: gated chords to a verified HST window, and the classic
menu bar checks (Alt alone and F10 activate a shown menu bar; with it hidden, Alt shows the KeyTips)."""
import os
import time

import windows_gui as wg

VK_ALT, VK_CTRL, VK_SHIFT, VK_ESC = 0x12, 0x11, 0x10, 0x1B


def letters(hwnd, word):
    for char in word:
        wg.chord(ord(char), target=hwnd, front=False)
        time.sleep(0.5)
    time.sleep(1.0)


def front(hwnd):
    """The document window in front, with no KeyTips left open (bringing it forward may press Alt itself)."""
    wg.foreground(hwnd)
    time.sleep(0.6)
    esc(hwnd, 2)


def alt_tip(hwnd, word):
    front(hwnd)
    wg.chord(VK_ALT, target=hwnd, front=False)
    time.sleep(0.8)
    letters(hwnd, word)


def esc(hwnd, times=2):
    for _ in range(times):
        wg.chord(VK_ESC, target=hwnd, front=False)
        time.sleep(0.3)


def menu_bar_focused(hwnd):
    """(has a native menu bar, its bar has the keyboard focus) of a window, from GetMenu and GetMenuBarInfo."""
    import ctypes
    from ctypes import wintypes

    class MenuBarInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcBar", wintypes.RECT), ("hMenu", wintypes.HANDLE),
                    ("hwndMenu", wintypes.HWND), ("flags", wintypes.DWORD)]
    user32 = ctypes.windll.user32
    info = MenuBarInfo(cbSize=ctypes.sizeof(MenuBarInfo))
    ok = user32.GetMenuBarInfo(wintypes.HWND(hwnd), ctypes.c_long(-3), 0, ctypes.byref(info))  # OBJID_MENU
    return bool(user32.GetMenu(wintypes.HWND(hwnd))), bool(ok) and bool(info.flags & 1)  # fBarFocused


def menu_bar_mode(office, doc, hwnd, res, out):
    """Classic menu bar shown: Alt alone and F10 activate it, no KeyTips; hidden again: Alt shows the KeyTips."""
    frame = doc.CurrentController.Frame
    helper = office.service("com.sun.star.frame.DispatchHelper")
    helper.executeDispatch(frame, ".uno:Menubar", "", 0, ())
    time.sleep(2.0)
    front(hwnd)
    wg.chord(VK_ALT, target=hwnd, front=False)
    time.sleep(1.0)
    wg.screenshot(os.path.join(out, "menubar-1-alt.png"))
    shown, focused = menu_bar_focused(hwnd)
    res("[menu bar] Alt alone activates the shown menu bar", shown and focused, (shown, focused))
    esc(hwnd)
    front(hwnd)
    wg.chord(0x79, target=hwnd, front=False)  # F10
    time.sleep(1.0)
    wg.screenshot(os.path.join(out, "menubar-2-f10.png"))
    shown, focused = menu_bar_focused(hwnd)
    res("[menu bar] F10 activates the shown menu bar", shown and focused, (shown, focused))
    esc(hwnd)
    helper.executeDispatch(frame, ".uno:Menubar", "", 0, ())
    time.sleep(2.0)
    front(hwnd)
    wg.chord(VK_ALT, target=hwnd, front=False)
    time.sleep(1.0)
    wg.screenshot(os.path.join(out, "menubar-3-hidden-alt.png"))
    letters(hwnd, "N")
    res("[menu bar] hidden again: Alt, N still runs the KeyTips (no text typed)", doc.Text.getString() == "",
        repr(doc.Text.getString()))
    esc(hwnd, 3)
