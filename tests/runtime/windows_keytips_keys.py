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


def popups(hwnd):
    """Visible SAL top-level windows of the process of `hwnd` (a VCL menu that opens is one more)."""
    import ctypes
    pid = ctypes.c_ulong()
    wg.user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    mine = []
    for window in wg.office_windows():
        other = ctypes.c_ulong()
        wg.user32.GetWindowThreadProcessId(ctypes.c_void_p(window[0]), ctypes.byref(other))
        if other.value == pid.value:
            mine.append(window[0])
    return set(mine)


def opens_menu(hwnd, first_vk):
    """Press `first_vk` (Alt alone or F10), then Down: True when a menu of the menu bar opened (a new SAL window)."""
    before = popups(hwnd)
    front(hwnd)
    wg.chord(first_vk, target=hwnd, front=False)
    time.sleep(0.8)
    wg.chord(0x28, target=hwnd, front=False)  # Down opens the highlighted menu
    time.sleep(1.0)
    opened = popups(hwnd) - before
    return opened


def menu_bar_mode(office, doc, hwnd, res, out):
    """Classic menu bar shown: Alt alone and F10 activate it, no KeyTips; hidden again: Alt shows the KeyTips."""
    frame = doc.CurrentController.Frame
    helper = office.service("com.sun.star.frame.DispatchHelper")
    helper.executeDispatch(frame, ".uno:Menubar", "", 0, ())
    time.sleep(2.0)
    for name, vk in (("Alt alone", VK_ALT), ("F10", 0x79)):
        opened = opens_menu(hwnd, vk)
        wg.screenshot(os.path.join(out, f"menubar-{vk:x}.png"))
        res(f"[menu bar] {name}, Down opens a menu of the shown menu bar", bool(opened), sorted(opened))
        esc(hwnd, 3)
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
