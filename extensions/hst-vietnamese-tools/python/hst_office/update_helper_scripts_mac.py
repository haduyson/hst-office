# SPDX-License-Identifier: AGPL-3.0-only
"""POSIX shell templates of the macOS helper: verified app swap and the dmg install step."""

MAC_SWAP = r'''
safe_path() {
    case "$1" in /*) ;; *) return 1 ;; esac
    case "$1" in *[[:cntrl:]\"\\]*|@PATH_CONTROLS@) return 1 ;; esac
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
swap() {
    source=$1; dest=$2; staged=$2.hst-new; old=$2.hst-old
    safe_path "$source" && safe_path "$dest" || return 1
    [ -d "$dest" ] && [ ! -L "$dest" ] || return 1
    if [ -e "$staged" ] || [ -L "$staged" ] || [ -e "$old" ] || [ -L "$old" ]; then
        log_step 'Swap refused: staging or backup already exists'; return 1
    fi
    trap recover_swap EXIT
    trap 'exit 1' HUP INT TERM
    log_step 'Staging app beside destination'
    if ! ditto "$source" "$staged" >/dev/null 2>&1 || ! verify "$staged"; then
        log_step 'Staging verification failed'; return 1
    fi
    log_step 'Moving old app aside'
    mv "$dest" "$old" || return 1
    log_step 'Moving staged app into place'
    mv "$staged" "$dest" || return 1
    log_step 'Removing old app after successful swap'
    rm -rf "$old"
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
    if [ -d "$SOFFICE" ]; then
        log_step 'Relaunching HST Office'
        open "$SOFFICE" >/dev/null 2>&1 || log_step 'Relaunch failed'
    elif [ -d "$SOFFICE.hst-old" ]; then
        log_step 'Relaunching retained old app'
        open -a "$SOFFICE.hst-old" >/dev/null 2>&1 || log_step 'Relaunch failed'
    else log_step 'Relaunch unavailable: app missing'; fi
}
install_update() {
    safe_path "$0" && safe_path "$INSTALLER" && safe_path "$SOFFICE" || return 1
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
    verify "$app" && spctl --assess --type execute "$app" >/dev/null 2>&1 || return 1
    if [ -w "${SOFFICE%/*}" ] && [ -w "$SOFFICE" ]; then
        # Shell quoting for runtime paths, equivalent to shlex.quote's single-quote escape.
        quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
        if [ "$DRY_RUN" = --dry-run ]; then
            log_step "DRYRUN install: /bin/sh $(quote "$0") --swap $(quote "$app") $(quote "$SOFFICE")"
            return 0
        fi
        /bin/sh "$0" --swap "$app" "$SOFFICE"
    else
        command='do shell script ("/bin/sh " & quoted form of "'"$0"'" & " --swap " & quoted form of "'"$app"'" & " " & quoted form of "'"$SOFFICE"'") with administrator privileges'
        if [ "$DRY_RUN" = --dry-run ]; then
            log_step "DRYRUN install: osascript -e '$(printf '%s' "$command" | sed "s/'/'\\\\''/g")'"
            return 0
        fi
        log_step 'Requesting administrator privileges for swap'
        osascript -e "$command"
    fi
}
'''
