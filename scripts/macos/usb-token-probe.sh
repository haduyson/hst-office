#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Run HST ▸ Thiết lập USB Token… natively in a released HST Office.app with a branch-built extension.
#   usb-token-probe.sh <HSTOffice_*.dmg> <hst-vietnamese-tools.oxt> <work-dir> <out-dir> <verify-python>
# Copies the app out of the dmg, re-signs it ad hoc (as the other probes do), then runs
# tests/runtime/check-usb-token-setup-macos.py with the bundled Python twice: soffice without and with
# Homebrew modutil/certutil on PATH. <verify-python> has lxml + cryptography for the independent ODT
# signature check. Evidence (results, dialog screenshots, logs, module files; no PKI material) goes to
# <out-dir>. Exit status is non-zero when any scenario fails. Optional environment: PROBE_SCENARIO
# (all|fresh|firefox|firefox-warm, default all) and PROBE_REPEAT (rounds per mode, default 1).
# macOS crash reports of soffice/HST Office written during the probe are copied to <out-dir>/crash-reports.
set -Eeuo pipefail
[ $# -eq 5 ] || { echo "usage: $0 <dmg> <oxt> <work-dir> <out-dir> <verify-python>" >&2; exit 64; }
dmg="$1"; oxt="$2"; work="$3"; out="$4"; verify_py="$5"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; tests="$(cd "$here/../../tests/runtime" && pwd)"
mkdir -p "$work" "$out"; work="$(cd "$work" && pwd -P)"; out="$(cd "$out" && pwd -P)"
mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
bash "$here/adhoc-sign.sh" "$app" >"$out/adhoc-sign.log" 2>&1 || echo "adhoc-sign exit $?" >>"$out/adhoc-sign.log"
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
{
  echo "app: $app"; echo "python: $py"; "$py" -c 'import sys, platform; print(sys.version, platform.machine())'
  echo "pyuno: $pyuno"; ls -l "$app/Contents/MacOS/unopkg" "$app/Contents/Frameworks/libnss3.dylib" || true
  find "$app/Contents" -name 'libnssckbi*' -o -name 'libsoftokn3*' | sed "s|$app/||"
  echo "softhsm: $(find "$(brew --prefix softhsm)/lib" -name 'libsofthsm2*')"
  file "$(find "$(brew --prefix softhsm)/lib" -name 'libsofthsm2*' | head -1)"
  echo "modutil: $(command -v modutil)  certutil: $(command -v certutil)  pkcs11-tool: $(command -v pkcs11-tool)"
} >"$out/environment.txt" 2>&1
cat "$out/environment.txt"
# Test tooling for the driver only (token, certificates, independent listings): Homebrew OpenSSL 3 first.
openssl_bin="$(brew --prefix openssl@3)/bin"
export PATH="$openssl_bin:$PATH"
status=0
port=2093
scenario="${PROBE_SCENARIO:-all}"; repeat="${PROBE_REPEAT:-1}"
[[ "$repeat" =~ ^[1-9][0-9]?$ ]] || { echo "bad PROBE_REPEAT" >&2; exit 64; }
reports=(/Users/"$(id -un)"/Library/Logs/DiagnosticReports /Library/Logs/DiagnosticReports)
stamp="$work/.probe-start"; touch "$stamp"
for mode in no-tools tools; do
  dir="$work/$mode"
  rm -rf "$dir"
  URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" \
    PYTHONPATH="$app/Contents/Resources:$(dirname "$pyuno"):$tests" \
    perl -e 'alarm 3600; exec @ARGV' "$py" "$tests/check-usb-token-setup-macos.py" --app "$app" --oxt "$oxt" \
      --workdir "$dir" --port "$port" "--$mode" --scenario "$scenario" --repeat "$repeat" 2>&1 | tee "$out/driver-$mode.log" || status=1
  port=$((port + 1))
  if [ -f "$dir/results.json" ]; then
    "$verify_py" -I "$tests/check-usb-token-setup-macos.py" --verify "$dir/results.json" 2>&1 \
      | tee "$out/verify-$mode.log" || status=1
  else
    status=1
  fi
  # Collect evidence only: never the PKI directory (test keys/token) or the office profiles.
  for case in "$dir"/*/; do
    [ -d "$case" ] || continue
    name="$(basename "$case")"; dest="$out/$mode/$name"; mkdir -p "$dest"
    cp -R "$case/office/logs" "$dest/office-logs" 2>/dev/null || true
    cp -R "$case/office/setup-shots" "$dest/setup-dialog-shots" 2>/dev/null || true
    cp -R "$case/shots" "$dest/signing-shots" 2>/dev/null || true
    cp -R "$case/office/timeouts" "$dest/timeouts" 2>/dev/null || true
    cp "$case/signed.odt" "$dest/" 2>/dev/null || true
    cp "$case/office/home/Library/Application Support/HST Office/nssdb/pkcs11.txt" "$dest/hst-store-pkcs11.txt" 2>/dev/null || true
    find "$case/office/home/Library/Application Support/Firefox" -name pkcs11.txt -exec cp {} "$dest/firefox-pkcs11.txt" \; 2>/dev/null || true
    ls -laR "$case/office/home/Library/Application Support" >"$dest/home-listing.txt" 2>&1 || true
  done
  cp "$dir/results.json" "$out/results-$mode.json" 2>/dev/null || true
done
mkdir -p "$out/crash-reports"
for dir in "${reports[@]}"; do
  [ -d "$dir" ] || continue
  find "$dir" -newer "$stamp" \( -iname '*soffice*' -o -iname '*HST*' -o -iname '*python*' \) -exec cp {} "$out/crash-reports/" \; 2>/dev/null || true
done
ls -l "$out/crash-reports"
# Nothing started here may outlive the probe: stop any soffice still using a profile under <work-dir>.
pkill -f "UserInstallation=file://$work/" 2>/dev/null || true
exit "$status"
