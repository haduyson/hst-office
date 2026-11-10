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
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        def print_window():
            return next((w for w in desktop.windows() if w.window_text().strip() in {"In", "Print"}), None)
        window = wait(print_window)
        # An actual Windows virtual printer: never assume printer index zero.
        chosen = None
        for combo in window.descendants(control_type="ComboBox"):
            choices = combo.item_texts()
            printer = next((name for name in choices if name.endswith("Print to PDF")), None)
            if printer:
                chosen = combo, printer
                break
        if chosen is None:
            raise RuntimeError("Runner thiếu máy in PDF hệ thống hoặc không đọc được danh sách máy in")
        chosen[0].select(chosen[1])
        button = next(b for b in window.descendants(control_type="Button")
                      if b.window_text().replace("&", "") in {"In", "Print", "OK"})
        button.click_input()
        def save_window():
            return next((w for w in desktop.windows() if w.child_window(auto_id="1001", control_type="Edit").exists()), None)
        save = wait(save_window)
        save.child_window(auto_id="1001", control_type="Edit").set_edit_text(str(target))
        save.child_window(auto_id="1", control_type="Button").click_input()
    elif platform.system() == "Darwin":
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
        # The save panel runs out of process on macOS 15 (absent from the app's AX tree, run 42897049569):
        # keys as a user types them. The name field opens focused with the name selected; then Go To Folder.
        keyboard(text=target.stem)
        screenshot(target.with_name("save-1-name.png"))
        from Quartz import CGEventCreateKeyboardEvent, CGEventSetFlags, CGEventPost, kCGHIDEventTap
        for down in (True, False):
            event = CGEventCreateKeyboardEvent(None, 5, down)  # Cmd+Shift+G
            CGEventSetFlags(event, (1 << 20) | (1 << 17))
            CGEventPost(kCGHIDEventTap, event)
        time.sleep(1)
        keyboard(text=str(target.parent))
        keyboard(["enter"])
        time.sleep(1.5)
        screenshot(target.with_name("save-2-folder.png"))
        keyboard(["enter"])  # Lưu, the panel's default button
        time.sleep(2)
        screenshot(target.with_name("save-3-saved.png"))


def finish(target):
    wait(lambda: target.exists() and target.stat().st_size > 0, 45)
    previous = -1
    for _ in range(20):
        size = target.stat().st_size
        if size == previous:
            return dict(path=str(target), bytes=size)
        previous = size
        time.sleep(0.5)
    raise TimeoutError("Tệp in chưa ghi xong")
