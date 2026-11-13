# SPDX-License-Identifier: AGPL-3.0-only
"""Document tabs keep the user interface mode of their own module (Linux, GUI build, existing X display).

Scenario and judgement: ui_mode_tabs_scenario.py. Usage: python3 tests/runtime/check-ui-mode-tabs.py
[--instdir upstream/libreoffice/instdir] [--out tests/output/ui-mode-tabs] [--display :97]. Exit 1 on any FAIL.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import ui_mode_tabs_scenario as scenario  # noqa: E402

PORT = 21987  # deterministic per check (see hst_gui)


class Adapter:
    """hst_gui.Office with the interface the scenario expects."""

    def __init__(self, office):
        self.office = office

    @property
    def desktop(self):
        return self.office.desktop()

    def dispatch(self, frame, command, args=()):
        return self.office.dispatch(frame, command, args)

    def set_config(self, node, name, value):
        self.office.set_config(node, name, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/ui-mode-tabs"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
        return ok

    office = hst_gui.Office(args.instdir, args.out, PORT, display=args.display, nodefault=True)
    office.start()
    try:
        os.makedirs(os.path.join(args.out, "docs"), exist_ok=True)
        if os.geteuid() == 0:
            os.chmod(os.path.join(args.out, "docs"), 0o777)
        scenario.run(Adapter(office), check, os.path.join(args.out, "docs"))
    except Exception as error:  # noqa: BLE001 - report the harness failure as a FAIL
        check("scenario ran", False, repr(error))
    finally:
        office.stop()
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1)
    failed = sum(r["status"] == "FAIL" for r in results)
    print("%d checks, %d failed" % (len(results), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
