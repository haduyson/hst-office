#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Start-up timing of an HST Office MSI on a GitHub Windows runner (Git Bash), with the variants that split the time.
#   startup-timing-windows.sh <HST msi> <out-dir> [variants]
# variants (comma list, default all): hst (the installed office: fresh, warm x3, cold), trace (with the Python
# tracer), noext (the HST extension moved out), lazy / lazy-trace (the extension of $HST_OVERLAY_OXT, built from this
# checkout, instead of the installed one), lazy-cache (that extension with a per-user bytecode cache in the profile),
# lazy-pyc (that extension, and the installation's Python modules compiled to unchecked-hash bytecode), lo (stock LibreOffice MSI of $LO_MSI_URL / $LO_MSI_SHA256), scale150 (the splash and the
# Start Center at 150 %), scan (last: the runner's Defender exclusions of C:\ and D:\ removed and real-time scanning
# on, as on a user's PC, then hst, lazy, lazy-pyc and lo again). "cold" empties the file cache (standby list) with
# RAMMap first: a start after a reboot. Evidence only; fails only when nothing could be installed.
set -Eeuo pipefail
msi="$1"; out="$2"; variants=",${3:-hst,trace,noext,lazy,lazy-trace,lazy-cache,lazy-pyc,lo,scale150,scan},"
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
ext="$install/share/extensions/hst-vietnamese-tools"
cp -r "$ext" "$work/ext-installed"
use_ext() { # use_ext installed|overlay: which HST extension the next starts load
  rm -rf "$ext"
  if [ "$1" = installed ]; then cp -r "$work/ext-installed" "$ext"; return 0; fi
  mkdir -p "$ext"
  python -I -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$HST_OVERLAY_OXT" "$(w "$ext")"
}
use_pyc() { # use_pyc on|off: unchecked-hash bytecode next to every Python module of the installation (it ships none)
  if [ "$1" = off ]; then find "$install" -name __pycache__ -type d -prune -exec rm -rf {} +; return 0; fi
  for dir in "$program" "$install/share/extensions"; do
    "$program/python.exe" -m compileall -q --invalidation-mode unchecked-hash "$(w "$dir")" >> "$out/pyc-compile.log" 2>&1 \
      || echo "compileall $dir exit $?" >> "$out/pyc-compile.log"
  done
  echo "pyc files now: $(find "$install" -name '*.pyc' | wc -l)" >> "$out/pyc-compile.log"
}

timing() { # timing <label> <soffice> <starts> [more harness options]
  local label="$1" office="$2" starts="$3"; shift 3
  python -I "$(w "$here/startup-timing.py")" --soffice "$(w "$office")" --python "$(w "$(dirname "$office")/python.exe")" \
    --intro "$(w "$(dirname "$office")/intro.png")" --profile "$(w "$work/profile-$label")" --out "$(w "$out")" \
    --label "$label" --starts "$starts" --cold-command "$cold" "$@" || echo "$label: no window seen" >> "$out/failures.txt"
  MSYS2_ARG_CONV_EXCL='*' taskkill.exe /F /IM soffice.bin /IM soffice.exe >/dev/null 2>&1 || echo "no office left running"
}
starts="${STARTS:-fresh,warm,warm,warm,cold}"  # $STARTS: another sequence, e.g. more cold starts
lazy_runs() { # lazy_runs <label prefix>: the extension of this checkout, without and with bytecode
  [ -n "${HST_OVERLAY_OXT:-}" ] || { echo "no overlay extension: lazy variants skipped" >> "$out/failures.txt"; return 0; }
  use_ext overlay
  if has lazy; then timing "${1}lazy" "$soffice" "$starts"; fi
  if has lazy-trace; then timing "${1}lazy-trace" "$soffice" fresh,warm,cold --trace; fi
  if has lazy-cache; then  # a per-user bytecode cache in the profile, as the office would keep one
    timing "${1}lazy-cache" "$soffice" "$starts" --trace --env "HST_STARTUP_PYCACHE=$(w "$work/profile-${1}lazy-cache/cache/python")"
  fi
  if has lazy-pyc; then use_pyc on; timing "${1}lazy-pyc" "$soffice" "$starts" --trace; use_pyc off; fi
  use_ext installed
}

