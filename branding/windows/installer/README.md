# Windows installer artwork

| File | Size | Used by |
|---|---|---|
| `Image.bmp` | 162×312, 24-bit BMP | MSI `ImageBmp` (Welcome, Completed, Maintenance, Resume pages; 122×234 dialog units) |
| `Banner.bmp` | 632×57, 24-bit BMP | MSI `BannerBmp` (top banner of inner pages; 474×44 dialog units) |
| `hst-installer-side.png`, `hst-installer-banner.png` | same | PNG masters of the two bitmaps |
| `source/side-background.png`, `source/banner-background.png` | 948×1659, 2172×724 | Background illustrations (no text, no logo) |
| `source/prompts.json` | | Exact image prompts |

How it was made (2026-10-30): Codex CLI 0.165.0 with model `gpt-6-astra` (`codex exec`) got a
brief with the dialog pixel sizes, HST colours and assets. It produced the two backgrounds with
its built-in image generator and wrote the composition script, now
[`scripts/brand/msi_installer_art.py`](../../../scripts/brand/msi_installer_art.py). The HST
mark is pasted from `assets/brand/hst-office-mark.png`, never redrawn. Text is set in
Liberation Sans (SIL OFL 1.1; the font is not shipped). The banner's left 452 px stay white
because Windows draws the page title there. The upstream bitmaps are 8-bit. These are 24-bit,
because a 256-colour palette left dither noise on the gradients.

Regenerate:

```bash
.venv/bin/python scripts/brand/msi_installer_art.py --preview work/msi-preview
```

At build time `scripts/windows/trial-build.sh --patch` copies both BMPs over
`instsetoo_native/inc_common/windows/msi_templates/Binary/` and removes the unused upstream
`Image_2.bmp`.
