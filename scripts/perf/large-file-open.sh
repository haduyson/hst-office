#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Open time of large synthetic documents, HST Office next to stock LibreOffice of the same engine, on a GitHub runner.
#   large-file-open.sh <windows|linux> <out-dir> <variants> [only-files]
# variants (comma list): hst, lo (stock), hst-noext (HST extension moved out), hst-toolbar (standard toolbars instead
# of the tabbed bar), lo-tabbed (stock with the tabbed bar), hst-nothreads / lo-nothreads (threaded formula calculation
# off), hst-norowheight / lo-norowheight (optimal row heights not recalculated on load), hst-save / lo-save (open, then store again with the file's own filter: the cost of a save or an autorecovery
# copy). HST is the installer of Desktop build run $HST_WIN_RUN / $HST_LINUX_RUN (1.0.1: the released build); stock is $LO_MSI_URL / $LO_DEB_URL. Evidence only.
set -Eeuo pipefail
os="$1"; out="$2"; variants=",$3,"; only="${4:-}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$out"; work="$RUNNER_TEMP/lfo-work"; mkdir -p "$work"
has() { [[ "$variants" == *",$1"* ]]; }
w() { if [ "$os" = windows ]; then cygpath -w "$1"; else echo "$1"; fi; }
py=python; [ "$os" = linux ] && py=python3

$py -m pip install -q pillow python-docx python-pptx psutil
$py -I "$(w "$here/large_file_fixtures.py")" "$(w "$work/fx")" | tee "$out/fixtures.txt"
# the .xls variant: 60 000 formula rows (the format's row limit is 65 536), converted by stock LibreOffice below
$py -I "$(w "$here/large_file_fixtures.py")" "$(w "$work/fx60k")" --rows 60000 --only calc-formulas.xlsx >> "$out/fixtures.txt"

if [ "$os" = windows ]; then
  pwsh -NoProfile -Command 'Get-CimInstance Win32_Processor | Select-Object Name,NumberOfLogicalProcessors | Format-List;
    Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory | Format-List' > "$out/runner.txt" 2>&1 || true
  msiexec_q() { MSYS2_ARG_CONV_EXCL='*' msiexec.exe "$@"; }
  RUN_ID="$HST_WIN_RUN" bash "$here/../windows/download-smoke-msi.sh" "$work/msi" HST_MSI
  msiexec_q /i "$(grep '^HST_MSI=' "$GITHUB_ENV" | tail -n 1 | cut -d= -f2-)" /qn /norestart /l*v "$(w "$out/hst-install.log")"
  hst="$(find '/c/Program Files' -maxdepth 4 -ipath '*HST*' -iname soffice.exe | head -n 1)"
  hst_py="$(dirname "$hst")/python.exe"
  curl -fsSL --retry 3 --connect-timeout 30 --max-time 900 -o "$work/lo.msi" "$LO_MSI_URL"
  sha256sum "$work/lo.msi" > "$out/lo-msi.sha256"
  msiexec_q /i "$(w "$work/lo.msi")" /qn /norestart /l*v "$(w "$out/lo-install.log")"
  lo="$(find '/c/Program Files/LibreOffice/program' -maxdepth 1 -iname soffice.exe | head -n 1)"
  lo_py="$(dirname "$lo")/python.exe"
