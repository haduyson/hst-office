#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Optional Developer ID signing + notarization of an unsigned HST Office dmg (gated job in
# .github/workflows/desktop-macos.yml, GitHub environment "macos-signing").
#   sign-notarize.sh --enabled              print enabled=true|false (all secrets non-empty?)
#   sign-notarize.sh --import               temporary keychain with the Developer ID identity
#   sign-notarize.sh --sign <dmg> <kit> <out-dir>
#                                           sign the app with upstream's macosx-codesign-app-bundle
#                                           (hardened runtime + LibreOffice entitlements), rebuild
#                                           and sign the dmg, notarize (--wait), staple, verify
#   sign-notarize.sh --cleanup              delete the keychain and key files (safe to repeat)
# Secrets arrive only as environment variables and are never printed (no `set -x` here).
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO" >&2' ERR
TMP="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/hst-signing"
KEYCHAIN="$TMP/hst-signing.keychain-db"
SECRETS=(MACOS_DEVELOPER_ID_P12_BASE64 MACOS_DEVELOPER_ID_P12_PASSWORD MACOS_SIGNING_IDENTITY APPLE_TEAM_ID
         APPLE_API_KEY_P8_BASE64 APPLE_API_KEY_ID APPLE_API_ISSUER_ID)
BUNDLE_ID=vn.hasontech.hstoffice

enabled() {
  local name missing=()
  for name in "${SECRETS[@]}"; do [ -n "${!name:-}" ] || missing+=("$name"); done
  if [ "${#missing[@]}" -eq 0 ]; then echo "enabled=true"; else
    echo "signing disabled: missing secrets ${missing[*]}" >&2; echo "enabled=false"; fi
}

do_import() {
  local password
  mkdir -p "$TMP"; chmod 700 "$TMP"
  password="$(openssl rand -hex 24)"
  printf '%s' "$MACOS_DEVELOPER_ID_P12_BASE64" | base64 --decode > "$TMP/cert.p12"
  # The key may be stored base64-encoded (documented) or as the PEM text itself.
  case "$APPLE_API_KEY_P8_BASE64" in
    -----BEGIN*) printf '%s\n' "$APPLE_API_KEY_P8_BASE64" > "$TMP/api-key.p8" ;;
    *) printf '%s' "$APPLE_API_KEY_P8_BASE64" | tr -d ' \r\n' | base64 --decode > "$TMP/api-key.p8" ;;
  esac
  chmod 600 "$TMP/cert.p12" "$TMP/api-key.p8"
  security create-keychain -p "$password" "$KEYCHAIN"
  security set-keychain-settings -lut 21600 "$KEYCHAIN"
  security unlock-keychain -p "$password" "$KEYCHAIN"
  security import "$TMP/cert.p12" -k "$KEYCHAIN" -P "$MACOS_DEVELOPER_ID_P12_PASSWORD" -f pkcs12 \
    -T /usr/bin/codesign -T /usr/bin/security >/dev/null
  security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$password" "$KEYCHAIN" >/dev/null
  rm -f "$TMP/cert.p12"
  # Search list: the temporary keychain first, existing user keychains after it.
  local existing=()
  while IFS= read -r kc; do kc="${kc//\"/}"; kc="${kc#"${kc%%[![:space:]]*}"}"; [ -n "$kc" ] && existing+=("$kc"); done \
    < <(security list-keychains -d user)
  security list-keychains -d user -s "$KEYCHAIN" "${existing[@]}"
  security find-identity -v -p codesigning "$KEYCHAIN" | grep -qF "$MACOS_SIGNING_IDENTITY" \
    || { echo "signing identity named in MACOS_SIGNING_IDENTITY is not in the imported certificate" >&2; return 1; }
  echo "imported Developer ID identity into a temporary keychain"
  check_notary_auth
}

notary() { # notary <subcommand> <args...>: notarytool with the App Store Connect API key
  local sub="$1"; shift
  xcrun notarytool "$sub" "$@" --key "$TMP/api-key.p8" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID"
}

