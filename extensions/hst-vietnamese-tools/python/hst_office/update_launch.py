# SPDX-License-Identifier: AGPL-3.0-only
"""Write, detach and cancel the external updater without invoking a shell; quit the office behind it."""
import os
import signal
import subprocess

from .update_elevate_windows import ElevationDeclined  # noqa: F401 - raised through elevate_and_quit
from .update_helper_cmd import argv as helper_argv


def log_path(cache_dir):
    return os.path.join(cache_dir, "update.log")


def write_helper(helper, directory):
    """Write a private helper using its declared encoding and executable mode."""
    if helper["name"] not in ("hst-update.sh", "hst-update.ps1"):
        raise ValueError("invalid helper filename")
    path = os.path.abspath(os.path.join(directory, helper["name"]))
    helper_argv(helper, path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    mode = 0o700 if helper["name"].endswith(".sh") else 0o600
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags, mode), "w", encoding=helper["encoding"], newline="\n") as handle:
        os.chmod(path, mode)
        handle.write(helper["text"])
    return path


# macOS helpers start with a login-like environment, not the office's own. The office process carries variables that
# point into the bundle it runs from (URE_BOOTSTRAP, PYTHONPATH, ...). `open` passes the caller's environment on, so
# a copy opened from a helper of a translocated office looked for its UNO types in the old, unmounted bundle and
# crashed at start (SIGSEGV in LocaleBackend::getPropertyValue). Kept: what the scripts and LaunchServices need.
MAC_HELPER_ENV = ("HOME", "USER", "LOGNAME", "TMPDIR")
MAC_HELPER_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def mac_helper_environment(environ=None):
    environ = os.environ if environ is None else environ
    env = {name: environ[name] for name in MAC_HELPER_ENV if environ.get(name)}
    env["PATH"] = MAC_HELPER_PATH
    return env


def spawn(argv, system, log_dir=None):
    """Start a detached helper; log_dir optionally ensures the log's parent exists."""
    if system not in ("Windows", "Darwin", "Linux"):
        raise ValueError("unsupported system")
    if log_dir is not None:
        os.makedirs(log_dir, mode=0o700, exist_ok=True)
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
               "stderr": subprocess.DEVNULL, "close_fds": True, "shell": False}
    if system == "Windows":
        # A new console without a window, not DETACHED_PROCESS: powershell.exe started with no console at all exits
        # at once with code 0 and never runs its -File script (checked on Windows 11), so no update ever ran.
        options["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                                    | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    else:
        options["start_new_session"] = True
    if system == "Darwin":
        options["env"] = mac_helper_environment()
    return subprocess.Popen(argv, **options)


def cancel(proc):
    """Terminate this helper's session, escalating after five seconds; reap the child."""
    if proc.poll() is not None:
        return False

    def stop(force=False):
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
            elif force:
                proc.kill()
            else:
                proc.terminate()
        except ProcessLookupError:
            pass

    stop()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        stop(force=True)
        proc.wait()
    return True


def quit_office(ctx):
    """Close the office the way its own Quit command does; True when it is quitting.

    Desktop.terminate() closes every window first (modified documents get their save prompt), then asks the terminate
    listeners. On macOS the office's Dock menu (the quick starter) vetoes every termination, so that the app stays
    alive with no window: a plain terminate() closes the Start Center and returns False. Like the office's own Quit
    (desktop/source/app/app.cxx, Desktop::QueryExit), lift that veto for this call and restore it when a save prompt
    was cancelled."""
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    desktop.setPropertyValue("SuspendQuickstartVeto", True)
    closing = False
    try:
        closing = bool(desktop.terminate())
    finally:
        if not closing:
            desktop.setPropertyValue("SuspendQuickstartVeto", False)
    return closing


def spawn_and_quit(ctx, argv, system):
    """Start the helper that waits for this office to exit, then quit the office (quit_office). When the quit is
    cancelled at a save prompt, or fails, the helper is stopped and the office keeps running. True when quitting."""
    proc, closing = spawn(argv, system), False
    try:
        closing = quit_office(ctx)
    finally:
        if not closing:
            cancel(proc)
    return closing


# Windows: the helper must start elevated *before* the office closes (update_elevate_windows). The office cannot
# stop an elevated process, so a quit cancelled at a save prompt leaves this marker, which the helper obeys.
CANCEL_NAME = "update-cancel"  # read by the Windows helper (update_helper_scripts_windows)


def cancel_marker(cache_dir):
    return os.path.join(cache_dir, CANCEL_NAME)


def run_elevated(argv):
    """Start argv elevated (update_elevate_windows.run_elevated); ElevationDeclined when the user says No."""
    from .update_elevate_windows import run_elevated as run
    return run(argv[0], subprocess.list2cmdline(argv[1:]))


def elevate_and_quit(ctx, argv, cache_dir, run=run_elevated):
    """Windows: start the elevated helper, then quit the office (quit_office). The office cannot stop an elevated
    process, so a quit cancelled at a save prompt leaves the cancel marker, which the helper obeys. True when quitting."""
    marker = cancel_marker(cache_dir)
    try:
        os.unlink(marker)
    except FileNotFoundError:
        pass
    run(argv)  # ElevationDeclined / OSError: the office has not been asked to close
    closing = False
    try:
        closing = quit_office(ctx)
    finally:
        if not closing:
            with open(marker, "w", encoding="ascii") as handle:
                handle.write("cancel\n")
    return closing
