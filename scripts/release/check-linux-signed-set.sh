#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# A release's Linux packages are the GPG-signed set once the packaging key is configured (the public key committed at
# data/hst/RPM-GPG-KEY-hasontech): .rpm, every .AppImage with its .asc, the Linux SHA256SUMS with its .asc, and the
# public key, which must be the committed one. Used by collect-release-assets.sh; docs/LINUX_PACKAGES.md.
#   check-linux-signed-set.sh <artifact-dir>     exit 1 with the missing parts listed
set -euo pipefail
dir="${1:?usage: $0 <artifact-dir>}"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
missing=()
shopt -s nullglob
rpms=("$dir"/HSTOffice_*_Linux_x86-64.rpm); apps=("$dir"/HSTOffice_*_Linux_x86-64.AppImage)
sums=("$dir"/HSTOffice_*_Linux_x86-64.SHA256SUMS)
[ ${#rpms[@]} -gt 0 ] || missing+=(".rpm")
[ ${#apps[@]} -gt 0 ] || missing+=(".AppImage")
for app in "${apps[@]}"; do [ -f "$app.asc" ] || missing+=("$(basename "$app").asc"); done
if [ ${#sums[@]} -eq 1 ]; then [ -f "${sums[0]}.asc" ] || missing+=("$(basename "${sums[0]}").asc")
else missing+=("one HSTOffice_<release>_Linux_x86-64.SHA256SUMS"); fi
key="$dir/RPM-GPG-KEY-hasontech"
if [ ! -f "$key" ]; then missing+=("RPM-GPG-KEY-hasontech")
elif ! cmp -s "$key" "$repo/data/hst/RPM-GPG-KEY-hasontech" && command -v gpg >/dev/null; then
  fpr() { gpg --batch --with-colons --show-keys "$1" 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}'; }
  [ "$(fpr "$key")" = "$(fpr "$repo/data/hst/RPM-GPG-KEY-hasontech")" ] || missing+=("RPM-GPG-KEY-hasontech of the committed key")
fi
if [ ${#missing[@]} -gt 0 ]; then
  printf 'linux release: the signed set lacks: %s\n' "${missing[*]}" >&2
  exit 1
fi
echo "linux release: signed set complete (${#rpms[@]} rpm, ${#apps[@]} AppImage)"
