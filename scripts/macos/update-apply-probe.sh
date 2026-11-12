#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Evidence probe of the macOS "Cập nhật ngay" install step with the published dmgs (diagnosis only).
#   update-apply-probe.sh <old.dmg> <old-release> <new.dmg> <new-release> <out-dir>
# A  old app in /Applications runs ITS OWN launch_and_quit (target: new dmg): does the office quit, does the helper swap?
# C  helper only (this checkout's build_helper) old -> new: a dummy PID exits, the helper swaps and relaunches.
# B  new app in /Applications runs ITS OWN launch_and_quit (target: old dmg, standing in for a later release).
set -uo pipefail
[ $# -eq 5 ] || { echo "usage: $0 <old.dmg> <old-release> <new.dmg> <new-release> <out-dir>" >&2; exit 64; }
old_dmg="$1"; old_rel="$2"; new_dmg="$3"; new_rel="$4"; out="$5"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
# shellcheck source=probe-lib.sh
. "$here/probe-lib.sh"
mkdir -p "$out"; work="$(mktemp -d)"; app="/Applications/HST Office.app"
cache="$HOME/Library/Caches/HSTOffice/update"; mkdir -p "$cache"
summary="$out/summary.md"; printf '# macOS update apply probe\n\n- macOS %s\n' "$(sw_vers -productVersion)" >"$summary"
note() { printf -- '- %s\n' "$*" | tee -a "$summary"; }

install_app() {  # install_app <dmg>: the app of <dmg> copied to /Applications the way a user drags it
  local mnt="$work/mnt"; mkdir -p "$mnt"
  stop_all
  rm -rf "$app"
  hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$1" >/dev/null
  ditto "$mnt/HST Office.app" "$app"; hdiutil detach "$mnt" >/dev/null
  note "installed $(defaults read "$app/Contents/Info.plist" CFBundleShortVersionString) owner $(stat -f %Su:%Sg "$app")"
}
stop_all() {  # only the probe's own offices: every soffice of this runner's /Applications copy
  pkill -f "/Applications/HST Office.app/Contents/MacOS/soffice" 2>/dev/null || :
  sleep 3; pkill -9 -f "/Applications/HST Office.app/Contents/MacOS/soffice" 2>/dev/null || :
}
cached() {  # cached <dmg>: the verified installer where "Cập nhật ngay" leaves it
  cp "$1" "$cache/$(basename "$1")"; echo "$cache/$(basename "$1")"
}
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

# A driver copy of the old app supplies the UNO Python; /Applications is replaced under the probe.
mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$old_dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/driver.app"; hdiutil detach "$mnt" >/dev/null
drv="$work/driver.app"
py="$(find "$drv/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyhome="$(dirname "$(find "$drv/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)")"
driver() {
  PYTHONDONTWRITEBYTECODE=1 URE_BOOTSTRAP="vnd.sun.star.pathname:$drv/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$drv/Contents/Resources:$pyhome" perl -e 'alarm 900; exec @ARGV' "$py" "$here/update-apply-probe.py" "$@"
}
for dmg in "$old_dmg" "$new_dmg"; do
  mnt2="$work/m2"; mkdir -p "$mnt2"; hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt2" "$dmg" >/dev/null
  { codesign -dv --verbose=4 "$mnt2/HST Office.app" 2>&1 | grep -E '^(Identifier|TeamIdentifier|Notarization|Timestamp)'
    spctl --assess --type execute -vv "$mnt2/HST Office.app" 2>&1; xcrun stapler validate "$mnt2/HST Office.app" 2>&1 | tail -1
  } | sed "s|^|$(basename "$dmg"): |" | tee -a "$out/signatures.txt"
  hdiutil detach "$mnt2" >/dev/null
done

phase() {  # phase <name> <installed dmg> <target dmg> <from> <to>
  install_app "$2"; rm -f "$cache/update.log" "$cache/update-result.json"
  local profile="$work/profile-$1" target; target="$(cached "$3")"
  init_profile "$app" "$profile"; python3 "$here/probe-profile.py" "$profile" --shown true --no-tip
  driver --app "$app" --profile "$profile" --dmg "$target" --sha256 "$(sha "$target")" --release-from "$4" \
    --release-to "$5" --out "$out/phase-$1.json" --pipe "hstupd$1" >"$out/phase-$1.log" 2>&1
  note "phase $1 driver exit $?; version after: $(defaults read "$app/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null)"
  cp "$cache/update.log" "$out/phase-$1-update.log" 2>/dev/null || note "phase $1: no update.log"
  [ -f "$cache/update-result.json" ] && cp "$cache/update-result.json" "$out/phase-$1-update-result.json"
  pgrep -lf 'MacOS/soffice' >"$out/phase-$1-processes.txt" || :
  stop_all
}

phase A "$old_dmg" "$new_dmg" "$old_rel" "$new_rel"

# C: the helper alone, built by this checkout, old app -> new dmg; the "office" is a short sleep.
install_app "$old_dmg"; rm -f "$cache/update.log" "$cache/update-result.json"
target="$(cached "$new_dmg")"
dummy=$(sh -c 'sleep 4 >/dev/null 2>&1 & echo $!')  # grandchild: launchd reaps it, no zombie for kill -0
python3 - "$repo/extensions/hst-vietnamese-tools/python" "$dummy" "$target" "$(sha "$target")" "$app" "$cache" "$old_rel" "$new_rel" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from hst_office import update_helper_cmd as cmd, update_launch as launch
pid, dmg, digest, app, cache, frm, to = int(sys.argv[2]), *sys.argv[3:]
helper = cmd.build_helper("Darwin", pid=pid, installer=dmg, sha256=digest, soffice=app + "/Contents/MacOS/soffice",
                          log=launch.log_path(cache), app_dest=app, release_from=frm, release_to=to)
proc = launch.spawn(cmd.argv(helper, launch.write_helper(helper, cache)), "Darwin")
print("helper exit", proc.wait(timeout=900))
PY
sleep 20
note "phase C version after: $(defaults read "$app/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null)"
cp "$cache/update.log" "$out/phase-C-update.log" 2>/dev/null || note "phase C: no update.log"
pgrep -lf 'MacOS/soffice' | tee "$out/phase-C-processes.txt" || note "phase C: no office relaunched"
stop_all

phase B "$new_dmg" "$old_dmg" "$new_rel" "$old_rel"
stop_all; rm -rf "$work" "$app" "$cache"
cat "$summary"
