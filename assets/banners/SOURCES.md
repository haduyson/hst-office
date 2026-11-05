# Banner artwork provenance

Product web assets retrieved 2026-11-04 over verified HTTPS. The company logo is the
**official file supplied by the owner**, copied unchanged from
`/work/banner-inbox/local/hasontech-official-logo.png` (476×393, RGBA).
This file is the only company-logo reference. Logos are original HASON TECH/product assets,
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
| HST Post / `hst-post.svg`, `hst-post-512.png`, `hst-post-1024.png`, `hst-post-icon.svg`, `hst-post-icon-512.png` | Owner-supplied official `hasontech-official-logo.png` (476×393, RGBA), retained as `logos/hasontech.png` | Official blue HS triangle; H/S/T/O extracted from the all-caps official wordmark, P constructed from O/H strokes. All lettering is dark `#322e2e`. Surrounding product artwork uses forest green `#245c2a`. |
| AI Dễ Lắm / `ai-de-lam.svg` | [Official page's inline `rel=icon` SVG](https://aidelam.com) | URL-decoded exact SVG, not a recreation. Gradient stops `#0f3ea0`, `#2570e6`. Live `og-aidelam.png` returned HTTP 403; the inline vector is sharper for this slot. |
| Company / `hasontech.png` | **Official file supplied by the owner:** `/work/banner-inbox/local/hasontech-official-logo.png` | Unmodified 476×393 RGBA reference: blue HS triangle above italic, all-caps, one-colour “HASON TECH”. Supersedes the previously selected website logo. |

Additional live assets inspected: AIOS `icon.svg` (embeds a 256px raster, not a true vector),
`logo-mark.png` (256px), `apple-touch-icon.png` (180px), `manifest.webmanifest`, `icon-512.png`,
`og-image.jpg`; eChatbot `assets/echatbot-social.jpg`; eSpace
`landing/og-espace-da-linh-vuc.png`; HST SEO `assets/hstseo-thumbnail.jpg`.
HST SEO `/manifest.json`, `/manifest.webmanifest` and eSpace `/zaloapp/manifest.webmanifest`
returned 404; their pages advertise no manifest. eChatbot and AI Dễ Lắm advertise no
web manifest or touch icon. No TLS checks were bypassed.

Local candidates inspected (not committed): `banner-inbox/local/hst-seo-apple-touch-icon.png`,
`zalo-mini-app-logo.png`, `zalo-mini-app-apple-touch-icon.png`, `espace-logo.png`,
`echatbot-favicon.svg`, `ai-de-lam-aidelam.png`.
The Zalo candidates depict other marks; the current eSpace product icon was selected.
The AI Dễ Lắm candidate is a marketing composition, so its live vector favicon was selected.

## HST Post derivative (owner request, 2026-11-04)

The owner requested a derivative of the supplied official company logo on 2026-11-04.
The official source stays byte-for-byte unchanged. The triangle retains its geometry,
negative spaces and blue `#0072bb`; only the lettering changes to **HST POST**.
The previous mixed-case website logo and substitute Exo 2 lettering are superseded.

`scripts/brand/hst-post-shapes.json` holds outlines extracted from the official source and
its pinned SHA-256. H, S, T and O come directly from the official wordmark's alpha mask,
including the distinctive H crossbar and T stem notches. Glyph source boxes are recorded
in the file. Their outlines were extracted at 8× with 0.45px smoothing and Potrace 1.16;
the mark's straight edges were fitted to the original pixel alpha coverage. P uses O's
bowl shortened by 19px, preserving its stroke thickness, with the lower bowl shifted 3px
to follow the slant, joined to H's full-height left stem. No substitute typeface is used.

The lettering preserves the source's roughly 48px cap height, 9px strokes, italic slant,
44px letter advance and 24px word gap. Every letter is the original dark **`#322e2e`**.
The shorter wordmark is centred under the unchanged mark, on the source's 476×393 canvas.
Regression tests pin the official source hash and compare the mark and extracted glyph
silhouettes against it, allowing raster/vector edge antialiasing differences.

The SVGs are self-contained paths, without embedded bitmaps or runtime font dependencies.
The transparent logo PNGs are 512×423 and 1024×845. The square SVG (320×320 viewBox) and
512×512 PNG contain the mark alone with centred safe margins. The banner uses this square
icon beside its large “HST Post” title. `scripts/brand/render-hst-post-logo.py` reproduces
all five logo assets and the side-by-side preview from the committed outlines, verifying
the official source hash first. `--check` compares all six outputs byte for byte.

At the owner's request, HST Post's banner and social artwork share a deep forest green
palette in `brands.json`: **`#245c2a`** for accents and text, pale moss `#f2f7e8` for
backgrounds, `#e4edcf` for soft fills, `#b9ce96` for illustration outlines and `#7d9e55`
for muted illustration details. Green text contrast is **7.96:1 on white** and
**7.29:1 on the tint**. The lowest added-text contrast is **5.88:1** (`#526071` on
`#f2f7e8`), exceeding 4.5:1. Renderers and regression tests check these text pairs.
The green's hue is 126.43°, more yellow than eChatbot's 172.68° teal `#07594f`
(46.25° apart); pale moss also separates the backgrounds. The generated banner preview
includes both cards side by side at their actual ribbon size for visual review.
HST SEO retains its separate blue palette. The official blue mark and dark wordmark
are preserved. Social favicons use the same square mark on an opaque pale-moss canvas.

## HASON TECH company banner (2026-11-05)

The seventh card promotes the company itself, after the six product cards. Its copy is
stored with the company palette in `brands.json`; `data/hst/solutions.json` remains the
product catalogue. The chosen tagline **“Công nghệ tạo giá trị”** is the first part of
the [homepage](https://hasontech.vn/) headline. The owner supplied the supporting copy
**“Giải pháp chuyển đổi số toàn diện”**; CTA **“Khám phá hệ sinh thái →”** also comes from that page.
Alternative taglines considered: “Chuyển đổi số – Dẫn tương lai” and “Hệ sinh thái công nghệ số”.
No statistics, awards or customer claims are added.

Content reference: supplied `build/hasontech-site/text.txt` and `index.html`.
Palette reference: [homepage stylesheet](https://hasontech.vn/wp-content/themes/hason-tech/style.css?ver=3.0.54),
retrieved over verified HTTPS on 2026-11-05, specifically `.hst-hero`, `.hst-h1`, `.hst-more`
and `.hst-trust`. Its SHA-256 is `2e82d8c7960ea3dc3ef9df201b19141b9bae284e98e0bd398e08a547b29cdeb6`.
Tokens: accent `#0072bc`, deep-blue ink `#004f8b`, body text `#11233a`, hero tint
`#eef7ff`. Secondary text uses the family's `#526071`; the site's
`#65758a` would reach only 4.34:1 on the tint. Ratios on white / tint respectively:

| Colour | Use | Contrast |
|---|---|---|
| `#004f8b` | Company name, CTA | 8.43:1 / 7.78:1 |
| `#11233a` | Tagline | 15.84:1 / 14.63:1 |
| `#526071` | Supporting line, website | 6.42:1 / 5.93:1 |
| `#0072bc` | Decorative accent | 5.08:1 / 4.69:1 |

Three layouts were rendered and visually inspected at 1×, 2× and pixel-exact 3× zoom:
the product-family layout, a company signature with a larger logo on the left, and a
right-aligned logo layout. The owner selected variant A, the family layout: the small
logo and company name share the first row, followed by the tagline and supporting line.
The CTA sits bottom-left and `hasontech.vn` bottom-right. The logo uses a 38×30px
contain box and copy uses 17px line spacing; the supporting line remains 12px regular
and fits on one line. The complete original logo is proportionally scaled, without
cropping, recolouring or redrawing; it matches
`assets/brand/source/hasontech-logo-original.png` byte for byte. Vietnamese copy is
12px or larger, with full diacritics and no clipping. Review-only artifacts are in
`build/banner-hasontech/` (uncommitted): `variants.png` (original explorations),
`final.png`, `final-zoom3x.png`, `rotation.png` (seven cards at 1×).
Production images follow the contract's 360×104, 720×208 and 1080×312 sizes; the ribbon
aspect-fits them inside its slot. The complete seven-card preview is `docs/design/banners-preview.png`.

Before publication, configure `/hst-office/go/hasontech` to count and 302-redirect to
`https://hasontech.vn/`, preserving the three documented UTM parameters. Upload all
three company PNGs and publish the seven-card feed with a fresh UTC generation and
detached signature atomically, after owner review. Only the unsigned publishing
example is regenerated here; no deployed feed or signing key is changed.

## Font

Be Vietnam Pro Regular, SemiBold and Bold, unmodified Google Fonts TTFs:
[upstream directory](https://github.com/google/fonts/tree/main/ofl/bevietnampro).
Downloaded from `https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/`
with filenames `BeVietnamPro-Regular.ttf`, `BeVietnamPro-SemiBold.ttf`,
`BeVietnamPro-Bold.ttf`, `OFL.txt`. SIL Open Font License 1.1 permits redistribution;
the complete licence is beside the fonts in `banners/fonts/OFL.txt`.

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
| `logos/hasontech.png` | `2f77a5fce52a515d52333cca3879a0aec18e582628a7111c00a05714b1c4d2ef` |
| `logos/hst-seo.png` | `8099441e2e8fedf9f0f2b97fb58c4ed7db866d1b2512b22a5f8aada990ee8822` |
