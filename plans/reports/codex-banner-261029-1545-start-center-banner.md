# HST Office Start Center banner

Status: DONE. The image deliverable is complete; live Start Center integration remains UNVERIFIED by this task.

## Delivered files

- [Banner](../../branding/libreoffice/hst-banner.png): 1280×160 RGBA, displayed at 640×80 logical pixels.
- [Light preview](../../branding/libreoffice/hst-banner-preview-light.png) and [dark preview](../../branding/libreoffice/hst-banner-preview-dark.png): 640×80 RGBA, fully composited on `#FFFFFF` and `#1E1E1E`.
- [Renderer](../../scripts/brand/start_center_banner.py) and [generator](../../scripts/generate-brand-assets.py): deterministic Pillow rendering, with only two wiring lines added to the existing generator.
- [Brand specification](../../assets/brand/brand-spec.json): exact copy, output paths, palette, font paths, SHA-256 pins and license provenance in `startCenterBanner`.
- [Tests](../../tests/brand/test-brand-assets.py): six banner tests added. [Brand documentation](../../docs/BRAND.md): purpose, dimensions, previews and regeneration commands.

## Design rationale and visual review

The original HS mark anchors the left edge. The exact headline emphasizes HASON TECH in brand blue; six quiet, pale labels keep the solution names distinct. A blue CTA completes the strip. The opaque white rounded card protects contrast in both desktop themes. No gradients, extra slogans, invented claims or replacement logo artwork were introduced.

Three renders were opened and visually inspected, with two refinements after the initial design. First, the headline grew from 15 to 16 logical pixels and the labels from 11 to 12, with tighter label padding. Second, the pale CTA became a solid blue button and the redundant divider was removed. The final 1280 px image and both 640 px previews were opened: all accents, names and the arrow are legible and unclipped.

Liberation Sans Regular/Bold provides all requested glyphs under SIL OFL 1.1. The installed Noto Sans lacks `→`, so it was rejected before rendering. Font files are hash-checked at runtime and are not redistributed. The HS mark is resized once from 269×233 to 90×78 without redrawing or recoloring.

## Validation

All commands ran from `/home/office`, using the project venv for Pillow.

| Command or check | Result |
|---|---|
| `fc-list :lang=vi file family style`; `fc-query --format=%{charset}` for candidate fonts | Liberation covers every requested character; Noto Sans lacks the arrow. |
| `dpkg-query -W fonts-liberation`; `sha256sum` of both selected fonts; local package copyright inspection | Version `1:2.1.5-3`, pinned hashes match, SIL OFL 1.1 recorded. |
| Inline Python calling `build_start_center_banner` and writing only its three outputs | Three design passes generated successfully. |
| `.venv/bin/python tests/brand/test-brand-assets.py -k banner` | PASS: 6 tests. |
| `.venv/bin/python scripts/generate-brand-assets.py --check` | PASS: 54 files, including all three banner images. |
| `.venv/bin/python tests/brand/test-brand-assets.py` | PASS: 15 tests. Existing non-banner tests emit unclosed-file `ResourceWarning`s. |
| `.venv/bin/python tests/brand/test-check-branding.py` | PASS: 10 tests. |
| `git diff --check`; inline line-count, NFC and documentation-link checks | PASS. Authored code/config files remain below 200 lines. |
| Inline PNG chunk inspection and repeated-render byte comparisons | PASS: only IHDR/IDAT/IEND chunks; no timestamps; byte-identical output. |

Final banner SHA-256: `c2684db24fd325d5e4444cd126add693f0fad266d735101d52f66adc544b10eb` (59,121 bytes).

No upstream source edits, commits, branches, heavy builds, GUI sessions or background processes were started. Other contributors' workspace changes were left intact.

## Integration handoff

The coordinator should consume `branding/libreoffice/hst-banner.png` at 640×80 logical pixels. Display on every launch and CTA click behavior are UNVERIFIED here and belong to the Start Center integration/runtime checks. There are no unresolved image-design questions.
