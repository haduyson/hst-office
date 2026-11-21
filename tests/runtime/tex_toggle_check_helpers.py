# SPDX-License-Identifier: AGPL-3.0-only
"""Helpers of the Chuyển TeX ⇄ công thức runtime checks (check-tex-toggle.py, check-tex-toggle-key.py): the test
document, reading it back, running on the office's main thread and quitting there."""
import json
import os
import re
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "python"))
import headless_office  # noqa: E402
from hst_office import tex_to_starmath  # noqa: E402

COMMAND = "org.hst.office.vi:TexToggle"
MATH = "078B7ABA-54FC-457F-8551-6147E776A997"
CENTER = 3
HIGHLIGHT = 0xFFFF00
ROWS = []


def record(name, ok, detail=""):
    ROWS.append((name, ok))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, str(detail)[:400]), flush=True)


def on_main(office, function):
    """Run function on the office's main thread (URP keeps the nested calls there) and return its result."""
    import unohelper
    from com.sun.star.awt import XCallback
    done, box = threading.Event(), {}

    class Run(unohelper.Base, XCallback):
        def notify(self, data):
            try:
                box["value"] = function()
            except Exception as error:  # noqa: BLE001 - reported by the caller
                box["error"] = error
            finally:
                done.set()
    office.service("com.sun.star.awt.AsyncCallback").addCallback(Run(), None)
    if not done.wait(600):
        raise SystemExit("main-thread call timed out")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def corpus():
    with open(os.path.join(ROOT, "tests", "fixtures", "tex-toggle", "exam-snippets.json"), encoding="utf-8") as stream:
        return json.load(stream)


def build(doc, data):
    """Write the test text; returns {span: (expected formula, font size, display)} and the failing spans."""
    text = doc.getText()
    cursor = text.createTextCursor()
    expected = {}

    def paragraph(content, size=12.0):
        cursor.setPropertyValue("CharHeight", size)
        text.insertString(cursor, content, False)
        text.insertControlCharacter(cursor, 0, False)

    for number, item in enumerate(data["snippets"], 1):
        size = 14.0 if number % 5 == 0 else 12.0
        if number % 11 == 0:  # display math alone in its paragraph (limits above and below: display=True)
            span = "$$%s$$" % item["tex"]
            paragraph(span, size)
            expected[span] = (tex_to_starmath.convert(item["tex"], True), size, True)
        elif number % 13 == 0:  # display math inside a sentence: it gets its own paragraph
            span = "\\[%s\\]" % item["tex"]
            paragraph("Câu %d. Ta có %s nên suy ra kết quả." % (number, span), size)
            expected[span] = (tex_to_starmath.convert(item["tex"], True), size, True)
        else:
            span = "$%s$" % item["tex"]
            paragraph("Câu %d. Tính %s với điều kiện đã cho." % (number, span), size)
            expected[span] = (item["starmath"], size, False)
    failing = ["$%s$" % item["tex"] for item in data["failures"]]
    paragraph("Các biểu thức sai: " + ", ".join(failing) + ".")
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(1, 2)
    text.insertTextContent(cursor, table, False)
    cell_item = data["snippets"][0]
    table.getCellByName("A1").setString("Trong bảng: $%s$" % cell_item["tex"])
    return expected, failing, "$%s$" % cell_item["tex"]


def formulas(doc):
    objects = doc.getEmbeddedObjects()
    found = [objects.getByName(name) for name in objects.getElementNames()]
    return [o for o in found if (o.CLSID or "").upper() == MATH]


def body_text(doc):
    """Body text and the text of each table cell."""
    parts = [doc.getText().getString()]
    tables = doc.getTextTables()
    for index in range(tables.getCount()):
        table = tables.getByIndex(index)
        parts.extend(table.getCellByName(name).getString() for name in table.getCellNames())
    return "\n".join(parts)


def text_sizes(doc):
    """{paragraph label ("Câu 7."): set of the font sizes of its text portions} of the body."""
    sizes = {}
    paragraphs = doc.getText().createEnumeration()
    while paragraphs.hasMoreElements():
        paragraph = paragraphs.nextElement()
        if not paragraph.supportsService("com.sun.star.text.Paragraph"):
            continue
        label = re.match(r"(Câu \d+\.)", paragraph.getString())
        portions = paragraph.createEnumeration()
        while label and portions.hasMoreElements():
            portion = portions.nextElement()
            if portion.TextPortionType == "Text" and portion.getString().strip():
                sizes.setdefault(label.group(1), set()).add(portion.getPropertyValue("CharHeight"))
    return sizes


def dispatch(office, doc):
    office.dispatch(doc, COMMAND)


def png(office, doc, path):
    """Page 1 as PNG, and the whole document as PDF next to it (for side-by-side pictures of any page)."""
    doc.getCurrentController().getViewCursor().jumpToFirstPage()
    doc.storeToURL(office.url(path), headless_office.props(FilterName="writer_png_Export"))
    doc.storeToURL(office.url(path[:-4] + ".pdf"), headless_office.props(FilterName="writer_pdf_Export"))


def quit_office(office):
    """.uno:Quit on the main thread, then wait for the process (never terminate() over the bridge)."""
    import unohelper
    from com.sun.star.awt import XCallback

    class Quit(unohelper.Base, XCallback):
        def notify(self, data):
            office.service("com.sun.star.frame.DispatchHelper").executeDispatch(office.desktop, ".uno:Quit", "", 0,
                                                                               ())
    try:
        office.service("com.sun.star.awt.AsyncCallback").addCallback(Quit(), None)
    except Exception:  # noqa: BLE001 - the bridge goes away while the office quits
        pass
    try:
        office.proc.wait(timeout=60)
    except Exception:  # noqa: BLE001 - subprocess.TimeoutExpired: it did not quit
        office.proc.kill()


