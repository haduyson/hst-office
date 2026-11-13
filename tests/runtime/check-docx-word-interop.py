# SPDX-License-Identifier: AGPL-3.0-only
"""Check .docx details that matter when Word opens and saves HST Writer documents.

Usage: python3 tests/runtime/check-docx-word-interop.py [--instdir upstream/libreoffice/instdir] [--out tests/output/docx-word-interop]

- New documents name Times New Roman as East Asian font; documents without Han, Kana or Hangul text
  export it equal to the Latin font, documents with Chinese text keep their CJK font. Otherwise Word
  stores each letter of U+1E00-U+1EFF in its own run (hst-writer-cjk-default-font.patch,
  hst-docx-east-asian-font-without-cjk-text.patch).
- Endnote placement only in settings.xml, never for footnotes, also after a reopen; in <w:sectPr>
  it makes Word save a .doc it cannot open (hst-docx-endnote-position-export.patch).
- Runs split by Word import with the same text, bold run and bookmark (hst-writerfilter-merge-split-runs.patch).
- findAll() without a match returns nothing instead of aborting (hst-sw-findall-no-match-crash.patch).

Exit 1 when any check fails; evidence.json and the saved files stay in --out.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docx_word_interop_samples import check_east_asian_export, check_split_runs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCX = "MS Word 2007 XML"


def connect(pipe, timeout=120):
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


def part(path, name):
    with zipfile.ZipFile(path) as package:
        return package.read(name).decode("utf-8")


def run_checks(ctx, out, expect):
    import uno
    from com.sun.star.beans import PropertyValue

    def prop(name, value):
        item = PropertyValue()
        item.Name, item.Value = name, value
        return item

    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = (prop("Hidden", True),)

    def url(name):
        return uno.systemPathToFileUrl(os.path.join(out, name))

    def store(doc, name, filter_name=DOCX):
        doc.storeToURL(url(name), (prop("FilterName", filter_name),))
        return os.path.join(out, name)

    def notes_document(collect_in_section=False):
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, hidden)
        text = doc.getText()
        cursor = text.createTextCursor()
        text.insertString(cursor, "Nguyễn Văn An nghiên cứu chính sách tiền tệ.", False)
        for kind in ("Footnote", "Endnote"):
            note = doc.createInstance("com.sun.star.text." + kind)
            text.insertTextContent(cursor, note, False)
            note.getText().setString(f"Chú thích ({kind}).")
        if collect_in_section:
            section = doc.createInstance("com.sun.star.text.TextSection")
            section.EndnoteIsCollectAtTextEnd = True
            text.insertControlCharacter(cursor, 0, False)
            text.insertTextContent(cursor, section, False)
        return doc

    # 1. East Asian font of a new document.
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, hidden)
    doc.getText().setString("Kết quả nghiên cứu cho thấy chính sách tiền tệ có tác động rõ rệt.")
    path = store(doc, "new.docx")
    doc.close(True)
    defaults = re.search(r"<w:rPrDefault>.*?</w:rPrDefault>", part(path, "word/styles.xml")).group(0)
    fonts = dict(re.findall(r'w:(ascii|hAnsi|eastAsia)="([^"]*)"', re.search(r"<w:rFonts [^>]*>", defaults).group(0)))
    expect("new .docx: East Asian font equals the Latin font", fonts.get("eastAsia"), fonts.get("ascii"))

    # 2. Footnote and endnote placement, first save and after reopening.
    doc = notes_document()
    first = store(doc, "notes.docx")
    doc.close(True)
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(first), "_blank", 0, hidden)
    second = store(doc, "notes-resaved.docx")
    doc.close(True)
    for label, path in (("saved", first), ("reopened and saved", second)):
        settings, body = part(path, "word/settings.xml"), part(path, "word/document.xml")
        expect(f"notes .docx {label}: no footnote placement",
               re.findall(r"<w:footnotePr>(?:(?!</w:footnotePr>).)*<w:pos ", settings + body), [])
        expect(f"notes .docx {label}: no placement in the section properties",
               re.findall(r"<w:sectPr\b(?:(?!</w:sectPr>).)*<w:pos ", body), [])
        expect(f"notes .docx {label}: endnotes at the end of the document", "sectEnd" in settings, False)

    # A section that really collects endnotes keeps that placement, in settings.xml only.
    doc = notes_document(collect_in_section=True)
    path = store(doc, "notes-section-end.docx")
    doc.close(True)
    settings = part(path, "word/settings.xml")
    expect("section collecting endnotes: settings.xml says sectEnd",
           bool(re.search(r'<w:endnotePr><w:pos w:val="sectEnd"/>', settings)), True)
    expect("section collecting endnotes: not as a footnote placement",
           bool(re.search(r'<w:footnotePr><w:pos ', settings)), False)

    # 3. Split runs import; East Asian font of documents without and with CJK text.
    check_split_runs(desktop, out, expect, prop)
    check_east_asian_export(desktop, out, expect, prop)

    # 4. findAll() with and without a match, on a document loaded hidden.
    doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, hidden)
    doc.getText().setString("Chú thích cuối trang và chú thích cuối tài liệu.")
    odt = store(doc, "search.odt", "writer8")
    doc.close(True)
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(odt), "_blank", 0, hidden)
    for needle, count in (("chú thích", 2), ("zzzz", 0)):
        descriptor = doc.createSearchDescriptor()
        descriptor.SearchString = needle
        try:
            found = doc.findAll(descriptor).getCount()
        except Exception as error:  # a disposed bridge here means the office aborted
            found = f"ERROR {type(error).__name__}"
        expect(f"findAll({needle!r}) on a hidden document", found, count)
    doc.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/docx-word-interop"))
    args = parser.parse_args()
    args.out = os.path.abspath(args.out)
    program = os.path.join(os.path.abspath(args.instdir), "program")
    child_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")):
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    profile = os.path.join(args.out, "profile")
    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(profile)
    for _ in range(3):  # exit code 81 = restart requested while the profile is created
        if subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore", "--terminate_after_init",
                           f"-env:UserInstallation=file://{profile}"], env=child_env, timeout=300, check=False).returncode == 0:
            break
    pipe = f"hstdocxword{os.getpid()}"
    # The soffice launcher restarts the office when it asks for it (exit code 81).
    proc = subprocess.Popen([os.path.join(program, "soffice"), "--headless", "--norestore", "--nologo",
                             f"-env:UserInstallation=file://{profile}", f"--accept=pipe,name={pipe};urp;"], env=child_env)
    rows, failed = [], 0

    def expect(name, actual, wanted):
        nonlocal failed
        ok = actual == wanted
        failed += not ok
        rows.append({"check": name, "actual": actual, "expected": wanted, "status": "PASS" if ok else "FAIL"})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {actual!r}", flush=True)

    try:
        ctx = connect(pipe)
        run_checks(ctx, args.out, expect)
        try:
            ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate()
        except Exception:
            pass
    except Exception as error:
        expect("run completed", f"{type(error).__name__}: {error}", "completed")
    finally:
        try:
            proc.wait(60)
        except subprocess.TimeoutExpired:
            proc.kill()
    expect("office exit code", proc.returncode, 0)
    with open(os.path.join(args.out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=1)
    print(f"{len(rows) - failed}/{len(rows)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
