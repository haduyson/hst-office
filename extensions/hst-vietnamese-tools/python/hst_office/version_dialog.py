# SPDX-License-Identifier: AGPL-3.0-only
"""Dialog "Phiên bản trước" (command org.hst.office.vi:PreviousVersions: Tệp tin menu of HST Writer, HST Sheets and
HST Slides): the stored versions of the open document's file, newest first, with "Mở xem" (a read-only copy) and
"Khôi phục". Khôi phục asks inside the dialog, then, after the dialog has closed, keeps the current file as a version,
closes the document, puts the chosen version in place and opens the file again (version_restore for the file steps).
"""
import os

from . import diag_log
from . import version_texts as T
from .dialogs import Dialog, message_box, palette

OPEN, RESTORE = 3, 4
WIDTH, HEIGHT = 280, 214


class VersionsDialog:
    """The dialog itself; show() returns None, ("open", version) or ("restore", version)."""

    def __init__(self, ctx, file_name, folder, versions, state_text, modified):
        self.versions, self.modified, self.choice, self.asked = versions, modified, None, None
        d = self.d = Dialog(ctx, T.TITLE, WIDTH, HEIGHT)
        muted = palette(ctx)["muted"]
        d.label("l_file", T.FILE, 8, 8, 24)
        d.label("file", file_name, 34, 8, WIDTH - 42)
        d.label("folder", folder, 34, 18, WIDTH - 42, h=10)
        d.model.getByName("folder").TextColor = muted
        d.label("l_list", T.LIST, 8, 34, WIDTH - 16)
        d.listbox("versions", 8, 46, WIDTH - 16, [T.item_label(v) for v in versions], h=92, help_text=T.LIST,
                  dropdown=False)
        d.label("empty", T.EMPTY, 8, 46, WIDTH - 16, h=60, wrap=True)
        d.label("state", state_text, 8, 142, WIDTH - 16, h=28, wrap=True)
        d.label("hint", T.HINT, 8, 142 if not state_text else 172, WIDTH - 16, h=10)
        d.model.getByName("hint").TextColor = muted
        d.label("confirm", "", 8, 142, WIDTH - 16, h=40, wrap=True)
        y = HEIGHT - 22
        d.button("open", T.OPEN, 8, y, 70, callback=self._open)
        d.button("restore", T.RESTORE, 82, y, 70, callback=self._ask)
        d.button("yes", T.CONFIRM_YES, 8, y, 90, callback=self._restore)
        d.button("no", T.CONFIRM_NO, 102, y, 60, callback=self._cancel)
        d.button("close", T.CLOSE, WIDTH - 78, y, 70, kind=2, default=not versions)
        d.on_ready = self._layout

    def _show(self, **visible):
        for name, shown in visible.items():
            self.d.dialog.getControl(name).setVisible(shown)

    def _layout(self, confirming=False):
        has = bool(self.versions)
        self._show(versions=has, l_list=has, empty=not has, open=has and not confirming,
                   restore=has and not confirming, yes=confirming, no=confirming, confirm=confirming,
                   state=not confirming and bool(self.d.model.getByName("state").Label),
                   hint=has and not confirming)
        if confirming:
            self.d.dialog.getControl("no").setFocus()
        elif has:
            self.d.dialog.getControl("versions").setFocus()

    def _selected(self):
        index = self.d.get("versions")
        return self.versions[index] if 0 <= index < len(self.versions) else None

    def _open(self):
        if self._selected() is not None:
            self.choice = ("open", self._selected())
            self.d.end(OPEN)

    def _ask(self):
        version = self._selected()
        if version is None:
            return
        self.asked = version  # restored on "yes" even if the selection moves meanwhile
        text = T.CONFIRM % T.format_time(version.saved) + (T.CONFIRM_UNSAVED if self.modified else "")
        self.d.model.getByName("confirm").Label = text
        self._layout(confirming=True)

    def _cancel(self):
        self.asked = None
        self._layout()

    def _restore(self):
        if self.asked is not None:
            self.choice = ("restore", self.asked)
            self.d.end(RESTORE)

    def show(self, peer):
        self.d.execute(peer)
        return self.choice


