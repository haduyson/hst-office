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
  printf '%s' "$APPLE_API_KEY_P8_BASE64" | base64 --decode > "$TMP/api-key.p8"
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
}

do_sign() {
  local dmg="$1" kit="$2" out="$3" mnt="$TMP/mnt" stage="$TMP/stage" name app signed
  name="$(basename "$dmg")"; signed="$out/$name"
  rm -rf "$mnt" "$stage"; mkdir -p "$mnt" "$stage" "$out"
  hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$mnt" "$dmg" >/dev/null
  ditto "$mnt/HST Office.app" "$stage/HST Office.app"
  hdiutil detach "$mnt" >/dev/null
  app="$stage/HST Office.app"
  [ -d "$app" ] || { echo "HST Office.app not in $name" >&2; return 1; }
  # Upstream's own signing pass (what --enable-macosx-code-signing runs at packaging time):
  # dylibs, nested apps, frameworks, executables, then the bundle, hardened runtime + entitlements.
  env BUILDDIR="$kit/build" SRCDIR="$kit/src" MACOSX_BUNDLE_IDENTIFIER="$BUNDLE_ID" \
    MACOSX_CODESIGNING_IDENTITY="$MACOS_SIGNING_IDENTITY" ENABLE_MACOSX_SANDBOX= ENABLE_RELEASE_BUILD=TRUE \
    bash "$kit/macosx-codesign-app-bundle" "$app"
  codesign --verify --deep --strict --verbose=2 "$app"
  rm -f "$signed"
  # Same HST layout (background, volume icon, icon positions) as the unsigned image.
  bash "$(dirname "${BASH_SOURCE[0]}")/build-dmg.sh" "$app" "$signed"
  codesign --force --timestamp --sign "$MACOS_SIGNING_IDENTITY" "$signed"
  echo "notarizing $name (waits for Apple)"
  xcrun notarytool submit "$signed" --key "$TMP/api-key.p8" --key-id "$APPLE_API_KEY_ID" \
    --issuer "$APPLE_API_ISSUER_ID" --team-id "$APPLE_TEAM_ID" --wait --timeout 2h --output-format json \
    > "$out/notarytool-submit.json"
  local id status
  id="$(plutil -extract id raw "$out/notarytool-submit.json")"
  status="$(plutil -extract status raw "$out/notarytool-submit.json")"
  xcrun notarytool log "$id" --key "$TMP/api-key.p8" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID" \
    --team-id "$APPLE_TEAM_ID" "$out/notarytool-log.json" >/dev/null
  [ "$status" = Accepted ] || { echo "notarization status: $status (see notarytool-log.json)" >&2; return 1; }
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
