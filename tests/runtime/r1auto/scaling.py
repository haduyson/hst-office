# SPDX-License-Identifier: AGPL-3.0-only
"""Configure actual desktop scaling; never resize screenshots to claim HiDPI."""
import ctypes
from pathlib import Path
import platform
import time


def windows_scale():
    from ctypes import wintypes
    locate = ctypes.windll.user32.MonitorFromPoint
    locate.argtypes, locate.restype = [wintypes.POINT, wintypes.DWORD], wintypes.HANDLE
    monitor = locate(wintypes.POINT(0, 0), 1)
    get_scale = ctypes.windll.shcore.GetScaleFactorForMonitor
    get_scale.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_int)]
    get_scale.restype = ctypes.c_long
    value = ctypes.c_int()
    if get_scale(monitor, ctypes.byref(value)) != 0:
        raise RuntimeError("Không đọc được tỉ lệ màn hình hiện tại")
    return value.value


def configure(percent):
    if platform.system() == "Darwin":
        import Quartz as q
        def retina_modes(display):
            modes = q.CGDisplayCopyAllDisplayModes(display, {"kCGDisplayShowDuplicateLowResolutionModes": True})
            return [m for m in modes or [] if q.CGDisplayModeGetWidth(m) >= 1440 and
                    q.CGDisplayModeGetPixelWidth(m) == q.CGDisplayModeGetWidth(m) * 2]
        display, virtual = q.CGMainDisplayID(), False
        candidates = retina_modes(display)
        if not candidates:  # runner VMs offer 1x modes only: add a real HiDPI display instead
            from mac_hidpi import create
            created, virtual = create(), True
            # It is now the main display, in its only (HiDPI) mode. CoreGraphics returns no mode object for it on
            # the runner (run 42476302775), so measure what a screenshot holds: pixels per point.
            time.sleep(2)
            import subprocess
            import tempfile
            from PIL import Image
            shot = Path(tempfile.mkdtemp()) / "scale.png"
            subprocess.run(["screencapture", "-x", str(shot)], check=True, timeout=60)
            pixels = Image.open(shot).size[0]
            points = q.CGDisplayBounds(q.CGMainDisplayID()).size.width
            factor = pixels / points
            if factor != 2:
                raise RuntimeError(f"Màn hình ảo {created} chưa 2×: {pixels} điểm ảnh / {points} điểm")
            return dict(scale=factor, virtual_display=True, logical_width=int(points), pixel_width=pixels)
        if not candidates:
            raise RuntimeError("Runner không có chế độ màn hình 2×; cần runner có HiDPI")
        chosen = min(candidates, key=q.CGDisplayModeGetWidth)
        if q.CGDisplaySetDisplayMode(display, chosen, None):
            raise RuntimeError("Không bật được chế độ màn hình 2×")
        time.sleep(2)
        factor = q.CGDisplayModeGetPixelWidth(chosen) / q.CGDisplayModeGetWidth(chosen)
        return dict(scale=factor, virtual_display=False, logical_width=q.CGDisplayModeGetWidth(chosen),
                    pixel_width=q.CGDisplayModeGetPixelWidth(chosen))
    if platform.system() == "Windows":
        import os
        from pywinauto import Desktop
        from support import wait
        ctypes.windll.user32.SetProcessDPIAware()
        before, wanted = windows_scale(), int(percent)
        if before != wanted:
            os.startfile("ms-settings:display")
            desktop = Desktop(backend="uia")
            def scale_box():
                for window in desktop.windows():
                    for combo in window.descendants(control_type="ComboBox"):
                        if "%" in combo.window_text():
                            return window, combo
                return None
            window, combo = wait(scale_box)
            try:
                options = combo.item_texts()
                selected = next(text for text in options if text.startswith(str(percent) + "%"))
                combo.select(selected)
                time.sleep(3)
            finally:
                window.close()
        actual = windows_scale()
        if actual != wanted:
            raise RuntimeError(f"Không đặt được tỉ lệ màn hình thật: yêu cầu {wanted}, quan sát {actual}")
        return dict(scale=actual / 100, percent=actual)
    return dict(scale=1, note="Linux chỉ xác minh logic dùng chung")
