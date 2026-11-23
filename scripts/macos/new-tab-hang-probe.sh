#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Time "open another tab" on macOS the way a user starts the app (LaunchServices, Start Center first, no
# --nodefault): Command-N, File > New, the tab strip "+" and Finder-style opens, in Writer and Sheets.
#   new-tab-hang-probe.sh <HSTOffice_*.dmg> <out-dir>
# A step that takes longer than a few seconds is sampled (sample <pid> 10). Evidence only.
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/macos/probe-lib.sh
. "$here/probe-lib.sh"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
xattr -dr com.apple.quarantine "$app" 2>/dev/null || true
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist" >"$out/version.txt" || true
sw_vers >"$out/sw_vers.txt"; system_profiler SPDisplaysDataType >"$out/displays.txt" 2>&1 || true
brew list cliclick >/dev/null 2>&1 || brew install cliclick >"$out/brew-cliclick.log" 2>&1 || true
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
: >"$out/summary.md"
for scenario in writer calc-from-start-center; do
  profile="$work/profile-$scenario"; mkdir -p "$profile/user"
  cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
  init_profile "$app" "$profile"
  # Like a Dock/Finder start: LaunchServices, no --nodefault, so the Start Center comes first (tdf#41775).
  # A pipe (not a socket) avoids the local-network alert. Bundle variables of this shell are not passed on.
  env -u URE_BOOTSTRAP -u PYTHONPATH -u PYTHONHOME open -n -a "$app" --args --norestore \
    "-env:UserInstallation=file://$profile" "--accept=pipe,name=hstnewtab$scenario;urp;"
  pid=""
  for _ in $(seq 1 60); do
    pid="$(pgrep -n -x soffice || true)"; [ -n "$pid" ] && break; sleep 1
  done
  [ -n "$pid" ] || { echo "no soffice for $scenario" | tee -a "$out/summary.md"; continue; }
  sleep 12
  pid="$(pgrep -n -x soffice || echo "$pid")" # a first start may restart once
  echo "$pid" >"$out/pid-$scenario.txt"
  screencapture -x "$out/$scenario-00-launch.png" || true
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" PYTHONPATH="$app/Contents/Resources:$pyhome" \
    perl -e 'alarm 1500; exec @ARGV' "$py" "$here/new-tab-hang-probe.py" "$pid" "$out" "$scenario" "hstnewtab$scenario" "$app" \
    >"$out/driver-$scenario.log" 2>&1 || echo "driver $scenario exit $?" >>"$out/driver-$scenario.log"
  screencapture -x "$out/$scenario-99-end.png" || true
  pid="$(pgrep -n -x soffice || true)"
  if [ -n "$pid" ]; then sample "$pid" 3 -file "$out/$scenario-final-sample.txt" >/dev/null 2>&1 || true; fi
  pkill -x soffice 2>/dev/null || true; sleep 3; pkill -9 -x soffice 2>/dev/null || true
  grep '^RESULT' "$out/driver-$scenario.log" | sed 's/^RESULT /- /' >>"$out/summary.md" || true
done
cat "$out/summary.md"
