#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Local preflight for the macOS build: catches the setup failures that otherwise cost a runner run.
# Lints the macOS scripts and workflow, validates the configure options against the pinned
# configure.ac, checks the HST patch series and the app-icon staging on this Linux machine.
# Checks whose inputs (upstream tree, Pillow) are absent are skipped with a notice.
set -Eeuo pipefail
trap 'echo "PREFLIGHT FAILED line $LINENO: $BASH_COMMAND" >&2' ERR
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
TOOLS="$ROOT/work/tools"
fail=0
bad() { echo "FAIL: $*" >&2; fail=1; }
PY="${PYTHON:-python3}"; [ -x "$ROOT/.venv/bin/python" ] && PY="$ROOT/.venv/bin/python"

echo "== shellcheck + bash -n"
scripts=(scripts/macos/*.sh)
if command -v shellcheck >/dev/null; then shellcheck "${scripts[@]}" || bad shellcheck; else bad "shellcheck not installed"; fi
for f in "${scripts[@]}"; do bash -n "$f" || bad "bash -n $f"; done
for f in scripts/macos/*.py; do "$PY" -m py_compile "$f" || bad "py_compile $f"; done

echo "== line endings"
for f in "${scripts[@]}" scripts/macos/*.py build-config/macos-*.conf .github/workflows/desktop-macos.yml; do
  if grep -q $'\r' "$f"; then bad "CRLF in $f"; fi
done

echo "== actionlint"
if [ -x "$TOOLS/actionlint" ]; then
  "$TOOLS/actionlint" .github/workflows/desktop-macos.yml || bad actionlint
else
  echo "SKIP actionlint: $TOOLS/actionlint missing (scripts/windows/preflight-local.sh installs it)"
fi

echo "== dmg background up to date"
if fc-list 2>/dev/null | grep -q LiberationSans-Bold && "$PY" -c 'import PIL' 2>/dev/null; then
  "$PY" -I scripts/macos/make-dmg-background.py --check || bad "dmg background"
else
  echo "SKIP dmg background: needs Pillow and fonts-liberation"
fi

echo "== signing gate without secrets"
gate="$(env -i PATH="$PATH" bash scripts/macos/sign-notarize.sh --enabled 2>/dev/null)" || bad "sign-notarize --enabled failed"
[ "$gate" = "enabled=false" ] || bad "signing gate must report enabled=false without secrets, got: $gate"

LO="$ROOT/upstream/libreoffice"
if [ -f "$LO/configure.ac" ]; then
  tmp="$(mktemp -d "$ROOT/work/macos-preflight.XXXXXX")"
  trap 'rm -rf "$tmp"' EXIT
  echo "== configure options (both arches) against the pinned configure.ac"
  mkdir -p "$tmp/w/lo"; cp "$LO/configure.ac" "$tmp/w/lo/"
  for arch in arm64 x86_64; do
    HST_ARCH="$arch" HST_WORK="$tmp/w" HST_REPO="$ROOT" HST_KEEP_PATH=1 HST_PYTHON="$PY" \
      bash scripts/macos/trial-build.sh --options >"$tmp/options-$arch.log" 2>&1 \
      || { tail -5 "$tmp/options-$arch.log" >&2; bad "configure options ($arch)"; }
    grep -q -- "--with-branding=$tmp/w/branding" "$tmp/w/lo/autogen.input" || bad "branding placeholder not resolved ($arch)"
  done
  echo "== HST patch series"
  HST_LO_SRC="$LO" bash scripts/apply-patches.sh --check >"$tmp/patches.log" 2>&1 || { tail -5 "$tmp/patches.log" >&2; bad "apply-patches --check"; }
  echo "== app and document icon staging"
  icons=sysui/desktop/icons/macos
  if "$PY" -c 'import PIL' 2>/dev/null; then
    mkdir -p "$tmp/tree/sysui/desktop/icons"; cp -R "$LO/$icons" "$tmp/tree/sysui/desktop/icons/"
    "$PY" -I scripts/macos/stage-macos-icons.py --tree "$tmp/tree" >/dev/null || bad "stage-macos-icons"
    for png in app-launcher/main.iconset/icon_512x512@2x.png mime-oasis/text.iconset/icon_256x256.png mime-generic/spreadsheet.iconset/icon_32x32.png; do
      if cmp -s "$LO/$icons/$png" "$tmp/tree/$icons/$png"; then bad "icon unchanged: $png"; fi
    done
  else
    echo "SKIP icon staging: Pillow not installed for $PY"
  fi
else
  echo "SKIP option/patch/icon checks: no upstream tree at $LO"
fi
[ "$fail" -eq 0 ] && echo "macos preflight: ok"
exit "$fail"
