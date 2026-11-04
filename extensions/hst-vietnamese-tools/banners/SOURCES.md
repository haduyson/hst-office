# Banner artwork provenance

Retrieved 2026-11-04 over verified HTTPS. Logos are original HASON TECH/product assets,
used to identify the owner's solutions; they are not redrawn or newly generated marks.
Local candidates were inspected alongside the live site's header, `og:image`, touch icons
and advertised web manifest. The committed copies live under
`extensions/hst-vietnamese-tools/banners/logos/`; this document is also bundled as `banners/SOURCES.md`.

| Solution / file | Chosen source | Reason / brand colour |
|---|---|---|
| AIOS / `aios.png` | [Header logo, 640×327](https://aios.hasontech.vn/logo-full.png) | Original transparent full logo, better suited to a horizontal slot than the padded 512×512 PWA icon. Blue `#0072bb`. |
| eChatbot / `echatbot.svg` | [Official favicon vector](https://echatbot.vn/assets/favicon.svg) | True vector; same speech-bubble mark as the site header. Site theme `#07594f`. |
| Zalo Mini App / `espace.png` | [eSpace product icon, 360×360](https://espace.vn/zaloapp/espace-logo.png) | The product's own current icon, advertised as favicon and touch icon. Blue sampled from logo; accent `#0068ff`. |
| HST SEO / `hst-seo.png` | [Official touch icon, 180×180](https://seo.hasontech.vn/apple-touch-icon.png) | Actual product touch icon, sufficient for the 32px slot even at 3×; the page header uses the company logo. Site CSS `--blue: #0874c9`, `--blue-dark: #005a9f`. |
| HST Post / no logo file | [Requested live site](https://post.hasontech.vn) | **No verifiable product logo found.** TLS certificate hostname mismatch prevented inspection. The company [HST Content page](https://hasontech.vn/hst-content/) has no independently verifiable HST Post logo. Approved fallback: “HST Post” as a typographic wordmark, corporate blue `#0072bb` from the company site's CSS. The owner-approved name and destination remain unchanged. |
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

## Font

Be Vietnam Pro Regular, SemiBold and Bold, unmodified Google Fonts TTFs:
[upstream directory](https://github.com/google/fonts/tree/main/ofl/bevietnampro).
Downloaded from `https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/`
with filenames `BeVietnamPro-Regular.ttf`, `BeVietnamPro-SemiBold.ttf`,
`BeVietnamPro-Bold.ttf`, `OFL.txt`. SIL Open Font License 1.1 permits redistribution;
the complete licence is beside the fonts in `banners/fonts/OFL.txt`.

The HTML template uses only these bundled fonts for banner copy. The official AI Dễ Lắm SVG
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
