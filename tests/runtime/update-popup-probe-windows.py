# SPDX-License-Identifier: AGPL-3.0-only
"""Windows probe: why the new-version pop-up waits. Runs like update-popup-drive-windows.py (same image, manifests,
LOCALAPPDATA in <work>) but only watches: every 5 s it records the desktop's frames (title, controller or none,
action lock: what welcome_job.loading() reads) and whether a window titled "Cập nhật HST Office" is shown, until the
pop-up shows or `--minutes` pass. Writes <out> (JSON).
"""
import argparse
import http.server
import json
import os
import shutil
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from update_popup_win_office import NODE, Office, seed, windows_titled  # noqa: E402

SERVED = {}
WELCOME = "HST Office chào đón bạn"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        status, body = SERVED.get(self.path.split("?")[0], (404, b""))
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def windows_foreground():
    import ctypes
    user32 = ctypes.windll.user32
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(user32.GetForegroundWindow(), buffer, 512)
    return buffer.value


def frames(office):
    out = []
    desktop = office.service("com.sun.star.frame.Desktop")
    tasks = desktop.getFrames()
    for index in range(tasks.getCount()):
        frame = tasks.getByIndex(index)
        out.append({"title": frame.getPropertyValue("Title") if hasattr(frame, "getPropertyValue") else frame.getName(),
                    "controller": frame.getController() is not None,
                    "locked": bool(frame.isActionLocked()) if hasattr(frame, "isActionLocked") else None,
                    "visible": bool(frame.getContainerWindow().isVisible())})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--program", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--srv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--minutes", type=float, default=11)
    ap.add_argument("--welcome-close", type=float, default=None,
                    help="leave the welcome dialog to open (a real first start) and close it after this many seconds")
    args = ap.parse_args()
    shutil.rmtree(args.work, ignore_errors=True)
    local = os.path.join(args.work, "localappdata")
    os.makedirs(local)
    env = dict(os.environ, LOCALAPPDATA=local, HST_UPDATE_TEST_URL="http://127.0.0.1:22196/latest.json")
    for suffix in ("", ".sig"):
        with open(os.path.join(args.srv, "latest-1.0.8.json" + suffix), "rb") as handle:
            SERVED["/latest.json" + suffix] = (200, handle.read())
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 22196), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    office = Office(args.program, args.work, 22195, env)
    office.init_profile()
    shown = "false" if args.welcome_close is not None else "true"
    seed(office.profile, [("/org.hasontech.hstoffice.Welcome", "Shown", shown),
                          ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"), (NODE, "LastCheck", "0")])
    log, started = [], time.time()
    try:
        office.start()
        while time.time() - started < args.minutes * 60:
            entry = {"t": round(time.time() - started)}
            try:
                entry["frames"] = frames(office)
            except Exception as error:  # noqa: BLE001
                entry["frames"] = repr(error)
            try:
                current = office.service("com.sun.star.frame.Desktop").getCurrentFrame()
                entry["current_frame"] = None if current is None else current.getName() or "(unnamed)"
            except Exception as error:  # noqa: BLE001
                entry["current_frame"] = repr(error)
            entry["foreground"] = windows_foreground()
            entry["popup"] = [t for _h, t in windows_titled(lambda title: "HST" in title)]
            welcome = [h for h, t in windows_titled(lambda title: title == WELCOME)]
            entry["welcome"] = bool(welcome)
            if welcome and args.welcome_close is not None and entry["t"] >= args.welcome_close:
                import ctypes
                ctypes.windll.user32.PostMessageW(welcome[0], 0x0010, 0, 0)  # WM_CLOSE to our own dialog
                entry["welcome_closed"] = True
            log.append(entry)
            print(json.dumps(entry), flush=True)  # ASCII: the Windows console is cp1252
            if any(t == "Cập nhật HST Office" for t in entry["popup"]):
                break
            time.sleep(2 if args.welcome_close is not None else 5)
    finally:
        office.stop()
        server.shutdown()
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(log, handle, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
