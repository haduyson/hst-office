#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Diagnose the code signature of a released HST Office dmg and check the ad-hoc re-sign fix.
#   signature-probe.sh <HSTOffice_*.dmg> <out-dir>
# Writes <out-dir>/signature-probe.txt: codesign/spctl results for the shipped bundle, then for a copy
# re-signed by scripts/macos/adhoc-sign.sh (with and without a simulated quarantine flag), then a
# headless document conversion with the re-signed app. Exits non-zero when the re-signed copy fails
# strict verification or the conversion; the shipped bundle's results are evidence only.
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
report="$out/signature-probe.txt"; : > "$report"
log() { printf '%s\n' "$*" | tee -a "$report"; }
run() { # run <command...>: record command, output and exit status; never aborts the probe
  local rc=0
  log "\$ $*"
  "$@" >> "$report" 2>&1 || rc=$?
  log "-> exit $rc"; return 0
}

inspect() { # inspect <label> <app>
  local label="$1" app="$2"
  log ""; log "===== $label: $app"
  run codesign --verify --deep --strict --verbose=4 "$app"
  run codesign -dv --verbose=4 "$app"
  run codesign -dv "$app/Contents/MacOS/soffice"
  run codesign --verify --strict --verbose=4 "$app/Contents/MacOS/soffice"
  local dylib framework
  dylib="$(find "$app/Contents/Frameworks" -maxdepth 1 -name '*.dylib' | head -1)"
  [ -z "$dylib" ] || run codesign -dv "$dylib"
  framework="$(find "$app/Contents/Frameworks" -maxdepth 1 -name '*.framework' | head -1)"
  [ -z "$framework" ] || run codesign --verify --strict --verbose=4 "$framework"
  run spctl --assess --type execute -vv "$app"
}

log "dmg: $(basename "$dmg") $(wc -c < "$dmg") bytes, sha256 $(shasum -a 256 "$dmg" | cut -d' ' -f1)"
log "host: $(sw_vers -productVersion) $(uname -m)"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
inspect "shipped bundle (read-only dmg)" "$mnt/HST Office.app"
ditto "$mnt/HST Office.app" "$work/HST Office.app"
hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"

log ""; log "===== shipped bundle with simulated quarantine"
xattr -w com.apple.quarantine "0081;$(printf %x "$(date +%s)");Safari;" "$app"
run xattr -p com.apple.quarantine "$app"
run spctl --assess --type execute -vv "$app"
command -v syspolicy_check >/dev/null && run syspolicy_check distribution "$app"
xattr -d com.apple.quarantine "$app"

log ""; log "===== ad-hoc re-sign (scripts/macos/adhoc-sign.sh)"
rc=0; bash "$here/adhoc-sign.sh" "$app" 2>&1 | tee -a "$report" || rc=$?
log "-> exit $rc"
inspect "re-signed copy" "$app"
codesign --verify --deep --strict "$app" || { log "FAIL: re-signed copy does not verify"; rc=1; }

log ""; log "===== re-signed copy with simulated quarantine"
xattr -w com.apple.quarantine "0081;$(printf %x "$(date +%s)");Safari;" "$app"
run xattr -p com.apple.quarantine "$app"
run spctl --assess --type execute -vv "$app"
command -v syspolicy_check >/dev/null && run syspolicy_check distribution "$app"
xattr -d com.apple.quarantine "$app"

log ""; log "===== headless conversion with the re-signed app"
printf 'HST Office kiểm tra chuyển đổi PDF.\n' > "$work/probe.txt"
convert_rc=0
"$app/Contents/MacOS/soffice" -env:UserInstallation="file://$work/profile" --headless --convert-to pdf \
  --outdir "$work" "$work/probe.txt" >> "$report" 2>&1 || convert_rc=$?
log "-> soffice exit $convert_rc"
if [ "$convert_rc" -eq 0 ] && [ -s "$work/probe.pdf" ]; then
  log "PDF written: $(wc -c < "$work/probe.pdf") bytes"; cp "$work/probe.pdf" "$out/"
else
  log "FAIL: headless conversion produced no PDF"; rc=1
fi
rm -rf "$work"
exit "$rc"
