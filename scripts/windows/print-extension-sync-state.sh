#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Print what decides whether an office start re-registers the bundled extensions in a profile (Git Bash on Windows):
# user/extensions/buildid against the install's version.ini buildid (desktop app.cxx cleanExtensionCache) and the
# modification time of user/extensions/bundled/lastsynchronized against share/extensions (dp_misc.cxx
# needToSyncRepository: a sync only when the folder is newer). Usage: print-extension-sync-state.sh PROFILE INSTALL
set -u
profile="$1" install="$2"
stamp() { if [ -e "$1" ]; then date -u -r "$1" '+%Y-%m-%dT%H:%M:%SZ'; else echo missing; fi; }
echo "profile: $profile"
echo "install: $install"
echo "version.ini buildid: [$(grep -i '^buildid=' "$install/program/version.ini" 2>/dev/null | cut -d= -f2- | tr -d '\r')]"
echo "profile buildid: [$(tr -d '\r\n' < "$profile/user/extensions/buildid" 2>/dev/null || echo missing)]"
echo "share/extensions mtime: $(stamp "$install/share/extensions")"
echo "bundled lastsynchronized mtime: $(stamp "$profile/user/extensions/bundled/lastsynchronized")"
registry="$profile/user/extensions/bundled/registry"
echo "registered implementation names of the HST extension:"
grep -rhoE 'org\.hst\.office\.vi\.[A-Za-z]+' "$registry" 2>/dev/null | sort -u | tr '\n' ' '
echo
echo "registered configuration files of the HST extension:"
grep -rhoE 'hst-vietnamese-tools/[A-Za-z]+\.xc[su]' "$registry" 2>/dev/null | sort -u | tr '\n' ' '
echo
