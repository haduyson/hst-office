#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# The Linux signing step (scripts/linux/sign-linux-packages.sh) against a THROWAWAY key generated inside an
# auto-removed Ubuntu 22.04 container (the CI image), so the pipeline is proven before the owner creates the real key.
#   tests/runtime/check-linux-signing.sh <installer-dir> <out-dir>
# Copies the .rpm, .AppImage and their SHA256SUMS lines from <installer-dir> to <out-dir> (copies: rpmsign rewrites
# the .rpm), then checks: no key -> skipped; wrong fingerprint -> refused; signing -> rpmkeys --checksig OK, the
# AppImage .asc and the Linux SHA256SUMS.asc verify with ONLY the exported public key, sha256sum -c OK.
# <out-dir> keeps the signed packages and the throwaway RPM-GPG-KEY-hasontech, for
#   RPM_KEY=<out-dir>/RPM-GPG-KEY-hasontech tests/runtime/check-rpm-install.sh <out-dir>/HSTOffice_*.rpm
# The throwaway secret key never leaves the container.
set -euo pipefail
IN="$(realpath "${1:?usage: $0 <installer-dir> <out-dir>}")"; OUT="$(realpath -m "${2:?out-dir}")"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${IMAGE:-ubuntu:22.04@sha256:076e7bf82319619f28dd0aa9c02ab34b055ad37100395b4f49a2ffba04fb5e11}"
mkdir -p "$OUT"
for f in "$IN"/HSTOffice_*_Linux_x86-64.rpm "$IN"/HSTOffice_*_Linux_x86-64.AppImage; do cp -p "$f" "$OUT/"; done
grep -E '\.(rpm|AppImage)$' "$IN/SHA256SUMS" > "$OUT/SHA256SUMS"
NAME="hst-signing-qa-$$"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || :' EXIT
docker run --rm --name "$NAME" -v "$REPO:/repo:ro" -v "$OUT:/out" "$IMAGE" bash -c '
set -u
pass() { echo "PASS $*"; }; fail() { echo "FAIL $*"; }
apt-get update -qq >/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends rpm gnupg >/dev/null 2>&1
S=/repo/scripts/linux/sign-linux-packages.sh
before=$(sha256sum /out/*.rpm)
bash $S /out | grep -q skipped && [ "$(sha256sum /out/*.rpm)" = "$before" ] && pass "no key: skipped, nothing changed" || fail "no-key run"
[ "$(HST_LINUX_GPG_PRIVATE_KEY=x bash $S --enabled 2>/dev/null)" = enabled=true ] && [ "$(bash $S --enabled 2>/dev/null)" = enabled=false ] \
  && pass "CI gate" || fail "CI gate"
export GNUPGHOME=/tmp/throwaway; mkdir -m 700 $GNUPGHOME; printf "%s" throwaway-pass > /tmp/pw
gpg --batch --quiet --pinentry-mode loopback --passphrase-file /tmp/pw --quick-gen-key "Throwaway HST test <test@invalid>" rsa4096 sign 1d 2>/dev/null
FPR=$(gpg --with-colons --list-secret-keys | awk -F: "\$1==\"fpr\"{print \$10; exit}")
KEY=$(gpg --batch --pinentry-mode loopback --passphrase-file /tmp/pw --armor --export-secret-keys "$FPR")
unset GNUPGHOME
HST_LINUX_GPG_PRIVATE_KEY="$KEY" HST_LINUX_GPG_PASSPHRASE=throwaway-pass HST_LINUX_GPG_FINGERPRINT=0000000000000000000000000000000000000000 \
  bash $S /out >/dev/null 2>&1 && fail "wrong fingerprint accepted" || pass "wrong fingerprint refused"
HST_LINUX_GPG_PRIVATE_KEY="$KEY" HST_LINUX_GPG_PASSPHRASE=throwaway-pass HST_LINUX_GPG_FINGERPRINT="$FPR" bash $S /out | tail -1 | grep -q "OK ($FPR)" \
  && pass "signed with throwaway key $FPR" || fail "signing"
cd /out
export GNUPGHOME=/tmp/verify; mkdir -m 700 $GNUPGHOME; gpg --batch --quiet --import RPM-GPG-KEY-hasontech 2>/dev/null
rpmkeys --dbpath /tmp/rpmdb --initdb 2>/dev/null; rpmkeys --dbpath /tmp/rpmdb --import RPM-GPG-KEY-hasontech
for r in *.rpm; do rpmkeys --dbpath /tmp/rpmdb --checksig "$r" | grep -qi "signatures ok" && pass "rpm signature: $r" || fail "rpm signature $r"; done
for a in *.AppImage; do gpg --batch --verify "$a.asc" "$a" 2>/dev/null && pass "AppImage .asc verifies (public key only)" || fail "AppImage .asc"; done
L=$(ls *_Linux_x86-64.SHA256SUMS)
gpg --batch --verify "$L.asc" "$L" 2>/dev/null && sha256sum -c --quiet "$L" && pass "$L.asc verifies and its hashes match" || fail "$L"
sha256sum -c --quiet SHA256SUMS && pass "artifact SHA256SUMS" || fail "artifact SHA256SUMS"
echo 1 >> "$L"; gpg --batch --verify "$L.asc" "$L" 2>/dev/null && fail "tampered list verifies" || pass "tampered list rejected"
sed -i "\$d" "$L"
' 2>&1 | tee "$OUT/signing.log"
! grep -q '^FAIL' "$OUT/signing.log"
