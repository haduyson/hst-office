#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Screenshot the HST Office Start Center of a dmg on a macOS GUI runner at several window sizes.
#   start-center-probe.sh <HSTOffice_*.dmg> <out-dir> [sizes]
# sizes: comma-separated WxH in points and/or "maximized" (default below). A first headless start stores five
# sample documents and makes them the recent ones (two pinned); the GUI start then shows the Start Center, which
# start-center-probe.py sizes, screenshots and checks (start-center.json: items outside the window, scroll bars,
# the DPI the office sees). Evidence only: a missed screenshot never fails the probe.
set -Eeuo pipefail
[ $# -ge 2 ] || { echo "usage: $0 <dmg> <out-dir> [sizes]" >&2; exit 64; }
dmg="$1"; out="$2"; sizes="${3:-960x600,1100x700,1280x800,1440x900,maximized}"
[[ "$sizes" =~ ^([0-9]+x[0-9]+|maximized)(,([0-9]+x[0-9]+|maximized))*$ ]] || { echo "bad sizes" >&2; exit 64; }
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign.log" 2>&1 || true
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
system_profiler SPDisplaysDataType >"$out/displays.txt" 2>&1 || true
profile="$work/profile"
mkdir -p "$profile/user"
# no welcome dialog (modal, it would cover the Start Center)
cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
drive() { # drive <step> [args...]: the UNO driver with the bundled Python, at most 5 minutes
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$pyhome" perl -e 'alarm 300; exec @ARGV' "$py" "$here/start-center-probe.py" "$@"
}
stop() { kill "$1" 2>/dev/null || true; sleep 3; kill -9 "$1" 2>/dev/null || true; pkill -f "UserInstallation=file://$profile" 2>/dev/null || true; sleep 2; }

accept='--accept=socket,host=localhost,port=2002;urp;'
"$app/Contents/MacOS/soffice" --headless --norestore --nologo "$accept" "-env:UserInstallation=file://$profile" \
  >"$out/soffice-seed.log" 2>&1 &
pid=$!
drive seed "$out" >"$out/driver-seed.log" 2>&1 || echo "seed exit $?" >>"$out/driver-seed.log"
stop "$pid"

"$app/Contents/MacOS/soffice" --norestore --nologo "$accept" "-env:UserInstallation=file://$profile" \
  >"$out/soffice-gui.log" 2>&1 &
pid=$!
sleep 12
drive shoot "$out" "$sizes" >"$out/driver-shoot.log" 2>&1 || echo "shoot exit $?" >>"$out/driver-shoot.log"
stop "$pid"
cat "$out/driver-seed.log" "$out/driver-shoot.log"
ls -l "$out"
