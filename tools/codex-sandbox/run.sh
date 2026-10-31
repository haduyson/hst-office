#!/usr/bin/env bash
# Start a disposable sandbox container and run Codex in it on <prompt-file>.
#   tools/codex-sandbox/run.sh <branch> <prompt-file>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRANCH="$1"; PROMPT="$(cat "$2")"
WT="/home/office-codex/${BRANCH//\//-}"
IMAGE=hst-codex-sandbox:2
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build -t "$IMAGE" "$ROOT/tools/codex-sandbox"
mkdir -p /home/office-codex
# A standalone clone (not a worktree), so /work/.git is self-contained inside the container.
[ -d "$WT/.git" ] || { git clone -q "$ROOT" "$WT" && git -C "$WT" checkout -q -B "$BRANCH" origin/main; }
CODEX_BIN_DIR="$(dirname "$(readlink -f /root/.local/bin/codex)")"
NAME="hst-codex-${BRANCH//\//-}"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run --name "$NAME" --rm -i \
  -v "$WT:/work" -v "$ROOT/upstream/libreoffice/instdir:/opt/hst:ro" -v "$CODEX_BIN_DIR:/opt/codex:ro" \
  --mount type=bind,src=/root/.codex/auth.json,dst=/tmp/codex-auth.json,readonly \
  --mount type=bind,src=/root/.codex/config.toml,dst=/tmp/codex-config.toml,readonly \
  -e HST_INSTDIR=/opt/hst --memory 8g --cpus 3 "$IMAGE" bash -lc '
    set -e; export CODEX_HOME=/tmp/codex-home; mkdir -p "$CODEX_HOME"
    cp /tmp/codex-auth.json /tmp/codex-config.toml "$CODEX_HOME"/ 2>/dev/null; mv "$CODEX_HOME/codex-auth.json" "$CODEX_HOME/auth.json"; mv "$CODEX_HOME/codex-config.toml" "$CODEX_HOME/config.toml"
    git config --global --add safe.directory /work; git config --global user.name "HST Office"; git config --global user.email "lienhe@hasontech.vn"
    /opt/codex/codex exec --skip-git-repo-check -s danger-full-access -C /work "$(cat)"' <<<"$PROMPT"
