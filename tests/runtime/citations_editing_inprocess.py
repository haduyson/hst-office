# SPDX-License-Identifier: AGPL-3.0-only
"""In-process checks of citations while the user edits around them (run by check-citations-commands.py next to
citations_commands_inprocess.py): moving a paragraph and updating renumbers; with change tracking on, the update
records no change; a read-only document is refused and left alone. Returns JSON results."""
import json
import sys
import types

A = {"id": "a", "type": "book", "title": "Giáo trình", "language": "vi",
     "author": [{"family": "Nguyễn", "given": "Văn An", "hst-vi": True}], "issued": {"date-parts": [[2010]]}}
B = {"id": "b", "type": "book", "title": "Economics", "language": "en",
     "author": [{"family": "Smith", "given": "John"}], "issued": {"date-parts": [[2020]]}}


def redlines(doc):
    enum, count = doc.getRedlines().createEnumeration(), 0
    while enum.hasMoreElements():
        enum.nextElement()
        count += 1
    return count


def run_checks(doc, ext_python):
    if ext_python not in sys.path:
        sys.path.insert(0, ext_python)
    import uno
    from hst_office import citation_actions as actions, citation_cite_actions as cite, citation_document as document
    from hst_office import citation_settings, citation_ui as ui
    ctx = uno.getComponentContext()
    results, said = [], []

    def check(name, ok, detail=None):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    ui.inform = lambda _c, _p, _t, text: said.append(text)
    controller = doc.getCurrentController()
    host = types.SimpleNamespace(ctx=ctx, frame=controller.getFrame(), controller=controller, doc=doc, peer=None,
                                 is_writer=lambda: True)
    texts = actions.texts_of(host)
    text, view = doc.getText(), controller.getViewCursor()

    def cited():
        return [f["result"] for f in sorted(document.scan(doc), key=lambda f: f["rank"]) if f["kind"] == "citation"]

    citation_settings.write(doc, {"style": "ieee", "preset": None, "opts": {}})
    text.setString("")
    for label, item in (("Một", A), ("Hai", B)):
        text.insertString(text.getEnd(), "Đoạn %s " % label, False)
        view.gotoRange(text.getEnd(), False)
        cite.insert_cluster(host, texts, {"citationID": "", "items": [{"id": item["id"]}]}, {item["id"]: item}, "insert")
        text.insertControlCharacter(text.getEnd(), 0, False)
    check("two-paragraphs-numbered", cited() == ["[1]", "[2]"], cited())

    second = text.createEnumeration()
    second.nextElement()
    paragraph = second.nextElement()
    view.gotoRange(paragraph.getStart(), False)
    view.gotoRange(paragraph.getEnd(), True)
    view.goRight(1, True)  # with its paragraph break
    document.dispatch(ctx, doc, "Cut")
    view.gotoRange(text.getStart(), False)
    document.dispatch(ctx, doc, "Paste")
    check("moved-paragraph-keeps-old-numbers-until-update", cited() == ["[2]", "[1]"], cited())

    doc.RecordChanges = True
    before = redlines(doc)
    actions.COMMANDS["CitationUpdate"](host)
    check("update-renumbers-moved-paragraph", cited() == ["[1]", "[2]"], cited())
    check("update-records-no-tracked-change", redlines(doc) == before and doc.RecordChanges,
          {"before": before, "after": redlines(doc)})
    doc.RecordChanges = False

    readonly = types.SimpleNamespace(**vars(host))  # the same document, reported read-only
    readonly.doc = types.SimpleNamespace(isReadonly=lambda: True, supportsService=doc.supportsService)
    said.clear()
    actions.COMMANDS["CitationUpdate"](readonly)
    check("read-only-is-refused", said == [texts["blockers"]["readOnly"]] and cited() == ["[1]", "[2]"], said)
    return json.dumps(results, ensure_ascii=False)


g_exportedScripts = (run_checks,)
