#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Free disk on a GitHub-hosted Ubuntu runner for the LibreOffice build and create $HST_WORK.
# Removes preinstalled toolchains the HST Office build never uses (Android SDK, .NET, Haskell,
# hosted tool caches, Swift, PowerShell, cached Docker images) and records disk/RAM/CPU
# before and after in $HST_WORK/logs/runner-disk.txt. Only for disposable CI runners.
set -Eeuo pipefail
trap 'echo "FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
WORK="${HST_WORK:?HST_WORK must name the build directory}"
report() { echo "== $1"; df -h / /mnt 2>/dev/null || df -h /; free -g; echo "cpus: $(nproc)"; }
before="$(report before)"
start=$(date +%s)
sudo rm -rf /usr/local/lib/android /usr/share/dotnet /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache \
  /usr/share/swift /usr/local/share/powershell /usr/local/share/chromium /usr/local/lib/node_modules \
  /opt/microsoft /opt/google /opt/az /usr/local/julia* /usr/local/share/boost
if command -v docker >/dev/null; then sudo docker system prune -af >/dev/null; fi
sudo mkdir -p "$WORK"
sudo chown "$(id -u):$(id -g)" "$WORK"
mkdir -p "$WORK/logs" "$WORK/metrics"
{ echo "$before"; report after; echo "cleanup seconds: $(( $(date +%s) - start ))"; echo "work: $WORK"; } \
  | tee "$WORK/logs/runner-disk.txt"
printf '{"phase":"free-disk","seconds":%d,"status":"ok","free_gib":%s}\n' $(( $(date +%s) - start )) \
  "$(df -BG --output=avail "$WORK" | tail -1 | tr -dc 0-9)" >> "$WORK/metrics/phases.jsonl"
