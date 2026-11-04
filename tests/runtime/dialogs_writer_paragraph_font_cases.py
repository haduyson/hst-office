# SPDX-License-Identifier: AGPL-3.0-only
"""Checks of the Writer dialogs that follow Word: Paragraph, Font. Used by check-dialogs-writer.py."""
from hst_dialog_uitest import click, select_entry, select_tab, state, tab_titles, type_value, visible

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
