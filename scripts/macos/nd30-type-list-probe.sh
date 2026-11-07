#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# ND30 "Loại văn bản" list on macOS: the dmg as built, then with this checkout's extension. Evidence only.
#   nd30-type-list-probe.sh <dmg> <out-dir> <oxt>
set -Eeuo pipefail
dmg="$1"; out="$2"; oxt="$3"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/base.app"; hdiutil detach "$mnt" >/dev/null
brew list cliclick >/dev/null 2>&1 || brew install cliclick >"$out/brew.log" 2>&1
. "$here/probe-lib.sh"
for label in beta5 checkout; do
  app="$work/$label/HST Office.app"; mkdir -p "$work/$label"; ditto "$work/base.app" "$app"
  ext="$(find "$app/Contents" -type d -name hst-vietnamese-tools -path '*extensions*' | head -1)"
  if [ "$label" = checkout ]; then
    rm -rf "$ext"; mkdir -p "$ext"; ditto -x -k "$oxt" "$ext"
  fi
  bash "$here/adhoc-sign.sh" "$app" >"$out/sign-$label.log" 2>&1 || true
  profile="$work/profile-$label"; mkdir -p "$profile"
  init_profile "$app" "$profile"
  python3 -I - "$profile/user/registrymodifications.xcu" <<'PY'
import sys
p = sys.argv[1]
add = ('<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>'
       '<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>')
t = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8").write(t.replace("</oor:items>", add + "</oor:items>"))
PY
  "$app/Contents/MacOS/soffice" --norestore --nologo --nodefault --accept="socket,host=localhost,port=2002;urp;" \
    "-env:UserInstallation=file://$profile" >"$out/soffice-$label.log" 2>&1 &
  pid=$!
  sleep 10
  close_welcome "$pid" "$out/welcome-$label.log"
  osascript -e "tell application \"System Events\" to set frontmost of (first process whose unix id is $pid) to true" || true
  py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
  pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$(dirname "$pyuno")" perl -e 'alarm 400; exec @ARGV' "$py" "$here/nd30-type-list-probe.py" "$out" "$label" "$ext/python" \
    >"$out/driver-$label.log" 2>&1 || echo "driver exit $?" >>"$out/driver-$label.log"
  kill "$pid" 2>/dev/null || true; sleep 3; pkill -9 -f "$work/$label/" 2>/dev/null || true
done
cat "$out"/driver-*.log
