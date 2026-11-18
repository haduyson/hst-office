#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# macOS probe of the launchers HST Writer, HST Sheets, HST Slides, HST Draw and HST PDF (scripts/macos/
# make-app-launchers.py, hst_office/mac_app_launchers.py) on a GUI runner:
#   - the five bundles inside HST Office.app (module, icon, signature, Gatekeeper when Developer ID signed);
#   - HST Office started from the mounted .dmg copies nothing;
#   - the first start of the installed app copies all five into /Applications (Spotlight finds them) and shows the
#     one-time notice; a second start and a simulated version bump add no duplicate, the bump refreshes the copies
#     and does not bring back one the user deleted;
#   - cold and warm start through each copy opens the right module (HST PDF: its open panel, then the PDF), with one
#     HST Office in the Dock and no launcher left running; the copies keep a valid signature and carry no quarantine;
#   - the options buttons remove the copies (no copy at the next start) and add them again;
#   - with HST Office gone, a copy offers to move itself to the Trash;
#   - "Thêm vào Dock" and the HST Base checks of earlier releases.
# The office is quit as a user quits it (Quit Apple Event); a kill fails the check.
#   app-launchers-probe.sh <dmg> <out-dir>          writes <out-dir>/summary.md; exit 1 when a check fails
set -uo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
ext_py="$repo/extensions/hst-vietnamese-tools/python"
app="/Applications/HST Office.app"
apps="/Applications"; user_apps="$HOME/Applications"
state="$HOME/Library/Application Support/HSTOffice/app-launchers.json"
names=("HST Writer" "HST Sheets" "HST Slides" "HST Draw" "HST PDF")
mkdir -p "$out"
summary="$out/summary.md"
: > "$summary"
fails=0
check() { # check <name> <command...>: one PASS/FAIL line per check
  local name="$1"; shift
  echo "== $name" >>"$out/checks.log"
  if "$@" >>"$out/checks.log" 2>&1; then echo "- PASS $name" | tee -a "$summary"
  else echo "- FAIL $name" | tee -a "$summary"; fails=$((fails + 1)); fi
}
skip() { echo "- SKIP $1" | tee -a "$summary"; }
shot() { screencapture -x "$out/$1.png" 2>/dev/null || true; }

mnt="$(mktemp -d)"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null || { echo "cannot mount $dmg" >&2; exit 1; }
rm -rf "$app" "$state"
for name in "${names[@]}"; do rm -rf "${apps:?}/$name.app" "${user_apps:?}/$name.app"; done
ditto "$mnt/HST Office.app" "$app"; rc=$?
hdiutil detach "$mnt" >/dev/null; rmdir "$mnt"
[ "$rc" -eq 0 ] || { echo "copy to /Applications failed" >&2; exit 1; }
echo "## Launchers in the bundle" >> "$summary"

signed_dev_id=false
codesign -dvv "$app" 2>&1 | grep -q '^Authority=Developer ID Application' && signed_dev_id=true
plist_is() { [ "$(/usr/libexec/PlistBuddy -c "Print :$2" "$1/Contents/Info.plist")" = "$3" ]; }
modules=(writer calc impress draw pdf)
for i in "${!names[@]}"; do
  name="${names[$i]}"; module="${modules[$i]}"; launcher="$app/Contents/Helpers/$name.app"
  check "$name.app exists" test -x "$launcher/Contents/MacOS/hst-app-launcher"
  check "$name.app opens $module" plist_is "$launcher" HSTOfficeModule "$module"
  check "$name.app is named $name" plist_is "$launcher" CFBundleDisplayName "$name"
  check "$name.app has its icon" test -s "$launcher/Contents/Resources/app.icns"
  check "$name.app signature is valid" codesign --verify --strict --verbose=2 "$launcher"
  codesign -dvvv "$launcher" >"$out/codesign-$module.txt" 2>&1 || true
done
check "HST Office.app signature is still valid with the launchers inside" codesign --verify --deep --strict "$app"

