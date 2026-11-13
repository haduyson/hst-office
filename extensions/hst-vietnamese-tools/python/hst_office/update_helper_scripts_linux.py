# SPDX-License-Identifier: AGPL-3.0-only
"""install_update() of the Linux updater for .rpm and AppImage installs (the .deb one is update_helper_scripts.LINUX_DEB).

Same contract as the .deb path: return the tool's exit code, set FAIL=cancel/auth from pkexec (126/127) and FAIL=tool
when nothing can install; the caller logs, records failures (update_outcome) and relaunches.
  rpm:      pkexec dnf install -y <file> (dnf 4 and 5 accept an unsigned local file) | pkexec zypper
            --non-interactive install --allow-unsigned-rpm <file> | pkexec rpm -U <file> | pkcon install-local <file>.
            The package is unsigned for now: SHA256 from the signed manifest, checked again here, is what vouches for it.
  AppImage: no root. The verified file already sits in a hidden directory beside the running AppImage (same file
            system, see update_prepare), so `mv` is one atomic rename over the old file; the path stays the same, so
            launchers written by the desktop integration keep working. The new AppImage starts with the variables
            the old mount exported removed.
"""

NO_TOOL = r'''
no_install_tool() {
    FAIL=tool
    message='HST Office update: no installer tool; please install the downloaded package manually.'
    log_step "$message"
    if command -v zenity >/dev/null 2>&1; then zenity --error --text="$message";
    elif command -v kdialog >/dev/null 2>&1; then kdialog --error "$message";
    elif command -v notify-send >/dev/null 2>&1; then notify-send 'HST Office update' "$message"; fi
    return 1
}
'''

LINUX_RPM = NO_TOOL + r'''
install_update() {
    TOOL=
    if command -v pkexec >/dev/null 2>&1; then
        if command -v dnf >/dev/null 2>&1; then TOOL=dnf; set -- dnf install -y "$INSTALLER"
        elif command -v zypper >/dev/null 2>&1; then TOOL=zypper; set -- zypper --non-interactive install --allow-unsigned-rpm "$INSTALLER"
        elif command -v rpm >/dev/null 2>&1; then TOOL=rpm; set -- rpm -U "$INSTALLER"
        fi
    fi
    if [ -n "$TOOL" ]; then
        if [ "$DRY_RUN" = --dry-run ]; then
            quoted=pkexec
            for arg in "$@"; do quoted="$quoted '$(printf '%s' "$arg" | sed "s/'/'\\\\''/g")'"; done
            log_step "DRYRUN install: $quoted"; return 0
        fi
        log_step "Installing with $TOOL"
        pkexec "$@"
        code=$?
        # pkexec: 126 = the password dialog was dismissed (the user's choice), 127 = not authorized.
        case "$code" in 126) FAIL=cancel ;; 127) FAIL=auth ;; esac
        return "$code"
    elif command -v pkcon >/dev/null 2>&1; then
        if [ "$DRY_RUN" = --dry-run ]; then log_step "DRYRUN install: $PKCON_COMMAND"; return 0; fi
        log_step 'Installing with pkcon'
        pkcon install-local "$INSTALLER"
    else
        no_install_tool
    fi
}
'''

LINUX_APPIMAGE = r'''
install_update() {
    if [ "$DRY_RUN" = --dry-run ]; then log_step "DRYRUN install: replace $SOFFICE"; return 0; fi
    log_step 'Replacing the AppImage'
    chmod 755 "$INSTALLER" || return 1
    mv -f "$INSTALLER" "$SOFFICE" || return 1
    rmdir "${INSTALLER%/*}" 2>/dev/null
    log_step 'AppImage replaced'
    return 0
}
# Called indirectly by finish's exit trap.
# shellcheck disable=SC2317
relaunch() {
    if [ ! -x "$SOFFICE" ]; then log_step 'Relaunch unavailable: AppImage missing'; return; fi
    log_step 'Relaunching HST Office'
    set -- env -u APPDIR -u APPIMAGE -u ARGV0 -u OWD -u PYTHONHOME -u PYTHONPATH -u URE_BOOTSTRAP -u UNO_PATH "$SOFFICE"
    if command -v setsid >/dev/null 2>&1; then setsid nohup "$@" >/dev/null 2>&1 &
    else nohup "$@" >/dev/null 2>&1 &
    fi
}
'''
