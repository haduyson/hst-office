#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Do the launcher apps of HST Office.app (Contents/Helpers) keep a valid signature, and pass Gatekeeper, once copied
# out of the bundle the way hst_office/mac_app_launchers.py copies them (ditto --noqtn)? Also assessed with a
# quarantine flag, as if a user had downloaded the copy. Gatekeeper is only meaningful for a Developer ID signed and
# notarized dmg; an ad-hoc dmg is reported as such.
#   launcher-copy-signature-check.sh <dmg> <out-dir>      appends to <out-dir>/summary.md; exit 1 when a check fails
set -uo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"
mkdir -p "$out"
summary="$out/summary.md"; log="$out/signature.log"
fails=0
check() {
  local name="$1"; shift
  echo "== $name" >>"$log"
  if "$@" >>"$log" 2>&1; then echo "- PASS $name" | tee -a "$summary"
  else echo "- FAIL $name" | tee -a "$summary"; fails=$((fails + 1)); fi
}
mnt="$(mktemp -d)"; copies="$(mktemp -d)"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null || { echo "cannot mount $dmg" >&2; exit 1; }
app="$mnt/HST Office.app"
echo "## Launchers copied out of the bundle: signature and Gatekeeper" >> "$summary"
signed=false
codesign -dvv "$app" 2>&1 | tee -a "$log" | grep -q '^Authority=Developer ID Application' && signed=true
echo "- dmg signature: $([ "$signed" = true ] && echo 'Developer ID' || echo 'ad-hoc (Gatekeeper not assessed)')" >> "$summary"
found=0
for launcher in "$app/Contents/Helpers/"*.app; do
  [ -d "$launcher" ] || continue
  found=$((found + 1))
  name="$(basename "$launcher" .app)"
  copy="$copies/$name.app"; quarantined="$copies/q/$name.app"
  mkdir -p "$copies/q"
  ditto --noqtn "$launcher" "$copy" && ditto "$launcher" "$quarantined"
  xattr -w com.apple.quarantine "0081;$(printf %x "$(date +%s)");Safari;" "$quarantined"
  check "$name copy: codesign --verify --strict --deep" codesign --verify --strict --deep --verbose=2 "$copy"
  check "$name copy carries no quarantine" bash -c "! xattr -p com.apple.quarantine $(printf %q "$copy")"
  codesign -d --verbose=4 "$copy" >>"$log" 2>&1 || true
  if [ "$signed" = true ]; then
    check "$name copy passes Gatekeeper (spctl --assess --type execute)" spctl --assess --type execute -vv "$copy"
    check "$name quarantined copy passes Gatekeeper" spctl --assess --type execute -vv "$quarantined"
    xcrun stapler validate "$copy" >>"$log" 2>&1 \
      && echo "- note: $name has a stapled ticket" >> "$summary" \
      || echo "- note: $name has no stapled ticket of its own (Gatekeeper looks the cdhash up online)" >> "$summary"
  fi
done
check "the bundle has launchers" test "$found" -gt 0
hdiutil detach "$mnt" >/dev/null 2>&1 || hdiutil detach -force "$mnt" >/dev/null 2>&1
rm -rf "$copies"
echo "$fails failed signature check(s)" >> "$summary"
[ "$fails" -eq 0 ]
