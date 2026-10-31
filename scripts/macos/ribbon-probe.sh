#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Screenshot the Writer, Sheets and Slides ribbon of an HST Office dmg on a macOS GUI runner, in light and dark
# appearance, with the shipped defaults and with a ribbon-colour override in the profile.
#   ribbon-probe.sh <HSTOffice_*.dmg> <out-dir> [transparency-override]
# The override is written to Office.Common/Misc/NotebookbarColorTransparency (255 = no module tint). Evidence
# only: a missed screenshot never fails the probe, only an app that cannot be prepared does.
set -Eeuo pipefail
[ $# -ge 2 ] || { echo "usage: $0 <dmg> <out-dir> [transparency]" >&2; exit 64; }
dmg="$1"; out="$2"; override="${3:-255}"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign.log" 2>&1 || { echo "ad-hoc sign failed" >&2; exit 1; }

seed_profile() { # seed_profile <profile> <transparency|default>
  mkdir -p "$1/user"
  { echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    echo '<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>'
    echo '<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>'
    [ "$2" = default ] || echo "<item oor:path=\"/org.openoffice.Office.Common/Misc\"><prop oor:name=\"NotebookbarColorTransparency\" oor:op=\"fuse\"><value>$2</value></prop></item>"
    echo '</oor:items>'; } >"$1/user/registrymodifications.xcu"
}

shoot() { # shoot <appearance light|dark> <variant> <module>
  local appearance="$1" variant="$2" module="$3" profile="$work/profile-$2-$1"
  [ -d "$profile" ] || seed_profile "$profile" "$([ "$variant" = default ] && echo default || echo "$override")"
  "$app/Contents/MacOS/soffice" --norestore --nologo "--$module" "-env:UserInstallation=file://$profile" >"$out/soffice-$variant-$appearance-$module.log" 2>&1 &
  local pid=$!
  sleep 25
  screencapture -x "$out/$module-$variant-$appearance.png" || true
  kill "$pid" 2>/dev/null || true; sleep 2; kill -9 "$pid" 2>/dev/null || true
  pkill -f "UserInstallation=file://$profile" 2>/dev/null || true
}

for appearance in light dark; do
  if [ "$appearance" = dark ]; then defaults write -g AppleInterfaceStyle -string Dark; else defaults delete -g AppleInterfaceStyle 2>/dev/null || true; fi
  sleep 2
  for variant in default override; do
    for module in writer calc impress; do shoot "$appearance" "$variant" "$module"; done
  done
done
defaults delete -g AppleInterfaceStyle 2>/dev/null || true
ls -l "$out"
