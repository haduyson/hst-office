# SPDX-License-Identifier: AGPL-3.0-only
"""POSIX shell template of the start-up move into /Applications (mac_app_location): HEADER + MAC_SWAP + MAC_MOVE."""

# Modes:
#   --copy SOURCE DEST LOG        verified copy into a missing DEST, as administrator when its folder is not writable;
#                                 exit 2 when the password dialog was cancelled.
#   --reopen PID DEST LOG [OLD]   after the office PID has quit: remove OLD (only a copy in ~/Downloads) and open DEST.
MAC_MOVE = r'''
case "${1-}" in
--copy)
    source=$2; dest=$3; LOG=$4
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
    command='do shell script ("/bin/sh " & quoted form of "'"$0"'" & " --swap " & quoted form of "'"$source"'" & " " & quoted form of "'"$dest"'") with administrator privileges'
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
    open "$dest" >/dev/null 2>&1 || { log_step 'Open failed'; exit 1; }
    exit 0
    ;;
esac
exit 64
'''
