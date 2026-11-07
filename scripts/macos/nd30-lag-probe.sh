#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Time field switching in the ND30 wizard of a macOS dmg, per extension variant. Evidence only.
#   nd30-lag-probe.sh <HSTOffice_*.dmg> <out-dir> <variant...>
# Variants (python edits on a copy of the app, then ad-hoc signed):
#   shipped    - extension as in the dmg (refresh() timed into refresh-<variant>.log)
#   nokeys     - shipped without the wizard's toolkit-wide key handler
#   norefresh  - shipped with refresh() reduced to "return True" (no validation, labels or preview)
#   fix        - the wizard files of this checkout (wizard_nd30.py, wizard_type_picker.py, dialogs.py, nd30_preview.py)
set -Eeuo pipefail
[ $# -ge 3 ] || { echo "usage: $0 <dmg> <out-dir> <variant...>" >&2; exit 64; }
dmg="$1"; out="$2"; shift 2; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/base.app"; hdiutil detach "$mnt" >/dev/null
brew list cliclick >/dev/null 2>&1 || brew install cliclick >"$out/brew-cliclick.log" 2>&1
. "$here/probe-lib.sh"
sw_vers >"$out/system.txt"; sysctl -n machdep.cpu.brand_string >>"$out/system.txt" 2>/dev/null || true
system_profiler SPDisplaysDataType >>"$out/system.txt" 2>/dev/null || true
for variant in "$@"; do
  app="$work/$variant/HST Office.app"; mkdir -p "$work/$variant"; ditto "$work/base.app" "$app"
  ext="$(find "$app/Contents" -type d -path '*hst-vietnamese-tools/python/hst_office' | head -1)"
  echo "$variant: $ext" >>"$out/variants.txt"
  python3 -I - "$ext" "$variant" "$repo" <<'PY'
import os, re, shutil, sys
ext, variant, repo = sys.argv[1:4]
def edit(name, old, new):
    path = os.path.join(ext, name)
    text = open(path, encoding="utf-8").read()
    assert old in text, (name, old)
    open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
if variant.startswith("fix"):
    src = os.path.join(repo, "extensions/hst-vietnamese-tools/python/hst_office")
    for name in ("wizard_nd30.py", "wizard_type_picker.py", "dialogs.py", "nd30_preview.py"):
        shutil.copy(os.path.join(src, name), os.path.join(ext, name))
    for name in ("vi.json", "en.json"):  # the checkout's wizard reads newer strings (duplex)
        shutil.copy(os.path.join(src, "../../locales", name), os.path.join(ext, "../../locales", name))
if variant == "nokeys":
    edit("wizard_type_picker.py", "self.toolkit.addKeyHandler(self.handler)", "pass")
if variant.endswith("wide"):  # keep the preview column on the 1024 px runner screen, as on the owner's Mac
    edit("wizard_nd30.py", "d.on_oversize = self._compact", "d.on_oversize = None")
if variant.startswith("norefresh"):
    edit("wizard_nd30.py", "    def refresh(self):\n", "    def refresh(self):\n        return True\n\n    def _unused_refresh(self):\n")
# every variant: time refresh() in the office (ms per call)
edit("wizard_nd30.py", "    def refresh(self):\n",
     "    def refresh(self):\n        import time as _t\n        _s = _t.perf_counter()\n        try:\n            return self._timed_refresh()\n"
     "        finally:\n            with open('/tmp/nd30-refresh.log', 'a') as _f:\n                _f.write('%.2f\\n' % ((_t.perf_counter() - _s) * 1000))\n\n"
     "    def _timed_refresh(self):\n")
cache = os.path.join(ext, "__pycache__")
shutil.rmtree(cache, ignore_errors=True)
PY
  bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign-$variant.log" 2>&1 || true
  profile="$work/profile-$variant"; mkdir -p "$profile"
  init_profile "$app" "$profile"
  cat >"$profile/user/registrymodifications.xcu.add" <<'XCU'
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>
XCU
  python3 -I - "$profile/user/registrymodifications.xcu" <<'PY'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
add = open(path + ".add", encoding="utf-8").read()
open(path, "w", encoding="utf-8").write(text.replace("</oor:items>", add + "</oor:items>"))
PY
  rm -f /tmp/nd30-refresh.log
  "$app/Contents/MacOS/soffice" --norestore --nologo --nodefault --accept="socket,host=localhost,port=2002;urp;" \
    "-env:UserInstallation=file://$profile" >"$out/soffice-$variant.log" 2>&1 &
  pid=$!
  sleep 10
  close_welcome "$pid" "$out/welcome-$variant.log"
  py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
  pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
  real="$(pgrep -n -f "$app/Contents/MacOS/soffice" || echo "$pid")"
  ( sleep 40; sample "$real" 20 -file "$out/sample-$variant.txt" >/dev/null 2>&1 ) &
  sampler=$!
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$(dirname "$pyuno")" perl -e 'alarm 900; exec @ARGV' "$py" "$here/${DRIVER:-nd30-lag-probe.py}" "$real" "$out" \
    "$( [ "${DRIVER:-}" = nd30-lag-probe2.py ] && dirname "$ext" || echo "$variant")" \
    >"$out/driver-$variant.log" 2>&1 || echo "driver $variant exit $?" >>"$out/driver-$variant.log"
  wait "$sampler" 2>/dev/null || true
  cp /tmp/nd30-refresh.log "$out/refresh-$variant.log" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true; sleep 3; kill -9 "$pid" 2>/dev/null || true
  pkill -9 -f "$work/$variant/" 2>/dev/null || true
  rm -rf "$work/$variant"
done
grep -h '^{' "$out"/driver-*.log | tee "$out/summary.txt" || true
