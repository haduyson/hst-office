# SPDX-License-Identifier: AGPL-3.0-only
"""Trợ giúp ▸ Báo lỗi cho HASON TECH…: the error report dialog (also opened by the crash prompt with kind=crash).

Nothing is sent until the user presses "Gửi". The summary (version, OS, app) is always part of the report and shown
read-only, together with the anonymous install ID when "Gửi mã máy ẩn danh" is on (update_install_id.for_report:
read once here, never created for a report); "Gửi kèm thông tin chẩn đoán" (systemInfo, the local log, the crash
facts) is ticked by default and can be unticked; "Xem nội dung sẽ gửi" shows the exact object that would be sent now. Sending runs on a worker thread (error_report_send, 15 s deadline); the answer comes back to the main
thread. A retry keeps the same reportId. On 429, 5xx or no answer the e-mail fallback is offered.
"""
import threading

from . import diag_log, error_report_info as info
from .dialogs import Dialog, message_box, palette
from .error_report_mail import mailto_url, summary_lines
from .error_report_payload import build_payload, encode, new_report_id, preview_text, problems, utc_now
from .error_report_send import send
from .error_report_texts import TEXT
from .update_install_id import for_error_report
from .update_fetch import release_info
from .update_ui import on_main_thread, proxy

WIDTH, HEIGHT = 320, 262


