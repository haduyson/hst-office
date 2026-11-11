#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Start-up timing of the HST Office dmg on a GitHub macOS runner, the app copied to /Applications as a user does.
#   startup-timing-macos.sh <HSTOffice_*.dmg> <out-dir> [variants]
# First the Gatekeeper cost of a downloaded copy: the dmg gets the quarantine flag a browser sets, the app is copied
# from it to /Applications, and the system's assessment and the deep signature check are timed. The quarantine flag
# is then removed (the first-launch prompt would block the timing) and the variants run: hst (fresh, warm x3, cold),
# trace (with the Python tracer), noext (the HST extension moved out), lazy / lazy-trace (the extension of
# $HST_OVERLAY_OXT, built from this checkout and compiled to bytecode as the build does), lo (stock LibreOffice dmg of
# $LO_DMG_URL). "cold" runs `purge` first. Evidence only.
set -Eeuo pipefail
dmg="$1"; out="$2"; variants=",${3:-hst,trace,noext,lazy,lazy-trace,lo},"
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
echo "pyuno: $(find "$app/Contents" -maxdepth 3 -name 'pyuno*' | tr '\n' ' ')" >> "$out/gatekeeper.txt"
office_python() { # the bundled interpreter with uno on its path
  local bundle="$1"
  # uno.py is in Resources, pyuno.so in Frameworks (next to the office's libraries)
  printf '#!/bin/sh\nPYTHONPATH="%s/Contents/Resources:%s/Contents/Frameworks" URE_BOOTSTRAP="vnd.sun.star.pathname:%s/Contents/Resources/fundamentalrc" exec "%s" "$@"\n' \
    "$bundle" "$bundle" "$bundle" "$(find "$bundle/Contents/Frameworks" -path '*/bin/python3.*' -type f -perm -u+x ! -name '*-config' | head -n 1)" \
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

starts=fresh,warm,warm,warm,cold
ext="$app/Contents/Resources/extensions/hst-vietnamese-tools"
if has hst; then timing hst "$app" "$starts" --shots; fi
if has trace; then timing hst-trace "$app" fresh,warm,cold --trace; fi
if has noext; then mv "$ext" "$work/hst-ext-aside"; timing hst-noext "$app" "$starts"; mv "$work/hst-ext-aside" "$ext"; fi
if [ -n "${HST_OVERLAY_OXT:-}" ] && { has lazy || has lazy-trace; }; then
  mv "$ext" "$work/hst-ext-installed"
  mkdir -p "$ext"
  python3 -I -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$HST_OVERLAY_OXT" "$ext"
  # as scripts/macos/precompile-python.sh does for the shipped bundle
  py="$(find "$app/Contents/Frameworks" -path '*/bin/python3.*' -type f -perm -u+x ! -name '*-config' | head -n 1)"
  env -u PYTHONDONTWRITEBYTECODE "$py" -I -m compileall -q --invalidation-mode unchecked-hash "$ext" > "$out/overlay-pyc.log" 2>&1 \
    || echo "compileall exit $?" >> "$out/overlay-pyc.log"
  if has lazy; then timing lazy "$app" "$starts"; fi
  if has lazy-trace; then timing lazy-trace "$app" fresh,warm,cold --trace; fi
  rm -rf "$ext"; mv "$work/hst-ext-installed" "$ext"
fi
if has lo && [ -n "${LO_DMG_URL:-}" ]; then
  if curl -fsSL --retry 3 -o "$work/lo.dmg" "$LO_DMG_URL"; then
    shasum -a 256 "$work/lo.dmg" > "$out/lo-dmg.sha256"
    mkdir -p "$work/lo-mnt"
    hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$work/lo-mnt" "$work/lo.dmg" > /dev/null
    ditto "$work/lo-mnt/LibreOffice.app" /Applications/LibreOffice.app
    hdiutil detach "$work/lo-mnt" > /dev/null
    timing lo /Applications/LibreOffice.app "$starts"
  fi
fi
python3 -I "$here/startup-timing-summary.py" "$out" > "$out/summary.md"
cat "$out/summary.md"
