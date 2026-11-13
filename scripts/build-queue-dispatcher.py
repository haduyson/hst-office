#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Dispatcher of the local build queue (`build-queue.sh dispatch`, systemd unit hst-build-queue.service).

Stable module path kept for existing callers; the code is in scripts/build_infra/dispatch_loop.py (with
dispatch_paths, dispatch_linux and dispatch_windows).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))   # scripts/ (python3 -I adds nothing)

from build_infra.dispatch_linux import *  # noqa: E402,F401,F403
from build_infra.dispatch_loop import *  # noqa: E402,F401,F403
from build_infra.dispatch_paths import *  # noqa: E402,F401,F403
from build_infra.dispatch_windows import *  # noqa: E402,F401,F403
