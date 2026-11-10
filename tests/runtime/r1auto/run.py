#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Điều phối R1 trên runner native; không dispatch CI và không sửa bản cài."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
from results import Results, gate, parse_items, row
from support import HERE
from native import screenshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--items", default="")
    parser.add_argument("--package", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--scale", type=int, choices=(100, 150, 200), default=100)
    args = parser.parse_args()
    items = parse_items(args.items, args.platform)
    args.out, args.work = str(Path(args.out).resolve()), str(Path(args.work).resolve())
    results = Results(args.out, args.platform, args.run_id, items)
    try:
        wanted = "Windows" if args.platform == "windows" else "Darwin"
        if platform.system() != wanted:
            raise RuntimeError("Cần runner native " + wanted)
        Path(args.work).mkdir(parents=True, exist_ok=True)
        from scaling import configure
        try:
            display = configure(args.scale)
            os.environ["R1_SCALE_READY"] = "1"
        except Exception as error:
            display = dict(error=f"{type(error).__name__}: {error}")
            os.environ["R1_SCALE_READY"] = "0"
        os.environ["R1_SCALE_DETAIL"] = json.dumps(display, ensure_ascii=False)
        results.report["display"] = display
        results.save()
        from prepare import installation
        install, receipt, startup_ok = installation(args, results)
        if os.environ.get("R1_OVERLAY_OXT"):
            # a fix of the bundled extension tried on this build, before any profile has registered the old one
            import shutil
            import zipfile
            target = Path(install) / "share" / "extensions" / "hst-vietnamese-tools"
            shutil.rmtree(target)
            zipfile.ZipFile(os.environ["R1_OVERLAY_OXT"]).extractall(target)
            results.report["overlay_extension"] = os.environ["R1_OVERLAY_OXT"]
        from launch import interpreter, probe
        from fixtures import generate
        fixtures = Path(args.work) / "fixtures"
        if set(items) & {"W12", "W13", "W14", "M8"}:
            generate(fixtures)
        python, env = interpreter(install)
        for item in items:
            if item in {"M1", "M2"}:
                continue
            if item == "M3" and not startup_ok:
                results.put(row(item, "FAIL", "Không đạt bước chuyển ứng dụng và đồng ý mở tài liệu mặc định"))
                continue
            out, work = Path(args.out) / item, Path(args.work) / item
            try:
                if item == "W16":
                    # Explorer routes in the tooling Python: the office is reached only through the shell.
                    import open_routes
                    results.put(open_routes.run(install, out, work))
                    continue
                if item in {"W1", "W2", "W6", "W11"}:
                    import delegated
                    # The child needs the bundled bridge search path without contaminating this tooling interpreter.
                    saved = dict(os.environ)
                    try:
                        os.environ.update(env)
                        value = delegated.run(item, python, install, out)
                    finally:
                        os.environ.clear()
                        os.environ.update(saved)
                    if item == "W1":
                        value["detail"] = dict(message=value["detail"] if isinstance(value["detail"], str)
                                                else value["detail"]["message"], installation=receipt,
                                                startup=value["detail"])
                        value["screenshot"] = receipt["screenshots"][0]
                    if item != "W2":
                        results.put(value)
                        continue
                    prompts = value
                thumbprint = None
                try:
                    if item == "W14":
                        from software_certificate import install as install_cert, remove
                        thumbprint = install_cert()
                        (Path(args.work) / "temporary-certificate.txt").write_text(thumbprint)
                    payload = probe(item, install, out, work, fixtures)
                finally:
                    if thumbprint:
                        remove(thumbprint)
                        (Path(args.work) / "temporary-certificate.txt").unlink()
                value = payload["result"]
                if item == "W2":
                    value["detail"]["startup"] = prompts["detail"]
                    if value["status"] == "PASS" and prompts["status"] != "PASS":
                        value["status"] = prompts["status"]
                        value["detail"]["message"] = prompts["detail"]
                results.report["owner_review"].extend(payload["owner_review"])
                results.put(value)
            except Exception as error:
                shot = Path(args.out) / (item + "-failure.png")
                screenshot(shot)
                results.put(row(item, "FAIL", dict(message=f"{type(error).__name__}: {error}"), shot.name))
    except Exception as error:
        results.report["setup_error"] = f"{type(error).__name__}: {error}"
        shot = Path(args.out) / "setup-failure.png"
        try:
            screenshot(shot)
        except Exception:
            pass
        for value in results.report["results"]:
            if value["detail"] == "Chưa chạy: chuẩn bị hoặc tiến trình bị gián đoạn":
                value.update(detail=dict(message=results.report["setup_error"]),
                             screenshot=shot.name if shot.exists() else None)
    finally:
        from artifacts import verify
        verify(args.out, results.report)
        results.save()
    return 0 if gate(results.report["results"]) and "setup_error" not in results.report and "error" not in results.report.get("display", {}) else 1


if __name__ == "__main__":
    raise SystemExit(main())
