# SPDX-License-Identifier: AGPL-3.0-only
"""UNO flow of "Cập nhật ngay": progress dialog -> verified installer -> question -> helper + normal office shutdown.

Never silent: the download starts on the user's click, the install only after the user answers "Cập nhật ngay" to
"Đóng HST Office để cập nhật?". Every failure ends in a message with "Tải về" (manual download in the browser).
The office is closed through Desktop.terminate(), so modified documents get the standard save prompts and Cancel
there aborts the update (the helper, started before terminate, is stopped then).
"""
import os
import platform
import threading
import time
import traceback

import uno

from . import update_config
from . import update_helper_cmd as cmd
from . import update_installer as installer
from . import update_launch as launch
from . import update_ui as ui
from .update_download import DownloadCancelled
from .update_fetch import release_info
from .update_prepare import PrepareError, prepare
from .update_texts import texts

DRY_RUN_ENV = "HST_UPDATE_DRY_RUN"  # test packages only (update_test_mode); release packages ignore it
NOTES_FALLBACK = "https://office.hasontech.vn/#tai-ve"


def _size(n):
    return "%.1f MB" % (n / 1048576.0)


def _ask(ctx, peer, title, text, buttons):
    """Modal question; `buttons` = [(label, key)]; returns the key of the clicked button or None (closed)."""
    from .dialogs import CANCEL, Dialog
    dialog = Dialog(ctx, title, 300, 64)
    dialog.label("message", text, 8, 8, 284, 28, wrap=True)
    keys, x = [], 8
    for index, (label, key) in enumerate(buttons):
        width = max(44, 8 + 5 * len(label))
        last = index == len(buttons) - 1
        dialog.button("b%d" % index, label, 292 - width if last else x, 44, width, kind=CANCEL if last else None,
                      default=index == 0, callback=None if last else (lambda k=key: (keys.append(k), dialog.end(1))))
        x += width + 4
    if dialog.execute(peer):
        return keys[0] if keys else None
    return buttons[-1][1]


def manual_download(ctx):
    release = ui.STATE["release"]
    ui.open_url(ctx, ui.release_download(release) if release else NOTES_FALLBACK)


def fail(ctx, peer, code):
    TEXT = texts(ctx)
    if _ask(ctx, peer, TEXT["install_title"], TEXT[code], [(TEXT["download"], "download"), (TEXT["close"], "close")]) == "download":
        manual_download(ctx)


def _download_dialog(ctx, peer, info, proxy):
    """Progress dialog with Cancel around the worker thread; returns the prepare() result or a PrepareError code."""
    from .dialogs import CANCEL, Dialog
    TEXT = texts(ctx)
    dialog = Dialog(ctx, TEXT["progress_title"], 260, 56)
    label = dialog.label("status", TEXT["checking"], 8, 8, 244)
    bar = dialog._add("ProgressBar", "bar", 8, 22, 244, 10, ProgressValueMin=0, ProgressValueMax=100, ProgressValue=0)
    dialog.button("cancel", TEXT["cancel"], 206, 38, 46, kind=CANCEL)
    outcome, stop, closed, last = {}, threading.Event(), threading.Event(), [0.0]

    def progress(done, total):
        now = time.monotonic()
        if done < total and now - last[0] < 0.2:
            return
        last[0] = now
        percent = int(done * 100 / total) if total else 0

        def show():
            label.Label = TEXT["downloading"] % (percent, _size(total))
            bar.ProgressValue = percent
        ui.on_main_thread(ctx, show)

    def work():
        try:
            outcome["result"] = prepare(info, proxy, progress, stop.is_set)
        except DownloadCancelled:
            outcome["cancelled"] = True
        except PrepareError as exc:
            print("HST update install: %s" % exc, flush=True)
            outcome["code"] = exc.code
        except Exception:  # noqa: BLE001 - never let the worker die silently
            traceback.print_exc()
            outcome["code"] = "err_network"
        while not closed.is_set():  # a request to end before the modal loop runs is lost: repeat until it is closed
            ui.on_main_thread(ctx, lambda: None if closed.is_set() else dialog.end(1))
            closed.wait(0.3)
    threading.Thread(target=work, name="hst-update-download", daemon=True).start()
    try:
        finished = dialog.execute(peer)
    finally:
        closed.set()
    if not finished:  # Cancel (or closed): the worker notices, removes its partial file and stops
        stop.set()
        return None
    return outcome


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


def launch_and_quit(ctx, result, info):
    """Start the helper (it waits for this process to exit), then close the office the normal way."""
    system = platform.system()
    cache = installer.cache_dir(system)
    soffice, bundle = office_paths(ctx, system)
    dry = info.get("test_mode") and bool(os.environ.get(DRY_RUN_ENV))
    helper = cmd.build_helper(system, pid=os.getpid(), installer=result["path"], sha256=result["entry"]["sha256"], soffice=soffice, log=launch.log_path(cache),
                              dry_run=bool(dry), app_dest=bundle)
    if not update_config.settings(ctx)["AllowInstall"]:  # the policy may have changed since the click
        return
    proc, closing = launch.spawn(cmd.argv(helper, launch.write_helper(helper, cache)), system), False
    try:
        closing = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate()
    finally:
        if not closing:  # Cancel in a save prompt (or an error): nothing is updated, the file stays for later
            launch.cancel(proc)


def start(ctx, peer):
    """Entry point of the "Cập nhật ngay" button / org.hst.office.update:Install."""
    try:
        info = release_info()
        if not update_config.settings(ctx)["AllowInstall"]:
            return manual_download(ctx)
        if cmd.preflight(platform.system()):
            return fail(ctx, peer, "err_tools")
        outcome = _download_dialog(ctx, peer, info, ui.proxy(ctx))
        if outcome is None or outcome.get("cancelled"):
            return None
        if "result" not in outcome:
            return fail(ctx, peer, outcome.get("code", "err_network")) if outcome.get("code") != "uptodate" else None
        TEXT = texts(ctx)
        version = outcome["result"]["release"]["version"]
        if _ask(ctx, peer, TEXT["install_title"], TEXT["ready"] % version,
                [(TEXT["install"], "install"), (TEXT["later"], "later")]) == "install":
            try:
                launch_and_quit(ctx, outcome["result"], info)
            except Exception:  # noqa: BLE001 - helper could not be written or started
                traceback.print_exc()
                fail(ctx, peer, "err_launch")
    except Exception:  # noqa: BLE001 - report instead of failing inside the UI thread
        traceback.print_exc()
    return None
