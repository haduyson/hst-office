# SPDX-License-Identifier: AGPL-3.0-only
"""Thin Windows wrappers; never replace checks owned by test/windows-r1-checks."""
from pathlib import Path
import re
import subprocess
from support import RUNTIME
from results import row

PENDING = "pending test/windows-r1-checks"
SCRIPTS = {"W1": ["check-startup-prompts.py"], "W2": ["check-startup-prompts.py"],
           "W11": ["check-hst-options-pages.py"],
           "W6": ["check-nd30-hover.py", "check-windows-nd30-hover.py", "check-nd30-type-list.py"]}


def run(item, python, install, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for filename in SCRIPTS[item]:
        script = RUNTIME / filename
        if not script.exists():
            continue
        source = script.read_text(encoding="utf-8")
        # The pre-existing Linux versions require --display and cannot run on native Windows.
        if '"--install"' not in source and "'--install'" not in source:
            continue
        help_run = subprocess.run([str(python), str(script), "--help"], capture_output=True,
                                  text=True, encoding="utf-8", timeout=30)
        if help_run.returncode:
            return row(item, "FAIL", "Không đọc được giao diện script " + filename)
        command = [str(python), str(script), "--install", str(install), "--out", str(out)]
        if "--screenshots" in help_run.stdout:
            command += ["--screenshots", str(out)]
        try:
            with (out / "delegate.log").open("w", encoding="utf-8") as log:
                done = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=360)
        finally:
            from native import cleanup
            cleanup(out.resolve().as_uri())
        screenshots = sorted(out.rglob("*.png"))
        shot = screenshots[0].relative_to(out.parent).as_posix() if screenshots else None
        output = (out / "delegate.log").read_text(encoding="utf-8")
        passed = done.returncode == 0 and not re.search(r"^FAIL\b", output, re.M) and bool(shot)
        return row(item, "PASS" if passed else "FAIL", dict(message="Kiểm tra nhánh Windows: " + filename,
                   exit_code=done.returncode, log=(out / "delegate.log").relative_to(out.parent).as_posix()), shot)
    return row(item, "SKIP", PENDING)
