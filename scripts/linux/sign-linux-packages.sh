#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Release step: GPG-sign the Linux packages with the HASON TECH Linux packaging key (docs/LINUX_PACKAGES.md):
#   - every HSTOffice_*_Linux_x86-64.rpm: rpmsign --addsign (header + payload), checked with rpmkeys --checksig;
#   - every HSTOffice_*_Linux_x86-64.AppImage: detached ASCII signature <name>.asc;
#   - HSTOffice_<release>_Linux_x86-64.SHA256SUMS (the Linux files and their signatures) + its detached .asc, which
#     the release publishes as is (the release's combined SHA256SUMS is rebuilt and cannot carry a Linux signature);
#   - RPM-GPG-KEY-hasontech (public key) beside them; SHA256SUMS (the artifact list) rewritten.
# Without a key it does nothing and exits 0 (unsigned packages; the in-app updater relies on the SHA-256 in the
# Ed25519-signed manifest either way).
#   sign-linux-packages.sh <installer-dir>
#   sign-linux-packages.sh --enabled     prints enabled=true|false (the CI gate: is the key secret set?); fails when
#                                        HST_LINUX_GPG_FINGERPRINT is set without the secret (a configured key must sign)
# Environment (GitHub environment "linux-signing", set by the owner's setup-linux-signing-key.sh; never in the repo):
#   HST_LINUX_GPG_PRIVATE_KEY   ASCII-armoured secret key (empty: skip)
#   HST_LINUX_GPG_PASSPHRASE    its passphrase
#   HST_LINUX_GPG_FINGERPRINT   expected 40-hex fingerprint; signing refuses any other key, and refuses when the
#                               public key committed at data/hst/RPM-GPG-KEY-hasontech (shipped in the .rpm for the
#                               updater) has another fingerprint
# Needs gpg, rpmsign, rpmkeys, sha256sum.
set -Eeuo pipefail
DIR="${1:?usage: $0 <installer-dir> | --enabled}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ "$DIR" = --enabled ]; then
  if [ -n "${HST_LINUX_GPG_PRIVATE_KEY:-}" ]; then echo enabled=true; exit 0; fi
  if [ -n "${HST_LINUX_GPG_FINGERPRINT:-}" ]; then # the key is configured, but its secret did not reach the job
    echo "linux signing: HST_LINUX_GPG_FINGERPRINT is set but the HST_LINUX_GPG_PRIVATE_KEY secret is empty" >&2; exit 1
  fi
  echo enabled=false
  echo "linux signing: no HST_LINUX_GPG_PRIVATE_KEY secret; the packages stay unsigned" >&2
  exit 0
fi
if [ -z "${HST_LINUX_GPG_PRIVATE_KEY:-}" ]; then
  echo "linux signing: skipped (no HST_LINUX_GPG_PRIVATE_KEY); .rpm and .AppImage stay unsigned, SHA256SUMS unchanged"
  exit 0
fi
FPR="${HST_LINUX_GPG_FINGERPRINT:?HST_LINUX_GPG_FINGERPRINT required with a signing key}"
[[ "$FPR" =~ ^[0-9A-F]{40}$ ]] || { echo "linux signing: fingerprint must be 40 upper-case hex digits" >&2; exit 2; }
for tool in gpg rpmsign rpmkeys sha256sum; do
  command -v "$tool" >/dev/null || { echo "linux signing: $tool missing (apt-get install gnupg rpm)" >&2; exit 2; }
done
GNUPGHOME="$(mktemp -d)"; export GNUPGHOME
trap 'rm -rf "$GNUPGHOME"' EXIT
chmod 700 "$GNUPGHOME"
key_fpr() { gpg --batch --with-colons --show-keys "$1" | awk -F: '$1=="fpr"{print $10; exit}'; }
PUBLISHED="$REPO/data/hst/RPM-GPG-KEY-hasontech"
if [ -f "$PUBLISHED" ] && [ "$(key_fpr "$PUBLISHED")" != "$FPR" ]; then
  echo "linux signing: $PUBLISHED is not the key $FPR (the updater imports that file)" >&2; exit 2
fi
PASS="$GNUPGHOME/passphrase"; printf '%s' "${HST_LINUX_GPG_PASSPHRASE:-}" > "$PASS"
printf '%s\n' "$HST_LINUX_GPG_PRIVATE_KEY" | gpg --batch --quiet --import
gpg --batch --with-colons --list-secret-keys | awk -F: '$1=="fpr"{print $10}' | grep -qx "$FPR" \
  || { echo "linux signing: the imported key is not $FPR" >&2; exit 2; }
gpg --batch --armor --export "$FPR" > "$DIR/RPM-GPG-KEY-hasontech"
SIGN_ARGS="--batch --pinentry-mode loopback --passphrase-file $PASS"
sign_detached() { # sign_detached <file>: <file>.asc, verified
  # shellcheck disable=SC2086  # SIGN_ARGS is a word list
  gpg $SIGN_ARGS --local-user "$FPR" --armor --detach-sign --yes -o "$1.asc" "$1"
  gpg --batch --quiet --verify "$1.asc" "$1" 2>/dev/null || { echo "linux signing: $1.asc does not verify" >&2; exit 1; }
  echo "signed $1.asc"
}
shopt -s nullglob
rpmkeys --dbpath "$GNUPGHOME/rpmdb" --initdb 2>/dev/null || :
rpmkeys --dbpath "$GNUPGHOME/rpmdb" --import "$DIR/RPM-GPG-KEY-hasontech"
release=
for rpm in "$DIR"/HSTOffice_*_Linux_x86-64.rpm; do
  rpmsign --define "__gpg $(command -v gpg)" --define "_gpg_name $FPR" --define "_gpg_sign_cmd_extra_args $SIGN_ARGS" \
    --addsign "$rpm" >/dev/null
  rpmkeys --dbpath "$GNUPGHOME/rpmdb" --checksig "$rpm" | grep -qi 'signatures ok' \
    || { echo "linux signing: $rpm does not verify" >&2; exit 1; }
  echo "signed $rpm"
  release="${rpm##*/HSTOffice_}"; release="${release%_Linux_x86-64.rpm}"
done
for app in "$DIR"/HSTOffice_*_Linux_x86-64.AppImage; do
  sign_detached "$app"
  release="${app##*/HSTOffice_}"; release="${release%_Linux_x86-64.AppImage}"
done
[ -n "$release" ] || { echo "linux signing: no .rpm or .AppImage in $DIR" >&2; exit 1; }
( cd "$DIR"
  # The .rpm bytes changed: the published Linux list, then its signature, then the artifact list of everything.
  linux="HSTOffice_${release}_Linux_x86-64.SHA256SUMS"
  for f in HSTOffice_*_Linux_x86-64.* RPM-GPG-KEY-hasontech; do
    case "$f" in "$linux"|"$linux.asc") ;; *) printf '%s\n' "$f" ;; esac
  done | xargs -r -d '\n' sha256sum -- > "$linux"
  sha256sum -c --quiet "$linux" )
sign_detached "$DIR/HSTOffice_${release}_Linux_x86-64.SHA256SUMS"
( cd "$DIR"
  names="$(awk '{print $2}' SHA256SUMS; printf '%s\n' ./*.asc ./*.SHA256SUMS RPM-GPG-KEY-hasontech | sed 's|^\./||')"
  printf '%s\n' "$names" | sort -u | xargs -r -d '\n' sha256sum -- > SHA256SUMS.new
  mv SHA256SUMS.new SHA256SUMS
  sha256sum -c --quiet SHA256SUMS )
echo "linux signing: OK ($FPR)"
