# SPDX-License-Identifier: AGPL-3.0-only
"""Platform prerequisites; startup failures remain failures while unrelated probes continue."""
import hashlib
from pathlib import Path
import subprocess
from results import row
from native import screenshot


def installation(args, results):
    package = Path(args.package).resolve()
    if not package.is_file():
        raise FileNotFoundError("Không có bộ cài")
    results.report["package"] = dict(name=package.name, sha256=hashlib.sha256(package.read_bytes()).hexdigest())
    results.save()
    if args.platform == "windows":
        from windows_install import install
        root, receipt = install(package, args.out)
        return root, receipt, True
    from mac_startup import prepare
    from mac_access import applications
    if Path("/Applications/HST Office.app").exists() or applications():
        raise RuntimeError("Runner đã có HST Office; không được dùng lại bản cài khác")
    def record(value):
        if value["item"] in {r["item"] for r in results.report["results"]}:
            results.put(value)
    try:
        return prepare(package, args.out, record), None, True
    except Exception as error:
        for item in ("M1", "M2"):
            current = next((r for r in results.report["results"] if r["item"] == item), None)
            if current and current["detail"] == "Chưa chạy: chuẩn bị hoặc tiến trình bị gián đoạn":
                shot = Path(args.out) / (item + "-startup-failure.png")
                screenshot(shot)
                record(row(item, "FAIL", dict(message=f"{type(error).__name__}: {error}"), shot.name))
        # Continue M4–M8 against the unchanged artifact. This does not satisfy M1–M3.
        destination = Path("/Applications/HST Office.app")
        if not destination.exists():
            mount = Path(args.work) / "fallback-mount"
            mount.mkdir(parents=True, exist_ok=True)
            subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint", str(mount),
                            str(package)], check=True, capture_output=True)
            try:
                subprocess.run(["ditto", str(mount / "HST Office.app"), str(destination)], check=True)
            finally:
                subprocess.run(["hdiutil", "detach", str(mount)], check=True, capture_output=True)
        return destination, None, False
