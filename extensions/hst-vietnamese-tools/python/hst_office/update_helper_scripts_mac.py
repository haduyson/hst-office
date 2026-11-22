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

MAC_INSTALL = r'''
MOUNT=; STAGED=; app=; WATCHER=
# Called indirectly by finish's exit trap.
# shellcheck disable=SC2317
cleanup() {
    if [ -n "$WATCHER" ]; then kill "$WATCHER" 2>/dev/null || :; fi
    # Staged while the office was open, then never moved into place (stopped at its save prompt, or a later failure).
    if [ -n "$STAGED" ] && [ -d "$SOFFICE.hst-new" ] && [ ! -L "$SOFFICE.hst-new" ]; then
        log_step 'Removing the unused staged app'
        rm -rf "$SOFFICE.hst-new"
    fi
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
    elif [ -d "$SOFFICE" ] && bundle_busy "$SOFFICE"; then
        # `open` would only bring that office to the front, and it may have started before the swap.
        log_step 'Relaunch skipped: an HST Office opened during the update runs'
        if [ "$status" -eq 0 ]; then notify "$NOTE_OLD_RUNNING"; fi
    elif [ -d "$SOFFICE" ]; then
        log_step 'Relaunching HST Office'
        open "$SOFFICE" >/dev/null 2>&1 || log_step 'Relaunch failed'
    elif [ -d "$SOFFICE.hst-old" ]; then
        log_step 'Relaunching retained old app'
        open -a "$SOFFICE.hst-old" >/dev/null 2>&1 || log_step 'Relaunch failed'
    else
        log_step 'Relaunch unavailable: app missing'
        notify "$NOTE_FAILED"
    fi
}
# The destination can be replaced by this user: its folder is writable and it is missing or writable itself.
writable_target() { [ -w "${SOFFICE%/*}" ] && { [ ! -e "$SOFFICE" ] || [ -w "$SOFFICE" ]; }; }
# Shell quoting for runtime paths, equivalent to shlex.quote's single-quote escape.
quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
# Everything that can run while the office is still open: SHA-256, image, signature, team and Gatekeeper checks and,
# when this user may replace the app, the verified copy beside it. Once the office has quit, only the renames and the
# relaunch are left, so the app is not gone for long enough that the user starts it again in the meantime.
prepare_update() {
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
    FAIL=verify
    verify_installer || return 1
    VERIFIED=1
    FAIL=install
    MOUNT=$(mktemp -d "${INSTALLER%/*}/.hst-update.XXXXXX") || return 1
    log_step 'Attaching installer image'
    hdiutil attach -nobrowse -readonly -noverify -mountpoint "$MOUNT" "$INSTALLER" >/dev/null 2>&1 || return 1
    set -- "$MOUNT"/*.app "$MOUNT"/.[!.]*.app "$MOUNT"/..?*.app
    count=0
    for candidate do
        if [ -d "$candidate" ]; then app=$candidate; count=$((count + 1)); fi
    done
    if [ "$count" -ne 1 ]; then log_step 'Image must contain exactly one app'; return 1; fi
    safe_path "$app" || { log_step 'Unsafe app path'; return 1; }
    log_step 'Verifying app signature, team and Gatekeeper assessment'
    FAIL=verify
    verify "$app" && spctl --assess --type execute "$app" >/dev/null 2>&1 || return 1
    FAIL=install
    # Administrator path: root copies and checks the app again in its swap, after the office has quit.
    writable_target || return 0
    if [ "$DRY_RUN" = --dry-run ]; then
        log_step "DRYRUN stage: /bin/sh $(quote "$0") --stage $(quote "$app") $(quote "$SOFFICE")"
        return 0
    fi
    STAGED=1
    /bin/sh "$0" --stage "$app" "$SOFFICE"
}
# Tells the user, as soon as the office has closed, that it opens again by itself: with no window and no notice the
# user took the update for a failed start and opened the old app again while it was being replaced.
watch_exit() {
    [ "$DRY_RUN" = --dry-run ] && return 0
    helper=$$
    (
        while kill -0 "$PID" 2>/dev/null && kill -0 "$helper" 2>/dev/null; do sleep 1; done
        if kill -0 "$helper" 2>/dev/null; then notify "$NOTE_INSTALLING"; fi
    ) &
    WATCHER=$!
}
# After the office has quit.
install_update() {
    if [ "$DRY_RUN" != --dry-run ] && [ -e "$SOFFICE" ] && bundle_busy "$SOFFICE"; then notify "$NOTE_BUSY"; fi
    if writable_target; then
        if [ "$DRY_RUN" = --dry-run ]; then
            log_step "DRYRUN install: /bin/sh $(quote "$0") --commit $(quote "$SOFFICE")"
            return 0
        fi
        /bin/sh "$0" --commit "$SOFFICE"
        code=$?
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
        case "$answer" in *'(-128)'*) FAIL=cancel ;; *"($BUSY_EXIT)"*) code=$BUSY_EXIT ;; esac
    fi
    if [ "$code" -eq "$BUSY_EXIT" ]; then
        FAIL=busy
        notify "$NOTE_BUSY_FAILED"
    fi
    return "$code"
}
'''
