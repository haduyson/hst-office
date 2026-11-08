#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Local syntax, YAML, authored length and available shell/action lint checks."""
import ast
from pathlib import Path
import shutil
import subprocess
import yaml

root = Path(__file__).resolve().parents[3]
python_files = list((root / "tests/runtime/r1auto").glob("*.py")) + list((root / "tests/unit").glob("test_r1_auto*.py"))
workflows = list((root / ".github/workflows").glob("r1-auto-*.yml"))
other = [root / "docs/r1-auto.md", root / "REPORT-c22.md"]
for path in python_files + workflows + [p for p in other if p.exists()]:
    text = path.read_text(encoding="utf-8")
    if text.count("\n") + 1 > 199:
        raise SystemExit("Tệp quá giới hạn dòng: " + str(path.relative_to(root)))
    if path.suffix == ".py":
        ast.parse(text, filename=str(path))
print(f"Cú pháp và giới hạn dòng: đạt ({len(python_files)} tệp Python)")
for path in workflows:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if shutil.which("shellcheck"):
        for step in data["jobs"]["r1"]["steps"]:
            if "run" in step:
                subprocess.run(["shellcheck", "--shell=bash", "-"], input=step["run"], text=True, check=True)
print("YAML và shellcheck: đạt" if shutil.which("shellcheck") else "YAML: đạt; chưa cài shellcheck")
if shutil.which("actionlint"):
    subprocess.run(["actionlint", *map(str, workflows)], check=True, cwd=root)
else:
    print("Chưa cài actionlint")
