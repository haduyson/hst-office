#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Local preflight for the Windows trial: catches the setup failures that otherwise cost a runner run.
# Lints scripts/workflow, checks line endings, validates configure options and simulates
# extract/patch/options/branding on this machine with a cygpath shim. Skips (with a notice)
# only the checks whose inputs (pinned tarballs, upstream tree) are not present.
set -Eeuo pipefail
trap 'echo "PREFLIGHT FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
WL_VERSION=1.7.12
WL_SHA256=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
TOOLS="$ROOT/work/tools"
fail=0
bad() { echo "FAIL: $*" >&2; fail=1; }

echo "== shellcheck + bash -n"
scripts=(scripts/windows/*.sh scripts/apply-patches.sh)
if command -v shellcheck >/dev/null; then shellcheck "${scripts[@]}" || bad shellcheck; else bad "shellcheck not installed"; fi
for f in "${scripts[@]}"; do bash -n "$f" || bad "bash -n $f"; done

echo "== line endings"
runner_files=("${scripts[@]}" scripts/windows/*.py scripts/stage-branding.py scripts/build-windows.ps1 build-config/windows-x86_64.conf patches/libreoffice/*)
for f in "${runner_files[@]}"; do
  if grep -q $'\r' "$f"; then bad "CRLF in $f"; fi
done
for rule in '*.sh text eol=lf' '*.patch text eol=lf' '*.conf text eol=lf'; do
  grep -qxF "$rule" .gitattributes || bad ".gitattributes missing: $rule"
done

echo "== actionlint"
if [ ! -x "$TOOLS/actionlint" ]; then
  mkdir -p "$TOOLS"
  curl -fsSL -o "$TOOLS/actionlint.tgz" "https://github.com/rhysd/actionlint/releases/download/v$WL_VERSION/actionlint_${WL_VERSION}_linux_amd64.tar.gz"
  echo "$WL_SHA256  $TOOLS/actionlint.tgz" | sha256sum -c - || { rm -f "$TOOLS/actionlint.tgz"; bad "actionlint sha256"; }
  tar -xzf "$TOOLS/actionlint.tgz" -C "$TOOLS" actionlint
fi
"$TOOLS/actionlint" .github/workflows/desktop-windows.yml || bad actionlint

TARBALLS="$ROOT/upstream/cache/libreoffice"
if [ -f "$TARBALLS/libreoffice-26.8.1.1.tar.xz" ]; then
  echo "== simulate extract / options / patch / branding"
  tmp="$(mktemp -d "$ROOT/work/preflight.XXXXXX")"
  trap 'rm -rf "$tmp"' EXIT
  printf '#!/bin/sh\nshift; printf "%%s\\n" "$@"\n' > "$tmp/cygpath"; chmod +x "$tmp/cygpath"
  export HST_CYGPATH="$tmp/cygpath" HST_WORK="$tmp/w" HST_DL="$TARBALLS" HST_REPO="$ROOT" HST_KEEP_PATH=1
  PY="${PYTHON:-python3}"; [ -x "$ROOT/.venv/bin/python" ] && PY="$ROOT/.venv/bin/python"
  "$PY" -I scripts/stage-branding.py --out "$tmp/w/branding" >/dev/null || bad "stage-branding"
  for stage in extract options patch; do
    bash scripts/windows/trial-build.sh "--$stage" >"$tmp/$stage.log" 2>&1 || { tail -20 "$tmp/$stage.log" >&2; bad "trial-build --$stage"; }
  done
else
  echo "SKIP simulation: pinned tarballs not in upstream/cache/libreoffice"
fi
[ "$fail" -eq 0 ] && echo "windows preflight: ok"
exit "$fail"
