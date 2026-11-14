#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Print page of the File panel (hst-backstage-print.patch) end to end in a visible office (Linux X display, gen
plugin; Windows: the test user's own session). Widgets are driven by id through the UITest service, no keys.
Usage: <office python> check-backstage-print.py --soffice PATH --out DIR [--shot CMD] [--no-pdf-printer]
Linux profiles get a generic PDF printer (psprint "pdf=", default) writing into DIR/pdf. Per application .uno:Print
(what Ctrl+P runs) must open the Print page with the document's page count; Writer then prints from the page and from
the classic dialog ("More Options"): same pages and text. Closing the panel cancels the job. Exit 1 on a failure.
"""
import argparse, glob, os, subprocess, sys, tempfile, time  # noqa: E401

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from headless_office import import_uno  # noqa: E402

PORT, failures = 22431, []


def check(ok, text):
    print(("PASS  " if ok else "FAIL  ") + text, flush=True)
    failures.extend([] if ok else [text])


def state(obj):
    return {p.Name: p.Value for p in obj.getState()}


class VisibleOffice:
    def __init__(self, soffice, workdir, printer_dir):
        self.uno = import_uno(soffice)
        profile = os.path.join(workdir, "profile")
        url = self.uno.systemPathToFileUrl(profile)
        # a fresh profile restarts the office once (the bridge would go with it): make it first
        subprocess.run([soffice, "--headless", "--terminate_after_init", "-env:UserInstallation=" + url], timeout=300)
        if printer_dir:  # a generic printer of the profile that writes PDF files (Linux, no CUPS needed)
            os.makedirs(os.path.join(profile, "user", "psprint"), exist_ok=True)
            with open(os.path.join(profile, "user", "psprint", "psprint.conf"), "w", encoding="utf-8") as handle:
                # the generic printer spools a PDF into its command: one file per job
                handle.write("[HST PDF]\nPrinter=SGENPRT/HST PDF\nDefaultPrinter=1\nLocation=\nComment=\n"
                             "Command=cat > %s/job-$(date +%%s%%N).pdf\nQueueName=\nFeatures=\n" % printer_dir)
        self.proc = subprocess.Popen([soffice, "--norestore", "--nologo", "--nodefault",
                                      "-env:UserInstallation=" + url,
                                      f"--accept=socket,host=127.0.0.1,port={PORT};urp;"])
        local = self.uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(240):
            try:
                self.ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={PORT};urp;StarOffice.ComponentContext")
                break
            except Exception:  # noqa: BLE001 - still starting
                time.sleep(0.5)
        assert hasattr(self, "ctx"), "office did not start"
        self.desktop = self.service("com.sun.star.frame.Desktop")
        self.ui = self.service("com.sun.star.ui.test.UITest")
        self.set_config("/org.hasontech.hstoffice.Welcome", "Shown", True)
        try:
            self.set_config("/org.hasontech.hstoffice.UpdateCheck", "AutoCheck", False)
        except Exception:  # noqa: BLE001 - not in every build
            pass

    def service(self, name):
        return self.ctx.ServiceManager.createInstanceWithContext(name, self.ctx)

    def set_config(self, node, name, value):
        from com.sun.star.beans import PropertyValue
        arg = PropertyValue()
        arg.Name, arg.Value = "nodepath", node
        access = self.service("com.sun.star.configuration.ConfigurationProvider").createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationUpdateAccess", (arg,))
        access.setPropertyValue(name, value)
        access.commitChanges()

    def close_welcome(self):
        top = self.ui.getTopFocusWindow()
        if "chào đón" in str(state(top).get("Text", "")).lower() and "ok" in top.getChildren():
            top.getChild("ok").executeAction("CLICK", ())

    def wait_dialog(self, dialog_id, timeout=30):
        """The top focus window once it is the dialog with that id, else None."""
        for _ in range(timeout * 2):
            if state(top := self.ui.getTopFocusWindow()).get("ID") == dialog_id:
                return top
            time.sleep(0.5)

    def stop(self):
        try:
            self.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
            pass
        try:
            self.proc.wait(timeout=60)
        except subprocess.TimeoutExpired:  # the wrapper is gone; the office of this profile is killed below
            self.proc.kill()


def make_doc(office, app):
    """A new document (with document tabs it becomes the shown tab) and its page count."""
    doc = office.desktop.loadComponentFromURL(f"private:factory/{app}", "_blank", 0, ())
    if app == "swriter":
        text = doc.Text
        for page in range(3):
            cursor = text.createTextCursorByRange(text.getEnd())
            if page:
                cursor.BreakType = 4  # PAGE_BEFORE
            text.insertString(cursor, "HST print page %d. " % (page + 1) + "Synthetic text. " * 40, False)
            text.insertControlCharacter(text.getEnd(), 0, False)
        return doc, 3
    if app == "scalc":
        doc.Sheets.getByIndex(0).getCellRangeByPosition(0, 0, 3, 9).setDataArray(
            tuple(tuple("R%dC%d" % (r, c) for c in range(4)) for r in range(10)))
        return doc, 1
    while doc.DrawPages.Count < (3 if app == "simpress" else 2):
        doc.DrawPages.insertNewByIndex(doc.DrawPages.Count)
    return doc, doc.DrawPages.Count


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice", required=True)
    parser.add_argument("--out", default=tempfile.mkdtemp(prefix="hst-bsprint-"))  # noqa
    parser.add_argument("--shot", help="screenshot command with {} for the file, e.g. 'import -window root {}'")
    parser.add_argument("--no-pdf-printer", action="store_true", help="no printer of the profile, no printing")
    parser.add_argument("--more-options-at", default="405,732", help="its button on a 1600x900 screen (gen)")
    args = parser.parse_args()
    out = os.path.abspath(args.out)  # noqa
    os.makedirs(pdf_dir := os.path.join(out, "pdf"), exist_ok=True)
    shot = lambda name: args.shot and subprocess.run(args.shot.format(os.path.join(out, name)), shell=True)  # noqa
    # keys on the private X display only (no window manager: the window under the pointer has the keyboard)
    key = lambda k: subprocess.run(["xdotool", "mousemove", "650", "450", "sleep", "0.5", "key", k], check=True)  # noqa
    pdfs = lambda: set(glob.glob(os.path.join(pdf_dir, "*.pdf")))  # noqa: E731
    office = VisibleOffice(args.soffice, out, None if args.no_pdf_printer else pdf_dir)
    try:
        docs = []
        for app in ("swriter", "scalc", "simpress", "sdraw"):
            doc, pages = make_doc(office, app)
            docs.append(doc)
            office.close_welcome()
            office.ui.executeCommandForProvider(".uno:Print", doc.getCurrentController().getFrame())
            time.sleep(5)  # the job comes back through the hand-over; the preview is painted on idle
            check(not office.wait_dialog("PrintDialog", 1), f"{app}: .uno:Print shows the Print page, not the print dialog")
            shot(f"{app}-print-page.png")
            if args.no_pdf_printer:
                office.ui.executeCommandForProvider(".uno:HSTBackstage", doc.getCurrentController().getFrame())
                continue
            before = pdfs()
            key("Return")  # the page focuses its In button
            printed = wait_pdf(pdf_dir, before)
            check(printed and pdf_summary(printed)[0][0].split()[-1] == str(pages),
                  f"{app}: the In button of the page prints {pages} page(s) to the PDF printer")
            printed and os.replace(printed, os.path.join(out, f"{app}-page.pdf"))
        if not args.no_pdf_printer:
            docs.append(make_doc(office, "swriter")[0])  # the same text in the shown tab
            writer, before = docs[-1].getCurrentController().getFrame(), pdfs()
            office.ui.executeCommandForProvider(".uno:Print", writer)
            time.sleep(4)
            office.ui.executeCommandForProvider(".uno:HSTBackstage", writer)  # closed: the job is cancelled
            time.sleep(2)
            check(not pdfs() - before, "writer: closing the panel cancels the job (nothing printed)")
            office.ui.executeCommandForProvider(".uno:Print", writer)
            time.sleep(4)
            x, y = args.more_options_at.split(",")  # "Thêm tùy chọn": the classic dialog for the same job
            subprocess.run(["xdotool", "mousemove", x, y, "click", "1"], check=True)
            dialog = office.wait_dialog("PrintDialog")
            check(dialog is not None, "writer: More Options opens the classic print dialog")
            shot("writer-classic-dialog.png")
            dialog and dialog.getChild("ok").executeAction("CLICK", ())
            dialog_pdf = wait_pdf(pdf_dir, before)
            panel_pdf = os.path.join(out, "swriter-page.pdf")
            check(dialog_pdf and os.path.exists(panel_pdf) and pdf_summary(panel_pdf) == pdf_summary(dialog_pdf),
                  "writer: the page and the classic dialog print the same pages and text")
        for doc in docs:
            doc.setModified(False)  # the office quits without asking
    finally:
        office.stop()
    print(f"{len(failures)} failure(s); output in {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
