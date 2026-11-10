# SPDX-License-Identifier: AGPL-3.0-only
"""macOS options regression gate and native Retina owner evidence."""
import time
from support import background, existing, native, wait


def run(e):
    office = e.office
    doc = office.load("private:factory/swriter")
    provider = office.service("com.sun.star.awt.ContainerWindowProvider")
    base = existing("check-hst-options-pages").EXTENSION
    handler = office.service("org.hst.office.vi.OptionsAppearance")
    parent = doc.CurrentController.Frame.ContainerWindow
    import ribbon_os
    office.focus(parent)
    time.sleep(2)
    # The ribbon's own region from the OS accessibility tree (UNO has none for toolkit windows), on screen.
    nodes = ribbon_os.read(e, "appearance")
    frame = ribbon_os.ribbon_frame(nodes)
    e.require(frame is not None, "Đo được vùng ribbon", method="OS accessibility tree")
    dx, dy = ribbon_os.screen_mapper(e, nodes, parent)
    toolbar_box = (frame.x + dx, frame.y + dy + 30, min(frame.w, 900), 90)
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
        # The real Options dialog opened on the Giao diện page and judged by the ink of its page area, as the
        # old-profile scenario does (mac_options_pages.py, 20/20 on this runner).
        from pdf_viewer_uno import signing_props
        from mac_options_pages import INK, page_ink
        expander = office.ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander")
        url = expander.expandMacros(base.replace("vnd.sun.star.expand:", "", 1) + "Appearance.xdl")
        task = background(office.dispatch, doc.CurrentController.Frame, ".uno:OptionsTreeDialog",
                          signing_props(OptionsPageURL=url))
        toolkit = office.service("com.sun.star.awt.Toolkit")
        def dialog():
            windows = [toolkit.getTopWindow(i) for i in range(toolkit.getTopWindowCount())]
            return next((w for w in windows if w.isVisible() and str(getattr(w, "Title", "")).startswith("Tùy chọn")), None)
        window = wait(dialog, 40)
        time.sleep(3)
        window.toFront()
        shot = e.shot("options-page")
        box = window.getPosSize()
        ink = page_ink(shot, (box.X, box.Y, box.X + box.Width, box.Y + box.Height), toolkit.getWorkArea().Width)
        e.require(ink > INK, "Trang Giao diện hiển thị trong Tùy chọn", method="screenshot ink of the page area",
                  ink=round(ink, 4), title=window.Title)
        office.focus(window)
        native("key", "escape")
        task.join(20)
    finally:
        for page in pages:
            if page:
                page.dispose()
        doc.close(True)
