#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# macOS probe of the launchers HST Writer, HST Sheets and HST Slides (scripts/macos/make-app-launchers.py) on a GUI
# runner: install the dmg's app into /Applications, check each launcher bundle (module, icon, signature, Gatekeeper
# when Developer ID signed), then open them the way the Dock does (Launch Services) and check over UNO that the right
# document opens, from a stopped office and into a running one (one office process, no launcher left running).
# Then "Thêm vào Dock" (hst_office.app_shortcuts) pins the three launchers in this runner's Dock. Last, HST Base:
# no launcher and no File ▸ New entry, but an .odb still opens.
#   app-launchers-probe.sh <dmg> <out-dir>          writes <out-dir>/summary.md; exit 1 when a check fails
set -uo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
app="/Applications/HST Office.app"
mkdir -p "$out"
summary="$out/summary.md"
: > "$summary"
fails=0
check() { # check <name> <command...>: one PASS/FAIL line per check
  local name="$1"; shift
  if "$@" >>"$out/checks.log" 2>&1; then echo "- PASS $name" | tee -a "$summary"
  else echo "- FAIL $name" | tee -a "$summary"; fails=$((fails + 1)); fi
}

mnt="$(mktemp -d)"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null || { echo "cannot mount $dmg" >&2; exit 1; }
rm -rf "$app"
ditto "$mnt/HST Office.app" "$app"; rc=$?
hdiutil detach "$mnt" >/dev/null; rmdir "$mnt"
[ "$rc" -eq 0 ] || { echo "copy to /Applications failed" >&2; exit 1; }
echo "## HST Writer, HST Sheets, HST Slides launchers" >> "$summary"

signed_dev_id=false
codesign -dvv "$app" 2>&1 | grep -q '^Authority=Developer ID Application' && signed_dev_id=true
plist_is() { [ "$(/usr/libexec/PlistBuddy -c "Print :$2" "$1/Contents/Info.plist")" = "$3" ]; }
for entry in "HST Writer:writer" "HST Sheets:calc" "HST Slides:impress"; do
  name="${entry%%:*}"; module="${entry#*:}"; launcher="$app/Contents/Helpers/$name.app"
  check "$name.app exists" test -x "$launcher/Contents/MacOS/hst-app-launcher"
  check "$name.app opens --$module" plist_is "$launcher" HSTOfficeModule "$module"
  check "$name.app is named $name" plist_is "$launcher" CFBundleDisplayName "$name"
  check "$name.app has its icon" test -s "$launcher/Contents/Resources/app.icns"
  check "$name.app signature is valid" codesign --verify --strict --verbose=2 "$launcher"
  codesign -dvvv "$launcher" >"$out/codesign-$module.txt" 2>&1 || true
  if [ "$signed_dev_id" = true ]; then
    check "$name.app passes Gatekeeper" spctl -a -t exec -vv "$launcher"
  fi
done
check "HST Office.app signature is still valid with the launchers inside" codesign --verify --deep --strict "$app"

# Office: default profile (the launchers cannot pass -env), created headless first, then seeded.
raw="$(sed -n 's/^UserInstallation=//p' "$app/Contents/Resources/bootstraprc" | head -1)"
profile="${raw/\$SYSUSERCONFIG/$HOME/Library/Application Support}"
profile="${profile#file://}"
echo "profile: $profile" >> "$out/checks.log"
for _ in 1 2 3; do
  "$app/Contents/MacOS/soffice" --headless --norestore --terminate_after_init >>"$out/profile-init.log" 2>&1 && break
done
check "probe profile seeded (no start-up question, UNO pipe)" python3 -I "$here/app-launchers-probe.py" seed "$profile"
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
uno() { # uno <args...>: the helper under the bundled python with pyuno
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$(dirname "$pyuno")" perl -e 'alarm 200; exec @ARGV' "$py" "$here/app-launchers-probe.py" "$@"
}
soffices() { pgrep -f "$app/Contents/MacOS/soffice" | wc -l | tr -d ' '; }
no_launcher_left() { ! pgrep -f "Contents/Helpers/.*\.app/Contents/MacOS/hst-app-launcher"; }
one_office() { [ "$(soffices)" = 1 ]; }
launch() { open "$app/Contents/Helpers/$1.app"; }
quit_office() {
  uno quit >>"$out/checks.log" 2>&1
  for _ in $(seq 1 30); do [ "$(soffices)" = 0 ] && return 0; sleep 1; done
  pkill -TERM -f "$app/Contents/MacOS/soffice"; sleep 3; pkill -KILL -f "$app/Contents/MacOS/soffice"; return 1
}
opens() { # opens <launcher> <documents expected afterwards>
  launch "$1" && uno wait "$2" --timeout 120 >>"$out/checks.log" 2>&1
}

check "HST Writer opens Writer when HST Office is not running" opens "HST Writer" writer
check "HST Sheets opens a spreadsheet in the running office" opens "HST Sheets" writer,calc
check "HST Slides opens a presentation in the running office" opens "HST Slides" writer,calc,impress
sleep 3
check "one office process after three launchers" one_office
check "no launcher left running" no_launcher_left
screencapture -x "$out/three-apps.png" 2>/dev/null || true
check "office closed" quit_office
check "HST Sheets opens Sheets when HST Office is not running" opens "HST Sheets" calc
check "office closed after HST Sheets" quit_office
check "HST Slides opens Slides when HST Office is not running" opens "HST Slides" impress
check "office closed after HST Slides" quit_office

# Thêm vào Dock: the extension's own code (no dialog), then the Dock settings must hold the three launchers.
dock_add() {
  python3 -I -c '
import sys
sys.path.insert(0, sys.argv[2])
from hst_office import app_shortcuts as s
launchers, missing = s.dock_status(sys.argv[1])
print("missing before:", [n for n, _p in missing])
s.add_to_dock(missing)
_launchers, left = s.dock_status(sys.argv[1])
print("missing after:", [n for n, _p in left])
sys.exit(1 if left else 0)' "$app" "$repo/extensions/hst-vietnamese-tools/python"
}
check "Thêm vào Dock pins HST Writer, HST Sheets and HST Slides" dock_add
sleep 5
screencapture -x "$out/dock.png" 2>/dev/null || true
defaults export com.apple.dock - > "$out/dock.plist" 2>/dev/null || true
check "HST Writer opens again after the Dock restart" opens "HST Writer" writer

# HST Base is offered nowhere, but an .odb still opens (hst-hide-base-launchers.patch).
check "no HST Base launcher in the bundle" test ! -e "$app/Contents/Helpers/HST Base.app"
check "File ▸ New (and the Dock menu) offers no database" uno no-base-menu
check "probe database stored" uno make-odb "$out/probe.odb"
check "office closed before the .odb" quit_office
odb_opens() { open -a "$app" "$out/probe.odb" && uno wait base --timeout 120 >>"$out/checks.log" 2>&1; }
check "an .odb opens in HST Office" odb_opens
quit_office >/dev/null 2>&1 || echo "office did not close cleanly" >>"$out/checks.log"

echo "" >> "$summary"
echo "$fails failed check(s); log: checks.log" >> "$summary"
cat "$summary"
[ "$fails" -eq 0 ]
