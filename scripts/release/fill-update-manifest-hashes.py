#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Fill a reviewed update-feed draft with the hashes and sizes of the installers that were actually built.

A draft directory (docs/releases/v<release>-update-draft/) holds latest-3.json, latest-2.json and latest.json as they
will be published, except that every stable installer has "sha256": "CHUA-DUNG" and "size": 0. Once the installers
exist, gather them in one directory and run:

  fill-update-manifest-hashes.py --draft docs/releases/v1.0.2-update-draft --assets-dir <installers> --out <dir>

The script requires one installer per platform listed in the draft, writes <out>/SHA256SUMS (cross-checked against a
SHA256SUMS already in the assets directory, if any), then runs generate-update-manifest.py on a copy of the published
feeds (website/office.hasontech.vn/update) and refuses the result unless it equals the draft apart from the filled
sha256/size values. Nothing under website/ is modified; sign the files in <out>/site with sign-update-manifest.py.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "release" / "generate-update-manifest.py"
PUBLISHED = ROOT / "website" / "office.hasontech.vn" / "update"
FEEDS = ("latest-3.json", "latest-2.json", "latest.json")
PLACEHOLDER = "CHUA-DUNG"


class FillError(Exception):
    pass


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FillError("cannot read %s: %s" % (path, exc)) from exc


def stable(doc, path):
    release = doc.get("channels", {}).get("stable")
    if not isinstance(release, dict) or not isinstance(release.get("version"), str):
        raise FillError("%s: no stable release" % path)
    return release


def draft_installers(draft_dir):
    """{file name: platform} of every installer in the drafts, checking they all still carry the placeholder."""
    names, version = {}, None
    for name in FEEDS:
        path = draft_dir / name
        if not path.exists():
            continue
        release = stable(load(path), path)
        if version not in (None, release["version"]):
            raise FillError("drafts disagree on the version: %s and %s" % (version, release["version"]))
        version = release["version"]
        for platform, entry in release.get("installers", {}).items():
            if entry.get("sha256") != PLACEHOLDER or entry.get("size") != 0:
                raise FillError("%s: %s is not a placeholder entry" % (path, platform))
            names[entry["url"].rsplit("/", 1)[-1]] = platform
    if version is None or not names:
        raise FillError("%s: no draft installers" % draft_dir)
    return version, names


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sums(assets_dir, names, out_dir, existing):
    missing = sorted(n for n in names if not (assets_dir / n).is_file())
    if missing:
        raise FillError("missing installers: " + ", ".join(missing))
    sums = {name: sha256_of(assets_dir / name) for name in sorted(names)}
    if existing.exists():
        for line in existing.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("*") in sums and parts[0].lower() != sums[parts[1].lstrip("*")]:
                raise FillError("%s: %s differs from the file" % (existing, parts[1]))
    path = out_dir / "SHA256SUMS"
    path.write_text("".join("%s  %s\n" % (digest, name) for name, digest in sums.items()), encoding="utf-8")
    return path


def blank(doc):
    """The document with stable installer hashes/sizes replaced by the placeholder, for comparison with the draft."""
    doc = copy.deepcopy(doc)
    for entry in doc["channels"]["stable"].get("installers", {}).values():
        entry["sha256"], entry["size"] = PLACEHOLDER, 0
    return doc


def fill(draft_dir, assets_dir, out_dir, published=PUBLISHED):
    version, names = draft_installers(draft_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stage = out_dir / "assets"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    for name in names:  # the generator reads every file of the directory: give it the installers only
        target = stage / name
        try:
            target.hardlink_to(assets_dir / name)
        except OSError:
            if not (assets_dir / name).is_file():
                raise FillError("missing installer: %s" % name)
            shutil.copyfile(assets_dir / name, target)
    sums = write_sums(stage, names, out_dir, assets_dir / "SHA256SUMS")
    site = out_dir / "site"
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()
    for name in FEEDS:
        if (published / name).exists():
            shutil.copyfile(published / name, site / name)
    release = stable(load(draft_dir / "latest-2.json"), draft_dir / "latest-2.json")
    command = [sys.executable, "-I", str(GENERATOR), "--tag", "v" + version, "--sums", str(sums),
               "--assets-dir", str(stage), "--site-dir", str(site), "--date", release["date"],
               "--notes", release["notes"]] + (["--critical"] if release.get("critical") else [])
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise FillError("generate-update-manifest.py failed: " + (result.stderr or result.stdout).strip())
    for name in FEEDS:
        draft, generated = draft_dir / name, site / name
        if draft.exists() != generated.exists():
            raise FillError("%s: present in only one of draft and generated output" % name)
        if draft.exists() and blank(load(generated)) != load(draft):
            raise FillError("%s: generated feed differs from the reviewed draft beyond hashes and sizes" % name)
    return [site / name for name in FEEDS if (site / name).exists()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--draft", type=Path, required=True, help="directory with the reviewed draft feeds")
    parser.add_argument("--assets-dir", type=Path, required=True, help="directory with the built installers")
    parser.add_argument("--out", type=Path, required=True, help="output directory (SHA256SUMS, site/*.json)")
    args = parser.parse_args(argv)
    try:
        outputs = fill(args.draft, args.assets_dir, args.out)
    except (FillError, OSError) as exc:
        parser.error(str(exc))
    print("Filled feeds match the draft. Review, then sign each file:")
    for path in outputs:
        print("python3 scripts/release/sign-update-manifest.py %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
