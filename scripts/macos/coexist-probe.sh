#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# HST Office and the official LibreOffice installed and running side by side on a macOS GUI runner.
#   coexist-probe.sh <HSTOffice_*.dmg> <LibreOffice_*.dmg> <out-dir>
# Installs LibreOffice, then HST, into /Applications and fails when
#   - the bundles clash (scripts/macos/check-coexist-plists.py: bundle ids, names, profiles, exported
#     UTIs, URL schemes, Spotlight/Quick Look plug-in ids);
#   - installing or removing HST hands LibreOffice's own URL scheme (vnd.libreoffice.command) to HST.
#     A changed default of a document type or ms-* scheme is a WARN: both suites claim them at the
#     same rank (ODF Owner, owner decision 2026-11-06; OOXML Alternate) and LaunchServices picks one;
#   - both cannot run at once as separate processes (lsappinfo) with their own windows, or a file
#     opened with one ("open -a") is opened by the other (its lock file names the owner's profile);
#   - their profiles are not separate, or removing either leaves the other unable to start.
# Writes <out-dir>/summary.md and the evidence. Exit 0 = every check passed, 1 = a check failed.
set -Eeuo pipefail
[ $# -eq 3 ] || { echo "usage: $0 <hst.dmg> <libreoffice.dmg> <out-dir>" >&2; exit 64; }
hst_dmg="$1"; lo_dmg="$2"; out="$3"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
HST_APP="/Applications/HST Office.app"; LO_APP=/Applications/LibreOffice.app
EXTS=(odt ods odp docx xlsx pptx); SCHEMES=(ms-word ms-excel ms-powerpoint vnd.libreoffice.command)
SUPPORT="$HOME/Library/Application Support"
fails=0
log() { printf '%s\n' "$*" | tee -a "$out/summary.md"; }
pass() { log "- PASS $*"; }
fail() { log "- FAIL $*"; fails=$((fails + 1)); }

install_app() { # install_app <dmg> <bundle name>: copy into /Applications and register with LaunchServices
  local mnt="$work/mnt"; mkdir -p "$mnt"
  hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$1" >/dev/null
  rm -rf "/Applications/$2"; ditto "$mnt/$2" "/Applications/$2"
  hdiutil detach "$mnt" >/dev/null
  # An unsigned CI build: ad-hoc sign so it may run (signed releases verify as they are).
  codesign --verify --deep --strict "/Applications/$2" 2>/dev/null || bash "$here/adhoc-sign.sh" "/Applications/$2" >>"$out/adhoc-sign.log" 2>&1
  "$LSREG" -f "/Applications/$2"; sleep 3
}

remove_app() { "$LSREG" -u "$1" 2>/dev/null || :; rm -rf "$1"; sleep 3; }

record() { # record <label>: default handler of every extension and scheme (LaunchServices + duti)
  "$work/helper" defaults "${EXTS[@]}" -- "${SCHEMES[@]}" > "$out/defaults-$1.txt"
  local e; for e in "${EXTS[@]}"; do printf 'duti %s: %s\n' "$e" "$(duti -x "$e" 2>&1 | tr '\n' ' ')"; done >> "$out/defaults-$1.txt"
}

same_defaults() { # same_defaults <label> <record> <baseline record>: FAIL for a key in lo-owned.txt, WARN otherwise
  local label="$1" line key changed=0; shift
  if [ ! -s "$out/defaults-$1.txt" ] || [ ! -s "$out/defaults-$2.txt" ]; then fail "$label: no record defaults-$1/$2"; return; fi
  if cmp -s "$out/defaults-$1.txt" "$out/defaults-$2.txt"; then pass "$label: default applications as with $2 ($(grep -c . "$out/defaults-$2.txt") entries)"; return; fi
  while IFS= read -r line; do
    key="${line%% *}"; changed=1
    if grep -qxF "$key" "$out/lo-owned.txt"; then fail "$label: LibreOffice's own scheme changed: $line (was: $(grep -F "$key " "$out/defaults-$2.txt" | head -1))"
    else log "- WARN $label: default of a type both suites claim changed (either is acceptable): $line (was: $(grep -F "$key " "$out/defaults-$2.txt" | head -1))"; fi
  done < <(comm -13 <(sort "$out/defaults-$2.txt") <(sort "$out/defaults-$1.txt") | grep -v '^duti ')
  [ "$changed" -eq 1 ] || pass "$label: default applications as with $2 (duti output only)"
}

lo_owned() { # keys only LibreOffice may handle: its own URL scheme
  echo scheme:vnd.libreoffice.command > "$out/lo-owned.txt"
}

first_launch() { # first_launch <app> <bundle id>: seed the profile, start once, quit (LaunchServices settles)
  seed_profile "$(profile_dir "$1")"
  open -a "$1"; app_pid "$2" >/dev/null || :; sleep 10
  quit_app "$2" "$1"; sleep 5
}

unregister_strays() { # other registered copies (e.g. the build tree's instdir app) would skew every default
  local id path
  for id in vn.hasontech.hstoffice org.libreoffice.script; do
    "$work/helper" copies "$id" | while IFS= read -r path; do
      case "$path" in /Applications/*) ;; *) log "unregistering stray copy $path"; "$LSREG" -u "$path" || : ;; esac
    done
  done
  sleep 3
}

profile_dir() { # profile_dir <app>: UserInstallation of bootstraprc with $SYSUSERCONFIG expanded, decoded
  local raw; raw="$(sed -n 's/^UserInstallation=//p' "$1/Contents/Resources/bootstraprc")"
  # shellcheck disable=SC2016  # $SYSUSERCONFIG is the literal bootstrap variable, replaced in Python
  python3 -c 'import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1].replace("$SYSUSERCONFIG",sys.argv[2])))' "$raw" "$SUPPORT"
}

seed_profile() { # no tip-of-the-day or HST welcome dialog: both are modal and would hold a file open
  mkdir -p "$1/user"
  cat >"$1/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
}

app_pid() { # app_pid <bundle id> [<seconds>]: pid of the running app as LaunchServices lists it
  local left="${2:-90}" asn pid
  while [ "$left" -gt 0 ]; do
    asn="$(lsappinfo find "bundleid=$1" 2>/dev/null | head -1)"
    if [ -n "$asn" ]; then
      pid="$(lsappinfo info -only pid "$asn" 2>/dev/null | sed -n 's/.*"pid"=\([0-9]*\).*/\1/p')"
      [ -n "$pid" ] && { echo "$pid"; return 0; }
    fi
    sleep 2; left=$((left - 2))
  done
  return 1
}

wait_windows() { # wait_windows <pid>: number of normal on-screen windows, waiting up to 60 s for one
  local n=0 left=60
  while [ "$left" -gt 0 ]; do n="$("$work/helper" windows "$1")"; [ "$n" -gt 0 ] && break; sleep 2; left=$((left - 2)); done
  echo "$n"
}

quit_app() { osascript -e "tell application id \"$1\" to quit" >/dev/null 2>&1 || :; sleep 5; pkill -f "$2/Contents/MacOS/soffice" 2>/dev/null || :; sleep 2; }

lock_owner() { # lock_owner <file>: profile URL in LibreOffice's lock file next to the opened document
  local lock left=60; lock="$(dirname "$1")/.~lock.$(basename "$1")#"
  while [ ! -s "$lock" ] && [ "$left" -gt 0 ]; do sleep 2; left=$((left - 2)); done
  [ -s "$lock" ] && cut -d, -f5- "$lock" | tr -d ';'
}

start_alone() { # start_alone <app> <bundle id> <label>
  local pid n
  open -a "$1"
  if pid="$(app_pid "$2")"; then
    n="$(wait_windows "$pid")"
    if [ "$n" -gt 0 ]; then pass "$3: $(basename "$1") starts alone (pid $pid, $n windows)"; else fail "$3: $(basename "$1") has no window"; fi
  else fail "$3: $(basename "$1") did not start"; fi
  quit_app "$2" "$1"
}

: > "$out/summary.md"
log "## HST Office / LibreOffice coexistence on $(sw_vers -productName) $(sw_vers -productVersion) $(uname -m)"
swiftc -O -o "$work/helper" "$here/coexist-probe-helper.swift" 2>"$out/swiftc.log"
command -v duti >/dev/null || brew install duti >"$out/brew-duti.log" 2>&1
unregister_strays
record none

log "### Install LibreOffice, then HST Office"
install_app "$lo_dmg" LibreOffice.app
LO_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$LO_APP/Contents/Info.plist")"
first_launch "$LO_APP" "$LO_ID"
record lo
lo_owned
log "LibreOffice $(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$LO_APP/Contents/Info.plist") ($LO_ID)"
install_app "$hst_dmg" "HST Office.app"
HST_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$HST_APP/Contents/Info.plist")"
first_launch "$HST_APP" "$HST_ID"
log "HST Office $(/usr/libexec/PlistBuddy -c 'Print :CFBundleGetInfoString' "$HST_APP/Contents/Info.plist" 2>/dev/null) ($HST_ID)"
record both
same_defaults "after installing HST" both lo
if python3 "$here/check-coexist-plists.py" --hst "$HST_APP" --lo "$LO_APP" > "$out/plists.txt"; then pass "bundle declarations do not clash ($(grep -c '^PASS' "$out/plists.txt") rules)"
else fail "bundle declarations clash:"; grep '^FAIL' "$out/plists.txt" | tee -a "$out/summary.md"; fi
"$LSREG" -dump > "$out/lsregister-dump.txt" 2>/dev/null || :
for p in "$LO_APP" "$HST_APP"; do cp "$p/Contents/Info.plist" "$out/Info-$(basename "$p" .app | tr ' ' -).plist"; done

