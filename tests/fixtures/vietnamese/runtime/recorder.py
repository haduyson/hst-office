# SPDX-License-Identifier: AGPL-3.0-only
"""PASS/FAIL/BLOCKED recorder for the runtime checks."""


class Recorder:
    def __init__(self):
        self.rows = []

    def check(self, name, condition, detail=""):
        self.rows.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": str(detail)})
        print("%-4s %s %s" % (self.rows[-1]["status"], name, ("- " + str(detail)) if detail and not condition else ""))
        return condition

    def run(self, name, fn, *args):
        """Run a scenario; an exception is recorded as FAIL with the traceback tail, never swallowed."""
        import traceback
        try:
            fn(self, *args)
        except Exception:  # noqa: BLE001
            self.check(name + " (exception)", False, traceback.format_exc()[-600:])

    def blocked(self, name, detail=""):
        """Record that a check could not run in this environment (never counted as PASS)."""
        self.rows.append({"name": name, "status": "BLOCKED", "detail": str(detail)})
        print("BLOCKED %s - %s" % (name, detail))

    @property
    def failed(self):
        return [r for r in self.rows if r["status"] == "FAIL"]
