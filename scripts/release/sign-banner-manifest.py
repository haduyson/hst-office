#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Sign exact banner manifest bytes using an explicitly supplied separate Ed25519 seed (hex, mode 600)."""
import argparse
import base64
import hashlib
from pathlib import Path
import os
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "extensions/hst-vietnamese-tools/python"))
from hst_office import banner_verify, ed25519, update_logic  # noqa: E402
from hst_office.banner_schema import parse_manifest  # noqa: E402


def sign(path, key_path):
    data = Path(path).read_bytes()
    parse_manifest(data)  # online URLs only; bundled defaults are trusted through the installed package
    if len(banner_verify.PUBLIC_KEY) != 32:
        raise ValueError("set the separate banner PUBLIC_KEY in banner_verify.py before signing")
    mode = Path(key_path).stat().st_mode
    if os.name == "posix" and mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError("private key must have mode 600")
    seed = bytes.fromhex(Path(key_path).read_text(encoding="ascii").strip())
    if len(seed) != 32:
        raise ValueError("expected a 32-byte hex Ed25519 seed")
    public = ed25519.secret_to_public(seed)
    if public == update_logic.PUBLIC_KEY:
        raise ValueError("the update key must never sign banners")
    if public != banner_verify.PUBLIC_KEY:
        raise ValueError("key does not match the embedded banner public key")
    signature = base64.b64encode(ed25519.sign(seed, data)) + b"\n"
    banner_verify.verify_manifest(data, signature)
    Path(str(path) + ".sig").write_bytes(signature)
    print("Signed banner manifest; public fingerprint sha256:" + hashlib.sha256(public).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--key", type=Path, help="required when signing; no default and no environment fallback")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify:
            banner_verify.verify_manifest(args.manifest.read_bytes(), Path(str(args.manifest) + ".sig").read_bytes())
            print("Verified banner manifest")
        elif args.key is None:
            parser.error("--key is required when signing")
        else:
            sign(args.manifest, args.key)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
