#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Download one HST Office Windows MSI for the smoke workflow and check it against SHA256SUMS.
#   download-smoke-msi.sh <dest-dir> <env-var>
# Env: GH_TOKEN, GITHUB_REPOSITORY; RUN_ID (Desktop Windows run whose MSI artifact is taken) or
# RELEASE_TAG (GitHub release). The MSI's Windows path is written to $GITHUB_ENV as <env-var>.
set -euo pipefail
dest="${1:?destination directory required}"; var="${2:?environment variable name required}"
[[ "$var" =~ ^[A-Z_][A-Z0-9_]*$ ]] || { echo "bad variable name: $var" >&2; exit 1; }
mkdir -p "$dest"
if [ -n "${RUN_ID:-}" ]; then
  [[ "$RUN_ID" =~ ^[0-9]+$ ]] || { echo "bad run id" >&2; exit 1; }
  gh run download "$RUN_ID" --repo "$GITHUB_REPOSITORY" -n "hst-office-windows-msi-$RUN_ID" --dir "$dest"
else
  [[ "${RELEASE_TAG:?RELEASE_TAG or RUN_ID required}" =~ ^v[0-9A-Za-z.+-]+$ ]] || { echo "bad release tag" >&2; exit 1; }
  gh release download "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --dir "$dest" \
    --pattern 'HSTOffice_*_Win_x86-64_en-US_vi.msi' --pattern SHA256SUMS
fi
ls -l "$dest"
cd "$dest"
# Installer names carry the release id (HSTOffice_1.0.0-beta.5_Win_...; up to beta.4: HSTOffice_1.0.0_Win_...):
# take the one MSI that was downloaded and check it against SHA256SUMS.
shopt -s nullglob
msis=(HSTOffice_*_Win_x86-64_en-US_vi.msi)
[ "${#msis[@]}" -eq 1 ] || { echo "expected one installer, found ${#msis[@]}" >&2; exit 1; }
if [ -n "${RUN_ID:-}" ] && [ ! -f SHA256SUMS ]; then
  echo "no SHA256SUMS in the build artifact; checksum not verified"
else
  # "<hash>  <name>" or, in binary mode, "<hash> *<name>"
  awk -v n="${msis[0]}" '$2 == n || $2 == "*" n' SHA256SUMS > msi.sha256
  [ -s msi.sha256 ] || { echo "${msis[0]} is not in SHA256SUMS" >&2; exit 1; }
  sha256sum -c msi.sha256
fi
echo "$var=$(cygpath -w "$PWD/${msis[0]}")" >> "$GITHUB_ENV"
