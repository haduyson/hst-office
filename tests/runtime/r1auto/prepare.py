# SPDX-License-Identifier: AGPL-3.0-only
"""Platform prerequisites; startup failures remain failures while unrelated probes continue."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from results import needs_signed_row, row
from native import screenshot

STARTUP_TIMEOUT = 900  # M1+M2 with Gatekeeper verification and two relaunches; a hang fails here, not at job timeout
QUIET = dict(check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=300)


def startup(package, out):
    """Run mac_startup.py in its own process so no AX, `open` or hdiutil call can outlive the hard timeout."""
    out = Path(out)
    records = out / "startup-records.jsonl"
    log = out / "startup.log"
    command = [sys.executable, str(Path(__file__).with_name("mac_startup.py")), str(package), str(out), str(records)]
    with log.open("w", encoding="utf-8") as stream:
        child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        try:
            child.wait(STARTUP_TIMEOUT)
            error = None if child.returncode == 0 else RuntimeError(f"Khởi động M1/M2 thất bại, exit={child.returncode}")
        except subprocess.TimeoutExpired:
            try:
                screenshot(out / "startup-timeout.png")
            except Exception:
                pass
            child.kill()
            child.wait(30)
            error = TimeoutError(f"M1/M2 quá {STARTUP_TIMEOUT} s; ngăn xếp trong startup-stack.log")
    rows = [json.loads(line) for line in records.read_text(encoding="utf-8").splitlines()] if records.exists() else []
    tail = [line for line in log.read_text(encoding="utf-8").splitlines() if line.startswith("{")]
    if error and tail:
        error = type(error)(f"{error}: {json.loads(tail[-1]).get('error', '')}")
    return rows, error


def installation(args, results):
    package = Path(args.package).resolve()
    if not package.is_file():
        raise FileNotFoundError("Không có bộ cài")
    results.report["package"] = dict(name=package.name, sha256=hashlib.sha256(package.read_bytes()).hexdigest())
    if args.platform == "macos":
        results.report["package"]["signed"] = os.environ.get("R1_SIGNED") == "true"
    results.save()
    if args.platform == "windows":
        from windows_install import install
        root, receipt = install(package, args.out)
        return root, receipt, True
    from mac_access import applications, close_owned
    destination = Path("/Applications/HST Office.app")
    if destination.exists() or applications():
        raise RuntimeError("Runner đã có HST Office; không được dùng lại bản cài khác")
    def record(value):
        if value["item"] in {r["item"] for r in results.report["results"]}:
            results.put(value)
    if not results.report["package"]["signed"]:
        # Gatekeeper refuses an unsigned quarantined bundle: M1-M3 wait for the signed release dmg.
        for item in ("M1", "M2"):
            record(needs_signed_row(item))
        install_without_quarantine(args, package, destination)
        return destination, None, None
    rows, error = startup(package, args.out)
    from mac_access import dismiss_download
    for _ in range(5):  # a prompt left by a stopped start would steal the keyboard from the probes
        if not dismiss_download():
            break
    for value in rows:
        record(value)
    if error is None:
        return destination, None, True
    pids = Path(args.out) / "startup-pids.txt"
    close_owned({int(pid) for pid in pids.read_text().split()} if pids.exists() else set())
    close_owned({app.processIdentifier() for app in applications()})
    subprocess.run(["hdiutil", "detach", "-force", str(Path(args.out).parent / "r1-mounted")],
                   check=False, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
    for item in ("M1", "M2"):
        current = next((r for r in results.report["results"] if r["item"] == item), None)
        if current and current["detail"] == "Chưa chạy: chuẩn bị hoặc tiến trình bị gián đoạn":
            shot = Path(args.out) / (item + "-startup-failure.png")
            try:
                screenshot(shot)
            except Exception:
                pass
            record(row(item, "FAIL", dict(message=f"{type(error).__name__}: {error}", log="startup.log",
                                          stack="startup-stack.log"), shot.name if shot.exists() else None))
    # Continue M4–M8 against the unchanged artifact. This does not satisfy M1–M3.
    install_without_quarantine(args, package, destination)
    return destination, None, False


def install_without_quarantine(args, package, destination):
    """The app copied without the quarantine flag: Gatekeeper is M1's subject, and a prompt here would only block
    the unrelated probes."""
    if not destination.exists():
        mount = Path(args.work) / "fallback-mount"
        mount.mkdir(parents=True, exist_ok=True)
        subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint", str(mount),
                        str(package)], **QUIET)
        try:
            subprocess.run(["ditto", "--noqtn", str(mount / "HST Office.app"), str(destination)], **QUIET)
        finally:
            subprocess.run(["hdiutil", "detach", "-force", str(mount)], **QUIET)
