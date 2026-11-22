#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Screenshot the "Save Document?" dialog of a macOS dmg in light and dark appearance, with its default
# (Save) button resting, hovered and pressed, and measure the label's contrast on the button's fill.
#   save-dialog-probe.sh <HSTOffice_*.dmg> <out-dir>
# Evidence only: writes summary.md; fails only when the app cannot be started.
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign.log" 2>&1 || true
brew list cliclick >/dev/null 2>&1 || brew install cliclick >"$out/brew-cliclick.log" 2>&1
python3 -m venv "$work/venv" && "$work/venv/bin/pip" -q install pillow >"$out/pip.log" 2>&1
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
timeout_osa() { perl -e 'alarm 20; exec @ARGV' osascript "$@"; }
screen_w="$(timeout_osa -e 'tell application "Finder" to get item 3 of (get bounds of window of desktop)')"
: > "$out/summary.md"
for look in light dark; do
  if [ "$look" = dark ]; then defaults write -g AppleInterfaceStyle Dark; else defaults delete -g AppleInterfaceStyle 2>/dev/null || true; fi
  profile="$work/profile-$look"; mkdir -p "$profile/user"
  cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
  "$app/Contents/MacOS/soffice" --norestore --nologo --nodefault --accept="socket,host=localhost,port=2002;urp;" \
    "-env:UserInstallation=file://$profile" >"$out/soffice-$look.log" 2>&1 &
  pid=$!
  sleep 8
  timeout_osa -e "tell application \"System Events\" to tell (first process whose unix id is $pid)
    set frontmost to true
    delay 1
    repeat with w in windows
      try
        click (first button of w whose subrole is \"AXCloseButton\")
      end try
    end repeat
  end tell" >"$out/welcome-$look.log" 2>&1 || true
  rm -f "$out/ready"
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$pyhome" perl -e 'alarm 200; exec @ARGV' "$py" "$here/save-dialog-probe.py" "$out" \
    >"$out/driver-$look.log" 2>&1 &
  driver=$!
  for _ in $(seq 1 120); do [ -f "$out/ready" ] && break; sleep 1; done
  sleep 4
  # the dialog: the front window of the office, activated by pid (an exec'd soffice is not frontmost)
  bounds="$(timeout_osa -e "tell application \"System Events\" to tell (first process whose unix id is $pid)
    set frontmost to true
    delay 1
    set w to window 1
    set p to position of w
    set s to size of w
    return (item 1 of p as text) & \" \" & (item 2 of p as text) & \" \" & (item 1 of s as text) & \" \" & (item 2 of s as text) & \" \" & (name of w as text)
  end tell" 2>"$out/bounds-$look.log" || true)"
  echo "$bounds" >"$out/bounds-$look.txt"
  read -r bx by bw bh _ <<<"$bounds" || true
  cliclick m:5,5 || true; sleep 1
  screencapture -x "$out/$look-rest.png" || true
  img_w="$("$work/venv/bin/python" -c 'import sys;from PIL import Image;print(Image.open(sys.argv[1]).width)' "$out/$look-rest.png")"
  scale="$(python3 -c "print($img_w/float($screen_w))")"
  measure() { "$work/venv/bin/python" -I "$here/save-dialog-measure.py" "$1" "$bx" "$by" "$bw" "$bh" "$scale"; }
  rest="$(measure "$out/$look-rest.png" || true)"; echo "$rest" >>"$out/measure.jsonl"
  centre="$(python3 -c 'import json,sys;d=json.loads(sys.argv[1]);print("%d,%d"%tuple(d["centre_pt"]))' "$rest" 2>/dev/null || true)"
  if [ -n "$centre" ]; then
    cliclick "m:$centre"; sleep 1; screencapture -x "$out/$look-hover.png" || true
    measure "$out/$look-hover.png" >>"$out/measure.jsonl" || true
    cliclick "dd:$centre"; sleep 1; screencapture -x "$out/$look-pressed.png" || true
    measure "$out/$look-pressed.png" >>"$out/measure.jsonl" || true
    # release away from the button: no click
    cliclick "du:5,5"; sleep 1
  fi
  cliclick kp:esc || true; sleep 2
  kill "$driver" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true; sleep 2; kill -9 "$pid" 2>/dev/null || true
  { echo "## $look"; echo; echo "dialog: $bounds"; echo; echo '```'; grep -F "$look-" "$out/measure.jsonl" || true; echo '```'; echo; } >>"$out/summary.md"
done
defaults delete -g AppleInterfaceStyle 2>/dev/null || true
cat "$out/summary.md"