else
  { nproc; grep -m1 'model name' /proc/cpuinfo; free -m; } > "$out/runner.txt" 2>&1 || true
  gh run download "$HST_LINUX_RUN" --repo "$GITHUB_REPOSITORY" --name "hst-office-linux-deb-$HST_LINUX_RUN" --dir "$work/deb"
  sudo apt-get update -q > "$out/hst-install.log" 2>&1 || true
  sudo apt-get install -y -q "$work"/deb/*.deb >> "$out/hst-install.log" 2>&1
  hst="$(find /opt -maxdepth 3 -path '*hst-office*/program/soffice' | head -n 1)"
  hst_py="$(dirname "$hst")/python"
  curl -fsSL --retry 3 --connect-timeout 30 --max-time 900 -o "$work/lo.tar.gz" "$LO_DEB_URL"
  sha256sum "$work/lo.tar.gz" > "$out/lo-deb.sha256"
  mkdir -p "$work/lo-debs" "$work/lo-root"
  tar -xzf "$work/lo.tar.gz" -C "$work/lo-debs"
  for deb in "$work"/lo-debs/*/DEBS/*.deb; do dpkg -x "$deb" "$work/lo-root"; done
  lo="$(find "$work/lo-root/opt" -maxdepth 3 -path '*/program/soffice' | head -n 1)"
  lo_py="$(dirname "$lo")/python"
  [ -x "$lo_py" ] || lo_py=python3  # the stock .deb uses the system Python with python3-uno
  [ -x "$hst_py" ] || hst_py=python3
  sudo apt-get install -y -q python3-uno >> "$out/hst-install.log" 2>&1 || true
  Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp > "$work/xvfb.log" 2>&1 &
  trap 'kill $! 2>/dev/null || true' EXIT
  export DISPLAY=:99
  sleep 2
fi
echo "HST: $hst ($hst_py)  stock: $lo ($lo_py)" | tee "$out/offices.txt"

# .xls made by stock LibreOffice from the 60 000-row workbook
conv_url="file://$work/conv-profile"; [ "$os" = windows ] && conv_url="file:///$(cygpath -m "$work/conv-profile")"
"$lo" --headless --norestore "-env:UserInstallation=$conv_url" \
  --convert-to 'xls:MS Excel 97' --outdir "$(w "$work/fx")" "$(w "$work/fx60k/calc-formulas.xlsx")" \
  > "$out/xls-convert.log" 2>&1 || echo "xls conversion failed" >> "$out/failures.txt"
[ -f "$work/fx/calc-formulas.xls" ] && mv "$work/fx/calc-formulas.xls" "$work/fx/calc-formulas-60k.xls"
ls -l "$work/fx" | tee -a "$out/fixtures.txt"

run() { # run <label> <soffice> <python> [harness options]
  local label="$1" office="$2" opy="$3"; shift 3
  $py -I "$(w "$here/large-file-open.py")" --soffice "$(w "$office")" --python "$(w "$opy")" --files "$(w "$work/fx")" \
    --out "$(w "$out")" --label "$label" --profile "$(w "$work/profile-$label")" ${only:+--only "$only"} "$@" \
    || echo "$label: harness exit $?" >> "$out/failures.txt"
  if [ "$os" = windows ]; then MSYS2_ARG_CONV_EXCL='*' taskkill.exe /F /IM soffice.bin /IM soffice.exe >/dev/null 2>&1 || true
  else pkill -x soffice.bin || true; fi
}
ext="$(dirname "$(dirname "$hst")")/share/extensions/hst-vietnamese-tools"
for v in ${variants//,/ }; do
  case "$v" in
    hst) run hst "$hst" "$hst_py" ;;
    lo) run lo "$lo" "$lo_py" ;;
    hst-toolbar) run hst-toolbar "$hst" "$hst_py" --seed toolbar ;;
    lo-tabbed) run lo-tabbed "$lo" "$lo_py" --seed tabbed ;;
    hst-nothreads) run hst-nothreads "$hst" "$hst_py" --seed nothreads ;;
    lo-nothreads) run lo-nothreads "$lo" "$lo_py" --seed nothreads ;;
    hst-norowheight) run hst-norowheight "$hst" "$hst_py" --seed norowheight ;;
    lo-norowheight) run lo-norowheight "$lo" "$lo_py" --seed norowheight ;;
    hst-save) run hst-save "$hst" "$hst_py" --save ;;
    lo-save) run lo-save "$lo" "$lo_py" --save ;;
    hst-noext)
      sudo_=""; [ "$os" = linux ] && sudo_=sudo
      $sudo_ mv "$ext" "$work/ext-moved"
      run hst-noext "$hst" "$hst_py"
      $sudo_ mv "$work/ext-moved" "$ext" ;;
    *) echo "unknown variant $v" >> "$out/failures.txt" ;;
  esac
done
$py -I "$(w "$here/large-file-open-summary.py")" "$(w "$out")" > "$out/summary.md"
cat "$out/summary.md"