log "### Both running at once"
HST_PROFILE="$(profile_dir "$HST_APP")"; LO_PROFILE="$(profile_dir "$LO_APP")"
if [ "$HST_PROFILE" != "$LO_PROFILE" ]; then pass "profiles: $LO_PROFILE / $HST_PROFILE"; else fail "one profile for both: $HST_PROFILE"; fi
open -a "$LO_APP"
lo_pid="$(app_pid "$LO_ID")" || lo_pid=""
open -a "$HST_APP"
hst_pid="$(app_pid "$HST_ID")" || hst_pid=""
lsappinfo list > "$out/lsappinfo.txt" 2>&1 || :
if [ -n "$lo_pid" ] && [ -n "$hst_pid" ] && [ "$lo_pid" != "$hst_pid" ]; then
  pass "both run: LibreOffice pid $lo_pid ($(wait_windows "$lo_pid") windows), HST Office pid $hst_pid ($(wait_windows "$hst_pid") windows)"
else fail "both run: LibreOffice pid '${lo_pid}', HST Office pid '${hst_pid}'"; fi
docs="$work/docs"; mkdir -p "$docs"
printf 'HST Office\n' > "$docs/for-hst.txt"; printf 'LibreOffice\n' > "$docs/for-lo.txt"
open -a "$HST_APP" "$docs/for-hst.txt"; open -a "$LO_APP" "$docs/for-lo.txt"
owner_hst="$(lock_owner "$docs/for-hst.txt" || :)"; owner_lo="$(lock_owner "$docs/for-lo.txt" || :)"
hst_profile_url="$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$HST_PROFILE")"
lo_profile_url="$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$LO_PROFILE")"
case "$owner_hst" in *"$hst_profile_url"*) pass "open -a 'HST Office' opened the file in HST ($owner_hst)" ;;
  *) fail "open -a 'HST Office': lock file owner '$owner_hst', expected $hst_profile_url" ;; esac
