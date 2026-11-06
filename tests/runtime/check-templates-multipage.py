#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Multi-page check of the administrative templates ("Văn bản hành chính") and of the wizard output of the same types.

For every Writer template and page count of tests/fixtures/templates/multipage.json the body is grown with realistic
Vietnamese paragraphs and a numbered list (a ruled form grows by table rows) until the document runs to that many pages;
it is exported to PDF, ODT, DOCX and DOC, the copies are reopened and printed again, and every page is measured:
margins, page number (none on a first page, then centred in the top margin, continuous), header blocks only on page 1,
signature block and Nơi nhận on one page, no blank page, contact details of an official letter on page 1, fonts, and
the DOCX section properties Word lays out from. A line-by-line sweep across the first page break checks that the
signature block never splits and never leaves a blank last page. Registers get 120 entries and must print them all
with the header rows on every page.

Usage: python3 tests/runtime/check-templates-multipage.py [--instdir upstream/libreoffice/instdir] [--only ID ...]
       [--pages 1 2 3 5] [--paths template wizard] [--out tests/output/templates-multipage]
Exit 0 PASS, 1 FAIL, 2 BLOCKED (no office or poppler). The office runs headless with its own profile and is stopped.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "extensions/hst-vietnamese-tools/python"))
RULES = os.path.join(ROOT, "tests/fixtures/templates/multipage.json")
PORT = 22093


def start_office(instdir, work):
    program = os.path.join(os.path.abspath(instdir), "program")
    sys.path.insert(0, program)
    os.environ["URE_BOOTSTRAP"] = "vnd.sun.star.pathname:" + os.path.join(program, "fundamentalrc")
    profile = os.path.join(work, "profile")
    proc = subprocess.Popen([os.path.join(program, "soffice"), "--headless", "--invisible", "--norestore", "--nologo", "--nodefault",
                             "-env:UserInstallation=file://" + profile, "--accept=socket,host=127.0.0.1,port=%d;urp;" % PORT],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(120):
        try:
            ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=%d;urp;StarOffice.ComponentContext" % PORT)
            return proc, ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        except Exception:
            if proc.poll() is not None:
                break
            time.sleep(1)
    stop_office(proc, None)
    raise SystemExit(2)


def stop_office(proc, desktop):
    try:
        if desktop is not None:
            desktop.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, 15)
        proc.wait(timeout=30)


def writer_case(desktop, rules, entry, spec, path_kind, pages, out):
    import templates_multipage_fill as F
    import templates_multipage_measure as M
    from hst_office.nd30 import get_type
    ident = entry["id"]
    t = get_type(ident)
    profile, attached = t["profile"], bool(t.get("attached"))
    base = os.path.join(out, path_kind, ident, "p%d" % pages)
    os.makedirs(base, exist_ok=True)
    document = F.create(desktop, path_kind, ident, os.path.join(out, "templates", entry["output"]))
    problems = []
    try:
        single = ident in rules["singleSheet"]
        filler = None if single else F.filler_for(document, spec.get("edit", "Body"), entry["output"].startswith("van-thu/"))
        reached = F.grow(document, filler, pages)
        sig = document.signature_pages()
        if sig and sig[0] != sig[1]:
            problems.append("signature block split over pages %s" % sig)
        for fmt in ("pdf", "odt", "docx", "doc"):
            document.export(os.path.join(base, "doc." + fmt), fmt)
    finally:
        document.close()
    for fmt in ("odt", "docx", "doc"):
        copy = desktop.loadComponentFromURL(F.url(os.path.join(base, "doc." + fmt)), "_blank", 0, F.props(Hidden=True))
        try:
            F.Document(copy).export(os.path.join(base, fmt + ".pdf"), "pdf")
        finally:
            copy.close(True)
    if single or (path_kind == "wizard" and ident in rules["appendedBlocks"]):
        return {"reached": reached, "problems": problems, "note": rules["singleSheet"].get(ident) or rules["appendedBlocks"].get(ident)}
    found, facts = M.pdf_problems(os.path.join(base, "doc.pdf"), profile, rules, attached)
    problems += ["pdf: " + x for x in found]
    for fmt in ("odt", "docx", "doc"):
        pdf = os.path.join(base, fmt + ".pdf")
        copy_found, copy_facts = M.pdf_problems(pdf, profile, rules, attached)
        problems += ["%s copy: %s" % (fmt, x) for x in copy_found]
        if copy_facts["pages"] != facts["pages"]:
            problems.append("%s copy has %d pages, original %d" % (fmt, copy_facts["pages"], facts["pages"]))
        shift = M.drift(os.path.join(base, "doc.pdf"), pdf, ignore=(rules["contactText"],))
        if shift[0] > 1.0:
            problems.append("%s copy: text moved %.1f mm (%s)" % (fmt, *shift))
    problems += ["docx: " + x for x in M.docx_problems(os.path.join(base, "doc.docx"), profile, rules)]
    return {"reached": reached, "pdfPages": facts["pages"], "problems": problems}


def sweep_case(desktop, entry, spec, path_kind, out):
    import templates_multipage_fill as F
    document = F.create(desktop, path_kind, entry["id"], os.path.join(out, "templates", entry["output"]))
    try:
        filler = F.filler_for(document, spec.get("edit", "Body"), False)
        return F.sweep(document, filler) if filler is not None else []
    finally:
        document.close()


