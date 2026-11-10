#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""One bounded item in bundled Python; controller owns timeout and final aggregation."""
import argparse
import json
import os
from pathlib import Path
import sys
from support import Evidence
from results import row
from office import Office

A11Y = {"W7", "W8", "W9", "W10", "M4", "M5", "M7"}  # accessibility reads: ribbon, glyph bounds (office.py)


def execute(e, fixtures):
    item = e.item
    if item in {"W5", "W7", "M5", "M6"}:
        import nd30
        nd30.run(e)
    elif item in {"W8", "W9", "W10", "M7"}:
        import ribbon
        ribbon.run(e)
    elif item in {"W12", "W13", "M8"}:
        import pdf_checks
        pdf_checks.run(e, fixtures)
    elif item == "W14":
        import permission_check
        permission_check.run(e, fixtures)
    elif item == "M4":
        import appearance
        appearance.run(e)
    else:
        import documents
        if item in {"W3", "M3"}:
            documents.shell_open(e, ["docx"] if item == "W3" else ["docx", "xlsx", "pptx"])
        elif item == "W4":
            documents.cycle(e)
        elif item == "W2":
            documents.about(e)
        elif item == "W15":
            documents.duplex(e)
        else:
            raise ValueError("Mục chưa có trình kiểm tra: " + item)
    if item in {"M4", "W7"}:
        e.require(os.environ.get("R1_SCALE_READY") == "1", "Ảnh phải chụp ở tỉ lệ màn hình yêu cầu",
                  scale=os.environ.get("R1_SCALE_DETAIL", ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("item", "install", "out", "work", "result", "fixtures"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.item in A11Y:
        os.environ["R1_A11Y"] = "1"
    office = Office(args.install, args.work)
    e = Evidence(args.item, args.out, office)
    status, message = "FAIL", "Chưa chạy"
    try:
        office.start()
        execute(e, args.fixtures)
        failed = [c["message"] for c in e.checks if not c["ok"]]
        if failed:  # recorded without raising (e.g. the office died on close): still a failure
            raise AssertionError("; ".join(failed))
        status = "SKIP" if args.item == "M4" else "PASS"
        message = "Chủ sở hữu duyệt độ sắc nét; kiểm tra trang tùy chọn đã đạt" if args.item == "M4" else "Đạt các phép đo tự động"
    except Exception as error:
        import traceback
        message = f"{type(error).__name__}: {error}"
        e.checks.append(dict(ok=False, message="traceback", where=traceback.format_exc().splitlines()[-6:]))
        try:
            from access import census
            e.checks.append(dict(ok=False, message="accessibility census", top_windows=census(office)))
        except Exception:
            pass
        if args.item in A11Y:  # the OS tree the ribbon checks must be rewritten against
            try:
                from support import native
                (e.out / "os-a11y.log").write_text(json.dumps(native("tree", "diagnose"), ensure_ascii=False,
                                                                default=str), encoding="utf-8")
                (e.out / "native-tree.log").write_text(json.dumps(native("tree", 2500), ensure_ascii=False),
                                                       encoding="utf-8")
            except Exception as dump_error:
                e.checks.append(dict(ok=False, message="native tree", error=f"{type(dump_error).__name__}: {dump_error}"))
        try:
            e.shot("failure")
        except Exception:
            pass
    finally:
        detail = e.detail(message)
        try:
            office.stop()
        except Exception as error:
            status = "FAIL"
            detail["cleanup_error"] = f"{type(error).__name__}: {error} {getattr(error, 'stderr', '') or ''}"[-600:]
        payload = dict(result=row(args.item, status, detail, e.shots[-1] if e.shots else None), owner_review=e.owner)
        Path(args.result).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return int(status == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
