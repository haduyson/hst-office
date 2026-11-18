# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức commands (Chèn ▸ nhóm Công thức, and the question on double-clicking a MathType equation):
  - ConvertFormulas ("Chuyển công thức"): every MathType equation of the document, one undo step;
  - AskConvertFormula: the selected MathType equation, after asking (the office asks this command when such an
    equation is double-clicked, since it cannot be edited here; hst-math-convert-on-double-click.patch).
The work is done by formula_convert; this module only talks to the user."""
from . import formula_convert
from .dialogs import message_box


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


def ask_convert_selected(host):
    found = _selected_equation(host)
    if found is None:
        return convert_all(host)
    container, obj = found
    s = host.s["formula"]
    if not message_box(host.ctx, host.peer, s["title"], s["askOne"], ask=True, buttons=(s["convert"], s["notNow"])):
        return
    from .undo import undo_step
    with undo_step(host.doc, host.s["undo"]["formula"]):
        result = formula_convert.convert_one(host.ctx, host.doc, container, obj)
    if not result:
        message_box(host.ctx, host.peer, s["title"], s["kept"] % 1 if result is False else s["none"])


TEMPLATES_PATH = "/org.hasontech.hstoffice.Formula"


def insert_templates(host):
    """Mẫu công thức: a new formula, opened for editing with the Elements panel on the Mẫu Toán category (formula.xcs
    tells the panel; its category list also has Mẫu Vật lí and Mẫu Hoá học) and the template bar of the editor."""
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
