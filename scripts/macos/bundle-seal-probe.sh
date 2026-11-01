#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Prove that an HST Office session leaves its own app bundle untouched when the bundle is user-writable (an admin's
# /Applications): no file added or rewritten, `codesign --verify --deep --strict` still passes.
#   bundle-seal-probe.sh <HSTOffice_*.dmg> <out-dir> [required|informational]
# The app is copied out of the dmg unchanged (ditto, as a Finder drag does; no re-signing) once per session:
#   as-shipped    the office as users start it;
#   no-bytecode   with PYTHONDONTWRITEBYTECODE=1 in the office's environment (what the pyuno loader sets since
#                 hst-python-no-bytecode.patch; children such as the update helper or the USB token worker inherit it);
#   cache-prefix  with PYTHONPYCACHEPREFIX in a temporary folder (the alternative: caches outside the bundle).
# Each session (bundle-seal-session.py over UNO): Writer with text, HST ▸ Kiểm tra cập nhật…, the Văn bản hành chính
# wizard, quit. Before/after: the bundle's file list with size and mtime, and the signature check.
# Also records which shipped .pyc files of the Python framework are stale for their source (pyc-staleness.txt).
# Exit 1 when no-bytecode leaves a trace, or when as-shipped does and the third argument is "required" (default).
set -Eeuo pipefail
[ $# -ge 2 ] || { echo "usage: $0 <dmg> <out-dir> [required|informational]" >&2; exit 64; }
dmg="$1"; out="$2"; baseline="${3:-required}"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$baseline" in required|informational) ;; *) echo "bad baseline mode: $baseline" >&2; exit 64;; esac
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
trap 'hdiutil detach "$mnt" >/dev/null 2>&1 || true' EXIT
status=0; summary="$out/summary.md"; port=2093
printf '# macOS bundle seal after a session\n\n' >"$summary"
note() { printf -- '- %s\n' "$*" | tee -a "$summary"; }
listing() { find "$1" -print0 | xargs -0 stat -f '%z %m %N' | LC_ALL=C sort -k3; }

session() {  # session <name> [VAR=value...]: copy, list, start, drive, quit, compare
  local name="$1" app="$work/$1/HST Office.app" profile="$work/$1/profile" pid py pyuno rc changes
  shift
  mkdir -p "$work/$name" "$profile/user"
  ditto "$mnt/HST Office.app" "$app"
  py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
  pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
  codesign --verify --deep --strict "$app" || { note "FAIL $name: signature does not verify before the session"; status=1; }
  listing "$app" >"$out/$name-before.txt"
  # no welcome dialog (modal); every other start-up job of the extension runs
  cat >"$profile/user/registrymodifications.xcu" <<'XCU'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.hasontech.hstoffice.Welcome"><prop oor:name="Shown" oor:op="fuse"><value>true</value></prop></item>
</oor:items>
XCU
  env -u PYTHONDONTWRITEBYTECODE -u PYTHONPYCACHEPREFIX "$@" "$app/Contents/MacOS/soffice" --norestore --nologo \
    --nodefault --nolockcheck "--accept=socket,host=127.0.0.1,port=$port;urp;" "-env:UserInstallation=file://$profile" \
    >"$out/$name-soffice.log" 2>&1 &
  pid=$!
  # the driver's own Python writes nothing (-B); the office it drives gets only the variables above
  rc=0
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" PYTHONPATH="$app/Contents/Resources:$(dirname "$pyuno")" \
    perl -e 'alarm 300; exec @ARGV' "$py" -B "$here/bundle-seal-session.py" "$port" "$out/$name-session.log" || rc=$?
  for _ in $(seq 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  if kill -0 "$pid" 2>/dev/null; then note "$name: the office did not quit within 60 s, stopped"; kill "$pid"; sleep 3; kill -9 "$pid" 2>/dev/null || true; fi
  wait "$pid" 2>/dev/null || true
  [ "$rc" -eq 0 ] || { note "FAIL $name: session driver exit $rc ($name-session.log)"; status=1; }
  listing "$app" >"$out/$name-after.txt"
  diff "$out/$name-before.txt" "$out/$name-after.txt" | grep -E '^[<>]' >"$out/$name-bundle-changes.txt" || true
  changes="$(grep -c '^>' "$out/$name-bundle-changes.txt" || true)"
  local verdict=PASS
  if codesign --verify --deep --strict -vvvv "$app" >"$out/$name-codesign-after.txt" 2>&1 && [ "$changes" -eq 0 ]; then
    note "PASS $name: bundle unchanged, signature verifies after the session"
  else
    verdict=FAIL
    note "$name: $changes bundle entries added or rewritten ($name-bundle-changes.txt): $(grep '^>' "$out/$name-bundle-changes.txt" | sed -E 's#.*/Contents/##' | head -3 | tr '\n' ' ')"
    note "$name: codesign after the session: $(grep -m 2 -E 'modified|added|missing|invalid' "$out/$name-codesign-after.txt" | sed -E 's#/[^ ]*/Contents/#Contents/#g' | tr '\n' ' ' | cut -c1-300)"
  fi
  if [ "$verdict" = FAIL ]; then
    if [ "$name" = as-shipped ] && [ "$baseline" = informational ]; then note "INFO $name: bundle modified (baseline informational)"
    elif [ "$name" = cache-prefix ]; then note "INFO $name: bundle modified (alternative only)"
    else note "FAIL $name: bundle modified"; status=1; fi
  fi
  if [ -n "$*" ] && [ -d "$work/pycache" ]; then note "$name: caches outside the bundle: $(find "$work/pycache" -name '*.pyc' | wc -l | tr -d ' ') .pyc"; fi
  printf '%s\n' "$py" >"$work/python"
}

note "macOS $(sw_vers -productVersion), app $(defaults read "$mnt/HST Office.app/Contents/Info.plist" CFBundleShortVersionString), $(basename "$dmg")"
# Shipped bytecode: a .pyc whose recorded source mtime/size differ from its .py is recompiled at every import and,
# when the folder is writable, rewritten (the "file modified" entries of a broken seal).
py="$(find "$mnt/HST Office.app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
"$py" -I -B - "$mnt/HST Office.app/Contents" >"$out/pyc-staleness.txt" 2>&1 <<'PY' || true
import os, struct, sys
counts, stale = {}, []
for root, dirs, files in os.walk(sys.argv[1]):
    if os.path.basename(root) != "__pycache__":
        continue
    for name in files:
        if not name.endswith(".pyc"):
            continue
        source = os.path.join(os.path.dirname(root), name.split(".")[0] + ".py")
        with open(os.path.join(root, name), "rb") as handle:
            flags, mtime, size = struct.unpack("<4xIII", handle.read(16))
        if flags:
            kind = "hash-based"
        elif not os.path.exists(source):
            kind = "no source"
        else:
            st = os.stat(source)
            kind = "fresh" if (int(st.st_mtime) & 0xFFFFFFFF, st.st_size & 0xFFFFFFFF) == (mtime, size) else "stale"
            if kind == "stale" and len(stale) < 20:
                stale.append("%s: pyc mtime %d size %d, source mtime %d size %d" % (source, mtime, size, int(st.st_mtime), st.st_size))
        counts[kind] = counts.get(kind, 0) + 1
print("shipped .pyc:", counts)
print("\n".join(stale))
PY
note "shipped bytecode: $(head -1 "$out/pyc-staleness.txt")"
session as-shipped
session no-bytecode PYTHONDONTWRITEBYTECODE=1
session cache-prefix "PYTHONPYCACHEPREFIX=$work/pycache"
# What not writing caches costs: compile time of the extension's modules (done on every start without caches).
"$(cat "$work/python")" -I -B - "$work/as-shipped/HST Office.app/Contents/Resources/extensions/hst-vietnamese-tools/python" >"$out/compile-time.txt" 2>&1 <<'PY' || true
import os, sys, time
paths = [os.path.join(r, f) for r, _d, fs in os.walk(sys.argv[1]) for f in fs if f.endswith(".py")]
start = time.perf_counter()
for path in paths:
    compile(open(path, encoding="utf-8").read(), path, "exec")
print("%d extension modules compiled in %.0f ms" % (len(paths), (time.perf_counter() - start) * 1000))
PY
note "$(head -1 "$out/compile-time.txt")"
exit "$status"
