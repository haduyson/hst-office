# SPDX-License-Identifier: AGPL-3.0-only
"""Authenticate exact manifest bytes with the separate banner key, then validate schema."""
import base64
import hashlib

from . import ed25519
from .banner_schema import MAX_IMAGE, MAX_MANIFEST, parse_manifest

# TODO(maintainer): set bytes.fromhex(<64 hex digits of the separate BANNER public key>) before release.
# Empty means reject ALL remote/cache manifests, continuing to show bundled defaults.
# NEVER substitute update_logic.PUBLIC_KEY or generate a production private key in this repository.
PUBLIC_KEY = b""


def verify_manifest(data, signature_text, public_key=None):
    key = PUBLIC_KEY if public_key is None else public_key
    if len(key) != 32 or len(data) > MAX_MANIFEST or len(signature_text) > 128:
        raise ValueError("banner signature unavailable")
    try:
        signature = base64.b64decode(signature_text.strip(), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid banner signature encoding") from exc
    if not ed25519.verify(key, data, signature):
        raise ValueError("invalid banner signature")
    return parse_manifest(data)


def verify_image(data, spec):
    """Return safe extension only after byte count, digest and PNG/JPEG/WebP magic checks."""
    if not 0 < len(data) <= MAX_IMAGE or len(data) != spec["size"]:
        raise ValueError("invalid banner image size")
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError("invalid banner image digest")
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 33 and data[12:16] == b"IHDR":
        return ".png"
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return ".jpg"
    if (len(data) >= 20 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
            and data[12:16] in (b"VP8 ", b"VP8L", b"VP8X") and int.from_bytes(data[4:8], "little") == len(data) - 8):
        return ".webp"
    raise ValueError("invalid banner image type")
