#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Tab strip "+" probe: fs-new-tab-probe.sh <dmg> <out-dir> <adopter: on|off> [tips: on|off]
# Starts the app like a user (LaunchServices, Start Center first), per layout writer-fs and both-fs. Evidence only.
set -Eeuo pipefail
[ $# -ge 3 ] || { echo "usage: $0 <dmg> <out-dir> <on|off> [on|off]" >&2; exit 64; }
dmg="$1"; out="$2"; adopter="$3"; tips="${4:-on}"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/macos/probe-lib.sh
. "$here/probe-lib.sh"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
xattr -dr com.apple.quarantine "$app" 2>/dev/null || true
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$app/Contents/Info.plist" >"$out/version.txt" || true
brew list cliclick >/dev/null 2>&1 || brew install cliclick >"$out/brew-cliclick.log" 2>&1 || true
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
: >"$out/summary.md"
for layout in fullscreen windowed; do
  label="$layout-adopter-$adopter-tips-$tips"
  profile="$work/profile-$layout"; mkdir -p "$profile/user"
  cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
  if [ "$tips" = off ]; then
    sed -i '' 's#</oor:items>#<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>\n</oor:items>#' "$profile/user/registrymodifications.xcu"
  fi
  init_profile "$app" "$profile"
  env -u URE_BOOTSTRAP -u PYTHONPATH -u PYTHONHOME open -n -a "$app" --args --norestore \
    "-env:UserInstallation=file://$profile" "--accept=pipe,name=hstfs$layout;urp;"
  pid=""
  for _ in $(seq 1 60); do pid="$(pgrep -n -x soffice || true)"; [ -n "$pid" ] && break; sleep 1; done
  [ -n "$pid" ] || { echo "- $label: no soffice" >>"$out/summary.md"; continue; }
  sleep 12; pid="$(pgrep -n -x soffice || echo "$pid")"
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" PYTHONPATH="$app/Contents/Resources:$pyhome" \
    perl -e 'alarm 600; exec @ARGV' "$py" "$here/fs-new-tab-probe.py" "$pid" "$out" "$label" "hstfs$layout" "$profile" \
    "$layout" "$adopter" >"$out/driver-$label.log" 2>&1 || echo "driver exit $?" >>"$out/driver-$label.log"
  screencapture -x "$out/$label-99-end.png" || true
  cp "$profile/user/hst-office"*.log "$out/" 2>/dev/null || true
  find "$profile/user" -name '*.log' -newer "$out/version.txt" -exec cp {} "$out/" \; 2>/dev/null || true
  pkill -x soffice 2>/dev/null || true; sleep 3; pkill -9 -x soffice 2>/dev/null || true; sleep 2
  grep '^RESULT' "$out/driver-$label.log" | sed 's/^RESULT /- /' >>"$out/summary.md" || echo "- $label: no result" >>"$out/summary.md"
done
cat "$out/summary.md"
