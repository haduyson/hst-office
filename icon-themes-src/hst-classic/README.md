# Cổ điển: Colibre icons redrawn by HST

The Cổ điển style (`hst_classic`, `hst_classic_dark`) is LibreOffice's Colibre with HST glyphs on top
(`scripts/brand/hst_classic_icons.py`). The files here replace a Colibre icon that Colibre does draw,
for every request that resolves to it (Colibre's own `links.txt` aliases included).

| Files | Commands | Why |
|---|---|---|
| `{light,dark}/cmd/sc_resetattributes.svg`, `lc_`, `32/` | `.uno:ResetAttributes`, `.uno:SetDefault` (Xóa định dạng / Xóa định dạng trực tiếp) | The eraser is white, not red: white reads as "wiped clean" (owner, 21/11/2026). |

They are generated, not hand-edited: `python3 scripts/brand/draw-hst-classic-eraser.py --tree <LibreOffice tree>`
(`--check` fails when they are stale, e.g. after a Colibre update). The letter A and the baseline are
Colibre's paths (CC0 1.0); the eraser is HST geometry (CC-BY-4.0, `../hst/LICENSE-CC-BY-4.0.txt`).
