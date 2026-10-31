# SPDX-License-Identifier: AGPL-3.0-only
# shellcheck shell=bash
# Shared helpers for the macOS signing scripts (sourced by adhoc-sign.sh and sign-notarize.sh).

# deepest_first: sort paths on stdin so nested code is handled before its container.
# Bundle paths contain no newlines.
deepest_first() { awk -F/ '{ print NF "\t" $0 }' | sort -rn | cut -f2-; }

# is_bundle_main_executable <file>: true for <bundle>/Contents/MacOS/<CFBundleExecutable>. Signing such
# a file signs (and seals) the whole bundle, so it must come after every sibling and is left to the
# bundle signature. On x86_64 the linker adds no signature at all, so the order matters there.
is_bundle_main_executable() {
  local file="$1" dir plist main
  dir="$(dirname "$file")"
  [ "$(basename "$dir")" = MacOS ] || return 1
  plist="$(dirname "$dir")/Info.plist"
  [ -f "$plist" ] || return 1
  main="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$plist" 2>/dev/null)" || return 1
  [ "$main" = "$(basename "$file")" ]
}

# macho_files <app> [all]: every Mach-O file in the bundle, deepest first. Detection reads each file's
# header (file -b), so executables without +x, versioned dylibs (libx.dylib.78, libx.so.1) and loadable
# bundles are all found. Without "all", bundle main executables are omitted.
macho_files() {
  local f
  while IFS= read -r f; do
    file -b "$f" | grep -q 'Mach-O' || continue
    if [ "${2:-}" != all ] && is_bundle_main_executable "$f"; then continue; fi
    printf '%s\n' "$f"
  done < <(find "$1/Contents" -type f | deepest_first)
}
