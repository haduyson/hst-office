# SPDX-License-Identifier: AGPL-3.0-only
"""The Quick Search list of the ND30 wizard's "Loại văn bản", shown as a popup over the form.

It is not a control of the dialog: VCL does not clip sibling controls against each other, they are assumed not to
overlap. A list control lying over the fields below the type was painted over by them whenever they repainted on their
own: Windows' themed edits redraw on mouse hover and painted white boxes through the list, a covered field whose text
changed did the same, and the multi-line fields drew their scroll bars over it. A FloatingWindow created without frame
styles is an overlap window inside the dialog's own frame (vcl floatwin.cxx ImplInitFloating): VCL clips the windows
under it, it gets the mouse before them, it moves with the dialog, and showing it never takes the focus from the field.
"""
import uno

ROWS_UNITS = 150  # height of the list in Map AppFont units: about 18 rows


class TypePopup:
    """A list box in a floating window, laid under the field `anchor` and as wide as `anchor` to `right` together."""

    def __init__(self, dialog, help_text):
        self.d, self.help_text = dialog, help_text
        self.window = self.control = self.model = None

    def create(self, anchor, right):
        """Build the popup (hidden); the dialog peer must exist."""
        from com.sun.star.awt import Rectangle, Size, WindowDescriptor
        from com.sun.star.awt.PosSize import POSSIZE
        from com.sun.star.awt.WindowClass import SIMPLE
        from com.sun.star.util.MeasureUnit import APPFONT
        d = self.d
        toolkit = d.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", d.ctx)
        dialog_peer = d.dialog.getPeer()
        field = d.dialog.getControl(anchor).getPeer().getPosSize()
        end = d.dialog.getControl(right).getPeer().getPosSize()
        width = end.X + end.Width - field.X
        height = dialog_peer.convertSizeToPixel(Size(0, ROWS_UNITS), APPFONT).Height
        descriptor = WindowDescriptor()
        descriptor.Type, descriptor.WindowServiceName, descriptor.ParentIndex = SIMPLE, "floatingwindow", -1
        descriptor.Parent, descriptor.WindowAttributes = dialog_peer, 0  # no frame styles: an overlap window
        descriptor.Bounds = Rectangle(field.X, field.Y + field.Height + 1, width, height)
        self.window = toolkit.createWindow(descriptor)
        self.window.setVisible(False)
        self.model = d.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlListBoxModel", d.ctx)
        for key, value in (("Dropdown", False), ("Tabstop", False), ("HelpText", self.help_text), ("Border", 1)):
            uno.invoke(self.model, "setPropertyValue", (key, value))
        self.control = d.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlListBox", d.ctx)
        self.control.setModel(self.model)
        self.control.createPeer(toolkit, self.window)
        self.control.setPosSize(0, 0, width, height, POSSIZE)
        self.control.setVisible(True)

    def box(self):
        """(x, y, width, height) of the popup in pixels relative to the dialog, or None before create()."""
        if self.window is None:
            return None
        box = self.window.getPosSize()
        return box.X, box.Y, box.Width, box.Height

    def show(self, visible):
        if self.window is not None:
            self.window.setVisible(visible)

    def dispose(self):
        for part in (self.control, self.window):
            if part is not None:
                try:
                    part.dispose()
                except Exception:  # noqa: BLE001 - already gone with the dialog
                    pass
        self.window = self.control = self.model = None
