#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Start-up timing of the HST Office dmg on a GitHub macOS runner, the app copied to /Applications as a user does.
#   startup-timing-macos.sh <HSTOffice_*.dmg> <out-dir> [variants]
# First the Gatekeeper cost of a downloaded copy: the dmg gets the quarantine flag a browser sets, the app is copied
# from it to /Applications, and the system's assessment and the deep signature check are timed. The quarantine flag
# is then removed (the first-launch prompt would block the timing) and the variants run: hst (fresh, warm, warm,
# cold), trace, noext, lo (stock LibreOffice dmg of $LO_DMG_URL). "cold" runs `purge` first. Evidence only.
set -Eeuo pipefail
dmg="$1"; out="$2"; variants=",${3:-hst,trace,noext,lo},"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$RUNNER_TEMP/startup-work"; mkdir -p "$work/mnt"
has() { [[ "$variants" == *",$1,"* ]]; }
now() { python3 -c 'import time; print("%.3f" % time.time())'; }
{ sw_vers; uname -m; sysctl -n machdep.cpu.brand_string hw.ncpu; spctl --status 2>&1; } > "$out/runner.txt" 2>&1 || true
app="/Applications/HST Office.app"
[ ! -e "$app" ] || { echo "the runner already has $app" >&2; exit 1; }
xattr -w com.apple.quarantine "0081;$(printf '%x' "$(date +%s)");Safari;" "$dmg"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$work/mnt" "$dmg" > /dev/null
ditto "$work/mnt/HST Office.app" "$app"
hdiutil detach "$work/mnt" > /dev/null
{ echo "quarantine on the copied app: $(xattr -p com.apple.quarantine "$app" 2>&1)"
  t0=$(now); spctl --assess --type execute -vv "$app" 2>&1; t1=$(now)
  echo "spctl --assess: $(python3 -c "print(round($t1 - $t0, 2))") s"
  t0=$(now); codesign --verify --deep --strict "$app" 2>&1; t1=$(now)
  echo "codesign --verify --deep --strict: $(python3 -c "print(round($t1 - $t0, 2))") s"
  echo "bundle files: $(find "$app" -type f | wc -l), size: $(du -sh "$app" | cut -f1)"
  echo "python files: $(find "$app" -name '*.py' | wc -l), pyc files: $(find "$app" -name '*.pyc' | wc -l)"
  echo "bundled extensions: $(ls "$app/Contents/Resources/extensions" | tr '\n' ' ')"
} > "$out/gatekeeper.txt" 2>&1 || echo "gatekeeper facts incomplete" >> "$out/gatekeeper.txt"
xattr -dr com.apple.quarantine "$app"
SUDO=""
overlay() { # overlay <extension dir>: the HST extension built from this commit instead of the bundled one
  [ -n "${HST_OVERLAY_OXT:-}" ] || return 0
  $SUDO rm -rf "$1" && $SUDO mkdir -p "$1"
  python3 -I -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$HST_OVERLAY_OXT" "$1"
  echo "overlaid $1 with $(basename "$HST_OVERLAY_OXT")" | tee -a "$out/overlay.txt"
}
overlay "$app/Contents/Resources/extensions/hst-vietnamese-tools"

office_python() { # the bundled interpreter with uno on its path
  local bundle="$1"
  printf '#!/bin/sh\nPYTHONPATH="%s/Contents/Resources" URE_BOOTSTRAP="vnd.sun.star.pathname:%s/Contents/Resources/fundamentalrc" exec "%s" "$@"\n' \
    "$bundle" "$bundle" "$(find "$bundle/Contents/Frameworks" -path '*/bin/python3.*' -type f -perm -u+x ! -name '*-config' | head -n 1)" \
    > "$work/python-$(basename "$bundle" .app | tr ' ' -)"
  chmod +x "$work/python-$(basename "$bundle" .app | tr ' ' -)"
  echo "$work/python-$(basename "$bundle" .app | tr ' ' -)"
}

timing() { # timing <label> <bundle> <starts> [more harness options]
  local label="$1" bundle="$2" starts="$3"; shift 3
  python3 -I "$here/startup-timing.py" --soffice "$bundle/Contents/MacOS/soffice" --python "$(office_python "$bundle")" \
    --intro "$bundle/Contents/Resources/intro.png" --profile "$work/profile-$label" --out "$out" --label "$label" \
    --starts "$starts" --cold-command "sync && sudo purge" "$@" || echo "$label: no window seen" >> "$out/failures.txt"
}

has hst && timing hst "$app" fresh,warm,warm,cold --shots
has trace && timing hst-trace "$app" fresh,warm,cold --trace
if has noext; then
  ext="$app/Contents/Resources/extensions/hst-vietnamese-tools"
  mv "$ext" "$work/hst-ext-aside"
  timing hst-noext "$app" fresh,warm,cold
  mv "$work/hst-ext-aside" "$ext"
fi
if has lo && [ -n "${LO_DMG_URL:-}" ]; then
  if curl -fsSL --retry 3 -o "$work/lo.dmg" "$LO_DMG_URL"; then
    shasum -a 256 "$work/lo.dmg" > "$out/lo-dmg.sha256"
    mkdir -p "$work/lo-mnt"
    hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$work/lo-mnt" "$work/lo.dmg" > /dev/null
    ditto "$work/lo-mnt/LibreOffice.app" /Applications/LibreOffice.app
    hdiutil detach "$work/lo-mnt" > /dev/null
    timing lo /Applications/LibreOffice.app fresh,warm,warm,cold
  fi
fi
python3 -I "$here/startup-timing-summary.py" "$out" > "$out/summary.md"
cat "$out/summary.md"
