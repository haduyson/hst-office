#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Does the ND 30 wizard, opened from a Sheets tab through HST > "Văn bản hành chính", reach the screen on macOS?
#   modal-probe.sh <HSTOffice_*.dmg> <out-dir> [overlay-python-dir]
# With an overlay directory its hst_office/*.py replace the bundled extension modules (bytecode removed) before
# the bundle is ad-hoc signed: the same run compares the shipped code and a candidate fix. Evidence only.
set -Eeuo pipefail
[ $# -ge 2 ] || { echo "usage: $0 <dmg> <out-dir> [overlay]" >&2; exit 64; }
dmg="$1"; out="$2"; overlay="${3:-}"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
if [ -n "$overlay" ]; then
  target="$(find "$app/Contents" -type d -path '*hst-vietnamese-tools*/python/hst_office' | head -1)"
  echo "overlay into: $target" | tee "$out/overlay.txt"
  for f in "$overlay"/*.py; do cp "$f" "$target/"; echo "  $(basename "$f")" >>"$out/overlay.txt"; done
  find "$target" -name '*.pyc' -delete
fi
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign.log" 2>&1 || true
swiftc -O -o "$work/windows" "$here/modal-probe-windows.swift" 2>"$out/swiftc.log"
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
: > "$out/summary.md"
for mode in windowed fullscreen; do
  profile="$work/profile-$mode"
  mkdir -p "$profile/user"
  cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.hasontech.hstoffice.DefaultApps"><prop oor:name="Ask" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>
</oor:items>
XCU
  "$app/Contents/MacOS/soffice" --norestore --nologo --accept="socket,host=localhost,port=2002;urp;" \
    "-env:UserInstallation=file://$profile" >"$out/soffice-$mode.log" 2>&1 &
  pid=$!
  sleep 10
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$pyhome" perl -e 'alarm 240; exec @ARGV' "$py" "$here/modal-probe.py" \
    "$pid" "$out" "$mode" "$work/windows" "$profile" >"$out/driver-$mode.log" 2>&1 || echo "driver $mode exit $?" >>"$out/driver-$mode.log"
  cp "$profile/user/hst-office/"*.log "$out/" 2>/dev/null || true
  find "$profile" -name 'hst-diagnostics*.log' -exec cp {} "$out/diag-$mode.log" \; 2>/dev/null || true
  kill "$pid" 2>/dev/null || true; sleep 2; kill -9 "$pid" 2>/dev/null || true
  pkill -9 -x soffice 2>/dev/null || true; sleep 2
  {
    echo "### $mode"
    grep -E '"event": "(menu-click|wizard-on-screen|wizard-on-screen-after-toFront|no-wizard-top-window|menu-click-did-nothing|new-tab|wizard-on-screen-after-parent-toFront|new-document|typed-after-close|wizard-owner)' "$out/driver-$mode.log" || true
  } >>"$out/summary.md"
done
cat "$out/summary.md"
