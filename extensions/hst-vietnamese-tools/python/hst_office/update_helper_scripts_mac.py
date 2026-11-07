# SPDX-License-Identifier: AGPL-3.0-only
"""POSIX shell templates of the macOS helper: verified app swap and the dmg install step."""

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
# Called indirectly by the swap's exit trap.
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
# Replaces the app at $2 with a verified copy of $1, or installs it there when $2 does not exist yet.
swap() {
    source=$1; dest=$2; staged=$2.hst-new; old=$2.hst-old; fresh=
    safe_path "$source" && safe_path "$dest" || return 1
    case "$dest" in *.app) ;; *) return 1 ;; esac
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        [ -d "$dest" ] && [ ! -L "$dest" ] || return 1
    else
        [ -d "${dest%/*}" ] && [ ! -L "${dest%/*}" ] || return 1
        fresh=1
    fi
    if [ -e "$staged" ] || [ -L "$staged" ] || [ -e "$old" ] || [ -L "$old" ]; then
        log_step 'Swap refused: staging or backup already exists'; return 1
    fi
    trap recover_swap EXIT
    trap 'exit 1' HUP INT TERM
    log_step 'Staging app beside destination'
    if ! ditto "$source" "$staged" >/dev/null 2>&1 || ! verify "$staged"; then
        log_step 'Staging verification failed'; return 1
    fi
    # Assessed again on the copy itself: the source may have changed after its own check, and the copy loses its
    # quarantine flag below, so macOS would not assess it again at its first start.
    if ! spctl --assess --type execute "$staged" >/dev/null 2>&1; then
        log_step 'Staged copy failed the Gatekeeper assessment'; return 1
    fi
    # A copy of a downloaded app keeps the quarantine flag, and macOS would translocate it again on every start.
    # Removed only from the copy that has just passed the signature and team check above.
    if command -v xattr >/dev/null 2>&1; then
        xattr -dr com.apple.quarantine "$staged" >/dev/null 2>&1 || log_step 'Quarantine flag not removed'
    fi
    if [ -z "$fresh" ]; then
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
if [ "${1-}" = --swap ]; then swap "$2" "$3"; exit $?; fi
'''

MAC_INSTALL = r'''
MOUNT=
# Called indirectly by finish's exit trap.
# shellcheck disable=SC2317
cleanup() {
    [ -n "$MOUNT" ] || return 0
    log_step 'Detaching installer image'
    if ! hdiutil detach "$MOUNT" >/dev/null 2>&1 && ! hdiutil detach -force "$MOUNT" >/dev/null 2>&1; then
        log_step 'Image detach failed'
    fi
    rmdir "$MOUNT" 2>/dev/null || :
}
# shellcheck disable=SC2317
relaunch() {
    # A failed install somewhere else (/Applications) reopens the copy that was running, which shows the failure.
    if [ "$status" -ne 0 ] && [ -n "$ORIGIN" ] && [ -d "$ORIGIN" ]; then
        log_step 'Relaunching the app that was running'
        open "$ORIGIN" >/dev/null 2>&1 || log_step 'Relaunch failed'
    elif [ -d "$SOFFICE" ]; then
        log_step 'Relaunching HST Office'
        open "$SOFFICE" >/dev/null 2>&1 || log_step 'Relaunch failed'
    elif [ -d "$SOFFICE.hst-old" ]; then
        log_step 'Relaunching retained old app'
        open -a "$SOFFICE.hst-old" >/dev/null 2>&1 || log_step 'Relaunch failed'
    else
        log_step 'Relaunch unavailable: app missing'
        notify 'Chưa cài được bản cập nhật HST Office. Hãy tải bản cài đặt tại office.hasontech.vn và cài thủ công.'
    fi
}
# The destination can be replaced by this user: its folder is writable and it is missing or writable itself.
writable_target() { [ -w "${SOFFICE%/*}" ] && { [ ! -e "$SOFFICE" ] || [ -w "$SOFFICE" ]; }; }
install_update() {
    safe_path "$0" && safe_path "$INSTALLER" && safe_path "$SOFFICE" || return 1
    # A mounted .dmg or an App Translocation path is read-only: an administrator password cannot help, so fail
    # (and record it) before asking for one. Checked in dry runs too, so that they report what a real run would do.
    if ! writable_target; then
        case "$SOFFICE" in /Volumes/*|*/AppTranslocation/*)
            FAIL='readonly'
            log_step 'Destination is read-only (disk image or translocated app); drag HST Office to Applications'
            return 1 ;;
        esac
    fi
    MOUNT=$(mktemp -d "${INSTALLER%/*}/.hst-update.XXXXXX") || return 1
    log_step 'Attaching installer image'
    hdiutil attach -nobrowse -readonly -noverify -mountpoint "$MOUNT" "$INSTALLER" >/dev/null 2>&1 || return 1
    set -- "$MOUNT"/*.app "$MOUNT"/.[!.]*.app "$MOUNT"/..?*.app
    app=; count=0
    for candidate do
        if [ -d "$candidate" ]; then app=$candidate; count=$((count + 1)); fi
    done
    if [ "$count" -ne 1 ]; then log_step 'Image must contain exactly one app'; return 1; fi
    safe_path "$app" || { log_step 'Unsafe app path'; return 1; }
    log_step 'Verifying app signature, team and Gatekeeper assessment'
    FAIL=verify
    verify "$app" && spctl --assess --type execute "$app" >/dev/null 2>&1 || return 1
    FAIL=install
    if writable_target; then
        # Shell quoting for runtime paths, equivalent to shlex.quote's single-quote escape.
        quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
        if [ "$DRY_RUN" = --dry-run ]; then
            log_step "DRYRUN install: /bin/sh $(quote "$0") --swap $(quote "$app") $(quote "$SOFFICE")"
            return 0
        fi
        /bin/sh "$0" --swap "$app" "$SOFFICE"
    else
        command=$(admin_command "$app" "$SOFFICE") || { log_step 'Swap refused: unknown script hash'; return 1; }
        if [ "$DRY_RUN" = --dry-run ]; then
            log_step "DRYRUN install: osascript -e '$(printf '%s' "$command" | sed "s/'/'\\\\''/g")'"
            return 0
        fi
        log_step 'Requesting administrator privileges for swap'
        answer=$(osascript -e "$command" 2>&1)
        code=$?
        log_step "Swap command exited with code $code: $answer"
        # The password dialog was cancelled: the user's choice, not a failure to report.
        case "$answer" in *'(-128)'*) FAIL=cancel ;; esac
        return "$code"
    fi
}
'''
