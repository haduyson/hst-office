# SPDX-License-Identifier: AGPL-3.0-only
"""The document-type dropdown of the ND30 wizard with Quick Search: a field to type in and a list that filters live.

The list opens when the user types, presses Down or clicks the arrow. Up/Down or the pointer move the highlight in it, a
click, Enter or Tab chooses (Tab then moves on), Esc closes it and brings the chosen type back. While it is open a key
handler keeps those keys from the dialog, whose default button and Cancel would otherwise take them. Group headings are
shown but can't be chosen.
"""
import unohelper
from com.sun.star.awt import XFocusListener, XItemListener, XKeyHandler, XMouseMotionListener, XTextListener
from com.sun.star.awt.Key import DOWN, ESCAPE, RETURN, TAB, UP

from . import nd30_search
from .wizard_type_popup import TypePopup


class _Keys(unohelper.Base, XKeyHandler):
    def __init__(self, picker):
        self.picker = picker

    def keyPressed(self, event):
        return self.picker.key(event.KeyCode)

    def keyReleased(self, event):
        return False

    def disposing(self, event):
        pass


class _Events(unohelper.Base, XTextListener, XItemListener, XFocusListener, XMouseMotionListener):
    def __init__(self, picker):
        self.picker = picker

    def textChanged(self, event):
        self.picker.typed()

    def itemStateChanged(self, event):
        self.picker.clicked()

    def focusGained(self, event):
        self.picker.select_all()

    def focusLost(self, event):
        pass

    def mouseMoved(self, event):
        self.picker.hovered(self.picker.popup.row_at(event.X, event.Y))

    def mouseDragged(self, event):
        pass

    def disposing(self, event):
        pass


class TypePicker:
    def __init__(self, dialog, types, group_names, on_choose, help_text=""):
        self.d, self.types, self.groups, self.on_choose = dialog, types, group_names, on_choose
        self.popup = TypePopup(dialog, help_text)
        self.current = types[0]["id"]
        self.table, self.index, self.open, self.silent = [], -1, False, False
        self.toolkit, self.handler = None, None

    def label_of(self, type_id):
        return next(t["label"] for t in self.types if t["id"] == type_id)

    def attach(self):
        """Hook the live controls (the peer exists now)."""
        events = _Events(self)
        self.field = self.d.dialog.getControl("type")
        self.popup.create("type", "typeOpen")  # under the field, which may have grown (dialog_edit_heights)
        self.list = self.popup.control
        self.field.addTextListener(events)
        self.field.addFocusListener(events)
        self.list.addItemListener(events)
        self.list.addMouseMotionListener(events)
        self.toolkit = self.d.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.d.ctx)
        self.handler = _Keys(self)
        self.toolkit.addKeyHandler(self.handler)

    def detach(self):
        if self.handler:
            self.toolkit.removeKeyHandler(self.handler)
            self.handler = None
        self.open = False
        self.popup.dispose()

    def _show_field(self, text):
        self.silent = True
        self.d.set_text("type", text)
        self.silent = False

    def select_all(self):
        import uno
        text = self.d.model.getByName("type").Text
        self.field.setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 0, len(text)))

    def _fill(self, query):
        self.table = nd30_search.rows(self.types, query, self.groups)
        import uno
        uno.invoke(self.popup.model, "setPropertyValue", ("StringItemList", uno.Any("[]string", tuple(row[0] for row in self.table))))
        self._select(nd30_search.next_row(self.table, -1, 1) if self.table else -1)

    def _select(self, index, scroll=True):
        import uno
        self.index = index
        chosen = (index,) if index >= 0 else ()
        self.silent = True
        uno.invoke(self.popup.model, "setPropertyValue", ("SelectedItems", uno.Any("[]short", chosen)))
        self.silent = False
        if index >= 0 and scroll:  # never under the pointer: a half-shown last row would scroll away from it
            self.list.makeVisible(index)

    def _set_open(self, value):
        self.open = value
        self.popup.show(value)

    def typed(self):
        if self.silent:
            return
        self._fill(self.d.model.getByName("type").Text)
        self._set_open(True)

    def toggle(self):
        if self.open:
            self.close()
        else:
            self._fill("")
            self._set_open(True)
        self.field.setFocus()

    def hovered(self, position):
        """The pointer is over row `position` of the open list: highlight it like a dropdown does (a group heading or no
        row keeps the highlight where it is). Enter or Tab then takes that row, as after Up/Down."""
        if self.open and position != self.index and 0 <= position < len(self.table) and self.table[position][1]:
            top = self.popup.top_row()
            self._select(position, scroll=False)
            # VCL scrolls a selected row it counts as not fully shown (imp_listbox.cxx SelectEntry ->
            # ShowProminentEntry), here already rows in the lower half: the list ran away under the pointer
            if top >= 0 and self.popup.top_row() != top:
                self.list.makeVisible(top)  # XListBox.makeVisible sets the top row

    def clicked(self):
        if self.silent or not self.open:
            return
        position = self.list.getSelectedItemPos()
        if 0 <= position < len(self.table) and self.table[position][1]:
            self.choose(self.table[position][1])

    def choose(self, type_id):
        self.current = type_id
        self._set_open(False)
        self._show_field(self.label_of(type_id))
        self.on_choose()

    def close(self):
        self._set_open(False)
        self._show_field(self.label_of(self.current))

    def key(self, code):
        """True when the key was ours. The field or the list must hold the focus: other controls keep their keys."""
        if not self.handler or (not self.open and code != DOWN):
            return False
        if not self._has_focus():
            if self.open:
                self.close()
            return False
        if code == DOWN and not self.open:
            self._fill("")
            self._set_open(True)
        elif code in (DOWN, UP):
            self._select(nd30_search.next_row(self.table, self.index, 1 if code == DOWN else -1))
        elif code == RETURN:
            if self.index >= 0:
                self.choose(self.table[self.index][1])
        elif code == ESCAPE:
            self.close()
        elif code == TAB:
            # Leaving the field with Tab (or Shift+Tab) takes the highlighted type, like a combo box, and closes the list;
            # the dialog still moves the focus. An open list left behind covered the next seven fields: the focus went
            # to a field under it, typing seemed to go nowhere and the next key reverted the type.
            if self.index >= 0:
                self.choose(self.table[self.index][1])
            else:
                self.close()
            return False
        else:
            return False
        return True

    def _has_focus(self):
        try:
            return self.field.getPeer().hasFocus() or self.list.getPeer().hasFocus()
        except Exception:  # noqa: BLE001 - no focus information: leave the key alone
            return False
