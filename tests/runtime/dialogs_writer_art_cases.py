# SPDX-License-Identifier: AGPL-3.0-only
"""Word's page border art: every one of its 164 names survives DOCX, and HST paints a set for it. Used by check-dialogs-writer.py."""
import os
import re
import shutil
import subprocess
import zipfile

from hst_dialog_uitest import click, props, select_entry, select_tab

NAMES = ("apples", "zigZagStitch", "basicBlackDots", "celticKnotwork")


def word_names(h):
    """Word's art names, from the OOXML schema of the source tree that holds this instdir."""
    tree = os.path.dirname(os.path.dirname(h.office.program))
    model = open(os.path.join(tree, "sw/source/writerfilter/ooxml/model.xml"), encoding="utf-8").read()
    names = re.findall(r"<value>(\w+)</value>", re.search(r'<define name="ST_Border">(.*?)</define>', model, re.S).group(1))
    return names[names.index("apples"):]


def pdf_page_png(path, work, stem):
    """First page of a PDF or PostScript file as a PNG, by Ghostscript."""
    target = os.path.join(work, stem + ".png")
    subprocess.run(["gs", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=png16m", "-r72", "-dFirstPage=1", "-dLastPage=1", f"-sOutputFile={target}", path], check=True)
    return target


def red_pixels(png):
    """Pixels in the art's apple red, counted by ImageMagick."""
    done = subprocess.run(["convert", png, "-fill", "black", "+opaque", "#C62828", "-fill", "white", "-opaque", "#C62828", "-format", "%[fx:int(mean*w*h)]", "info:"], capture_output=True, text=True, check=True)
    return int(done.stdout)


def with_art(source, target, name, display="allPages"):
    """A copy of a DOCX with art on the sides of its page borders, as Word writes them: one name for all, or four."""
    names = [name] * 4 if isinstance(name, str) else name
    borders = (f'<w:pgBorders w:display="{display}" w:offsetFrom="page">'
               + "".join(f'<w:{side} w:val="{art}" w:sz="20" w:space="24" w:color="auto"/>' for side, art in zip(("top", "left", "bottom", "right"), names))
               + "</w:pgBorders>")
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                text = re.sub(r"<w:pgBorders.*?</w:pgBorders>", "", data.decode("utf-8"), flags=re.S)
                text = re.sub(r"(<w:pgMar [^>]*/>)", lambda m: m.group(1) + borders, text, count=1)
                data = text.encode("utf-8")
            dst.writestr(item, data)


def page_png(h, doc, path):
    doc.storeToURL("file://" + path, props(FilterName="writer_png_Export"))


def edge_colours(path):
    """Distinct colours along the top edge area of the exported page."""
    out = subprocess.run(["convert", path, "-resize", "400x", "-crop", "400x40+0+0", "-format", "%k", "info:"], capture_output=True, text=True)
    return int(out.stdout.strip() or 0)


def check_page_art(h, c):
    work = h.office.workdir
    doc = h.new_document()
    doc.getText().setString("Trang có viền nghệ thuật")
    base = os.path.join(work, "art-base.docx")
    doc.storeToURL("file://" + base, props(FilterName="MS Word 2007 XML"))
    h.close_document(doc)
    for name in NAMES:
        source = os.path.join(work, f"art-{name}.docx")
        with_art(base, source, name)
        doc = h.office.load("file://" + source)
        h.wait_idle(1)
        saved = os.path.join(work, f"art-{name}-saved.docx")
        doc.storeToURL("file://" + saved, props(FilterName="MS Word 2007 XML"))
        with zipfile.ZipFile(saved) as package:
            xml = package.read("word/document.xml").decode("utf-8")
        c.equal(f"art: {name} survives opening and saving DOCX", f'w:top w:val="{name}" w:sz="20"' in xml, True)
        png = os.path.join(work, f"art-{name}.png")
        page_png(h, doc, png)
        c.equal(f"art: {name} is painted on the page", edge_colours(png) > 1, True)
        h.close_document(doc)

    # What people send on: PDF export, and printing to a file.
    source = os.path.join(work, "art-out.docx")
    with_art(base, source, "apples")
    doc = h.office.load("file://" + source)
    h.wait_idle(0.5)
    pdf = os.path.join(work, "art-apples.pdf")
    doc.storeToURL("file://" + pdf, props(FilterName="writer_pdf_Export"))
    c.equal("art: painted in PDF export", red_pixels(pdf_page_png(pdf, work, "art-pdf")) > 500, True)
    printed = os.path.join(work, "art-printed.pdf")
    doc.print(props(FileName="file://" + printed, Wait=True))
    h.wait_idle(1)
    c.equal("art: printing writes a file", os.path.exists(printed) and os.path.getsize(printed) > 0, True)
    c.equal("art: painted in the printed file", red_pixels(pdf_page_png(printed, work, "art-printed")) > 500, True)
    h.close_document(doc)

    # Every one of Word's names comes back as it was, four to a document.
    names = word_names(h)
    c.equal("art: Word has 164 names", len(names), 164)
    lost = []
    for start in range(0, len(names), 4):
        group = (names[start:start + 4] + names[:4])[:4]
        source = os.path.join(work, "art-group.docx")
        with_art(base, source, group)
        doc = h.office.load("file://" + source)
        saved = os.path.join(work, "art-group-saved.docx")
        doc.storeToURL("file://" + saved, props(FilterName="MS Word 2007 XML"))
        with zipfile.ZipFile(saved) as package:
            xml = package.read("word/document.xml").decode("utf-8")
        lost += [name for name in group if f'w:val="{name}"' not in xml]
        h.close_document(doc)
    c.equal("art: all 164 names survive DOCX", lost, [])

    doc = h.new_document()
    doc.getText().setString("Chọn nghệ thuật trong hộp thoại")
    dlg = h.open_dialog(".uno:BorderDialog", "HstBordersDialog")
    select_tab(dlg, 1)
    select_entry(dlg, "hstpageart", 11)  # the eleventh set: apples
    click(dlg, "ok")
    h.wait_idle()
    saved = os.path.join(work, "art-chosen.docx")
    doc.storeToURL("file://" + saved, props(FilterName="MS Word 2007 XML"))
    with zipfile.ZipFile(saved) as package:
        xml = package.read("word/document.xml").decode("utf-8")
    c.equal("art: the dialog's choice reaches DOCX", 'w:val="apples"' in xml, True)
    shutil.copy(saved, os.path.join(work, "art-chosen-kept.docx"))
    h.close_document(doc)
