#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# TEST ONLY: copy a module-build patch overlay (scripts/linux/local-build.sh --modules) over an extracted
# reference HST Office .deb. Never use the result as a release or on a user's machine.
#   dpkg-deb -x HSTOffice_<release>_Linux_x86-64.deb ref/
#   ./apply-build-overlay.sh ref/            (run from the unpacked overlay directory)
# The install root is the directory holding program/soffice.bin under ref/ (e.g. ref/opt/hstoffice/).
set -Eeuo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:?usage: apply-build-overlay.sh <extracted .deb directory>}"
if [ ! -d "$here/files" ] || [ ! -f "$here/FILES" ]; then echo "run from an unpacked overlay (files/, FILES)" >&2; exit 1; fi
(cd "$here/files" && sha256sum -c --quiet ../SHA256SUMS) || { echo "overlay checksums do not match" >&2; exit 1; }
mapfile -t roots < <(find "$target" -maxdepth 5 -path '*/program/soffice.bin' -printf '%h\n' | sed 's|/program$||')
[ "${#roots[@]}" -eq 1 ] || { echo "expected one program/soffice.bin under $target, found ${#roots[@]}" >&2; exit 1; }
root="${roots[0]}"; new=0
while IFS= read -r f; do
  [ -e "$root/$f" ] || { echo "new file (not in the reference package): $f"; new=$((new + 1)); }
  install -D -m "$(stat -c %a "$here/files/$f")" "$here/files/$f" "$root/$f"
done < "$here/FILES"
echo "applied $(wc -l < "$here/FILES") files onto $root ($new new); TEST ONLY"
