#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# End-to-end probe of the macOS "Cập nhật ngay" (CI only; evidence, never a release gate).
#   update-e2e-probe.sh <installed.dmg> <target.dmg> <scenario> <out-dir>
# The app of <installed.dmg> is copied to /Applications (as a user drags it), started like a user's with a document,
# and org.hst.office.update:Install is dispatched on the document (update-e2e-probe.py). The published manifest is
# read; <target.dmg> waits verified in the update cache, so nothing is downloaded. Scenarios:
#   shipped       the installed app's own updater code
#   branch        this checkout's updater code, imported by the same installed app
#   shipped-root  shipped code, /Applications copy owned by root (administrator password path)
#   branch-root   branch code, root-owned copy
# KEEP_WELCOME=1: the welcome dialog opens at the start and stays open. CLOSE_WELCOME=1: closed before the update.
# PRETEND=<release>: reported to the update check as the running release (an up-to-date app is offered the target).
set -uo pipefail
[ $# -eq 4 ] || { echo "usage: $0 <installed.dmg> <target.dmg> <scenario> <out-dir>" >&2; exit 64; }
installed_dmg="$1"; target_dmg="$2"; scenario="$3"; out="$4"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
# shellcheck source=scripts/macos/probe-lib.sh
. "$here/probe-lib.sh"
mkdir -p "$out"; work="$(mktemp -d)"; app="/Applications/HST Office.app"
cache="$HOME/Library/Caches/HSTOffice/update"
summary="$out/summary.md"
note() { printf -- '- %s\n' "$*" | tee -a "$summary"; }
stop_all() {  # only the probe's own offices: soffice of the /Applications copy and of the driver copy
  pkill -f "HST Office.app/Contents/MacOS/soffice" 2>/dev/null || :
  sleep 3; pkill -9 -f "HST Office.app/Contents/MacOS/soffice" 2>/dev/null || :
}
attach() { hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$2" "$1" >/dev/null; }

stop_all
sudo rm -rf "$app" "$app.hst-new" "$app.hst-old"; rm -rf "$cache"; mkdir -p "$cache"
mnt="$work/mnt"; mkdir -p "$mnt"; attach "$installed_dmg" "$mnt"
ditto "$mnt/HST Office.app" "$app"; ditto "$mnt/HST Office.app" "$work/driver.app"; hdiutil detach "$mnt" >/dev/null
case "$scenario" in *-root) sudo chown -R root:wheel "$app" ;; esac
installed_rel="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$app/Contents/Info.plist" 2>/dev/null)"
note "scenario $scenario on macOS $(sw_vers -productVersion) $(uname -m): installed $(defaults read "$app/Contents/Info.plist" CFBundleShortVersionString) ($installed_rel) owner $(stat -f %Su:%Sg "$app")"
cp "$target_dmg" "$cache/$(basename "$target_dmg")"

drv="$work/driver.app"
py="$(find "$drv/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyhome="$(dirname "$(find "$drv/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)")"
profile="$work/profile"; init_profile "$app" "$profile"; python3 "$here/probe-profile.py" "$profile" --shown "$([ -n "${KEEP_WELCOME:-}" ] && echo false || echo true)" --no-tip
printf '%s\n' '<item oor:path="/org.hasontech.hstoffice.DefaultApps"><prop oor:name="Ask" oor:op="fuse"><value>false</value></prop></item>' \
  | perl -0pi -e 'BEGIN { $item = <STDIN> } s|</oor:items>|$item</oor:items>|' "$profile/user/registrymodifications.xcu"
document="$work/probe.rtf"; printf '{\\rtf1\\ansi HST update probe\\par}\n' >"$document"
code=""; case "$scenario" in branch*) code="$repo/extensions/hst-vietnamese-tools/python" ;; esac
args=(--app "$app" --profile "$profile" --out "$out/$scenario.json" --pipe "hste2e$$" --pretend "${PRETEND:-}")
[ -n "$code" ] && args+=(--code "$code")
[ -n "$document" ] && args+=(--document "$document")
[ -n "${CLOSE_WELCOME:-}" ] && args+=(--close-welcome)
PYTHONDONTWRITEBYTECODE=1 URE_BOOTSTRAP="vnd.sun.star.pathname:$drv/Contents/Resources/fundamentalrc" \
  PYTHONPATH="$drv/Contents/Resources:$pyhome" perl -e 'alarm 900; exec @ARGV' "$py" "$here/update-e2e-probe.py" "${args[@]}" \
  >"$out/$scenario.log" 2>&1
note "$scenario driver exit $?; version after: $(defaults read "$app/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null)"
cp "$cache/update.log" "$out/$scenario-update.log" 2>/dev/null || note "$scenario: no update.log"
[ -f "$cache/update-result.json" ] && cp "$cache/update-result.json" "$out/$scenario-update-result.json"
pgrep -lf 'MacOS/soffice' >"$out/$scenario-processes.txt" || note "$scenario: no office running at the end"
stop_all; sudo rm -rf "$work" "$app"; rm -rf "$cache"
