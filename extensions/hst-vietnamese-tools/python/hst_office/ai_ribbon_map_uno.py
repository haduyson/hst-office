# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""UNO side of the ribbon command map (ai_ribbon_map): which notebookbar.ui the app loads, its gettext catalogue in the
UI language and the command labels of theUICommandDescription. Main thread only."""
import gettext
import os

from . import diag_log
from .ai_ribbon_map import APPS, format_map, parse_ribbon

_CACHE = {}


def _ui_language(ctx):
    try:
        provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider",
                                                                ctx)
        from com.sun.star.beans import PropertyValue
        node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess",
                                                    (PropertyValue(Name="nodepath", Value="/org.openoffice.Setup/L10N"),))
        return (node.getPropertyValue("ooLocale") or "").strip()
    except Exception:  # noqa: BLE001 - no setting: the build's default UI language
        return ""


def _system_path(ctx, variable):
    import uno
    subst = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
    return uno.fileUrlToSystemPath(subst.substituteVariables(variable, True))


def ui_file(ctx, module):
    """The notebookbar.ui the ribbon loads: the user's profile copy first, then the installation's."""
    relative = os.path.join("config", "soffice.cfg", "modules", module, "ui", "notebookbar.ui")
    for variable, rel in (("$(user)", relative), ("$(brandbaseurl)", os.path.join("share", relative))):
        try:
            path = os.path.join(_system_path(ctx, variable), rel)
        except Exception:  # noqa: BLE001 - variable unknown in this build
            continue
        if os.path.isfile(path):
            return path
    return None


def catalogue(ctx, domain, language):
    """The gettext catalogue of the module in the UI language, or None (English texts are shown as they are)."""
    try:
        base = _system_path(ctx, "$(brandbaseurl)")
    except Exception:  # noqa: BLE001
        return None
    tags = [language, language.split("-")[0]] if language else []
    for folder in (os.path.join(base, "program", "resource"), os.path.join(base, "Resources", "resource")):
        for tag in tags:
            path = os.path.join(folder, tag, "LC_MESSAGES", domain + ".mo")
            if os.path.isfile(path):
                with open(path, "rb") as handle:
                    return gettext.GNUTranslations(handle)
    return None


def command_labels(ctx, module_id):
    """command_label(".uno:X") from the UI command description of the module, then the generic one."""
    description = ctx.getValueByName("/singletons/com.sun.star.frame.theUICommandDescription")
    containers = []
    for name in (module_id, "com.sun.star.frame.Generic"):
        try:
            containers.append(description.getByName(name))
        except Exception:  # noqa: BLE001 - module without its own commands
            pass

    def label(command):
        for container in containers:
            try:
                if not container.hasByName(command):
                    continue
                props = {p.Name: p.Value for p in container.getByName(command)}
            except Exception:  # noqa: BLE001
                continue
            for key in ("Label", "ContextLabel", "PopupLabel", "TooltipLabel"):
                if props.get(key):
                    return props[key]
        return ""
    return label


def command_map(ctx, doc_kind):
    """The formatted ribbon map of the app, or "" when the ribbon definition cannot be read (the prompt then says
    to use "Tìm tính năng"). Cached per app, UI language and .ui file."""
    app = APPS.get(doc_kind)
    if app is None:
        return ""
    module, domain, module_id, app_name = app
    try:
        language = _ui_language(ctx)
        path = ui_file(ctx, module)
        if path is None:
            return ""
        key = (doc_kind, language, path, os.path.getmtime(path))
        if key not in _CACHE:
            translations = catalogue(ctx, domain, language)

            def translate(context, msgid):
                return translations.pgettext(context, msgid) if translations is not None else msgid
            with open(path, "rb") as handle:
                tabs = parse_ribbon(handle.read(), translate, command_labels(ctx, module_id))
            _CACHE[key] = format_map(app_name, tabs) if tabs else ""
        return _CACHE[key]
    except Exception:  # noqa: BLE001 - the help still works without the map
        diag_log.exception("ai_ribbon_map")
        return ""
