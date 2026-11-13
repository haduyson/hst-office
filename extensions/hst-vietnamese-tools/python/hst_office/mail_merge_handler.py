# SPDX-License-Identifier: AGPL-3.0-only
"""ProtocolHandler of the Trộn thư commands on the Gửi thư tab: org.hst.office.mailmerge:<Command>
(handler.commands()). One handler per frame. Status: "Preview" is a check item, "Record" shows
"Bản ghi n / N" as its label, the move commands are greyed out at the ends; everything is enabled only in Writer.
The command code is imported on first use (the office creates handlers while it starts)."""
import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo

IMPLEMENTATION_NAME = "org.hst.office.vi.MailMergeDispatchProvider"
PROTOCOL = "org.hst.office.mailmerge:"
COMMANDS = frozenset((
    "Recipients", "EditRecipients", "InsertField", "FieldFormat", "Preview", "First", "Prev", "Next", "Last",
    "Record", "Find", "Finish", "Wizard",
    # ▾ buttons (their menus: mail_merge_menu.py) and the menu items
    "Start", "Rules", "StartLetter", "StartEnvelope", "StartLabels", "StartEmail", "StartNormal", "NewList",
    "AddressBook", "InsertColumn", "AddressBlock", "Greeting", "RuleIf", "RuleSkip", "RuleAsk", "RuleSeq", "Check",
    "FinishEdit", "FinishPrint", "FinishMail", "FinishPdf", "FinishDocx"))
NEEDS_LIST = COMMANDS - {"Recipients", "EditRecipients", "Wizard", "Start", "StartLetter", "StartEnvelope",
                         "StartLabels", "StartEmail", "StartNormal", "NewList", "AddressBook"}
MENU_ONLY = {"Start", "Rules"}  # whole-button menus: nothing to run on a click
WIZARD = ".uno:MailMergeWizard"  # "Trình hướng dẫn trộn thư (đầy đủ)": the engine's wizard under the HST label
RECORD_LABEL = {"vi": "Bản ghi", "en": "Record"}


def status(command, session, language="vi"):
    """(enabled, state) of a command for the session of the document (None outside Writer). Pure: tests use it."""
    if session is None:
        return False, None
    has_list = session.has_list
    enabled = has_list or command not in NEEDS_LIST
    if command == "Preview":
        return enabled, bool(session.preview)
    label = RECORD_LABEL.get(language, RECORD_LABEL["vi"])
    loaded = session.table is not None
    count = len(session.checked()) if loaded else 0
    position = min(session.position, max(count - 1, 0))
    if command == "Record":
        return enabled, ("%s %d / %d" % (label, position + 1, count)) if loaded and count else label
    if command in ("First", "Prev"):
        return enabled and (not loaded or (count > 0 and (position > 0 or not session.preview))), None
    if command in ("Next", "Last"):
        return enabled and (not loaded or (count > 0 and (position < count - 1 or not session.preview))), None
    return enabled, None


def commands():
    """Every command function by name, from the four command modules (imported on first use)."""
    from . import mail_merge_commands, mail_merge_design_commands, mail_merge_finish_commands, mail_merge_list_commands
    table = {}
    for module in (mail_merge_commands, mail_merge_finish_commands, mail_merge_design_commands, mail_merge_list_commands):
        table.update(module.COMMANDS)
    return table


class MailMergeHandler(unohelper.Base, XServiceInfo, XInitialization, XDispatchProvider, XDispatch):
    def __init__(self, ctx, *args):
        self.ctx, self.frame, self.listeners = ctx, None, []

    def initialize(self, args):
        if args:
            self.frame = args[0]

    def getImplementationName(self):
        return IMPLEMENTATION_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.frame.ProtocolHandler",)

    def queryDispatch(self, url, target_frame_name, search_flags):
        return self if url.Protocol == PROTOCOL and url.Path in COMMANDS else None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags) for r in requests)

    def _document(self):
        controller = self.frame.getController() if self.frame else None
        model = controller.getModel() if controller else None
        return model if model is not None and model.supportsService("com.sun.star.text.TextDocument") else None

    def dispatch(self, url, arguments):
        try:
            if self._document() is None:
                return
            if url.Path == "Wizard":
                helper = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", self.ctx)
                return helper.executeDispatch(self.frame, WIZARD, "", 0, ())
            if url.Path in MENU_ONLY:
                return
            from .mail_merge_context import Context
            args = {getattr(a, "Name", ""): getattr(a, "Value", None) for a in arguments or ()}
            commands()[url.Path](Context(self.ctx, self.frame, args))
        except Exception:  # noqa: BLE001 - never raise into the office UI thread
            from .diag_log import exception
            exception("mail merge " + url.Path)
        finally:
            self._broadcast()

    def _state(self, url):
        doc = self._document()
        session = None
        if doc is not None:
            from . import mail_merge_session
            session = mail_merge_session.get(doc)
        language = "vi"
        if url.Path in ("Record",):
            from .mail_merge_texts import language as ui_language
            language = ui_language(self.ctx)
        return status(url.Path, session, language)

    def _send(self, control, url):
        from com.sun.star.frame import FeatureStateEvent
        try:
            enabled, state = self._state(url)
            event = FeatureStateEvent(FeatureURL=url, IsEnabled=enabled, Requery=False, Source=self)
            if state is not None:
                event.State = state
            control.statusChanged(event)
        except Exception:  # noqa: BLE001 - a control that went away, or a closing document
            pass

    def _broadcast(self):
        for control, url in list(self.listeners):
            self._send(control, url)

    def addStatusListener(self, control, url):
        self.listeners.append((control, url))
        self._send(control, url)

    def removeStatusListener(self, control, url):
        self.listeners = [(c, u) for c, u in self.listeners if not (c == control and u.Complete == url.Complete)]
