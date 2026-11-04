#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Writer dialogs follow Word's structure: tab order, key controls, and edits that reach the document.

Usage: check-dialogs-writer.py [--instdir DIR] [--work DIR] [dialog ...]   (default: every dialog)
Needs a built instdir with the vi language pack. Runs headless (svp) with a fresh profile.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hst_dialog_uitest import (Checks, DialogHarness, click, select_entry, select_tab, state, tab_titles,  # noqa: E402
                               type_value, visible)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CENTER, LEFT = 3, 0  # com.sun.star.style.ParagraphAdjust


def first_paragraph(doc):
    return doc.getText().createEnumeration().nextElement()


def check_paragraph(h, c):
    doc = h.new_document()
    doc.getText().setString("Đoạn văn kiểm tra hộp thoại.")
    h.wait_idle()

    dlg = h.open_dialog(".uno:ParagraphDialog", "ParagraphPropertiesDialog")
    titles = tab_titles(dlg)
    c.equal("paragraph: first two tabs like Word", titles[:2], ["Thụt lề và Giãn cách", "Ngắt Dòng và Trang"])
    c.equal("paragraph: Tabs is third", titles[2], "Tab")
    c.equal("paragraph: advanced alignment kept", "Căn chỉnh nâng cao" in titles, True)
    for kept in ("Viền", "Vùng"):
        c.equal(f"paragraph: {kept} page kept", any(kept in t for t in titles), True)
    c.equal("paragraph: Special list shown", visible(dlg, "comboLB_HST_SPECIAL"), True)
    c.equal("paragraph: old first-line field hidden", visible(dlg, "spinED_FLINEINDENT"), False)

    select_entry(dlg, "comboLB_HST_SPECIAL", 1)
    type_value(dlg, "spinED_HST_SPECIALBY", "1")
    select_entry(dlg, "comboLB_HST_ALIGN", 1)
    click(dlg, "ok")
    h.wait_idle()
    para = first_paragraph(doc)
    c.equal("paragraph: Special First line 1 cm", para.ParaFirstLineIndent, 1000)
    c.equal("paragraph: alignment list Centered", int(para.ParaAdjust), CENTER)

    dlg = h.open_dialog(".uno:ParagraphDialog", "ParagraphPropertiesDialog")
    c.equal("paragraph: reopened shows First line", state(dlg.getChild("comboLB_HST_SPECIAL")).get("SelectEntryPos"), "1")
    select_entry(dlg, "comboLB_HST_SPECIAL", 2)
    type_value(dlg, "spinED_HST_SPECIALBY", "0,5")  # vi decimal comma
    click(dlg, "ok")
    h.wait_idle()
    c.equal("paragraph: Special Hanging 0.5 cm (twip rounding)", abs(first_paragraph(doc).ParaFirstLineIndent + 500) <= 2, True)

    # A change on the advanced page must reach the list, and the list must not undo it.
    dlg = h.open_dialog(".uno:ParagraphDialog", "ParagraphPropertiesDialog")
    titles = tab_titles(dlg)
    select_tab(dlg, titles.index("Căn chỉnh nâng cao"))
    click(dlg, "radioBTN_LEFTALIGN")
    select_tab(dlg, 0)
    c.equal("paragraph: list follows the advanced page", state(dlg.getChild("comboLB_HST_ALIGN")).get("SelectEntryPos"), "0")
    click(dlg, "ok")
    h.wait_idle()
    c.equal("paragraph: advanced page alignment applied", int(first_paragraph(doc).ParaAdjust), LEFT)

    select_entry_none = h.open_dialog(".uno:ParagraphDialog", "ParagraphPropertiesDialog")
    select_entry(select_entry_none, "comboLB_HST_SPECIAL", 0)
    click(select_entry_none, "ok")
    h.wait_idle()
    c.equal("paragraph: Special (none) clears the indent", first_paragraph(doc).ParaFirstLineIndent, 0)
    h.close_document(doc)


