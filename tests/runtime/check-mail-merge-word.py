# SPDX-License-Identifier: AGPL-3.0-only
"""Word-compatible mail merge on an installed HST Office: a Word-made letter (.docx with w:mailMerge naming an Excel
list in a Windows folder that does not exist here, MERGEFIELD switches, IF fields) next to its list.

  python3 tests/runtime/check-mail-merge-word.py --instdir <office folder> [--out <folder>] [--list csv]

Checks: opening the letter connects it to the list next to it (job on OnLoad) without marking it modified; the
fields are imported with their Word instructions; merging to one document gives Word's text for every recipient
(mail_merge_word_samples.EXPECTED); merging to PDF gives one file per recipient with that text; saving as .docx
writes the nested MERGEFIELDs and Word's w:mailMerge link; the saved letter reads back the same instructions.
Exit 1 when a check fails; evidence.json, the letter, the merged files and the saved .docx stay in --out."""
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
import mail_merge_word_samples as samples  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IF_COLUMN = 'IF { MERGEFIELD Giới_tính } = "Nam" "Ông" "Bà"'


def connect(pipe, timeout=180):
    import uno
    local = uno.getComponentContext()
    deadline = time.time() + timeout
    time.sleep(6)
    while True:
        try:
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            return resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
        except Exception:  # NoConnectException until soffice listens
            if time.time() > deadline:
                raise
            time.sleep(1)


def columns(doc):
    found = {}
    enum = doc.TextFields.createEnumeration()
    while enum.hasMoreElements():
        field = enum.nextElement()
        if field.supportsService("com.sun.star.text.TextField.Database"):
            master = field.TextFieldMaster
            found[master.DataColumnName] = master.DataBaseName
    return found


def pdf_text(path):
    try:
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None


def run_checks(ctx, out, expect, list_kind):
    import uno
    from com.sun.star.beans import PropertyValue
    from hst_office import mail_merge_output as output
    from hst_office import mail_merge_session as sessions

    def prop(name, value):
        return PropertyValue(Name=name, Value=value)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    letter_dir = os.path.join(out, "thu")
    source = "C:\\Users\\vanthu\\Documents\\Tron thu\\" + (samples.CSV if list_kind == "csv" else samples.XLSX)
    letter = samples.write_all(letter_dir, source)
    wanted_list = os.path.join(letter_dir, os.path.basename(source.replace("\\", "/")))

    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(letter), "_blank", 0, (prop("Hidden", True),))
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

    session.load(ctx)
    merged, count = output.run(ctx, doc, session, output.Request(output.EDIT, session.checked()))
    got = [line for line in merged.Text.String.split("\n") if line.strip()]
    want = [line for record in samples.EXPECTED for line in record if line.strip()]
    expect("merge: recipients", count, len(samples.EXPECTED))
    expect("merge: Word's text for every recipient", got, want)
    merged.storeToURL(uno.systemPathToFileUrl(os.path.join(out, "tron-thu.odt")), (prop("FilterName", "writer8"),))
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
    again = desktop.loadComponentFromURL(uno.systemPathToFileUrl(saved), "_blank", 0, (prop("Hidden", True),))
    expect("reopen: instructions read back", IF_COLUMN in columns(again), True)
    again.close(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", required=True, help="office folder (with program/ and share/extensions/)")
    parser.add_argument("--out", default=os.path.join(ROOT, "tests/output/mail-merge-word"))
    parser.add_argument("--list", choices=("xlsx", "csv"), default="xlsx")
    args = parser.parse_args()
    out, instdir = os.path.abspath(args.out), os.path.abspath(args.instdir)
    program = os.path.join(instdir, "program")
    sys.path.insert(0, os.path.join(instdir, "share", "extensions", "hst-vietnamese-tools", "python"))
    child_env = {k: v for k, v in os.environ.items() if k != "URE_BOOTSTRAP"}
    if os.path.exists(os.path.join(program, "uno.py")):
        sys.path.insert(0, program)
        os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    profile = os.path.join(out, "profile")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(profile)
    profile_url = "file:///" + profile.replace("\\", "/").lstrip("/")
    binary = os.path.join(program, "soffice.exe" if os.name == "nt" else "soffice")
    pipe = f"hstmailmerge{os.getpid()}"
    proc = subprocess.Popen([binary, "--headless", "--norestore", "--nologo", f"-env:UserInstallation={profile_url}",
                             f"--accept=pipe,name={pipe};urp;"], env=child_env)
    rows, failed = [], 0

    def expect(name, actual, wanted):
        nonlocal failed
        ok = actual == wanted
        failed += not ok
        rows.append({"check": name, "actual": actual, "expected": wanted, "status": "PASS" if ok else "FAIL"})
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {actual!r}", flush=True)

    try:
        ctx = connect(pipe)
        run_checks(ctx, out, expect, args.list)
        try:
            ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away with the office
            pass
    except Exception as error:  # noqa: BLE001 - recorded as a failed check
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
