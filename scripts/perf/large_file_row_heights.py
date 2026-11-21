# SPDX-License-Identifier: AGPL-3.0-only
"""Row heights of spreadsheets after loading, to prove a change keeps them (run with the office's own Python).

    <office>/program/python large_file_row_heights.py --soffice <office>/program/soffice --profile <dir> FILE...

Starts one headless office on a private profile, loads every file hidden and prints one JSON line per sheet:
{"file": ..., "sheet": ..., "rows": n, "sha256": <hash of every used row's height>, "first": [the first 20 heights]}
Compare the lines of two office builds: equal hashes mean equal heights for every used row.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time


def prop(name, value):
    import uno
    p = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    p.Name, p.Value = name, value
    return p


def main():
    import uno
    ap = argparse.ArgumentParser()
    ap.add_argument("--soffice", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    pipe = "lfrh%d" % os.getpid()
    office = subprocess.Popen([a.soffice, "-env:UserInstallation=" + uno.systemPathToFileUrl(os.path.abspath(a.profile)),
                               "--headless", "--norestore", "--nologo", "--accept=pipe,name=%s;urp;" % pipe])
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    ctx = None
    for _ in range(600):
        try:
            ctx = resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % pipe)
            break
        except Exception:  # noqa: BLE001 - the office is still starting
            time.sleep(0.5)
    if ctx is None:
        office.kill()
        return 2
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    try:
        for path in a.files:
            try:
                doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(os.path.abspath(path)), "_blank", 0,
                                                   (prop("Hidden", True),))
            except Exception as e:  # noqa: BLE001 - reported per file
                print(json.dumps({"file": os.path.basename(path), "error": type(e).__name__}), flush=True)
                continue
            if doc is None or not hasattr(doc, "getSheets"):
                print(json.dumps({"file": os.path.basename(path), "error": "not a spreadsheet"}), flush=True)
                if doc is not None:
                    doc.close(True)
                continue
            sheets = doc.getSheets()
            for i in range(sheets.getCount()):
                sheet = sheets.getByIndex(i)
                cursor = sheet.createCursor()
                cursor.gotoEndOfUsedArea(False)
                last = cursor.getRangeAddress().EndRow
                rows = sheet.getRows()
                digest, first = hashlib.sha256(), []
                for r in range(last + 1):
                    h = rows.getByIndex(r).Height
                    digest.update(b"%d," % h)
                    if r < 20:
                        first.append(h)
                print(json.dumps({"file": os.path.basename(path), "sheet": sheet.getName(), "rows": last + 1,
                                  "sha256": digest.hexdigest(), "first": first}), flush=True)
            doc.close(True)
    finally:
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away with the office
            pass
        try:
            office.wait(timeout=120)
        except subprocess.TimeoutExpired:
            office.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
