#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Seed a remote Linux build host (after remote-build-host-setup.sh) from the dev server's build root, so its builds
# use the same base chroot (same image digest and deps marker), external tarballs, pinned tarballs and a warm tree.
#   sudo scripts/linux/remote-build-host-seed.sh --host vm103 [--from-slot N] [--slots 2]
# Reads the host's address, key and known_hosts from the queue's config.json (linux_remote_hosts). A local slot is
# copied only while its .lock is held, so no build changes it during the copy (the admission controller skips a
# locked slot). Remote slot 1 gets the copy; further remote slots are cloned from it on the host
# (build-slots-setup.sh clone, hard-linked tarballs). The ccache is not copied: it fills on the host (cap 10G).
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
NAME=""; FROM=""; SLOTS=2
BUILD_ROOT="${HST_BUILD_ROOT:-/data/hst-build}"; QUEUE_ROOT="${HST_QUEUE_ROOT:-/data/hst-build-queue}"
TARBALL_CACHE="${HST_LOCAL_TARBALL_CACHE:-/home/office/upstream/cache/libreoffice}"
while [ $# -gt 0 ]; do
  case "$1" in
    --host) NAME="$2"; shift 2 ;;
    --from-slot) FROM="$2"; shift 2 ;;
    --slots) SLOTS="$2"; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 64 ;;
  esac
done
log() { echo "[$(date '+%F %T')] $*"; }
die() { echo "remote-build-host-seed: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "needs root"
[[ "$SLOTS" =~ ^[12]$ ]] || die "--slots 1 or 2"
read -r ADDR KEY KH RROOT < <(python3 -I - "$QUEUE_ROOT/config.json" "$NAME" <<'EOF'
import json, sys
for h in json.load(open(sys.argv[1])).get("linux_remote_hosts", []):
    if h["name"] == sys.argv[2]:
        print(h["address"], h["key"], h["known_hosts"], h.get("root", "/data/hst-build"))
        break
else:
    sys.exit(f"no linux_remote_hosts entry {sys.argv[2]!r} in {sys.argv[1]}")
EOF
) || die "host lookup failed"
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o "UserKnownHostsFile=$KH" -o StrictHostKeyChecking=yes
     -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3)
RSYNC=(rsync -aH --info=stats1 --timeout=120 -e "${SSH[*]}")
remote() { "${SSH[@]}" "root@$ADDR" "$@"; }

if [ -z "$FROM" ]; then   # the first idle local slot (free-slot also skips locked ones)
  for s in "$BUILD_ROOT"/slots/*/; do
    s="$(basename "$s")"; exec 7>>"$BUILD_ROOT/slots/$s/.lock"
    if flock -n 7; then FROM="$s"; break; fi
  done
  [ -n "$FROM" ] || die "no idle local slot to copy"
else
  exec 7>>"$BUILD_ROOT/slots/$FROM/.lock"; flock -n 7 || die "local slot $FROM is busy"
fi
log "copying from local slot $FROM (locked during the copy) to $NAME ($ADDR):$RROOT"
"${RSYNC[@]}" --delete "$BUILD_ROOT/chroot/" "root@$ADDR:$RROOT/chroot/"
"${RSYNC[@]}" "$TARBALL_CACHE/" "root@$ADDR:$RROOT/tarball-cache/"
# One transfer for external-tarballs/ and the slot's src/ + checkout/, so the hard links between the tree's
# external/tarballs and the shared cache stay hard links on the host (-H works within one run). root/,
# chroot-upper/ and logs/ are per-host state and are not copied. The copy lands in slots/<from>/ and becomes slot 1.
remote "test ! -e $RROOT/slots/1 || test $FROM = 1" || die "$NAME already has a slot 1"
"${RSYNC[@]}" -R "$BUILD_ROOT/./external-tarballs" "$BUILD_ROOT/./slots/$FROM/src" "$BUILD_ROOT/./slots/$FROM/checkout" \
  "root@$ADDR:$RROOT/"
[ "$FROM" = 1 ] || remote mv "$RROOT/slots/$FROM" "$RROOT/slots/1"
remote mkdir -p "$RROOT/slots/1/logs/ci"
flock -u 7
log "local slot $FROM released"
remote "printf 'max_size = 10G\n' > $RROOT/ccache/ccache.conf"
if [ "$SLOTS" -eq 2 ]; then
  infra="$(remote "ls -d $RROOT/infra-* 2>/dev/null | tail -1")"
  [ -n "$infra" ] || die "no infra deployed on $NAME yet (the dispatcher deploys it at its first contact)"
  remote env HST_BUILD_ROOT="$RROOT" HST_MIN_FREE_GIB=15 HST_CCACHE_MAX_GIB=10 HST_OUT_RESERVE_GIB=3 \
    bash "$infra/scripts/linux/build-slots-setup.sh" clone 2
fi
log "seeded: $(remote "du -sh $RROOT 2>/dev/null | cut -f1; df -h $RROOT | tail -1")"
