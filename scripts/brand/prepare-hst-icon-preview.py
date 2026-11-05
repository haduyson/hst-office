#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Make a disposable copy of an installation and apply the icon/UI resources.

Never edits --installed. The destination must not exist. This does not compile
the C++ selector/fallback patch: use --legacy-binary with the screenshot runner.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--copy", type=Path, required=True)
    args = parser.parse_args()
    source, target = args.installed.resolve(), args.copy.resolve()
    if target.exists() or target.is_relative_to(source):
        parser.error("--copy must be a new directory outside --installed")
    if not (source / "share/config/soffice.cfg").is_dir():
        parser.error("--installed must be the product root containing share/config/soffice.cfg")
    builder = module("hst_icons", "scripts/brand/build-hst-icon-theme.py")
    ui = module("hst_ui", "scripts/patches/generate-ribbon-look.py")
    # Build and validate the replacement resources before the potentially large copy.
    archives = {name: builder.archive(builder.resources(name)) for name in builder.PALETTES}
    edits, provenance = {}, {}
    for _, name in ui.APPS:
        path = f"share/config/soffice.cfg/modules/{name}/ui/notebookbar.ui"
        before = (source / path).read_bytes()
        provenance[path] = hashlib.sha256(before).hexdigest()
        edits[path] = ui.transform(before.decode()).encode()
    path = "share/registry/main.xcd"
    config = (source / path).read_text()
    start = config.index('<prop oor:name="NotebookbarColorTransparency"')
    end = config.index("</prop>", start)
    old = config[start:end]
    if "<value>150</value>" not in old:
        parser.error("Unexpected installed ribbon tint default; inspect before previewing")
    edits[path] = (config[:start] + old.replace("<value>150</value>", "<value>255</value>") + config[end:]).encode()
    shutil.copytree(source, target, symlinks=True)
    for name, data in archives.items():
        (target / f"share/config/images_{name}.zip").write_bytes(data)
    for path, data in edits.items():
        (target / path).write_bytes(data)
    provenance["cpp_selector_rebuilt"] = False
    provenance["source_installation"] = str(source)
    provenance["archives"] = {name: hashlib.sha256(data).hexdigest() for name, data in archives.items()}
    (target / "hst-icon-preview.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
