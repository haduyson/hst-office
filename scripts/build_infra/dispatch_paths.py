# SPDX-License-Identifier: AGPL-3.0-only
"""Paths of the deployed build infrastructure used by the dispatcher, and its log line format.
"""
import os
import time

# Real directory of this deploy (infra-<sha>, not the infra-current symlink): jobs started by this dispatcher keep
# using this version even after the next deploy switches the symlink (scripts/linux/build-infra-deploy.sh).
HERE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))   # scripts/
LOCAL_BUILD = os.path.join(HERE, "linux", "local-build.sh")
BUILD_SLOTS = os.path.join(HERE, "linux", "build-slots.py")
WIN_HELPER = os.path.join(HERE, "windows", "hst-queue-remote.ps1")
# Deployed to <host>:D:\hst-build\tools\scripts (relative to scripts/); the checkout being built may predate them.
WIN_TOOLS = ["build-windows.ps1", "windows/hst4-build.ps1", "windows/hst4-detach.ps1", "windows/hst4-setup.ps1",
             "windows/hst4-tree.sh", "windows/hst4-make-targets.sh", "overlay/apply-build-overlay.ps1",
             "l10n/check-mo-fresh.py"]


def log(msg):
    print(f"[{time.strftime('%F %T')}] {msg}", flush=True)


def win_task_name(job_id):
    return "q-" + job_id[1:]   # hst4-detach.ps1 names: letters, digits, '-'
