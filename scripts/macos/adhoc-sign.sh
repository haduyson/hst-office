#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Ad-hoc sign a finished HST Office app bundle, inside-out, and verify it strictly.
#   adhoc-sign.sh <path/HST Office.app>
# Why: an upstream release build without a signing identity leaves only the linker's ad-hoc
# signatures on individual Mach-O files; the bundle itself (Info.plist, resources) is unsealed,
# and HST edits the bundle afterwards (Vietnamese language pack, icons, Info.plist). On Apple
# Silicon a quarantined bundle like that is reported as "damaged". With one consistent ad-hoc
# signature macOS shows the normal "cannot verify the developer" / Open Anyway path instead.
# Order follows solenv/bin/macosx-codesign-app-bundle: loose Mach-O files, then nested bundles
# (deepest first, frameworks per version), then the app. No hardened runtime and no entitlements:
# they only matter with a Developer ID signature (scripts/macos/sign-notarize.sh re-signs).
set -Eeuo pipefail
[ $# -eq 1 ] || { echo "usage: $0 <app bundle>" >&2; exit 64; }
app="${1%/}"
[ -d "$app/Contents/MacOS" ] || { echo "not an app bundle: $app" >&2; exit 1; }
id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app/Contents/Info.plist")"
sign() { # codesign failures propagate (pipefail); only the "replacing existing signature" notes are dropped
  codesign --force --sign - "$@" 2>&1 | { grep -v 'replacing existing signature' >&2 || :; }
}
deepest_first() { awk -F/ '{ print NF "\t" $0 }' | sort -rn | cut -f2-; }  # bundle paths contain no newlines

# 1. Every Mach-O file (dylibs, Python extension modules, helper executables), deepest path first.
count=0
while IFS= read -r file; do
  if file -b "$file" | grep -q 'Mach-O'; then sign "$file"; count=$((count + 1)); fi
done < <(find "$app/Contents" -type f \( -perm -u+x -o -name '*.dylib' -o -name '*.dylib.*' -o -name '*.so' \) | deepest_first)
echo "ad-hoc signed $count Mach-O files"

# 2. Nested bundles, deepest first; a framework is signed per real Versions/<v> directory.
bundles=0
while IFS= read -r bundle; do
  case "$bundle" in
    *.framework)
      for version in "$bundle"/Versions/*; do
        [ -L "$version" ] || [ ! -d "$version" ] || { sign "$version"; bundles=$((bundles + 1)); }
      done ;;
    *) sign "$bundle"; bundles=$((bundles + 1)) ;;
  esac
done < <(find "$app/Contents" -type d \( -name '*.framework' -o -name '*.app' -o -name '*.appex' -o -name '*.bundle' \
           -o -name '*.mdimporter' -o -name '*.qlgenerator' -o -name '*.xpc' -o -name '*.plugin' \) | deepest_first)
echo "ad-hoc signed $bundles nested bundles"

# 3. The app: seals Info.plist, resources and the main executable.
sign --identifier "$id" "$app"
codesign --verify --deep --strict "$app"
echo "codesign --verify --deep --strict: ok"
codesign -dv "$app" 2>&1 | grep -E '^(Identifier|Format|Signature|Sealed Resources|CodeDirectory)'
