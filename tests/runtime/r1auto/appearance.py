# SPDX-License-Identifier: AGPL-3.0-only
"""macOS options regression gate and native Retina owner evidence."""
import time
from access import box, click, named, snapshot
from support import background, existing, native, wait


def run(e):
    office = e.office
    doc = office.load("private:factory/swriter")
    provider = office.service("com.sun.star.awt.ContainerWindowProvider")
    base = existing("check-hst-options-pages").EXTENSION
    handler = office.service("org.hst.office.vi.OptionsAppearance")
    parent = doc.CurrentController.Frame.ContainerWindow
    from com.sun.star.accessibility.AccessibleRole import TOOL_BAR
    office.focus(parent)
    toolbar = wait(lambda: next((n for n in snapshot(office) if n.getAccessibleRole() == TOOL_BAR
                                and box(parent)[1] + 40 < box(n)[1] < box(parent)[1] + 230
                                and box(n)[2] > 50), None))
    toolbar_box = box(toolbar)
    pages = []
    try:
        apps = provider.createContainerWindow(base + "DefaultApps.xdl", "", parent,
                                              office.service("org.hst.office.vi.OptionsPage"))
        pages.append(apps)
        e.require(apps is not None and apps.getControl("defaultApps") is not None,
                  "Trang Mở tài liệu có điều khiển")
        look = provider.createContainerWindow(base + "Appearance.xdl", "", parent, handler)
        pages.append(look)
        e.require(look is not None and look.getControl("modern") is not None,
                  "Trang Giao diện có điều khiển")
        handler.callHandlerMethod(look, "initialize", "external_event")
        # appearance_options.py: Cổ điển writes "auto" (the default), Hiện đại "hst_modern".
        for name, expected in (("classic", "auto"), ("modern", "hst_modern")):
            look.getControl("modern").setState(name == "modern")
            look.getControl("classic").setState(name == "classic")
            handler.callHandlerMethod(look, "ok", "external_event")
            actual = office.config("/org.openoffice.Office.Common/Misc", "SymbolStyle")
            e.require(actual == expected, "Đổi biểu tượng không khởi động lại", expected=expected, actual=actual)
            time.sleep(2)
            e.review("Độ sắc nét biểu tượng ở tỉ lệ Retina 2×: " + ("Hiện đại" if name == "modern" else "Cổ điển"), name)
        repaint = native("icon-change", e.out / "classic.png", e.out / "modern.png", *toolbar_box)
        e.require(repaint["changed_pixels"] > 20, "Biểu tượng vẽ lại ngay trong cùng phiên", **repaint)
        background(office.dispatch, doc.CurrentController.Frame, ".uno:OptionsTreeDialog")
        root = wait(lambda: named(office, "HST Office"))
        click(root[-1])
        native("key", "down")
        page = wait(lambda: named(office, "Giao diện"))
        click(page[-1])
        e.require(bool(wait(lambda: named(office, "Hiện đại"))), "Trang Giao diện hiển thị trong Tùy chọn")
        e.shot("options-page")
        native("key", "escape")
    finally:
        for page in pages:
            if page:
                page.dispose()
        doc.close(True)
