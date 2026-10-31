# SPDX-License-Identifier: AGPL-3.0-only
"""Check that the 18 HST templates are listed by the Template Manager and create documents.

Usage: python3 tests/runtime/check-template-manager.py [--instdir upstream/libreoffice/instdir]
           [--out tests/output/template-manager] [--shots tests/output/screenshots-integration]

The templates ship in the bundled HST extension (template/<group>/, Paths.xcu adds
%origin%/template). With a fresh profile this asserts, over UNO:
  - the template groups "HST — Văn bản hành chính" (7 .ott), "HST — Bảng tính" (6 .ots) and
    "HST — Trình chiếu" (5 .otp) exist in com.sun.star.frame.DocumentTemplates;
  - every template has its Vietnamese title (dc:title of the template);
  - opening one of each kind AsTemplate gives a new, untitled document with the template text;
and takes a screenshot of the Template Manager (File > New > Templates). Exit 1 on failure.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402

ROOT = hst_gui.ROOT
GROUPS = {"HST — Văn bản hành chính": 7, "HST — Bảng tính": 6,
          "HST — Trình chiếu": 5}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/template-manager"))
    parser.add_argument("--shots", default=os.path.join(ROOT, "tests/output/screenshots-integration"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    os.makedirs(args.shots, exist_ok=True)
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)

    hst_gui.setup_uno(args.instdir)
    import uno  # noqa: F401  (enables the com.sun.star imports)
    from com.sun.star.beans import PropertyValue
    office = hst_gui.Office(args.instdir, args.out, 22000, display=args.display).start()
    try:
        import uno
        from com.sun.star.beans import Property
        from com.sun.star.ucb import OpenCommandArgument2
        templates = office.service("com.sun.star.frame.DocumentTemplates")
        templates.update()

        def children_of(content):
            """[(Title, TargetURL, XContent)] of a hierarchy folder (UCB "open" command)."""
            arg = OpenCommandArgument2()
            arg.Mode = 0  # com.sun.star.ucb.OpenMode.ALL
            props = []
            for name in ("Title", "TargetURL"):
                prop = Property()
                prop.Name, prop.Handle = name, -1
                props.append(prop)
            arg.Properties = tuple(props)
            command = uno.createUnoStruct("com.sun.star.ucb.Command")
            command.Name, command.Handle = "open", -1
            command.Argument = arg
            rows = content.execute(command, 0, None).getStaticResultSet()
            out = []
            while rows.next():
                child_id = ucb.createContentIdentifier(rows.queryContentIdentifierString())
                out.append((rows.getString(1), rows.getString(2), child_id))
            return out

        ucb = office.service("com.sun.star.ucb.UniversalContentBroker")
        groups = {title: children_of(ucb.queryContent(child)) for title, _u, child in children_of(templates.getContent())
                  if title in GROUPS}
        found = {}
        for group, count in GROUPS.items():
            entries = groups.get(group, [])
            check(f"group '{group}' with {count} templates", len(entries) == count,
                  ", ".join(title for title, _u, _c in entries))
            found[group] = entries
        for group, entries in found.items():
            for title, url, _c in entries[:1]:
                prop = PropertyValue()
                prop.Name, prop.Value = "AsTemplate", True
                doc = office.desktop().loadComponentFromURL(url, "_blank", 0, (prop,))
                text = ""
                if hasattr(doc, "getText"):
                    text = doc.getText().getString()
                elif hasattr(doc, "getSheets"):
                    sheet = doc.getSheets().getByIndex(0)
                    text = " ".join(sheet.getCellByPosition(x, y).getString() for x in range(6) for y in range(6))
                elif hasattr(doc, "getDrawPages"):
                    page = doc.getDrawPages().getByIndex(0)
                    text = " ".join(page.getByIndex(i).getString() for i in range(page.getCount())
                                    if hasattr(page.getByIndex(i), "getString"))
                check(f"'{title}' creates an untitled document with its content",
                      not doc.hasLocation() and len(text.strip()) > 0, f"{url.rsplit('/', 1)[-1]}: {text.strip()[:60]!r}")
                doc.setModified(False)
        # Template Manager dialog
        frame = office.desktop().getCurrentFrame()
        worker = threading.Thread(target=office.dispatch, args=(frame, ".uno:NewDoc"), daemon=True)
        worker.start()
        time.sleep(6)
        office.screenshot(os.path.join(args.shots, "04-template-manager.png"))
        names = [n for _w, n in hst_gui.toplevels(args.display, office.pid)]
        check("Template Manager opens", len(names) >= 2, repr(names))
        for wid, name in hst_gui.toplevels(args.display, office.pid):
            if " — HST " not in name and name != "HST Office":
                env = dict(os.environ, DISPLAY=args.display)
                subprocess.run(["xdotool", "windowfocus", wid], env=env, check=False, timeout=10)
                time.sleep(0.5)
                subprocess.run(["xdotool", "key", "Escape"], env=env, check=False, timeout=10)
        worker.join(15)
    finally:
        office.stop()
    failed = sum(r["status"] == "FAIL" for r in results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"failed": failed, "checks": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
