# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Start-up guard of "Cập nhật ngay" (Jobs.xcu, OnStartApp): no second office while the updater installs, and no
office that keeps running inside an app bundle replaced under it.

Before update_install starts the external helper, it writes updating.lock beside update.log: the helper's process ID
(0 until the helper has started), the office's own and the time. The helper removes the file when it ends, before it
opens HST Office again (update_helper_scripts RUN). An office started while the file names a helper that still runs
says "đang cập nhật" (macOS: a notification, so that the quit does not wait for a click) and quits: on macOS such a copy, started from the Dock while the helper copied the new app,
went on running inside a bundle that was then replaced, loaded the libraries of both versions and hung.

macOS also checks that the bundle on disk still holds the version this office runs (Info.plist against
release.json), and that its own executable was not moved aside by a swap (".app.hst-old/"). When either changed, the
user is told, a waiter opens the app again once this office has quit (mac_move_script --reopen), and the office quits.
A reopen for the same versions is not repeated within REOPEN_PAUSE, so a broken bundle cannot start a loop.
Every file stays on this machine.
"""
import os
import platform
import re
import time

import unohelper
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJob

from . import diag_log
# The lock and reopen files, and the local process queries (ctypes), live in their own modules; re-exported here
# because update_install and the tests use them as update_guard.*.
from .update_guard_files import (LOCK_NAME, REOPEN_PAUSE, read_lock, remove_lock, reopen_due,  # noqa: F401
                                 write_lock)
from .update_guard_process import own_executable, pid_alive  # noqa: F401

JOB_NAME = "org.hst.office.vi.UpdateGuardJob"
MAX_AGE = 45 * 60  # the helper waits up to 30 minutes for the office to quit, then checks, swaps and relaunches
SPAWN_GRACE = 120  # a lock without a helper yet: the office is starting it
MOVED_ASIDE = ".app.hst-old/"  # the swap renames the old bundle to <name>.app.hst-old (update_helper_scripts_mac)


def update_in_progress(cache, now=None, alive=pid_alive):
    """True while the lock names a helper that still runs (or one being started). A stale lock is removed."""
    record = read_lock(cache)
    if record is None:
        return False
    now = int(time.time() if now is None else now)
    age = now - record["time"] if record else -1
    if record and 0 <= age <= MAX_AGE:
        if record["helper"]:
            if alive(record["helper"]):
                return True
        elif record["office"] != os.getpid() and age <= SPAWN_GRACE:
            return True
    remove_lock(cache)
    return False


def release_core(release):
    """"1.0.4" of "1.0.4-rc.1"; None for a text that is not a release id."""
    match = re.match(r"(\d+\.\d+\.\d+)(?:$|[-+])", release or "")
    return match.group(1) if match else None


def bundle_version(bundle):
    """CFBundleShortVersionString of the bundle on disk, or None when it cannot be read."""
    import plistlib
    try:
        with open(os.path.join(bundle, "Contents", "Info.plist"), "rb") as handle:
            value = plistlib.load(handle).get("CFBundleShortVersionString")
    except (OSError, ValueError, AttributeError, plistlib.InvalidFileException):
        return None
    return value if isinstance(value, str) else None


def replaced_bundle(bundle, release, executable=None):
    """The version now on disk ("" when unknown) when the bundle this office runs from was replaced; else None."""
    disk = bundle_version(bundle)
    if executable and MOVED_ASIDE in executable:
        return disk or ""
    running = release_core(release)
    if disk and running and disk != running:
        return disk
    return None


def _tell(ctx, message):
    from .update_install import _ask
    from .update_texts import texts
    text = texts(ctx)
    _ask(ctx, None, text["install_title"], message, [(text["close"], "close")], text_height=40)


def _quit(ctx):
    from . import update_launch as launch
    if not launch.quit_office(ctx):
        diag_log.info("update_guard", "the office did not quit")


def _notify_mac(message):
    """A macOS notification that outlives this office (the helper's notify); message has no double quotes."""
    from . import update_launch as launch
    launch.spawn(["/usr/bin/osascript", "-e", 'display notification "%s" with title "HST Office"' % message.replace('"', "'")],
                 "Darwin")


def _updating(ctx, system):
    """Says that the update is installing, then quits. macOS: a notification and the quit at once, since the helper
    waits only 60 s for this copy before it gives the update up; elsewhere a message, then the quit."""
    from .update_texts import texts
    diag_log.info("update_guard", "an update is being installed; this copy quits")
    message = texts(ctx)["guard_updating"]
    try:
        if system == "Darwin":
            _notify_mac(message)
        else:
            _tell(ctx, message)
    finally:
        _quit(ctx)


def _replaced(ctx, cache, bundle, running, disk):
    from . import mac_move_script as move
    from . import update_launch as launch
    from .update_texts import texts
    diag_log.info("update_guard", "bundle replaced under the running office: %s on disk, %s running" % (disk, running))
    script = move.write_script(cache)
    launch.spawn(move.reopen_argv(script, os.getpid(), bundle, os.path.join(cache, "update.log")), "Darwin")
    try:
        _tell(ctx, texts(ctx)["guard_replaced"] % (disk or "?", running))
    finally:
        _quit(ctx)


def check(ctx, system=None):
    """The start-up check: "updating", "replaced" or None. The dialog and the quit run on a later main-thread turn."""
    from . import update_installer as installer
    from . import update_ui as ui
    system = system or platform.system()
    cache = installer.cache_dir(system)
    if update_in_progress(cache):
        ui.on_main_thread(ctx, lambda: _updating(ctx, system))
        return "updating"
    if system != "Darwin":
        return None
    from .update_fetch import release_info
    from .update_install import office_paths
    bundle = office_paths(ctx, system)[1]
    running = release_info()["release"]
    disk = replaced_bundle(bundle, running, own_executable())
    if disk is None or not reopen_due(cache, running, disk):
        return None
    ui.on_main_thread(ctx, lambda: _replaced(ctx, cache, bundle, running, disk))
    return "replaced"


class UpdateGuardJob(unohelper.Base, XServiceInfo, XJob):
    def __init__(self, ctx):
        self.ctx = ctx

    def getImplementationName(self):
        return JOB_NAME

    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getSupportedServiceNames(self):
        return ("com.sun.star.task.Job",)

    def execute(self, arguments):
        try:
            check(self.ctx)
        except Exception:  # noqa: BLE001 - never block or break start-up
            diag_log.exception("update_guard")
        return None
