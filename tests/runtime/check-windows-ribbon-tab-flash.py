#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: switching ribbon tabs never shows an intermediate layout, on an INSTALLED HST Office (console session).

Before hst-ribbon-adaptive-compact.patch reserved the banner's width before the page layout, a tab page first laid
its groups out at the full width and narrowed them about 100 ms later (a visible jump on every tab switch). The
Linux check records the screen with ffmpeg; here a thread copies the ribbon band (the top BAND px of the screen,
1:1 with GDI BitBlt) as fast as it can while each tab is clicked like a user does (gated input). Per switch the band
left of the banner is grouped into runs of identical frames: a run between the old and the new page that lasts
>= LIMIT_MS is a transient layout and fails. Usage (console session, under C:\\hst-test\\console-lock.txt):
  "<install>\\program\\python.exe" tests/runtime/check-windows-ribbon-tab-flash.py --install DIR --out DIR
Evidence: <out>/results.json and <out>/switch-<n>-<k>.bmp (each run's first frame).
"""
import argparse
import ctypes
import hashlib
import os
import struct
import sys
import threading
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import windows_gui as wg  # noqa: E402
from windows_gui_a11y import _role, walk  # noqa: E402

BAND, LIMIT_MS = 200, 60
TABS = ["Chèn", "Thiết kế", "Bố cục", "Tham khảo", "Trang đầu", "Xem lại", "Trang đầu"]
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32


class Band(threading.Thread):
    """Copies of the screen's top BAND px, `right` px wide, with their times, until stopped."""

    def __init__(self, right):
        super().__init__(daemon=True)
        self.right, self.frames, self.stop = right, [], threading.Event()

    def run(self):
        screen = user32.GetDC(0)
        memory = gdi32.CreateCompatibleDC(screen)
        bitmap = gdi32.CreateCompatibleBitmap(screen, self.right, BAND)
        gdi32.SelectObject(memory, bitmap)
        header = struct.pack("<IiiHHIIiiII", 40, self.right, -BAND, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(self.right * BAND * 4)
        try:
            while not self.stop.is_set():
                gdi32.BitBlt(memory, 0, 0, self.right, BAND, screen, 0, 0, 0x00CC0020)
                gdi32.GetDIBits(memory, bitmap, 0, BAND, buffer, header, 0)
                self.frames.append((time.perf_counter(), buffer.raw))
        finally:
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory)
            user32.ReleaseDC(0, screen)

    def save(self, path, data):
        header = struct.pack("<IiiHHIIiiII", 40, self.right, -BAND, 1, 32, 0, len(data), 0, 0, 0, 0)
        with open(path, "wb") as handle:
            handle.write(b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54) + header + data)


def ribbon_boxes(office):
    """{tab name: (x, y, w, h)} of the ribbon's tabs and the banner's box (or None), on the screen."""
    tabs, banner = {}, None
    page_tab, link = _role("PAGE_TAB"), _role("HYPER_LINK")
    for window in office.top_windows():
        for context, _depth in walk(window, limit=10):
            try:
                role, name = context.getAccessibleRole(), context.getAccessibleName()
                where, size = context.getLocationOnScreen(), context.getSize()
            except Exception:  # noqa: BLE001 - widgets come and go
                continue
            box = (where.X, where.Y, size.Width, size.Height)
            if role == page_tab and name in TABS and box[1] < 80:
                tabs[name] = box
            elif role == link and box[1] < BAND and size.Width > 100 and banner is None:  # the banner
                banner = box
    return tabs, banner


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2379)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    profile = os.path.join(args.out, "profile")
    res = wg.Results(args.out, profile)
    office = wg.WinOffice(args.install, profile, args.port, args.out, nodefault=True)
    office.start(fresh=True)
    try:
        time.sleep(15)
        office.ctx = office._connect()
        wg.dismiss_startup(office, os.path.join(args.out, "startup.png"))
        office.load("private:factory/swriter")
        time.sleep(5)
        wg.dismiss_startup(office, os.path.join(args.out, "writer-startup.png"), timeout=8, settle=2)
        office.desktop.getCurrentFrame().getContainerWindow().IsMaximized = True
        time.sleep(3)
        window = wg.find_window(lambda title: "HST Writer" in title, timeout=30)
        tabs, banner = ribbon_boxes(office)
        if not res("ribbon tabs found", bool(window) and len(tabs) >= 5, (sorted(tabs), banner)):
            return res.exit_code()
        # left of the banner (its art rotates); without it, up to the last tab's right edge
        right = banner[0] - 2 if banner else max(x + w for x, _y, w, _h in tabs.values())
        wg.foreground(window[0])
        time.sleep(1)
        band = Band(right)
        band.start()
        marks = []
        for name in TABS:
            box = tabs[name]
            wg.mouse_move(box[0] + box[2] // 2, box[1] + box[3] // 2)
            time.sleep(1.2)
            marks.append(time.perf_counter())
            wg.click(box[0] + box[2] // 2, box[1] + box[3] // 2)
            time.sleep(1.2)
        band.stop.set()
        band.join(10)
        rate = len(band.frames) / max(band.frames[-1][0] - band.frames[0][0], 0.001)
        res.note("band frames per second", round(rate, 1))
        for n, (name, start) in enumerate(zip(TABS, marks), start=1):
            frames = [(t, f) for t, f in band.frames if start - 0.3 <= t <= start + 1.1]
            runs = []  # [first time, last time, digest, first frame]
            for t, frame in frames:
                digest = hashlib.md5(frame[BAND // 4 * band.right * 4:]).hexdigest()  # below the tab row
                if runs and runs[-1][2] == digest:
                    runs[-1][1] = t
                else:
                    runs.append([t, t, digest, frame])
            for k, run in enumerate(runs):
                band.save(os.path.join(args.out, f"switch-{n}-{k}.bmp"), run[3])
            middle = [round((r[1] - r[0]) * 1000) for r in runs[1:-1]]
            res(f"[{n}] {name}: no intermediate layout of {LIMIT_MS} ms or more", all(ms < LIMIT_MS for ms in middle),
                {"runs": len(runs), "middle_ms": middle})
    finally:
        office.stop()
    return res.exit_code()


if __name__ == "__main__":
    sys.exit(main())
