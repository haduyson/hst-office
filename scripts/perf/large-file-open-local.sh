#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Large-file open times of a local build (build queue output) on this Linux machine or on a Windows test PC.
#   large-file-open-local.sh linux   <.deb | queue job id> <out-dir> [harness options]
#   large-file-open-local.sh <host>  <.msi | queue job id> <out-dir> [harness options]   (host: hst4, hst5)
# harness options go to large-file-open.py: --label L (default: the package's name), --only a,b, --mode gui|cli|headless,
# --seed default|spell|..., --cpus N, --repeat N, --timeout S, --save. Fixtures (large_file_fixtures.py) are written
# once to $LFO_FIXTURES (default <out-dir>/../fixtures); FIXTURE_ARGS passes options to the generator (e.g. --rows).
# Linux: the .deb is unpacked (dpkg-deb -x, nothing installed) under <out-dir>/inst and runs under its own Xvfb on
# display :$LFO_DISPLAY (default 73; a display already in use stops the run). Windows: the .msi is unpacked as an
# administrative image (msiexec /a, nothing installed) under D:\hst-test\large-open on the host, and the harness runs
# there in the SSH session (no desktop: use --mode headless or cli) through $HST_REMOTE (remote.py of tests/realwin).
# Summary: <out-dir>/summary.md (large-file-open-summary.py). See docs/PERFORMANCE_LARGE_FILES.md.
set -Eeuo pipefail
target="$1"; pkg="$2"; out="$(mkdir -p "$3" && cd "$3" && pwd)"; shift 3
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
queue_out="${HST_QUEUE_OUT:-/data/hst-build-queue/out}"
ext=deb; [ "$target" = linux ] || ext=msi
if [ ! -f "$pkg" ]; then pkg="$(find "$queue_out/$pkg" -maxdepth 1 -name "*.$ext" | head -n 1)"; fi
[ -f "$pkg" ] || { echo "no .$ext for $2" >&2; exit 2; }
fixtures="${LFO_FIXTURES:-$(dirname "$out")/fixtures}"
label="$(basename "$out")"
for arg in "$@"; do [ "${prev:-}" = --label ] && label="$arg"; prev="$arg"; done
only=""; prev=""; for arg in "$@"; do [ "$prev" = --only ] && only="$arg"; prev="$arg"; done
# missing fixtures only; a directory that already has files and no --only is used as it is (own fixtures)
if [ -n "$only" ] || [ -z "$(ls -A "$fixtures" 2>/dev/null)" ]; then
  python3 -I "$here/large_file_fixtures.py" "$fixtures" ${only:+--only "$only"} \
    --skip "$(cd "$fixtures" 2>/dev/null && ls | paste -sd, || true)" ${FIXTURE_ARGS:-} | tee -a "$out/fixtures.txt"
fi
sha256sum "$pkg" > "$out/package.sha256"

if [ "$target" = linux ]; then
  inst="$out/inst"
  if ! cmp -s "$out/package.sha256" "$inst/.package.sha256" 2>/dev/null; then
    rm -rf "$inst"; dpkg-deb -x "$pkg" "$inst"; cp "$out/package.sha256" "$inst/.package.sha256"
  fi
  soffice="$(find "$inst/opt" -maxdepth 3 -path '*/program/soffice' | head -n 1)"
  display="${LFO_DISPLAY:-73}"
  if [ -e "/tmp/.X11-unix/X$display" ] || [ -e "/tmp/.X$display-lock" ]; then
    echo "display :$display is in use (stop its owner or set LFO_DISPLAY)" >&2; exit 3
  fi
  Xvfb ":$display" -screen 0 1600x1000x24 -nolisten tcp > "$out/xvfb.log" 2>&1 &
  xvfb=$!
  trap 'kill "$xvfb" 2>/dev/null || true' EXIT
  sleep 2
  { nproc; grep -m1 'model name' /proc/cpuinfo; } > "$out/machine.txt"
  DISPLAY=":$display" SAL_USE_VCLPLUGIN=gen python3 -I "$here/large-file-open.py" --soffice "$soffice" \
    --python "$(dirname "$soffice")/python" --files "$fixtures" --out "$out" --label "$label" "$@" || true
else
  remote="${HST_REMOTE:-/home/wt-realwin-102/tests/realwin/remote.py}"
  root='D:\hst-test\large-open'
  python3 "$remote" "$target" push "$here"/large*file*.py "$here/large-file-open-windows.ps1" "$root\\scripts"
  python3 "$remote" "$target" push "$pkg" "$root\\pkg\\$label"
  # the fixtures this run opens (all of them without --only)
  if [ -n "$only" ]; then
    files=(); IFS=, read -ra names <<< "$only"; for n in "${names[@]}"; do files+=("$fixtures/$n"); done
    python3 "$remote" "$target" push "${files[@]}" "$root\\fixtures"
  else
    python3 "$remote" "$target" push "$fixtures" "$root"
  fi
  python3 -I -c 'import sys; sys.path.insert(0, sys.argv[1]); import remote
done = remote.run_ps(sys.argv[2], sys.argv[3], *sys.argv[4:], timeout=6 * 3600, check=False)
print(done.stdout[-4000:]); print(done.stderr[-2000:], file=sys.stderr)' "$(dirname "$remote")" "$target" \
    "$here/large-file-open-windows.ps1" "$root" "$label" "$(basename "$pkg")" "$@" | tee "$out/remote.log" || true
  python3 "$remote" "$target" pull "$root\\out\\$label\\$label.jsonl" "$out" || true
  python3 "$remote" "$target" pull "$root\\out\\$label\\machine.txt" "$out" || true
fi
python3 -I "$here/large-file-open-summary.py" "$out" > "$out/summary.md"
cat "$out/summary.md"
