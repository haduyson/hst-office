# SPDX-License-Identifier: AGPL-3.0-only
"""Result dialog of HST ▸ Kiểm tra cập nhật…: up to date / new version (with its actions) / could not check."""
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
    dialog = Dialog(ctx, TEXT["title"], 300, 70)
    dialog.label("message", text, 8, 8, 284, 30, wrap=True)
    x, chosen = 8, []
    if release is not None and not failed:
        ui.STATE["release"] = release
        actions = [("download", 44, lambda: ui.open_url(ctx, ui.release_download(release))),
                   ("notes", 56, lambda: ui.open_url(ctx, release["notes"])),
                   ("skip", 80, lambda: ui.save(ctx, "SkippedVersion", release["version"]))]
        if ui.can_install(ctx, release):
            actions.insert(0, ("install", 60, lambda: chosen.append("install")))
        for name, width, fn in actions:
            dialog.button(name, TEXT[name], x, 48, width, callback=(lambda f=fn: (f(), dialog.end(1))),
                          default=(name == actions[0][0]))
            x += width + 4
    dialog.button("close", TEXT["close"], 252, 48, 40, kind=CANCEL, default=release is None or failed)
    dialog.execute(parent_peer)
    if chosen:  # after the dialog is gone: the installer flow opens its own dialogs
        from .update_install import start
        start(ctx, parent_peer)
