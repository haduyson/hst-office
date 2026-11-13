#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Install-lifecycle test of the HST Office .rpm in a clean, auto-removed container:
# install (dnf / zypper, unsigned local file) -> metadata, launchers, MIME, icons -> open and save .docx/.xlsx with
# Vietnamese text as a normal user -> GUI start under Xvfb -> optional distribution LibreOffice side by side ->
# upgrade/reinstall with `rpm -U --replacepkgs` -> erase -> nothing left, user documents kept.
#   tests/runtime/check-rpm-install.sh <rpm-file> [out-dir]
# Environment: IMAGE (default fedora:42; fedora:40/41, opensuse/leap:15.6, opensuse/tumbleweed work; rockylinux:9 fails
#              by design: glibc 2.34 < the package's GLIBC_2.35, see docs/LINUX_PACKAGES.md),
#              COEXIST=1 also installs the distribution's LibreOffice Writer first and checks both run.
#              RPM_KEY=<public key file>: the package is GPG-signed; the key is imported first, zypper runs WITHOUT
#              --allow-unsigned-rpm and `rpm -K` must report the signature OK.
# Needs network inside the container (dependencies). Exit 0 = every check passed.
set -euo pipefail
IMAGE="${IMAGE:-fedora:42}"
RPM="${1:?usage: $0 <rpm-file> [out-dir]}"
[ -f "$RPM" ] || { echo "BLOCKED: no such file $RPM"; exit 2; }
RPM="$(cd "$(dirname "$RPM")" && pwd)/$(basename "$RPM")"
OUT="${2:-tests/output/rpm-install-${IMAGE//[:\/]/-}}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="hst-rpm-qa-$$"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || :' EXIT
KEYMOUNT=()
if [ -n "${RPM_KEY:-}" ]; then KEYMOUNT=(-v "$(realpath "$RPM_KEY"):/pkg/RPM-GPG-KEY-hasontech:ro"); fi
docker run --rm --name "$NAME" -e COEXIST="${COEXIST:-}" "${KEYMOUNT[@]}" -v "$RPM:/pkg/hst.rpm:ro" \
  -v "$HERE/check-rpm-install-inside.sh:/inside.sh:ro" -v "$HERE/office-roundtrip-vi.py:/roundtrip.py:ro" "$IMAGE" \
  bash /inside.sh 2>&1 | tee "$OUT/install-lifecycle.log"
status=${PIPESTATUS[0]}
grep -q '^FAIL' "$OUT/install-lifecycle.log" && status=1
echo "result: $([ "$status" = 0 ] && echo PASS || echo FAIL) (log: $OUT/install-lifecycle.log)"
exit "$status"
