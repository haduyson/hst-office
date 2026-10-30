# Brief round 2: HST Office app icons — revise the 3 concepts

Context and hard requirements: `work/icon-concepts/brief-round1.md` (still valid). Round-1 output is in
`work/icon-concepts/concept-{1,2,3}/`; review sheets (256/48/16 px, light+dark, taskbar, dock) are
`work/icon-concepts/concept-{1,2,3}.png` — look at them first. Before editing, copy each concept's current
SVGs to `concept-N/round1/` (keep them). Then overwrite `concept-N/*.svg` with the round-2 versions.
Regenerate sheets yourself with: `.venv/bin/python work/icon-concepts/make-preview-sheet.py work/icon-concepts/concept-N work/icon-concepts/concept-N.png "Concept N — round 2"` and inspect them.

## Family-wide fixes
- **Math**: the √ reads as a checkmark. Draw a real radical: short rising tick, long downstroke, rising
  stroke, horizontal vinculum, and a small solid square/“x-box” sitting under the vinculum. Must still read at 16 px.
- Keep every glyph big (≥ 55% of the body width) and bold.

## Concept 1 — Tile (keep, strengthen identity)
- Good: silhouette, colours, 16 px legibility. Keep them.
- Problem: the white corner triangle is generic; HST identity is lost on module icons. Replace it with a small
  **simplified HST mark** (the triangle with its white S/H channel cut, from `hst-mark.svg`, simplified to the
  1–2 main channels so it survives at 48 px), white, ~20–22% of tile width, same position on every module
  (top-right inside the tile). Make sure the glyph does not collide with it.

## Concept 2 — Folded document (rework)
- Problem: white paper top is invisible on light backgrounds; the mini mark becomes noise at 16 px; reads as
  a label more than a document. Also avoid the LibreOffice look (white page + coloured folded corner).
- New direction: a **full-colour portrait page** (aspect ≈ 0.78, generous corner radius ~ 7% of width,
  module-colour gradient body) whose **top-right corner is folded**: the dog-ear flap is a lighter tint of the
  module colour and its cut edge forms a crisp triangle echoing the HST triangle. Large white glyph centred
  slightly below middle. Subtle soft shadow so the page reads on light and dark. Main: brand-blue page with
  the white HST mark. This must look clearly different from concept 1 (portrait page + fold vs square tile).

## Concept 3 — Triangle-born (refine)
- Good: most distinctive, strongly on-brand. Keep the triangle silhouette.
- Problems: (a) the amber/yellow triangle with a dark glyph reads as a **road warning sign** — no dark glyph,
  use white glyph on a deeper amber/gold gradient (e.g. `#E39B00`→`#C77700`), and soften all three corners with
  a larger radius (~ 9–10% of the side) so the family feels like friendly pebbles, not signage; (b) glyph area
  too small at 16 px — enlarge the triangle to the full 1024 width (minus ~40 px margin) and push glyphs
  lower and larger; (c) make the HST channel visible: one clear white/lighter diagonal channel cut (the S-cut
  language of the mark) across the upper part of every module triangle, same position across the family,
  thick enough to see at 48 px. Main stays the HST mark, polished.

Only write under `work/icon-concepts/`. Finish with a short summary of what changed per concept.