def register_case(desktop, rules, entry, out):
    import templates_multipage_fill as F
    import templates_multipage_measure as M
    base = os.path.join(out, "registers", entry["id"])
    os.makedirs(base, exist_ok=True)
    doc = desktop.loadComponentFromURL(F.url(os.path.join(out, "templates", entry["output"])), "_blank", 0, F.props(Hidden=True, AsTemplate=True))
    count = rules["registerRows"]
    try:
        sheet = doc.Sheets.getByName("Sổ")
        cols = len([c for c in range(30) if sheet.getCellByPosition(c, 0).getString()])
        data = tuple(tuple("Mục %d dòng %d" % (c + 1, r + 1) for c in range(cols)) for r in range(count))
        sheet.getCellRangeByPosition(0, 2, cols - 1, count + 1).setDataArray(data)
        heading = sheet.getCellByPosition(0, 1).getString()
        doc.storeToURL(F.url(os.path.join(base, "doc.pdf")), F.props(FilterName="calc_pdf_Export"))
        doc.storeToURL(F.url(os.path.join(base, "doc.xlsx")), F.props(FilterName="Calc MS Excel 2007 XML", Overwrite=True))
    finally:
        doc.close(True)
    copy = desktop.loadComponentFromURL(F.url(os.path.join(base, "doc.xlsx")), "_blank", 0, F.props(Hidden=True))
    try:
        copy.storeToURL(F.url(os.path.join(base, "xlsx.pdf")), F.props(FilterName="calc_pdf_Export"))
    finally:
        copy.close(True)
    problems = []
    for name in ("doc.pdf", "xlsx.pdf"):
        pages = M.pdf_lines(os.path.join(base, name))
        text = ["\n".join(ln["text"] for ln in p) for p in pages]
        printed = {int(x) for t in text for x in re.findall(r"dòng\s+(\d+)", t)}
        if len(printed) != count:
            problems.append("%s: %d of %d entries printed" % (name, len(printed), count))
        for k, t in enumerate(text, 1):
            if "dòng" in t and heading not in t:
                problems.append("%s: p%d has entries without the header rows" % (name, k))
    return {"problems": problems}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tests/output/templates-multipage"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--pages", nargs="*", type=int)
    ap.add_argument("--paths", nargs="*")
    ap.add_argument("--no-sweep", action="store_true")
    a = ap.parse_args()
    rules = json.load(open(RULES, encoding="utf-8"))
    if not shutil.which("pdftotext") or not shutil.which("pdffonts") or not os.path.exists(os.path.join(a.instdir, "program", "soffice")):
        print("BLOCKED: soffice or poppler missing")
        return 2
    os.makedirs(a.out, exist_ok=True)
    out = tempfile.mkdtemp(prefix="run-", dir=a.out)
    env = dict(os.environ, SOURCE_DATE_EPOCH="1767225600")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts/generate-templates.py"), "--out", os.path.join(out, "templates")], check=True, env=env,
                   stdout=subprocess.DEVNULL)
    from templates.runtime_requirements import load_requirements, resolve
    manifest = json.load(open(os.path.join(out, "templates", "manifest.json"), encoding="utf-8"))
    table = load_requirements([e["id"] for e in manifest["templates"]])
    proc, desktop = start_office(a.instdir, out)
    report, failed = {"results": []}, 0
    try:
        for entry in manifest["templates"]:
            ident = entry["id"]
            if a.only and ident not in a.only:
                continue
            if entry["module"] == "sheets":
                if entry["output"].startswith("van-thu/"):
                    result = {"id": ident, "case": "register", **register_case(desktop, rules, entry, out)}
                    report["results"].append(result)
                    failed += bool(result["problems"])
                    print(("FAIL" if result["problems"] else "PASS"), ident, "; ".join(result["problems"]), flush=True)
                continue
            if entry["module"] != "writer":
                continue
            spec = resolve(table, ident)
            for path_kind in a.paths or rules["paths"]:
                for pages in ([1] if ident in rules["singleSheet"] else (a.pages or rules["pageCounts"])):
                    result = {"id": ident, "path": path_kind, "pages": pages, **writer_case(desktop, rules, entry, spec, path_kind, pages, out)}
                    report["results"].append(result)
                    failed += bool(result["problems"])
                    print(("FAIL" if result["problems"] else "PASS"), path_kind, ident, pages, "; ".join(result["problems"])[:600], flush=True)
                if not a.no_sweep and ident not in rules["singleSheet"] and not entry["output"].startswith("van-thu/") and not (path_kind == "wizard" and ident in rules["appendedBlocks"]):
                    problems = sweep_case(desktop, entry, spec, path_kind, out)
                    report["results"].append({"id": ident, "path": path_kind, "case": "sweep", "problems": problems})
                    failed += bool(problems)
                    print(("FAIL" if problems else "PASS"), path_kind, ident, "sweep", "; ".join(problems)[:300], flush=True)
    finally:
        stop_office(proc, desktop)
    report["status"] = "FAIL" if failed else "PASS"
    with open(os.path.join(out, "multipage.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print("%s: %d failing cases; %s" % (report["status"], failed, os.path.join(out, "multipage.json")))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
