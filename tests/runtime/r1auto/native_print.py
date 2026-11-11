# SPDX-License-Identifier: AGPL-3.0-only
"""Print through the platform's real PDF destination, without exporting the source."""
from pathlib import Path
import time
from support import wait
from native import keyboard, screenshot


def save_print(target):
    import platform
    target = Path(target)
    if target.exists():
        raise RuntimeError("Tệp in đã tồn tại")
    screenshot(target.with_name("print-dialog.png"))
    if platform.system() == "Windows":
        windows_print(target)
    elif platform.system() == "Darwin":
        saved_copy(target).unlink(missing_ok=True)  # an old file must not pass for this print
        try:
            mac_print(target)
        except Exception:
            import json
            from native_tree import mac_nodes
            target.with_name("print-tree.log").write_text(json.dumps(mac_nodes(3000), ensure_ascii=False))
            raise
    else:
        raise RuntimeError("Đường in native chỉ chạy trên Windows/macOS")
    return finish(target)


def windows_print(target):
    """The office's print dialog: Microsoft Print to PDF, In, then the driver's save dialog."""
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")

    def windows():
        # UI Automation shows an owned window (a dialog) under its owner, not under the desktop: the office's
        # print dialog is a child of the document window there (r1-auto Windows run 42959783025, W12: the
        # dialog was on screen for 60 s and absent from the desktop's windows).
        for top in desktop.windows():
            yield top
            try:
                yield from top.children(control_type="Window")
            except Exception:  # noqa: BLE001 - a window that went away while listed
                continue

    def print_window():
        return next((w for w in windows() if w.window_text().strip() in {"In", "Print"}), None)
    try:
        window = wait(print_window, 60)
    except TimeoutError:
        # what is on screen instead of the print dialog (a message box, a hidden dialog, nothing)
        screenshot(target.with_name("print-timeout.png"))
        shown = [(w.window_text(), w.class_name(), w.process_id()) for w in windows()]
        target.with_name("print-timeout.log").write_text(repr(shown), encoding="utf-8")
        raise RuntimeError("Không thấy hộp thoại In sau 60 giây (print-timeout.png, print-timeout.log)")
    try:
        # An actual Windows virtual printer: never assume printer index zero.
        # (the UI Automation ComboBoxWrapper of pywinauto 0.6.9 lists its items with texts(), not item_texts())
        chosen = None
        for combo in window.descendants(control_type="ComboBox"):
            try:
                shown = combo.selected_text() or combo.window_text() or ""
            except Exception:  # noqa: BLE001 - a combo without a selection pattern
                shown = ""
            if shown.endswith("Print to PDF"):  # the runner's default printer
                chosen = combo, None
                break
            printer = next((name for name in combo.texts() if name.endswith("Print to PDF")), None)
            if printer:
                chosen = combo, printer
                break
        if chosen is None:
            raise RuntimeError("Runner thiếu máy in PDF hệ thống hoặc không đọc được danh sách máy in")
        if chosen[1]:
            chosen[0].select(chosen[1])
        button = next(b for b in window.descendants(control_type="Button")
                      if b.window_text().replace("&", "") in {"In", "Print", "OK"})
        button.click_input()
    except Exception:
        screenshot(target.with_name("print-dialog-failed.png"))
        window.close()  # Hủy: the document must not be closed under its open print dialog
        raise

    def save_window():
        return next((w for w in windows() if w.child_window(auto_id="1001", control_type="Edit").exists()), None)
    save = wait(save_window)
    save.child_window(auto_id="1001", control_type="Edit").set_edit_text(str(target))
    save.child_window(auto_id="1", control_type="Button").click_input()


def saved_copy(target):
    """Where the macOS save panel's default folder puts the file."""
    return Path.home() / "Documents" / target.name


def mac_print(target):
    """macOS print sheet: PDF ▸ Save as PDF, then the save panel; its AX tree is dumped on failure."""
    if True:
        import ApplicationServices as ax
        from mac_access import applications, attribute, nodes, press
        app = wait(lambda: next(iter(applications()), None))
        # The panel's "PDF" is a label button plus an AXMenuButton; only the menu button opens the PDF menu
        # (print-tree.log of r1-auto macOS run 42892534997).
        def pdf_menu():
            found = [n for n in nodes(app) if attribute(n, "AXTitle") == "PDF" or attribute(n, "AXDescription") == "PDF"]
            return next((n for n in found if attribute(n, "AXRole") == "AXMenuButton"), None)
        pdf_button = wait(pdf_menu)
        ax.AXUIElementPerformAction(pdf_button, "AXPress")
        item = wait(lambda: next((n for n in nodes(app) if attribute(n, "AXTitle") in
                                 {"Save as PDF", "Save as PDF…", "Lưu thành PDF", "Lưu thành PDF…",
                                  "Lưu dưới dạng PDF", "Lưu dưới dạng PDF…"}), None))
        ax.AXUIElementPerformAction(item, "AXPress")
        time.sleep(2)
        # The save panel runs out of process on macOS 15 (absent from the app's AX tree, run 42897049569) and its
        # Go To Folder shortcut did not open (run 42900251744): type the name as a user does, save to the panel's
        # default folder (Tài liệu), then move the file to the evidence path.
        keyboard(text=target.stem)
        screenshot(target.with_name("save-1-name.png"))
        keyboard(["enter"])  # Lưu, the panel's default button
        time.sleep(2)
        screenshot(target.with_name("save-2-saved.png"))


def finish(target):
    import platform
    if platform.system() == "Darwin":
        copy = saved_copy(target)
        wait(lambda: copy.exists() and copy.stat().st_size > 0, 45)
        time.sleep(2)
        copy.replace(target)
    wait(lambda: target.exists() and target.stat().st_size > 0, 45)
    previous = -1
    for _ in range(20):
        size = target.stat().st_size
        if size == previous:
            return dict(path=str(target), bytes=size)
        previous = size
        time.sleep(0.5)
    raise TimeoutError("Tệp in chưa ghi xong")
