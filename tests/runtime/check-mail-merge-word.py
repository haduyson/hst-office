# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Word-compatible mail merge on an installed HST Office: a Word-made letter (.docx with w:mailMerge naming an Excel
list in a Windows folder that does not exist here, MERGEFIELD switches, IF fields) next to its list.

  check-mail-merge-word.py --instdir <office folder> [--out <folder>] [--list csv] [--keep-blank-lines]

Checks: opening the letter connects it to the list next to it (job on OnLoad) without marking it modified; the
fields are imported with their Word instructions; merging to one document gives Word's text for every recipient
(mail_merge_word_samples.word_output: the paragraph of the empty "Chức vụ" is left out, or kept with
--keep-blank-lines, the letter then having w:doNotSuppressBlankLines); merging to PDF gives one file per recipient with that text; saving as .docx
writes the nested MERGEFIELDs and Word's w:mailMerge link; the saved letter reads back the same instructions.
Exit 1 when a check fails; evidence.json, the letter, the merged files and the saved .docx stay in --out."""
import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mail_merge_word_pages as pages, mail_merge_word_samples as samples  # noqa: E401,E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IF_COLUMN = 'IF { MERGEFIELD Giới_tính } = "Nam" "Ông" "Bà"'


def connect(port, timeout=180):
    import uno
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    time.sleep(6)
    while True:
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
            ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getComponents()
            return ctx
        except Exception:  # NoConnectException until soffice listens; a disposed bridge while it restarts
            if time.time() > deadline:
                raise
            time.sleep(2)


def columns(doc, tries=20):
    for _ in range(tries):  # {column: data source}; read again while the reconnect job replaces the fields
        found, enum = {}, doc.TextFields.createEnumeration()
        try:
            while enum.hasMoreElements():
                field = enum.nextElement()
                if field.supportsService("com.sun.star.text.TextField.Database"):
                    found[field.TextFieldMaster.DataColumnName] = field.TextFieldMaster.DataBaseName
            return found
        except Exception:  # noqa: BLE001 - UnknownPropertyException for a field being replaced
            time.sleep(0.5)
    return found


def pdf_text(path):
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=60).stdout
    return None


def run_checks(ctx, out, expect, list_kind, keep):
    import uno
    from com.sun.star.beans import PropertyValue
    from hst_office import mail_merge_output as output, mail_merge_session as sessions
    prop = lambda name, value: PropertyValue(Name=name, Value=value)  # noqa: E731
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    letter_dir = os.path.join(out, "thu")
    source = "C:\\Users\\vanthu\\Documents\\Tron thu\\" + (samples.CSV if list_kind == "csv" else samples.XLSX)
    letter = samples.write_all(letter_dir, source, keep)
    wanted_list = os.path.join(letter_dir, os.path.basename(source.replace("\\", "/")))

    # Not hidden: the office sends OnLoad, which runs the reconnect job, only for a document loaded visibly
    # (SfxObjectShell::PostActivateEvent_Impl), as when a user opens the letter.
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(letter), "_blank", 0, ())
    deadline = time.time() + 60
    found = columns(doc)
    while "" in found.values() and time.time() < deadline:
        time.sleep(1)
        found = columns(doc)
    expect("import: IF with a nested MERGEFIELD", IF_COLUMN in found, True)
    expect("import: MERGEFIELD switches kept", 'MERGEFIELD Lương \\# "#,##0"' in found, True)
    session = sessions.get(doc)
    expect("open: connected to the list next to the letter", session.meta["source"], wanted_list)
    expect("open: fields read the HST data source", sorted({v[:12] for v in found.values()}), ["HST_TronThu_"])
    expect("open: the letter is not marked modified", doc.isModified(), False)
    bag = {p.Name: p.Value for p in doc.getPropertyValue("InteropGrabBag")}
    link = {p.Name: p.Value for p in bag.get("HSTMailMergeSource", ())}
    expect("open: Word link of the list", link.get("Path"), wanted_list)
    settings = doc.createInstance("com.sun.star.text.DocumentSettings")
    expect("open: paragraphs of empty fields hidden as in Word", settings.EmptyDbFieldHidesPara, not keep)

    session.load(ctx)
    merged, count = output.run(ctx, doc, session, output.Request(output.EDIT, session.checked()))
    lines = merged.Text.String.splitlines()  # \r\n on Windows
    word, year = samples.word_output(keep), samples.EXPECTED[1][4]  # recipient 2: no Chức vụ after the year
    expect("merge: recipients", count, len(samples.EXPECTED))
    expect("merge: Word's text for every recipient", [line for line in lines if line.strip()],
           [line for record in word for line in record if line.strip()])
    expect("merge: paragraph after the empty Chức vụ field", lines[lines.index(year) + 1] if year in lines else None,
           word[1][word[1].index(year) + 1])
    merged.storeToURL(uno.systemPathToFileUrl(os.path.join(out, "tron-thu.odt")), (prop("FilterName", "writer8"),))
    pages.check(merged, out, expect, len(samples.EXPECTED))
    merged.close(True)

    pdf_dir = os.path.join(out, "pdf")
    output.run(ctx, doc, session, output.Request(output.PDF, session.checked(), "{Họ và tên}", pdf_dir))
    names = sorted(os.listdir(pdf_dir))
    expect("PDF: one file per recipient", len(names), len(samples.EXPECTED))
    text = pdf_text(os.path.join(pdf_dir, "Trần Thị Bích Ngọc.pdf"))
    if text is not None:
        expect("PDF: Word's text", all(line in text for line in samples.EXPECTED[1] if line), True)

    saved = os.path.join(out, "thu-moi-hst.docx")
    doc.storeToURL(uno.systemPathToFileUrl(saved), (prop("FilterName", "MS Word 2007 XML"),))
    doc.close(True)
    with zipfile.ZipFile(saved) as package:
        body = package.read("word/document.xml").decode("utf-8")
        settings = package.read("word/settings.xml").decode("utf-8")
        rels = package.read("word/_rels/settings.xml.rels").decode("utf-8")
    expect("save: nested MERGEFIELD inside the IF",
           bool(re.search(r'<w:fldChar w:fldCharType="begin"/><w:instrText[^>]*> MERGEFIELD Giới_tính </w:instrText>'
                          r'<w:fldChar w:fldCharType="end"/>', body)), True)
    expect("save: MERGEFIELD switches written", ' MERGEFIELD Lương \\# &quot;#,##0&quot; ' in body
           or ' MERGEFIELD Lương \\# "#,##0" ' in body, True)
    expect("save: Word link of the list", "mailMergeSource" in rels and "<w:dataSource " in settings, True)
    expect("save: no internal data source name for Word", "HST_TronThu_" in settings, False)
    expect("save: w:doNotSuppressBlankLines as in the letter", "<w:doNotSuppressBlankLines/>" in settings, keep)
    again = desktop.loadComponentFromURL(uno.systemPathToFileUrl(saved), "_blank", 0, (prop("Hidden", True),))
    expect("reopen: instructions read back", IF_COLUMN in columns(again), True)
    again.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True, help="office folder (with program/ and share/extensions/)")
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/mail-merge-word"))
    parser.add_argument("--list", choices=("xlsx", "csv"), default="xlsx")
    parser.add_argument("--port", type=int, default=2117)
    parser.add_argument("--keep-blank-lines", action="store_true",
                        help="the letter has w:doNotSuppressBlankLines: the empty Chức vụ paragraph stays")
    args = parser.parse_args()
    out, instdir = os.path.abspath(args.out), os.path.abspath(args.instdir)
    program = os.path.join(instdir, "program")
    sys.path.insert(0, os.path.join(instdir, "share", "extensions", "hst-vietnamese-tools", "python"))
    child_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")):
        sys.path.insert(0, program)
        rc = "fundamental.ini" if os.name == "nt" else "fundamentalrc"  # the Windows office names it .ini
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, rc)
    profile = os.path.join(out, "profile")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(profile)
    profile_url = "file:///" + profile.replace("\\", "/").lstrip("/")
    binary = os.path.join(program, "soffice.exe" if os.name == "nt" else "soffice")
    for _ in range(3):  # create the profile first: the office restarts itself once (exit code 81) while doing so
        if subprocess.run([os.path.join(program, "soffice.bin"), "--headless", "--norestore", "--terminate_after_init",
                           f"-env:UserInstallation={profile_url}"], env=child_env, timeout=300).returncode == 0:
            break
    proc = subprocess.Popen([binary, "--headless", "--norestore", "--nologo", f"-env:UserInstallation={profile_url}",
                             f"--accept=socket,host=127.0.0.1,port={args.port};urp;"], env=child_env)
    rows, failed = [], 0

    def expect(name, actual, wanted):
        nonlocal failed
        ok = actual == wanted
        failed += not ok
        rows.append({"check": name, "actual": actual, "expected": wanted, "status": "PASS" if ok else "FAIL"})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {actual!r}", flush=True)

    try:
        ctx = connect(args.port)
        run_checks(ctx, out, expect, args.list, args.keep_blank_lines)
        with contextlib.suppress(Exception):  # the bridge goes away with the office
            ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate()
    except Exception as error:  # noqa: BLE001 - recorded as a failed check
        import traceback
        traceback.print_exc()
        expect("run completed", f"{type(error).__name__}: {error}", "completed")
    finally:
        try:
            proc.wait(90)
        except subprocess.TimeoutExpired:
            proc.kill()
    with open(os.path.join(out, "evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=1)
    print(f"{len(rows) - failed}/{len(rows)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
