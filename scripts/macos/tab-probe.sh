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
echo "python: $py" >"$out/python.txt"
screencapture -x "$out/desktop-before.png" || true
: > "$out/summary.md"
for mode in windowed fullscreen; do
  profile="$work/profile-$mode"
  "$app/Contents/MacOS/soffice" --norestore --nologo --nodefault --accept="socket,host=localhost,port=2002;urp;" \
    "-env:UserInstallation=file://$profile" >"$out/soffice-$mode.log" 2>&1 &
  pid=$!
  sleep 8
  ( screencapture -v -V 150 "$out/screen-$mode.mov" 2>"$out/screencapture-$mode.log" || true ) &
  rec=$!
  origin="$(python3 -c 'import time;print(int(time.time()*1000))')"
  echo "$origin" >"$out/sampler-start-$mode.txt"
  "$work/sampler" "$pid" 140 >"$out/samples-$mode.csv" 2>"$out/sampler-$mode.log" &
  sampler=$!
  PYTHONPATH="$app/Contents/Resources" perl -e 'alarm 300; exec @ARGV' "$py" "$here/tab-probe.py" "$pid" "$out" "$mode" \
    >"$out/driver-$mode.log" 2>&1 || echo "driver $mode exit $?" >>"$out/driver-$mode.log"
  screencapture -x "$out/desktop-after-$mode.png" || true
  kill "$sampler" 2>/dev/null || true; wait "$sampler" 2>/dev/null || true
  kill -INT "$rec" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true; sleep 2; kill -9 "$pid" 2>/dev/null || true
  python3 -I "$here/tab-probe-summary.py" "$out" "$mode" "$pid" >>"$out/summary.md" 2>>"$out/summary-errors.log" || true
done
cat "$out/summary.md"
