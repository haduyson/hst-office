#!/bin/sh
# Run a command inside a new network namespace that only has loopback, so the
# editor, plugins and driver cannot reach any network. Requires root
# (unshare -n). The X server is reached through its filesystem socket.
#   sudo scripts/runtime/run-offline.sh node scripts/runtime/qa-admin-documents.js
set -eu
exec unshare -n sh -c 'ip link set lo up && HST_OFFLINE=1 exec "$@"' run-offline "$@"
