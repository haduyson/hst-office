# SPDX-License-Identifier: AGPL-3.0-only
"""VBA language and object-model regressions, in real VBA projects run in the disposable sandbox.

Usage: check-vba-corpus-regression.py [--instdir upstream/libreoffice/instdir] [--image hst-vba-sandbox:1] [--work DIR]
Needs Docker and the image built from tests/runtime/vba-corpus/sandbox. Builds the fixtures (language_cases.py, regression_cases.py,
make_vietnamese_fixtures.py), runs them with no network, not as root, on a read-only mount; every case must return OK. Exit 1 on a failure.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vba-corpus")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def run_group(args, work, name, maker):
    corpus = os.path.join(work, name)
    jobs = os.path.join(work, name + ".json")
    subprocess.run([sys.executable, "-I", os.path.join(HERE, maker), corpus, jobs], check=True, timeout=120)
    out = os.path.join(work, name + ".jsonl")
    subprocess.run([os.path.join(HERE, "run_sandboxed.sh"), args.image, args.instdir, corpus, jobs, out, "900"], check=True, timeout=960)
    with open(jobs, encoding="utf-8") as handle:
        wanted = sum(len(job["only"]) for job in json.load(handle))
    passed, failed = 0, []
    with open(out, encoding="utf-8") as handle:
        for line in handle:
            result = json.loads(line[4:])
            if result["event"] == "proc":
                if result["status"] == "pass":
                    passed += 1
                else:
                    failed.append(f"{result['file']} {result['module']}.{result['proc']}: {result['status']} {str(result.get('return', result.get('detail')))[:200]}")
    return passed, wanted, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--instdir", default=os.path.join(ROOT, "upstream/libreoffice/instdir"))
    parser.add_argument("--image", default="hst-vba-sandbox:1")
    parser.add_argument("--work")
    args = parser.parse_args()
    work = args.work or tempfile.mkdtemp(prefix="hst-vba-regression-")
    os.makedirs(work, exist_ok=True)
    total_failed = []
    for name, maker in (("regression", "make_regression_fixtures.py"), ("vietnamese", "make_vietnamese_fixtures.py")):
        passed, wanted, failed = run_group(args, work, name, maker)
        print(f"{name}: {passed}/{wanted}")
        total_failed += failed
        if passed + len(failed) != wanted:
            total_failed.append(f"{name}: {wanted - passed - len(failed)} cases gave no result")
    for line in total_failed:
        print("FAIL", line)
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
