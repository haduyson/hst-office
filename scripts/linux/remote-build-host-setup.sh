#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# One-time setup of a REMOTE Linux build host for the build queue (dispatch_remote_linux.py), run ON that host as
# root (the dev server streams it: `ssh root@host bash -s -- [options] < remote-build-host-setup.sh`).
#   --mem-gib N     MemoryMax of hst-build.slice, all builds together (default 24)
#   --cpus N        CPUQuota of the slice in cores (default 12; leave the rest to the OS and sshd)
#   --root DIR      build root (default /data/hst-build)
# Anti-hang measures, the host must stay reachable whatever a build does:
#   - hst-build.slice: MemoryMax/MemoryHigh, MemorySwapMax=0, CPUQuota, IOWeight 10 for every queue job and its make
#     scopes (local-build.sh HST_LOCAL_SLICE);
#   - earlyoom: kills compilers/linkers first when memory runs out, never sshd/systemd/journald;
#   - sshd and journald: OOMScoreAdjust=-1000 (the kernel OOM killer picks a build instead);
#   - the disk floor is enforced by build-slots.py/local-build.sh (HST_MIN_FREE_GIB from the dispatcher).
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
MEM_GIB=24; CPUS=12; ROOT=/data/hst-build
while [ $# -gt 0 ]; do
  case "$1" in
    --mem-gib) MEM_GIB="$2"; shift 2 ;;
    --cpus) CPUS="$2"; shift 2 ;;
    --root) ROOT="$2"; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 64 ;;
  esac
done
[[ "$MEM_GIB" =~ ^[0-9]+$ && "$CPUS" =~ ^[0-9]+$ && "$ROOT" = /* ]] || { echo "bad options" >&2; exit 64; }
[ "$(id -u)" -eq 0 ] || { echo "needs root" >&2; exit 1; }
log() { echo "[$(date '+%F %T')] $*"; }

export DEBIAN_FRONTEND=noninteractive
log "packages"
apt-get update -qq
apt-get install -y -qq --no-install-recommends git rsync python3 earlyoom ca-certificates util-linux >/dev/null

log "hst-build.slice: MemoryMax=${MEM_GIB}G, CPUQuota=$((CPUS * 100))%, no swap"
cat > /etc/systemd/system/hst-build.slice <<EOF
[Unit]
Description=HST Office queue builds (all of them together)
[Slice]
MemoryMax=${MEM_GIB}G
MemoryHigh=$((MEM_GIB - 2))G
MemorySwapMax=0
CPUQuota=$((CPUS * 100))%
IOWeight=10
EOF

log "sshd and journald protected from the OOM killer"
for unit in ssh systemd-journald; do
  mkdir -p "/etc/systemd/system/$unit.service.d"
  printf '[Service]\nOOMScoreAdjust=-1000\n' > "/etc/systemd/system/$unit.service.d/hst-oom.conf"
done

log "earlyoom: kill builds first, never sshd"
cat > /etc/default/earlyoom <<'EOF'
# HST Office build host: act at 6 % free RAM / 10 % free swap; build processes first; never the access path.
EARLYOOM_ARGS="-m 6 -s 10 -r 300 --prefer ^(cc1plus|cc1|clang|clang[+][+]|clang-[0-9]+|ld|ld[.]lld|lld|make|java|javac)$ --avoid ^(sshd|systemd|systemd-journal|systemd-logind|earlyoom|dbus-daemon|agetty)$"
EOF
systemctl daemon-reload
systemctl enable -q --now earlyoom
systemctl restart earlyoom
systemctl try-restart ssh systemd-journald || true

log "layout under $ROOT"
mkdir -p "$ROOT"/{slots,locks,queue/logs,queue/out,queue/rc,tarball-cache,ccache,external-tarballs}
if [ ! -d "$ROOT/repo.git" ]; then
  git init -q --bare "$ROOT/repo.git"
  git -C "$ROOT/repo.git" remote add origin https://github.com/haduyson/hst-office.git
fi
git -C "$ROOT/repo.git" config gc.auto 0
log "done: $(nproc) cores, $(awk '/MemTotal/ {printf "%d GiB", $2/1048576}' /proc/meminfo), $(df -BG --output=avail "$ROOT" | tail -1 | tr -d ' ') free on $ROOT"
