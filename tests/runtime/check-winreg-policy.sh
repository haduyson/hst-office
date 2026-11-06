#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Run the Windows policy-key logic of configmgr (hst-own-policy-paths.patch) on Linux against an in-memory registry.
#   tests/runtime/check-winreg-policy.sh [LO_SRC]     (default: $HST_LO_SRC or upstream/libreoffice)
# Needs a built Linux tree (instdir/program/libuno_sal.so.3 and the generated UNO headers). winreg.cxx is copied with
# the tree's other files into a scratch directory; when the tree does not carry the patch yet it is applied there.
# The tree itself is only read. Exit status 1 when a check fails.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$(cd "${1:-${HST_LO_SRC:-$ROOT/upstream/libreoffice}}" && pwd)"
HERE="$ROOT/tests/runtime/winreg-policy"
PATCH="$ROOT/patches/libreoffice/hst-own-policy-paths.patch"
PROGRAM="$SRC/instdir/program"
UNOHEADERS="$SRC/workdir/UnoApiHeadersTarget/udkapi/normal"
for need in "$PROGRAM/libuno_sal.so.3" "$PROGRAM/libuno_cppu.so.3" "$UNOHEADERS/com/sun/star/uno/RuntimeException.hpp"; do
  [ -e "$need" ] || { echo "not a built tree: $need is missing" >&2; exit 2; }
done
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
for f in configmgr/source/winreg.cxx configmgr/source/winreg.hxx shell/source/win32/simplemail/smplmailclient.cxx; do
  mkdir -p "$work/tree/$(dirname "$f")"
  cp "$SRC/$f" "$work/tree/$f"
done
if ! grep -q 'HASON TECH' "$work/tree/configmgr/source/winreg.cxx"; then
  patch -d "$work/tree" -p1 -s --no-backup-if-mismatch < "$PATCH"
fi
cp "$HERE/writemodfile.hxx" "$work/tree/configmgr/source/"  # found before the tree's: same directory as winreg.cxx
# -fshort-wchar: a 16-bit wchar_t as on Windows, so the registry strings and o3tl::toW/toU behave the same
"${CXX:-g++}" -std=c++20 -fshort-wchar -Wall -Wextra -Wno-unused-parameter -Werror \
  -DLINUX -DUNX -DX86_64 -D_REENTRANT -DCPPU_ENV=gcc3 -DOSL_DEBUG_LEVEL=0 -DLIBO_INTERNAL_ONLY \
  -I"$work/tree/configmgr/source" -I"$HERE/inc" -I"$SRC/include" -I"$SRC/config_host" -I"$UNOHEADERS" \
  -o "$work/test" "$HERE/test-winreg-policy.cxx" "$work/tree/configmgr/source/winreg.cxx" \
  -L"$PROGRAM" -l:libuno_sal.so.3 -l:libuno_cppu.so.3 -Wl,-rpath,"$PROGRAM"
"$work/test"
