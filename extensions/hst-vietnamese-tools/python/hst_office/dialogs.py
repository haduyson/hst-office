# SPDX-License-Identifier: AGPL-3.0-only
"""Small helper to build native modal UNO dialogs in code (no XDL files, no web views).

Controls are added in tab order; OK/Cancel use the standard push-button types so Enter/Esc work, every control
gets a HelpText for screen readers. All positions are in Map AppFont units.
"""
import uno
import unohelper
from com.sun.star.awt import XActionListener, XItemListener, XTextListener

OK, CANCEL = 1, 2
# Accent text colours that stay readable (contrast >= 4.5:1) on the light and on the dark dialog background.
PALETTES = {False: {"link": 0x0B57D0, "muted": 0x5F6368, "error": 0xC5221F},
            True: {"link": 0x8AB4F8, "muted": 0xBDC1C6, "error": 0xF28B82}}


def is_dark(ctx):
    """True when the office draws dialogs dark (dark GTK theme, macOS/Windows dark appearance or Tools ▸ Options ▸
    Appearance): judged from the dialog colour of the active window, the same colour our dialogs get."""
    try:
        smgr = ctx.ServiceManager
        window = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx).getActiveTopWindow()
        if window is None:
            frame = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
            window = frame.getContainerWindow() if frame else None
        colour = window.StyleSettings.DialogColor  # XStyleSettingsSupplier; the attribute form also works over a bridge
        red, green, blue = (colour >> 16) & 0xFF, (colour >> 8) & 0xFF, colour & 0xFF
        return 0.299 * red + 0.587 * green + 0.114 * blue < 128
    except Exception:  # noqa: BLE001 - no window yet or no style settings: keep the light palette
        return False


def palette(ctx):
    return PALETTES[is_dark(ctx)]


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
        self._single_lines, self._overlays = [], set()  # single-line edits (see _fit_edits); lists shown over others
        self.result = 0
        self.on_oversize = None  # called with no arguments when the peer is larger than the screen work area
        self.on_ready, self.on_closed = None, None  # called right after the peer exists / after the dialog has ended

    def _add(self, kind, name, x, y, w, h, **props):
        model = self.model.createInstance("com.sun.star.awt.UnoControl%sModel" % kind)
        for key, value in dict(PositionX=x, PositionY=y, Width=w, Height=h, **props).items():
            uno.invoke(model, "setPropertyValue", (key, value))  # invoke() accepts uno.Any values
        self.model.insertByName(name, model)
        return model

    def label(self, name, text, x, y, w, h=10, wrap=False):
        return self._add("FixedText", name, x, y, w, h, Label=text, MultiLine=wrap)

    def edit(self, name, x, y, w, h=12, text="", multiline=False, readonly=False, help_text=""):
        if not multiline:
            self._single_lines.append(name)
        return self._add("Edit", name, x, y, w, h, Text=text, MultiLine=multiline, VScroll=multiline, HScroll=False,
                         ReadOnly=readonly, HelpText=help_text or name, Tabstop=not readonly or multiline)

    def plain_list(self, name, x, y, w, h, help_text=""):
        """A list box that shows its rows (the Quick Search list); it never takes part in Tab order. It is shown over the
        controls under it, so it never limits their room (_room_below)."""
        self._overlays.add(name)
        return self._add("ListBox", name, x, y, w, h, Dropdown=False, Tabstop=False, HelpText=help_text or name)

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
        """Run `callback` after any text/selection/state change of the named edits, list and check boxes (added at execute)."""
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

    def _room_below(self, name):
        """Map AppFont units from the top of `name` to the top of the nearest control below it that it overlaps
        horizontally (the dialog bottom when there is none). Overlay lists don't count: they are drawn over the fields."""
        model = self.model.getByName(name)
        room = self.model.Height - model.PositionY
        for other in self.model.ElementNames:
            below = self.model.getByName(other)
            if (other != name and other not in self._overlays and below.PositionY > model.PositionY
                    and below.PositionX < model.PositionX + model.Width and model.PositionX < below.PositionX + below.Width):
                room = min(room, below.PositionY - model.PositionY)
        return room

    def _fit_edits(self):
        """Make every single-line edit at least as high as the platform draws it, within the room below it.

        A fixed AppFont height is not enough everywhere: macOS draws a native edit box with a fixed 29 px frame whose
        text area starts 6 px below the top (vcl/osx salnativewidgets), so a 12-unit edit (about 22 px) pinned the text
        to the top border and cut the descenders of g/y; the gen backend (20 px) cut the hook of Ủ. The peer's preferred
        height (Edit::CalcMinimumSize) is the text height plus borders, or the native frame when that is higher.
        Edits that are already high enough keep their layout height."""
        from com.sun.star.awt import Size
        from com.sun.star.util.MeasureUnit import APPFONT
        peer = self.dialog.getPeer()
        for name in self._single_lines:
            model = self.model.getByName(name)
            try:
                pixels = self.dialog.getControl(name).getPreferredSize().Height
                need = peer.convertSizeToLogic(Size(0, pixels), APPFONT).Height
                while peer.convertSizeToPixel(Size(0, need), APPFONT).Height < pixels:
                    need += 1
            except Exception:  # noqa: BLE001 - no size information: keep the layout height
                continue
            if need > model.Height:
                model.Height = max(model.Height, min(need, self._room_below(name)))

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
        self._fit_edits()
        if self.on_oversize and self._exceeds_screen(toolkit):
            self.on_oversize()
        for name, listener in self._listeners:
            self.dialog.getControl(name).addActionListener(listener)
        for name, listener in self._watchers:
            control = self.dialog.getControl(name)
            model = self.model.getByName(name)
            if any(model.supportsService("com.sun.star.awt.UnoControl%sModel" % kind) for kind in ("ListBox", "CheckBox")):
                control.addItemListener(listener)
            else:
                control.addTextListener(listener)
        if self.on_ready:
            self.on_ready()
        try:
            self.dialog.execute()
            return self.result
        finally:
            if self.on_closed:
                self.on_closed()
            self.dialog.dispose()


def message_box(ctx, parent_peer, title, text, error=False, ask=False, buttons=None):
    """HST message (always Vietnamese buttons, whatever the UI language); returns True for OK / the first button.

    `ask` shows two buttons, `buttons`=(confirm, decline) or Có / Không; the decline button has the focus and is the
    default, so Enter or Esc never confirm. `error` is kept for callers; the title says which tool reports it."""
    import math
    from .data_files import load_locale
    common = load_locale("vi")["common"]
    labels = (buttons or (common["yes"], common["no"])) if ask else (common["ok"],)
    lines = sum(max(1, math.ceil(len(part) / 52)) for part in text.split("\n"))
    width, text_height = 260, lines * 9 + 2
    dialog = Dialog(ctx, title, width, text_height + 38)
    dialog.label("text", text, 8, 8, width - 16, text_height, wrap=True)
    y, x = text_height + 16, width - 8 - 70
    results = (1, 0) if ask else (1,)
    # the last label is inserted first: tab order, so it has the focus
    for label, result in reversed(list(zip(labels, results))):
        dialog.button("b%d" % result, label, x, y, 70, default=label == labels[-1],
                      callback=lambda result=result: dialog.end(result))
        x -= 74
    return dialog.execute(parent_peer) == 1
