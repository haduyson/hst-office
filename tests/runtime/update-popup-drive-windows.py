# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""The new-version pop-up on a Windows test PC, run with the office's own Python in the console user's session.

Usage (check-update-popup-windows.ps1 prepares the folder):
  python.exe update-popup-drive-windows.py --program <image>\\program --work <dir> --srv <dir with the signed
      manifests latest-<version>.json(.sig)> [--out report.json]

The office is an administrative image whose bundled extension is the test package (HST_UPDATE_TEST_URL); the
manifests come from a local HTTP server on 127.0.0.1 started here. LOCALAPPDATA points into <work>, so the user's
own update cache is never touched. Buttons are pressed through the accessibility tree (UNO), keys with SendInput.
Steps as tests/runtime/check-update-popup.py: shows when ready, modeless (typing goes through), "Để sau" remembers
the day, a newer release shows at once, "Bỏ qua bản này" persists, AutoCheck off sends nothing. The administrator
policy (registry) is checked by the .ps1 with the -Phase policy run.
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
from update_popup_win_office import NODE, Office, seed, type_into, wait  # noqa: E402

SERVED, REQUESTS, RESULTS, SEEN = {}, [], [], []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        REQUESTS.append(self.path)
        status, body = SERVED.get(self.path.split("?")[0], (404, b""))
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def check(label, ok):
    RESULTS.append((label, bool(ok)))
    print("%-4s %s" % ("PASS" if ok else "FAIL", label), flush=True)


def serve(srv, version):
    for suffix in ("", ".sig"):
        with open(os.path.join(srv, "latest-%s.json%s" % (version, suffix)), "rb") as handle:
            SERVED["/latest.json" + suffix] = (200, handle.read())


def policy(office, start, args, server):
    """HKLM policy AutoCheck=false (Final): reads false, a user change is refused, nothing is requested."""
    try:
        start()
        time.sleep(30)
        check("policy: AutoCheck locked off", office.setting("AutoCheck") is False)
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", NODE
        node = office.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
        try:
            node.setPropertyValue("AutoCheck", True)
            node.commitChanges()
            refused = node.getPropertyValue("AutoCheck") is False
        except Exception as error:  # noqa: BLE001 - configmgr: modification of a finalized item
            refused = "final" in str(error).lower()
        check("policy: user change refused", refused)
        check("policy: no automatic request, no pop-up", not REQUESTS and office.popup() is None)
    except Exception as error:  # noqa: BLE001
        check("driver error: %r" % error, False)
    finally:
        office.stop()
        server.shutdown()
    return report(args)


def report(args):
    failed = [label for label, ok in RESULTS if not ok]
    print("update pop-up (Windows): %d checks, %d failed" % (len(RESULTS), len(failed)), flush=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"results": RESULTS, "requests": REQUESTS, "seen": SEEN}, handle, ensure_ascii=False, indent=1)
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--program", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--srv", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--uno-port", type=int, default=22195)
    ap.add_argument("--http-port", type=int, default=22196)
    ap.add_argument("--policy", action="store_true", help="only: the registry policy (set by the .ps1) locks AutoCheck off")
    args = ap.parse_args()
    shutil.rmtree(args.work, ignore_errors=True)
    local = os.path.join(args.work, "localappdata")
    os.makedirs(local)
    env = dict(os.environ, LOCALAPPDATA=local, HST_UPDATE_TEST_URL="http://127.0.0.1:%d/latest.json" % args.http_port)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.http_port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    office = Office(args.program, args.work, args.uno_port, env)
    reminder = os.path.join(local, "HSTOffice", "update", "update-reminder.json")
    base = [("/org.hasontech.hstoffice.Welcome", "Shown", "true"), ("/org.hasontech.hstoffice.DefaultApps", "Ask", "false"),
            ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay", "false")]

    def start(extra=()):
        office.init_profile()
        seed(office.profile, base + [(NODE, "LastCheck", "0")] + list(extra))
        REQUESTS.clear()
        return office.start()
    try:
        serve(args.srv, "1.0.8")
        if args.policy:
            return policy(office, start, args, server)
        doc = start()
        check("1: the pop-up shows after the start-up check", wait(office.popup, 240))
        window = doc.getCurrentController().getFrame().getContainerWindow()
        check("1: the document window stays enabled (modeless)", window.isEnabled())
        typed = type_into("HST Writer", "hstpopup") and wait(lambda: "hstpopup" in doc.getText().getString(), 10)
        check("1: typing reaches the document while the pop-up is open", typed and office.popup() is not None)
        check("1: no infobar while the pop-up shows it", not doc.getCurrentController().hasInfobar("hst-update-available"))
        check("2: Để sau closes the pop-up", office.press("Để sau", 1) and wait(lambda: office.popup() is None, 10))
        check("2: the version is remembered for the day", wait(lambda: json.load(open(reminder))["version"] == "1.0.8", 10))
        office.stop()
        doc = start()
        check("2: next start: infobar, no second pop-up the same day",
              wait(lambda: doc.getCurrentController().hasInfobar("hst-update-available"), 90) and office.popup() is None)
        office.stop()
        serve(args.srv, "1.0.9")
        doc = start()
        check("3: a newer version is announced at once", wait(office.popup, 240))
        check("3: Bỏ qua bản này closes the pop-up",
              office.press("Bỏ qua phiên bản này", 2) and wait(lambda: office.popup() is None, 10))
        check("3: SkippedVersion saved", wait(lambda: office.setting("SkippedVersion") == "1.0.9", 10))
        office.stop()
        doc = start()
        time.sleep(30)
        check("3: next start: the skipped version shows nothing",
              office.popup() is None and not doc.getCurrentController().hasInfobar("hst-update-available"))
        check("3: the check did run", any(r.startswith("/latest.json") for r in REQUESTS))
        office.stop()
        serve(args.srv, "1.0.10")
        start([(NODE, "AutoCheck", "false")])
        time.sleep(30)
        check("4: AutoCheck off: no request, no pop-up", not REQUESTS and office.popup() is None)
    except Exception as error:  # noqa: BLE001 - report what happened instead of a bare traceback
        check("driver error: %r" % error, False)
    finally:
        if any(not ok for _label, ok in RESULTS):
            try:
                SEEN.append(office.describe())
            except Exception as error:  # noqa: BLE001 - the office is gone
                SEEN.append(repr(error))
        office.stop()
        server.shutdown()
    return report(args)


if __name__ == "__main__":
    sys.exit(main())
