#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Start-up timing of an HST Office MSI on a GitHub Windows runner (Git Bash), with the variants that split the time.
#   startup-timing-windows.sh <HST msi> <out-dir> [variants]
# variants (comma list, default all): hst (fresh, warm, warm, cold), trace (the Python tracer), noext (the HST
# extension moved out), pyc (the installation's Python modules compiled to unchecked-hash bytecode first), defender (real-time scanning on, then the install excluded), lo (stock LibreOffice MSI of
# $LO_MSI_URL / $LO_MSI_SHA256), scale150 (splash and Start Center at 150 %). "cold" empties the standby list (the
# file cache) with RAMMap first: a start after a reboot. Evidence only; fails only when nothing could be installed.
set -Eeuo pipefail
msi="$1"; out="$2"; variants=",${3:-hst,trace,noext,pyc,defender,lo,scale150},"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
mkdir -p "$out"; work="$(cygpath -u "$RUNNER_TEMP")/startup-work"; mkdir -p "$work"
w() { cygpath -w "$1"; }
has() { [[ "$variants" == *",$1,"* ]]; }
msiexec_q() { MSYS2_ARG_CONV_EXCL='*' msiexec.exe "$@"; }

# The runner itself: CPU, disk, Defender state (users have real-time scanning on).
pwsh -NoProfile -Command 'Get-CimInstance Win32_Processor | Select-Object Name,NumberOfLogicalProcessors | Format-List;
  Get-PhysicalDisk | Select-Object MediaType,BusType,Size | Format-List;
  Get-MpComputerStatus | Select-Object AMServiceEnabled,RealTimeProtectionEnabled,OnAccessProtectionEnabled,IsTamperProtected | Format-List;
  Get-MpPreference | Select-Object ExclusionPath,DisableRealtimeMonitoring | Format-List' > "$out/runner.txt" 2>&1 || echo "runner facts incomplete" >> "$out/runner.txt"

# RAMMap empties the standby list: the next start reads every file from disk again.
rammap=""
if curl -fsSL --retry 3 -o "$work/RAMMap.zip" https://download.sysinternals.com/files/RAMMap.zip; then
  unzip -oq "$work/RAMMap.zip" -d "$work/rammap" && rammap="$work/rammap/RAMMap64.exe"
  MSYS2_ARG_CONV_EXCL='*' reg.exe add 'HKCU\Software\Sysinternals\RamMap' /v EulaAccepted /t REG_DWORD /d 1 /f >/dev/null
fi
cold="rem"
if [ -n "$rammap" ]; then r="\"$(w "$rammap")\""; cold="$r -Ew && $r -Es && $r -Em && $r -Et"; fi

msiexec_q /i "$(w "$msi")" /qn /norestart /l*v "$(w "$out/hst-install.log")"
soffice="$(find '/c/Program Files' -maxdepth 4 -ipath '*HST*' -iname soffice.exe | head -n 1)"
[ -n "$soffice" ] || { echo "HST soffice.exe not found after install" >&2; exit 1; }
program="$(dirname "$soffice")"; install="$(dirname "$program")"
echo "HST installed at $install"
{ echo "python files: $(find "$install" -name '*.py' | wc -l)"
  echo "pyc files: $(find "$install" -name '*.pyc' | wc -l)"
  echo "bundled extensions: $(ls "$install/share/extensions" | tr '\n' ' ')"
  echo "share/extensions files: $(find "$install/share/extensions" -type f | wc -l)"
  grep -iE '^(Logo|NativeProgress|Progress)' "$program/soffice.ini" "$program/sofficerc" 2>/dev/null || true
} > "$out/hst-install-facts.txt"
SUDO=""
overlay() { # overlay <extension dir>: the HST extension built from this commit instead of the bundled one
  [ -n "${HST_OVERLAY_OXT:-}" ] || return 0
  $SUDO rm -rf "$1" && $SUDO mkdir -p "$1"
  python -I -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$HST_OVERLAY_OXT" "$(w "$1")"
  echo "overlaid $1 with $(basename "$HST_OVERLAY_OXT")" | tee -a "$out/overlay.txt"
}
overlay "$install/share/extensions/hst-vietnamese-tools"

