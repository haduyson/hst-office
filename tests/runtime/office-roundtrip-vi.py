# SPDX-License-Identifier: AGPL-3.0-only
"""Open/save round trip with Vietnamese text in an installed HST Office (run with the office's bundled python).

  <office>/program/python office-roundtrip-vi.py <workdir> <office command...>
Starts the office command headless with a private profile and a UNO pipe, writes a Writer document and a Sheets
spreadsheet holding Vietnamese text, saves them as .docx and .xlsx, closes, opens both files again and compares the
text. Prints PASS/FAIL lines; exit 0 only when everything matched. Used by check-rpm-install-inside.sh and
check-appimage-inside.sh (the command is then the AppImage itself).
"""
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

TEXT = "Cộng hòa xã hội chủ nghĩa Việt Nam — Độc lập, Tự do, Hạnh phúc. Tiếng Việt: ăâđêôơư ẮẰẲẴẶ"


def props(**kw):
    out = []
    for name, value in kw.items():
        p = PropertyValue()
        p.Name, p.Value = name, value
        out.append(p)
    return tuple(out)


def office_env():
    """This python's launcher exports its own UNO and Python paths; the office under test must not inherit them."""
    return {k: v for k, v in os.environ.items() if k not in ("UNO_PATH", "URE_BOOTSTRAP", "PYTHONPATH", "PYTHONHOME")}


def connect(pipe, proc):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(180):
        if proc.poll() is not None:
            raise SystemExit("FAIL office exited early (%s)" % proc.returncode)
        try:
            return resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % pipe)
        except Exception:  # noqa: BLE001 - not listening yet
            time.sleep(1)
    raise SystemExit("FAIL no UNO connection")


def main():
    work, command = os.path.abspath(sys.argv[1]), sys.argv[2:]
    os.makedirs(work, exist_ok=True)
    pipe = "hstroundtrip%d" % os.getpid()
    profile = uno.systemPathToFileUrl(os.path.join(work, "profile"))
    proc = subprocess.Popen(command + ["-env:UserInstallation=" + profile, "--headless", "--invisible", "--norestore",
                                       "--accept=pipe,name=%s;urp;" % pipe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=office_env())
    ok = True
    try:
        ctx = connect(pipe, proc)
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        docx, xlsx = (uno.systemPathToFileUrl(os.path.join(work, n)) for n in ("vi.docx", "vi.xlsx"))
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, props(Hidden=True))
        doc.Text.setString(TEXT)
        doc.storeToURL(docx, props(FilterName="MS Word 2007 XML"))
        doc.close(True)
        sheet = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, props(Hidden=True))
        sheet.Sheets.getByIndex(0).getCellByPosition(0, 0).setString(TEXT)
        sheet.Sheets.getByIndex(0).getCellByPosition(1, 0).setFormula("=LEN(A1)")
        sheet.storeToURL(xlsx, props(FilterName="Calc MS Excel 2007 XML"))
        sheet.close(True)
        doc = desktop.loadComponentFromURL(docx, "_blank", 0, props(Hidden=True))
        got = doc.Text.getString().strip()
        doc.close(True)
        print(("PASS" if got == TEXT else "FAIL") + " docx-roundtrip-vietnamese")
        ok &= got == TEXT
        sheet = desktop.loadComponentFromURL(xlsx, "_blank", 0, props(Hidden=True))
        cells = sheet.Sheets.getByIndex(0)
        got, length = cells.getCellByPosition(0, 0).getString(), cells.getCellByPosition(1, 0).getValue()
        sheet.close(True)
        good = got == TEXT and int(length) == len(TEXT)
        print(("PASS" if good else "FAIL") + " xlsx-roundtrip-vietnamese (LEN=%d)" % length)
        ok &= good
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge drops while the office quits
            pass
    finally:
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
