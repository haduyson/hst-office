# SPDX-License-Identifier: AGPL-3.0-only
"""Thin Windows wrappers; never replace the checks windows-smoke.yml already owns."""
from pathlib import Path
import re
import subprocess
from support import RUNTIME
from results import row

# The ticked installer box (W1) means no default-apps question at any start: windows-smoke's "ui-parity" scenario.
SCRIPTS = {"W1": ("check-windows-startup-prompts.py", "--expect", "registered"),
           "W2": ("check-windows-startup-prompts.py", "--expect", "registered"),
           "W6": ("check-windows-nd30-type-hover.py",),
           "W11": ("check-windows-options-pages.py",)}


def run(item, python, install, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    script, *extra = SCRIPTS[item]
    command = [str(python), "-X", "utf8", str(RUNTIME / script), "--install", str(install), "--out", str(out), *extra]
    log = out / "delegate.log"
    try:
        with log.open("w", encoding="utf-8") as stream:
            done = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  timeout=900)
        code = done.returncode
    except subprocess.TimeoutExpired:
        code = "timeout 900 s"
    finally:
        from native import cleanup
        cleanup(out.resolve().as_uri())
    screenshots = sorted(out.rglob("*.png"))
    shot = screenshots[-1].relative_to(out.parent).as_posix() if screenshots else None
    output = log.read_text(encoding="utf-8", errors="replace")
    failed = re.findall(r"^FAIL\s+(.*)$", output, re.M)
    passed = code == 0 and not failed and bool(shot)
    return row(item, "PASS" if passed else "FAIL", dict(message="Kiểm tra Windows: " + script, exit_code=code,
               failed=[line[:300] for line in failed], log=log.relative_to(out.parent).as_posix()), shot)
