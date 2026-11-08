# SPDX-License-Identifier: AGPL-3.0-only
"""Resolve the artifact's own pyuno interpreter and contain probe process lifetimes."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from support import HERE
from native import cleanup, screenshot
from results import row


def interpreter(install):
    install = Path(install)
    env = dict(os.environ, R1_TOOLS_PYTHON=sys.executable)
    if platform.system() == "Windows":
        program = install / "program"
        python = program / "python.exe"
        env.update(UNO_PATH=str(program), PATH=str(program) + os.pathsep + env["PATH"])
    elif platform.system() == "Darwin":
        candidates = [p for p in install.glob("Contents/**/bin/python3*")
                      if p.is_file() and not p.name.endswith("-config") and os.access(p, os.X_OK)]
        if not candidates:
            raise RuntimeError("Thiếu Python trong ứng dụng")
        python = sorted(candidates, key=lambda p: len(p.name))[0]
        bridges = list(install.glob("Contents/**/pyuno*.so")) + list(install.glob("Contents/**/pyuno*.dylib"))
        if not bridges:
            raise RuntimeError("Thiếu pyuno trong ứng dụng")
        resources = install / "Contents/Resources"
        env.update(URE_BOOTSTRAP="vnd.sun.star.pathname:" + str(resources / "fundamentalrc"),
                   PYTHONPATH=os.pathsep.join([str(resources), str(bridges[0].parent)]))
    else:
        python = Path("/usr/bin/python3")
        program = install / "program"
        env.update(PYTHONPATH=str(program), URE_BOOTSTRAP="vnd.sun.star.pathname:" + str(program / "fundamentalrc"))
    if not python.is_file():
        raise RuntimeError("Không tìm thấy Python đã đóng gói")
    return python, env


def probe(item, install, out, work, fixtures):
    python, env = interpreter(install)
    out, work = Path(out), Path(work)
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    result = work / "probe-result.json"
    command = [str(python), str(HERE / "probe.py"), "--item", item, "--install", str(install),
               "--out", str(out), "--work", str(work), "--result", str(result), "--fixtures", str(fixtures)]
    try:
        with (out / "probe.log").open("w", encoding="utf-8") as log:
            done = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=420)
        if result.exists():
            payload = json.loads(result.read_text(encoding="utf-8"))
            if done.returncode and payload["result"]["status"] != "FAIL":
                payload["result"] = row(item, "FAIL", "Tiến trình kiểm tra kết thúc bất thường")
            return payload
        raise RuntimeError(f"Tiến trình không ghi kết quả, exit={done.returncode}")
    except Exception as error:
        shot = out / "watchdog.png"
        try:
            screenshot(shot)
        except Exception:
            pass
        return dict(result=row(item, "FAIL", dict(message=f"{type(error).__name__}: {error}"),
                               shot.relative_to(out.parent).as_posix() if shot.exists() else None), owner_review=[])
    finally:
        cleanup((work / "profile").as_uri())
        from default_session import stop_recorded
        stop_recorded(work / "default-pids.txt")
