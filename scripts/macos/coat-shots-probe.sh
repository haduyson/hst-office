#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Screenshots of the HST coat (frame and sample dialogs) of a macOS dmg, without the coat (HST_UI_COAT=0) and
# with it, in light and dark appearance.
#   coat-shots-probe.sh <HSTOffice_*.dmg> <out-dir>
# Evidence only: never fails on a missed shot, only when the app cannot be prepared.
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign.log" 2>&1 || true
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
port=2002
for theme in light dark; do
  if [ "$theme" = dark ]; then defaults write -g AppleInterfaceStyle -string Dark; appearance=2
  else defaults delete -g AppleInterfaceStyle 2>/dev/null || true; appearance=1; fi
  for coat in before after; do
    look="$coat-$theme"; profile="$work/profile-$look"; mkdir -p "$profile/user"
    cat >"$profile/user/registrymodifications.xcu" <<XCU
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Appearance"><prop oor:name="ApplicationAppearance" oor:op="fuse"><value>$appearance</value></prop></item>
<item oor:path="/org.openoffice.Office.HSTUpdate"><prop oor:name="AutoCheck" oor:op="fuse"><value>false</value></prop></item>
</oor:items>
XCU
    HST_UI_COAT=$([ "$coat" = before ] && echo 0 || echo 1) LANG=vi_VN.UTF-8 LC_ALL=vi_VN.UTF-8 \
      "$app/Contents/MacOS/soffice" --norestore --nologo --nodefault --accept="socket,host=127.0.0.1,port=$port;urp;" \
      "-env:UserInstallation=file://$profile" >"$out/soffice-$look.log" 2>&1 &
    pid=$!
    sleep 10
    URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
      PYTHONPATH="$app/Contents/Resources:$pyhome" perl -e 'alarm 600; exec @ARGV' "$py" "$here/coat-shots-probe.py" \
      "$pid" "$port" "$out" "$look" >"$out/driver-$look.log" 2>&1 || echo "driver $look exit $?" >>"$out/driver-$look.log"
    kill "$pid" 2>/dev/null || true; sleep 3; kill -9 "$pid" 2>/dev/null || true
    port=$((port + 1))
  done
done
defaults delete -g AppleInterfaceStyle 2>/dev/null || true
ls -l "$out"
