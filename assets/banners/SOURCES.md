# Banner artwork provenance

Product web assets retrieved 2026-11-04 over verified HTTPS, except the later updates
dated below. The company logo is the
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
| eChatbot / `echatbot.png` | [Official robot logo, 1254×1254 RGBA](https://echatbot.vn/assets/robot-logo.png), retrieved 2026-11-07 | Current `rel=icon` and 48px header logo. Downscaled to 90×90 RGBA for the 30px banner slot at 3×. Site `theme-color` / accent `#0b6fc1`; navy ink `#172b3f`, pale blue-grey tint `#f3f6f9`. |
| eChatbot / `echatbot-chibi.png` | [Official chibi mascot, 384×384 RGBA WebP](https://echatbot.vn/assets/robot-chibi.webp), from the eChatbot website, retrieved 2026-11-07 | Owner-supplied `.inbox/robot-chibi.webp`: waving white-and-blue robot holding a blue chat bubble. Downscaled to 312×312 RGBA for the wide banner's 104px illustration at 3×. |
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

## eChatbot brand refresh (2026-11-07)

The owner supplied the website snapshot in `.inbox/index.html`, `.inbox/site.css`
and `.inbox/robot-logo.png`; this update used those local files without network access.
The PNG is the blue-gradient robot head in a speech-ring used by the current header
and favicon. The old teal `/assets/favicon.svg` still served by the site is superseded.
The source PNG SHA-256 is `61ec5b75cfe732b54266271fb495b7dbaa94120740215b4795aa6bc35aa66204`.
ImageMagick Lanczos downsampling preserves the full square canvas and alpha, without
cropping or recolouring; metadata is stripped and PNG compression is set to level 9.
The committed 90×90 RGBA PNG is 9,721 bytes. Both templates use a 30px-high contain
box, so `logoWidth: 30` remains appropriate at 1×, 2× and 3×. For comparison, the
existing HST SEO and eSpace PNGs are 180×180 and 360×360 in 32×30px contain boxes.

The accent is the snapshot's `theme-color` `#0b6fc1`. Ink uses the site's `--ink`
`#172b3f`; tint uses its `--cream` `#f3f6f9`. WCAG sRGB relative-luminance contrast:

| Pair | Contrast |
|---|---|
| Ink `#172b3f` / tint `#f3f6f9` | 13.32:1 |
| Accent `#0b6fc1` / tint `#f3f6f9` | 4.77:1 |
| White / accent `#0b6fc1` | 5.17:1 (neither template uses white-on-accent text) |
| Existing body `#25364a` / tint; endorsement `#526071` / tint | 11.35:1; 5.92:1 |

The navy exceeds 4.5:1 for normal text and distinguishes the title/CTA from HST SEO's
brighter blue ink. Body text retains the shared template colour. The palette comparison
below covers the remaining blue-family similarity; rendered PNGs and manifests require
the coordinator's browser-based regeneration and visual review.

## eChatbot chibi illustration (2026-11-07)

The supplied `.inbox/robot-chibi.webp` was converted locally without network access.
Its SHA-256 is `7f7f99e5f1e27312c3116163ae912732858908c9c5d13f944401245018402e55`.
ImageMagick Lanczos downsampling retains the complete square canvas and alpha;
metadata stripping, PNG compression level 9 and lossless OptiPNG optimization produce
a 312×312 RGBA PNG of 102,400 bytes. The original colours are retained without palette
quantization. Only the illustration asset is converted; banner PNG regeneration remains
with the coordinator.

The optional `illustration` filename in `brands.json` resolves under `logos/` and is used
only by the wide template. eChatbot was the first brand to set it; the other cards followed on 2026-11-14 (below). Its 104×104px contain
box sits at the right edge, 2px below the inner bottom edge, clipped by the card. The
header, description and footer reserve 114px at the right: a 230px text column, separated
from the illustration by 10px. Existing font sizes, copy and colours are preserved.
The complete banner tagline, “Chatbot AI – trợ lý số cho cơ quan chính quyền, doanh
nghiệp, giáo dục”, measures as two lines with the bundled 12.5px font: “Chatbot AI –
trợ lý số cho cơ quan” (207.21px) and “chính quyền, doanh nghiệp, giáo dục” (222.51px).
CTA and HASON TECH share the footer within the text column. The renderer checks their
separation and text/illustration bounds at each scale; browser verification is pending
the coordinator's render. The catalogue's longer `description` field is not banner copy.

The 160×104 compact card keeps its logo, title and HASON TECH unchanged. A full-height
104px mascot would leave at most 28px for text after borders, insets and the clear gap;
even the endorsement needs about 86px. Shrinking the existing type would impair readability,
so the compact template ignores `illustration`.

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
The green's HSL hue is 126.43°, 80.60° from eChatbot's new 207.03° blue `#0b6fc1`;
pale moss also separates their backgrounds. eChatbot is only 0.61° from HST SEO's
accent `#0874c9` (206.42°), 1.00° from its ink `#005a9f` (206.04°), and 8.50° from
Zalo/eSpace's `#0068ff` (215.53°). These are shortest circular hue distances, not
perceptual colour differences. In particular, eChatbot and HST SEO accents are too
close to distinguish the cards by hue alone. The chosen resolution keeps the official
blue and uses eChatbot's dark navy title/CTA, pale blue-grey tint and distinct robot
silhouette, alongside the existing HST SEO logo and brighter ink. The coordinator
should compare the regenerated wide and compact cards at 1× and 3×; if they still
look alike, strengthen eChatbot's tint using the site's `#d2e0ed` token and recheck
text contrast. HST SEO and Zalo/eSpace palettes are unchanged. HST Post's official
blue mark and dark wordmark are preserved. Social favicons use the same square mark
on an opaque pale-moss canvas.

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

## Generated product illustrations (owner request, 2026-11-14)

The owner asked for every default card to carry a striking right-hand illustration like the eChatbot
mascot. Six original illustrations were generated for HST SEO, AIOS, Zalo Mini App, HST Post, AI Dễ Lắm
and the HASON TECH card; eChatbot keeps its official mascot unchanged. They are not product marks and
contain no text, logos or third-party designs. No stock imagery or external image input was used; the
eChatbot banner served only as a visual style reference for the designer.

**Tool:** OpenAI Codex CLI 0.166 (`codex exec -m gpt-6-astra`), built-in image generation tool
(`image_gen.imagegen`, `transparent_background: true`); the tool does not report its image model.
Each source was a 1254×1254 RGBA PNG with real alpha, kept outside the repository. Round 1 generated one
image per card; after art-director review, AIOS, Zalo Mini App and HASON TECH were regenerated as two
candidates each and the clearer one at 104 px and 75 px was kept.

**Post-processing** (Pillow 10.4.0, OptiPNG 0.7.8): low-opacity haze removed by remapping alpha
`max(0, round((alpha - c) × 255 / (255 - c)))` with cut-off c = 32 (128 for HASON TECH), no colour
keying or recolouring; crop to the alpha bounds; premultiplied LANCZOS fit into 302×302; centred on a
transparent 312×312 canvas with a 3 px bottom margin; `optipng -o3 -strip all`. Each asset is a
312×312 RGBA PNG under 110 KB, shown in a 104 px box at the right of the wide card only.
The 160×104 compact cards are unchanged.

Each prompt is a shared preamble followed by the card's own `Subject:` line, quoted verbatim.

Preamble 1 (HST SEO, HST Post, AI Dễ Lắm):

```text
Use case: stylized-concept.
Asset type: isolated square illustration for a Vietnamese office software product banner, displayed at just 75 to 104 pixels tall.
Style: premium glossy soft 3D toy-like product render in the same visual family as a friendly white-and-blue chibi robot mascot: rounded chunky forms, white ceramic/plastic, saturated coloured enamel accents, soft ambient occlusion, broad controlled specular highlights, gentle studio light from upper left, slight three-quarter perspective. Not a flat icon, not line art.
Composition: one bold main object with at most two simple supporting elements. Tight coherent silhouette, large readable forms, no tiny decoration. Fill a square well, about 90 percent of its height and width, centred horizontally with the subject resting near the bottom edge, fully visible with a slim transparent margin. The art alone; no banner.
Background: true transparent alpha, clean antialiased cutout edges. No floor, no backdrop, no cast shadow outside the subject, no white box, no checkerboard, no glowing fringe.
Strict constraints: absolutely no text, letters, digits, words, pseudo-text, watermark, logos, brand marks, app brands, or recognisable third-party product designs. Do not put text-like dashes on cards. No people, characters, faces or robots. Generic geometric pictograms only.
```

Preamble 2 (AIOS, Zalo Mini App, HASON TECH):

```text
Use case: stylized-concept.
Asset type: isolated square product illustration for an office-software banner, viewed at only 104 px and 75 px. Generate the illustration only, no banner.
Style: premium glossy soft 3D toy-like render matching a friendly white-and-blue chibi mascot's materials, but no character. Chunky rounded forms, porcelain-white plastic, saturated blue enamel, broad soft specular highlights, gentle upper-left studio lighting, clean ambient occlusion, slight three-quarter perspective. Simple iconic silhouette, bold forms, controlled highlights, no thin outlines or flat vector aesthetic.
Background: genuinely transparent RGBA with clean antialiased edges. No backdrop, floor, checkerboard, external cast shadow, halo, or white box. Keep the complete subject visible, tightly framed in the square with a slim transparent margin and bottom aligned.
Strict constraints: no text, letters, digits, words, pseudo-text, watermarks, logos, brand marks or recognizable third-party designs. No people, faces, limbs or robot. Generic pictograms only. Avoid micro-detail, decorative sparkles and extra floating objects.
```

**`logos/hst-seo-illustration.png`**: magnifier over a rising bar chart with an upward arrow and a sparkle. Preamble 1, round 1;
generated source SHA-256 `7dcfe0700e25d53efc808460583c98062b20a4c4a036d08901ae22a9e62e463a`.

```text
Subject: a large glossy blue magnifying glass, its circular lens framing three chunky rising blue chart bars on a small white rounded chart pedestal. The magnifying-glass handle extends diagonally down to the right. One bold rising blue arrow curls just behind the chart, plus one small white-and-blue four-point sparkle near the lens. The lens is clear enough to keep the bars readable. Integrate chart, lens and arrow into a single compact composition. No axes, labels, ticks or grid. Palette: white, brand blue #0874c9, deep blue #005a9f, pale icy blue #edf7fb. Blue must be substantial enough to silhouette clearly against a pale banner.
```

**`logos/aios-illustration.png`**: glowing assistant orb on a dock beside a to-do card with checks and a small calendar. Preamble 2, round 2;
generated source SHA-256 `a40c6c9a38b8fe8e31c1a1dcdc3e325e1f2b182bc336a1e5b3d7e1c78963e5e9`.

```text
Subject: a personal AI companion taking care of daily tasks. A glossy luminous blue orb sits in a very low white-and-blue saucer dock at the LOWER LEFT foreground. ONE large upright rounded white to-do card with thick blue depth is BEHIND and to the RIGHT, tilted subtly clockwise in three-quarter perspective. The card is the tallest element and takes 65 percent of the total width: two large blue checkmarks inside separate rounded square recesses, stacked vertically, with one large empty square below. No lines, words or writing. The orb overlaps the lower left corner of the card and is roughly half the card height. ONE tiny calendar chip tucked off the card's upper LEFT edge, well above the orb: simple blue top binding and four large blue square day cells, no numbers. Hierarchy is an asymmetric diagonal from the low orb toward the tall task list; never two similarly sized tiles flanking a central orb, never mouse ears. Large easily read checks make work completion obvious at 75 px. Palette: white, #0072bb blue, #005a94 deep blue, #eef7fc light blue. No face, no robot, no external glow. Exactly the orb/dock, one checklist card, one small calendar.
```

**`logos/zalo-mini-app-illustration.png`**: smartphone with four generic mini-app pictograms, a civic building and a shop awning. Preamble 2, round 2;
generated source SHA-256 `39aef1819c0ec2cc877b70b05e0223f53949ca97fe759cc84db6bf20d98786b9`.

```text
Subject: one chunky glossy blue-and-white generic smartphone containing mini-app services, with a small government building and a small business storefront emerging at its base. Broad almost-front-facing screen, subtle three-quarter turn, tilted only slightly right. The upper two-thirds of the screen show a clean 2-by-2 grid of FOUR LARGE separated rounded blue/light-blue tiles. Each tile carries ONE BOLD WHITE PICTOGRAM: folded-corner document with no writing, calendar with two binding tabs and one solid square day, shopping bag with a thick handle, map pin with circular hole. Icons are large, high contrast, inset flat relief on the glossy tiles and still recognizable at 75 px; never plain unmarked blue squares. No text-like lines. At the lower foreground, a small white civic building with triangular blue roof and exactly three thick white columns sits LEFT; a separate small white shop with a chunky blue-and-white scalloped awning and one broad dark-blue shop opening sits RIGHT. Both buildings are secondary, together covering only the lower quarter of the phone so all four app tiles stay visible. Exactly phone plus two buildings, no extra badges or platform. Compact full square silhouette. Palette white, saturated #0068ff, deep #0052c7, pale #eff6ff. No Z, no letter, no logo, no hardware-brand details or notch.
```

**`logos/hst-post-illustration.png`**: green megaphone sending a heart card and a share card. Preamble 1, round 1;
generated source SHA-256 `774910ccc6ad46449be4c0a1f841ac4f5902ccb8c54472ca43312e2c9e1c4996`.

```text
Subject: one bold friendly megaphone with a glossy white horn, thick forest-green rounded rim and a chunky green handle angled downward. It broadcasts toward two overlapping rounded social-post cards floating to its upper right. The front white card contains only one large forest-green heart pictogram. The back green card contains only one large white generic share arrow pictogram. No text-like bars, no social network logos, no tiny UI. Exactly the main megaphone and two cards, compact and legible. Green-dominant palette: rich forest green #245c2a, white, soft light green #e4edcf, warm pale green #f2f7e8, restrained muted green #7d9e55. No blue, no red, no gold.
```

**`logos/ai-de-lam-illustration.png`**: open toolbox with a lightbulb and a sparkle star. Preamble 1, round 1;
generated source SHA-256 `e4ee4b57a4bb357283a4780b0b34ffeddfd1beb5cd46b623607089b105c68716`.

```text
Subject: one open chunky white-and-blue 3D toolbox, friendly rounded corners, vivid blue bottom half and thick blue handle on its open back lid. Emerging from inside are just two bold learning tools: a plump white lightbulb with a pale-blue luminous glass head on the left, and a large glossy blue four-point magic sparkle star on a short white wand on the right. A practical approachable AI-learning kit. Keep these two objects large, separated and readable, no extra tools and no floating dust or tiny sparkles. Palette: white, brand blue #2570e6, deep blue #0f3ea0, pale blue #f0f4fd. No letters or emblems on the box.
```

**`logos/hasontech-illustration.png`**: isometric platform with three connected cubes and a rising arrow. Preamble 2, round 2;
generated source SHA-256 `b761d08b0be553d251d0e9cefbd6f367d31a69379a2622e41f9c490cae667546`.

```text
Subject: digital ecosystem growth distilled to one white isometric rounded platform, THREE chunky connected blue cube nodes, and one large upward arrow. Platform is a soft thick square seen from above at three-quarter angle with a vivid blue rim. One cube at front LEFT, one at front RIGHT, one at back CENTRE, all similarly large. Wide blue Y-shaped tracks join them, conspicuous against the white platform. ONE very broad glossy blue arrow starts low behind the rear cube and rises diagonally toward the UPPER RIGHT, with a big simple triangular arrowhead and only one gentle bend. Leave clean transparent negative space beside the arrow; omit the cloud entirely. No tiny cables, floating chips, sparkle or extra ornament. Broad highlights, rounded toy-like surfaces, each cube a large readable volume, thick compact platform. Network and growth arrow should be immediately clear as a unified icon at 104 and 75 px. Palette white with brand #0072bc blue, #004f8b shadow blue, #eef7ff highlights. Exactly platform, three connected cubes, arrow.
```

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

## Content hashes of the committed assets

| File | SHA-256 |
|---|---|
| `fonts/BeVietnamPro-Bold.ttf` | `7f738fe5c43c8872807b20e2d30d42163618de8a4daf7f48a939adac32c16847` |
| `fonts/BeVietnamPro-Regular.ttf` | `cd1ef6e9d7db28ad5cdb88a65ccbe693870e60d340b791f349d248342b4fe4c3` |
| `fonts/BeVietnamPro-SemiBold.ttf` | `bd8e27eb02720b9d91e59e4f10a90878643219f25ce6a8d9a4f06a8a88d3bb71` |
| `fonts/OFL.txt` | `6b7f8f73609a25ea78c891e34cf37b06f8a676b7ea986e941e43b009110f2a85` |
| `logos/ai-de-lam.svg` | `a8d37601aeb6b6948e4c7c4d79aa2688ca2d2358f18261cfa44c12e83b7b5291` |
| `logos/aios.png` | `b759611d6d6f8ed42709fb8a9c9a75548f1b4c3aa8d64d87cb3df529af912fd1` |
| `logos/echatbot.png` | `4ffc1c87a8f463e219cfb9c6a9c824830ec031606cdf63ccb9c97db1a2dc4fa9` |
| `logos/echatbot-chibi.png` | `faa6273a437123903e27853604abe601f10fd9acb5ae0512d4a20983f1b4c05f` |
| `logos/ai-de-lam-illustration.png` | `5448851141f387fadc73d2c1a28f3b7b05493a90f6b36aaf1660999e8f55d89a` |
| `logos/aios-illustration.png` | `43a95a7015f01f8fa8cb52d808d0a9db0e0b7049865131468b2b49cee4de29e7` |
| `logos/hasontech-illustration.png` | `db1857c1d67fbc801b395520efd0eadbaf8a1fdc8b629bcbf544dd48f9a5a121` |
| `logos/hst-post-illustration.png` | `7243bd5ce81fc9e65ddbaec31a9686e75ac1b8dc00eadf73b327933237812850` |
| `logos/hst-seo-illustration.png` | `159bc5d1723773a20f794788398682bdd187313aa6fad457b5f09c99b06bd583` |
| `logos/zalo-mini-app-illustration.png` | `d977953c6854b2f0bc25c1d9dfbb1c5e68aa67eb5ba883140fa416c02835b640` |
| `logos/espace.png` | `bc390a069546d13784ddc6a8ae36c9cf877d7fc4ea3ce5472e036b4b529ba0ae` |
| `logos/hasontech.png` | `2f77a5fce52a515d52333cca3879a0aec18e582628a7111c00a05714b1c4d2ef` |
| `logos/hst-seo.png` | `8099441e2e8fedf9f0f2b97fb58c4ed7db866d1b2512b22a5f8aada990ee8822` |
