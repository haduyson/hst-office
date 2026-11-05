# SPDX-License-Identifier: AGPL-3.0-only
"""Find and Replace has Word's tabs: Find, Replace and, in Writer, Go To. Searching stays as it was, and the dialog
stays non-modal; Sheets and Slides share it. Used by check-dialogs-writer.py."""
from hst_dialog_uitest import click, props, select_entry, select_tab, state, type_value, visible, writer_edit

TAB_FIND, TAB_REPLACE, TAB_GOTO = 0, 1, 2
PAGE, SECTION, LINE, BOOKMARK, COMMENT, FOOTNOTE, ENDNOTE, FIELD, TABLE, GRAPHIC, EQUATION, OBJECT, HEADING = range(13)


def open_find(h):
    return h.open_dialog(".uno:SearchDialog", "searchterm", modeless=True)


def sample(h):
    """Three pages: a heading on each of the last two, a bookmark on page 3, a table and a footnote on page 2."""
    from com.sun.star.style.BreakType import PAGE_BEFORE
    doc = h.new_document()
    text = doc.getText()
    text.setString("Đoạn đầu cần tìm\nDòng hai\nDòng ba")
    for title in ("Mục một", "Mục hai"):
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        text.insertControlCharacter(cursor, 0, False)
        cursor.gotoEnd(False)
        cursor.setPropertyValue("ParaStyleName", "Heading 1")
        cursor.setPropertyValue("BreakType", PAGE_BEFORE)
        text.insertString(cursor, title, False)
        if title == "Mục một":
            note = doc.createInstance("com.sun.star.text.Footnote")
            text.insertTextContent(cursor, note, False)
            table = doc.createInstance("com.sun.star.text.TextTable")
            table.initialize(2, 2)
            text.insertTextContent(text.getEnd(), table, False)
    mark = doc.createInstance("com.sun.star.text.Bookmark")
    mark.setName("Dau")
    cursor = text.createTextCursor()
    cursor.gotoEnd(False)
    text.insertTextContent(cursor, mark, False)
    doc.getCurrentController().getViewCursor().gotoStart(False)
    h.wait_idle()
    return doc


def page_count(dlg):
    """A horizontal tab strip reports no titles to UITest, only how many pages."""
    return int(state(dlg.getChild("hsttabs"))["PageCount"])


def page_of(doc):
    return doc.getCurrentController().getViewCursor().getPage()


def go(dlg, what, value):
    select_entry(dlg, "hstgotowhat", what)
    type_value(dlg, "hstgotovalue", value)
    click(dlg, "hstgotogo")


