#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Sign (or verify) the update manifest served at https://office.hasontech.vn/update/latest.json.

  sign-update-manifest.py [MANIFEST]            validate, sign, write MANIFEST.sig, verify with the built-in key
  sign-update-manifest.py --verify [MANIFEST]   only check MANIFEST.sig against the public key in the extension

MANIFEST defaults to website/office.hasontech.vn/update/latest.json. The signature is base64 Ed25519 over the
exact bytes of MANIFEST (detached, one line). The private key is a 32-byte seed in hex, read from --key, else
$HST_UPDATE_SIGNING_KEY_FILE, else /root/.config/hst-office/update-signing-ed25519.key; it must be mode 600
and must never enter the repository. The key itself is never printed, only the public-key fingerprint.
Uses the extension's pure-Python Ed25519 (RFC 8032), so no third-party package is needed. See docs/UPDATE_CHECK.md.
"""
import argparse
import base64
import hashlib
import os
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "extensions", "hst-vietnamese-tools", "python"))
from hst_office import ed25519  # noqa: E402
from hst_office import update_logic as logic  # noqa: E402

DEFAULT_MANIFEST = os.path.join(ROOT, "website", "office.hasontech.vn", "update", "latest.json")
DEFAULT_KEY = "/root/.config/hst-office/update-signing-ed25519.key"


def fingerprint(public):
    return "sha256:" + hashlib.sha256(public).hexdigest()


def load_seed(path):
    mode = os.stat(path).st_mode
    if os.name == "posix" and mode & (stat.S_IRWXG | stat.S_IRWXO):
        sys.exit("refusing %s: permissions must be 600 (chmod 600)" % path)
    text = open(path, encoding="ascii").read().strip()
    try:
        seed = bytes.fromhex(text)
    except ValueError:
        sys.exit("%s: expected 64 hex characters" % path)
    if len(seed) != 32:
        sys.exit("%s: expected a 32-byte Ed25519 seed" % path)
    return seed


def check(manifest_path):
    """Exit status 0 when MANIFEST.sig verifies with the extension's public key and the manifest parses."""
    data = open(manifest_path, "rb").read()
    try:
        signature = base64.b64decode(open(manifest_path + logic.SIGNATURE_SUFFIX, encoding="ascii").read().strip(), validate=True)
    except (OSError, ValueError) as exc:
        print("FAIL %s: no usable signature (%s)" % (manifest_path, exc))
        return 1
    if not ed25519.verify(logic.PUBLIC_KEY, data, signature):
        print("FAIL %s: signature does not verify with %s" % (manifest_path, fingerprint(logic.PUBLIC_KEY)))
        return 1
    try:
        channels = logic.parse_manifest(data)
    except logic.ManifestError as exc:
        print("FAIL %s: %s" % (manifest_path, exc))
        return 1
    summary = ", ".join("%s=%s" % (k, v["version"] if v else "-") for k, v in sorted(channels.items()))
    print("PASS %s signed by %s (%s)" % (os.path.relpath(manifest_path, ROOT), fingerprint(logic.PUBLIC_KEY), summary))
    return 0


def sign(manifest_path, key_path):
    data = open(manifest_path, "rb").read()
    logic.parse_manifest(data)  # refuse to sign a manifest the office would reject
    seed = load_seed(key_path)
    public = ed25519.secret_to_public(seed)
    if public != logic.PUBLIC_KEY:
        sys.exit("key %s (%s) is not the key built into the extension (%s)"
                 % (key_path, fingerprint(public), fingerprint(logic.PUBLIC_KEY)))
    signature = ed25519.sign(seed, data)
    with open(manifest_path + logic.SIGNATURE_SUFFIX, "w", encoding="ascii", newline="\n") as handle:
        handle.write(base64.b64encode(signature).decode("ascii") + "\n")
    return check(manifest_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest", nargs="?", default=DEFAULT_MANIFEST)
    ap.add_argument("--verify", action="store_true", help="only verify the existing signature")
    ap.add_argument("--key", default=os.environ.get("HST_UPDATE_SIGNING_KEY_FILE", DEFAULT_KEY))
    args = ap.parse_args()
    if args.verify:
        return check(args.manifest)
    return sign(args.manifest, args.key)


if __name__ == "__main__":
    sys.exit(main())
