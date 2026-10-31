#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Collect upstream's macOS signing inputs from a LibreOffice source tree into a "signing kit".
#   make-signing-kit.sh <libreoffice-src> <kit-dir>
# The kit holds solenv/bin/macosx-codesign-app-bundle and the *templates* of the entitlement and
# launch-constraint files. scripts/macos/sign-notarize.sh fills them at signing time: an unsigned
# configure leaves MACOSX_CODESIGNING_TEAM_IDENTIFIER empty in LaunchConstraint.plist, which would
# stop the signed helpers from launching, so the configure-generated copies are not used.
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <libreoffice-src> <kit-dir>" >&2; exit 64; }
src="$1"; kit="$2"
rm -rf "$kit"; mkdir -p "$kit/templates"
cp "$src/solenv/bin/macosx-codesign-app-bundle" "$kit/"
for f in hardened_runtime.xcent.in LaunchConstraint.plist.in quicklookappex.entitlements; do
  cp "$src/sysui/desktop/macosx/$f" "$kit/templates/"
done
ls -l "$kit" "$kit/templates"
