# SPDX-License-Identifier: AGPL-3.0-only
"""Window helpers of "Cập nhật ngay" (update_install): the question dialog, the window that parents a message, and
where this installation lives. update_install re-exports them; tests patch them there."""
import os

import uno


def _ask(ctx, peer, title, text, buttons, text_height=28):
    """Modal question; `buttons` = [(label, key)]; returns the key of the clicked button or None (closed)."""
    from .dialogs import CANCEL, Dialog
    top = 16 + text_height
    dialog = Dialog(ctx, title, 300, top + 20)
    dialog.label("message", text, 8, 8, 284, text_height, wrap=True)
    keys, x = [], 8
    for index, (label, key) in enumerate(buttons):
        width = max(44, 8 + 5 * len(label))
        last = index == len(buttons) - 1
        dialog.button("b%d" % index, label, 292 - width if last else x, top, width, kind=CANCEL if last else None,
                      default=index == 0, callback=None if last else (lambda k=key: (keys.append(k), dialog.end(1))))
        x += width + 4
    if dialog.execute(peer):
        return keys[0] if keys else None
    return buttons[-1][1]


def office_paths(ctx, system):
    """(soffice executable, running app bundle or None) of this installation."""
    base = uno.fileUrlToSystemPath(ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander").expandMacros("$BRAND_BASE_DIR"))
    base = os.path.normpath(base.replace("vnd.sun.star.expand:", ""))
    if system == "Darwin":
        bundle = base  # BRAND_BASE_DIR is <name>.app/Contents: climb to the bundle itself
        while not bundle.endswith(".app") and os.path.dirname(bundle) != bundle:
            bundle = os.path.dirname(bundle)
        return os.path.join(bundle, "Contents", "MacOS", "soffice"), bundle
    return os.path.join(base, "program", "soffice.exe" if system == "Windows" else "soffice"), None


def needs_password(bundle, writable=None):
    """macOS: the helper must ask for the administrator password to replace the app (its folder or the bundle is not
    writable by this user; same test as the helper's writable_target), so the question says so before the office
    closes. False elsewhere (bundle None) and for a read-only .dmg or translocated copy, which goes to /Applications."""
    if not bundle:
        return False
    from . import mac_app_location
    target = mac_app_location.update_target(bundle)
    writable = writable or (lambda path: os.access(path, os.W_OK))
    return not (writable(os.path.dirname(target)) and (not os.path.exists(target) or writable(target)))


def _live_peer(ctx, peer):
    """The window to parent a message to: the clicked one may have closed while the office tried to quit."""
    try:
        if peer is not None and peer.isVisible():
            return peer
    except Exception:  # noqa: BLE001 - disposed
        pass
    try:
        frame = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).getCurrentFrame()
        return frame.getContainerWindow() if frame else None
    except Exception:  # noqa: BLE001
        return None
