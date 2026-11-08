#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Start-up questions and HST option pages of a macOS dmg, started the way a user does (Finder-like `open` from the
# mounted volume), each start with a fresh-profile sequence: start 1-3 from the volume, start 4 after a copy to
# /Applications. Per start: the office's stdout/stderr, ps, a screenshot, every window with its texts (System Events),
# and what the extension code sees (startup-chain-probe.py). Evidence only.
#   startup-chain-probe.sh <dmg> <out-dir> <case: volume | quarantined | owner> [<older dmg>]
# owner: Vietnamese macOS in dark mode; the older dmg's app is first installed in /Applications and started three
# times with the default profile (the user's), then deleted, as an owner who uninstalls it; the profile stays.
set -Euo pipefail
dmg="$1"; out="$2"; case="$3"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"
cp "$dmg" "$work/probe.dmg"
if [ "$case" = quarantined ] || [ "$case" = owner ]; then
  xattr -w com.apple.quarantine "0083;$(printf %x "$(date +%s)");Safari;$(uuidgen)" "$work/probe.dmg"
fi
xattr -l "$work/probe.dmg" >"$out/dmg-xattr.txt" 2>&1 || true
hdiutil attach -nobrowse -noautoopen "$work/probe.dmg" >"$out/attach.txt" 2>&1
mnt="$(awk -F'\t' '/\/Volumes\//{print $NF; exit}' "$out/attach.txt")"
echo "mounted at: $mnt" | tee "$out/mount.txt"
volume_app="$mnt/HST Office.app"
xattr -l "$volume_app" >"$out/app-xattr.txt" 2>&1 || true
spctl --assess --type execute -vv "$volume_app" >"$out/spctl.txt" 2>&1 || true
profile="$work/profile"
profile_args=("-env:UserInstallation=file://$profile")
if [ "$case" = owner ]; then
  profile_args=()  # the default profile in ~/Library/Application Support, as a user has it
  defaults write -g AppleLanguages -array vi en
  osascript -e 'tell application "System Events" to tell appearance preferences to set dark mode to true' >"$out/dark.log" 2>&1 || true
fi
rm -rf "$HOME/Library/Application Support/HSTOffice/move-offered"

dump_windows() { # dump_windows <pid> <file>
  perl -e 'alarm 60; exec @ARGV' osascript >"$2" 2>&1 <<OSA || echo "osascript exit $?" >>"$2"
tell application "System Events"
  set out to ""
  repeat with p in (every process whose unix id is ${1:-0})
    repeat with w in windows of p
      set out to out & "WINDOW: " & (name of w as text) & linefeed
      try
        repeat with e in (entire contents of w)
          try
            set out to out & "  " & (role of e as text) & " | " & (name of e as text) & " | " & (value of e as text) & linefeed
          on error
            try
              set out to out & "  " & (role of e as text) & " | " & (name of e as text) & linefeed
            end try
          end try
        end repeat
      end try
    end repeat
  end repeat
  return out
end tell
OSA
}

press() { # press <pid> <button label> <log>
  perl -e 'alarm 60; exec @ARGV' osascript >>"$3" 2>&1 <<OSA || echo "osascript exit $?" >>"$3"
tell application "System Events"
  set p to first process whose unix id is ${1:-0}
  set frontmost of p to true
  delay 0.5
  repeat with w in windows of p
    try
      click button "$2" of w
      return "clicked $2"
    end try
  end repeat
  return "no button $2"
end tell
OSA
}

