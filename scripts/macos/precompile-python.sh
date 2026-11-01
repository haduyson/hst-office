#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Give HST Office.app valid, sealed Python bytecode before it is signed.
#   precompile-python.sh <HST Office.app>
# Upstream compiles the framework's standard library at `make install`, then copies the framework into the
# installation with `cp -R`, which gives every .py a later mtime: all shipped .pyc are stale, so Python recompiles
# each module at every start (and, in a bundle the user can write to, rewrote them before
# hst-python-no-bytecode.patch). The office's own Python (uno.py, pythonloader.py, ...) and the bundled extensions
# ship no bytecode at all. This compiles all of them with the bundled interpreter as unchecked-hash .pyc, which
# Python uses without comparing them to the source (the signed bundle is immutable). Run after the last change to the
# bundle's files and before signing.
set -Eeuo pipefail
[ $# -eq 1 ] || { echo "usage: $0 <HST Office.app>" >&2; exit 64; }
app="$1"
py="$(find "$app/Contents/Frameworks/LibreOfficePython.framework/Versions" -path '*/bin/python3.*' -type f -perm -u+x \
  ! -name '*-config' | head -1)"
[ -n "$py" ] || { echo "precompile: no bundled python3 in $app" >&2; exit 1; }
lib="$(dirname "$py")/../lib/$(basename "$py")"
[ -d "$lib" ] || { echo "precompile: no standard library at $lib" >&2; exit 1; }
res="$app/Contents/Resources"
# -l: the office's own modules sit at the top of Resources; extensions and the standard library are recursive.
# All three optimization levels, as installed. Excluded: files of the standard library that are deliberately
# invalid (as Python's own `make install` does).
env -u PYTHONDONTWRITEBYTECODE -u PYTHONPYCACHEPREFIX "$py" -I -m compileall -q -f -j 0 -o 0 -o 1 -o 2 \
  --invalidation-mode unchecked-hash -x '(bad_coding|badsyntax|test_lib2to3/data)' "$lib" "$res/extensions"
env -u PYTHONDONTWRITEBYTECODE -u PYTHONPYCACHEPREFIX "$py" -I -m compileall -q -f -l \
  --invalidation-mode unchecked-hash "$res"
# Gate: no timestamp-based (stale-prone) .pyc is left.
"$py" -I -B - "$app/Contents" <<'PY'
import os, sys
total = checked = 0
for root, _dirs, files in os.walk(sys.argv[1]):
    for name in files:
        if name.endswith(".pyc"):
            with open(os.path.join(root, name), "rb") as handle:
                flags = int.from_bytes(handle.read(8)[4:8], "little")
            total += 1
            checked += flags != 3
if checked:
    sys.exit("precompile: %d of %d .pyc are not unchecked-hash" % (checked, total))
print("precompile: %d unchecked-hash .pyc" % total)
PY
