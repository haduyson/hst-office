# SPDX-License-Identifier: AGPL-3.0-only
"""The ▾ menus of the Gửi thư tab: a PopupMenuController (Controller.xcu "PopupMenu") for the commands whose ribbon
buttons carry GenericPopupToolbarController (Controller.xcu "ToolBar"). Each item runs an
org.hst.office.mailmerge: command (mail_merge_handler.py); "Chèn trường trộn ▾" lists the columns of the document's
recipient list. The menu is filled again every time it opens."""
import unohelper
from com.sun.star.awt import XMenuListener
from com.sun.star.frame import XPopupMenuController
from com.sun.star.lang import XInitialization, XServiceInfo

IMPLEMENTATION_NAME = "org.hst.office.vi.MailMergeMenu"
PROTOCOL = "org.hst.office.mailmerge:"
RADIO = 2  # com.sun.star.awt.MenuItemStyle.RADIOCHECK
# button command -> [(item command, text key)]; "Start" marks the document type with a radio check
MENUS = {
    "Start": [("StartLetter", "menu.letter"), ("StartEnvelope", "menu.envelope"), ("StartLabels", "menu.labels"),
              ("StartEmail", "menu.email"), ("StartNormal", "menu.normal"), ("Wizard", "menu.wizard")],
    "Recipients": [("Recipients", "menu.existing"), ("NewList", "menu.new"), ("AddressBook", "menu.book")],
    "Rules": [("RuleIf", "rule.if"), ("RuleSkip", "rule.skip"), ("RuleAsk", "rule.ask"), ("RuleSeq", "rule.seq")],
    "Finish": [("FinishEdit", "fin.edit"), ("FinishPrint", "fin.print"), ("FinishMail", "fin.mail"),
               ("FinishPdf", "fin.pdf"), ("FinishDocx", "fin.docx")],
}
TYPE_ITEMS = {"letter": "StartLetter", "email": "StartEmail"}


def menu_items(command, texts, columns=(), doc_type=""):
    """[(item command, label, arguments, checked)] of a menu. Pure: tests use it."""
    if command == "InsertField":
        if not columns:
            return [("", texts["menu.no-list"], {}, None)]
        return ([("InsertColumn", column, {"Column": column}, None) for column in columns]
                + [("FieldFormat", texts["menu.format"], {}, None)])
    checked = TYPE_ITEMS.get(doc_type)
    return [(item, texts[key], {}, (item == checked) if command == "Start" and item in TYPE_ITEMS.values() else None)
            for item, key in MENUS.get(command, ())]


class MailMergeMenu(unohelper.Base, XPopupMenuController, XInitialization, XMenuListener, XServiceInfo):
    def __init__(self, ctx, *args):
        self.ctx, self.frame, self.command, self.menu, self.items = ctx, None, "", None, []
        if args:  # unohelper hands the factory's arguments (Frame, CommandURL, ...) to the constructor
            self.initialize(args)

    def initialize(self, args):
        for arg in args:
            name, value = getattr(arg, "Name", ""), getattr(arg, "Value", None)
            if name == "Frame":
                self.frame = value
            elif name == "CommandURL" and isinstance(value, str):
                self.command = value[len(PROTOCOL):] if value.startswith(PROTOCOL) else value

    def getImplementationName(self):
        return IMPLEMENTATION_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.frame.PopupMenuController",)

    def setPopupMenu(self, menu):
        self.menu = menu
        menu.addMenuListener(self)
        self.updatePopupMenu()

    def _session(self):
        from . import mail_merge_session as sessions
        return sessions.get(self.frame.getController().getModel())

    def _columns(self, session):
        """Insertable columns of the document's list (computed columns included), or ()."""
        from . import mail_merge_table as mt
        if not session.has_list:
            return ()
        session.load(self.ctx)
        return mt.insertable(session.effective().headers)

    def updatePopupMenu(self):
        if self.menu is None:
            return
        try:
            from .mail_merge_texts import texts
            session = self._session() if self.command in ("InsertField", "Start") else None
            columns = self._columns(session) if self.command == "InsertField" else ()
            doc_type = session.meta.get("type", "") if session is not None else ""
            self.items = menu_items(self.command, texts(self.ctx), columns, doc_type)
        except Exception:  # noqa: BLE001 - unreadable list: an empty menu, the error goes to the local log
            from .diag_log import exception
            exception("mail merge menu " + self.command)
            self.items = []
        self.menu.clear()
        for index, (item, label, _args, checked) in enumerate(self.items, 1):
            self.menu.insertItem(index, label, RADIO if checked is not None else 0, index - 1)
            self.menu.enableItem(index, bool(item))
            if checked:
                self.menu.checkItem(index, True)

    def itemSelected(self, event):
        index = event.MenuId - 1
        if not 0 <= index < len(self.items) or not self.items[index][0] or self.frame is None:
            return
        from com.sun.star.beans import PropertyValue
        item, _label, args, _checked = self.items[index]
        helper = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", self.ctx)
        props = tuple(PropertyValue(Name=k, Value=v) for k, v in args.items())
        try:
            helper.executeDispatch(self.frame, PROTOCOL + item, "", 0, props)
        except Exception:  # noqa: BLE001 - the handler reports its own errors; never raise into the menu
            from .diag_log import exception
            exception("mail merge menu item " + item)

    def itemHighlighted(self, event):
        pass

    def itemActivated(self, event):
        pass

    def itemDeactivated(self, event):
        pass

    def disposing(self, event):
        self.menu = None