timing() { # timing <label> <soffice> <starts> [more harness options]
  local label="$1" office="$2" starts="$3"; shift 3
  python -I "$(w "$here/startup-timing.py")" --soffice "$(w "$office")" --python "$(w "$(dirname "$office")/python.exe")" \
    --intro "$(w "$(dirname "$office")/intro.png")" --profile "$(w "$work/profile-$label")" --out "$(w "$out")" \
    --label "$label" --starts "$starts" --cold-command "$cold" "$@" || echo "$label: no window seen" >> "$out/failures.txt"
  MSYS2_ARG_CONV_EXCL='*' taskkill.exe /F /IM soffice.bin /IM soffice.exe >/dev/null 2>&1 || echo "no office left running"
}

has hst && timing hst "$soffice" fresh,warm,warm,cold --shots
has trace && timing hst-trace "$soffice" fresh,warm,cold --trace
if has noext; then
  mv "$install/share/extensions/hst-vietnamese-tools" "$work/hst-ext-aside"
  timing hst-noext "$soffice" fresh,warm,cold
  mv "$work/hst-ext-aside" "$install/share/extensions/hst-vietnamese-tools"
fi
if has pyc; then
  # what a build step would ship: bytecode the office's Python uses without checking the source
  for dir in "$program" "$install/share/extensions"; do
    "$program/python.exe" -I -m compileall -q -j 0 --invalidation-mode unchecked-hash "$(w "$dir")" \
      >> "$out/pyc-compile.log" 2>&1 || echo "compileall $dir exit $?" >> "$out/pyc-compile.log"
  done
  echo "pyc files now: $(find "$install" -name '*.pyc' | wc -l)" >> "$out/pyc-compile.log"
  timing hst-pyc "$soffice" fresh,warm,cold --trace
  # back to the installed state (it shipped no bytecode when the facts above count none)
  if grep -q '^pyc files: 0$' "$out/hst-install-facts.txt"; then find "$install" -name __pycache__ -type d -prune -exec rm -rf {} +; fi
fi
if has defender; then
  # real-time scanning as users have it, then with the install folder excluded
  pwsh -NoProfile -Command 'Set-MpPreference -DisableRealtimeMonitoring $false; Start-Sleep 3; (Get-MpComputerStatus).RealTimeProtectionEnabled' \
    > "$out/defender-on.txt" 2>&1 || echo "could not enable" >> "$out/defender-on.txt"
  timing hst-scan-on "$soffice" fresh,warm,cold --trace
  pwsh -NoProfile -Command "Add-MpPreference -ExclusionPath '$(w "$install")'; Start-Sleep 2; (Get-MpPreference).ExclusionPath" \
    > "$out/defender-exclusion.txt" 2>&1 || echo "could not exclude" >> "$out/defender-exclusion.txt"
  timing hst-scan-excluded "$soffice" fresh,warm,cold --trace
  pwsh -NoProfile -Command "Remove-MpPreference -ExclusionPath '$(w "$install")'" >/dev/null 2>&1 || echo "exclusion kept"
fi
if has scale150; then
  python -I -c "import sys; sys.path.insert(0, sys.argv[1]); import windows_dpi; print(windows_dpi.set_scale(150))" \
    "$(w "$repo/tests/runtime/r1auto")" > "$out/scale150.txt" 2>&1 || echo "scale not set" >> "$out/scale150.txt"
  timing hst-scale150 "$soffice" fresh,warm --shots
  python -I -c "import sys; sys.path.insert(0, sys.argv[1]); import windows_dpi; print(windows_dpi.set_scale(100))" \
    "$(w "$repo/tests/runtime/r1auto")" >> "$out/scale150.txt" 2>&1 || echo "scale not reset" >> "$out/scale150.txt"
fi
if has lo && [ -n "${LO_MSI_URL:-}" ]; then
  lo_msi="$work/LibreOffice.msi"
  if curl -fsSL --retry 3 -o "$lo_msi" "$LO_MSI_URL" || curl -fsSL --retry 3 -o "$lo_msi" "${LO_MSI_ARCHIVE_URL:-}"; then
    echo "$LO_MSI_SHA256  $lo_msi" | sha256sum -c
    msiexec_q /i "$(w "$lo_msi")" /qn /norestart /l*v "$(w "$out/lo-install.log")"
    lo="$(find '/c/Program Files/LibreOffice/program' -maxdepth 1 -iname soffice.exe | head -n 1)"
    [ -z "$lo" ] || timing lo "$lo" fresh,warm,warm,cold
  fi
fi
python -I "$(w "$here/startup-timing-summary.py")" "$(w "$out")" > "$out/summary.md"
cat "$out/summary.md"
