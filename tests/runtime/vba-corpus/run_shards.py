# SPDX-License-Identifier: AGPL-3.0-only
"""Run a jobs list in N sandboxes side by side. Usage: run_shards.py IMAGE INSTDIR CORPUS JOBS.json OUT.jsonl [N] [LIMIT_SECONDS]"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    image, instdir, corpus, jobs_path, out = sys.argv[1:6]
    count = int(sys.argv[6]) if len(sys.argv) > 6 else 4
    limit = sys.argv[7] if len(sys.argv) > 7 else "3000"
    with open(jobs_path, encoding="utf-8") as handle:
        jobs = json.load(handle)
    procs = []
    for shard in range(count):
        part = f"{out}.part{shard}"
        with open(part + ".jobs", "w", encoding="utf-8") as handle:
            json.dump(jobs[shard::count], handle)
        procs.append(subprocess.Popen([os.path.join(HERE, "run_sandboxed.sh"), image, instdir, corpus, part + ".jobs", part, limit]))
    for proc in procs:
        proc.wait()
    with open(out, "w", encoding="utf-8") as merged:
        for shard in range(count):
            part = f"{out}.part{shard}"
            if os.path.exists(part):
                with open(part, encoding="utf-8") as handle:
                    merged.write(handle.read())


if __name__ == "__main__":
    main()
