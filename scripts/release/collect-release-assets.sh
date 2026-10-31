#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Collects the installers of successful Windows, Linux and macOS builds of ONE commit on main,
# verifies each artifact against its own SHA256SUMS and writes them, plus one combined
# SHA256SUMS, to an output directory for the release workflow.
#   collect-release-assets.sh <out-dir>
# Environment (all optional):
#   PLATFORMS         space-separated subset of "windows linux macos" (default: all three)
#   COMMIT            commit to release (default: head of the newest successful Windows build)
#   WINDOWS_RUN_ID / LINUX_RUN_ID / MACOS_RUN_ID   pin a specific run instead of searching
#   MACOS_COMMIT      take the macOS dmgs from this later commit instead; accepted only when it
#                     descends from COMMIT and changes nothing the Windows/Linux installers are
#                     built from (scripts/release/macos-commit-paths.sh), e.g. a macOS packaging fix
# Requires gh with GH_TOKEN/GH_REPO set (actions: read).
set -euo pipefail

out="${1:?usage: $0 <out-dir>}"
platforms="${PLATFORMS:-windows linux macos}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$out"

declare -A WORKFLOW=([windows]=desktop-windows.yml [linux]=desktop-linux.yml [macos]=desktop-macos.yml)
declare -A PINNED=([windows]="${WINDOWS_RUN_ID:-}" [linux]="${LINUX_RUN_ID:-}" [macos]="${MACOS_RUN_ID:-}")

die() { echo "release: $*" >&2; exit 1; }

check_run() { # <platform> <run id> -> prints head sha; fails unless a successful run of that workflow on main
  local platform="$1" id="$2" wf branch status conclusion sha
  [[ "$id" =~ ^[0-9]+$ ]] || die "bad $platform run id: $id"
  IFS=$'\t' read -r wf branch status conclusion sha < <(gh api "repos/$GH_REPO/actions/runs/$id" \
    --jq '[.path, .head_branch, .status, .conclusion, .head_sha] | @tsv')
  [ "$wf" = ".github/workflows/${WORKFLOW[$platform]}" ] || die "run $id is $wf, not the $platform build"
  if [ "$branch" != main ] || [ "$status" != completed ] || [ "$conclusion" != success ]; then
    die "$platform run $id must be a successful build on main ($branch $status $conclusion)"
  fi
  echo "$sha"
}

find_run() { # <platform> <commit> -> newest successful run id of that workflow on main at commit
  gh run list --workflow "${WORKFLOW[$1]}" --branch main --status success -L 50 \
    --json databaseId,headSha --jq "[.[] | select(.headSha == \"$2\")][0].databaseId // empty"
}

artifact_names() { # <run id> -> artifact names, one per line (expired ones excluded)
  gh api "repos/$GH_REPO/actions/runs/$1/artifacts" --paginate --jq '.artifacts[] | select(.expired | not) | .name'
}

fetch() { # <run id> <artifact name> -> verified copy of its installer files into $out
  local dir="$work/$2"
  gh run download "$1" -n "$2" -D "$dir"
  [ -f "$dir/SHA256SUMS" ] || die "$2 has no SHA256SUMS"
  (cd "$dir" && sha256sum -c SHA256SUMS)
  find "$dir" -maxdepth 1 -type f ! -name SHA256SUMS -exec cp {} "$out/" \;
}

commit="${COMMIT:-}"
if [ -z "$commit" ]; then
  if [ -n "${PINNED[windows]}" ]; then
    commit="$(check_run windows "${PINNED[windows]}")"
  else
    commit="$(gh run list --workflow desktop-windows.yml --branch main --status success -L 1 --json headSha --jq '.[0].headSha // empty')"
  fi
  [ -n "$commit" ] || die "no successful Windows build on main to release"
fi
echo "release commit: $commit"

macos_commit="${MACOS_COMMIT:-}"
if [ -n "$macos_commit" ] && [ "$macos_commit" != "$commit" ]; then
  [[ "$macos_commit" =~ ^[0-9a-f]{40}$ ]] || macos_commit="$(gh api "repos/$GH_REPO/commits/$macos_commit" --jq .sha)"
  IFS=$'\t' read -r cmp_status behind nfiles < <(gh api "repos/$GH_REPO/compare/$commit...$macos_commit" \
    --jq '[.status, .behind_by, (.files | length)] | @tsv')
  if [ "$cmp_status" != ahead ] || [ "$behind" != 0 ]; then
    die "macOS commit $macos_commit is not a descendant of $commit ($cmp_status)"
  fi
  [ "$nfiles" -lt 300 ] || die "macOS commit $macos_commit changes too many files to check ($nfiles)"
  gh api "repos/$GH_REPO/compare/$commit...$macos_commit" --jq '.files[].filename' \
    | bash "$(dirname "${BASH_SOURCE[0]}")/macos-commit-paths.sh" \
    || die "macOS commit $macos_commit changes more than macOS packaging/CI/docs since $commit"
  echo "macOS commit: $macos_commit (only macOS packaging, CI or docs changed since $commit)"
else
  macos_commit="$commit"
fi

for platform in $platforms; do
  [ -n "${WORKFLOW[$platform]:-}" ] || die "unknown platform: $platform"
  expected="$commit"
  if [ "$platform" = macos ]; then expected="$macos_commit"; fi
  id="${PINNED[$platform]}"
  [ -n "$id" ] || id="$(find_run "$platform" "$expected")"
  [ -n "$id" ] || die "no successful $platform build on main at $expected; run ${WORKFLOW[$platform]} (mode=full) first"
  sha="$(check_run "$platform" "$id")"
  [ "$sha" = "$expected" ] || die "$platform run $id built $sha, not $expected: installers must come from the release commit"
  names="$(artifact_names "$id")"
  case "$platform" in
    windows) fetch "$id" "hst-office-windows-msi-$id" ;;
    linux)   fetch "$id" "hst-office-linux-deb-$id" ;;
    macos)
      for arch in arm64 x86_64; do
        # Prefer the signed and notarized dmg when the signing stage produced one.
        if grep -qx "hst-office-macos-$arch-dmg-signed-$id" <<<"$names"; then
          fetch "$id" "hst-office-macos-$arch-dmg-signed-$id"
        elif grep -qx "hst-office-macos-$arch-dmg-$id" <<<"$names"; then
          fetch "$id" "hst-office-macos-$arch-dmg-$id"
        else
          die "macOS run $id has no $arch dmg artifact"
        fi
      done ;;
  esac
  echo "$platform: run $id"
done

(cd "$out" && rm -f SHA256SUMS && sha256sum -- * > "$work/sums" && mv "$work/sums" SHA256SUMS)
printf 'commit=%s\nmacos_commit=%s\n' "$commit" "$macos_commit" > "$out/.release-commit"
ls -la "$out"
