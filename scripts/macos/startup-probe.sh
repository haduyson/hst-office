#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Time HST Office start-up on macOS with and without the welcome dialog, for the shipped extension code and
# for the extension code of this checkout (overlaid on a copy of the same bundle), cold and warm profile.
#   startup-probe.sh <HSTOffice_*.dmg> <out-dir>
# Per case: starts the app, samples its windows at 20 Hz (startup-probe-sampler.swift), takes a screenshot
# about every 0.5 s, and for welcome cases sends Return (the dialog's default "Đóng" button) through
# System Events 10 s after the first window. Writes summary.md. Evidence only: measurement failures never fail
# the probe, only an app that cannot be prepared does.
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
now_ms() { python3 -c 'import time;print(int(time.time()*1000))'; }

hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/shipped.app"; hdiutil detach "$mnt" >/dev/null
ditto "$work/shipped.app" "$work/current.app"
ext="$(dirname "$(find "$work/current.app" -path '*hst-vietnamese-tools/python/hst_office/welcome_job.py' -print -quit)")"
[ -d "$ext" ] || { echo "extension directory not found in the bundle" >&2; exit 1; }
cp "$repo"/extensions/hst-vietnamese-tools/python/hst_office/*.py "$ext/"
for variant in shipped current; do
  bash "$here/adhoc-sign.sh" "$work/$variant.app" >"$out/adhoc-sign-$variant.log" 2>&1 || { echo "ad-hoc sign failed: $variant" >&2; exit 1; }
done
swiftc -O -o "$work/sampler" "$here/startup-probe-sampler.swift" 2>"$out/swiftc.log"
screencapture -x "$out/desktop-before.png" || true
osascript -e 'tell application "System Events" to get name of first process whose frontmost is true' >"$out/system-events-check.txt" 2>&1 || true
{ echo "# macOS start-up probe"; echo; echo "host: $(sw_vers -productVersion) $(uname -m); dmg: $(basename "$dmg")"; } >"$out/summary.md"

seed_profile() { # seed_profile <profile> <shown true|false>: registry values read at the first start
  mkdir -p "$1/user"
  { echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    echo "<item oor:path=\"/org.hasontech.hstoffice.Welcome\"><prop oor:name=\"Shown\" oor:op=\"fuse\"><value>$2</value></prop></item>"
    echo '<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>'
    echo '</oor:items>'; } >"$1/user/registrymodifications.xcu"
}

run_case() { # run_case <variant> <case> <profile> <close: yes|no> <seconds>
  local variant="$1" name="$2" profile="$3" close="$4" secs="$5" dir="$out/$1-$2"
  mkdir -p "$dir"
  "$work/sampler" "$secs" >"$dir/samples.csv" 2>"$dir/sampler.log" &
  local sampler=$!
  ( end=$(( $(date +%s) + secs )); while [ "$(date +%s)" -lt "$end" ]; do
      screencapture -x -t jpg "$dir/shot-$(now_ms).jpg" 2>/dev/null || true; sleep 0.3; done ) &
  local shots=$!
  now_ms >"$dir/launch.txt"
  "$work/$variant.app/Contents/MacOS/soffice" --norestore --nologo "-env:UserInstallation=file://$profile" >"$dir/soffice.log" 2>&1 &
  local pid=$!
  if [ "$close" = yes ]; then
    # first window on screen + 10 s: the dialog is up in both variants
    local first=""
    for _ in $(seq 1 600); do
      first="$(awk -F, 'NR>1 && $2!="" {print $1; exit}' "$dir/samples.csv" 2>/dev/null || true)"
      [ -z "$first" ] || break; sleep 0.1
    done
    if [ -n "$first" ]; then
      while [ "$(now_ms)" -lt $((first + 10000)) ]; do sleep 0.2; done
      screencapture -x -t jpg "$dir/before-close.jpg" || true
      now_ms >"$dir/closed.txt"
      osascript -e 'tell application "System Events" to key code 36' >"$dir/close.log" 2>&1 || echo "osascript exit $?" >>"$dir/close.log"
    fi
  fi
  wait "$sampler" 2>/dev/null || true
  kill "$shots" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true; sleep 2; kill -9 "$pid" 2>/dev/null || true
  pkill -f "UserInstallation=file://$profile" 2>/dev/null || true
  python3 -I "$here/startup-probe-summary.py" "$dir" "$variant / $name" >>"$out/summary.md" 2>>"$out/summary-errors.log" || true
}

for variant in shipped current; do
  p="$work/profile-$variant-quiet"; seed_profile "$p" true
  run_case "$variant" cold-no-welcome "$p" no 35
  run_case "$variant" warm-no-welcome "$p" no 25
  p="$work/profile-$variant-welcome"; seed_profile "$p" false
  run_case "$variant" cold-welcome "$p" yes 50
  sed -i '' '/Welcome/d' "$p/user/registrymodifications.xcu" 2>/dev/null || true
  run_case "$variant" warm-welcome "$p" yes 40
done
cat "$out/summary.md"
