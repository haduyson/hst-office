# SPDX-License-Identifier: AGPL-3.0-only
"""macOS probe driver (bundled Python, UNO on port 2002) for the start-up questions and the HST option pages.
  startup-chain-probe.py state <out.json> <extension python dir>   what the start-up chain sees in this office
  startup-chain-probe.py options <out.json> <extension python dir>  builds both HST option pages and dumps them
Evidence only."""
import json
import sys
import time
import traceback

import uno


def connect():
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(90):
        try:
            return resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        except Exception:  # noqa: BLE001
            time.sleep(1)
    raise RuntimeError("no UNO connection")


def guard(result, key, fn):
    try:
        result[key] = fn()
    except Exception:  # noqa: BLE001
        result[key] = "ERROR " + traceback.format_exc()


def walk(acc, depth=0, limit=6):
    context = acc.getAccessibleContext()
    node = {"role": context.getAccessibleRole(), "name": context.getAccessibleName()}
    try:
        b = context.getBounds()
        node["bounds"] = [b.X, b.Y, b.Width, b.Height]
    except Exception:  # noqa: BLE001
        pass
    if depth < limit:
        node["children"] = [walk(context.getAccessibleChild(i), depth + 1, limit)
                            for i in range(min(context.getAccessibleChildCount(), 40))]
    return node


def state(ctx, result):
    from hst_office import default_apps, default_apps_os, mac_app_location as mac, update_install, welcome_job
    from hst_office.update_fetch import release_info
    guard(result, "brand_base_dir", lambda: ctx.getValueByName("/singletons/com.sun.star.util.theMacroExpander")
          .expandMacros("$BRAND_BASE_DIR"))
    guard(result, "office_paths", lambda: update_install.office_paths(ctx, "Darwin"))
    guard(result, "locate", lambda: mac.locate(update_install.office_paths(ctx, "Darwin")[1]))
    guard(result, "release", lambda: release_info())
    guard(result, "offered", lambda: mac.offered(release_info()["release"]))
    guard(result, "welcome_shown", lambda: welcome_job.is_shown(ctx))
    guard(result, "default_apps_state", lambda: default_apps.load_state(ctx))
    guard(result, "mac_in_applications(module file)", lambda: default_apps_os.mac_in_applications())
    guard(result, "mac_is_registered", lambda: default_apps_os.mac_is_registered())
    guard(result, "module_file", lambda: default_apps_os.__file__)


def options(ctx, result):
    smgr = ctx.ServiceManager
    pip = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
    origin = pip.getPackageLocation("vn.hasontech.hst.vietnamese-tools")
    result["origin"] = origin
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    frame = desktop.getCurrentFrame() or desktop.getFrames().getByIndex(0)
    parent = frame.getContainerWindow()
    provider = smgr.createInstanceWithContext("com.sun.star.awt.ContainerWindowProvider", ctx)
    for page, service in (("DefaultApps", "org.hst.office.vi.OptionsPage"), ("Appearance", "org.hst.office.vi.OptionsAppearance")):
        entry = result.setdefault(page, {})
        try:
            handler = smgr.createInstanceWithContext(service, ctx)
            entry["handler"] = handler.getImplementationName() if handler else None
            window = provider.createContainerWindow(origin + "/dialogs/" + page + ".xdl", "", parent, handler)
            entry["window"] = window is not None
            if handler is not None:
                try:
                    entry["initialize"] = handler.callHandlerMethod(window, "initialize", "external_event")
                except Exception:  # noqa: BLE001
                    entry["initialize"] = "ERROR " + traceback.format_exc()
            b = window.getPosSize()
            entry["bounds"] = [b.X, b.Y, b.Width, b.Height]
            entry["accessible"] = walk(window)
            window.dispose()
        except Exception:  # noqa: BLE001
            entry["error"] = traceback.format_exc()
    # the real dialog, opened at the Appearance page
    url = origin + "/dialogs/Appearance.xdl"
    import threading
    dispatcher = smgr.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    arg = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    arg.Name, arg.Value = "OptionsPageURL", url
    threading.Thread(target=lambda: dispatcher.executeDispatch(frame, ".uno:OptionsTreeDialog", "", 0, (arg,)),
                     daemon=True).start()
    time.sleep(6)
    top = toolkit.getActiveTopWindow()
    result["options_dialog"] = walk(top, limit=9) if top is not None else None


def main():
    mode, out, extpy = sys.argv[1], sys.argv[2], sys.argv[3]
    sys.path.insert(0, extpy)
    result = {"mode": mode}
    try:
        ctx = connect()
        (state if mode == "state" else options)(ctx, result)
    except Exception:  # noqa: BLE001
        result["error"] = traceback.format_exc()
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(result, ensure_ascii=False, default=str)[:4000], flush=True)


if __name__ == "__main__":
    main()