# Office: default profile (the launchers cannot pass -env), created by a full headless start, then seeded. Not
# --terminate_after_init: it ends before the bundled extensions are registered (desktop/source/app/app.cxx), and the
# first real start then dropped the seeded extension settings (launcher probe run 42943021139).
raw="$(sed -n 's/^UserInstallation=//p' "$app/Contents/Resources/bootstraprc" | head -1)"
profile="${raw/\$SYSUSERCONFIG/$HOME/Library/Application Support}"
profile="${profile#file://}"
echo "profile: $profile" >> "$out/checks.log"
init="$(mktemp -d)"; : > "$init/init.txt"
for _ in 1 2 3; do
  "$app/Contents/MacOS/soffice" --headless --norestore --convert-to pdf --outdir "$init" "$init/init.txt" \
    >>"$out/profile-init.log" 2>&1 && [ -s "$init/init.pdf" ] && break
done
cp "$init/init.pdf" "$out/probe.pdf" 2>/dev/null || true
check "probe profile seeded (no start-up question, UNO pipe)" python3 -I "$here/app-launchers-probe.py" seed "$profile"
# The move question of a copy on the .dmg was answered for this release: the .dmg start below meets no modal.
release_json="$(find "$app/Contents" -path '*hst-vietnamese-tools*/data/release.json' -print -quit)"
mkdir -p "$(dirname "$state")"
python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["release"])' "$release_json" \
  > "$(dirname "$state")/move-offered" 2>>"$out/checks.log"
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
uno() { # uno <args...>: the helper under the bundled python with pyuno
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$(dirname "$pyuno")" perl -e 'alarm 200; exec @ARGV' "$py" "$here/app-launchers-probe.py" "$@"
}
bundle_id="$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$app/Contents/Info.plist")"
soffices() { pgrep -f "HST Office.app/Contents/MacOS/soffice" | wc -l | tr -d ' '; }
launchers_running() { pgrep -f "\.app/Contents/MacOS/hst-app-launcher" | wc -l | tr -d ' '; }
dock_icons() { lsappinfo list | grep -c "bundleID=\"$bundle_id\""; }
processes() { # processes <label>: the HST rows of the process table, the evidence of the counts below
  echo "-- processes $1 (soffice $(soffices), Dock $(dock_icons), launchers $(launchers_running))"
  pids="$(pgrep -d, -f 'HST (Office|Writer|Sheets|Slides|Draw|PDF)\.app/Contents/MacOS/')"
  [ -z "$pids" ] || ps -o pid,ppid,etime,command -p "$pids"
} >>"$out/processes.log" 2>&1
settled() { # a launcher hands over within a few seconds (HST Slides: while Impress's template dialog is up)
  for _ in $(seq 1 10); do
    [ "$(dock_icons)" = 1 ] && [ "$(launchers_running)" = 0 ] && { processes settled; return 0; }
    processes waiting; sleep 1
  done
  processes "not settled"; return 0
}
no_launcher_left() { [ "$(launchers_running)" = 0 ] || { processes "launcher left"; return 1; }; }
one_office() {
  if [ "$(dock_icons)" = 1 ] && [ "$(soffices)" = 1 ]; then return 0; fi
  processes "office count"; return 1
}
press_in() { # press_in <pid> <AppleScript lines...>: keys to the frontmost window of that process
  local pid="$1"; shift
  local args=(-e 'on run argv' -e 'tell application "System Events"'
              -e 'set frontmost of (first process whose unix id is (item 1 of argv as integer)) to true' -e 'delay 1')
  local line; for line in "$@"; do args+=(-e "$line"); done
  osascript "${args[@]}" -e 'end tell' -e 'end run' "$pid"
}
close_window() { # close_window <title>: an office dialog closed as a user does (Esc), checked over UNO
  local office; office="$(pgrep -o -f "HST Office.app/Contents/MacOS/soffice")" || return 1
  for _ in 1 2 3; do
    press_in "$office" 'key code 53' >>"$out/checks.log" 2>&1; sleep 2
    uno window-gone "$1" >>"$out/checks.log" 2>&1 && { processes "closed $1"; return 0; }
  done
  processes "still open: $1"; return 1
}
quit_office() { # as a user quits (Cmd-Q, the Dock's Quit: the Quit Apple Event); a kill fails
  uno frames >>"$out/checks.log" 2>&1
  osascript -e "tell application id \"$bundle_id\" to quit" >>"$out/checks.log" 2>&1
  for _ in $(seq 1 30); do [ "$(soffices)" = 0 ] && return 0; sleep 1; done
  processes "quit refused"; shot "quit-refused-$(date +%H%M%S)"; uno frames >>"$out/checks.log" 2>&1
  pkill -TERM -f "HST Office.app/Contents/MacOS/soffice"; sleep 3; pkill -KILL -f "HST Office.app/Contents/MacOS/soffice"
  return 1
}
opens() { # opens <launcher bundle> <documents expected afterwards>
  open "$1" && uno wait "$2" --timeout 120 >>"$out/checks.log" 2>&1; local rc=$?
  processes "after $1"; return "$rc"
}
pdf_opens() { # pdf_opens <HST PDF bundle>: its open panel takes the probe PDF (Go to Folder), HST PDF shows it
  open "$1" || return 1
  local pid=""
  for _ in $(seq 1 20); do pid="$(pgrep -n -f "HST PDF.app/Contents/MacOS/hst-app-launcher")" && break; sleep 0.5; done
  [ -n "$pid" ] || { echo "HST PDF did not start"; return 1; }
  sleep 3; shot "pdf-panel"
  press_in "$pid" 'keystroke "g" using {command down, shift down}' 'delay 1' "keystroke \"$out/probe.pdf\"" \
    'delay 1' 'key code 36' 'delay 2' 'key code 36' || return 1
  uno title probe.pdf --timeout 120; local rc=$?
  processes "after HST PDF"; shot "pdf-opened"; return "$rc"
}
ours_in() { # ours_in <folder>: the HST launchers there (bundle id <host>.launcher.*), one name per line
  local name id
  for name in "${names[@]}"; do
    id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$1/$name.app/Contents/Info.plist" 2>/dev/null)"
    [[ "$id" == "$bundle_id.launcher."* ]] && echo "$name"
  done
}
count_in() { ours_in "$1" | wc -l | tr -d ' '; }
copies_are() { # copies_are <n in /Applications> <n in ~/Applications>: and no hidden partial copy left
  ls -la "$apps" "$user_apps" 2>/dev/null
  [ "$(count_in "$apps")" = "$1" ] && [ "$(count_in "$user_apps")" = "$2" ] \
    && ! compgen -G "$apps/.HST *" >/dev/null
}
state_has() { python3 -I -c 'import json,sys; s=json.load(open(sys.argv[1])); print(s); sys.exit(0 if s.get(sys.argv[2]) == json.loads(sys.argv[3]) else 1)' "$state" "$1" "$2"; }
copy_valid() { codesign --verify --strict --deep --verbose=2 "$apps/$1.app" && ! xattr -p com.apple.quarantine "$apps/$1.app" 2>/dev/null; }

