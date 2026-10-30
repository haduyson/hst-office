# SPDX-License-Identifier: AGPL-3.0-only
"""Native modal "Chào mừng đến HST Office" dialog. Links open the system browser only when the user clicks them.

Introductory content: always Vietnamese (welcome_job loads the "vi" strings in every UI language). Sections:
logo and greeting with the "Miễn phí vĩnh viễn" badge, the three applications with their icons, the key HST
features, the F1 guide tip, other HASON TECH solutions (names; tagline as tooltip), contact and website link,
"Không hiển thị lại" and Close. Images are the brand PNGs packaged in <extension>/icons (build-extensions.py).
"""
import math
import os

import unohelper
from com.sun.star.awt import XActionListener, XWindowListener

from . import welcome_content
from .data_files import EXT_ROOT, load_data
from .dialogs import Dialog

WIDTH, PAD = 340, 10
TEXT_W = WIDTH - 2 * PAD
LINK_COLOR, BADGE_TEXT, BADGE_BACK, MUTED = 0x0B57D0, 0xC8102E, 0xFFD60A, 0x5F6368
APPS = (("appWriter", "hst-writer-64.png"), ("appSheets", "hst-sheets-64.png"), ("appSlides", "hst-slides-64.png"))
OPENED = []   # URLs handed to open_url (kept so the runtime check can see what a click produced)
CURRENT = None  # the dialog being shown (runtime check hook)


def open_url(ctx, url):
    """Open `url` in the system browser (the only place a network-capable action happens, and only on a click)."""
    shell = ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", ctx)
    shell.execute(url, "", 0)  # flags 0 = DEFAULTS; URLs are validated https by welcome_content


def icon_url(name):
    """file URL of a packaged brand image, or "" when it is missing (the dialog then simply shows no image)."""
    import uno
    path = os.path.join(EXT_ROOT, "icons", name)
    return uno.systemPathToFileUrl(path) if os.path.isfile(path) else ""


def text_height(text, width, line=9):
    """Height for a wrapped label: AppFont units are font-relative, so the estimate holds on every platform."""
    per_line = max(1, int(width / 3.0))  # measured: ~3 units per Vietnamese character
    lines = sum(max(1, math.ceil(len(part) / per_line)) for part in text.split("\n"))
    return lines * line + 1


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
            self.d.model.getByName("status").Label = self.s["openError"] % exc

    def _link(self, name, text, url, x, y, w, help_text):
        model = self.d._add("FixedHyperlink", name, x, y, w, 10, Label=text, HelpText=help_text, TextColor=LINK_COLOR)
        self.links.append((name, url))
        return model

    def _image(self, name, file_name, x, y, w, h):
        return self.d._add("ImageControl", name, x, y, w, h, ImageURL=icon_url(file_name), ScaleImage=True,
                           ScaleMode=1, Border=0, Tabstop=False)  # ScaleMode 1 = ANISOTROPIC: keep the aspect ratio

    def _heading(self, name, text, y):
        self.d.label(name, text, PAD, y, TEXT_W, 10).FontWeight = 150
        return y + 12

    def _rule(self, name, y):
        self.d._add("FixedLine", name, PAD, y, TEXT_W, 4)
        return y + 6

    def _build(self):
        d, m, s = self.d, self.model, self.s
        # Greeting: logo, heading, one-liner, badge.
        self._image("logo", "hst-office-logo.png", PAD, PAD, 56, 48)
        x = PAD + 64
        heading = d.label("heading", s["heading"], x, PAD + 2, WIDTH - PAD - x, 14)
        heading.FontWeight, heading.FontHeight = 150, 13
        d.label("oneLiner", s["oneLiner"], x, PAD + 18, WIDTH - PAD - x, 18, wrap=True)
        badge = d.label("freeBadge", s["freeBadge"], x, PAD + 38, 80, 11)
        badge.FontWeight, badge.TextColor, badge.BackgroundColor, badge.Align = 150, BADGE_TEXT, BADGE_BACK, 1
        y = self._rule("rule1", PAD + 54)
        # The three applications.
        y = self._heading("appsHeading", s["appsHeading"], y)
        tile = TEXT_W / 3.0
        for i, (key, image) in enumerate(APPS):
            left = int(PAD + i * tile)
            self._image("icon%d" % i, image, int(left + tile / 2 - 12), y, 24, 24)
            label = d.label(key, s[key], left, y + 26, int(tile), 18, wrap=True)
            label.Align = 1
        y += 48
        # Key features.
        y = self._heading("featuresHeading", s["featuresHeading"], y)
        for i, feature in enumerate(s["features"]):
            text = "•  " + feature
            h = text_height(text, TEXT_W - 6)
            d.label("feature%d" % i, text, PAD + 4, y, TEXT_W - 4, h, wrap=True)
            y += h + 1
        tip = d.label("helpTip", s["helpTip"], PAD, y + 2, TEXT_W, 10)
        tip.TextColor = MUTED
        y = self._rule("rule2", y + 15)
        # Other HASON TECH solutions, two columns of names (tagline and description as tooltip).
        y = self._heading("solutionsHeading", s["solutions"], y)
        half = TEXT_W // 2
        rows = int(math.ceil(len(m["solutions"]) / 2.0))
        for i, sol in enumerate(m["solutions"]):
            col, row = i // rows, i % rows
            tooltip = "%s — %s. %s" % (sol["name"], sol["tagline"], s["openHelp"] % sol["label"])
            self._link("link%d" % i, sol["name"], sol["url"], PAD + col * half, y + row * 11, half - 4, tooltip)
        y += rows * 11 + 3
        c = m["contact"]
        contact = s["contactLine"] % {"email": c["email"], "phone": c["phone"]}
        d.label("contactLine", contact, PAD, y, TEXT_W, 10)
        y += 11
        self._link("linkWebsite", s["website"] % c["website_label"], c["website"], PAD, y, TEXT_W, s["openHelp"] % c["website_label"])
        y += 12
        d.label("status", "", PAD, y, TEXT_W, 10)
        y += 12
        d.check("dontShow", s["dontShow"], PAD, y + 2, 180, state=True, h=10)
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
