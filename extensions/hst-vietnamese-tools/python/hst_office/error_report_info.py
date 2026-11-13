# SPDX-License-Identifier: AGPL-3.0-only
"""What an error report says about this installation, read on the main thread when the dialog opens.

Always in the report (the dialog shows it read-only): HST Office version, build and engine, OS family/version/arch,
office locale and the app (Writer, Sheets, Slides, Start Center...). With "Gửi kèm thông tin chẩn đoán" (ticked by
default, the user can untick it): systemInfo (the lines of Help ▸ About ▸ Copy version info this extension can read,
plus VCL backend, UI scale and the Skia setting) and the last lines of HST's local log (diag_log: hst-office.log in
the user profile, already filtered when written and filtered again here). Nothing here touches documents.
"""
import platform
import re
import sys

from .data_files import load_data
from .error_report_filter import personal_strings, scrub
from .error_report_payload import LOG_BYTES, LOG_LINES, os_info
from . import diag_log

MODULE_APPS = {"com.sun.star.text.TextDocument": "writer", "com.sun.star.text.GlobalDocument": "writer",
               "com.sun.star.text.WebDocument": "writer", "com.sun.star.sheet.SpreadsheetDocument": "calc",
               "com.sun.star.presentation.PresentationDocument": "impress",
               "com.sun.star.drawing.DrawingDocument": "draw", "com.sun.star.formula.FormulaProperties": "math",
               "com.sun.star.sdb.OfficeDatabaseDocument": "base", "com.sun.star.frame.StartModule": "start"}
_VCLPLUG = re.compile(r"libvclplug_(\w+?)lo\.so")


def _config(ctx, path, names):
    import uno
    provider = ctx.ServiceManager.createInstanceWithContext("com.sun.star.configuration.ConfigurationProvider", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "nodepath", path
    node = provider.createInstanceWithArguments("com.sun.star.configuration.ConfigurationAccess", (arg,))
    return {name: node.getPropertyValue(name) for name in names if node.hasByName(name)}


def app_of_module(module):
    return MODULE_APPS.get(module or "", "unknown")


def app_of(ctx, frame):
    try:
        manager = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.ModuleManager", ctx)
        return app_of_module(manager.identify(frame))
    except Exception:  # noqa: BLE001 - no frame (called from a job) or an unknown component
        return "unknown"


def product(ctx):
    info = load_data("release.json")
    engine = ""
    try:
        values = _config(ctx, "/org.openoffice.Setup/Product", ("ooSetupVersionAboutBox", "ooSetupVersionAboutBoxSuffix"))
        engine = "".join(values.values())
    except Exception:  # noqa: BLE001
        diag_log.exception("error_report_info")
    return {"version": info["release"], "build": str(info.get("build", "")), "engine": engine}


def locale(ctx):
    """BCP 47 tag of the office UI language (Tools ▸ Options ▸ Languages), e.g. vi-VN."""
    try:
        tag = _config(ctx, "/org.openoffice.Setup/L10N", ("ooLocale",)).get("ooLocale", "")
    except Exception:  # noqa: BLE001
        tag = ""
    return {"vi": "vi-VN", "en": "en-US", "": "vi-VN"}.get(tag, tag)


def vcl_backend(system=None, maps_path="/proc/self/maps"):
    """Window-system plug-in of this office: win, osx, or the loaded libvclplug_<name>lo.so on Linux (gtk3, kf6...)."""
    system = platform.system() if system is None else system
    if system in ("Windows", "Darwin"):
        return {"Windows": "win", "Darwin": "osx"}[system]
    try:
        with open(maps_path, encoding="utf-8", errors="replace") as handle:
            found = _VCLPLUG.search(handle.read())
        return found.group(1) if found else "gen"
    except OSError:
        return ""


def ui_scale(frame):
    """Display scale of the frame's window in percent of 96 DPI, e.g. "100% (96 DPI)"; "" when unknown."""
    try:
        info = frame.getContainerWindow().getInfo()
        dpi = info.PixelPerMeterX * 0.0254
        return "%d%% (%d DPI)" % (round(dpi / 96 * 100), round(dpi)) if dpi > 0 else ""
    except Exception:  # noqa: BLE001 - no window
        return ""


def system_info_text(fields):
    """The About ▸ Copy version info style lines of the non-empty fields, in a fixed order."""
    order = ("Version", "Engine", "Build ID", "OS", "VCL", "UI scale", "Skia", "Locale", "App", "Python")
    return "\n".join("%s: %s" % (key, fields[key]) for key in order if fields.get(key))


def system_info(ctx, frame, payload):
    fields = {"Version": "%s (%s)" % (payload["product"]["version"], payload["os"]["arch"]),
              "Engine": payload["product"]["engine"], "OS": payload["os"]["version"], "VCL": vcl_backend(),
              "UI scale": ui_scale(frame) if frame is not None else "", "Locale": payload["locale"],
              "App": payload["app"], "Python": platform.python_version()}
    try:
        fields["Build ID"] = ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander").expandMacros(
            "${$BRAND_BASE_DIR/program/" + ("version.ini" if sys.platform == "win32" else "versionrc") + ":buildid}")
    except Exception:  # noqa: BLE001 - macOS keeps versionrc elsewhere: the line is left out
        pass
    try:
        skia = _config(ctx, "/org.openoffice.Office.Common/VCL", ("UseSkia", "ForceSkia", "ForceSkiaGPU"))
        fields["Skia"] = ", ".join("%s=%s" % (k, str(v).lower()) for k, v in sorted(skia.items()))
        fields["Skia"] += skia_in_use(_read_skia_log(ctx))
    except Exception:  # noqa: BLE001
        pass
    return scrub(system_info_text(fields), office_secrets(ctx))


