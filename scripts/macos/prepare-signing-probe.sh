#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Prepare the inputs of the signing probe (.github/workflows/macos-signature-probe.yml, job "sign")
# from a released dmg, the way a desktop-macos build hands them to its "sign" job:
#   prepare-signing-probe.sh <released dmg> <work-dir>
# Produces <work-dir>/adhoc/<dmg name> (the release app re-signed by adhoc-sign.sh and repacked
# with build-dmg.sh, i.e. what the fixed unsigned build ships) and <work-dir>/signing-kit (from the
# pinned LibreOffice source tarball, sha256-checked against upstream/libreoffice-lock.json).
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <work-dir>" >&2; exit 64; }
dmg="$1"; work="$2"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
mkdir -p "$work/src" "$work/stage" "$work/adhoc" "$work/mnt"

# Signing kit from the pinned main source tarball (only the four files are extracted).
read -r url sha name < <(python3 -c '
import json, sys
t = json.load(open(sys.argv[1]))["tarballs"][0]
print(t["url"], t["sha256"], t["name"])' "$repo/upstream/libreoffice-lock.json")
curl -fsSL --retry 3 -o "$work/$name" "$url"
echo "$sha  $work/$name" | shasum -a 256 -c -
top="${name%.tar.xz}"
tar -xf "$work/$name" -C "$work/src" --strip-components=1 "$top/solenv/bin/macosx-codesign-app-bundle" \
  "$top/sysui/desktop/macosx/hardened_runtime.xcent.in" "$top/sysui/desktop/macosx/LaunchConstraint.plist.in" \
  "$top/sysui/desktop/macosx/quicklookappex.entitlements"
rm -f "$work/$name"
bash "$here/make-signing-kit.sh" "$work/src" "$work/signing-kit"

# The released app with the ad-hoc fix, repacked like the build does.
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$work/mnt" "$dmg" >/dev/null
ditto "$work/mnt/HST Office.app" "$work/stage/HST Office.app"
hdiutil detach "$work/mnt" >/dev/null
bash "$here/adhoc-sign.sh" "$work/stage/HST Office.app"
bash "$here/build-dmg.sh" "$work/stage/HST Office.app" "$work/adhoc/$(basename "$dmg")"
(cd "$work/adhoc" && shasum -a 256 -- *.dmg > SHA256SUMS && cat SHA256SUMS)
