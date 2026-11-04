# SPDX-License-Identifier: AGPL-3.0-only
"""Check that new documents save as .docx / .xlsx / .pptx by default, without the "Keep current
format" question, on a real HST Office build (GTK3, fresh profile, vi UI).

Usage: python3 tests/runtime/check-msoffice-save-format.py [--instdir upstream/libreoffice/instdir]
       [--out tests/output/msoffice-save-format] [--display :97]

  1. Configuration: Setup Factories ooSetupFactoryDefaultFilter = MS Word 2007 XML,
     Calc MS Excel 2007 XML, Impress MS PowerPoint 2007 XML; WarnAlienFormat stays on.
  2. Per document - a blank Writer document with an ND 30 "Quyết định" inserted by the bundled
     extension's own code, a document from the HST "Công văn" template, a workbook from the
     "Bảng lương" template, a presentation from the "Hội nghị" template - Ctrl+S opens the file
     dialog, the typed name is saved as .docx/.xlsx/.pptx (the file is an OOXML package) and no
     other dialog appears; after an edit, Ctrl+S saves again with no dialog at all.
  3. AutoRecovery (interval set to 1 minute): the modified .docx gets a recovery copy.
  4. The ND 30 document reopened from .docx keeps its A4 page and margins (20/20/30/15 mm).
  5. Legacy formats still warn: a document stored as .doc / .xls / .ppt, edited, then Ctrl+S
     shows the "Keep current format" question.
Exit 1 when any check fails.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hst_gui  # noqa: E402
import msoffice_save_steps as steps  # noqa: E402
from shortcut_keys import RESULTS, Keys, check, wait  # noqa: E402

PORT = 22953


def run(office, keys, args, work):
    steps.config_checks(office)
    files = os.path.join(work, "files")
    shutil.rmtree(files, ignore_errors=True)
    os.makedirs(files)
    subprocess.run(["chown", hst_gui.BUILD_USER, files], check=False)

    nd30 = office.load("private:factory/swriter")
    wait(lambda: keys.doc_window() is not None, 20)
    result = steps.insert_nd30(office, nd30, args.instdir)
    check("ND 30 Quyết định inserted by the extension code", not result.get("blockers"), json.dumps(result, ensure_ascii=False)[:200])
    office.raise_windows()
    nd30_path = os.path.join(files, "quyet-dinh")
    if steps.first_save(office, keys, nd30, nd30_path, ".docx", "ND 30 document"):
        steps.resave(office, keys, nd30, "ND 30 document", False)
        steps._touch(nd30)
        backup = os.path.join(work, "profile", "user", "backup")
        before = set(glob.glob(os.path.join(backup, "*")))
        check("AutoRecovery writes a backup of the modified .docx",
              wait(lambda: set(glob.glob(os.path.join(backup, "*"))) - before, 110), os.listdir(backup) if os.path.isdir(backup) else "no dir")
        steps.close(nd30)
        reopened = office.load("file://" + nd30_path + ".docx")
        check("ND 30 .docx is A4 with margins 20/20/30/15 mm", steps._ooxml_page(nd30_path + ".docx") == (210, 297, 20, 20, 30, 15),
              steps._ooxml_page(nd30_path + ".docx"))
        check("ND 30 .docx keeps its text", "QUYẾT ĐỊNH" in reopened.getText().getString())
        steps.close(reopened)

    for rel, ext, name in (("hst-van-ban/cong-van.ott", ".docx", "Công văn template"),
                           ("hst-bang-tinh/bang-luong.ots", ".xlsx", "Bảng lương template"),
                           ("hst-trinh-chieu/hoi-nghi.otp", ".pptx", "Hội nghị template")):
        doc = steps.load_template(office, steps.template(args.instdir, rel))
        steps.focus_document(office, keys)
        steps._touch(doc)
        path = os.path.join(files, os.path.basename(rel).rsplit(".", 1)[0])
        if steps.first_save(office, keys, doc, path, ext, name):
            steps.resave(office, keys, doc, name, False)
        steps.close(doc)

    for factory, legacy, filter_name in (("swriter", ".doc", "MS Word 97"), ("scalc", ".xls", "MS Excel 97"),
                                         ("simpress", ".ppt", "MS PowerPoint 97")):
        path = os.path.join(files, "cu" + legacy)
        doc = office.load(f"private:factory/{factory}", hidden=True)
        steps._touch(doc)
        steps.store_legacy(doc, path, filter_name)
        steps.close(doc)
        doc = office.load("file://" + path)  # as a user opens an old file
        steps.focus_document(office, keys)
        steps.resave(office, keys, doc, f"legacy {legacy}", True)
        steps.close(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(hst_gui.ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--out", default=os.path.join(hst_gui.ROOT, "tests/output/msoffice-save-format"))
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    hst_gui.setup_uno(args.instdir)
    work = os.path.abspath(args.out)
    os.makedirs(work, exist_ok=True)
    office = hst_gui.Office(args.instdir, work, PORT, display=args.display, lang="vi_VN.UTF-8", restore=True,
                            config=[("/org.openoffice.Office.Impress/Misc", "StartWithTemplate", "false"),
                                    ("/org.openoffice.Office.Recovery/AutoSave", "TimeIntervall", "1"),
                                    ("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", "false")])
    try:
        office.start()
        run(office, Keys(office), args, work)
        office.screenshot(os.path.join(work, "final.png"))
        for comp in office.desktop().getComponents():  # no "save?" question on terminate
            comp.setModified(False)
    except Exception as error:  # noqa: BLE001
        check("run completed", False, repr(error))
    finally:
        office.stop()
    failed = [name for name, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
