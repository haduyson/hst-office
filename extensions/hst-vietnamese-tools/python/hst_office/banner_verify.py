# SPDX-License-Identifier: AGPL-3.0-only
"""Authenticate exact manifest bytes with the separate banner key, then validate schema."""
import base64
import hashlib

from . import ed25519
from .banner_image import inspect
from .banner_schema import MAX_IMAGE, MAX_MANIFEST, parse_manifest

# TODO(maintainer): set bytes.fromhex(<64 hex digits of the separate BANNER public key>) before release.
# Empty means reject ALL remote/cache manifests, continuing to show bundled defaults.
# NEVER substitute update_logic.PUBLIC_KEY or generate a production private key in this repository.
PUBLIC_KEY = b""


def valid_key(key):
    """Canonical, nonidentity point in the prime-order subgroup, before any cache/network use."""
    if not isinstance(key, bytes) or len(key) != 32:
        return False
    point = ed25519.point_decompress(key)
    identity = (0, 1, 1, 0)
    return bool(point and ed25519.point_compress(point) == key
                and not ed25519.point_equal(point, identity)
                and ed25519.point_equal(ed25519.point_mul(ed25519.q, point), identity))


def verify_manifest(data, signature_text, public_key=None):
    key = PUBLIC_KEY if public_key is None else public_key
    if not valid_key(key) or len(data) > MAX_MANIFEST or len(signature_text) > 128:
        raise ValueError("banner signature unavailable")
    try:
        signature = base64.b64decode(signature_text.strip(), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid banner signature encoding") from exc
    if not ed25519.verify(key, data, signature):
        raise ValueError("invalid banner signature")
    return parse_manifest(data)


def verify_image(data, spec, scale=None):
    """Authenticate this exact immutable buffer and bound static raster dimensions before decoding."""
    if not 0 < len(data) <= MAX_IMAGE or len(data) != spec["size"]:
        raise ValueError("invalid banner image size")
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError("invalid banner image digest")
    return inspect(data, scale)
