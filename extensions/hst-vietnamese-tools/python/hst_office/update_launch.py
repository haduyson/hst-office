# SPDX-License-Identifier: AGPL-3.0-only
"""Write, detach and cancel the external updater without invoking a shell."""
import os
import signal
import subprocess

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


def spawn(argv, system, log_dir=None):
    """Start a detached helper; log_dir optionally ensures the log's parent exists."""
    if system not in ("Windows", "Darwin", "Linux"):
        raise ValueError("unsupported system")
    if log_dir is not None:
        os.makedirs(log_dir, mode=0o700, exist_ok=True)
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
               "stderr": subprocess.DEVNULL, "close_fds": True, "shell": False}
    if system == "Windows":
        options["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
                                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                                    | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    else:
        options["start_new_session"] = True
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
