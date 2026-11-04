# SPDX-License-Identifier: AGPL-3.0-only
"""Checks of the smaller Writer dialogs that follow Word. Used by check-dialogs-writer.py."""
from dialogs_writer_paragraph_font_cases import first_paragraph
from hst_dialog_uitest import click, props, select_tab, state, tab_titles, type_value, visible

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
    width = int(state(dlg).get("Size", "9999x0").lower().split("x")[0])
    c.equal("page setup: the dialog fits a 1366 px wide screen", width <= 1366, True)
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


def check_special_character(h, c):
    doc = h.new_document()
    dlg = h.open_dialog(".uno:InsertSymbol", "SpecialCharactersDialog")
    c.equal("special character: Word's two tabs", state(dlg.getChild("hstsymboltabs")).get("PageCount"), "2")
    dlg.getChild("hstsymboltabs").executeAction("SELECT", props(POS="1"))
    dlg.getChild("hstspeciallist").getChild("0").executeAction("SELECT", ())
    h.wait_idle(0.5)
    c.equal("special character: Em Dash shown", state(dlg.getChild("decimalvalue")).get("Text"), str(0x2014))
    click(dlg, "insert")  # with a document open "insert" is the action button and closes the dialog
    h.wait_idle()
    c.equal("special character: Em Dash inserted", doc.getText().getString(), "\u2014")
    h.close_document(doc)


def check_page_number(h, c):
    doc = h.new_document()
    dlg = h.open_dialog(".uno:PageNumberWizard", "PageNumberDialog")
    click(dlg, "checkHST_STARTAT")
    type_value(dlg, "spinHST_STARTAT", "5")
    click(dlg, "ok")
    h.wait_idle()
    c.equal("page number: Start at 5", first_paragraph(doc).PageNumberOffset, 5)
    h.close_document(doc)


def check_slide_properties(h, c):
    doc = h.new_document("simpress")
    dlg = h.open_dialog(".uno:PageSetup", "DrawPageDialog")
    c.equal("slide properties: no margins", visible(dlg, "spinMargLeft"), False)
    c.equal("slide properties: orientation kept", visible(dlg, "radiobuttonPortrait"), True)
    click(dlg, "cancel")
    h.close_document(doc)
