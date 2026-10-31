# SPDX-License-Identifier: AGPL-3.0-only
"""UI language preference and session restart; pure resolution works without UNO."""
from .data_files import load_locale

COMMANDS = {"UILanguageVi": "vi", "UILanguageEn": "en-US", "UILanguageSystem": ""}
CONFIG_PATH = "/org.openoffice.Office.Linguistic/General"


def _primary(tag):
    return tag.replace("_", "-").split("-", 1)[0].lower()


def resolve(raw, installed):
    """Prefer exact tags, then case-insensitive tags, then the first same-language tag."""
    if not raw:
        return ""
    if raw in installed:
        return raw
    for tag in installed:
        if tag.lower() == raw.lower():
            return tag
    return next((tag for tag in installed if _primary(tag) == _primary(raw)), "")


def current_choice(raw, installed):
    return {"vi": "vi", "en": "en-US"}.get(_primary(resolve(raw, installed)), "")


def _node(ctx, path, writable=False):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    kind = "ConfigurationUpdateAccess" if writable else "ConfigurationAccess"
    return provider.createInstanceWithArguments("com.sun.star.configuration." + kind, (arg,))


def read_state(ctx):
    raw = _node(ctx, CONFIG_PATH).getPropertyValue("UILocale")
    installed = tuple(_node(ctx, "/org.openoffice.Setup/Office/InstalledLocales").getElementNames())
    locked = False
    try:
        from com.sun.star.beans.PropertyAttribute import READONLY
        # Read access itself is read-only; only update access exposes the administrator's lock.
        prop = _node(ctx, CONFIG_PATH, True).getPropertySetInfo().getPropertyByName("UILocale")
        locked = bool(prop.Attributes & READONLY)
    except Exception:  # noqa: BLE001 - unknown lock state: let the write report any failure
        pass
    return {"raw": raw, "installed": installed, "locked": locked}


def write_choice(ctx, value):
    node = _node(ctx, CONFIG_PATH, True)
    node.setPropertyValue("UILocale", value)
    node.commitChanges()


def request_restart(ctx):
    """The core owns document backup, shutdown, restart and session recovery."""
    import uno
    url = uno.createUnoStruct("com.sun.star.util.URL")
    url.Complete = "vnd.sun.star.autorecovery:/doSessionRestart"
    transformer = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx)
    _, url = transformer.parseStrict(url)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "DispatchAsynchron", True
    ctx.getValueByName("/singletons/com.sun.star.frame.theAutoRecovery").dispatch(url, (arg,))


def run(ctx, frame, command):
    from .dialogs import message_box
    strings = load_locale("vi")["uiLanguage"]
    peer = frame.getContainerWindow() if frame else None
    state = read_state(ctx)
    target = COMMANDS[command]
    if state["locked"]:
        message_box(ctx, peer, strings["title"], strings["locked"])
        return
    raw = state["raw"]
    # An unresolvable preference checks System, but selecting it must still clear the stored value.
    if current_choice(raw, state["installed"]) == target and (raw == "") == (target == ""):
        message_box(ctx, peer, strings["title"], strings["selected"].format(name=strings["names"][target]))
        return
    try:
        write_choice(ctx, target)
    except Exception as exc:  # noqa: BLE001 - show configuration failures before offering restart
        message_box(ctx, peer, strings["title"], strings["saveError"].format(error=exc), error=True)
        return
    if message_box(ctx, peer, strings["title"], strings["restart"], ask=True,
                   buttons=(strings["restartNow"], strings["later"])):
        request_restart(ctx)


def status(ctx, command):
    try:
        state = read_state(ctx)
        return not state["locked"], current_choice(state["raw"], state["installed"]) == COMMANDS[command]
    except Exception:  # noqa: BLE001 - menu remains usable if configuration cannot be read
        return True, False
