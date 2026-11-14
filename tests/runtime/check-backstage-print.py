#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Print page of the File panel (hst-backstage-print.patch) end to end in a visible office (Linux X display or the
Windows test user's own session). Usage: <python with uno> check-backstage-print.py --soffice PATH --out DIR [--shot CMD]

Fresh profile, fixed port; on Linux the profile gets a generic PDF printer (psprint "pdf=" feature, default printer)
writing into DIR/pdf (Windows: --no-pdf-printer, the default printer must be a PDF/file printer). Per application
(Writer 3 pages, Sheets, Slides 3 slides, Draw 2 pages) .uno:Print, what Ctrl+P runs, must open the File panel's Print
page with the page count of the document (--shot "import -window root {}" saves screenshots). Writer then prints from
the page and from the classic dialog reached by "More Options": both PDFs must have the same pages and text. Closing
the panel cancels the job: .uno:Print opens the page again. Exit 1 when a check fails; stops the office.
"""
import argparse
import glob
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from headless_office import import_uno, props  # noqa: E402

PORT = 22431
PAGE_SETUP, MORE, PRINT = ("Page Setup", "Thiết lập trang"), ("More Options", "Thêm tùy chọn"), ("Print", "In")
failures = []


def check(ok, text):
    print(("PASS  " if ok else "FAIL  ") + text, flush=True)
    if not ok:
        failures.append(text)


def name_of(acc):
    return acc.getAccessibleContext().getAccessibleName().replace("_", "").replace("~", "").rstrip(".… ")


def walk(acc, depth=0):
    yield acc
    ctx = acc.getAccessibleContext()
    if depth < 40:
        for i in range(min(ctx.getAccessibleChildCount(), 500)):
            yield from walk(ctx.getAccessibleChild(i), depth + 1)


class VisibleOffice:
    def __init__(self, soffice, workdir, printer_dir):
        self.uno = import_uno(soffice)
        profile = os.path.join(workdir, "profile")
        if printer_dir:  # a generic PDF printer of the profile (Linux, no CUPS needed)
            os.makedirs(os.path.join(profile, "user", "psprint"), exist_ok=True)
            with open(os.path.join(profile, "user", "psprint", "psprint.conf"), "w", encoding="utf-8") as handle:
                handle.write("[HST PDF]\nPrinter=SGENPRT/HST PDF\nDefaultPrinter=1\nLocation=\nComment=\n"
                             "Command=\nQueueName=\nFeatures=pdf=%s\n" % printer_dir)
        self.proc = subprocess.Popen([soffice, "--norestore", "--nologo", "--nodefault",
                                      "-env:UserInstallation=" + self.uno.systemPathToFileUrl(profile),
                                      f"--accept=socket,host=127.0.0.1,port={PORT};urp;"])
        local = self.uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(240):
            try:
                self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={PORT};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - still starting
                time.sleep(0.5)
        if not hasattr(self, "ctx"):
            raise SystemExit("office did not start")
        self.desktop = self.service("com.sun.star.frame.Desktop")
        self.toolkit = self.service("com.sun.star.awt.Toolkit")

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)

    def dispatch(self, doc, command):
        frame = doc.getCurrentController().getFrame()
        self.service("com.sun.star.frame.DispatchHelper").executeDispatch(frame, command, "", 0, ())

    def find(self, names, timeout=20):
        """The first accessible object named one of names in any top window (waits for it)."""
        for _ in range(timeout * 2):
            for i in range(self.toolkit.getTopWindowCount()):
                for acc in walk(self.toolkit.getTopWindow(i)):
                    if name_of(acc) in names:
                        return acc
            time.sleep(0.5)
        return None

    def labels(self):
        return {name_of(acc) for i in range(self.toolkit.getTopWindowCount()) for acc in walk(self.toolkit.getTopWindow(i))}

    def stop(self):
        try:
            self.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
        try:
            self.proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def make_docs(office):
    docs = {}
    writer = office.desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
    text = writer.Text
    for page in range(3):
        cursor = text.createTextCursorByRange(text.getEnd())
        if page:
            cursor.BreakType = 4  # PAGE_BEFORE
        text.insertString(cursor, "HST print page %d. " % (page + 1) + "Synthetic text. " * 40, False)
        text.insertControlCharacter(text.getEnd(), 0, False)
    docs["writer"] = (writer, 3)
    calc = office.desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
    calc.Sheets.getByIndex(0).getCellRangeByPosition(0, 0, 3, 9).setDataArray(
        tuple(tuple("R%dC%d" % (r, c) for c in range(4)) for r in range(10)))
    docs["calc"] = (calc, 1)
    impress = office.desktop.loadComponentFromURL("private:factory/simpress", "_blank", 0, ())
    while impress.DrawPages.Count < 3:
        impress.DrawPages.insertNewByIndex(impress.DrawPages.Count)
    docs["impress"] = (impress, 3)
    draw = office.desktop.loadComponentFromURL("private:factory/sdraw", "_blank", 0, ())
    draw.DrawPages.insertNewByIndex(0)
    docs["draw"] = (draw, 2)
    return docs


def pdf_summary(path):
    text = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True).stdout
    info = subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout
    return [line for line in info.splitlines() if line.startswith(("Pages:", "Page size:"))], text.split()


def wait_pdf(folder, before, timeout=60):
    for _ in range(timeout * 2):
        new = sorted(set(glob.glob(os.path.join(folder, "*.pdf"))) - before)
        if new and os.path.getsize(new[0]) > 0:
            time.sleep(2)  # the file is complete when the job ended
            return new[0]
        time.sleep(0.5)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsprint-"))
    parser.add_argument("--shot", help="screenshot command with {} for the file, e.g. 'import -window root {}'")
    parser.add_argument("--no-pdf-printer", action="store_true", help="Windows: use the installed default printer")
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    pdf_dir = os.path.join(out, "pdf")
    os.makedirs(pdf_dir, exist_ok=True)
    office = VisibleOffice(args.soffice, out, None if args.no_pdf_printer else pdf_dir)
    try:
        docs = make_docs(office)
        for app, (doc, pages) in docs.items():
            doc.getCurrentController().getFrame().getContainerWindow().setFocus()
            office.dispatch(doc, ".uno:Print")
            shown = office.find(PAGE_SETUP) is not None and office.find(MORE) is not None
            check(shown, f"{app}: .uno:Print opens the Print page of the File panel")
            time.sleep(3)  # the preview is painted on idle
            check(f"/ {pages}" in office.labels(), f"{app}: the preview counts {pages} page(s)")
            if args.shot:
                subprocess.run(args.shot.format(os.path.join(out, f"{app}-print-page.png")), shell=True, check=False)
            office.dispatch(doc, ".uno:HSTBackstage")  # closes the panel: the job is cancelled
            time.sleep(1)
        writer = docs["writer"][0]
        office.dispatch(writer, ".uno:Print")
        check(office.find(PAGE_SETUP) is not None, "writer: the Print page opens again after a cancelled job")
        if not args.no_pdf_printer:
            before = set(glob.glob(os.path.join(pdf_dir, "*.pdf")))
            button = office.find(PRINT)
            button.getAccessibleContext().doAccessibleAction(0)
            panel_pdf = wait_pdf(pdf_dir, before)
            check(panel_pdf is not None, "writer: the In button prints to the PDF printer")
            office.dispatch(writer, ".uno:Print")
            office.find(MORE).getAccessibleContext().doAccessibleAction(0)
            time.sleep(3)
            if args.shot:
                subprocess.run(args.shot.format(os.path.join(out, "writer-classic-dialog.png")), shell=True, check=False)
            before = set(glob.glob(os.path.join(pdf_dir, "*.pdf")))
            office.find(PRINT).getAccessibleContext().doAccessibleAction(0)  # the dialog's Print button
            dialog_pdf = wait_pdf(pdf_dir, before)
            check(dialog_pdf is not None, "writer: the classic dialog from More Options prints the same job")
            if panel_pdf and dialog_pdf:
                check(pdf_summary(panel_pdf) == pdf_summary(dialog_pdf),
                      "writer: the page and the classic dialog print the same pages and text")
        for doc, _ in docs.values():
            doc.setModified(False)  # the office quits without asking
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