echo "## Not from the .dmg" >> "$summary"
# mounted under /Volumes as a user's double click mounts it (hst_office/mac_app_location.py: kind "volume")
vol="$(hdiutil attach -readonly -nobrowse -noautoopen -mountrandom /Volumes -plist "$dmg" | python3 -I -c '
import plistlib, sys
print(next(e["mount-point"] for e in plistlib.load(sys.stdin.buffer)["system-entities"] if e.get("mount-point")))')"
echo "dmg mounted at $vol" >> "$out/checks.log"
check "HST Office from the mounted .dmg opens Writer" opens "$vol/HST Office.app/Contents/Helpers/HST Writer.app" writer
sleep 10
check "HST Office from the .dmg copied no launcher and kept no state" copies_are 0 0
check "no launcher state written by the .dmg copy" test ! -e "$state"
check "office from the .dmg closed" quit_office
hdiutil detach "$vol" >/dev/null 2>&1 || hdiutil detach -force "$vol" >/dev/null 2>&1

echo "## First start of the installed app" >> "$summary"
check "HST Writer (in the bundle) opens Writer when HST Office is not running" opens "$app/Contents/Helpers/HST Writer.app" writer
check "the one-time notice is shown" uno window "Biểu tượng ứng dụng" --timeout 90
shot notice
check "first start copied all five launchers into /Applications" copies_are 5 0
check "the notice is remembered as shown" state_has notice '"shown"'
check "the notice closes" close_window "Biểu tượng ứng dụng"
for name in "${names[@]}"; do check "$name.app in /Applications: valid signature, no quarantine" copy_valid "$name"; done
if [ "$signed_dev_id" = true ]; then
  for name in "${names[@]}"; do check "$name.app in /Applications passes Gatekeeper" spctl -a -t exec -vv "$apps/$name.app"; done
