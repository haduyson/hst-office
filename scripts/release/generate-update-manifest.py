#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Generate unsigned schema 2 and legacy manifests from release assets and SHA256SUMS.

Local assets are verified against SHA256SUMS. With --gh-tag, hashes come from SHA256SUMS
and sizes from GitHub; GitHub's asset digest is also checked when supplied by gh.
Sign each output separately with sign-update-manifest.py after reviewing it.
"""
import argparse
import datetime
import fnmatch
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "extensions" / "hst-vietnamese-tools" / "python"))
from hst_office import update_logic as logic  # noqa: E402
from hst_office.update_installer import InstallerError, verify_file  # noqa: E402

PATTERNS = {"windows": "*_Win_x86-64_*.msi", "macos-arm": "*_macOS_arm64.dmg",
            "macos-intel": "*_macOS_x86_64.dmg", "linux": "*_Linux_x86-64.deb"}
DEFAULT_SITE = ROOT / "website" / "office.hasontech.vn" / "update"
NOTES = "https://office.hasontech.vn/#tai-ve"


def asset_platform(name):
    for platform, pattern in PATTERNS.items():
        if fnmatch.fnmatchcase(name, pattern):
            return platform
    return None


def read_sums(path):
    hashes = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})  ([A-Za-z0-9._-]+)", line)
        if not match:
            raise ValueError("SHA256SUMS line %s: expected '<sha256>  <filename>'" % number)
        digest, name = match.groups()
        if name in hashes:
            raise ValueError("duplicate checksum: %s" % name)
        hashes[name] = digest.lower()
    return hashes


def asset_metadata(args):
    if args.assets_dir is not None:
        return {path.name: {"size": path.stat().st_size} for path in args.assets_dir.iterdir() if path.is_file()}
    result = subprocess.run(["gh", "release", "view", args.gh_tag, "--repo", "haduyson/hst-office",
                             "--json", "assets"], check=True, capture_output=True, text=True)
    doc = json.loads(result.stdout)
    if not isinstance(doc, dict) or not isinstance(doc.get("assets"), list):
        raise ValueError("gh release view: expected an assets array")
    assets = {}
    for asset in doc["assets"]:
        if not isinstance(asset, dict) or not isinstance(asset.get("name"), str):
            raise ValueError("gh release view: invalid asset")
        name = asset["name"]
        if name in assets:
            raise ValueError("duplicate release asset: %s" % name)
        assets[name] = asset
    return assets


def build_installers(args):
    hashes, assets = read_sums(args.sums), asset_metadata(args)
    installers = {}
    for name in sorted(hashes.keys() | assets.keys()):
        platform = asset_platform(name)
        if platform is None:
            continue
        if name not in hashes:
            raise ValueError("missing sha256 for %s" % name)
        if name not in assets:
            raise ValueError("missing asset for checksum: %s" % name)
        if platform in installers:
            raise ValueError("multiple installers for %s" % platform)
        size = assets[name].get("size")
        if type(size) is not int or not 1 <= size <= 4294967296:
            raise ValueError("invalid installer size for %s" % name)
        entry = {"url": "https://github.com/haduyson/hst-office/releases/download/%s/%s" % (args.tag, name),
                 "sha256": hashes[name], "size": size}
        if args.assets_dir is not None:
            verify_file(args.assets_dir / name, entry)
        elif assets[name].get("digest"):
            if assets[name]["digest"] != "sha256:" + hashes[name]:
                raise ValueError("sha256 mismatch for %s" % name)
        installers[platform] = entry
    if not installers:
        raise ValueError("no installer found (legacy .tar.gz archives are not installers)")
    return installers


def existing_channels(site):
    for name in ("latest-2.json", "latest.json"):
        path = site / name
        if path.exists():
            data = path.read_bytes()
            logic.parse_manifest(data)
            doc = json.loads(data)
            return {channel: doc["channels"].get(channel) for channel in logic.CHANNELS}
    return dict.fromkeys(logic.CHANNELS)


def generate(args):
    version = args.tag[1:] if args.tag.startswith("v") else args.tag
    if version != version.strip():
        raise ValueError("tag must not contain surrounding whitespace")
    logic.version_key(version)
    date = args.date or datetime.date.today().isoformat()
    if datetime.date.fromisoformat(date).isoformat() != date:
        raise ValueError("date must be YYYY-MM-DD")
    channel = args.channel or logic.channel_of(version)
    channels = existing_channels(args.site_dir)
    channels[channel] = {"version": version, "date": date, "notes": args.notes,
                         "downloads": {p: "https://office.hasontech.vn/tai/" + p for p in logic.PLATFORMS},
                         "critical": args.critical, "installers": build_installers(args)}
    legacy = {key: {k: v for k, v in value.items() if k != "installers"} if value is not None else None
              for key, value in channels.items()}
    outputs = []
    for name, schema, releases in (("latest-2.json", 2, channels), ("latest.json", 1, legacy)):
        data = (json.dumps({"schema": schema, "channels": releases}, indent=2) + "\n").encode("utf-8")
        logic.parse_manifest(data)
        if len(data) > logic.MAX_BYTES:
            raise ValueError("generated manifest exceeds client size limit")
        outputs.append((args.site_dir / name, data))
    args.site_dir.mkdir(parents=True, exist_ok=True)
    for path, data in outputs:
        path.write_bytes(data)
    print("Generated unsigned manifests. Next, review and sign both files:")
    for path, _ in outputs:
        print("python3 scripts/release/sign-update-manifest.py %s" % shlex.quote(os.fspath(path)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sums", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--assets-dir", type=Path)
    source.add_argument("--gh-tag")
    parser.add_argument("--date")
    parser.add_argument("--channel", choices=logic.CHANNELS)
    parser.add_argument("--notes", default=NOTES)
    parser.add_argument("--critical", action="store_true")
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE)
    args = parser.parse_args(argv)
    try:
        generate(args)
    except (OSError, ValueError, InstallerError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
