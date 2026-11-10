# SPDX-License-Identifier: AGPL-3.0-only
"""OS input and screen capture, executed with the tooling Python, never pyuno's ABI."""
import ctypes
import json
import platform
from pathlib import Path
import subprocess
import sys
import time

SYSTEM = platform.system()
KEYS = {"tab": (9, 48), "enter": (13, 36), "escape": (27, 53), "a": (65, 0),
        "q": (81, 12), "k": (75, 40), "z": (90, 6), "down": (40, 125),
        "ctrl": (17, 59), "alt": (18, 58), "cmd": (91, 55)}


def win_event(kind, *args):
    from ctypes import wintypes as w
    class Mouse(ctypes.Structure):
        _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("data", w.DWORD), ("flags", w.DWORD),
                    ("time", w.DWORD), ("extra", ctypes.c_size_t)]
    class Key(ctypes.Structure):
        _fields_ = [("vk", w.WORD), ("scan", w.WORD), ("flags", w.DWORD),
                    ("time", w.DWORD), ("extra", ctypes.c_size_t)]
    class Union(ctypes.Union):
        _fields_ = [("mouse", Mouse), ("key", Key)]
    class Input(ctypes.Structure):
        _fields_ = [("kind", w.DWORD), ("value", Union)]
    event = Input(kind, Union())
    if kind == 0:
        event.value.mouse = Mouse(*args, 0, 0)
    else:
        event.value.key = Key(*args, 0, 0)
    if ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(event)) != 1:
        raise OSError("SendInput không gửi được đầu vào")


def keyboard(names=None, text=None):
    if SYSTEM == "Windows":
        if text is not None:
            data = text.encode("utf-16-le")
            for i in range(0, len(data), 2):
                code = int.from_bytes(data[i:i + 2], "little")
                win_event(1, 0, code, 4)
                win_event(1, 0, code, 6)
        else:
            for name in names:
                win_event(1, KEYS[name][0], 0, 0)
            for name in reversed(names):
                win_event(1, KEYS[name][0], 0, 2)
    elif SYSTEM == "Darwin":
        import Quartz as q
        masks = {"cmd": q.kCGEventFlagMaskCommand, "alt": q.kCGEventFlagMaskAlternate,
                 "ctrl": q.kCGEventFlagMaskControl}
        if text is not None:
            for char in text:
                for pressed in (True, False):
                    event = q.CGEventCreateKeyboardEvent(None, 0, pressed)
                    q.CGEventKeyboardSetUnicodeString(event, len(char.encode("utf-16-le")) // 2, char)
                    q.CGEventPost(q.kCGHIDEventTap, event)
        else:
            flags = 0
            for pressed, sequence in ((True, names), (False, reversed(names))):
                for name in sequence:
                    mask = masks.get(name, 0)
                    flags = flags | mask if pressed else flags & ~mask
                    event = q.CGEventCreateKeyboardEvent(None, KEYS[name][1], pressed)
                    q.CGEventSetFlags(event, flags)
                    q.CGEventPost(q.kCGHIDEventTap, event)
    else:
        subprocess.run(["xdotool", "type", "--clearmodifiers", text] if text is not None else
                       ["xdotool", "key", "+".join(names)], check=True)
    time.sleep(0.35)


def pointer(action, x, y=0):
    if SYSTEM == "Windows":
        ctypes.windll.user32.SetProcessDPIAware()
        if action == "wheel":
            win_event(0, 0, 0, int(x) * 120 & 0xffffffff, 0x800)
        else:
            ctypes.windll.user32.SetCursorPos(int(x), int(y))
            if action == "click":
                win_event(0, 0, 0, 0, 2)
                win_event(0, 0, 0, 0, 4)
    elif SYSTEM == "Darwin":
        import Quartz as q
        if action == "wheel":
            event = q.CGEventCreateScrollWheelEvent(None, q.kCGScrollEventUnitLine, 1, int(x))
            q.CGEventPost(q.kCGHIDEventTap, event)
        else:
            events = [q.kCGEventMouseMoved] if action == "move" else [q.kCGEventLeftMouseDown, q.kCGEventLeftMouseUp]
            for kind in events:
                event = q.CGEventCreateMouseEvent(None, kind, (float(x), float(y)), q.kCGMouseButtonLeft)
                q.CGEventPost(q.kCGHIDEventTap, event)
    else:
        command = ["xdotool", "click", "4" if int(x) > 0 else "5"] if action == "wheel" else [
            "xdotool", "mousemove", str(x), str(y)] + (["click", "1"] if action == "click" else [])
        subprocess.run(command, check=True)
    time.sleep(0.6)


def screenshot(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if SYSTEM == "Darwin":
        import Quartz as q
        if hasattr(q, "CGPreflightScreenCaptureAccess") and not q.CGPreflightScreenCaptureAccess():
            raise RuntimeError("Runner chưa cấp quyền ghi màn hình")
        subprocess.run(["screencapture", "-x", str(path)], check=True, stdin=subprocess.DEVNULL, timeout=60)
    else:
        from PIL import ImageGrab
        ImageGrab.grab().save(path)
    return str(path)


def cleanup(profile):
    import psutil
    owned = []
    for proc in psutil.process_iter(["pid", "cmdline", "name"]):
        if proc.pid == os_pid() or not (proc.info["name"] or "").lower().startswith(("soffice", "oosplash")):
            continue
        if any(profile in arg for arg in (proc.info["cmdline"] or [])):
            owned.append(proc)
    for proc in owned:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass  # it ended between the listing and the signal
    _, alive = psutil.wait_procs(owned, timeout=10)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=5)
    return [p.pid for p in owned]


def os_pid():
    import os
    return os.getpid()


def main():
    action, *args = sys.argv[1:]
    if action == "shot":
        return screenshot(args[0])
    if action == "key":
        return keyboard(args[0].split("+"))
    if action == "text":
        return keyboard(text=args[0])
    if action in {"move", "click", "wheel"}:
        return pointer(action, *map(int, args))
    if action == "product-version":
        from windows_install import product_version
        return product_version(args[0])
    if action == "activate":  # macOS: a soffice started directly is never the active app until asked
        from AppKit import NSRunningApplication
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(int(args[0]))
        return bool(app and app.activateWithOptions_(3))
    if action == "foreground":
        from windows_focus import foreground
        return foreground(*args)
    if action == "cleanup":
        return cleanup(args[0])
    if action == "print":
        from native_print import save_print
        return save_print(*args)
    if action in {"measure", "text-band"}:
        from pdf_metrics import run
        return run(action, *args)
    if action == "icon-change":
        from visual_metrics import icon_change
        return icon_change(*args)
    if action == "handlers":
        from mac_access import handlers
        return handlers()
    raise ValueError(action)


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
