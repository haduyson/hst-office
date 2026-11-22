# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Result dialog of HST ▸ Kiểm tra cập nhật…: up to date / new version (with its actions) / could not check.

With a new version the buttons are Cập nhật ngay (when allowed), Tải về, Xem điểm mới, Bỏ qua phiên bản này and
Để sau, which closes the dialog without skipping the version (Esc does the same); otherwise Đóng."""
from . import update_config
from . import update_ui as ui
from .update_texts import texts


def show_result(ctx, parent_peer, release, installed, failed):
    from .dialogs import CANCEL, Dialog
    TEXT = texts(ctx)
    if failed:
        text = TEXT["failed"]
    elif release is None:
        text = TEXT["uptodate"] % installed
    else:
        text = "%s\n%s" % (TEXT["new"] % release["version"], TEXT["current"] % installed)
    prefs, locked = update_config.load(ctx)
    from .update_handler import set_available, skip_release
    chosen, actions = [], []
    if release is not None and not failed:
        actions = [("download", 44, lambda: ui.open_url(ctx, ui.release_download(release))),
                   ("notes", 56, lambda: ui.open_url(ctx, release["notes"])),
                   ("skip", 80, lambda: skip_release(ctx, release["version"]))]
        if ui.can_install(ctx, release):
            actions.insert(0, ("install", 60, lambda: chosen.append("install")))
    # a new version: "Để sau" closes like "Đóng" (nothing skipped; the next automatic check announces it again)
    close_name, close_width = ("later", 40) if actions else ("close", 40)
    close_x = max(252, 8 + sum(width + 4 for _name, width, _fn in actions))
    width = close_x + close_width + 8
    dialog = Dialog(ctx, TEXT["title"], width, 86)
    dialog.label("message", text, 8, 8, width - 16, 30, wrap=True)
    auto = dialog.check("autocheck", TEXT["autocheck"], 8, 44, width - 16, state=prefs["AutoCheck"])
    if "AutoCheck" in locked:  # finalized by the administrator (.xcd, registry, macOS profile, policy package)
        auto.Enabled, auto.HelpText = False, TEXT["locked"]
    else:
        dialog.on_change(["autocheck"], lambda: ui.save(ctx, "AutoCheck", dialog.get("autocheck")))
    if not failed:  # the File panel entry and the File tab dot follow the answer (None: up to date)
        set_available(release)
    if actions:
        ui.STATE["release"] = release
    x = 8
    for name, button_width, fn in actions:
        dialog.button(name, TEXT[name], x, 64, button_width, callback=(lambda f=fn: (f(), dialog.end(1))),
                      default=(name == actions[0][0]))
        x += button_width + 4
    dialog.button(close_name, TEXT[close_name], close_x, 64, close_width, kind=CANCEL, default=not actions)
    dialog.execute(parent_peer)
    if chosen:  # after the dialog is gone: the installer flow opens its own dialogs
        from .update_install import start
        start(ctx, parent_peer)
