#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Reject a run that did not successfully build the requested desktop artifact."""
import json
import os
import sys
from pathlib import Path

source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = ".github/workflows/desktop-" + sys.argv[2] + ".yml"
if source.get("path") != expected or source.get("conclusion") != "success" or source.get("status") != "completed":
    raise SystemExit("Bản dựng không đúng workflow hoặc chưa thành công")
if source.get("repository", {}).get("full_name") != os.environ["GITHUB_REPOSITORY"]:
    raise SystemExit("Bản dựng thuộc kho khác")
safe = {key: source[key] for key in ("id", "path", "head_sha", "status", "conclusion")}
Path(sys.argv[1]).write_text(json.dumps(safe, indent=2), encoding="utf-8")
print("Đã xác nhận nguồn bản dựng: " + str(source["id"]))
