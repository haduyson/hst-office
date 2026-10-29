#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Inventory prerequisites and print the exact configure command; no build claim.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
arch="$(uname -m)"
if [[ $# -gt 0 ]]; then
  [[ $# == 2 && "$1" == --arch ]] || { printf 'usage: %s [--arch arm64|x86_64]\n' "$0" >&2; exit 64; }
  arch="$2"
fi
case "$arch" in arm64|x86_64) ;; *) printf 'BLOCKED: unsupported architecture %s\n' "$arch" >&2; exit 1 ;; esac
config="$ROOT/build-config/macos-$arch.conf"
source_dir="$ROOT/upstream/libreoffice"
[[ -f "$config" ]] || { printf 'BLOCKED: missing %s\n' "$config" >&2; exit 1; }
options=()
while IFS= read -r option || [[ -n "$option" ]]; do
  [[ -z "$option" || "$option" == \#* ]] && continue
  [[ "$option" == --* ]] || { printf 'BLOCKED: invalid configure argument\n' >&2; exit 1; }
  options+=("$option")
done < "$config"
printf 'UNVERIFIED configure invocation (not executed):\n(cd %q && ./autogen.sh' "$source_dir"
printf ' %q' "${options[@]}"
printf ')\n'
block() { printf 'BLOCKED: %s\n' "$*" >&2; exit 1; }
[[ "$(uname -s)" == Darwin ]] || block 'requires macOS with a native Xcode toolchain; Linux cannot validate this build'
[[ "$(uname -m)" == "$arch" ]] || block "requires native $arch host; cross-compilation/Rosetta is unverified"
for tool in xcodebuild xcrun clang clang++ make autoconf automake perl pkg-config bison flex gperf zip codesign pkgbuild productbuild; do
  command -v "$tool" >/dev/null || block "missing tool: $tool"
done
xcodebuild -version
xcode_version="$(xcodebuild -version | awk '/^Xcode / { print $2 }')"
sdk_version="$(xcrun --sdk macosx --show-sdk-version)"
printf 'macOS SDK: %s\n' "$sdk_version"
version_at_least() { awk -v actual="$1" -v required="$2" 'BEGIN {
  split(actual,a,"."); split(required,b,"."); exit !((a[1]*100+a[2]) >= (b[1]*100+b[2]))
}'; }
version_at_least "$xcode_version" 14.3 || block 'Xcode >=14.3 required by pinned configure.ac'
[[ "$xcode_version" != 15.0 ]] || block 'Xcode 15.0 linker is rejected by upstream for the macOS 11 target'
version_at_least "$sdk_version" 13.3 || block 'macOS SDK >=13.3 required by pinned configure.ac'
[[ -d "$(xcrun --sdk macosx --show-sdk-path)" ]] || block 'selected SDK path does not exist'
free_kib="$(df -Pk "$ROOT" | awk 'END {print $4}')"
(( free_kib * 1024 >= 100000000000 )) || block 'OPS-01: at least 100 GB free disk required'
(( $(sysctl -n hw.memsize) >= 16 * 1024 * 1024 * 1024 )) || block 'OPS-01: at least 16 GiB RAM required'
[[ -f "$source_dir/configure.ac" && -f "$source_dir/autogen.sh" ]] || block 'missing pinned LibreOffice source checkout'
for asset in intro.png about.svg logo.svg; do
  [[ -f "$ROOT/branding/libreoffice/$asset" ]] || block "missing branding asset: $asset"
done
printf 'Prerequisite inventory complete; configure was not executed.\n'
block 'TODO: needs validated HST patch integration, signing/notarization credentials and platform QA (SIGN-01, QA-01)'