class ReportDialog:
    def __init__(self, ctx, frame, kind="user", crash="", app=None):
        self.ctx, self.frame, self.kind, self.crash = ctx, frame, kind, crash
        self.report_id = new_report_id()
        self.product, self.os, self.locale, self.app = info.environment(ctx, frame)
        self.app = app or self.app  # a crash report names the app that was open, not the one now in front
        self.release = release_info()
        self.install_id = for_error_report(ctx)  # None when the box is off or no ID exists yet
        self.proxy = proxy(ctx)  # read on the main thread; the worker only sends
        self._diagnostics = None
        self.outcome, self.closed, self.dialog = None, False, None

    def diagnostics(self):
        """systemInfo, crash facts and the filtered log, gathered once on the main thread when first needed."""
        if self._diagnostics is None:
            base = self.payload(False)
            secrets = info.office_secrets(self.ctx)
            self._diagnostics = {"systemInfo": info.system_info(self.ctx, self.frame, base), "crash": self.crash,
                                 "log": info.recent_log(secrets)}
        return self._diagnostics

    def payload(self, with_diagnostics=None):
        dialog = self.dialog
        if with_diagnostics is None:
            with_diagnostics = bool(dialog and dialog.get("diagnostics"))
        return build_payload(self.report_id, self.kind, utc_now(), self.product, self.os, self.locale, self.app,
                             dialog.get("description") if dialog else "", dialog.get("email") if dialog else "",
                             self.diagnostics() if with_diagnostics else None, self.install_id)

    def run(self, parent_peer=None):
        crash = self.kind == "crash"
        colours = palette(self.ctx)
        d = self.dialog = Dialog(self.ctx, TEXT["title"], WIDTH, HEIGHT)
        d.label("intro", TEXT["intro_crash" if crash else "intro"], 8, 6, WIDTH - 16, 20, wrap=True)
        d.label("description_label", TEXT["description_crash" if crash else "description"], 8, 30, WIDTH - 16)
        d.edit("description", 8, 41, WIDTH - 16, 62, multiline=True, help_text=TEXT["description"])
        d.label("email_label", TEXT["email"], 8, 108, WIDTH - 16)
        d.edit("email", 8, 119, WIDTH - 16, help_text=TEXT["email"])
        d.label("summary_label", TEXT["summary"], 8, 137, WIDTH - 16)
        summary = "\n".join(summary_lines(build_payload(self.report_id, self.kind, "", self.product, self.os,
                                                        self.locale, self.app)))
        d.edit("summary", 8, 148, WIDTH - 16, 32, text=summary, multiline=True, readonly=True,
               help_text=TEXT["summary"])
        d.check("diagnostics", TEXT["diagnostics"], 8, 186, WIDTH - 16, state=True)
        note = d.label("note", TEXT["diagnostics_note_crash" if crash else "diagnostics_note"], 18, 197,
                       WIDTH - 26, 18, wrap=True)
        note.TextColor = colours["muted"]
        status = d.label("status", "", 8, 218, WIDTH - 16, 18, wrap=True)
        status.TextColor = colours["error"]
        d.button("preview", TEXT["preview"], 8, HEIGHT - 20, 92, callback=self.show_preview)
        d.button("send", TEXT["send"], WIDTH - 8 - 54 - 4 - 54, HEIGHT - 20, 54, callback=self.on_send, default=True)
        d.button("cancel", TEXT["cancel"], WIDTH - 8 - 54, HEIGHT - 20, 54, kind=2)

        def closed():
            self.closed = True
        d.on_closed = closed
        d.execute(parent_peer)
        if self.outcome is not None and self.outcome.kind == "sent":
            message_box(self.ctx, parent_peer, TEXT["title"], TEXT["sent"] % self.outcome.ticket)
        return self.outcome

    def _status(self, text):
        self.dialog.model.getByName("status").Label = text

    def _busy(self, busy):
        for name in ("description", "email", "diagnostics", "preview", "send"):
            self.dialog.model.getByName(name).Enabled = not busy

    def _peer(self):
        try:
            return self.dialog.dialog.getPeer() if not self.closed else None
        except Exception:  # noqa: BLE001
            return None

    def show_preview(self):
        try:
            text = preview_text(self.payload())
            view = Dialog(self.ctx, TEXT["preview_title"], 380, 262)
            view.label("intro", TEXT["preview_intro"], 8, 6, 364)
            view.edit("content", 8, 18, 364, 218, text=text, multiline=True, readonly=True,
                      help_text=TEXT["preview_title"])
            view.button("close", TEXT["close"], 380 - 8 - 54, 242, 54, kind=1, default=True)
            view.execute(self._peer())
        except Exception:  # noqa: BLE001 - never raise into the dialog's event loop
            diag_log.exception("error_report_dialog")

    def on_send(self):
        payload = self.payload()
        found = problems(payload)
        if found:
            code = found[0]
            self._status(TEXT[code] % len(payload.get("description", "")) if code == "description_long" else TEXT[code])
            return
        self._status(TEXT["sending"])
        self._busy(True)
        body, version = encode(payload), self.release["release"]

        def work():
            outcome = send(body, version, self.proxy, self.release.get("test_mode", False))
            on_main_thread(self.ctx, lambda: self.finished(outcome, payload))
        threading.Thread(target=work, name="hst-error-report", daemon=True).start()

    def finished(self, outcome, payload):
        """Main thread: the answer to one POST."""
        self.outcome = outcome
        if self.closed:  # the user closed the dialog while it was sending: still say what happened
            parent = self.frame.getContainerWindow() if self.frame is not None else None
            if outcome.kind == "sent":
                message_box(self.ctx, parent, TEXT["title"], TEXT["sent"] % outcome.ticket)
            else:
                self.fallback(outcome, payload, parent)
            return
        if outcome.kind == "sent":
            self.dialog.end(1)
            return
        self._busy(False)
        self._status(TEXT["not_sent"])
        self.fallback(outcome, payload, self._peer())

    def fallback(self, outcome, payload, parent):
        if not outcome.offers_email:
            message_box(self.ctx, parent, TEXT["title"], TEXT[outcome.kind], error=True)
            return
        if message_box(self.ctx, parent, TEXT["title"], TEXT[outcome.kind], ask=True,
                       buttons=(TEXT["mail"], TEXT["close"])):
            open_mail(self.ctx, payload, parent)


def open_mail(ctx, payload, parent=None):
    try:
        shell = ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", ctx)
        shell.execute(mailto_url(payload), "", 1)  # 1 = URIS_ONLY
    except Exception:  # noqa: BLE001 - no mail program
        diag_log.exception("error_report_dialog")
        message_box(ctx, parent, TEXT["title"], TEXT["mail_failed"], error=True)


def run(ctx, frame, kind="user", crash="", app=None):
    peer = frame.getContainerWindow() if frame is not None else None
    return ReportDialog(ctx, frame, kind, crash, app).run(peer)
