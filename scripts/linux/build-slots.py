#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Admission controller of the parallel local Linux build slots (scripts/linux/local-build.sh --slot N).

Stable entry point used by local-build.sh and the build queue dispatcher; the code and the full usage are in
scripts/build_infra/slots_cli.py (with slots_model, slots_host and slots_controller).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))   # scripts/ (python3 -I adds nothing)

from build_infra.slots_cli import main  # noqa: E402
from build_infra.slots_controller import Controller  # noqa: E402,F401
from build_infra.slots_host import *  # noqa: E402,F401,F403
from build_infra.slots_model import *  # noqa: E402,F401,F403

if __name__ == "__main__":
    sys.exit(main())
