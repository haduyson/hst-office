#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Prove the macOS update-lock templates of the user guide (help/files/hst-office-*.mobileconfig) on a released dmg.
#   update-policy-probe.sh <HSTOffice_*.dmg> <out-dir>
# The app is copied out of the dmg unchanged (no re-signing: the lock must not touch the bundle) and probed with
# tests/runtime/check-update-policy.py --source managed over UNO with the bundled Python:
#   1. no lock;
#   2. every template: `profiles install` is tried and its outcome logged (since macOS 11 a configuration profile
#      needs the user's approval in System Settings or an MDM, so a CI runner cannot install one). The payload of
#      the template is then written where macOS puts an installed profile, /Library/Managed Preferences/
#      vn.hasontech.hstoffice.plist, which is the file HST Office reads; the lock is checked and the file removed;
#   3. one template as a per-user profile (/Library/Managed Preferences/<user>/...); 4. no lock again;
#   5. what the office wrote into the bundle is listed (only Python caches allowed). Writes summary.md and the probe's JSON results; exit 1 on a failure.
set -Eeuo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <dmg> <out-dir>" >&2; exit 64; }
dmg="$1"; out="$2"; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
mkdir -p "$out"; work="$(mktemp -d)"; mnt="$work/mnt"; mkdir -p "$mnt"
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
ditto "$mnt/HST Office.app" "$work/HST Office.app"; hdiutil detach "$mnt" >/dev/null
app="$work/HST Office.app"
py="$(find "$app/Contents" -path '*bin/python3*' -type f -perm -u+x ! -name '*-config' | head -1)"
pyuno="$(find "$app/Contents" -name 'pyuno*.so' -o -name 'pyuno*.dylib' | head -1)"
pyhome="$(dirname "$pyuno")"
files="$repo/extensions/hst-vietnamese-tools/help/files"
managed="/Library/Managed Preferences"; domain="vn.hasontech.hstoffice"; user="$(id -un)"
status=0; summary="$out/summary.md"
printf '# macOS update-lock templates\n\n' >"$summary"
note() { printf -- '- %s\n' "$*" | tee -a "$summary"; }

probe() {  # probe <profile> <out>
  # the probe's own Python writes no caches into the bundle; the office still may (see bundle-changes.txt)
  if PYTHONDONTWRITEBYTECODE=1 URE_BOOTSTRAP="vnd.sun.star.pathname:$app/Contents/Resources/fundamentalrc" PYTHONPATH="$app/Contents/Resources:$pyhome" \
      perl -e 'alarm 600; exec @ARGV' "$py" "$repo/tests/runtime/check-update-policy.py" --soffice "$app/Contents/MacOS/soffice" \
      --profile "$1" --source managed --out "$2" >"$2.log" 2>&1; then
    note "PASS $1 ($(basename "$2"))"
  else
    note "FAIL $1 ($(basename "$2"))"; status=1
  fi
  cat "$2.log"
}

payload() {  # payload <mobileconfig> <plist>: the managed preferences macOS writes for the template's payload
  "$py" -I -c 'import plistlib, sys
doc = plistlib.load(open(sys.argv[1], "rb"))
assert doc["PayloadType"] == "Configuration" and doc["PayloadScope"] == "System", "not a system configuration profile"
(item,) = doc["PayloadContent"]
assert item["PayloadType"] == sys.argv[3], item["PayloadType"]
plistlib.dump({k: v for k, v in item.items() if not k.startswith("Payload")}, open(sys.argv[2], "wb"))' "$1" "$2" "$domain"
}

note "macOS $(sw_vers -productVersion), app $(defaults read "$app/Contents/Info.plist" CFBundleShortVersionString)"
if codesign --verify --deep --strict "$app"; then note "signature verifies before the probe"; else note "FAIL signature before the probe"; status=1; fi
marker="$work/started"; touch "$marker"
probe none "$out/none"
sudo mkdir -p "$managed"
for name in tat-kiem-tra chi-tai-ve kenh-chinh-thuc; do
  config="$files/hst-office-$name.mobileconfig"
  plutil -lint "$config" | tee -a "$summary"
  # shellcheck disable=SC2024 # the log is the runner user's file; only profiles needs root
  if sudo profiles install -type configuration -path "$config" >"$out/profiles-install-$name.log" 2>&1; then
    note "profiles install accepted hst-office-$name.mobileconfig"
    probe "$name" "$out/installed-$name"
    # shellcheck disable=SC2024
    sudo profiles remove -identifier vn.hasontech.hstoffice.update-policy >>"$out/profiles-install-$name.log" 2>&1 || note "profiles remove failed"
  else
    note "profiles install refused hst-office-$name.mobileconfig (exit $?): $(tr '\n' ' ' <"$out/profiles-install-$name.log" | cut -c1-200)"
  fi
  payload "$config" "$work/$name.plist"
  sudo install -m 644 "$work/$name.plist" "$managed/$domain.plist"
  probe "$name" "$out/$name"
  sudo rm -f "$managed/$domain.plist"
done
sudo mkdir -p "$managed/$user"
sudo install -m 644 "$work/tat-kiem-tra.plist" "$managed/$user/$domain.plist"
probe tat-kiem-tra "$out/per-user-tat-kiem-tra"
sudo rm -f "$managed/$user/$domain.plist"
probe none "$out/none-after-removal"
# The lock lives in /Library/Managed Preferences only; the probe never writes into the bundle. The office itself
# writes Python bytecode caches into a bundle it can write to, which breaks the signature seal: that is recorded
# (bundle-changes.txt, codesign-after.txt) as information, not as a failure of the templates.
find "$app" -newer "$marker" -type f >"$out/bundle-changes.txt"
other="$(grep -v -E '[.]pyc$' "$out/bundle-changes.txt" || true)"
note "files the office wrote inside the bundle while it ran: $(wc -l <"$out/bundle-changes.txt" | tr -d ' ') (bundle-changes.txt)"
if [ -n "$other" ]; then note "FAIL bundle files other than Python caches changed: $(printf '%s' "$other" | head -5 | tr '\n' ' ')"; status=1; fi
if codesign --verify --deep --strict -vvvv "$app" >"$out/codesign-after.txt" 2>&1; then
  note "signature still verifies after the office ran"
else
  note "INFO signature seal broken after the office ran (Python caches): $(grep -m 3 -E 'modified|added|missing' "$out/codesign-after.txt" | tr '\n' ' ' | cut -c1-300)"
fi
exit "$status"
