#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Real-mouse picture selection check in Writer for one macOS dmg.
#   image-select-probe.sh <HSTOffice_*.dmg> <out-dir> <label>
# Copies the app out of the dmg, starts it with a fresh profile (welcome marked as shown) listening on a pipe,
# writes a two-picture .docx and runs image-select-probe.py with the bundled Python. Evidence only.
set -Eeuo pipefail
[ $# -eq 3 ] || { echo "usage: $0 <dmg> <out-dir> <label>" >&2; exit 64; }
dmg="$1"; out="$2"; label="$3"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
brew list cliclick >/dev/null 2>&1 || brew install cliclick >"$out/brew-cliclick.log" 2>&1
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign-$label.log" 2>&1 || true
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
profile="$work/profile"; mkdir -p "$profile/user"
cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
docx="$work/inline-pictures.docx"
python3 "$here/make-inline-picture-docx.py" "$docx"
"$app/Contents/MacOS/soffice" --norestore --nologo --nodefault --accept="pipe,name=hstimgsel;urp;" \
  "-env:UserInstallation=file://$profile" >"$out/soffice-$label.log" 2>&1 &
pid=$!
sleep 10
URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" PYTHONPATH="$app/Contents/Resources:$pyhome" \
  perl -e 'alarm 300; exec @ARGV' "$py" "$here/image-select-probe.py" "$pid" "$docx" "$out" "$label" \
  >"$out/driver-$label.log" 2>&1 || echo "driver exit $?" >>"$out/driver-$label.log"
screencapture -x "$out/$label-desktop-end.png" || true
kill "$pid" 2>/dev/null || true; sleep 3; kill -9 "$pid" 2>/dev/null || true
cat "$out/driver-$label.log"
