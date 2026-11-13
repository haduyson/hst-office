# SPDX-License-Identifier: AGPL-3.0-only
"""In-process checks of the six citation commands (runs inside the office through the script provider; see
check-citations-commands.py). The real command code runs; only the dialogs and message boxes are replaced by
recorders, so no window is needed. Returns JSON: [{"check", "status", "detail"}]."""
import json
import sys
import types

A = {"id": "a", "type": "book", "title": "Giáo trình kinh tế", "language": "vi", "publisher": "Giáo dục",
     "publisher-place": "Hà Nội", "author": [{"family": "Nguyễn", "given": "Văn An", "hst-vi": True}],
     "issued": {"date-parts": [[2010]]}}
B = {"id": "b", "type": "article-journal", "title": "A study", "language": "en", "container-title": "Nature",
     "volume": "5", "page": "1-9", "author": [{"family": "Smith", "given": "John"}], "issued": {"date-parts": [[2020]]}}


def run_checks(doc, ext_python, ris_path):
    if ext_python not in sys.path:
        sys.path.insert(0, ext_python)
    import uno
    from hst_office import citation_actions as actions, citation_cite_actions as cite, citation_document as document
    from hst_office import citation_insert_dialog, citation_save_job, citation_settings, citation_style_dialog
    from hst_office import citation_transfer_actions as transfer, citation_ui as ui
    ctx = uno.getComponentContext()
    results, said = [], []

    def check(name, ok, detail=None):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    ui.inform = lambda _ctx, _peer, _texts, text: said.append(text)
    ui.choose = lambda *args, **kwargs: args[5] if len(args) > 5 else 0
    controller = doc.getCurrentController()
    host = types.SimpleNamespace(ctx=ctx, frame=controller.getFrame(), controller=controller, doc=doc, peer=None,
                                 is_writer=lambda: True)
    texts = actions.texts_of(host)
    view, text = controller.getViewCursor(), doc.getText()

    def cited():
        return [f["result"] for f in sorted(document.scan(doc), key=lambda f: f["rank"]) if f["kind"] == "citation"]

    def paragraph(content):
        text.insertString(text.getEnd(), content, False)
        text.insertControlCharacter(text.getEnd(), 0, False)

    citation_settings.write(doc, {"style": "ieee", "preset": None, "opts": {}})
    locale = uno.createUnoStruct("com.sun.star.lang.Locale")
    locale.Language, locale.Country = "vi", "VN"  # a Vietnamese document: international styles print "tr."
    doc.getStyleFamilies().getByName("ParagraphStyles").getByName("Standard").CharLocale = locale
    for content in ("Đoạn một ¤.", "Đoạn hai ¤.", "Đoạn ba ¤."):
        paragraph(content)
    search = doc.createSearchDescriptor()
    search.SearchString = "¤"
    for item in (A, B, A):
        found = doc.findFirst(search)
        view.gotoRange(found, False)
        view.setString("")
        cite.insert_cluster(host, texts, {"citationID": "", "items": [{"id": item["id"]}]}, {item["id"]: item}, "insert")
    check("insert-three-ieee-numbers", cited() == ["[1]", "[2]", "[1]"], cited())
    from hst_office import citation_reinsert_dialog
    listed = []
    citation_reinsert_dialog.run = lambda *a: listed.append(a[3]) and None
    view.gotoRange(document.scan(doc)[0]["mark"].getAnchor().getEnd(), False)  # right after "[1]": not typed text
    cite.reinsert(host)
    check("reinsert-ignores-citation-before-cursor", cited() == ["[1]", "[2]", "[1]"] and len(listed) == 1, cited())
    view.gotoRange(text.getEnd(), False)
    actions.bibliography(host)
    bib = [f for f in document.scan(doc) if f["kind"] == "bibliography"]
    styles = [p.ParaStyleName for p in document_paragraphs(bib[0]["mark"])] if bib else []
    check("bibliography-inserted-and-styled", len(bib) == 1 and styles == ["Bibliography Title"] + ["Bibliography"] * 2
          and not bib[0]["result"].endswith("\n"),
          {"styles": styles, "paras": [p.getString() for p in document_paragraphs(bib[0]["mark"])] if bib else [],
           "text": bib[0]["result"] if bib else "", "after": text.getString()[-80:]})

    typed = text.createTextCursorByRange(text.getStart())
    typed.gotoEndOfParagraph(False)
    text.insertControlCharacter(typed, 0, False)
    text.insertString(typed, "Như đã nêu [2, tr. 7", False)
    view.gotoRange(typed.getEnd(), False)
    cite.reinsert(host)
    check("reinsert-typed-number", cited()[:2] == ["[1]", "[2, tr. 7]"] and "[2, tr. 7" not in text.getString().replace(
        "[2, tr. 7]", ""), cited())
    doc.getUndoManager().undo()
    check("reinsert-one-undo-step", "Như đã nêu [2, tr. 7" in text.getString() and len(cited()) == 3, cited())
    doc.getUndoManager().redo()

    view.gotoRange(document.scan(doc)[0]["mark"].getAnchor().getStart(), False)
    view.goRight(1, False)
    citation_insert_dialog.run = lambda *a: ({"citationID": "", "items": [{"id": "a", "locator": "99", "label": "page"}],
                                              "mode": "normal"}, {"a": A})
    actions.COMMANDS["CitationInsert"](host)
    check("edit-citation-under-cursor", "[1, tr. 99]" in cited(), cited())

    first = sorted(document.scan(doc), key=lambda f: f["rank"])[0]
    view.gotoRange(first["mark"].getAnchor().getStart(), False)
    view.gotoRange(first["mark"].getAnchor().getEnd(), True)
    document.dispatch(ctx, doc, "Delete")
    said.clear()
    actions.COMMANDS["CitationUpdate"](host)
    check("update-renumbers-after-delete", cited() == ["[1, tr. 7]", "[1]", "[2]"] and said[:1] == ["Đã cập nhật 3 trích dẫn."], {"cited": cited(), "said": said})

    for style_id, footnotes in (("chicago-chu-thich", 3), ("apa-7", 0)):
        citation_style_dialog.run = lambda *a, s=style_id: {"style": s, "preset": None, "opts": {}}
        actions.COMMANDS["CitationStyle"](host)
        count = doc.getFootnotes().getCount()
        check("style-%s-footnotes" % style_id, count == footnotes and len(cited()) == 3, {"footnotes": count, "cited": cited()})

    view.gotoRange(text.getEnd(), False)
    document.insert_field(ctx, doc, document.scan(doc)[0]["code"].replace('"citationID":"', '"citationID":"x'), "[?]")
    check("save-job-updates-stale", citation_save_job.update_before_save(ctx, doc) is True, cited())
    from hst_office import citation_refresh
    _f, again = citation_refresh.compute(ctx, doc, None, texts["bibliography"]["empty"])
    check("save-job-quiet-when-current", citation_save_job.update_before_save(ctx, doc) is False,
          {"changed": again["citations_changed"], "bib_changed": again["bib_changed"],
           "bib": [f["result"] for f in _f if f["kind"] == "bibliography"], "plan": again["bibliography"][0][1][:300]})

    path = ctx.ServiceManager.createInstanceWithContext(  # a file URL in the test profile
        "com.sun.star.util.PathSubstitution", ctx).substituteVariables("$(user)", True) + "/commands.docx"
    store = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    store.Name, store.Value = "FilterName", "MS Word 2007 XML"
    doc.storeToURL(path, (store,))
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    hidden.Name, hidden.Value = "Hidden", True
    reopened = desktop.loadComponentFromURL(path, "_blank", 0, (hidden,))
    try:
        kept = citation_settings.read(reopened)
        count = len([f for f in document.scan(reopened) if f["kind"] == "citation"])
        check("docx-keeps-settings-and-citations", kept and kept["style"] == "apa-7" and count == 4, {"settings": kept, "count": count})
    finally:
        reopened.close(True)

    library = ui.open_library(ctx, None, texts)
    before = len(library)
    ui.pick_file = lambda *a, **k: ris_path
    transfer._preview = lambda _c, _p, _t, _path, result: list(result.suggestions)
    added = transfer.import_into(ctx, None, texts, library)
    check("import-ris-into-library", added > 0 and len(ui.open_library(ctx, None, texts)) == before + added,
          {"added": added, "said": said[-1:]})
    return json.dumps(results, ensure_ascii=False)


def document_paragraphs(mark):
    anchor = mark.getAnchor()
    enum = anchor.getText().createTextCursorByRange(anchor).createEnumeration()
    out = []
    while enum.hasMoreElements():
        para = enum.nextElement()
        if para.supportsService("com.sun.star.text.Paragraph"):
            out.append(para)
    return out


g_exportedScripts = (run_checks,)
