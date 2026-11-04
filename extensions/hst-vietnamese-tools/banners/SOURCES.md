# Banner artwork provenance

Retrieved 2026-11-04 over verified HTTPS. Logos are original HASON TECH/product assets,
used to identify the owner's solutions. HST Post is the owner-requested derivative documented below.
Local candidates were inspected alongside the live site's header, `og:image`, touch icons
and advertised web manifest. The committed copies live under
`extensions/hst-vietnamese-tools/banners/logos/`; this document is also bundled as `banners/SOURCES.md`.

| Solution / file | Chosen source | Reason / brand colour |
|---|---|---|
| AIOS / `aios.png` | [Header logo, 640×327](https://aios.hasontech.vn/logo-full.png) | Original transparent full logo, better suited to a horizontal slot than the padded 512×512 PWA icon. Blue `#0072bb`. |
| eChatbot / `echatbot.svg` | [Official favicon vector](https://echatbot.vn/assets/favicon.svg) | True vector; same speech-bubble mark as the site header. Site theme `#07594f`. |
| Zalo Mini App / `espace.png` | [eSpace product icon, 360×360](https://espace.vn/zaloapp/espace-logo.png) | The product's own current icon, advertised as favicon and touch icon. Blue sampled from logo; accent `#0068ff`. |
| HST SEO / `hst-seo.png` | [Official touch icon, 180×180](https://seo.hasontech.vn/apple-touch-icon.png) | Actual product touch icon, sufficient for the 32px slot even at 3×; the page header uses the company logo. Site CSS `--blue: #0874c9`, `--blue-dark: #005a9f`. |
| HST Post / `hst-post.svg`, `hst-post-512.png`, `hst-post-1024.png`, `hst-post-icon.svg`, `hst-post-icon-512.png` | [Company original, 460×336](https://hasontech.vn/wp-content/uploads/2026/08/hason-tech-logo.png) | Derived at the owner’s request on **2026-11-04**: retain the triangle HS symbol, replace the company lettering with “HST POST”. Two blue vector paths trace the mark; outlined Exo 2 ExtraBold Italic matches the bold, slanted sans style. Original blue `#0072bb` and grey `#58595b`. |
| AI Dễ Lắm / `ai-de-lam.svg` | [Official page's inline `rel=icon` SVG](https://aidelam.com) | URL-decoded exact SVG, not a recreation. Gradient stops `#0f3ea0`, `#2570e6`. Live `og-aidelam.png` returned HTTP 403; the inline vector is sharper for this slot. |
| Company / `hasontech.png` | [Official 460×336 logo](https://hasontech.vn/wp-content/uploads/2026/08/hason-tech-logo.png) | Retained reference asset. Banners use a subtle typeset “HASON TECH” endorsement, not a fabricated company symbol. |

Additional live assets inspected: AIOS `icon.svg` (embeds a 256px raster, not a true vector),
`logo-mark.png` (256px), `apple-touch-icon.png` (180px), `manifest.webmanifest`, `icon-512.png`,
`og-image.jpg`; eChatbot `assets/echatbot-social.jpg`; eSpace
`landing/og-espace-da-linh-vuc.png`; HST SEO `assets/hstseo-thumbnail.jpg`;
HASON TECH `wp-content/uploads/2023/11/Logo-HasonTech-slogan.png` (622×162).
HST SEO `/manifest.json`, `/manifest.webmanifest` and eSpace `/zaloapp/manifest.webmanifest`
returned 404; their pages advertise no manifest. eChatbot and AI Dễ Lắm advertise no
web manifest or touch icon. No TLS checks were bypassed.

Local candidates inspected (not committed): `banner-inbox/local/hst-seo-apple-touch-icon.png`,
`zalo-mini-app-logo.png`, `zalo-mini-app-apple-touch-icon.png`, `espace-logo.png`,
`echatbot-favicon.svg`, `ai-de-lam-aidelam.png`, `hasontech-logo.png`.
The Zalo candidates depict other marks; the current eSpace product icon was selected.
The AI Dễ Lắm candidate is a marketing composition, so its live vector favicon was selected.

## HST Post derivative (owner request, 2026-11-04)

There is no separate official HST Post logo. The owner explicitly requested this derivative of
HASON TECH's company logo on 2026-11-04. The original reference stays unmodified. Only the
lettering changes to “HST POST”; the two-component triangular HS design and its negative spaces
are preserved in a straight-edge vector trace at the original coordinates. As with any raster-to-vector
trace, edge antialiasing is renderer-dependent; the symbol is not redesigned.

The site's media API and full-size assets were checked over verified HTTPS. The 2026 original
and `2023/11/Logo-HasonTech.png` are both 460×336 (the same original); the 622×162
[2023 slogan logo](https://hasontech.vn/wp-content/uploads/2023/11/Logo-HasonTech-slogan.png)
has only a roughly 147×128 mark, versus 269×233 in the selected original. The other 2023
`hasontech-logo.png` (440×441) and `hasontech-logoblue.png` (408×353) also contain a mark of
roughly 269×233, so their larger canvas does not add symbol detail. No higher-resolution mark
was advertised by the media API.

The SVGs are self-contained paths, with no embedded bitmap or runtime font dependency.
The 512px and 1024px transparent PNGs retain the original stacked layout; the square SVG and
512×512 PNG contain the mark alone with equal centering and safe margins.
`scripts/brand/render-hst-post-logo.py` reproduces all five assets and the side-by-side preview
from the committed trace and font. `--check` compares the six generated outputs byte for byte.

## Font

Be Vietnam Pro Regular, SemiBold and Bold, unmodified Google Fonts TTFs:
[upstream directory](https://github.com/google/fonts/tree/main/ofl/bevietnampro).
Downloaded from `https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/`
with filenames `BeVietnamPro-Regular.ttf`, `BeVietnamPro-SemiBold.ttf`,
`BeVietnamPro-Bold.ttf`, `OFL.txt`. SIL Open Font License 1.1 permits redistribution;
the complete licence is beside the fonts in `banners/fonts/OFL.txt`.

The derivative lettering uses Exo 2 ExtraBold Italic (weight 800), a matching squared sans,
instantiated from the [Google Fonts Exo 2 italic variable font](https://github.com/google/fonts/tree/main/ofl/exo2)
with fontTools. The static instance and original SIL OFL 1.1 text are bundled under `fonts/exo2/`.
The exact original lettering font was not available from the source artwork; Exo 2 provides the
bold slant and squared curves without tracing or distorting individual source letters.

The HTML template uses Be Vietnam Pro for banner copy. The official AI Dễ Lắm SVG
retains its original embedded text instructions (Arial). Logos are exempt from the text
contrast measurement; all added text, including CTA and company endorsement, passes 4.5:1.

## Content hashes of the chosen originals

| File | SHA-256 |
|---|---|
| `fonts/BeVietnamPro-Bold.ttf` | `7f738fe5c43c8872807b20e2d30d42163618de8a4daf7f48a939adac32c16847` |
| `fonts/BeVietnamPro-Regular.ttf` | `cd1ef6e9d7db28ad5cdb88a65ccbe693870e60d340b791f349d248342b4fe4c3` |
| `fonts/BeVietnamPro-SemiBold.ttf` | `bd8e27eb02720b9d91e59e4f10a90878643219f25ce6a8d9a4f06a8a88d3bb71` |
| `fonts/OFL.txt` | `6b7f8f73609a25ea78c891e34cf37b06f8a676b7ea986e941e43b009110f2a85` |
| `logos/ai-de-lam.svg` | `a8d37601aeb6b6948e4c7c4d79aa2688ca2d2358f18261cfa44c12e83b7b5291` |
| `logos/aios.png` | `b759611d6d6f8ed42709fb8a9c9a75548f1b4c3aa8d64d87cb3df529af912fd1` |
| `logos/echatbot.svg` | `e1b1cd23a96ab95e699603710c5e9959aa2641e1d8f48d972d38a82cbbc845af` |
| `logos/espace.png` | `bc390a069546d13784ddc6a8ae36c9cf877d7fc4ea3ce5472e036b4b529ba0ae` |
| `logos/hasontech.png` | `13e048eae4b04b8865dff12a60784bce82dba19b4e3df5f9c07309508f377dd5` |
| `logos/hst-seo.png` | `8099441e2e8fedf9f0f2b97fb58c4ed7db866d1b2512b22a5f8aada990ee8822` |
| `fonts/exo2/Exo2-ExtraBoldItalic.ttf` | `cd9b734519f516b17eed7f2177afdaf86ff9164bcf7cfda1a9e323c57ae2a1a5` |
| `fonts/exo2/OFL.txt` | `41970aabe4fafb48410304c00fa10f29c03318f142b9928f332ecb15bb404b78` |
