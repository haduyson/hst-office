# Brief: HST Office application icons — 3 concept families (round 1)

You are the icon designer for **HST Office**, a Vietnamese office suite by HASON TECH (engine: LibreOffice).
We need the default *application* icons (desktop shortcut, Start menu, taskbar, Linux launcher, macOS Dock).
They replace the LibreOffice app icons. The current icons are just the HST logo with a small coloured
badge (see `work/icon-concepts/current-icons.png`) — the owner rejects that: he wants **real app icons**.

## Brand
- Mark: `assets/brand/hst-office-mark.png` (269×233, colour `#0072BB`) — an equilateral-ish triangle whose
  interior is cut into an "S" (top) and "H" (bottom-left) by white channels. Full logo with wordmark:
  `assets/brand/hst-office-logo.png`. Do NOT alter the mark's proportions when you use it whole.
- Brand blue `#0072BB`; text dark `#322E2E`.

## Step 0 — vector mark (do this first, all concepts depend on it)
Write `work/icon-concepts/hst-mark.svg`: a faithful vector reconstruction of the mark (single colour,
`fill="#0072BB"`, clean straight-edged polygons, viewBox matching the PNG 0 0 269 233). Verify it: render with
`rsvg-convert -w 269 -h 233` and compare the alpha mask with the PNG (Python + Pillow); intersection-over-union
must be ≥ 0.97. Print the IoU. Iterate until it passes.

## Step 1 — mood references (image generation)
Use your image generation tool to create one 1024×1024 reference board per concept (four icons side by side:
main, Văn bản/Writer, Bảng tính/Calc, Trình chiếu/Impress) to explore the look. Copy each generated image to
`work/icon-concepts/concept-N/reference.png`. These are references only; the deliverables are SVG.

## Step 2 — the deliverables: 3 distinct concept families as hand-written SVG
For each N in 1,2,3 write into `work/icon-concepts/concept-N/`:
`main.svg, writer.svg, calc.svg, impress.svg, draw.svg, math.svg, base.svg` (viewBox `0 0 1024 1024`,
transparent outside the silhouette) plus `NOTES.md` (3–5 lines: idea, palette hex values, construction grid).

Concept directions (keep them clearly different from each other):
1. **Tile** — a rounded-square (macOS-style squircle, ~ 824 px body centred with margins for shadow) filled
   with the module colour (subtle top-to-bottom gradient allowed). A large, bold white module glyph in the
   centre. HST identity: the triangle silhouette is integrated in the glyph or as a crisp white triangle
   emblem/corner cut — consistent position across the family. Main icon: brand-blue tile with the white HST mark.
2. **Folded document** — a portrait document/sheet silhouette (white or very light paper) whose folded
   top-right corner is a small HST triangle in the module colour; a solid module-colour band or block carries
   the glyph. Main icon: stack of sheets or paper with the full HST mark.
3. **Triangle-born** — the family silhouette derives from the HST triangle itself (rounded-corner triangle or
   triangle on a rounded tile), with the mark's diagonal channel language reused. Each module = the same
   construction re-coloured, the glyph sitting inside the triangle. Main = the HST mark in a polished
   multi-tone blue rendering.

Module colours (use these hues, choose tones that work for white glyphs and at 16 px):
Writer blue (~`#2F5BD3`), Calc green (~`#1E8E3E`), Impress orange/red (~`#E8590C`), Draw amber/yellow
(~`#F2A900`, glyph may be dark), Math teal/grey (~`#0F8A8A` or slate), Base purple (~`#7B3FC4`), Main brand blue `#0072BB`.
Module glyphs: Writer = text lines (paragraph), Calc = grid / table cells, Impress = presentation screen or
slide with a chart/play, Draw = shapes (circle+triangle / pen curve), Math = √ or Σ, Base = database cylinder or
table rows. No letters of words; no text at all except possibly a single glyph.

## Hard requirements
- Modern desktop app-icon style (Fluent / macOS Big Sur quality), consistent family silhouette.
- Must read at **16 px**: bold shapes, big glyph, no hairlines (min stroke ~ 1024/16 = 64 units for anything
  that must survive at 16 px; fine detail may vanish but the silhouette + colour + glyph must stay).
- Beautiful at 256/512/1024 px: gentle gradients, subtle inner highlight or soft shadow are fine (SVG
  `linearGradient`, `filter` with feGaussianBlur only if rsvg renders it correctly — check).
- Works on light AND dark backgrounds (use a slight border/shadow or a light paper with outline if needed).
- No look-alikes of LibreOffice (document with coloured corner tab), Microsoft Office (letter on a square
  overlapping a document), Google Workspace or WPS. No third-party marks. No embedded raster images in SVG.
- Plain SVG 1.1 that renders correctly in `rsvg-convert` (no CSS variables, no text elements, no external refs).

## Self-check before finishing
Render every SVG with `rsvg-convert -w 256` and `-w 16` into `work/icon-concepts/concept-N/render/` and
look at them. Fix anything that is muddy at 16 px or broken. Only write files under `work/icon-concepts/`.
Finish with a short summary listing the files you wrote and the IoU of the mark.
