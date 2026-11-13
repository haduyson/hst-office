# SPDX-License-Identifier: AGPL-3.0-only
"""Plain-Python stand-ins for driving the real source form (citation_entry_dialog.run) without an office.

FakeDialog mirrors the dialogs.Dialog surface the form uses; ``script`` is the list of user actions run while the
dialog is "open" (after on_ready, like the real execute). Network traffic is whatever reaches ``Transport``.
"""
import os
import sys
import types

import _paths


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        value = type(name, (), {})
        setattr(self, name, value)
        return value


for _name in ("uno", "unohelper", "com", "com.sun", "com.sun.star", "com.sun.star.awt", "com.sun.star.awt.Key",
              "com.sun.star.lang", "com.sun.star.util", "com.sun.star.util.MeasureUnit"):
    sys.modules.setdefault(_name, _StubModule(_name))

RECORDED = os.path.join(_paths.ROOT, "tests", "fixtures", "citations", "lookup")


def recorded(name):
    with open(os.path.join(RECORDED, name), "rb") as handle:
        return handle.read()


class Control:
    def __init__(self, kind, name, x, y, w, h, **props):
        self.kind, self.name, self.x, self.y, self.w, self.h = kind, name, x, y, w, h
        self.Label = props.get("text", "")
        self.Text, self.Enabled = props.get("value", ""), True
        self.State, self.Selected, self.callback = props.get("state", False), props.get("selected", 0), None


class FakeDialog:
    script = []  # [callable(dialog)], set by the test before run()

    def __init__(self, ctx, title, width, height):
        self.title, self.width, self.height = title, width, height
        self.controls, self.watchers, self.on_ready, self.result = {}, [], None, 0
        self.model = types.SimpleNamespace(getByName=lambda name: self.controls[name])
        self.dialog = types.SimpleNamespace(getPeer=lambda: None)

    def _add(self, kind, name, x, y, w, h, **props):
        self.controls[name] = Control(kind, name, x, y, w, h, **props)
        return self.controls[name]

    def label(self, name, text, x, y, w, h=10, wrap=False):
        self._add("label", name, x, y, w, h, text=text)

    def edit(self, name, x, y, w, h=12, text="", multiline=False, readonly=False, help_text=""):
        self._add("edit", name, x, y, w, h, value=text)

    def listbox(self, name, x, y, w, items, selected=0, h=12, help_text="", dropdown=True):
        self._add("list", name, x, y, w, h, selected=selected)

    def check(self, name, text, x, y, w, state=True, h=10):
        self._add("check", name, x, y, w, h, text=text, state=state)

    def button(self, name, text, x, y, w, kind=None, callback=None, default=False, h=14):
        self._add("button", name, x, y, w, h, text=text).callback = callback or (lambda: self.end(0))

    def on_change(self, names, callback):
        self.watchers += [(name, callback) for name in names]

    def get(self, name):
        control = self.controls[name]
        return {"list": control.Selected, "check": bool(control.State)}.get(control.kind, control.Text)

    def select(self, name, index):
        self.controls[name].Selected = index

    def set_text(self, name, text):
        self.controls[name].Text = text

    def end(self, code=1):
        self.result = code

    def execute(self, peer=None):
        if self.on_ready:
            self.on_ready()
        for action in self.script:
            action(self)
        return self.result

    # user actions -------------------------------------------------------------------------------------------
    def type_into(self, name, text):
        """Typing or pasting: the text changes, then every change listener of that control runs."""
        self.controls[name].Text = text
        for watched, callback in self.watchers:
            if watched == name:
                callback()

    def click(self, name):
        self.controls[name].callback()


class Transport:
    """Records every request the lookup layer would send; answers from recorded service replies by host."""

    def __init__(self, replies):
        self.replies, self.requests = replies, []

    def __call__(self, request):
        self.requests.append(request)
        host = request["url"].split("/")[2]
        return 200, self.replies[host]


class Library:
    read_only = False

    def __init__(self):
        self.added, self.updated = [], []

    def get(self, item_id):
        return None

    def add(self, items):
        self.added += items
        return items, []

    def update(self, item):
        self.updated.append(item)


def crossref_replies():
    return {"doi.org": recorded("doi-org-10.1038-nature14539.json"),
            "api.crossref.org": recorded("crossref-query-bibliographic.json")}


def ui_recorder(ui, answers=()):
    """Replace the message boxes of citation_ui; returns the list of texts the user was shown."""
    shown, answers = [], list(answers)

    def choose(ctx, peer, title, text, labels, default=0):
        shown.append(text)
        return answers.pop(0) if answers else default

    ui.choose = choose
    ui.inform = lambda ctx, peer, texts, text: shown.append(text)
    ui.ask = lambda ctx, peer, texts, text: shown.append(text) and False
    ui.save_library = lambda ctx, peer, texts, library: shown.append("saved library")
    return shown
