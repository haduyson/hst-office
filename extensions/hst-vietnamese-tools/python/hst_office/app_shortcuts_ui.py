# SPDX-License-Identifier: AGPL-3.0-only
"""Tùy chọn ▸ HST Office ▸ Mở tài liệu ▸ "Lối tắt ứng dụng" (dialogs/DefaultApps.xdl, options_page.py).

macOS: "Thêm vào Dock" pins HST Writer, HST Sheets, HST Slides, HST Draw and HST PDF, and "Gỡ biểu tượng ứng dụng" / "Thêm lại biểu tượng
ứng dụng" remove or restore the five launchers in /Applications (mac_app_launchers_ui); Linux: "Tạo lối tắt trên màn
hình nền". They ask first and change nothing on "Để sau". On Windows the installer creates the shortcuts, so the
section is hidden.
"""
import platform

from . import app_shortcuts as shortcuts
from . import diag_log

TITLE = "Lối tắt ứng dụng"
NAMES = "HST Writer, HST Sheets và HST Slides"
MAC_NAMES = "HST Writer, HST Sheets, HST Slides, HST Draw và HST PDF"
LATER = "Để sau"
TEXTS = {
    "Darwin": {
        "note": "%s có trong Launchpad và thư mục Ứng dụng; ghim chúng vào Dock để mở thẳng từng ứng dụng." % MAC_NAMES,
        "button": "Thêm vào Dock",
        "ask": "Thêm %s vào Dock?\nDock sẽ khởi động lại trong giây lát." % MAC_NAMES,
        "done": "Đã thêm %s vào Dock." % MAC_NAMES,
        "already": "%s đã có trong Dock." % MAC_NAMES,
    },
    "Linux": {
        "note": "Đặt lối tắt %s lên màn hình nền." % NAMES,
        "button": "Tạo lối tắt trên màn hình nền",
        "ask": "Tạo lối tắt %s trên màn hình nền?" % NAMES,
        "done": "Đã tạo lối tắt %s trên màn hình nền.\nNếu biểu tượng chưa mở được, nhấp chuột phải vào nó và chọn "
                "cho phép khởi chạy." % NAMES,
    },
}
MOVE_FIRST = "Hãy chuyển HST Office vào thư mục Ứng dụng (Applications) rồi thử lại."
FAILED = "Không tạo được lối tắt: %s"
CONTROLS = ("shortcutsHeading", "shortcutsNote", "appShortcuts")
MAC_CONTROLS = ("removeLaunchers", "addLaunchers")  # the app icons in /Applications: macOS only


def texts(system=None):
    """The texts of this OS, or None where the section is hidden (Windows and others)."""
    return TEXTS.get(system or platform.system())


def configure_page(window, system=None):
    """Label the section's button for this OS, or hide the section."""
    system = system or platform.system()
    text = texts(system)
    for name in CONTROLS + MAC_CONTROLS:
        control = window.getControl(name)
        if control is None:
            continue
        control.setVisible(text is not None and (name in CONTROLS or system == "Darwin"))
        if text is not None and name == "appShortcuts":
            control.getModel().Label = text["button"]
            control.getModel().HelpText = text["note"]
        elif text is not None and name == "shortcutsNote":
            control.getModel().Label = text["note"]


def _message(ctx, peer, text, ask=False, button=None):
    from .dialogs import message_box
    return message_box(ctx, peer, TITLE, text, ask=ask, buttons=(button, LATER) if ask else None)


def _mac(ctx, peer, text):
    from .mac_app_location import MOVABLE, _running_bundle, locate
    bundle = _running_bundle(ctx)
    if locate(bundle)["kind"] in MOVABLE:  # a .dmg, Downloads or translocated copy: the tiles would not last
        return _message(ctx, peer, MOVE_FIRST)
    _launchers, missing = shortcuts.dock_status(bundle)
    if not missing:
        return _message(ctx, peer, text["already"])
    if not _message(ctx, peer, text["ask"], ask=True, button=text["button"]):
        return False
    shortcuts.add_to_dock(missing)
    return _message(ctx, peer, text["done"])


def _linux(ctx, peer, text):
    launchers = shortcuts.installed_launchers()
    if not _message(ctx, peer, text["ask"], ask=True, button=text["button"]):
        return False
    shortcuts.copy_to_desktop(launchers, shortcuts.desktop_dir())
    return _message(ctx, peer, text["done"])


def _guarded(ctx, peer, action):
    """action() with every failure shown to the user and logged, never raised into the options dialog."""
    from .mac_app_launchers import LauncherError
    try:
        return action()
    except (shortcuts.ShortcutError, LauncherError) as exc:
        diag_log.exception("app_shortcuts")
        return _message(ctx, peer, FAILED % exc)
    except Exception as exc:  # noqa: BLE001 - never raise into the options dialog
        diag_log.exception("app_shortcuts")
        try:
            return _message(ctx, peer, FAILED % exc)
        except Exception:  # noqa: BLE001 - not even the message could be shown
            diag_log.exception("app_shortcuts")
            return False


def run(ctx, peer=None, system=None):
    """The button's action. Never raises: every failure is shown to the user and logged."""
    system = system or platform.system()
    text = texts(system)
    if text is None:
        return False
    return _guarded(ctx, peer, lambda: (_mac if system == "Darwin" else _linux)(ctx, peer, text))


def launcher_icons(ctx, peer=None, add=False, system=None):
    """"Thêm lại biểu tượng ứng dụng" (add) or "Gỡ biểu tượng ứng dụng" on macOS. Never raises."""
    if (system or platform.system()) != "Darwin":
        return False
    from . import mac_app_launchers_ui as icons
    action = icons.add_from_options if add else icons.remove_from_options

    def message(text, ask=False, button=None):
        return _message(ctx, peer, text, ask=ask, button=button)
    return _guarded(ctx, peer, lambda: action(ctx, message))