def check_font(h, c):
    doc = h.new_document()
    doc.getText().setString("Chữ kiểm tra hộp thoại.")
    cursor = doc.getCurrentController().getViewCursor()
    cursor.gotoStart(False)
    cursor.gotoEnd(True)
    h.wait_idle()

    dlg = h.open_dialog(".uno:FontDialog", "CharacterPropertiesDialog")
    titles = tab_titles(dlg)
    c.equal("font: Word's two tabs first", titles[:2], ["Phông chữ", "Nâng cao"])
    c.equal("font: no separate effects tab", "Hiệu ứng phông" in " ".join(titles), False)
    for kept in ("Viền",):
        c.equal(f"font: {kept} page kept", any(kept in t for t in titles), True)
    c.equal("font: font name on the Font tab", visible(dlg, "edWestFontName"), True)
    c.equal("font: colour on the Font tab", visible(dlg, "fontcolorlb"), True)
    c.equal("font: underline on the Font tab", visible(dlg, "underlinelb"), True)
    c.equal("font: superscript on the Font tab", visible(dlg, "checkHST_SUPERSCRIPT"), True)

    click(dlg, "checkHST_SUPERSCRIPT")
    select_entry(dlg, "underlinelb", 1)
    click(dlg, "ok")
    h.wait_idle()
    run = doc.getText().createEnumeration().nextElement().createEnumeration().nextElement()
    c.equal("font: superscript applied", run.CharEscapement > 0, True)
    c.equal("font: underline applied", run.CharUnderline != 0, True)

    # Superscript and Advanced stay one setting.
    dlg = h.open_dialog(".uno:FontDialog", "CharacterPropertiesDialog")
    select_tab(dlg, 1)
    c.equal("font: Advanced shows the superscript", state(dlg.getChild("superscript")).get("Checked"), "true")
    click(dlg, "normal")
    select_tab(dlg, 0)
    c.equal("font: Font tab follows Advanced", state(dlg.getChild("checkHST_SUPERSCRIPT")).get("Selected"), "false")
    click(dlg, "ok")
    h.wait_idle()
    run = doc.getText().createEnumeration().nextElement().createEnumeration().nextElement()
    c.equal("font: back to normal position", run.CharEscapement, 0)
    h.close_document(doc)


def check_word_count(h, c):
    doc = h.new_document()
    text = doc.getText()
    text.setString("Một hai ba")
    text.insertControlCharacter(text.getEnd(), 0, False)  # PARAGRAPH_BREAK
    text.insertString(text.getEnd(), "Bốn năm", False)
    h.wait_idle(2)
    dlg = h.open_dialog(".uno:WordCountDialog", "hstdocpages", modeless=True)
    h.wait_idle(1)
    c.equal("word count: pages", state(dlg.getChild("hstdocpages")).get("Text"), "1")
    c.equal("word count: paragraphs", state(dlg.getChild("hstdocparas")).get("Text"), "2")
    c.equal("word count: words", state(dlg.getChild("docwords")).get("Text"), "5")
    c.equal("word count: paragraphs in an empty selection", state(dlg.getChild("hstselectparas")).get("Text"), "0")
    click(dlg, "close")
    h.close_document(doc)


def check_hyperlink(h, c):
    doc = h.new_document()
    dlg = h.open_dialog(".uno:HyperlinkDialog", "tabcontrol", modeless=True)
    c.equal("hyperlink: Word's Link to order", [t.replace("~", "") for t in tab_titles(dlg)],
            ["Tệp hoặc Trang Web Hiện có", "Vị trí trong Tài liệu Này", "Tạo Tài liệu Mới", "Địa chỉ Email"])
    c.equal("hyperlink: Cancel is translated", state(dlg.getChild("cancel")).get("Text").replace("~", ""), "Hủy")
    click(dlg, "cancel")
    h.close_document(doc)


def check_page_setup(h, c):
    doc = h.new_document()
    dlg = h.open_dialog(".uno:PageDialog", "TemplateDialog8")
    titles = tab_titles(dlg)
    c.equal("page setup: page comes first", titles[0], "Trang")
    c.equal("page setup: style organizer last", titles[-1], "Chung")
    c.equal("page setup: nested Word tabs", state(dlg.getChild("hstPageTabs")).get("PageCount"), "3")
    type_value(dlg, "spinMargLeft", "3")
    click(dlg, "ok")
    h.wait_idle()
    style = doc.StyleFamilies.getByName("PageStyles").getByName(doc.getText().createEnumeration().nextElement().PageStyleName or "Standard")
    c.equal("page setup: left margin applied", abs(style.LeftMargin - 3000) <= 2, True)

    dlg = h.open_dialog(".uno:PageDialog", "TemplateDialog8")
    select_tab(dlg, titles.index("Đầu trang"))
    click(dlg, "checkHeaderOn")
    click(dlg, "checkHST_DIFFLR-header")
    click(dlg, "ok")
    h.wait_idle()
    c.equal("header: Different odd and even pages applied", style.HeaderIsShared, False)
    h.close_document(doc)


DIALOGS = {"paragraph": check_paragraph, "font": check_font, "word-count": check_word_count, "hyperlink": check_hyperlink,
           "page-setup": check_page_setup}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--work", default=os.path.join(ROOT, "tests/output/dialogs-writer"))
    parser.add_argument("dialogs", nargs="*", default=[])
    args = parser.parse_args()
    harness = DialogHarness(args.instdir, args.work, 22979, ":79")
    checks = Checks()
    try:
        for name in args.dialogs or DIALOGS:
            DIALOGS[name](harness, checks)
    finally:
        harness.close()
    return checks.finish()


if __name__ == "__main__":
    sys.exit(main())
