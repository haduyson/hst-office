# SPDX-License-Identifier: AGPL-3.0-only
"""Results and office life-cycle evidence of check-windows-smoke.py (see there)."""
import json
import os
import time

ROWS = []
OUT = None  # set by check-windows-smoke.py: smoke-results.json is rewritten there after every check


def record(name, ok, detail=""):
    ROWS.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:1500]})
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:300]), flush=True)
    if OUT:  # written after every check so a hang still leaves evidence
        with open(os.path.join(OUT, "smoke-results.json"), "w", encoding="utf-8") as handle:
            json.dump({"results": ROWS, "failed": sum(r["status"] == "FAIL" for r in ROWS)}, handle, ensure_ascii=False, indent=1)
    return ok


class Lifecycle:
    """Office life-cycle evidence for a failed check: Desktop terminate requests and global document events, timestamped.

    The listeners live in this process; the office calls them over the UNO bridge. When the office quits, the last
    entries show whether it went through Desktop.terminate (a clean quit) and which document event came before."""

    def __init__(self):
        self.events = []
        self.started = time.time()

    def note(self, text):
        self.events.append("%.2f %s" % (time.time() - self.started, text))

    def attach(self, ctx, desktop):
        import unohelper
        from com.sun.star.document import XDocumentEventListener
        from com.sun.star.frame import XTerminateListener
        owner = self

        class Terminate(unohelper.Base, XTerminateListener):
            def queryTermination(self, event):
                owner.note("queryTermination")

            def notifyTermination(self, event):
                owner.note("notifyTermination")

            def disposing(self, event):
                owner.note("desktop disposing")

        class Documents(unohelper.Base, XDocumentEventListener):
            def documentEventOccured(self, event):
                try:
                    title = event.Source.getTitle()
                except Exception:  # noqa: BLE001 - a closing model may not answer
                    title = "?"
                owner.note("%s %s" % (event.EventName, title))

            def disposing(self, event):
                pass

        desktop.addTerminateListener(Terminate())
        ctx.getValueByName("/singletons/com.sun.star.frame.theGlobalEventBroadcaster").addDocumentEventListener(Documents())

    def report(self, proc):
        state = "running" if proc is None or proc.poll() is None else "exited with %s" % proc.returncode
        return "office process %s; last events: %s" % (state, " | ".join(self.events[-16:]))


LIFE = Lifecycle()


def office_alive(ctx):
    try:
        return ctx.ServiceManager is not None
    except Exception:  # noqa: BLE001 - a dead bridge
        return False
