# SPDX-License-Identifier: AGPL-3.0-only
"""POSIX shell templates for waiting, installing, recovering and relaunching.

Linux script = HEADER + SETUP + variables + LINUX + one install_update (LINUX_DEB here, or LINUX_RPM / LINUX_APPIMAGE of
update_helper_scripts_linux) + RUN."""

HEADER = r'''#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-only
umask 077
log_step() { printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"; }
verify_installer() {
    [ -f "$INSTALLER" ] || { log_step 'SHA256 verification failed: installer missing'; return 1; }
    for tool in $HASH_TOOLS; do
        command -v "$tool" >/dev/null 2>&1 || continue
        case "$tool" in
            sha256sum) digest=$(sha256sum < "$INSTALLER") ;;
            shasum) digest=$(shasum -a 256 < "$INSTALLER") ;;
            openssl) digest=$(openssl dgst -sha256 < "$INSTALLER") ;;
        esac || { log_step 'SHA256 verification failed: hash tool failed'; return 1; }
        digest=${digest##*= }
        [ "${digest%% *}" = "$SHA256" ] && return 0
        log_step 'SHA256 mismatch; installation skipped'; return 1
    done
    log_step 'SHA256 verification failed: no hash tool'; return 1
}
# The start-up job shows this once (update_outcome.py); it stays on this machine. Called by finish's exit trap.
# shellcheck disable=SC2317
record_failure() {
    temp=$STATE.$$
    if printf '{"schema":1,"code":"%s","exit":%d,"from":"%s","to":"%s"}\n' "$1" "$2" "$FROM_RELEASE" "$TO_RELEASE" >"$temp" \
        && mv -f "$temp" "$STATE"; then
        log_step "Recorded failure: $1 ($2)"
    else
        log_step 'Failure not recorded'
    fi
}
'''

SETUP = r'''
PID=$1; INSTALLER=$2; SOFFICE=$3; LOG=$4; SHA256=$5; DRY_RUN=${6-}
STATE=${LOG%/*}/update-result.json
exec >>"$LOG" 2>&1 || exit 1
'''

LINUX = r'''
# Called indirectly by finish's exit trap.
# shellcheck disable=SC2317
cleanup() { :; }
if command -v setsid >/dev/null 2>&1; then RELAUNCH="setsid $RELAUNCH"; fi
# shellcheck disable=SC2317
relaunch() {
    if [ ! -x "$SOFFICE" ]; then log_step 'Relaunch unavailable: executable missing'; return; fi
    log_step 'Relaunching HST Office'
    if command -v setsid >/dev/null 2>&1; then
        setsid nohup "$SOFFICE" >/dev/null 2>&1 &
    else
        nohup "$SOFFICE" >/dev/null 2>&1 &
    fi
}
'''

# .deb installs (dpkg owns the office): apt-get through pkexec, else PackageKit. rpm and AppImage installs replace this
# function (update_helper_scripts_linux.py).
LINUX_DEB = r'''
install_update() {
    if command -v pkexec >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
        if [ "$DRY_RUN" = --dry-run ]; then log_step "DRYRUN install: $APT_COMMAND"; return 0; fi
        log_step 'Installing with apt-get'
        pkexec env DEBIAN_FRONTEND=noninteractive apt-get install -y "$INSTALLER"
        code=$?
        # pkexec: 126 = the password dialog was dismissed (the user's choice), 127 = not authorized.
        case "$code" in 126) FAIL=cancel ;; 127) FAIL=auth ;; esac
        return "$code"
    elif command -v pkcon >/dev/null 2>&1; then
        if [ "$DRY_RUN" = --dry-run ]; then log_step "DRYRUN install: $PKCON_COMMAND"; return 0; fi
        log_step 'Installing with pkcon'
        pkcon install-local "$INSTALLER"
    else
        FAIL=tool
        message='HST Office update: no installer tool; please install the downloaded package manually.'
        log_step "$message"
        if command -v zenity >/dev/null 2>&1; then zenity --error --text="$message";
        elif command -v kdialog >/dev/null 2>&1; then kdialog --error "$message";
        elif command -v notify-send >/dev/null 2>&1; then notify-send 'HST Office update' "$message"; fi
        return 1
    fi
}
'''

RUN = r'''
# Called indirectly by the exit trap.
# shellcheck disable=SC2317
finish() {
    status=$?
    trap - EXIT
    cleanup
    # Stopped while the office was still open (Cancel at its save prompt): nothing to report, nothing to reopen.
    if [ -n "$STOPPED" ]; then log_step 'Stopped before installing; the office stays open'; exit "$status"; fi
    if [ "$status" -ne 0 ] && [ "$FAIL" != cancel ]; then record_failure "$FAIL" "$status"; fi
    if [ "$DRY_RUN" = --dry-run ]; then
        log_step "DRYRUN relaunch: $RELAUNCH"
    else
        if [ "$status" -eq 0 ]; then
            if rm -f "$INSTALLER"; then log_step 'Deleted installer'; else log_step 'Installer deletion failed'; fi
        fi
        relaunch
    fi
    exit "$status"
}
STOPPED=; FAIL='wait'
trap finish EXIT
trap 'STOPPED=1; exit 1' HUP INT TERM
log_step "Waiting for process $PID"
seconds=0
while kill -0 "$PID" 2>/dev/null; do
    if [ "$seconds" -ge 1800 ]; then log_step 'Timed out after 30 minutes; installation skipped'; exit 1; fi
    sleep 1
    seconds=$((seconds + 1))
done
log_step 'Process exited'
trap 'exit 1' HUP INT TERM
rm -f "$STATE"
FAIL=verify
verify_installer || exit 1
FAIL=install
install_update
code=$?
log_step "Installer exited with code $code"
exit "$code"
'''