check_notary_auth() { # fail before signing when Apple rejects the API key; report formats only, never values
  local fmt=ok
  grep -q -- '-----BEGIN PRIVATE KEY-----' "$TMP/api-key.p8" || { echo "APPLE_API_KEY_P8_BASE64: not a .p8 private key after decoding" >&2; fmt=bad; }
  [[ "$APPLE_API_KEY_ID" =~ ^[A-Z0-9]{10}$ ]] || { echo "APPLE_API_KEY_ID: expected 10 upper-case letters/digits" >&2; fmt=bad; }
  [[ "$APPLE_API_ISSUER_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] \
    || { echo "APPLE_API_ISSUER_ID: expected a lower-case UUID (App Store Connect > Users and Access > Integrations)" >&2; fmt=bad; }
  [[ "$APPLE_TEAM_ID" =~ ^[A-Z0-9]{10}$ ]] || { echo "APPLE_TEAM_ID: expected 10 upper-case letters/digits" >&2; fmt=bad; }
  echo "notary credential formats: $fmt"
  if notary history --output-format json > "$TMP/history.json" 2> "$TMP/history.err"; then
    echo "notarytool authentication: ok"
  else
    echo "notarytool authentication failed: $(head -3 "$TMP/history.err")" >&2
    echo "check that APPLE_API_KEY_ID and APPLE_API_ISSUER_ID belong to the .p8 key (Team key, role Developer or higher)" >&2
    return 1
  fi
}

# shellcheck source=scripts/macos/macho-lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/macho-lib.sh"

prepare_kit() { # prepare_kit <kit> <dir>: fill the upstream templates for this identity (BUILDDIR/SRCDIR layout)
  local kit="$1" dir="$2"
  mkdir -p "$dir/build/sysui/desktop/macosx" "$dir/src/sysui/desktop/macosx"
  # Release build: no get-task-allow (notarization rejects it).
  sed -e 's/@GET_TASK_ALLOW_ENTITLEMENT@//' "$kit/templates/hardened_runtime.xcent.in" > "$dir/build/hardened_runtime.xcent"
  # The parent-process constraint names our bundle id and team (empty in an unsigned configure).
  sed -e "s/@MACOSX_BUNDLE_IDENTIFIER@/$BUNDLE_ID/" -e "s/@MACOSX_CODESIGNING_TEAM_IDENTIFIER@/$APPLE_TEAM_ID/" \
    "$kit/templates/LaunchConstraint.plist.in" > "$dir/build/sysui/desktop/macosx/LaunchConstraint.plist"
  cp "$kit/templates/quicklookappex.entitlements" "$dir/src/sysui/desktop/macosx/"
  ! grep -q '@[A-Z_]*@' "$dir/build/hardened_runtime.xcent" "$dir/build/sysui/desktop/macosx/LaunchConstraint.plist" \
    || { echo "unfilled placeholders in the signing kit" >&2; return 1; }
  plutil -lint "$dir/build/hardened_runtime.xcent" "$dir/build/sysui/desktop/macosx/LaunchConstraint.plist"
  if grep -q 'get-task-allow' "$dir/build/hardened_runtime.xcent"; then echo "get-task-allow in entitlements" >&2; return 1; fi
}

check_signatures() { # check_signatures <app>: every Mach-O has a timestamped Developer ID signature
  local f info bad=0 total=0
  while IFS= read -r f; do
    total=$((total + 1))
    info="$(codesign -dvv "$f" 2>&1)" || { echo "unsigned: ${f#"$1"/}"; bad=$((bad + 1)); continue; }
    grep -q '^Authority=Developer ID Application' <<<"$info" || { echo "not Developer ID: ${f#"$1"/}"; bad=$((bad + 1)); continue; }
    grep -q '^Timestamp=' <<<"$info" || { echo "no secure timestamp: ${f#"$1"/}"; bad=$((bad + 1)); }
  done < <(macho_files "$1" all)
  echo "Developer ID check: $total Mach-O files, $bad problems"
  [ "$bad" -eq 0 ]
}

json_field() { # json_field <file> <key>: top-level string value, empty when the file is empty or not JSON
  python3 -c 'import json, sys
try:
    print(json.load(open(sys.argv[1])).get(sys.argv[2]) or "")
except (OSError, ValueError, AttributeError):
    print("")' "$1" "$2"
}

notary_summary() { # notary_summary <log.json>: the issues Apple reported, one line each
  python3 - "$1" <<'PY'
import json, sys
log = json.load(open(sys.argv[1]))
print(f"status: {log.get('status')} - {log.get('statusSummary')}")
for issue in log.get("issues") or []:
    print(f"{issue.get('severity')}: {issue.get('path')} [{issue.get('architecture')}] {issue.get('message')}")
PY
}

do_sign() {
  local dmg="$1" kit="$2" out="$3" mnt="$TMP/mnt" stage="$TMP/stage" name app signed
  name="$(basename "$dmg")"; signed="$out/$name"
  rm -rf "$mnt" "$stage" "$TMP/kit"; mkdir -p "$mnt" "$stage" "$out"
  prepare_kit "$kit" "$TMP/kit"
  hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
  # Upstream's script does not quote every path: sign under the space-free bundle name, rename after
  # (the bundle directory name is not part of the signature).
  ditto "$mnt/HST Office.app" "$stage/HSTOffice.app"
  hdiutil detach "$mnt" >/dev/null
  app="$stage/HSTOffice.app"
  [ -d "$app/Contents/MacOS" ] || { echo "HST Office.app not in $name" >&2; return 1; }
  # 1. Every Mach-O except bundle main executables, deepest first: Developer ID, hardened runtime,
  #    secure timestamp. Covers files outside the patterns of upstream's script, which then re-signs
  #    the ones it knows and signs the bundles (and with them their main executables).
  local f n=0
  while IFS= read -r f; do
    codesign --force --timestamp --options=runtime --sign "$MACOS_SIGNING_IDENTITY" "$f" 2>&1 | { grep -v 'replacing existing signature' || :; }
    n=$((n + 1))
  done < <(macho_files "$app")
  echo "pre-signed $n Mach-O files"
  # 2. Upstream's own pass (what --enable-macosx-code-signing runs at packaging time): identifiers,
  #    entitlements and launch constraints for executables, nested bundles, then the app.
  env BUILDDIR="$TMP/kit/build" SRCDIR="$TMP/kit/src" MACOSX_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
    MACOSX_CODESIGNING_IDENTITY="$MACOS_SIGNING_IDENTITY" ENABLE_MACOSX_SANDBOX= ENABLE_RELEASE_BUILD=TRUE \
    bash "$kit/macosx-codesign-app-bundle" "$app" 2>&1 | { grep -v 'replacing existing signature' || :; }
  # 3. Gates before spending a notarization round trip.
  check_signatures "$app"
  codesign --verify --deep --strict "$app"
  codesign -dvv --entitlements - "$app" 2>&1 | grep -E '^(Identifier|Authority|TeamIdentifier|Timestamp|flags)|CodeDirectory|security\.' || :
  mv "$app" "$stage/HST Office.app"; app="$stage/HST Office.app"
  rm -f "$signed"
  # Same HST layout (background, volume icon, icon positions) as the unsigned image.
  bash "$(dirname "${BASH_SOURCE[0]}")/build-dmg.sh" "$app" "$signed"
  codesign --force --timestamp --sign "$MACOS_SIGNING_IDENTITY" "$signed"
  echo "notarizing $name (waits for Apple)"
  local rc=0 id status
  notary submit "$signed" --wait --timeout 2h --output-format json > "$out/notarytool-submit.json" || rc=$?
  cat "$out/notarytool-submit.json"
  id="$(json_field "$out/notarytool-submit.json" id)"
  status="$(json_field "$out/notarytool-submit.json" status)"
  if [ -n "$id" ]; then
    notary log "$id" "$out/notarytool-log.json" >/dev/null && notary_summary "$out/notarytool-log.json"
  fi
  if [ "$rc" -ne 0 ] || [ "$status" != Accepted ]; then
    echo "notarization failed: status '${status:-none}', exit $rc" >&2; return 1
  fi
  xcrun stapler staple "$signed"
  xcrun stapler validate "$signed"
  spctl -a -t open --context context:primary-signature -v "$signed"
  # The app inside the stapled dmg: strict deep signature check and Gatekeeper assessment.
  hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$signed" >/dev/null
  codesign --verify --deep --strict --verbose=2 "$mnt/HST Office.app"
  spctl -a -t exec -vv "$mnt/HST Office.app"
  hdiutil detach "$mnt" >/dev/null
  (cd "$out" && shasum -a 256 "$name" > SHA256SUMS && cat SHA256SUMS)
}

do_cleanup() {
  if [ -f "$KEYCHAIN" ]; then
    security delete-keychain "$KEYCHAIN"
    echo "deleted temporary keychain"
  fi
  rm -rf "$TMP"
}

case "${1:-}" in
  --enabled) enabled ;;
  --import) do_import ;;
  --sign) [ $# -eq 4 ] || { echo "usage: $0 --sign <dmg> <kit> <out-dir>" >&2; exit 64; }; do_sign "$2" "$3" "$4" ;;
  --cleanup) do_cleanup ;;
  *) echo "usage: $0 --enabled|--import|--sign <dmg> <kit> <out-dir>|--cleanup" >&2; exit 64 ;;
esac
