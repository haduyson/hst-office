# SPDX-License-Identifier: AGPL-3.0-only
"""Create, edit, save, reopen and export documents in all three HST modules.

Usage: python3 tests/runtime/check-office-roundtrip.py [--instdir upstream/libreoffice/instdir] [--out tests/output/roundtrip]

For Writer/Sheets/Slides: create a document via UNO, insert Vietnamese text,
store as ODF + OOXML + PDF, close, reload each saved file and verify the text
survived. Writes evidence.json; exit 1 on any failure.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEXT = "Kiểm thử HST Office: ăâđêôơư ÁÀẢÃẠ ỨỪỬỮỰ"
MODULES = {
    "writer": ("private:factory/swriter", [("odt", "writer8"), ("docx", "MS Word 2007 XML"), ("pdf", "writer_pdf_Export")]),
    "sheets": ("private:factory/scalc", [("ods", "calc8"), ("xlsx", "Calc MS Excel 2007 XML"), ("pdf", "calc_pdf_Export")]),
    "slides": ("private:factory/simpress", [("odp", "impress8"), ("pptx", "Impress MS PowerPoint 2007 XML"), ("pdf", "impress_pdf_Export")]),
}


def prop(name, value):
    from com.sun.star.beans import PropertyValue
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def put_text(module, doc):
    if module == "writer":
        doc.getText().setString(TEXT)
    elif module == "sheets":
        doc.getSheets().getByIndex(0).getCellByPosition(0, 0).setString(TEXT)
        doc.getSheets().getByIndex(0).getCellByPosition(0, 1).setFormula("=SUM(2;3)")
    else:
        page = doc.getDrawPages().getByIndex(0)
        from com.sun.star.awt import Point, Size
        shape = doc.createInstance("com.sun.star.drawing.TextShape")
        page.add(shape)
        shape.setPosition(Point(2000, 2000))  # 1/100 mm; a zero-size shape is not rendered
        shape.setSize(Size(20000, 3000))
        shape.setString(TEXT)


def read_text(module, doc):
    if module == "writer":
        return doc.getText().getString()
    if module == "sheets":
        sheet = doc.getSheets().getByIndex(0)
        return sheet.getCellByPosition(0, 0).getString() + f"|{sheet.getCellByPosition(0, 1).getValue():g}"
    page = doc.getDrawPages().getByIndex(0)
    return " ".join(page.getByIndex(i).getString() for i in range(page.getCount()) if hasattr(page.getByIndex(i), "getString"))


def connect(pipe, timeout=90):
    """Connect over the UNO pipe (profile is pre-initialised, so no first-start restart)."""
    import uno
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    time.sleep(6)  # the pipe opens early in startup; calls made before startup settles get disposed
    while True:
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:  # NoConnectException until soffice listens
            if time.time() > deadline:
                raise
            time.sleep(1)


def run_checks(ctx, out):
    import uno
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = (prop("Hidden", True),)
    results = []
    for module, (factory, formats) in MODULES.items():
        doc = desktop.loadComponentFromURL(factory, "_blank", 0, hidden)
        put_text(module, doc)
        saved = []
        for ext, filt in formats:
            path = os.path.join(out, f"{module}.{ext}")
            store = doc.storeToURL if ext == "pdf" else doc.storeToURL
            store(uno.systemPathToFileUrl(path), (prop("FilterName", filt),))
            saved.append(path)
        doc.close(True)
        for path in saved:
            ok, detail = os.path.getsize(path) > 0, ""
            if not path.endswith(".pdf"):
                reopened = desktop.loadComponentFromURL(uno.systemPathToFileUrl(path), "_blank", 0, hidden)
                detail = read_text(module, reopened)
                reopened.close(True)
                ok = ok and TEXT in detail and (module != "sheets" or detail.endswith("|5"))
            else:
                text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
                ok = ok and "Kiểm thử HST Office" in text
            results.append({"module": module, "file": os.path.basename(path), "status": "PASS" if ok else "FAIL",
                            "detail": detail[:120]})
            print(f"{'PASS' if ok else 'FAIL'}  {module} {os.path.basename(path)}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/roundtrip"))
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)  # profile must be an absolute file:// URL
    program = os.path.join(os.path.abspath(args.instdir), "program")  # URE bootstrap needs an absolute path
    # Use the tested build's own Python-UNO bridge when it ships one (HST builds
    # with --enable-python=system do); otherwise fall back to the system bridge.
    # URE_BOOTSTRAP is for this Python process only; soffice must not inherit it.
    child_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")):
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(os.path.join(args.out, "profile"))
    pipe = f"hstroundtrip{os.getpid()}"
    # A fresh profile makes soffice restart itself once; initialise it first so the
    # listening process below is the one that stays up.
    for _ in range(3):  # exit code 81 = "restart requested" while the profile is created
        warm = subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore",
                               "--terminate_after_init", "-env:UserInstallation=file://" + os.path.join(args.out, "profile")], env=child_env, timeout=120, check=False)
        if warm.returncode == 0:
            break
    proc = subprocess.Popen([os.path.join(program, "soffice"), "--headless", "--norestore", "--nologo",
                             "-env:UserInstallation=file://" + os.path.join(args.out, "profile"),
                             f"--accept=pipe,name={pipe};urp;"], env=child_env)
    try:
        results = run_checks(connect(pipe), args.out)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    failed = sum(r["status"] != "PASS" for r in results)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "failed": failed, "results": results}, handle, indent=2, ensure_ascii=False)
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