run_start() { # run_start <n> <app> <driver mode or ""> <button to press>
  local n="$1" app="$2" mode="$3" button="$4" dir="$out/start-$1"
  mkdir -p "$dir"
  echo "$app" >"$dir/app.txt"
  open -n --stdout "$dir/stdout.log" --stderr "$dir/stderr.log" "$app" --args --norestore \
    ${profile_args[@]+"${profile_args[@]}"} "--accept=socket,host=localhost,port=2002;urp;" >"$dir/open.log" 2>&1 \
    || echo "open exit $?" >>"$dir/open.log" &
  local pid="" i
  # A quarantined app: macOS first verifies the bundle, then asks once per start whether to open it (the translocated
  # copy is new each time). Answer Open like a user, until the office shows a window (at most 5 minutes).
  for i in $(seq 1 100); do
    pid="$(pgrep -f "Contents/MacOS/soffice" | head -1)"
    if [ -n "$pid" ] && perl -e 'alarm 20; exec @ARGV' osascript -e "tell application \"System Events\" to count windows of (first process whose unix id is $pid)" 2>/dev/null | grep -qv '^0$'; then
      break
    fi
    perl -e 'alarm 20; exec @ARGV' osascript -e 'tell application "System Events"
      repeat with p in (every process whose background only is false or name is "CoreServicesUIAgent")
        repeat with w in windows of p
          try
            click button "Open" of w
            return "clicked Open in " & (name of p)
          end try
          try
            click button "Mở" of w
            return "clicked Mở in " & (name of p)
          end try
        end repeat
      end repeat
      return ""
    end tell' >>"$dir/gatekeeper.log" 2>&1 || true
    [ $((i % 10)) -eq 1 ] && { screencapture -x "$dir/wait-$i.png" 2>/dev/null || true; }
    sleep 3
  done
  echo "waited $((i * 3))s" >>"$dir/gatekeeper.log"
  echo "pid=$pid" >"$dir/pid.txt"
  sleep 20
  ps -o pid,command -p "${pid:-0}" >"$dir/ps.txt" 2>&1 || true
  lsof -p "${pid:-0}" 2>/dev/null | grep -m3 'soffice\|libmergedlo' >>"$dir/ps.txt" || true
  screencapture -x "$dir/screen.png" || true
  dump_windows "$pid" "$dir/windows.txt"
  local py extpy
  py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
  extpy="$(dirname "$(find "$app/Contents" -path '*hst-vietnamese-tools/python/hst_office/welcome_job.py' -print -quit)")/.."
  local pyuno; pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
  for m in state $mode; do
    OPTIONS_PAGE=DefaultApps URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
      PYTHONPATH="$app/Contents/Resources:$(dirname "$pyuno")" perl -e 'alarm 120; exec @ARGV' "$py" \
      "$here/startup-chain-probe.py" "$m" "$dir/$m.json" "$extpy" >"$dir/driver-$m.log" 2>&1 || echo "driver exit $?" >>"$dir/driver-$m.log"
    if [ "$m" = options ]; then  # opened at "Mở tài liệu": go to "Giao diện" in the tree like a user, away and back
      screencapture -x "$dir/options-0-opened.png" || true
      for step in 1-up:126 2-down:125 3-up:126; do
        perl -e 'alarm 30; exec @ARGV' osascript -e "tell application \"System Events\"
          set frontmost of (first process whose unix id is $pid) to true
          delay 0.5
          key code ${step#*:}
        end tell" >>"$dir/options-keys.log" 2>&1 || true
        sleep 3
        screencapture -x "$dir/options-${step%%:*}.png" || true
        dump_windows "$pid" "$dir/windows-options-${step%%:*}.txt"
      done
    fi
  done
  if [ -n "$button" ]; then  # the Vietnamese label, then the English one (UI language of the runner)
    press "$pid" "$button" "$dir/press.log"
    case "$button" in "Để sau") press "$pid" "Later" "$dir/press.log" ;; "Đóng") press "$pid" "Close" "$dir/press.log" ;; esac
  fi
  sleep 3
  dump_windows "$pid" "$dir/windows-after.txt"
  kill "$pid" 2>/dev/null || true; sleep 4; kill -9 "$pid" 2>/dev/null || true
  pkill -9 -f "Contents/MacOS/soffice" 2>/dev/null || true
  sleep 2
}

if [ "$case" = owner ]; then
  older="$4"; omnt="$work/older-mnt"; mkdir -p "$omnt"
  hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$omnt" "$older" >/dev/null
  ditto "$omnt/HST Office.app" "/Applications/HST Office.app"; hdiutil detach "$omnt" >/dev/null
  out_main="$out"; out="$out/older"; mkdir -p "$out"
  run_start 1 "/Applications/HST Office.app" "" "Đóng"
  run_start 2 "/Applications/HST Office.app" "" "Để sau"
  run_start 3 "/Applications/HST Office.app" "" "Để sau"
  out="$out_main"
  rm -rf "/Applications/HST Office.app"
  ls -la "$HOME/Library/Application Support" >"$out/app-support-after-older.txt" 2>&1 || true
fi
run_start 1 "$volume_app" "" "Để sau"
run_start 2 "$volume_app" "" "Đóng"
run_start 3 "$volume_app" "" "Để sau"
ditto "$volume_app" "/Applications/HST Office.app"
run_start 4 "/Applications/HST Office.app" options "Để sau"
ls -la "$HOME/Library/Application Support/HSTOffice" >"$out/app-support.txt" 2>&1 || true
cat "$HOME/Library/Application Support/HSTOffice/move-offered" >>"$out/app-support.txt" 2>&1 || true
hdiutil detach "$mnt" >/dev/null 2>&1 || true
for f in "$out"/start-*/windows.txt; do echo "== $f"; cat "$f"; done
for f in "$out"/start-*/stderr.log; do echo "== $f"; head -60 "$f"; done
