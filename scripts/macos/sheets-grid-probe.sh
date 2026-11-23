#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
# Grid of a new HST Sheets document on macOS, at 100 %, 50 % and 200 % zoom, for one dmg and one Skia mode.
#   sheets-grid-probe.sh <HSTOffice_*.dmg> <out-dir> <label> <default|raster> [direct|startcenter]
# startcenter: the app opens on its Start Center and the spreadsheet is made by the Start Center tile dispatch.
# default: no SAL_SKIA variable; raster: SAL_SKIA=raster. Evidence only: fails only when the app cannot start.
set -Eeuo pipefail
[ $# -ge 4 ] && [ $# -le 5 ] || { echo "usage: $0 <dmg> <out-dir> <label> <default|raster> [direct|startcenter]" >&2; exit 64; }
dmg="$1"; out="$2"; label="$3"; skia="$4"; mode="${5:-direct}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign-$label.log" 2>&1 || true
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
if [ "$skia" = raster ]; then export SAL_SKIA=raster; else unset SAL_SKIA; fi
echo "skia=${SAL_SKIA:-default}" >"$out/mode-$label.txt"
# --nodefault suppresses the Start Center; the startcenter mode needs it shown
nodefault=(--nodefault); [ "$mode" = startcenter ] && nodefault=()
"$app/Contents/MacOS/soffice" --norestore --nologo "${nodefault[@]}" --accept="pipe,name=hstsheetgrid;urp;" \
  "-env:UserInstallation=file://$profile" >"$out/soffice-$label.log" 2>&1 &
pid=$!
sleep 10
URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" PYTHONPATH="$app/Contents/Resources:$pyhome" \
  perl -e 'alarm 420; exec @ARGV' "$py" "$here/sheets-grid-probe.py" "$pid" "$out" "$label" "$mode" \
  >"$out/driver-$label.log" 2>&1 || echo "driver exit $?" >>"$out/driver-$label.log"
kill "$pid" 2>/dev/null || true; sleep 3; kill -9 "$pid" 2>/dev/null || true
cat "$out/driver-$label.log"