else
  skip "Gatekeeper of the copies: the dmg is not Developer ID signed (signing runs on main only)"
fi
spotlight() {
  mdutil -s / ; for name in "${names[@]}"; do mdimport "$apps/$name.app"; done
  for _ in $(seq 1 45); do
    found="$(mdfind "kMDItemCFBundleIdentifier == '$bundle_id.launcher.*'" | grep -c "^$apps/HST ")"
    [ "$found" = 5 ] && return 0; sleep 2
  done
  mdfind "kMDItemCFBundleIdentifier == '$bundle_id.launcher.*'"; return 1
}
sudo -n mdutil -i on / 2>&1 | tee -a "$out/checks.log" >/dev/null || true
if mdutil -s / 2>&1 | grep -q "Indexing enabled"; then
  check "Spotlight finds the five launchers in /Applications" spotlight
else
  skip "Spotlight: indexing is disabled on this runner ($(mdutil -s / 2>&1 | tail -1))"
fi
registered() {
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -dump \
    | grep -F "$apps/HST " | grep -F ".app" | sort -u | tee "$out/lsregister.txt" | grep -qF "$apps/HST PDF.app"
}
check "Launch Services knows the copies (Launchpad, Finder)" registered

echo "## Each app, warm and cold, through the copies" >> "$summary"
check "HST Sheets opens a spreadsheet in the running office" opens "$apps/HST Sheets.app" writer,calc
uno template true >>"$out/checks.log" 2>&1
check "HST Slides opens a presentation in the running office" opens "$apps/HST Slides.app" writer,calc,impress
settled
check "the template dialog closes" close_window "Lựa chọn mẫu"
uno template false >>"$out/checks.log" 2>&1
check "HST Draw opens a drawing in the running office" opens "$apps/HST Draw.app" writer,calc,impress,draw
check "HST PDF opens the chosen PDF in the running office" pdf_opens "$apps/HST PDF.app"
settled
check "one HST Office (Dock and processes) after five launchers" one_office
check "no launcher left running" no_launcher_left
shot five-apps
check "office closed" quit_office
for entry in "HST Sheets:calc" "HST Slides:impress" "HST Draw:draw" "HST Writer:writer"; do
  name="${entry%%:*}"
  check "$name opens ${entry#*:} when HST Office is not running" opens "$apps/$name.app" "${entry#*:}"
  check "no launcher left after $name" no_launcher_left
  check "office closed after $name" quit_office
done
check "HST PDF opens the chosen PDF when HST Office is not running" pdf_opens "$apps/HST PDF.app"
check "one HST Office after HST PDF" one_office
check "office closed after HST PDF" quit_office

