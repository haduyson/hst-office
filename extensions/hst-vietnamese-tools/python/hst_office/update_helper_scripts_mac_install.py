# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""POSIX shell template of the macOS helper's dmg install step (mount, verify, swap through MAC_SWAP, relaunch)."""

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
