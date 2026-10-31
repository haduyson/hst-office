# SPDX-License-Identifier: AGPL-3.0-only
"""Small helper to build native modal UNO dialogs in code (no XDL files, no web views).

Controls are added in tab order; OK/Cancel use the standard push-button types so Enter/Esc work, every control
gets a HelpText for screen readers. All positions are in Map AppFont units.
"""
import uno
import unohelper
from com.sun.star.awt import XActionListener, XItemListener, XTextListener

OK, CANCEL = 1, 2


class _Action(unohelper.Base, XActionListener):
    def __init__(self, callback):
        self.callback = callback

    def actionPerformed(self, event):
        self.callback()

    def disposing(self, event):
        pass


class _Changed(unohelper.Base, XTextListener, XItemListener):
    """Calls `callback` whenever an edit's text or a list box's selection changes (live preview)."""

    def __init__(self, callback):
        self.callback = callback

    def textChanged(self, event):
        self.callback()

    def itemStateChanged(self, event):
        self.callback()

    def disposing(self, event):
        pass


class Dialog:
    def __init__(self, ctx, title, width, height):
        self.ctx, self.smgr = ctx, ctx.ServiceManager
        self.model = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.Title, self.model.Width, self.model.Height = title, width, height
        self.dialog = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
        self.dialog.setModel(self.model)
        self._listeners = []
        self._watchers = []  # (control name, _Changed)
        self.result = 0
        self.on_oversize = None  # called with no arguments when the peer is larger than the screen work area

    def _add(self, kind, name, x, y, w, h, **props):
        model = self.model.createInstance("com.sun.star.awt.UnoControl%sModel" % kind)
        for key, value in dict(PositionX=x, PositionY=y, Width=w, Height=h, **props).items():
            uno.invoke(model, "setPropertyValue", (key, value))  # invoke() accepts uno.Any values
        self.model.insertByName(name, model)
        return model

    def label(self, name, text, x, y, w, h=10, wrap=False):
        return self._add("FixedText", name, x, y, w, h, Label=text, MultiLine=wrap)

    def edit(self, name, x, y, w, h=12, text="", multiline=False, readonly=False, help_text=""):
        return self._add("Edit", name, x, y, w, h, Text=text, MultiLine=multiline, VScroll=multiline, HScroll=False,
                         ReadOnly=readonly, HelpText=help_text or name, Tabstop=not readonly or multiline)

    def listbox(self, name, x, y, w, items, selected=0, h=12, help_text=""):
        return self._add("ListBox", name, x, y, w, h, Dropdown=True, StringItemList=uno.Any("[]string", tuple(items)),
                         SelectedItems=uno.Any("[]short", (selected,)),
                         LineCount=min(10, len(items)), HelpText=help_text or name)

    def check(self, name, text, x, y, w, state=True, h=10):
        return self._add("CheckBox", name, x, y, w, h, Label=text, State=1 if state else 0, HelpText=text)

    def button(self, name, text, x, y, w, kind=None, callback=None, default=False, h=14):
        model = self._add("Button", name, x, y, w, h, Label=text, HelpText=text, DefaultButton=default,
                          **({"PushButtonType": kind} if kind else {}))
        if callback:
            self._listeners.append((name, _Action(callback)))
        return model

    def on_change(self, names, callback):
        """Run `callback` after any text/selection change of the named edits and list boxes (added at execute)."""
        listener = _Changed(callback)
        self._watchers += [(name, listener) for name in names]

    def get(self, name):
        model = self.model.getByName(name)
        if hasattr(model, "SelectedItems") and model.supportsService("com.sun.star.awt.UnoControlListBoxModel"):
            items = model.SelectedItems
            return items[0] if items else -1
        if model.supportsService("com.sun.star.awt.UnoControlCheckBoxModel"):
            return bool(model.State)
        return model.Text

    def select(self, name, index):
        uno.invoke(self.model.getByName(name), "setPropertyValue", ("SelectedItems", uno.Any("[]short", (index,))))

    def set_text(self, name, text):
        self.model.getByName(name).Text = text

    def end(self, code=1):
        self.dialog.endExecute()
        self.result = code

    def _exceeds_screen(self, toolkit):
        """True when the created dialog (pixels) does not fit the work area, e.g. Windows display scaling on a small screen."""
        try:
            size, area = self.dialog.getPeer().getPosSize(), toolkit.getWorkArea()
            return size.Width > area.Width or size.Height > area.Height
        except Exception:  # noqa: BLE001 - unknown geometry: keep the full layout
            return False

    def execute(self, parent_peer=None):
        """Show modally; returns 1 only if end(1) was called (OK), else 0. Always disposes the dialog."""
        toolkit = self.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        self.dialog.setVisible(False)
        self.dialog.createPeer(toolkit, parent_peer)
        if self.on_oversize and self._exceeds_screen(toolkit):
            self.on_oversize()
        for name, listener in self._listeners:
            self.dialog.getControl(name).addActionListener(listener)
        for name, listener in self._watchers:
            control = self.dialog.getControl(name)
            if self.model.getByName(name).supportsService("com.sun.star.awt.UnoControlListBoxModel"):
                control.addItemListener(listener)
            else:
                control.addTextListener(listener)
        try:
            self.dialog.execute()
            return self.result
        finally:
            self.dialog.dispose()


def message_box(ctx, parent_peer, title, text, error=False, ask=False):
    """Native message box; returns True for Yes/OK. `ask` shows Yes/No."""
    from com.sun.star.awt.MessageBoxType import ERRORBOX, INFOBOX, QUERYBOX
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    buttons = 3 if ask else 1  # MessageBoxButtons: BUTTONS_OK=1, BUTTONS_YES_NO=3
    box = toolkit.createMessageBox(parent_peer, QUERYBOX if ask else (ERRORBOX if error else INFOBOX), buttons, title, text)
    try:
        return box.execute() in (1, 2)  # RET_OK=1, RET_YES=2
    finally:
        box.dispose()
