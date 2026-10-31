# Codex sandbox (cách A)

Isolated container in which Codex CLI runs with full access *inside the container only*.

Mounted:
- `/work` (rw): a separate local git clone of this repo on a `codex/*` branch (never the shared tree).
- `/opt/hst` (ro): `upstream/libreoffice/instdir` of the local build.
- `/opt/codex` (ro): the Codex CLI binary. Its auth is copied into a container-only `CODEX_HOME`.

Not mounted: `/root`, `.claude/`, signing keys, Docker socket, other projects. No git push credentials:
the coordinator reviews the branch on the host and merges.

Usage: `tools/codex-sandbox/run.sh <branch> <prompt-file>` (see the script).
