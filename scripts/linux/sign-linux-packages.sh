#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# OPTIONAL release step: GPG-sign the .rpm (rpmsign, header + payload) and write a detached ASCII signature
# <name>.AppImage.asc, then refresh SHA256SUMS. Without a key it does nothing and exits 0: the packages ship unsigned,
# and the in-app updater trusts them through the SHA-256 in the Ed25519-signed manifest (docs/LINUX_PACKAGES.md).
#   sign-linux-packages.sh <installer-dir>
#   sign-linux-packages.sh --enabled     prints enabled=true|false (the CI gate: is the key secret set?)
# Environment (GitHub secrets of the release owner; never stored in the repository):
#   HST_LINUX_GPG_PRIVATE_KEY   ASCII-armoured secret key (empty: skip)
#   HST_LINUX_GPG_PASSPHRASE    its passphrase (may be empty for a key without one)
#   HST_LINUX_GPG_FINGERPRINT   expected 40-hex fingerprint; signing refuses any other key
# Writes RPM-GPG-KEY-hasontech (public key) beside the packages for the website. Needs gpg, rpmsign, rpmkeys.
set -Eeuo pipefail
DIR="${1:?usage: $0 <installer-dir> | --enabled}"
if [ "$DIR" = --enabled ]; then
  if [ -n "${HST_LINUX_GPG_PRIVATE_KEY:-}" ]; then echo enabled=true; else echo enabled=false
    echo "linux signing: no HST_LINUX_GPG_PRIVATE_KEY secret; the packages stay unsigned" >&2; fi
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
PASS="$GNUPGHOME/passphrase"; printf '%s' "${HST_LINUX_GPG_PASSPHRASE:-}" > "$PASS"
printf '%s\n' "$HST_LINUX_GPG_PRIVATE_KEY" | gpg --batch --quiet --import
gpg --batch --with-colons --list-secret-keys | awk -F: '$1=="fpr"{print $10}' | grep -qx "$FPR" \
  || { echo "linux signing: the imported key is not $FPR" >&2; exit 2; }
gpg --batch --armor --export "$FPR" > "$DIR/RPM-GPG-KEY-hasontech"
SIGN_ARGS="--batch --pinentry-mode loopback --passphrase-file $PASS"
shopt -s nullglob
for rpm in "$DIR"/HSTOffice_*_Linux_x86-64.rpm; do
  rpmsign --define "__gpg $(command -v gpg)" --define "_gpg_name $FPR" --define "_gpg_sign_cmd_extra_args $SIGN_ARGS" \
    --addsign "$rpm"
  rpmkeys --dbpath "$GNUPGHOME/rpmdb" --initdb 2>/dev/null || :
  rpmkeys --dbpath "$GNUPGHOME/rpmdb" --import "$DIR/RPM-GPG-KEY-hasontech"
  rpmkeys --dbpath "$GNUPGHOME/rpmdb" --checksig "$rpm" | grep -qiE 'signatures ok|digests signatures ok' \
    || { echo "linux signing: $rpm does not verify" >&2; exit 1; }
  echo "signed $rpm"
done
for app in "$DIR"/HSTOffice_*_Linux_x86-64.AppImage; do
  # shellcheck disable=SC2086  # SIGN_ARGS is a word list
  gpg $SIGN_ARGS --local-user "$FPR" --armor --detach-sign --yes -o "$app.asc" "$app"
  gpg --batch --verify "$app.asc" "$app"
  echo "signed $app.asc"
done
# The .rpm bytes changed: rewrite SHA256SUMS for every file it lists, plus the new signatures and key.
( cd "$DIR"
  names="$(awk '{print $2}' SHA256SUMS; ls -1 ./*.asc RPM-GPG-KEY-hasontech 2>/dev/null | sed 's|^\./||')"
  printf '%s\n' "$names" | sort -u | xargs -r -d '\n' sha256sum -- > SHA256SUMS.new
  mv SHA256SUMS.new SHA256SUMS
  sha256sum -c SHA256SUMS )