def _state_text(path, has_location, enabled, locked):
    if not has_location:
        return T.NOT_SAVED
    if path is None:
        return T.NOT_LOCAL
    if not enabled:
        return T.DISABLED_LOCKED if locked else T.DISABLED
    return ""


def _error(ctx, peer, code):
    message_box(ctx, peer, T.ERROR_TITLE, T.ERRORS.get(code, T.ERRORS["open"]), error=True)


def _desktop(ctx):
    return ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)


def _load(ctx, url, read_only=False):
    import uno
    args = ()
    if read_only:
        arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        arg.Name, arg.Value = "ReadOnly", True
        args = (arg,)
    return _desktop(ctx).loadComponentFromURL(url, "_blank", 0, args)


def open_view(ctx, peer, version, path):
    import uno
    from .version_restore import RestoreError, view_copy
    try:
        _load(ctx, uno.systemPathToFileUrl(view_copy(version, path)), read_only=True)
    except RestoreError as exc:
        _error(ctx, peer, exc.code)
    except Exception:  # noqa: BLE001 - say it instead of failing silently
        diag_log.exception("previous_versions")
        _error(ctx, peer, "open")


def restore(ctx, model, path, version):
    """Keep the current file, close the document, put `version` in place, open the file again. Runs from the main
    thread's callback queue, after the command that showed the dialog has returned (the document closes itself)."""
    from . import version_capture, version_config
    from .version_files import remove_quietly
    from .version_restore import RestoreError, keep_current, replace, stage_restore
    controller = model.getCurrentController()
    peer = controller.getFrame().getContainerWindow() if controller else None
    url = model.getLocation()
    try:
        keep_current(version_config.store(ctx), path)
        staged = stage_restore(version, path)
    except RestoreError as exc:
        return _error(ctx, peer, exc.code)
    version_capture.discard(path)
    try:
        model.close(True)
    except Exception:  # noqa: BLE001 - CloseVetoException: something still uses the document
        diag_log.exception("previous_versions")
        remove_quietly(staged)
        return _error(ctx, peer, "close")
    failure = None
    try:
        replace(staged, path)
    except RestoreError as exc:
        failure = exc.code
    try:
        document = _load(ctx, url)
        controller = document.getCurrentController() if document is not None else None
        peer = controller.getFrame().getContainerWindow() if controller else None
    except Exception:  # noqa: BLE001 - the file is restored; only reopening failed
        diag_log.exception("previous_versions")
        failure, peer = failure or "reopen", None
    if failure:
        _error(ctx, peer, failure)
    else:
        diag_log.info("previous_versions", "restored a version")


def run(ctx, frame):
    """Command entry point (actions.previous_versions; dispatch has checked that the frame shows a document)."""
    from . import version_config
    from .version_config import document_path
    from .version_store import StoreBusy
    peer = frame.getContainerWindow()
    model = frame.getController().getModel()
    path = document_path(model)
    has_location = bool(model.hasLocation()) if hasattr(model, "hasLocation") else False
    enabled, locked = version_config.load(ctx)
    try:
        versions = version_config.store(ctx).versions(path) if path else []
    except StoreBusy:
        return _error(ctx, peer, "busy")
    name = os.path.basename(path) if path else (model.getTitle() if hasattr(model, "getTitle") else "")
    folder = os.path.dirname(path) if path else ""
    modified = bool(model.isModified()) if hasattr(model, "isModified") else False
    choice = VersionsDialog(ctx, name, folder, versions, _state_text(path, has_location, enabled, locked),
                            modified).show(peer)
    if choice is None:
        return None
    action, version = choice
    if action == "open":
        return open_view(ctx, peer, version, path)
    from .update_ui import on_main_thread
    on_main_thread(ctx, lambda: restore(ctx, model, path, version))
    return None
