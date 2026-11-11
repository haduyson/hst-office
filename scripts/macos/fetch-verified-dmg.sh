#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Fetch a released dmg for CI by its sha256, GitHub first (r1-auto-macos.yml old-profile).
#   fetch-verified-dmg.sh <out.dmg> <sha256> <run-id> <artifact> <url>
# 1. <out.dmg> already there with that sha256 (actions/cache restored it): done.
# 2. The artifact <artifact> of the build run <run-id> (gh, GH_TOKEN with actions: read): three attempts of at most
#    10 minutes each. The dmg inside must have the sha256; another file is never retried.
# 3. The published <url>, once, resumable and bounded: office.hasontech.vn served GitHub's macOS runners at ~23 kB/s
#    (r1-auto macOS run 42929394182: 28 of 288 MB in 20 min, twice), so a slow transfer is given up within a minute
#    instead of being retried until the job times out.
# Exit 0 only with <out.dmg> matching <sha256>.
set -uo pipefail
[ $# -eq 5 ] || { echo "usage: $0 <out.dmg> <sha256> <run-id> <artifact> <url>" >&2; exit 64; }
out="$1"; sha="$2"; run="$3"; artifact="$4"; url="$5"
[[ "$sha" =~ ^[0-9a-f]{64}$ && "$run" =~ ^[0-9]+$ ]] || { echo "bad sha256 or run id" >&2; exit 64; }
verified() { [ -f "$out" ] && echo "$sha  $out" | shasum -a 256 -c --status; }
within() { local seconds="$1"; shift; perl -e 'alarm shift; exec @ARGV' "$seconds" "$@"; }
mkdir -p "$(dirname "$out")"
if verified; then echo "dmg from the cache: $out"; exit 0; fi
rm -f "$out"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
for attempt in 1 2 3; do
  rm -rf "$tmp/artifact"; mkdir "$tmp/artifact"
  if within 600 gh run download "$run" --repo "$GITHUB_REPOSITORY" --name "$artifact" --dir "$tmp/artifact"; then
    found="$(find "$tmp/artifact" -name '*.dmg' -print -quit)"
    if [ -n "$found" ]; then
      mv "$found" "$out"
      if verified; then echo "dmg from artifact $artifact of run $run"; exit 0; fi
      echo "artifact $artifact holds another dmg than $sha" >&2
      rm -f "$out"
      break
    fi
    echo "artifact $artifact has no dmg" >&2
    break
  fi
  echo "artifact download attempt $attempt failed" >&2
  sleep $((attempt * 15))
done

echo "falling back to $url" >&2
if curl -fL --retry 2 --retry-all-errors --retry-delay 30 -C - --speed-limit 100000 --speed-time 60 \
     --max-time 600 -o "$tmp/download.dmg" "$url"; then
  mv "$tmp/download.dmg" "$out"
fi
if verified; then echo "dmg from $url"; exit 0; fi
rm -f "$out"
echo "no dmg with sha256 $sha" >&2
exit 1
