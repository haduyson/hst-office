#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# HST Office AppImage on a clean distribution, in an auto-removed container, as a normal user:
#   - start without FUSE at all (expected: the runtime's hint) and with --appimage-extract-and-run;
#   - start with /dev/fuse and fuse3 only (no libfuse2 installed): the static type-2 runtime mounts by itself;
#   - first-start desktop integration in ~/.local/share (launchers point at the AppImage, icons, MIME), the
#     moved-AppImage refresh, removal (--remove-desktop-integration) that is remembered;
#   - open/save .docx/.xlsx with Vietnamese text, GUI start under Xvfb.
#   tests/runtime/check-appimage.sh <AppImage> [out-dir]
# Environment: IMAGE (default ubuntu:24.04; ubuntu:22.04, debian:12, fedora:41, archlinux work).
# Uses --device /dev/fuse --cap-add SYS_ADMIN for the FUSE step only (the host's /dev/fuse); network for packages.
set -euo pipefail
IMAGE="${IMAGE:-ubuntu:24.04}"
APP="${1:?usage: $0 <AppImage> [out-dir]}"
[ -f "$APP" ] || { echo "BLOCKED: no such file $APP"; exit 2; }
APP="$(cd "$(dirname "$APP")" && pwd)/$(basename "$APP")"
OUT="${2:-tests/output/appimage-${IMAGE//[:\/]/-}}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="hst-appimage-qa-$$"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || :' EXIT
docker run --rm --name "$NAME" --device /dev/fuse --cap-add SYS_ADMIN --security-opt apparmor:unconfined \
  -v "$APP:/pkg/HSTOffice.AppImage:ro" -v "$HERE/check-appimage-inside.sh:/inside.sh:ro" \
  -v "$HERE/office-roundtrip-vi.py:/roundtrip.py:ro" "$IMAGE" bash /inside.sh 2>&1 | tee "$OUT/appimage.log"
status=${PIPESTATUS[0]}
grep -q '^FAIL' "$OUT/appimage.log" && status=1
echo "result: $([ "$status" = 0 ] && echo PASS || echo FAIL) (log: $OUT/appimage.log)"
exit "$status"
