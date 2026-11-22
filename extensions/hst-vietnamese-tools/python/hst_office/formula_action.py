# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức commands (Chèn ▸ nhóm Công thức, and the question on double-clicking a MathType equation):
  - ConvertFormulas ("Chuyển công thức"): every MathType equation of the document, one undo step;
  - AskConvertFormula: the selected MathType equation, after asking (formula_click runs it when such an equation is
    double-clicked): "Chuyển thành công thức HST" / "Để nguyên", plus "Mở bằng MathType" on Windows when MathType is
    installed (formula_mathtype_server; owner decision 18/11/2026).
The work is done by formula_convert; this module only talks to the user."""
from . import formula_convert
from .dialogs import message_box
from .formula_mathtype_server import CONVERT, LEAVE, OPEN, choices


def _selected_equation(host):
    """(container or None, object) of the selected embedded object, or None."""
    selection = host.controller.getSelection()
    if selection is None:
        return None
    if selection.supportsService("com.sun.star.text.TextEmbeddedObject"):
        return None, selection
    if not hasattr(selection, "getCount"):
        return None
    for container, shape in formula_convert.shape_objects(host.doc):
        for i in range(selection.getCount()):
            if selection.getByIndex(i) == shape:
                return container, shape
    return None


def _report(host, done, kept):
    s = host.s["formula"]
    text = s["done"] % done if done else s["none"]
    if kept:
        text += "\n" + s["kept"] % kept
    message_box(host.ctx, host.peer, s["title"], text)


def convert_all(host):
    done, kept = formula_convert.convert_all(host.ctx, host.doc, host.s["undo"]["formula"])
    _report(host, done, kept)


def _choose(host, text, answers):
    """The answer picked; closing the question means LEAVE. The last button has the focus and is the default."""
    from .dialogs import Dialog
    s = host.s["formula"]
    labels = {CONVERT: s["convert"], OPEN: s["openMathType"], LEAVE: s["notNow"]}
    width = 140 + 124 * len(answers)
    lines = sum(max(1, -(-len(part) // int(width / 5))) for part in text.split("\n"))
    dialog = Dialog(host.ctx, s["title"], width, lines * 9 + 40)
    dialog.label("text", text, 8, 8, width - 16, lines * 9 + 2, wrap=True)
    x, y = width - 8 - 120, lines * 9 + 18
    for index in reversed(range(len(answers))):
        dialog.button("b%d" % index, labels[answers[index]], x, y, 120, default=index == len(answers) - 1,
                      callback=lambda code=index + 1: dialog.end(code))
        x -= 124
    code = dialog.execute(host.peer)
    return answers[code - 1] if 1 <= code <= len(answers) else LEAVE


def open_selected(host):
    """The selected object's primary verb through the view, as a double-click runs it: the view's in-place client
    takes MathType's changes back into the document and its picture."""
    from com.sun.star.beans import PropertyValue
    verb = PropertyValue()
    verb.Name, verb.Value = "VerbID", 0  # com.sun.star.embed.EmbedVerbs.MS_OLEVERB_PRIMARY
    helper = host.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", host.ctx)
    helper.executeDispatch(host.frame, ".uno:ObjectMenue", "", 0, (verb,))


def ask_convert_selected(host):
    found = _selected_equation(host)
    if found is None:
        return convert_all(host)
    container, obj = found
    s = host.s["formula"]
    from . import formula_ole
    data = formula_convert.ole_data(host.ctx, obj.EmbeddedObject)
    if not formula_ole.is_mathtype(data):
        return message_box(host.ctx, host.peer, s["title"], s["none"])
    answers = choices(formula_ole.root_class_id(data))
    answer = _choose(host, s["askOneMathType"] if OPEN in answers else s["askOne"], answers)
    if answer == OPEN:  # as before HST Công thức: the equation's own program opens it
        return open_selected(host)
    if answer != CONVERT:
        return
    from .undo import undo_step
    with undo_step(host.doc, host.s["undo"]["formula"]):
        result = formula_convert.convert_one(host.ctx, host.doc, container, obj)
    if not result:
        message_box(host.ctx, host.peer, s["title"], s["kept"] % 1)


TEMPLATES_PATH = "/org.hasontech.hstoffice.Formula"


def insert_templates(host):
    """Mẫu công thức: a new formula, opened for editing with the Elements panel on the Mẫu Toán category (Formula.xcs
    in officecfg tells the panel; its category list also has Mẫu Vật lí and Mẫu Hoá học) and the template bar of the
    editor."""
    from com.sun.star.beans import PropertyValue
    provider = host.ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.configuration.ConfigurationProvider", host.ctx)
    path = PropertyValue()
    path.Name, path.Value = "nodepath", TEMPLATES_PATH
    access = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationUpdateAccess", (path,))
    access.setPropertyValue("OpenTemplates", True)
    access.commitChanges()
    helper = host.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", host.ctx)
    helper.executeDispatch(host.frame, ".uno:InsertObjectStarMath", "", 0, ())
    helper.executeDispatch(host.frame, ".uno:SidebarDeck.ElementsDeck", "", 0, ())
