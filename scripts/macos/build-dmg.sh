#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Build the HST Office disk image from an app bundle with the HST layout (scripts/macos/dmg-settings.py).
#   build-dmg.sh <path/HST Office.app> <out.dmg>
# Env: HST_PYTHON (python with dmgbuild, default python3). Used for the unsigned build and again
# after Developer ID signing (scripts/macos/sign-notarize.sh).
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <app> <out.dmg>" >&2; exit 64; }
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${HST_PYTHON:-python3}"
app="$1"; out="$2"
[ -d "$app" ] || { echo "no app bundle at $app" >&2; exit 1; }
[ "$(basename "$app")" = "HST Office.app" ] || { echo "unexpected app name $(basename "$app")" >&2; exit 1; }
rm -f "$out"
"$PY" -m dmgbuild -s "$REPO/scripts/macos/dmg-settings.py" -D app="$app" -D repo="$REPO" "HST Office" "$out"
# dmgbuild ignores ditto's exit status: compare the copied bundle with its source.
mnt="$(mktemp -d)"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$out" >/dev/null
rc=0
diff -rq "$app" "$mnt/HST Office.app" >/dev/null || { echo "app bundle in $out differs from $app" >&2; rc=1; }
compgen -G "$mnt/.background*" >/dev/null || { echo "missing background in $out" >&2; rc=1; }
for item in .DS_Store .VolumeIcon.icns Applications; do
  [ -e "$mnt/$item" ] || [ -L "$mnt/$item" ] || { echo "missing $item in $out" >&2; rc=1; }
done
hdiutil detach "$mnt" >/dev/null
rmdir "$mnt"
exit "$rc"
