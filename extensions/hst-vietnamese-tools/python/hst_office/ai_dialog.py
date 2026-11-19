# SPDX-License-Identifier: AGPL-3.0-only
"""The Trợ lý AI dialog of one action (FormulaWrite, FormulaExplain, Writing, Help).

The input box is prefilled from the document (the selection, or the formula of the cell) and stays editable; nothing
leaves the machine until the user presses "Gửi", and "Xem nội dung sẽ gửi" shows the exact system and user text
first. The request runs on a worker thread (ai_client, 2-minute deadline); the answer comes back on the main
thread. Insert buttons change the document only when pressed, in one undo step (ai_document).
"""
import threading

from . import ai_document as document
from . import diag_log
from .ai_client import Settings, complete
from .ai_providers import MAX_PROMPT, PROVIDERS, AiError
from .ai_ribbon_map_uno import command_map
from .ai_texts import ACTIONS, FORMULA_EXPLAIN, FORMULA_WRITE, TEXT, WRITING_MODES, error_text, extract_formula, \
    help_system, writing_system
from .dialogs import Dialog, palette
from .update_ui import on_main_thread

WIDTH, HEIGHT = 330, 310


class AssistantDialog:
    def __init__(self, ctx, frame, action, settings):
        self.ctx, self.frame, self.action, self.settings = ctx, frame, action, settings
        self.controller = frame.getController()
        self.model = self.controller.getModel()
        self.cell = document.active_cell(self.controller) if document.kind(self.model) == "calc" else None
        self.label = PROVIDERS[settings.provider]["label"]
        self.answer, self.closed, self.dialog = "", False, None
        # read on the main thread now; the request itself runs on a worker
        self.ribbon_map = command_map(ctx, document.kind(self.model)) if action == "Help" else ""

    def prefill(self):
        if self.action == "FormulaExplain" and self.cell is not None:
            return self.cell.getFormula()
        if self.action == "Writing":
            return document.selected_text(self.controller)
        return ""

    def request(self):
        """(system, user text) that "Gửi" sends now."""
        d, text = self.dialog, self.dialog.get("input").strip()
        if self.action == "FormulaWrite":
            where = " Công thức sẽ đặt tại ô %s." % document.cell_name(self.cell) if self.cell is not None else ""
            return FORMULA_WRITE, text + where
        if self.action == "FormulaExplain":
            return FORMULA_EXPLAIN, text
        if self.action == "Writing":
            return writing_system(max(0, d.get("mode")), d.get("instruction")), text
        return help_system(self.ribbon_map), text

    def run(self, parent_peer=None):
        d = self.dialog = Dialog(self.ctx, "%s: %s" % (TEXT["title"], ACTIONS[self.action]), WIDTH, HEIGHT)
        muted = palette(self.ctx)["muted"]
        d.label("using", TEXT["using"] % (self.label, self.settings.model), 8, 6, WIDTH - 16).TextColor = muted
        y = 20
        if self.action == "Writing":
            d.label("mode_label", TEXT["mode"], 8, y + 2, 60)
            d.listbox("mode", 70, y, WIDTH - 78, [m[0] for m in WRITING_MODES], help_text=TEXT["mode"])
            d.label("instruction_label", TEXT["instruction"], 8, y + 18, 60)
            d.edit("instruction", 70, y + 16, WIDTH - 78, help_text=TEXT["instruction"])
            y += 32
        key = {"FormulaWrite": "input_formula", "FormulaExplain": "input_explain", "Writing": "input_writing"}
        d.label("input_label", TEXT[key.get(self.action, "input_help")], 8, y, WIDTH - 16)
        d.edit("input", 8, y + 11, WIDTH - 16, 58 if self.action != "Writing" else 50, text=self.prefill(),
               multiline=True, help_text=TEXT[key.get(self.action, "input_help")])
        y += 72 if self.action != "Writing" else 64
        d.label("privacy", TEXT["privacy"] % self.label, 8, y, WIDTH - 16, 26, wrap=True).TextColor = muted
        d.button("preview", TEXT["preview"], 8, y + 28, 100, callback=self.show_preview)
        d.button("send", TEXT["send"], WIDTH - 8 - 60, y + 28, 60, callback=self.on_send, default=True)
        y += 46
        status = d.label("status", "", 8, y, WIDTH - 16, 10)
        status.TextColor = muted
        d.label("answer_label", TEXT["answer"], 8, y + 12, WIDTH - 16)
        d.edit("answer", 8, y + 23, WIDTH - 16, HEIGHT - y - 23 - 26, multiline=True, readonly=True,
               help_text=TEXT["answer"])
        bottom = HEIGHT - 20
        if self.action == "FormulaWrite" and self.cell is not None:
            d.button("apply", TEXT["insert_formula"] % document.cell_name(self.cell), 8, bottom, 110,
                     callback=self.insert_formula)
        elif self.action == "Writing":
            d.button("apply", TEXT["replace"], 8, bottom, 84, callback=lambda: self.apply(document.replace_selection))
            d.button("apply_after", TEXT["insert_after"], 96, bottom, 90,
                     callback=lambda: self.apply(document.insert_after_selection))
        d.button("close", TEXT["close"], WIDTH - 8 - 60, bottom, 60, kind=2)
        d.on_ready = lambda: self._busy(False)

        def closed():
            self.closed = True
        d.on_closed = closed
        d.execute(parent_peer)

    def _set(self, name, **props):
        if self.closed:
            return
        try:
            model = self.dialog.model.getByName(name)
            for key, value in props.items():
                setattr(model, key, value)
        except Exception:  # noqa: BLE001 - optional control missing for this action
            pass

    def _busy(self, busy):
        for name in ("input", "mode", "instruction", "preview", "send"):
            self._set(name, Enabled=not busy)
        ready = not busy and bool(self.answer)
        for name in ("apply", "apply_after"):
            self._set(name, Enabled=ready)

    def show_preview(self):
        try:
            system, text = self.request()
            view = Dialog(self.ctx, TEXT["preview_title"], 360, 250)
            view.label("intro", TEXT["preview_intro"] % self.label, 8, 6, 344, 18, wrap=True)
            content = "[Mô tả nhiệm vụ gửi kèm]\n%s\n\n[Nội dung của bạn]\n%s" % (system, text)
            view.edit("content", 8, 26, 344, 198, text=content, multiline=True, readonly=True,
                      help_text=TEXT["preview_title"])
            view.button("close", TEXT["close"], 360 - 8 - 54, 230, 54, kind=1, default=True)
            view.execute(self.dialog.dialog.getPeer())
        except Exception:  # noqa: BLE001 - never raise into the dialog's event loop
            diag_log.exception("ai_dialog")

    def on_send(self):
        system, text = self.request()
        if not text:
            self._set("status", Label=TEXT["empty"])
            return
        if len(text) > MAX_PROMPT:
            self._set("status", Label=TEXT["too_long"] % MAX_PROMPT)
            return
        self.answer = ""
        self._set("answer", Text="")
        self._set("status", Label=TEXT["sending"] % self.label)
        self._busy(True)
        settings = self.settings

        def work():
            try:
                outcome = complete(settings, system, text)
            except AiError as error:
                outcome = error
            except Exception as error:  # noqa: BLE001 - any failure is reported, never raised in a thread
                diag_log.exception("ai_dialog")
                outcome = AiError("reply", type(error).__name__)
            on_main_thread(self.ctx, lambda: self.finished(outcome))
        threading.Thread(target=work, name="hst-ai-request", daemon=True).start()

    def finished(self, outcome):
        """Main thread: the answer (text, truncated) or an AiError."""
        if self.closed:
            return
        if isinstance(outcome, AiError):
            self.answer = ""
            self._set("status", Label="")
            self._set("answer", Text=error_text(outcome))
        else:
            self.answer, truncated = outcome
            self._set("status", Label=TEXT["done"] % self.label + (TEXT["truncated"] if truncated else ""))
            self._set("answer", Text=self.answer)
        self._busy(False)

    def insert_formula(self):
        formula = extract_formula(self.answer)
        if not formula:
            self._set("status", Label=TEXT["no_formula"])
        elif document.insert_formula(self.model, self.cell, formula):
            self._set("status", Label=TEXT["applied"])
        else:
            self._set("status", Label=TEXT["formula_failed"])

    def apply(self, action):
        try:
            done = action(self.model, self.controller, self.answer)
        except Exception:  # noqa: BLE001 - read-only document, protected section...
            diag_log.exception("ai_dialog")
            done = False
        self._set("status", Label=TEXT["applied"] if done else error_text(AiError("apply")))


def run(ctx, frame, action, provider, model, key, version, proxy):
    settings = Settings(provider, model, key, version, proxy)
    AssistantDialog(ctx, frame, action, settings).run(frame.getContainerWindow())
