# SPDX-License-Identifier: AGPL-3.0-only
"""Standard banner sizes ("sizes" field of a version 1 banner manifest item).

The banner is never stretched: a campaign submits one fixed artwork per standard width, at 1x and 2x, and the
client shows the largest standard width that fits the free ribbon space (never below 360 px, never above 960 px).
The left SAFE_ZONE px of every size carry the logo and the main message, so the narrowest size loses nothing.

Item shape (schemaVersion stays 1; clients before 1.0.3 ignore the unknown field and keep using "image"):

    "sizes": [
      {"width": 360, "height": 96, "1x": {"url", "sha256", "size"}, "2x": {"url", "sha256", "size"}},
      {"width": 640, ...}, {"width": 960, ...}
    ]

All standard widths are required exactly once, in ascending order; images are PNG or JPEG, at most 300 KB each,
with exact pixel dimensions width x height x scale. "image" (and "imageCompact") stay required/optional as before,
so one manifest serves 1.0.2 and later clients.
"""
import re

SIZES_FIELD = "sizes"
HEIGHT = 96
WIDTHS = (360, 640, 960)
SCALES = ("1x", "2x")
SAFE_ZONE = 360
MAX_IMAGE = 300 * 1024  # bytes, same limit as every other banner image
IMAGE_TYPES = (".png", ".jpg")  # banner_image.inspect suffixes accepted for standard sizes (no WebP)
_ONLINE_PATH = re.compile(r"[^?#]*\.(?:png|jpe?g)", re.I)
BUNDLED_PATH = r"banners/[a-z0-9-]+-(?:360|640|960)x96@[12]x\.(?:png|jpg)"


def _require(condition):
    if not condition:
        raise ValueError("invalid banner sizes")


def size_key(width, scale):
    """Image key of one standard-size artwork, e.g. "640@2x" (distinct from the 1x..3x and c1x..c3x keys)."""
    return "%d@%s" % (width, scale)


def pixel_size(key):
    """Exact pixel (width, height) of a size_key, or None when `key` is not a standard-size key."""
    match = re.fullmatch(r"(\d+)@([12])x", key or "")
    if not match or int(match.group(1)) not in WIDTHS:
        return None
    factor = int(match.group(2))
    return int(match.group(1)) * factor, HEIGHT * factor


def validate(item, check_image):
    """Check item["sizes"] when present. `check_image(descriptor)` validates url/sha256/size like "image" does."""
    if SIZES_FIELD not in item:
        return
    sizes = item[SIZES_FIELD]
    _require(isinstance(sizes, list) and len(sizes) == len(WIDTHS))
    for entry, width in zip(sizes, WIDTHS):
        _require(isinstance(entry, dict) and set(entry) == {"width", "height"} | set(SCALES))
        _require(type(entry["width"]) is int and entry["width"] == width)
        _require(type(entry["height"]) is int and entry["height"] == HEIGHT)
        for scale in SCALES:
            descriptor = entry[scale]
            check_image(descriptor)
            _require(descriptor["size"] <= MAX_IMAGE)


def url_allowed(url, bundled):
    """Extra locator rule for standard sizes: PNG/JPEG file names (the bytes are checked separately)."""
    if not isinstance(url, str):
        return False
    return bool(re.fullmatch(BUNDLED_PATH, url) if bundled else _ONLINE_PATH.fullmatch(url))


def has_sizes(item):
    return isinstance(item.get(SIZES_FIELD), list)


def size_specs(item):
    """(key, descriptor) of every standard-size image of a validated item, narrowest first; [] without sizes.

    Kept apart from banner_schema.image_specs so clients that do not show standard sizes never download them."""
    if not has_sizes(item):
        return []
    return [(size_key(entry["width"], scale), entry[scale]) for entry in item[SIZES_FIELD] for scale in SCALES]


def fit_width(available):
    """The standard width shown in `available` logical px: the largest that fits, at least the narrowest one.

    The ribbon guarantees SAFE_ZONE px (groups collapse first), so a smaller value still yields 360."""
    fitting = [w for w in WIDTHS if w <= available]
    return fitting[-1] if fitting else WIDTHS[0]