echo "## Second start and an update" >> "$summary"
check "HST Writer opens Writer at a later start" opens "$apps/HST Writer.app" writer
sleep 15
check "a later start adds no duplicate: still exactly five copies" copies_are 5 0
check "no second notice" uno window-gone "Biểu tượng ứng dụng"
check "office closed after the second start" quit_office
touch "$apps/HST Writer.app/Contents/Resources/probe-stale"   # gone once the copy is replaced
rm -rf "$apps/HST Draw.app"                                   # the user deleted this one in Finder
python3 -I -c 'import json,sys; p=sys.argv[1]; s=json.load(open(p)); s["version"]="1.0.2.0"; json.dump(s, open(p, "w"))' "$state"
check "HST Sheets opens after the simulated update" opens "$apps/HST Sheets.app" calc
sleep 5
check "the update refreshed the copies (stale file gone)" test ! -e "$apps/HST Writer.app/Contents/Resources/probe-stale"
check "the update kept four copies: no duplicate, the deleted HST Draw not re-added" copies_are 4 0
check "the refreshed HST Writer copy is valid" copy_valid "HST Writer"
check "no notice after the update" uno window-gone "Biểu tượng ứng dụng"

echo "## Remove and add again (Tùy chọn ▸ HST Office ▸ Mở tài liệu)" >> "$summary"
check "Gỡ biểu tượng ứng dụng removes them" uno icons remove "$ext_py"
check "no copy left after the removal" copies_are 0 0
check "the removal is remembered" state_has removed true
check "office closed after the removal" quit_office
check "HST Writer (in the bundle) opens Writer after the removal" opens "$app/Contents/Helpers/HST Writer.app" writer
sleep 5
check "a start after the removal copies nothing" copies_are 0 0
check "Thêm lại biểu tượng ứng dụng adds all five" uno icons add "$ext_py"
check "five copies again" copies_are 5 0
check "office closed after adding them again" quit_office

echo "## HST Office removed" >> "$summary"
mkdir -p "$HOME/.Trash"; mv "$app" "$HOME/.Trash/HST Office.app"
host_missing() {
  open "$apps/HST Sheets.app" || return 1
  local pid=""
  for _ in $(seq 1 20); do pid="$(pgrep -n -f "HST Sheets.app/Contents/MacOS/hst-app-launcher")" && break; sleep 0.5; done
  [ -n "$pid" ] || return 1
  sleep 3; shot host-missing
  osascript -e 'on run argv' -e 'tell application "System Events" to get value of static texts of window 1 of (first process whose unix id is (item 1 of argv as integer))' -e 'end run' "$pid" \
    | tee "$out/host-missing.txt" | grep -q "HST Office chưa được cài đặt" || return 1
  press_in "$pid" 'click button "Chuyển vào Thùng rác" of window 1 of (first process whose unix id is (item 1 of argv as integer))' || return 1
  sleep 3; [ ! -e "$apps/HST Sheets.app" ] && [ -e "$HOME/.Trash/HST Sheets.app" ]
}
check "a copy without HST Office offers the Trash and moves itself there" host_missing
mv "$HOME/.Trash/HST Office.app" "$app"
pkill -f "hst-app-launcher" 2>/dev/null || true

echo "## Dock and HST Base" >> "$summary"
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
sys.exit(1 if left else 0)' "$app" "$ext_py"
}
check "Thêm vào Dock pins HST Writer, HST Sheets and HST Slides" dock_add
sleep 5; shot dock
defaults export com.apple.dock - > "$out/dock.plist" 2>/dev/null || true
check "HST Writer opens again after the Dock restart" opens "$app/Contents/Helpers/HST Writer.app" writer
check "no HST Base launcher in the bundle" test ! -e "$app/Contents/Helpers/HST Base.app"
check "File ▸ New (and the Dock menu) offers no database" uno no-base-menu
odb_fixture() { cp "$repo/tests/fixtures/base/probe.odb" "$out/probe.odb" && mkdir -p "$out/probe-tables"; }
check "probe database copied from the fixture" odb_fixture
check "office closed before the .odb" quit_office
odb_opens() { open -a "$app" "$out/probe.odb" && uno wait base --timeout 120 >>"$out/checks.log" 2>&1; }
check "an .odb opens in HST Office" odb_opens
quit_office >/dev/null 2>&1 || echo "office did not close cleanly" >>"$out/checks.log"
cp "$state" "$out/app-launchers.json" 2>/dev/null || true

echo "" >> "$summary"
echo "$fails failed check(s); log: checks.log" >> "$summary"
cat "$summary"
[ "$fails" -eq 0 ]
