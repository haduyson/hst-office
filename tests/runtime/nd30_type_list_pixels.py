# SPDX-License-Identifier: AGPL-3.0-only
"""Pixel judgement of check-nd30-type-list.py: is the open "Loại văn bản" list visible in a band of a screenshot?

The list shows its rows' text there; a field painted over the list is an empty white box, so almost every pixel row of
the band has one colour. Every image is judged on its own against a fixed limit: a band that is already covered before
the pointer moves fails too, it never relaxes the limit for the next image."""

MAX_FLAT_SHARE = 0.8  # measured (gtk3): list visible 0.00-0.62 (a band holding one short row); empty field over it 0.90


def crop(path, box):
    from PIL import Image
    with Image.open(path) as image:
        return image.convert("RGB").crop(box).tobytes()


def flat_share(path, box):
    """Share of the pixel rows inside `box` that have one colour only."""
    from PIL import Image
    with Image.open(path) as image:
        band = image.convert("RGB").crop(box)
    width, height = band.size
    pixels = band.load()
    flat = sum(1 for y in range(height) if len({pixels[x, y] for x in range(width)}) == 1)
    return flat / float(height or 1)


def list_visible(path, box):
    return flat_share(path, box) <= MAX_FLAT_SHARE


def unchanged(path_a, path_b, box):
    """True when the band is pixel-identical in both screenshots (nothing painted over the list in between)."""
    return crop(path_a, box) == crop(path_b, box)


def visibility_problems(shots, box):
    """Names of the screenshots ({name: path}) in which the list is not visible inside `box`."""
    return [name for name, path in shots.items() if not list_visible(path, box)]
