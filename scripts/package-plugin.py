"""Write a deterministic ONLYOFFICE .plugin (ZIP) from a staging directory.

Usage: python3 scripts/package-plugin.py <staging-dir> <out.plugin>

config.json sits at the archive root; entries are sorted, timestamps fixed at
1980-01-01, permissions 0644, no directories/symlinks/'..' entries, so the
same inputs always yield byte-identical archives.
"""
import os
import sys
import zipfile

FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def collect(stage):
    files = []
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames.sort()
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            if os.path.islink(abs_path):
                raise SystemExit(f"Refusing symlink in package: {abs_path}")
            rel = os.path.relpath(abs_path, stage).replace(os.sep, "/")
            if rel.startswith("../") or "/../" in rel:
                raise SystemExit(f"Unsafe path: {rel}")
            files.append(rel)
    return sorted(files)


def main(stage, out_file):
    files = collect(stage)
    if "config.json" not in files:
        raise SystemExit("config.json missing at package root")
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    tmp = out_file + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel in files:
            info = zipfile.ZipInfo(rel, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            with open(os.path.join(stage, rel), "rb") as handle:
                archive.writestr(info, handle.read(), compresslevel=9)
    os.replace(tmp, out_file)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
