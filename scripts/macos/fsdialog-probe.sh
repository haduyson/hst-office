#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# macOS native full screen: a dialog is open and another document opens (fsdialog-probe.py). Evidence only.
#   fsdialog-probe.sh <HSTOffice_*.dmg> <out-dir> [overlay-module-dir]
# With an overlay directory its *.py replace the bundled hst_office modules (bytecode removed) before the bundle is
# ad-hoc signed, so one run compares the shipped code and a candidate fix.
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
swiftc -O -o "$work/windows" "$here/fsdialog-probe-windows.swift" 2>"$out/swiftc.log"
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
: > "$out/summary.md"
for run in citation lo-dialog lo-dialog:rescue; do
  scenario="${run%%:*}"; extra="${run#*:}"; [ "$extra" = "$run" ] && extra=""
  label="${run/:/-}"
  profile="$work/profile-$label"
  mkdir -p "$profile/user" "$out/$label"
  cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.hasontech.hstoffice.DefaultApps"><prop oor:name="Ask" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.HSTUpdate"><prop oor:name="AutoCheck" oor:op="fuse"><value>false</value></prop></item>
</oor:items>
XCU
  "$app/Contents/MacOS/soffice" --norestore --nologo --accept="socket,host=localhost,port=2002;urp;" \
    "-env:UserInstallation=file://$profile" >"$out/$label/soffice.log" 2>&1 &
  pid=$!
  sleep 10
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$pyhome" perl -e 'alarm 240; exec @ARGV' "$py" "$here/fsdialog-probe.py" \
    "$pid" "$out/$label" "$scenario" "$work/windows" "$profile" "$here/fsdialog-probe-inproc.py" $extra \
    >"$out/$label/driver.log" 2>&1 || echo "driver exit $?" >>"$out/$label/driver.log"
  cp "$profile/user/hst-office/hst-office.log" "$out/$label/" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true; sleep 2; kill -9 "$pid" 2>/dev/null || true
  pkill -9 -x soffice 2>/dev/null || true; sleep 2
  {
    echo "### $label"
    grep -E '"event": "(citation-kept-typing|field-(before|after)-new-document|lo-dialog-on-screen[a-z-]*|typed-after-close|reparent|new-document:(loaded|failed)|open-after-esc|watcher|adopt-now)"' "$out/$label/driver.log" \
      | sed -E 's/"windows": \[[^]]*\]/"windows": "…"/g' | cut -c1-600 || true
    grep -E 'driver exit|Traceback|Error' "$out/$label/driver.log" | head -5 || true
  } >>"$out/summary.md"
done
cat "$out/summary.md"
