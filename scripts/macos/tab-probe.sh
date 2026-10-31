#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Time and record HST Office document-tab actions on macOS, windowed and in native full screen.
#   tab-probe.sh <HSTOffice_*.dmg> <out-dir>
# Per mode: starts the app, samples its windows at 50 Hz (tab-probe-sampler.swift), records the screen
# (screencapture -v when permitted, else screenshots), drives tabs over UNO (tab-probe.py) and writes
# summary.md. Evidence only: never fails on a measurement, only when the app cannot be started.
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign.log" 2>&1 || true
swiftc -O -o "$work/sampler" "$here/tab-probe-sampler.swift" 2>"$out/swiftc.log"
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
{ echo "python: $py"; echo "pyuno: $pyuno"; find "$app/Contents" -name 'uno.py' -o -name 'fundamentalrc'; } >"$out/python.txt"
pyhome="$(dirname "$pyuno")"
screencapture -x "$out/desktop-before.png" || true
: > "$out/summary.md"
for mode in windowed fullscreen; do
  profile="$work/profile-$mode"
  mkdir -p "$profile/user"
  # no welcome dialog (modal, blocks UNO)
  cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
  "$app/Contents/MacOS/soffice" --norestore --nologo --nodefault --accept="socket,host=localhost,port=2002;urp;" \
    "-env:UserInstallation=file://$profile" >"$out/soffice-$mode.log" 2>&1 &
  pid=$!
  sleep 8
  # The welcome dialog is modal and blocks UNO: close it (accessibility first, then a real click on
  # its red close button at the top left of the window).
  timeout_osa() { perl -e 'alarm 20; exec @ARGV' osascript "$@"; }
  timeout_osa -e "tell application \"System Events\" to tell (first process whose unix id is $pid)
    set frontmost to true
    delay 1
    repeat with w in windows
      try
        click (first button of w whose subrole is \"AXCloseButton\")
      end try
    end repeat
  end tell" >"$out/welcome-osascript-$mode.log" 2>&1 || echo "osascript exit $?" >>"$out/welcome-osascript-$mode.log"
  sleep 1
  screencapture -x "$out/welcome-after-osa-$mode.png" || true
  screencapture -v -V 150 "$out/screen-$mode.mov" 2>"$out/screencapture-$mode.log" &
  rec=$!
  origin="$(python3 -c 'import time;print(int(time.time()*1000))')"
  echo "$origin" >"$out/sampler-start-$mode.txt"
  "$work/sampler" "$pid" 140 >"$out/samples-$mode.csv" 2>"$out/sampler-$mode.log" &
  sampler=$!
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$pyhome" perl -e 'alarm 300; exec @ARGV' "$py" "$here/tab-probe.py" "$pid" "$out" "$mode" \
    >"$out/driver-$mode.log" 2>&1 || echo "driver $mode exit $?" >>"$out/driver-$mode.log"
  screencapture -x "$out/desktop-after-$mode.png" || true
  kill "$sampler" 2>/dev/null || true; wait "$sampler" 2>/dev/null || true
  kill -INT "$rec" 2>/dev/null || true; wait "$rec" 2>/dev/null || true; sleep 2
  kill "$pid" 2>/dev/null || true; sleep 2; kill -9 "$pid" 2>/dev/null || true
  python3 -I "$here/tab-probe-summary.py" "$out" "$mode" "$pid" >>"$out/summary.md" 2>>"$out/summary-errors.log" || true
done
cat "$out/summary.md"
