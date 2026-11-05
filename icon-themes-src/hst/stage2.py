# SPDX-License-Identifier: AGPL-3.0-only
"""Explicit, original constructions for the remaining ribbon families.

Every registration names an inventory family. No catch-all icon or random
variation: related actions share a visual noun and a semantic modifier.
"""
from drawing import GLYPHS  # noqa: F401  re-exported for the generator
from stage2_controls import controls_and_view
from stage2_documents import documents
from stage2_shapes import shapes_and_slides
from stage2_tables import tables_and_data


def stage2():
    documents()
    tables_and_data()
    shapes_and_slides()
    controls_and_view()