def check_find_tabs(h, c):
    doc = sample(h)
    dlg = open_find(h)
    c.equal("find: opens on Replace, as the dialog always showed", visible(dlg, "replaceterm"), True)
    c.equal("find: Word's three tabs (titles checked on the screenshot)", page_count(dlg), 3)

    select_tab(dlg, TAB_FIND, "hsttabs")
    c.equal("find: Find hides the replace field", visible(dlg, "replaceterm"), False)
    c.equal("find: Find hides Replace All", visible(dlg, "replaceall"), False)
    for widget in ("searchterm", "search", "backsearch", "searchall", "matchcase", "OptionsExpander"):
        c.equal(f"find: Find keeps {widget}", visible(dlg, widget), True)
    # Every option is still there, under the expander.
    dlg.getChild("OptionsExpander").executeAction("EXPAND", ())
    h.wait_idle(0.5)
    for widget in ("selection", "regexp", "layout", "notes", "attributes", "format", "noformat", "similarity"):
        c.equal(f"find: Nâng cao keeps {widget}", visible(dlg, widget), True)

    type_value(dlg, "searchterm", "cần tìm")
    click(dlg, "search")
    h.wait_idle()
    found = doc.getCurrentController().getSelection().getByIndex(0).getString()
    c.equal("find: Find Next finds it", found, "cần tìm")
    c.equal("find: the dialog stays open beside the document", visible(dlg, "searchterm"), True)

    select_tab(dlg, TAB_REPLACE, "hsttabs")
    c.equal("find: Replace shows the field again", visible(dlg, "replaceterm"), True)
    type_value(dlg, "replaceterm", "đã thay")
    click(dlg, "replaceall")
    h.wait_idle()
    c.equal("find: Replace All reaches the document", "Đoạn đầu đã thay" in doc.getText().getString(), True)

    select_tab(dlg, TAB_GOTO, "hsttabs")
    c.equal("go to: hides the search field", visible(dlg, "searchterm"), False)
    c.equal("go to: shows its list", visible(dlg, "hstgotowhat"), True)
    c.equal("go to: Word's thirteen places", int(state(dlg.getChild("hstgotowhat"))["EntryCount"]), 13)
    go(dlg, PAGE, "2")
    c.equal("go to: page 2", page_of(doc), 2)
    click(dlg, "hstgotonext")
    c.equal("go to: Next page", page_of(doc), 3)
    click(dlg, "hstgotoprev")
    c.equal("go to: Previous page", page_of(doc), 2)
    go(dlg, PAGE, "+1")
    c.equal("go to: +1", page_of(doc), 3)
    go(dlg, PAGE, "99")
    c.equal("go to: past the end is the last page", page_of(doc), 3)
    go(dlg, BOOKMARK, "Dau")
    c.equal("go to: bookmark", page_of(doc), 3)
    go(dlg, BOOKMARK, "Khong co")
    c.equal("go to: an unknown bookmark says so", state(dlg.getChild("hstgotomessage")).get("Text"), "Không tìm thấy.")
    go(dlg, PAGE, "1")
    select_entry(dlg, "hstgotowhat", TABLE)
    click(dlg, "hstgotonext")
    h.wait_idle(0.5)
    cursor = doc.getCurrentController().getViewCursor()
    c.equal("go to: Next table", cursor.TextTable is not None, True)
    go(dlg, HEADING, "2")
    h.wait_idle(0.5)
    c.equal("go to: heading 2", doc.getCurrentController().getViewCursor().getPage(), 3)
    go(dlg, FOOTNOTE, "1")
    c.equal("go to: footnote 1", page_of(doc), 2)
    go(dlg, TABLE, "5")
    c.equal("go to: no such table says so", state(dlg.getChild("hstgotomessage")).get("Text"), "Không tìm thấy.")
    go(dlg, LINE, "2")
    c.equal("go to: line 2 of the document", doc.getCurrentController().getViewCursor().getPage(), 1)

    # Non-modal: typing goes to the document with the dialog open.
    select_tab(dlg, TAB_REPLACE, "hsttabs")
    doc.getCurrentController().getViewCursor().gotoStart(False)
    click(dlg, "close")
    h.wait_idle()
    writer_edit(h.ui).executeAction("TYPE", props(TEXT="z"))
    h.wait_idle()
    c.equal("find: the document takes typing after", doc.getText().getString().startswith("z"), True)
    h.close_document(doc)


def check_find_other_apps(h, c):
    """Sheets and Slides keep their own terms and options, with Find and Replace tabs but no Go To."""
    doc = h.new_document("scalc")
    sheet = doc.getSheets().getByIndex(0)
    sheet.getCellByPosition(0, 3).setString("cần tìm")
    dlg = open_find(h)
    c.equal("find sheets: Find and Replace tabs, no Go To", page_count(dlg), 2)
    select_tab(dlg, TAB_REPLACE, "hsttabs")
    c.equal("find sheets: all sheets option kept", visible(dlg, "allsheets"), True)
    c.equal("find sheets: expander keeps its term", state(dlg.getChild("OptionsExpander")).get("Text", "").replace("_", "").replace("~", "") != "Nâng cao", True)
    type_value(dlg, "searchterm", "cần tìm")
    type_value(dlg, "replaceterm", "đã thay")
    click(dlg, "replaceall")
    h.wait_idle()
    c.equal("find sheets: Replace All reaches the cell", sheet.getCellByPosition(0, 3).getString(), "đã thay")
    h.close_document(doc)

    doc = h.new_document("simpress")
    shape = doc.getDrawPages().getByIndex(0).getByIndex(0)
    shape.setString("cần tìm")
    dlg = open_find(h)
    c.equal("find slides: Find and Replace tabs, no Go To", page_count(dlg), 2)
    select_tab(dlg, TAB_REPLACE, "hsttabs")
    type_value(dlg, "searchterm", "cần tìm")
    type_value(dlg, "replaceterm", "đã thay")
    click(dlg, "replaceall")
    h.wait_idle()
    c.equal("find slides: Replace All reaches the shape", shape.getString(), "đã thay")
    h.close_document(doc)
