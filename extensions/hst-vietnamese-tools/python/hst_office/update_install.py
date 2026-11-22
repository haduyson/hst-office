# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""UNO flow of "Cập nhật ngay": progress dialog -> verified installer -> question -> helper + normal office shutdown.

Never silent: the download starts on the user's click, the install only after the user answers "Cập nhật ngay" to
"Đóng HST Office để cập nhật?". Every failure ends in a message with "Tải về" (manual download in the browser).
The office is closed through Desktop.terminate(), so modified documents get the standard save prompts and Cancel
there aborts the update (the helper, started before terminate, is stopped then, without relaunching anything).
A failed install is reported at the next start (update_outcome). On macOS a bundle that cannot be replaced (the .dmg,
an App Translocation path) is updated into /Applications instead, and that copy is opened (mac_app_location); the
office quits only once the helper has checked and copied the new app (update_helper_ready).
"""
import os
import platform
from . import update_config
from . import update_guard as guard
from . import update_helper_ready as ready
from . import update_helper_cmd as cmd
from . import update_installer as installer
from . import update_launch as launch
from . import update_linux_install as linux_install
from . import update_resume as resume
from . import update_ui as ui
from .update_install_progress import _download_dialog
from .update_install_ui import _ask, _live_peer, needs_password, office_paths  # noqa: F401 - patched by tests as update_install.*
from .update_texts import texts
from . import diag_log

DRY_RUN_ENV = "HST_UPDATE_DRY_RUN"  # test packages only (update_test_mode); release packages ignore it
NOTES_FALLBACK = "https://office.hasontech.vn/#tai-ve"
OWN_DIALOG_TURNS = 50  # main-thread turns to wait for ended dialogs to leave their modal loops


def manual_download(ctx):
    release = ui.STATE["release"]
    ui.open_url(ctx, ui.release_download(release) if release else NOTES_FALLBACK)


def fail(ctx, peer, code):
    TEXT = texts(ctx)
    if _ask(ctx, peer, TEXT["install_title"], TEXT[code], [(TEXT["download"], "download"), (TEXT["close"], "close")]) == "download":
        manual_download(ctx)


def launch_and_quit(ctx, result, info, peer=None):
    """Start the helper (it waits for this process to exit), then close the office the normal way.

    True when the office is quitting; False when it stays open (Cancel at a save prompt, or a window that refused to
    close); None when the administrator turned installing off meanwhile. Before quitting, update_resume's record names
    the open documents, so the office that the helper starts again reopens them; it is removed when the office stays."""
    system = platform.system()
    cache = installer.cache_dir(system)
    soffice, bundle = office_paths(ctx, system)
    target, linux_kind = bundle, linux_install.linux_kind() if system == "Linux" else "deb"
    if linux_kind == "appimage":  # the AppImage file is replaced and started again, not the program in its mount
        soffice = os.environ["APPIMAGE"]
    if system == "Darwin":  # a bundle on the .dmg, translocated or not writable: install into /Applications instead
        from . import mac_app_location
        target = mac_app_location.update_target(bundle)
    dry = info.get("test_mode") and bool(os.environ.get(DRY_RUN_ENV))
    notices = None
    if system == "Darwin":  # shown by the helper after the office closed, in the office's language
        TEXT = texts(ctx)
        notices = {name: TEXT["helper_" + name] for name in cmd.MAC_NOTICES}
    helper = cmd.build_helper(system, pid=os.getpid(), installer=result["path"], sha256=result["entry"]["sha256"], soffice=soffice, log=launch.log_path(cache),
                              dry_run=bool(dry), app_dest=target, app_origin=bundle if target != bundle else None,
                              release_from=info["release"], release_to=result["release"]["version"], linux_kind=linux_kind,
                              notices=notices)
    if not update_config.settings(ctx)["AllowInstall"]:  # the policy may have changed since the click
        return None
    argv = cmd.argv(helper, launch.write_helper(helper, cache))
    try:
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        resume.write(cache, info["release"], result["release"]["version"], resume.document_urls(desktop))
    except Exception:  # noqa: BLE001 - without the record the update still runs; the documents are not reopened
        diag_log.exception("update_install")
    closing = False
    try:
        # Before the helper starts: an office opened while it installs quits again (update_guard); the helper removes
        # the lock when it ends.
        guard.write_lock(cache)

        def started(pid):
            guard.write_lock(cache, helper=pid)
        if system == "Windows" and not dry:  # elevated now, while the office is still the window the user looks at
            closing = launch.elevate_and_quit(ctx, argv, cache, on_started=started)
        elif system == "Darwin":  # quits once the helper has checked and copied the new app (update_helper_ready)
            ready.discard(cache)
            closing = launch.spawn_and_quit(ctx, argv, system, on_started=started,
                                            before_quit=lambda proc: ready.wait_with_dialog(ctx, peer, proc, cache))
        else:
            closing = launch.spawn_and_quit(ctx, argv, system, on_started=started)
    finally:
        if not closing:  # Cancel in a save prompt (or an error): nothing is updated, the file stays for later
            resume.discard(cache)
            guard.remove_lock(cache)
    return closing


def install(ctx, peer, result, info, turns=0):
    """The user answered "Cập nhật ngay": close the extension's own modal dialogs, then the office.

    A modal dialog left open in another window (the welcome dialog, say) keeps the office from closing. Those of this
    extension are ended first and the quit waits for them to leave their modal loops (later main-thread turns). When
    the office still does not close, the user is told and may try again: never a silent "nothing happened"."""
    try:
        _install(ctx, peer, result, info, turns)
    except Exception:  # noqa: BLE001 - this may run from a later main-thread turn: never silent
        diag_log.exception("update_install")
        try:
            fail(ctx, _live_peer(ctx, peer), "err_unexpected")
        except Exception:  # noqa: BLE001 - not even the message could be shown
            diag_log.exception("update_install")


def _install(ctx, peer, result, info, turns):
    if launch.end_own_dialogs() and turns < OWN_DIALOG_TURNS:
        ui.on_main_thread(ctx, lambda: install(ctx, peer, result, info, turns + 1))
        return
    try:
        closing = launch_and_quit(ctx, result, info, peer)
    except launch.ElevationDeclined:  # No at the administrator question: the office stays open
        diag_log.info("update_install", "administrator rights declined")
        return fail(ctx, _live_peer(ctx, peer), "err_elevation")
    except ready.PrepareCancelled:  # Cancel while the helper prepared the update: the office stays open
        diag_log.info("update_install", "update cancelled while it was prepared")
        return None
    except ready.HelperFailed as exc:  # macOS: a check or the copy failed before the quit
        diag_log.info("update_install", "the helper failed before the quit: %s" % exc.code)
        return fail(ctx, _live_peer(ctx, peer), ready.message_key(exc.code))
    except Exception:  # noqa: BLE001 - helper could not be written or started
        diag_log.exception("update_install")
        return fail(ctx, _live_peer(ctx, peer), "err_launch")
    if closing is False:
        diag_log.info("update_install", "the office did not close; nothing was installed")
        TEXT = texts(ctx)
        if _ask(ctx, _live_peer(ctx, peer), TEXT["install_title"], TEXT["err_quit"],
                [(TEXT["retry"], "retry"), (TEXT["later"], "later")], text_height=40) == "retry":
            install(ctx, peer, result, info)


def start(ctx, peer):
    """Entry point of the "Cập nhật ngay" button / org.hst.office.update:Install."""
    try:
        info = ui.release_info_for(ctx)
        if not update_config.settings(ctx)["AllowInstall"]:
            return manual_download(ctx)
        system = platform.system()
        if cmd.preflight(system, linux_kind=linux_install.linux_kind() if system == "Linux" else "deb"):
            return fail(ctx, peer, "err_tools")
        outcome = _download_dialog(ctx, peer, info, ui.proxy(ctx))
        if outcome is None or outcome.get("cancelled"):
            return None
        if "result" not in outcome:
            return fail(ctx, peer, outcome.get("code", "err_network")) if outcome.get("code") != "uptodate" else None
        TEXT = texts(ctx)
        version = outcome["result"]["release"]["version"]
        # macOS: the password is asked only after the office closed; say so now, or a skipped prompt looks like a no-op
        password = system == "Darwin" and needs_password(office_paths(ctx, system)[1])
        if _ask(ctx, peer, TEXT["install_title"], TEXT["ready_password" if password else "ready"] % version,
                [(TEXT["install"], "install"), (TEXT["later"], "later")], 52 if password else 28) == "install":
            install(ctx, peer, outcome["result"], info)
    except Exception:  # noqa: BLE001 - report instead of failing inside the UI thread
        diag_log.exception("update_install")
        try:  # never silent: the user clicked "Cập nhật ngay" and must learn that nothing was installed
            fail(ctx, peer, "err_unexpected")
        except Exception:  # noqa: BLE001 - not even the message could be shown
            diag_log.exception("update_install")
    return None
