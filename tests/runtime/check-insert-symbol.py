# SPDX-License-Identifier: AGPL-3.0-only
"""Check symbols and check boxes on a real HST Office build (fresh profile, headless).

Usage: <instdir>/program/python tests/runtime/check-insert-symbol.py --instdir <instdir> [--out DIR]

1. The Insert › Symbol drop-down defaults (hst-symbol-defaults.patch): favourites and recent characters hold the
   check boxes, ticks, arrows, math signs, ₫ and №.
2. A .docx as Word writes it, with Wingdings / Wingdings 2 check boxes (w:sym and text runs, font table with the
   symbol charset), draws them with OpenSymbol where Wingdings is missing, not as the letters ¨ þ ý.
3. A check box content control (.uno:InsertCheckboxContentControl, the ribbon's Phần mở rộng › Nhà phát triển ›
   Điều khiển nội dung › Hộp chọn) survives a .docx round trip as a w14:checkbox, checked state included.

Writes evidence.json to --out; exit 1 when a check fails.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REQUIRED = "☐☑☒✓✗✔•→←↑↓⇒°±×÷≤≥≠≈∞€©₫№"
FAVOURITE_BOXES = "☐☑☒✓✔✗"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
                 'officedocument.wordprocessingml.document.main+xml"/>'
                 '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-'
                 'officedocument.wordprocessingml.fontTable+xml"/></Types>')
PACKAGE_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                'officeDocument" Target="word/document.xml"/></Relationships>')
DOCUMENT_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                 'fontTable" Target="fontTable.xml"/></Relationships>')
# Word's font table marks both fonts with the symbol charset (02).
FONT_TABLE = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:fonts xmlns:w="{W}">'
              '<w:font w:name="Wingdings"><w:panose1 w:val="05000000000000000000"/><w:charset w:val="02"/>'
              '<w:family w:val="auto"/><w:pitch w:val="variable"/></w:font>'
              '<w:font w:name="Wingdings 2"><w:panose1 w:val="05020102010507070707"/><w:charset w:val="02"/>'
              '<w:family w:val="roman"/><w:pitch w:val="variable"/></w:font></w:fonts>')


def sym(font, char):
    return f'<w:r><w:sym w:font="{font}" w:char="{char}"/></w:r>'


def text_run(font, text):
    return (f'<w:r><w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/></w:rPr>'
            f'<w:t xml:space="preserve">{text}</w:t></w:r>')


def write_wingdings_docx(path):
    """Empty, ticked and crossed boxes: Wingdings F0A8 F0FE F0FD, Wingdings 2 F0A3 F052 F054, and the same three
    Wingdings boxes typed as text (¨ þ ý) in the Wingdings font, as old forms do."""
    body = ("<w:p>" + "".join(sym("Wingdings", c) for c in ("F0A8", "F0FE", "F0FD")) + "</w:p>"
            "<w:p>" + "".join(sym("Wingdings 2", c) for c in ("F0A3", "F052", "F054")) + "</w:p>"
            "<w:p>" + text_run("Wingdings", "¨þý") + "</w:p>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", CONTENT_TYPES)
        package.writestr("_rels/.rels", PACKAGE_RELS)
        package.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS)
        package.writestr("word/fontTable.xml", FONT_TABLE)
        package.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                              f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>')


def connect(pipe, timeout=90):
    import uno
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    time.sleep(6)  # calls made before startup settles get disposed
    while True:
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:  # NoConnectException until soffice listens
            if time.time() > deadline:
                raise
            time.sleep(1)


def props(**values):
    from com.sun.star.beans import PropertyValue
    result = []
    for name, value in values.items():
        prop = PropertyValue()
        prop.Name, prop.Value = name, value
        result.append(prop)
    return tuple(result)


def read_list(ctx, group, name):
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
                                                  props(nodepath=f"/org.openoffice.Office.Common/{group}"))
    return list(access.getPropertyValue(name))


def check_defaults(ctx):
    favourites = read_list(ctx, "FavoriteCharacters", "FavoriteCharacterList")
    recent = read_list(ctx, "RecentCharacters", "RecentCharacterList")
    missing = [c for c in REQUIRED if c not in favourites + recent]
    loose_boxes = [c for c in FAVOURITE_BOXES if c not in favourites]
    return not missing and not loose_boxes and len(favourites) < 16, {
        "favourites": favourites, "recent": recent, "missing": missing, "boxes_not_favourite": loose_boxes}


def check_wingdings(desktop, out):
    import uno
    from uno_main_thread_load import load
    source = os.path.join(out, "wingdings-checkboxes.docx")
    pdf = os.path.join(out, "wingdings-checkboxes.pdf")
    write_wingdings_docx(source)
    doc = load(desktop, uno.systemPathToFileUrl(source), Hidden=True)
    try:
        doc.storeToURL(uno.systemPathToFileUrl(pdf), props(FilterName="writer_pdf_Export"))
    finally:
        doc.close(True)
    # The PDF keeps the original characters for copying text, so look at the fonts that draw them instead: with
    # the Wingdings-to-OpenSymbol recoding every glyph comes from OpenSymbol; letters would need a text font.
    listing = subprocess.run(["pdffonts", pdf], capture_output=True, text=True, check=False).stdout.splitlines()[2:]
    fonts = sorted({line.split()[0].split("+")[-1] for line in listing if line.strip()})
    return fonts == ["OpenSymbol"], {"pdf": pdf, "fonts": fonts}


def checkbox_controls(desktop, path):
    import uno
    from uno_main_thread_load import load
    doc = load(desktop, uno.systemPathToFileUrl(path), Hidden=True)
    found = []
    try:
        paragraphs = doc.getText().createEnumeration()
        while paragraphs.hasMoreElements():
            portions = paragraphs.nextElement().createEnumeration()
            while portions.hasMoreElements():
                portion = portions.nextElement()
                if portion.TextPortionType == "ContentControl":
                    control = portion.ContentControl
                    found.append({"checkbox": control.Checkbox, "checked": control.Checked,
                                  "text": control.getString()})
    finally:
        doc.close(True)
    return found


def check_content_control(ctx, desktop, out):
    import uno
    from uno_main_thread_load import load
    first = os.path.join(out, "checkbox-content-control.docx")
    second = os.path.join(out, "checkbox-content-control-roundtrip.docx")
    doc = load(desktop, "private:factory/swriter", Hidden=True)
    try:
        dispatcher = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
        frame = doc.getCurrentController().getFrame()
        dispatcher.executeDispatch(frame, ".uno:InsertCheckboxContentControl", "", 0, ())
        text = doc.getText()
        text.insertControlCharacter(text.getEnd(), 0, False)  # PARAGRAPH_BREAK: the second box in its own line
        doc.getCurrentController().getViewCursor().gotoEnd(False)
        dispatcher.executeDispatch(frame, ".uno:InsertCheckboxContentControl", "", 0, ())
        doc.storeToURL(uno.systemPathToFileUrl(first), props(FilterName="MS Word 2007 XML"))
    finally:
        doc.close(True)
    exported = checkbox_controls(desktop, first)
    # Tick the second box as a user's click does (Checked), save again, and read it back.
    doc = load(desktop, uno.systemPathToFileUrl(first), Hidden=True)
    try:
        controls = [p for p in _portions(doc) if p.TextPortionType == "ContentControl"]
        if len(controls) >= 2:
            controls[1].ContentControl.Checked = True
        doc.storeToURL(uno.systemPathToFileUrl(second), props(FilterName="MS Word 2007 XML"))
    finally:
        doc.close(True)
    reread = checkbox_controls(desktop, second)
    with zipfile.ZipFile(second) as package:
        xml = package.read("word/document.xml").decode("utf-8")
    ok = (len(exported) == 2 and all(c["checkbox"] for c in exported) and not any(c["checked"] for c in exported)
          and [c["checked"] for c in reread] == [False, True] and xml.count("<w14:checkbox>") == 2
          and '<w14:checked w14:val="1"/>' in xml)
    return ok, {"files": [first, second], "exported": exported, "after_tick": reread,
                "w14_checkboxes": xml.count("<w14:checkbox>")}


def _portions(doc):
    paragraphs = doc.getText().createEnumeration()
    while paragraphs.hasMoreElements():
        portions = paragraphs.nextElement().createEnumeration()
        while portions.hasMoreElements():
            yield portions.nextElement()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True)
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/insert-symbol"))
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    program = os.path.join(os.path.abspath(args.instdir), "program")
    child_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")) and program not in sys.path:
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    import uno  # noqa: F401  (needs the build's program directory on sys.path)

    profile = os.path.join(out, "profile")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(profile)
    pipe = f"hstsymbol{os.getpid()}"
    for _ in range(3):  # exit code 81 = restart requested while the fresh profile is created
        warm = subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore",
                               "--terminate_after_init", f"-env:UserInstallation=file://{profile}"],
                              env=child_env, timeout=120, check=False)
        if warm.returncode == 0:
            break
    proc = subprocess.Popen([os.path.join(program, "soffice"), "--headless", "--norestore", "--nologo",
                             f"-env:UserInstallation=file://{profile}", f"--accept=pipe,name={pipe};urp;"],
                            env=child_env)
    results, failed = {}, 0
    try:
        ctx = connect(pipe)
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        for name, check in (("drop-down defaults", lambda: check_defaults(ctx)),
                            ("Wingdings check boxes render", lambda: check_wingdings(desktop, out)),
                            ("check box content control round trip",
                             lambda: check_content_control(ctx, desktop, out))):
            try:
                ok, detail = check()
            except Exception as error:  # report and keep going
                ok, detail = False, {"error": repr(error)}
            failed += not ok
            results[name] = {"status": "PASS" if ok else "FAIL", **detail}
            print(f"{'PASS' if ok else 'FAIL'}  {name}: {json.dumps(detail, ensure_ascii=False)[:400]}")
        try:
            desktop.terminate()
        except Exception:  # the bridge drops while the office exits
            pass
    finally:
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump({"instdir": args.instdir, "failed": failed, "checks": results}, handle, indent=2,
                  ensure_ascii=False)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
