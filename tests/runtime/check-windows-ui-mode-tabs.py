#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Document tabs keep the user interface mode of their own module, on an INSTALLED HST Office (Windows).

The Windows counterpart of check-ui-mode-tabs.py; scenario and judgement: ui_mode_tabs_scenario.py. Before
hst-ui-mode-per-tab.patch the Sheets tab showed only the menubar after "Apply to All" from the Writer tab (user report
13/11/2026). Usage: "<install>\\program\\python.exe" tests/runtime/check-windows-ui-mode-tabs.py --install DIR --out DIR
[--port 2170]. Evidence: <out>/results.json, <out>/<n>.png after each scenario. Exit 1 on any FAIL.
"""
import argparse
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ui_mode_tabs_scenario as scenario  # noqa: E402
import windows_gui as wg  # noqa: E402


class Adapter:
    """wg.WinOffice with the interface the scenario expects."""

    def __init__(self, office):
        self.office = office

    @property
    def desktop(self):
        return self.office.desktop

    def dispatch(self, frame, command, args=()):
        helper = self.office.service("com.sun.star.frame.DispatchHelper")
        return helper.executeDispatch(frame, command, "", 0, tuple(args))

    def set_config(self, node, name, value):
        provider = self.office.service("com.sun.star.configuration.ConfigurationProvider")
        access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess",
                                                      (scenario.prop("nodepath", node),))
        access.setPropertyValue(name, value)
        access.commitChanges()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--install", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--port", type=int, default=2170)
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    check = wg.Results(out, "ui-mode-tabs")
    shots = [0]

    def record(name, ok, detail=""):
        shots[0] += 1
        wg.screenshot(os.path.join(out, "%d.png" % shots[0]), cursor=False)
        return check(name, ok, detail)

    office = wg.WinOffice(args.install, os.path.join(out, "profile"), args.port, os.path.join(out, "log"))
    try:
        office.start(fresh=True)
        seen = wg.dismiss_startup(office, os.path.join(out, "startup.png"), timeout=30, settle=5)
        check.note("start-up dialogs", seen)
        # Documents loaded right after a start-up question was ended over UNO have crashed the office on this
        # harness: restart until a start shows no question.
        for start in range(2, 5):
            if not seen:
                break
            office.stop()
            office.start()
            seen = wg.dismiss_startup(office, os.path.join(out, "startup-%d.png" % start), timeout=15, settle=3)
            check.note("start-up dialogs, start %d" % start, seen)
        adapter = Adapter(office)
        scenario.open_documents(adapter, os.path.join(out, "docs"))
        for window, _title in wg.dialogs(office):
            wg.close_dialog(window)
        scenario.run_after_open(adapter, record, os.path.join(out, "docs"))
    except Exception:  # noqa: BLE001
        import traceback
        check("scenario ran", False, traceback.format_exc()[-1400:])
    finally:
        office.stop()
    return check.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