case "$owner_lo" in *"$lo_profile_url"*) pass "open -a LibreOffice opened the file in LibreOffice ($owner_lo)" ;;
  *) fail "open -a LibreOffice: lock file owner '$owner_lo', expected $lo_profile_url" ;; esac
n_hst="$(pgrep -f "$HST_APP/Contents/MacOS/soffice" | wc -l | tr -d ' ')"; n_lo="$(pgrep -f "$LO_APP/Contents/MacOS/soffice" | wc -l | tr -d ' ')"
if [ "$n_hst" = 1 ] && [ "$n_lo" = 1 ]; then pass "one process each after opening files (single-instance pipes are separate)"
else fail "processes after opening files: HST $n_hst, LibreOffice $n_lo"; fi
screencapture -x "$out/both-running.png" 2>/dev/null || :
quit_app "$HST_ID" "$HST_APP"; quit_app "$LO_ID" "$LO_APP"
for d in "$HST_PROFILE" "$LO_PROFILE"; do
  if [ -d "$d/user/config" ] || [ -d "$d/user/extensions" ]; then pass "profile written: $d"; else fail "profile not written: $d"; fi
done
find "$HOME/Library/Preferences" -maxdepth 1 \( -iname '*hasontech*' -o -iname '*libreoffice*' \) -exec basename {} \; > "$out/preferences.txt" 2>/dev/null || :
log "Preferences domains: $(tr '\n' ' ' < "$out/preferences.txt")"
record both-after-run
same_defaults "after running both" both-after-run lo

log "### Remove HST Office: LibreOffice keeps working"
remove_app "$HST_APP"
record lo-after-hst-removal
same_defaults "after removing HST" lo-after-hst-removal lo
start_alone "$LO_APP" "$LO_ID" "after removing HST"

log "### Reinstall HST Office, remove LibreOffice: HST keeps working"
install_app "$hst_dmg" "HST Office.app"
remove_app "$LO_APP"
record hst-only
start_alone "$HST_APP" "$HST_ID" "after removing LibreOffice"
log "HST alone, default applications (informational):"; sed 's/^/    /' "$out/defaults-hst-only.txt" | tee -a "$out/summary.md" >/dev/null
log "Result: $fails failed check(s)"
[ "$fails" -eq 0 ]
