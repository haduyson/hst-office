#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Record which spell checking services HST Office uses for Vietnamese on macOS and what each accepts.
#   spell-probe.sh <HSTOffice_*.dmg> <out-dir>
# Starts the app with a fresh profile (welcome dialog marked as shown), runs spell-probe.py over UNO with the
# bundled Python, writes spell-probe.md/json and a screenshot. Evidence only.
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
profile="$work/profile"; mkdir -p "$profile/user"
cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
"$app/Contents/MacOS/soffice" --norestore --nologo --nodefault --accept="socket,host=localhost,port=2002;urp;" \
  "-env:UserInstallation=file://$profile" >"$out/soffice.log" 2>&1 &
pid=$!
sleep 8
URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" PYTHONPATH="$app/Contents/Resources:$pyhome" \
  perl -e 'alarm 240; exec @ARGV' "$py" "$here/spell-probe.py" "$out" >"$out/driver.log" 2>&1 || echo "driver exit $?" >>"$out/driver.log"
screencapture -x "$out/desktop.png" || true
kill "$pid" 2>/dev/null || true; sleep 2; kill -9 "$pid" 2>/dev/null || true
cat "$out/driver.log"
