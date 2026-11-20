#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Run a test command so that HST Office started by it cannot reach system.hasontech.vn.
#
# Unreleased test packages report banner impressions, error reports and other statistics to the production server
# as if they were real users. This wrapper runs the command in a private mount namespace where /etc/hosts also maps
# system.hasontech.vn to 0.0.0.0 and ::. Everything else is unchanged: the rest of the network, local test servers on
# 127.0.0.1, the X display, D-Bus and AT-SPI. The server's own processes (deploy, curl) keep their normal access.
#
# Usage (as root; unprivileged user namespaces are disabled on this host):
#   tests/runtime/no-hst-telemetry.sh COMMAND [ARGS...]
#   tests/runtime/no-hst-telemetry.sh runuser -u hstbuild -- python3 tests/runtime/check-xyz.py ...
# Children inherit the namespace. An office that is already running outside the wrapper is NOT covered: start the
# office (or the harness that starts it) through this wrapper.
set -euo pipefail

BLOCKED_HOST="system.hasontech.vn"

if [ $# -eq 0 ]; then
    sed -n '3,14p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
fi

if [ "${HST_NO_TELEMETRY_STAGE:-}" = "inner" ]; then
    unset HST_NO_TELEMETRY_STAGE
    mount --bind "$HST_NO_TELEMETRY_HOSTS" /etc/hosts
    rm -f "$HST_NO_TELEMETRY_HOSTS"
    unset HST_NO_TELEMETRY_HOSTS
    # Refuse to run the test if the block is not effective (e.g. the resolver does not read /etc/hosts first).
    resolved="$(getent ahosts "$BLOCKED_HOST" | awk '{print $1}' | sort -u | tr '\n' ' ')"
    case "$resolved" in
        "0.0.0.0 "|":: "|"0.0.0.0 :: "|":: 0.0.0.0 ") ;;
        *) echo "no-hst-telemetry: $BLOCKED_HOST still resolves to: ${resolved:-nothing}; not running the test" >&2
           exit 3 ;;
    esac
    exec "$@"
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "no-hst-telemetry: run as root (it needs a mount namespace); drop privileges inside with runuser" >&2
    exit 2
fi

hosts="$(mktemp /tmp/no-hst-telemetry-hosts.XXXXXX)"
{
    cat /etc/hosts
    printf '\n# no-hst-telemetry.sh: test launches must not reach the production stats server\n'
    printf '0.0.0.0 %s\n:: %s\n' "$BLOCKED_HOST" "$BLOCKED_HOST"
} > "$hosts"
chmod 644 "$hosts"

HST_NO_TELEMETRY_STAGE=inner HST_NO_TELEMETRY_HOSTS="$hosts" \
    exec unshare --mount --propagation private -- "$(readlink -f "$0")" "$@"
