# HST Post social previews

Launch-ready web assets for `https://post.hasontech.vn/`. Deploy this directory at
`/assets/hst-post/` on that host. These files are not bundled into the Office extension.

| File | Dimensions | Purpose |
| --- | --- | --- |
| [og-hst-post.png](og-hst-post.png) | 1200 × 630 | Lossless landscape preview for Facebook, Zalo, LinkedIn and X. |
| [og-hst-post@2x.png](og-hst-post@2x.png) | 2400 × 1260 | High-resolution landscape master for reuse. |
| [og-hst-post.jpg](og-hst-post.jpg) | 1200 × 630 | Optimised progressive JPEG, under 300,000 bytes; used by the tags below. |
| [og-hst-post-square.png](og-hst-post-square.png) | 1200 × 1200 | Re-composed square artwork for square preview placements. |
| [favicon.svg](favicon.svg) | Vector, 320 × 320 viewBox | Square HS logo icon on pale violet, for browser tabs. |
| [favicon-32.png](favicon-32.png) | 32 × 32 | PNG browser icon fallback. |
| [apple-touch-icon.png](apple-touch-icon.png) | 180 × 180 | Opaque home-screen icon. |
| [icon-512.png](icon-512.png) | 512 × 512 | Large square icon for web/app integrations. |

[Preview sheet](../../docs/design/hst-post-social-preview.png): schematic Facebook-style
feed card and Zalo-style chat card, drawn from scratch using the landscape artwork.
These illustrate placement; actual cards and cropping depend on the app.

## Site integration

Add these tags to the server-rendered `<head>` of the home page, replacing any existing
social metadata for that page. Serve the images publicly over HTTPS with the matching
image MIME types. The URLs below assume the deployment path above; this repository
does not deploy or change the live site.

```html
<meta charset="utf-8">
<title>HST Post — Đăng bài đa nền tảng bằng AI</title>
<meta name="description" content="Công cụ đăng bài bằng AI trên hàng loạt nền tảng mạng xã hội của HASON TECH. Dùng ngay tại post.hasontech.vn.">
<link rel="canonical" href="https://post.hasontech.vn/">

<meta property="og:title" content="HST Post — Đăng bài đa nền tảng bằng AI">
<meta property="og:description" content="Công cụ đăng bài bằng AI trên hàng loạt nền tảng mạng xã hội của HASON TECH. Dùng ngay tại post.hasontech.vn.">
<meta property="og:image" content="https://post.hasontech.vn/assets/hst-post/og-hst-post.jpg">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="HST POST — Đăng bài đa nền tảng bằng AI. Một bài viết kết nối tới nhiều nền tảng. HASON TECH. Dùng ngay tại post.hasontech.vn.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://post.hasontech.vn/">
<meta property="og:site_name" content="HST Post">
<meta property="og:locale" content="vi_VN">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="HST Post — Đăng bài đa nền tảng bằng AI">
<meta name="twitter:description" content="Công cụ đăng bài bằng AI trên hàng loạt nền tảng mạng xã hội của HASON TECH. Dùng ngay tại post.hasontech.vn.">
<meta name="twitter:image" content="https://post.hasontech.vn/assets/hst-post/og-hst-post.jpg">
<meta name="twitter:image:alt" content="HST POST — Đăng bài đa nền tảng bằng AI. Một bài viết kết nối tới nhiều nền tảng. HASON TECH. Dùng ngay tại post.hasontech.vn.">

<link rel="icon" type="image/svg+xml" sizes="any" href="https://post.hasontech.vn/assets/hst-post/favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="https://post.hasontech.vn/assets/hst-post/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="https://post.hasontech.vn/assets/hst-post/apple-touch-icon.png">
```

The image dimensions, type and alt text follow the
[Open Graph structured image properties](https://ogp.me/#structured).
Use the landscape image as the default. For a separate square placement, explicitly
choose `og-hst-post-square.png` and dimensions `1200` × `1200`; the square design is
not a centre crop of the landscape image. After deployment, inspect the returned
HTML and image URLs, then refresh cached previews in the platforms' sharing tools.

## Regeneration

The renderer uses only committed artwork and fonts, with no network requests during
rendering. From the repository root, install the same rendering dependencies used by
the existing banner scripts (Python 3.12 in this environment):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install Pillow==10.4.0 playwright==1.64.1
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/brand/render-hst-post-social.py
.venv/bin/python scripts/brand/render-hst-post-social.py --check
bash scripts/ci-quality.sh
```

Linux hosts without browser system libraries can use `playwright install --with-deps chromium`.
`--check` regenerates in memory and compares all nine generated outputs byte for byte,
including the preview sheet. The renderer checks loaded fonts/images, text contrast,
safe-area bounds and the JPEG byte limit. Use the pinned browser/Pillow versions for
byte-identical results; other operating systems or font rasterisers may differ.

Sources:

- [Renderer](../../scripts/brand/render-hst-post-social.py) and
  [HTML/SVG composition](../../scripts/brand/hst-post-social.html).
- Existing [HST POST logo](../../extensions/hst-vietnamese-tools/banners/logos/hst-post.svg)
  and [square icon](../../extensions/hst-vietnamese-tools/banners/logos/hst-post-icon.svg).
  The favicon adds an opaque pale-violet canvas to the unchanged official blue mark.
  The full logo uses the owner-supplied official source and extracted dark `#322e2e` lettering.
- Bundled Be Vietnam Pro Regular, SemiBold and Bold, with
  [SIL Open Font License](../../extensions/hst-vietnamese-tools/banners/fonts/OFL.txt).
- Shared violet [brand palette](../../extensions/hst-vietnamese-tools/banners/brands.json)
  and [logo provenance](../banners/SOURCES.md).

All landscape text and the entire logo box stay inside `x=60…1140`, `y=32…598`
(the central 1080 × 566 safe area); at 2×, these coordinates double. The square uses
60 px safe margins. The four channel glyphs are original generic conversation,
gallery, feed and community drawings, with no other companies' marks or implied integrations.

Text contrast against its solid background is 12.32:1 for slate body copy, **7.10:1**
for violet `#6d28d9` headline/footer text, and
**13.41:1** for the dark `#322e2e` company name and logo lettering. No text sits on a
gradient. The renderer reads the same HST Post palette as the banner from `brands.json`.
The launch copy describes the product and invites readers to use `post.hasontech.vn`,
without invented usage claims.
