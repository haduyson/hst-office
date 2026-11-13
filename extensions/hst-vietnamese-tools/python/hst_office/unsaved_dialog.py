# SPDX-License-Identifier: AGPL-3.0-only
"""Dialog "Tài liệu chưa lưu" (command org.hst.office.vi:UnsavedDocuments: Start Center button, Tệp tin menu after
Tài liệu gần đây, File panel ▸ Thông tin): the documents closed without saving in the last 7 days, newest first.
"Mở" opens one as a new, untitled document (the kept copy stays until it expires or is deleted), "Xóa" and "Xóa tất
cả" remove kept copies after asking. The files are written by the office itself (unsaved_store explains the layout).
"""
import os
import time

from . import diag_log
from . import unsaved_store as store
from .dialogs import Dialog, message_box, palette

TITLE = "Tài liệu chưa lưu"
LIST = "Tài liệu đã đóng mà không lưu trong 7 ngày qua, mới nhất ở trên:"
EMPTY = ("Không có tài liệu nào.\nKhi bạn đóng một tài liệu đã sửa mà chọn không lưu, HST Office giữ bản tự lưu "
         "cuối cùng của nó ở đây 7 ngày (tổng tối đa 500 MB) trên máy này rồi tự xóa.")
ORIGINAL = "Tệp gốc: %s"
NEVER_SAVED = "Tài liệu này chưa lưu lần nào."
HINT = "Mở: mở thành tài liệu mới, hãy lưu lại bằng Lưu thành."
UNTITLED = "Tài liệu chưa đặt tên"
OPEN, DELETE, DELETE_ALL, CLOSE = "Mở", "Xóa", "Xóa tất cả", "Đóng"
CONFIRM_DELETE = "Xóa vĩnh viễn bản giữ lại của \"%s\"?"
CONFIRM_DELETE_ALL = "Xóa vĩnh viễn mọi tài liệu chưa lưu đang được giữ lại?"
ERROR_OPEN = "Không mở được tài liệu này (có thể bản giữ lại đã bị xóa hoặc hỏng)."
ERROR_DELETE = "Không xóa được (có thể tệp đang được mở). Hãy thử lại sau."
WIDTH, HEIGHT = 300, 200


def display_name(kept):
    """Title of the closed window, else the file name, else "Tài liệu chưa đặt tên" (pure)."""
    if kept.title:
        return kept.title
    path = store.file_path(kept.url)
    return os.path.basename(path) if path else UNTITLED


def item_label(kept, localtime=time.localtime):
    """"Báo cáo quý 3 · tự lưu 14:05 13/11/2026" (pure)."""
    return "%s · tự lưu %s" % (display_name(kept), time.strftime("%H:%M %d/%m/%Y", localtime(kept.saved)))


def origin_label(kept):
    path = store.file_path(kept.url)
    return ORIGINAL % path if path else (ORIGINAL % kept.url if kept.url else NEVER_SAVED)


class UnsavedDialog:
    def __init__(self, ctx, folder):
        self.ctx, self.folder, self.peer, self.kept = ctx, folder, None, store.list_kept(folder)
        d = self.d = Dialog(ctx, TITLE, WIDTH, HEIGHT)
        d.label("l_list", LIST, 8, 8, WIDTH - 16)
        d.listbox("items", 8, 20, WIDTH - 16, [], h=100, help_text=LIST, dropdown=False)
        d.label("empty", EMPTY, 8, 20, WIDTH - 16, h=60, wrap=True)
        d.label("origin", "", 8, 124, WIDTH - 16, h=20, wrap=True)
        d.label("hint", HINT, 8, 148, WIDTH - 16, h=10)
        d.model.getByName("hint").TextColor = palette(ctx)["muted"]
        y = HEIGHT - 22
        d.button("open", OPEN, 8, y, 60, callback=self._open)
        d.button("delete", DELETE, 72, y, 60, callback=self._delete)
        d.button("delete_all", DELETE_ALL, 136, y, 70, callback=self._delete_all)
        d.button("close", CLOSE, WIDTH - 68, y, 60, kind=2)
        d.on_change(("items",), self._selected_changed)
        d.on_ready = self._refresh

    def _selected(self):
        index = self.d.get("items")
        return self.kept[index] if 0 <= index < len(self.kept) else None

    def _selected_changed(self):
        kept = self._selected()
        self.d.model.getByName("origin").Label = origin_label(kept) if kept else ""

    def _refresh(self):
        self.kept = store.list_kept(self.folder)
        has = bool(self.kept)
        import uno
        uno.invoke(self.d.model.getByName("items"), "setPropertyValue",
                   ("StringItemList", uno.Any("[]string", tuple(item_label(k) for k in self.kept))))
        for name, shown in (("items", has), ("l_list", has), ("empty", not has), ("origin", has), ("hint", has),
                            ("open", has), ("delete", has), ("delete_all", has)):
            self.d.dialog.getControl(name).setVisible(shown)
        if has:
            self.d.select("items", 0)
            self._selected_changed()
            self.d.dialog.getControl("items").setFocus()

    def _open(self):
        kept = self._selected()
        if kept is None:
            return
        try:
            open_copy(self.ctx, kept)
            self.d.end(1)
        except Exception:  # noqa: BLE001 - say it instead of failing silently
            diag_log.exception("unsaved_documents")
            message_box(self.ctx, self.d.dialog.getPeer(), TITLE, ERROR_OPEN, error=True)

    def _delete(self):
        kept = self._selected()
        if kept is not None and message_box(self.ctx, self.d.dialog.getPeer(), TITLE,
                                            CONFIRM_DELETE % display_name(kept), ask=True):
            if not store.delete(kept):
                message_box(self.ctx, self.d.dialog.getPeer(), TITLE, ERROR_DELETE, error=True)
            self._refresh()

    def _delete_all(self):
        if message_box(self.ctx, self.d.dialog.getPeer(), TITLE, CONFIRM_DELETE_ALL, ask=True):
            removed = store.delete_all(self.folder)
            diag_log.info("unsaved_documents", "deleted %d kept documents" % removed)
            self._refresh()

    def show(self, peer):
        self.d.execute(peer)


def open_copy(ctx, kept):
    """Open the kept copy as a new untitled document (AsTemplate): saving never writes into the store."""
    import uno
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "AsTemplate", True
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    if desktop.loadComponentFromURL(uno.systemPathToFileUrl(kept.path), "_default", 0, (arg,)) is None:
        raise RuntimeError("document not loaded")


def user_dir(ctx):
    import uno
    subst = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
    return uno.fileUrlToSystemPath(subst.substituteVariables("$(user)", True))


def run(ctx, frame):
    """Command entry point (dispatch.ON_USE): works with or without a document."""
    peer = frame.getContainerWindow() if frame is not None else None
    UnsavedDialog(ctx, store.store_dir(user_dir(ctx))).show(peer)
