# SPDX-License-Identifier: AGPL-3.0-only
"""Default apps: "Mở tài liệu văn phòng bằng HST Office?" at start-up, in Tùy chọn and in the HST menu.

Show-once rule (owner 2026-11-06): asked on a start after the welcome dialog; "Để sau" asks again after SNOOZE_DAYS,
at most MAX_ASKS times; "Đồng ý" or a registration found on the machine ends the question. State:
/org.hasontech.hstoffice.DefaultApps (defaultapps.xcs), per user; an administrator can lock Ask to false.

Per-OS actions (the user's own choice, never at install time alone):
  * Linux: `xdg-mime default vn.hasontech.hstoffice-<module>.desktop <types>` for the document types the HST
    launchers declare (default_apps_linux.py);
  * macOS: LaunchServices LSSetDefaultRoleHandlerForContentType for the UTIs the HST bundle declares;
  * Windows: apps cannot set defaults themselves; Settings opens at HST Office's default-apps page. The Windows
    installer checkbox writes DefaultApps\\ChosenAtInstall = 1, which counts as answered. The upstream start-up
    notice about file types is turned off (StartupDefaults.xcu: Common/Misc/PerformFileExtCheck = false), so only
    this question is ever asked.
Product rule: the text names file types only ("tài liệu văn bản (.doc, .docx)"), never another vendor's product.
"""
import time
import traceback

from . import default_apps_os as osx

CONFIG_PATH = "/org.hasontech.hstoffice.DefaultApps"
SNOOZE_DAYS = 14
MAX_ASKS = 3
DAY = 86400
TITLE = "HST Office"
QUESTION = "Mở tài liệu văn phòng bằng HST Office?"
ACCEPT, LATER = "Đồng ý", "Để sau"
TYPES_NOTE = ("Gồm tài liệu văn bản (.doc, .docx, .odt), bảng tính (.xls, .xlsx, .ods) và bản trình chiếu "
              "(.ppt, .pptx, .odp).")
DONE_TEXT = "HST Office đã được đặt để mở các tài liệu văn phòng."
WINDOWS_TEXT = ("Trong cửa sổ Cài đặt vừa mở, chọn HST Office cho các loại tệp .doc, .docx, .xls, .xlsx, .ppt, "
                ".pptx, .odt, .ods và .odp.")
FAILED_TEXT = "Không đặt được HST Office để mở tài liệu văn phòng: %s"
DEFAULT_STATE = {"Ask": True, "Asked": 0, "LastAsked": 0, "Done": False}


def should_ask(state, now, registered):
    """True when the start-up question is due (pure). `registered`: HST already opens the office types."""
    if not state.get("Ask", True) or state.get("Done") or registered:
        return False
    asked = int(state.get("Asked", 0))
    if asked >= MAX_ASKS:
        return False
    return asked == 0 or int(now) - int(state.get("LastAsked", 0)) >= SNOOZE_DAYS * DAY


def after_answer(state, accepted, now):
    """New state after the start-up question (pure): Đồng ý ends it; Để sau (or Esc) snoozes, counted."""
    new = dict(state)
    new["Asked"] = int(state.get("Asked", 0)) + 1
    new["LastAsked"] = int(now)
    if accepted:
        new["Done"] = True
    return new


def _access(ctx, writable):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", CONFIG_PATH
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def load_state(ctx):
    try:
        node = _access(ctx, False)
        return {key: node.getPropertyValue(key) for key in DEFAULT_STATE}
    except Exception:  # noqa: BLE001 - schema missing: never ask rather than ask every start
        traceback.print_exc()
        return dict(DEFAULT_STATE, Ask=False)


def save_state(ctx, state):
    try:
        node = _access(ctx, True)
        for key in ("Asked", "LastAsked", "Done"):
            node.setPropertyValue(key, state[key])
        node.commitChanges()
    except Exception:  # noqa: BLE001 - a failing write must not break the start
        traceback.print_exc()


def make_default(ctx):
    """Run the action of this OS. Returns (ok, text to show or "")."""
    try:
        ok, kind = osx.make_default(osx.system())
        return ok, WINDOWS_TEXT if kind == "settings" else ""
    except Exception as exc:  # noqa: BLE001 - reported to the user, never raised into the UI thread
        traceback.print_exc()
        return False, FAILED_TEXT % exc


def _ask(ctx, parent_peer):
    from .dialogs import message_box
    return message_box(ctx, parent_peer, TITLE, QUESTION + "\n" + TYPES_NOTE, ask=True, buttons=(ACCEPT, LATER))


def _report(ctx, parent_peer, ok, detail, quiet_success):
    from .dialogs import message_box
    if not ok:
        message_box(ctx, parent_peer, TITLE, detail or FAILED_TEXT % "", error=True)
    elif detail:
        message_box(ctx, parent_peer, TITLE, detail)
    elif not quiet_success:
        message_box(ctx, parent_peer, TITLE, DONE_TEXT)


def offer_at_startup(ctx, parent_peer=None, now=None, ask=None, act=None):
    """The start-up step: True when the question was shown (one modal per start). `ask`/`act` are test seams."""
    now = int(time.time() if now is None else now)
    if osx.system() == "Darwin" and not osx.mac_in_applications():
        return False  # the move question handles this copy first; asking now would register the wrong one
    state = load_state(ctx)
    if not should_ask(state, now, False):
        return False
    try:
        registered = osx.is_registered(osx.system())
    except Exception:  # noqa: BLE001 - unknown state: ask, the action is harmless when already set
        traceback.print_exc()
        registered = False
    if registered:
        save_state(ctx, dict(state, Done=True))
        return False
    accepted = bool((ask or _ask)(ctx, parent_peer))
    save_state(ctx, after_answer(state, accepted, now))
    if accepted:
        ok, detail = (act or make_default)(ctx)
        _report(ctx, parent_peer, ok, detail, quiet_success=True)
    return True


def run_from_menu(ctx, parent_peer=None):
    """HST menu and Tùy chọn button "Dùng HST Office để mở tài liệu văn phòng": acts without the snooze rule."""
    ok, detail = make_default(ctx)
    if ok:
        state = load_state(ctx)
        save_state(ctx, dict(state, Done=True))
    _report(ctx, parent_peer, ok, detail, quiet_success=False)
    return ok
