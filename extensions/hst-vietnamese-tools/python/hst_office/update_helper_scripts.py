# SPDX-License-Identifier: AGPL-3.0-only
"""POSIX shell templates for waiting, installing, recovering and relaunching."""

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
'''

SETUP = r'''
PID=$1; INSTALLER=$2; SOFFICE=$3; LOG=$4; SHA256=$5; DRY_RUN=${6-}
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
install_update() {
    if command -v pkexec >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
        if [ "$DRY_RUN" = --dry-run ]; then log_step "DRYRUN install: $APT_COMMAND"; return 0; fi
        log_step 'Installing with apt-get'
        pkexec env DEBIAN_FRONTEND=noninteractive apt-get install -y "$INSTALLER" >/dev/null 2>&1
    elif command -v pkcon >/dev/null 2>&1; then
        if [ "$DRY_RUN" = --dry-run ]; then log_step "DRYRUN install: $PKCON_COMMAND"; return 0; fi
        log_step 'Installing with pkcon'
        pkcon install-local "$INSTALLER" >/dev/null 2>&1
    else
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
trap finish EXIT
trap 'exit 1' HUP INT TERM
log_step "Waiting for process $PID"
seconds=0
while kill -0 "$PID" 2>/dev/null; do
    if [ "$seconds" -ge 1800 ]; then log_step 'Timed out after 30 minutes; installation skipped'; exit 1; fi
    sleep 1
    seconds=$((seconds + 1))
done
log_step 'Process exited'
verify_installer || exit 1
install_update
code=$?
log_step "Installer exited with code $code"
exit "$code"
'''
