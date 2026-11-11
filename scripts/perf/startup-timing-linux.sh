#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Start-up timing of the HST Office .deb on a GitHub Ubuntu runner (Xvfb, no window manager), with the variants that
# split the time. Usage: startup-timing-linux.sh <deb-dir> <out-dir> [variants]
# variants (default all): hst (the installed office: fresh, warm x3, cold), trace (with the Python tracer), noext (the
# HST extension moved out), lazy / lazy-trace (the extension of $HST_OVERLAY_OXT, built from this checkout), lazy-pyc
# (that extension and the installation's Python modules compiled to unchecked-hash bytecode), lo (stock LibreOffice
# debs of $LO_DEB_URL, unpacked, not installed). "cold" drops the kernel's page cache first: a start after a reboot.
# Evidence only.
set -Eeuo pipefail
debs="$1"; out="$2"; variants=",${3:-hst,trace,noext,lazy,lazy-trace,lazy-pyc,lo},"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$RUNNER_TEMP/startup-work"; mkdir -p "$work"
has() { [[ "$variants" == *",$1,"* ]]; }
{ nproc; grep -m1 'model name' /proc/cpuinfo; lsblk -d -o NAME,ROTA,SIZE; } > "$out/runner.txt" 2>&1 || echo "runner facts incomplete" >> "$out/runner.txt"
sudo apt-get install -y -q "$debs"/*.deb > "$out/hst-install.log" 2>&1
soffice="$(find /opt -maxdepth 3 -path '*hst-office*/program/soffice' | head -n 1)"
[ -n "$soffice" ] || { echo "HST soffice not found after install" >&2; exit 1; }
program="$(dirname "$soffice")"; install="$(dirname "$program")"
{ echo "python files: $(find "$install" -name '*.py' | wc -l)"
  echo "pyc files: $(find "$install" -name '*.pyc' | wc -l)"
  echo "bundled extensions: $(ls "$install/share/extensions" | tr '\n' ' ')"
  grep -E '^(Logo|NativeProgress|Progress)' "$program/sofficerc" || true
} > "$out/hst-install-facts.txt"
Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp > "$work/xvfb.log" 2>&1 &
xvfb=$!
trap 'kill "$xvfb" 2>/dev/null || true' EXIT
export DISPLAY=:99
sleep 2
cold="sync && echo 3 | sudo tee /proc/sys/vm/drop_caches"

ext="$install/share/extensions/hst-vietnamese-tools"
sudo cp -r "$ext" "$work/ext-installed"
use_ext() { # use_ext installed|overlay: which HST extension the next starts load
  sudo rm -rf "$ext"
  if [ "$1" = installed ]; then sudo cp -r "$work/ext-installed" "$ext"; return 0; fi
  sudo mkdir -p "$ext"
  sudo python3 -I -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$HST_OVERLAY_OXT" "$ext"
}
use_pyc() { # use_pyc on|off: unchecked-hash bytecode next to every Python module of the installation (it ships none)
  if [ "$1" = off ]; then sudo find "$install" -name __pycache__ -type d -prune -exec rm -rf {} +; return 0; fi
  for dir in "$program" "$install/share/extensions"; do
    sudo "$program/python" -m compileall -q --invalidation-mode unchecked-hash "$dir" >> "$out/pyc-compile.log" 2>&1 \
      || echo "compileall $dir exit $?" >> "$out/pyc-compile.log"
  done
  echo "pyc files now: $(find "$install" -name '*.pyc' | wc -l)" >> "$out/pyc-compile.log"
}
timing() { # timing <label> <soffice> <starts> [more harness options]
  local label="$1" office="$2" starts="$3"; shift 3
  python3 -I "$here/startup-timing.py" --soffice "$office" --python "$(dirname "$office")/python" \
    --intro "$(dirname "$office")/intro.png" --profile "$work/profile-$label" --out "$out" --label "$label" \
    --starts "$starts" --cold-command "$cold" "$@" || echo "$label: no window seen" >> "$out/failures.txt"
}
starts=fresh,warm,warm,warm,cold

if has hst; then timing hst "$soffice" "$starts" --shots; fi
if has trace; then timing hst-trace "$soffice" fresh,warm,cold --trace; fi
if has noext; then sudo rm -rf "$ext"; timing hst-noext "$soffice" "$starts"; use_ext installed; fi
if [ -n "${HST_OVERLAY_OXT:-}" ]; then
  use_ext overlay
  if has lazy; then timing lazy "$soffice" "$starts"; fi
  if has lazy-trace; then timing lazy-trace "$soffice" fresh,warm,cold --trace; fi
  if has lazy-pyc; then use_pyc on; timing lazy-pyc "$soffice" "$starts" --trace; use_pyc off; fi
  use_ext installed
fi
if has lo && [ -n "${LO_DEB_URL:-}" ]; then
  if curl -fsSL --retry 3 -o "$work/lo.tar.gz" "$LO_DEB_URL"; then
    sha256sum "$work/lo.tar.gz" > "$out/lo-deb.sha256"
    mkdir -p "$work/lo-debs" "$work/lo-root"
    tar -xzf "$work/lo.tar.gz" -C "$work/lo-debs"
    for deb in "$work"/lo-debs/*/DEBS/*.deb; do dpkg -x "$deb" "$work/lo-root"; done
    lo="$(find "$work/lo-root/opt" -maxdepth 3 -path '*/program/soffice' | head -n 1)"
    if [ -n "$lo" ]; then timing lo "$lo" "$starts"; fi
  fi
fi
python3 -I "$here/startup-timing-summary.py" "$out" > "$out/summary.md"
cat "$out/summary.md"