SKIA_KEYS = ("RenderMethod", "DeviceName", "Driver", "Denylisted")


def skia_in_use(text):
    """"; in use: vulkan (device, driver x, denylisted no)" from the office's skia.log (pure); "" without one.

    The office rewrites that log whenever Skia starts, so it shows what really draws: after a crash in the graphics
    driver the office falls back to raster by itself (ForceSkiaGPU=false), which the settings alone cannot show."""
    values = {}
    for line in (text or "").splitlines():
        key, _sep, value = line.partition(":")
        if key.strip() in SKIA_KEYS and value.strip():
            values[key.strip()] = value.strip()
    method = values.get("RenderMethod")
    if not method:
        return ""
    details = [values[k] for k in ("DeviceName",) if k in values]
    details += ["driver %s" % values["Driver"]] if "Driver" in values else []
    details += ["denylisted %s" % values["Denylisted"]] if "Denylisted" in values else []
    return "; in use: %s%s" % (method, " (%s)" % ", ".join(details) if details else "")


def _read_skia_log(ctx):
    """<UserInstallation>/cache/skia.log, written by the office's Skia start-up; "" when missing."""
    import os
    import uno
    subst = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
    user = uno.fileUrlToSystemPath(subst.substituteVariables("$(user)", True))
    try:
        with open(os.path.join(os.path.dirname(user.rstrip("\\/")), "cache", "skia.log"), encoding="utf-8",
                  errors="replace") as handle:
            return handle.read(4096)
    except OSError:
        return ""


def office_secrets(ctx):
    """personal_strings() plus the office's own user, work (Documents) and home folders, as paths and URLs."""
    extra = []
    try:
        import uno
        subst = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
        for variable in ("$(user)", "$(work)", "$(home)", "$(userurl)"):
            url = subst.substituteVariables(variable, False)
            if url:
                extra.append(url)
                if url.startswith("file:"):
                    extra.append(uno.fileUrlToSystemPath(url))
    except Exception:  # noqa: BLE001 - outside the office (tests): the environment strings remain
        pass
    return personal_strings(extra=extra)


def recent_log(secrets):
    """HST's recent local log lines, filtered; "" when there is no log."""
    from . import diag_log
    return scrub(diag_log.recent(LOG_LINES, LOG_BYTES), secrets).strip()


def environment(ctx, frame):
    """(product, os, locale, app) of the always-sent part."""
    return product(ctx), os_info(), locale(ctx), app_of(ctx, frame) if frame is not None else "unknown"
