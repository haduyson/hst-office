# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""POSIX shell templates of the macOS helper: verified app swap and the dmg install step."""
# The dmg install step lives in its own module (size); re-exported for update_helper_cmd.
from .update_helper_scripts_mac_install import MAC_INSTALL  # noqa: F401

MAC_SWAP = r'''
safe_path() {
    case "$1" in /*) ;; *) return 1 ;; esac
    case "$1" in *[[:cntrl:]\"\\]*|@PATH_CONTROLS@) return 1 ;; esac
}
# A failure the user must see even when no HST Office window opens again (fixed texts without double quotes).
# shellcheck disable=SC2317
notify() { osascript -e "display notification \"$1\" with title \"HST Office\"" >/dev/null 2>&1 || :; }
# The AppleScript that runs "--swap $1 $2" as administrator. Root copies this script into a fresh root-owned folder and
# runs that copy only if its SHA-256 equals $SCRIPT_SHA256, which the office computed when it wrote the script: a change
# made to the user's file in the meantime is never run as root.
admin_command() {
    case "$SCRIPT_SHA256" in *[!0-9a-f]*|'') return 1 ;; esac
    [ "${#SCRIPT_SHA256}" -eq 64 ] || return 1
    # shellcheck disable=SC2016 # the $... parts are expanded by root's shell, not by this one
    printf '%s' 'do shell script ("d=$(/usr/bin/mktemp -d /tmp/hst-swap.XXXXXX) || exit 1; /bin/cp " & quoted form of "'"$0"'" & " \"$d/s.sh\" && h=$(/usr/bin/shasum -a 256 < \"$d/s.sh\") && [ \"${h%% *}\" = '"$SCRIPT_SHA256"' ] && /bin/sh \"$d/s.sh\" --swap " & quoted form of "'"$1"'" & " " & quoted form of "'"$2"'" & "; r=$?; /bin/rm -rf \"$d\"; exit $r") with administrator privileges'
}
verify() {
    codesign --verify --deep --strict "$1" >/dev/null 2>&1 || return 1
    details=$(codesign -dv --verbose=4 "$1" 2>&1) || return 1
    printf '%s\n' "$details" | grep -Fxq 'TeamIdentifier=@TEAM_ID@'
}
# Exit code of a swap refused because HST Office still runs from the app (the administrator step returns it too).
BUSY_EXIT=75
BUSY_WAIT=60
# True when a process runs an executable from inside the app $1: macOS `ps -o comm` prints its full path.
bundle_busy() {
    ps -axww -o comm= 2>/dev/null | { while IFS= read -r line; do case "$line" in "$1"/*) exit 0 ;; esac; done; exit 1; }
}
# Waits up to BUSY_WAIT seconds for every process running from the app $1 to end. Replacing the bundle under a running
# office made it load the libraries of the new version beside its own and crash, then hang in its recovery UI.
wait_until_free() {
    bundle_busy "$1" || return 0
    log_step 'HST Office runs from the app; waiting for it to quit'
    waited=0
    while bundle_busy "$1"; do
        if [ "$waited" -ge "$BUSY_WAIT" ]; then
            log_step "Swap refused: HST Office still runs from the app after $BUSY_WAIT seconds"; return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
    log_step 'The app is no longer in use'
}
# Called indirectly by the commit's exit trap.
# shellcheck disable=SC2317
recover_swap() {
    result=$?
    trap - EXIT
    trap '' HUP INT TERM
    if [ ! -e "$dest" ] && [ -d "$old" ]; then
        log_step 'Swap failed; restoring old app'
        mv "$old" "$dest" || log_step 'Restore failed; old app retained in backup'
    fi
    if [ -e "$staged" ]; then rm -rf "$staged"; fi
    exit "$result"
}
# Places a verified copy of $1 beside the app $2 as $2.hst-new. Runs while the office is still open (or as the first
# half of the administrator step), so that only two renames are left once it has quit.
stage() {
    source=$1; dest=$2; staged=$2.hst-new; old=$2.hst-old
    safe_path "$source" && safe_path "$dest" || return 1
    case "$dest" in *.app) ;; *) return 1 ;; esac
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        [ -d "$dest" ] && [ ! -L "$dest" ] || return 1
    else
        [ -d "${dest%/*}" ] && [ ! -L "${dest%/*}" ] || return 1
    fi
    if [ -e "$old" ] || [ -L "$old" ] || [ -L "$staged" ]; then
        log_step 'Swap refused: staging or backup already exists'; return 1
    fi
    # A staging copy left by an update that was stopped while it copied (Cancel at the office's save prompt).
    if [ -d "$staged" ]; then
        log_step 'Removing a staging copy left by an earlier update'
        rm -rf "$staged" || return 1
    fi
    if [ -e "$staged" ]; then log_step 'Swap refused: staging or backup already exists'; return 1; fi
    trap 'rm -rf "$staged"; exit 1' HUP INT TERM
    log_step 'Staging app beside destination'
    if ! ditto "$source" "$staged" >/dev/null 2>&1 || ! verify "$staged"; then
        log_step 'Staging verification failed'; rm -rf "$staged"; return 1
    fi
    # Assessed again on the copy itself: the source may have changed after its own check, and the copy loses its
    # quarantine flag below, so macOS would not assess it again at its first start.
    if ! spctl --assess --type execute "$staged" >/dev/null 2>&1; then
        log_step 'Staged copy failed the Gatekeeper assessment'; rm -rf "$staged"; return 1
    fi
    # A copy of a downloaded app keeps the quarantine flag, and macOS would translocate it again on every start.
    # Removed only from the copy that has just passed the signature and team check above.
    if command -v xattr >/dev/null 2>&1; then
        xattr -dr com.apple.quarantine "$staged" >/dev/null 2>&1 || log_step 'Quarantine flag not removed'
    fi
    trap - HUP INT TERM
    log_step 'Staged app is ready'
}
# Moves the staged copy into place once no process runs from the app $1 any more; exit BUSY_EXIT when one still does.
commit() {
    dest=$1; staged=$1.hst-new; old=$1.hst-old; fresh=
    safe_path "$dest" || return 1
    case "$dest" in *.app) ;; *) return 1 ;; esac
    if [ ! -d "$staged" ] || [ -L "$staged" ]; then log_step 'Swap refused: no staged app'; return 1; fi
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        [ -d "$dest" ] && [ ! -L "$dest" ] || return 1
    else
        fresh=1
    fi
    if [ -e "$old" ] || [ -L "$old" ]; then log_step 'Swap refused: staging or backup already exists'; return 1; fi
    trap recover_swap EXIT
    trap 'exit 1' HUP INT TERM
    if [ -z "$fresh" ]; then
        wait_until_free "$dest" || return "$BUSY_EXIT"
        log_step 'Moving old app aside'
        mv "$dest" "$old" || return 1
    fi
    log_step 'Moving staged app into place'
    mv "$staged" "$dest" || return 1
    if [ -z "$fresh" ]; then
        log_step 'Removing old app after successful swap'
        rm -rf "$old"
    fi
}
# Replaces the app at $2 with a verified copy of $1, or installs it there when $2 does not exist yet.
swap() { stage "$1" "$2" && commit "$2"; }
case "${1-}" in
    --swap) swap "$2" "$3"; exit $? ;;
    --stage) stage "$2" "$3"; exit $? ;;
    --commit) commit "$2"; exit $? ;;
esac
'''
