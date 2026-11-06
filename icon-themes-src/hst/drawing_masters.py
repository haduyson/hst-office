# SPDX-License-Identifier: AGPL-3.0-only
"""Write the editable SVG masters of the glyphs drawing.py constructed."""
from html import escape
import json

from drawing import ROOT, GLYPHS


def write(stage):
    selected = json.loads((ROOT/'metadata/families.json').read_text())
    for f in selected:
        if f['stage'] != stage or f.get('skip'):
            continue
        name = f['glyph']
        if name not in GLYPHS:
            raise ValueError('Missing drawing: '+name)
        body, concept = GLYPHS[name]
        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- SPDX-License-Identifier: CC-BY-4.0; Copyright 2026 HASON TECH -->
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <title>HST {escape(name)}</title>
  <desc>{escape(concept)}. Original HST geometry; 24-unit grid.</desc>
  <g fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">
    {body}
  </g>
</svg>
'''
        path=ROOT/'glyphs'/f'stage-{stage}'/(name+'.svg')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(svg)
