# SPDX-License-Identifier: AGPL-3.0-only
"""The script of the start-up move into /Applications (mac_app_location): HEADER + MAC_SWAP + MAC_MOVE, written into a
private folder and run without a shell. Its digest goes into the arguments, so the root step (admin_command) can refuse
a copy of the file that changed after it was written."""
import hashlib
import os
import stat
import traceback

from . import update_helper_cmd as cmd
from . import update_helper_scripts as scripts

SCRIPT_NAME = "hst-move.sh"
LOG_NAME = "move.log"
LOG_LIMIT = 256 * 1024  # bytes; one older log is kept as move.log.1
COPY_TIMEOUT = 900  # seconds
CANCELLED = 2  # --copy: the administrator password dialog was cancelled
TIMED_OUT = "timeout"

# Shell modes:
#   --copy SOURCE DEST LOG HASH   verified copy into a missing DEST, as administrator when its folder is not writable;
#                                 exit 2 when the password dialog was cancelled.
#   --reopen PID DEST LOG [OLD]   after the office PID has quit: remove OLD (only a copy in ~/Downloads) and open DEST.
MAC_MOVE = r'''
case "${1-}" in
--copy)
    source=$2; dest=$3; LOG=$4; SCRIPT_SHA256=${5-}
    exec >>"$LOG" 2>&1 || exit 1
    if ! { safe_path "$0" && safe_path "$source" && safe_path "$dest"; }; then log_step 'Move refused: unsafe path'; exit 1; fi
    if [ -e "$dest" ] || [ -L "$dest" ]; then log_step 'Move refused: destination exists'; exit 1; fi
    log_step 'Verifying the running app before the move'
    if ! verify "$source" || ! spctl --assess --type execute "$source" >/dev/null 2>&1; then
        log_step 'Move refused: signature, team or Gatekeeper check failed'; exit 1
    fi
    if [ -w "${dest%/*}" ]; then
        /bin/sh "$0" --swap "$source" "$dest"
        code=$?
        log_step "Move exited with code $code"
        exit "$code"
    fi
    command=$(admin_command "$source" "$dest") || { log_step 'Move refused: unknown script hash'; exit 1; }
    log_step 'Requesting administrator privileges for the move'
    answer=$(osascript -e "$command" 2>&1)
    code=$?
    log_step "Move command exited with code $code: $answer"
    case "$answer" in *'(-128)'*) exit 2 ;; esac
    exit "$code"
    ;;
--reopen)
    PID=$2; dest=$3; LOG=$4; old=${5-}
    exec >>"$LOG" 2>&1 || exit 1
    safe_path "$dest" || exit 1
    seconds=0
    while kill -0 "$PID" 2>/dev/null; do
        if [ "$seconds" -ge 1800 ]; then log_step 'Timed out waiting for HST Office to quit'; exit 1; fi
        sleep 1
        seconds=$((seconds + 1))
    done
    if [ -n "$old" ]; then
        case "$old" in
            */../*|*/./*) log_step 'Downloaded copy kept: unsafe path' ;;
            "$HOME"/Downloads/*.app)
                if safe_path "$old" && [ -d "$old" ] && [ ! -L "$old" ] && verify "$dest"; then
                    if rm -rf "$old"; then log_step 'Removed the downloaded copy'; else log_step 'Downloaded copy not removed'; fi
                fi ;;
            *) log_step 'Downloaded copy kept: not in Downloads' ;;
        esac
    fi
    log_step 'Opening HST Office from Applications'
    if [ ! -d "$dest" ] || ! open "$dest" >/dev/null 2>&1; then
        log_step 'Open failed'
        notify 'Không mở được HST Office từ thư mục Ứng dụng. Hãy mở HST Office trong thư mục Ứng dụng bằng Finder.'
        exit 1
    fi
    exit 0
    ;;
esac
exit 64
'''


def script_text():
    return scripts.HEADER + cmd.mac_swap() + MAC_MOVE


def script_sha256():
    return hashlib.sha256(script_text().encode("utf-8")).hexdigest()


def write_script(directory):
    """Write the script (0700) into `directory`, a real folder of this user without group or world access."""
    os.makedirs(directory, mode=0o700, exist_ok=True)
    folder = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(folder)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise OSError("not a private folder of this user: %s" % directory)
        if stat.S_IMODE(info.st_mode) & 0o077:
            os.fchmod(folder, 0o700)
    finally:
        os.close(folder)
    path = cmd.mac_path(os.path.join(os.path.abspath(directory), SCRIPT_NAME))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o700)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        os.fchmod(handle.fileno(), 0o700)
        handle.write(script_text())
    return path


def cap_log(path):
    """Keep the move log small: past LOG_LIMIT it becomes move.log.1 (replacing the older one)."""
    try:
        if os.lstat(path).st_size > LOG_LIMIT:
            os.replace(path, path + ".1")
    except OSError:
        pass


def copy_argv(script, source, dest, log):
    return ["/bin/sh", cmd.mac_path(script), "--copy", cmd.mac_bundle(source), cmd.mac_bundle(dest), cmd.mac_path(log), script_sha256()]


def reopen_argv(script, pid, dest, log, remove=None):
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive process ID")
    extra = [cmd.mac_bundle(remove)] if remove else []
    return ["/bin/sh", cmd.mac_path(script), "--reopen", str(pid), cmd.mac_bundle(dest), cmd.mac_path(log)] + extra


def run_copy(argv, timeout=COPY_TIMEOUT):
    """The --copy exit code, or TIMED_OUT. A timed-out copy is left running: its root part cannot be stopped from here
    and may still finish."""
    from . import update_launch as launch  # the one module allowed to start processes
    proc = launch.spawn(argv, "Darwin")
    try:
        return proc.wait(timeout=timeout)
    except launch.subprocess.TimeoutExpired:
        return TIMED_OUT
    except Exception:  # noqa: BLE001 - interrupted: stop it and report a failed move
        traceback.print_exc()
        launch.cancel(proc)
        return 1
