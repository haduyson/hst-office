#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""HST Office local build queue: agents submit builds themselves, a dispatcher runs them on the build slots.

Stable entry point (scripts/build-queue.sh, the systemd unit hst-build-queue.service); the code and the full usage
are in scripts/build_infra/queue_cli.py (with queue_store, queue_rules, queue_ops, queue_report).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))   # scripts/ (python3 -I adds nothing)

from build_infra.queue_cli import main  # noqa: E402
from build_infra.queue_core import *  # noqa: E402,F401,F403

if __name__ == "__main__":
    sys.exit(main())
