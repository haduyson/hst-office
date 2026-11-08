#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Workflow-final cleanup, restricted to this run's profiles and recorded startup PIDs."""
from pathlib import Path
import platform
import subprocess
import sys
from native import cleanup
from default_session import stop_recorded

work, out = map(lambda p: Path(p).resolve(), sys.argv[1:3])
for item in [f"W{i}" for i in range(1, 16)] + [f"M{i}" for i in range(1, 9)]:
    cleanup((work / item / "profile").as_uri())
    cleanup((out / item).as_uri())
    stop_recorded(work / item / "default-pids.txt")
if platform.system() == "Darwin":
    from mac_access import close_owned
    pids = out / "startup-pids.txt"
    if pids.exists():
        close_owned({int(pid) for pid in pids.read_text().split()})
    for mount in (out.parent / "r1-mounted", work / "fallback-mount"):
        if mount.exists():
            subprocess.run(["hdiutil", "detach", str(mount)], check=False, capture_output=True)

certificate = work / "temporary-certificate.txt"
if platform.system() == "Windows" and certificate.exists():
    from software_certificate import remove
    remove(certificate.read_text().strip())
    certificate.unlink()
