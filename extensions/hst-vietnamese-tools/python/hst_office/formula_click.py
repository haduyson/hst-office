# SPDX-License-Identifier: AGPL-3.0-only
"""HST Công thức: double-clicking a MathType equation asks to convert it (AskConvertFormula) instead of trying to
start MathType, which the office cannot do without it. Where MathType is installed (formula_mathtype_server), the
double-click goes on as usual and MathType opens the equation, as in HST Office 1.0.2. Every other double-click goes
on as usual too.

A mouse click handler on each document view (XUserInputInterception, attached by formula_open_job at
OnViewCreated). It looks at the second press of a left double-click only: the first press has selected the object.
The question is shown after the event has been consumed (com.sun.star.awt.AsyncCallback), never inside it."""
import unohelper
from com.sun.star.awt import XCallback, XMouseClickHandler

from . import diag_log

LEFT = 1  # com.sun.star.awt.MouseButton.LEFT
COMMAND = "org.hst.office.vi:AskConvertFormula"


def selected_embedded(controller):
    """The selected object's XEmbeddedObject (Writer object or single OLE shape), else None."""
    selection = controller.getSelection()
    if selection is None:
        return None
    if selection.supportsService("com.sun.star.text.TextEmbeddedObject"):
        return selection.EmbeddedObject
    if hasattr(selection, "getCount") and selection.getCount() == 1:
        shape = selection.getByIndex(0)
        if shape.getShapeType() == "com.sun.star.drawing.OLE2Shape":
            return shape.EmbeddedObject
    return None


def selected_class_id(controller):
    """The OLE class id of the selected embedded object ("0002CE03-0000-0000-C000-000000000046"), "" if none.
    Read from the object's CLSID property: the object is neither stored nor unloaded."""
    selection = controller.getSelection()
    if selection is None:
        return ""
    if not selection.supportsService("com.sun.star.text.TextEmbeddedObject"):
        if not (hasattr(selection, "getCount") and selection.getCount() == 1):
            return ""
        selection = selection.getByIndex(0)
        if selection.getShapeType() != "com.sun.star.drawing.OLE2Shape":
            return ""
    return (selection.CLSID or "").upper()


def opens_in_mathtype(controller, installed=None):
    """True when the selected object is a MathType or Equation 3.x equation and MathType, its program, is installed:
    the office's own double-click opens it there."""
    from . import formula_ole
    class_id = selected_class_id(controller)
    if class_id not in (formula_ole.EQUATION3, formula_ole.MATHTYPE):
        return False
    if installed is None:
        from .formula_mathtype_server import server_installed as installed
    return installed(class_id)


def is_mathtype_selected(ctx, controller):
    from . import formula_convert, formula_ole
    embedded = selected_embedded(controller)
    return embedded is not None and formula_ole.is_mathtype(formula_convert.ole_data(ctx, embedded))


class _AskLater(unohelper.Base, XCallback):
    def __init__(self, ctx, frame):
        self.ctx, self.frame = ctx, frame

    def notify(self, data):
        try:
            import uno
            url = uno.createUnoStruct("com.sun.star.util.URL")
            url.Complete = COMMAND
            dispatcher = self.frame.queryDispatch(url, "", 0)
            if dispatcher is not None:
                dispatcher.dispatch(url, ())
        except Exception:  # noqa: BLE001
            diag_log.exception("formula_click")


class FormulaClickHandler(unohelper.Base, XMouseClickHandler):
    def __init__(self, ctx, controller):
        self.ctx, self.controller = ctx, controller

    def mousePressed(self, event):
        if event.ClickCount != 2 or event.Buttons != LEFT:
            return False
        try:
            if opens_in_mathtype(self.controller):
                return False  # MathType edits it, as a double-click always did before HST Công thức
            if not is_mathtype_selected(self.ctx, self.controller):
                return False
            callback = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.AsyncCallback", self.ctx)
            callback.addCallback(_AskLater(self.ctx, self.controller.getFrame()), None)
            return True
        except Exception:  # noqa: BLE001 - a double-click must keep working whatever happens here
            diag_log.exception("formula_click")
            return False

    def mouseReleased(self, event):
        return False

    def disposing(self, source):
        self.controller = None


def attach(ctx, controller):
    """Watch double-clicks on this view; views without user input interception are left alone."""
    if controller is not None and hasattr(controller, "addMouseClickHandler"):
        controller.addMouseClickHandler(FormulaClickHandler(ctx, controller))
