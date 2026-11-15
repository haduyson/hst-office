#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Local build queue for agents (Linux .deb on the dev server's slots, Windows MSI on HST4/HST5): see
# scripts/build-queue.py and docs/BUILD_MATRIX.md. Submitting needs write access to /data/hst-build-queue (root).
#   scripts/build-queue.sh submit --platform linux|windows --ref <branch|sha> [--priority N] [--no-package] [--modules a,b]
#   scripts/build-queue.sh status|wait|cancel <id>;  scripts/build-queue.sh list [--all]
exec python3 -I "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/build-queue.py" "$@"
