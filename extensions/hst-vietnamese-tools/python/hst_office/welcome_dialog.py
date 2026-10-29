# SPDX-License-Identifier: AGPL-3.0-only
"""Native modal "Welcome to HST Office" dialog. Links open the system browser only when the user clicks them."""
import unohelper
from com.sun.star.awt import XActionListener, XWindowListener

from . import welcome_content
from .data_files import load_data
from .dialogs import Dialog

WIDTH, PAD = 330, 8
OPENED = []   # URLs handed to open_url (kept so the runtime check can see what a click produced)
CURRENT = None  # the dialog being shown (runtime check hook)


def open_url(ctx, url):
    """Open `url` in the system browser (the only place a network-capable action happens, and only on a click)."""
    shell = ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", ctx)
    shell.execute(url, "", 0)  # flags 0 = DEFAULTS; URLs are validated https by welcome_content


class _Click(unohelper.Base, XActionListener):
    def __init__(self, callback):
        self.callback = callback

    def actionPerformed(self, event):
        self.callback()

    def disposing(self, event):
        pass


class _Shown(unohelper.Base, XWindowListener):
    def __init__(self, callback):
        self.callback, self.done = callback, False

    def windowShown(self, event):
        if not self.done:
            self.done = True
            self.callback()

    def windowResized(self, event):
        pass

    def windowMoved(self, event):
        pass

    def windowHidden(self, event):
        pass

    def disposing(self, event):
        pass


class Welcome:
    """Builds the dialog from the content model; `on_shown` runs once the window is really displayed."""

    def __init__(self, ctx, strings, medium, on_shown=None):
        self.ctx, self.s = ctx, strings["welcome"]
        self.model = welcome_content.build_model(load_data("solutions.json"), medium)
        self.links = []  # (control name, url)
        self.on_shown = on_shown
        self.d = Dialog(ctx, self.s["title"], WIDTH, 100)
        self._build()

    def _click(self, url):
        try:
            OPENED.append(url)
            open_url(self.ctx, url)
        except Exception as exc:  # noqa: BLE001 - a missing browser must not close or crash the dialog
            self.d.set_text("status", self.s["openError"] % exc)

    def _link(self, name, text, url, x, y, w, help_text):
        model = self.d._add("FixedHyperlink", name, x, y, w, 9, Label=text, HelpText=help_text, TextColor=0x0B57D0)
        self.links.append((name, url))
        return model

    def _build(self):
        d, m, s, w = self.d, self.model, self.s, WIDTH - 2 * PAD
        y = PAD
        d.label("oneLiner", s["oneLiner"], PAD, y, w, 11).FontWeight = 150
        y += 14
        d.label("company", "%s\n%s" % (m["company"]["name"], m["company"]["slogan"]), PAD, y, w, 20, wrap=True)
        y += 22
        d.label("intro", m["company"]["intro"], PAD, y, w, 34, wrap=True)
        y += 38
        d.label("solutionsHeading", s["solutions"], PAD, y, w, 10).FontWeight = 150
        y += 12
        for i, sol in enumerate(m["solutions"]):
            self._link("link%d" % i, "%s — %s" % (sol["name"], sol["tagline"]), sol["url"], PAD, y, w, s["openHelp"] % sol["label"])
            note = (" (%s)" % sol["note"]) if sol["note"] else ""
            d.label("desc%d" % i, sol["description"] + note, PAD + 8, y + 10, w - 8, 19, wrap=True)
            y += 31
        d.label("services", "%s %s" % (s["services"], m["services"]), PAD, y, w, 10)
        y += 12
        c = m["contact"]
        d.label("contactLine", "%s %s · %s %s · %s %s" % (s["address"], c["address"], s["phone"], c["phone"], s["email"], c["email"]), PAD, y, w, 18, wrap=True)
        y += 19
        self._link("linkWebsite", c["website_label"], c["website"], PAD, y, w, s["openHelp"] % c["website_label"])
        y += 13
        d.label("status", "", PAD, y, w, 10)
        y += 12
        d.check("dontShow", s["dontShow"], PAD, y, 150, state=True, h=14)
        d.button("close", s["close"], WIDTH - PAD - 60, y, 60, kind=1, default=True)
        d.model.Height = y + 22

    def run(self, parent_peer=None):
        """Show modally. Returns True when "do not show again" was still ticked at close."""
        global CURRENT
        d, toolkit = self.d, self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        d.dialog.setVisible(False)
        d.dialog.createPeer(toolkit, parent_peer)
        keep = []
        for name, url in self.links:
            listener = _Click(lambda u=url: self._click(u))
            d.dialog.getControl(name).addActionListener(listener)
            keep.append(listener)
        if self.on_shown:
            shown = _Shown(self.on_shown)
            d.dialog.addWindowListener(shown)
            keep.append(shown)
        CURRENT = self
        try:
            d.dialog.execute()
            return bool(d.get("dontShow"))
        finally:
            CURRENT = None
            d.dialog.dispose()

    def click_link(self, index):
        """Fire the action of link `index` exactly as the dialog's listener does (runtime check hook)."""
        self._click(self.links[index][1])

    def close(self, dont_show=True):
        self.d.model.getByName("dontShow").State = 1 if dont_show else 0
        self.d.dialog.endExecute()