if has hst; then timing hst "$soffice" "$starts" --shots; fi
if has trace; then timing hst-trace "$soffice" fresh,warm,cold --trace; fi
if has noext; then rm -rf "$ext"; timing hst-noext "$soffice" "$starts"; use_ext installed; fi
lazy_runs ""
if has scale150; then
  # 150 % needs a larger display than the runner's 1024x768 (which offers 100 and 125 % only); 125 % first
  python -I -c "import sys; sys.path.insert(0, sys.argv[1]); import windows_dpi; print(windows_dpi.set_scale(125))" \
    "$(w "$repo/tests/runtime/r1auto")" > "$out/scale125.txt" 2>&1 || echo "scale not set" >> "$out/scale125.txt"
  timing hst-scale125 "$soffice" fresh,warm --shots
  pwsh -NoProfile -Command 'Set-DisplayResolution -Width 1920 -Height 1080 -Force' >> "$out/scale150.txt" 2>&1 \
    || echo "display resolution unchanged" >> "$out/scale150.txt"
  python -I -c "import sys; sys.path.insert(0, sys.argv[1]); import windows_dpi; print(windows_dpi.set_scale(150))" \
    "$(w "$repo/tests/runtime/r1auto")" >> "$out/scale150.txt" 2>&1 || echo "scale not set" >> "$out/scale150.txt"
  timing hst-scale150 "$soffice" fresh,warm --shots
  python -I -c "import sys; sys.path.insert(0, sys.argv[1]); import windows_dpi; print(windows_dpi.set_scale(100))" \
    "$(w "$repo/tests/runtime/r1auto")" >> "$out/scale150.txt" 2>&1 || echo "scale not reset" >> "$out/scale150.txt"
fi
lo=""
if { has lo || has scan; } && [ -n "${LO_MSI_URL:-}" ]; then
  lo_msi="$work/LibreOffice.msi"
  if curl -fsSL --retry 3 -o "$lo_msi" "$LO_MSI_URL" || curl -fsSL --retry 3 -o "$lo_msi" "${LO_MSI_ARCHIVE_URL:-}"; then
    echo "$LO_MSI_SHA256  $lo_msi" | sha256sum -c
    msiexec_q /i "$(w "$lo_msi")" /qn /norestart /l*v "$(w "$out/lo-install.log")"
    lo="$(find '/c/Program Files/LibreOffice/program' -maxdepth 1 -iname soffice.exe | head -n 1)"
  fi
fi
if has lo && [ -n "$lo" ]; then timing lo "$lo" "$starts"; fi
if has scan; then
  # as on a user's PC: no exclusions, real-time scanning on (the runner image excludes C:\ and D:\ and turns it off)
  pwsh -NoProfile -Command 'Remove-MpPreference -ExclusionPath "C:\","D:\" -ErrorAction SilentlyContinue;
    Set-MpPreference -DisableRealtimeMonitoring $false; Start-Sleep 5;
    Get-MpComputerStatus | Select-Object AMServiceEnabled,RealTimeProtectionEnabled,OnAccessProtectionEnabled | Format-List;
    Get-MpPreference | Select-Object ExclusionPath,DisableRealtimeMonitoring | Format-List' > "$out/scan-state.txt" 2>&1 \
    || echo "scan state not fully set" >> "$out/scan-state.txt"
  timing scan-hst "$soffice" "$starts" --trace
  lazy_runs scan-
  if [ -n "$lo" ]; then timing scan-lo "$lo" "$starts"; fi
fi
python -I "$(w "$here/startup-timing-summary.py")" "$(w "$out")" > "$out/summary.md"
cat "$out/summary.md"
