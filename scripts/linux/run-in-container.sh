#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Runs scripts/linux/ci-build.sh inside a long-lived build container so the .deb is linked
# against that image's glibc (Ubuntu 22.04: the oldest supported desktop). ci-build.sh calls
# this itself when HST_CONTAINER=<image> is set and HST_IN_CONTAINER is not.
#   run-in-container.sh <ci-build.sh args>   (container hst-build, created on first use)
# The repository and HST_WORK are bind-mounted at the same paths as on the host, so
# every phase sees the same tree and the host can upload the results.
set -Eeuo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${HST_WORK:-/mnt/hst}"
IMAGE="${HST_CONTAINER:?HST_CONTAINER (image) required}"
NAME="${HST_CONTAINER_NAME:-hst-build}"
DL="${HST_DL:-$WORK/dl}"
mkdir -p "$WORK" "$DL"
if ! docker inspect --format '{{.State.Running}}' "$NAME" 2>/dev/null | grep -qx true; then
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  mounts=(-v "$REPO:$REPO" -v "$WORK:$WORK")
  case "$DL" in "$WORK"/*) ;; *) mounts+=(-v "$DL:$DL") ;; esac
  docker run -d --name "$NAME" "${mounts[@]}" "$IMAGE" sleep infinity >/dev/null
fi
env_args=(-e HST_IN_CONTAINER=1 -e HST_SUDO= -e "HST_WORK=$WORK" -e "HST_DL=$DL")
for v in HST_BUILD_DEADLINE HST_MIN_FREE_GIB HST_CLANG HST_JOB_START; do
  [ -z "${!v:-}" ] || env_args+=(-e "$v=${!v}")
done
exec docker exec "${env_args[@]}" -w "$REPO" "$NAME" bash "$REPO/scripts/linux/ci-build.sh" "$@"
