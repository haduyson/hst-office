# HASON TECH ribbon banners — delivery report

Date: 2026-11-04. Target: HST Office 1.0.0-beta.5. Branch: `codex/banner`.

## Delivered

- Six light-theme 360×104 cards, each exported at 1×, 2× and 3× as PNG (18 files).
  Names and taglines are verbatim from `data/hst/solutions.json`; each card includes
  “Tìm hiểu thêm →” and a subtle “HASON TECH” endorsement. Be Vietnam Pro fonts and their
  OFL licence are bundled. Taglines are 12.5px, all added text passes 4.5:1 contrast,
  and the cards use an 8px radius and tinted border. PNG sizes range from 23,388 to
  147,042 bytes; all are below 300 KiB.
- Committed HTML template, palettes, original logos, fonts, renderer and all outputs.
  The renderer runs without network, checks fonts/images/layout/contrast, and supports
  byte-for-byte `--check`. [Preview sheet](../../docs/design/banners-preview.png)
  shows all six at 1× and 2×. [Writer mockup](../../docs/design/banner-on-writer.png)
  uses the supplied real screenshot, with space reserved beside the two-row ribbon.
- Shared bundled manifest and a complete, valid
  [online example](../../assets/banners/banners-online.example.json) with real image hashes/sizes
  at `https://system.hasontech.vn/hst-office/`. The signing script accepts an explicit
  separate key path, validates before signing, refuses the update key, and has no default
  key path/environment fallback. **No real private key was created or read.**
- Background feed with a profile-wide 24-hour attempt stamp, HTTPS-only transport,
  five-second request timeout, same-origin redirects, signature-before-schema validation,
  strict item/image host allow-list, byte/hash/magic verification, atomic cache publication,
  prior-generation fallback, time/SemVer windows, clamped rotation and weighted ordering.
  No banner visibility settings, administrator disable policy, device identifiers or telemetry.
  Click URLs use only the shared UTM source/campaign plus `medium=banner`.
- Registered `org.hst.office.BannerFeed` XJob service and startup job, plus the pure Python
  snapshot API. All seven extension banner modules are at most 136 lines. Integration,
  cache semantics, limits, publishing and C++/Python examples are documented in
  [BANNERS.md](../../docs/BANNERS.md#integration-for-the-ribbon-widget).
- OXT packaging includes the manifest and entire artwork tree. The validator checks stale
  manifests, image presence/hash/size/type, font licensing and the narrow network import exception.

## Logo provenance

All selected assets were fetched over verified HTTPS; originals and SHA-256 values are
recorded in [SOURCES.md](../../assets/banners/SOURCES.md) and its bundled copy.

| Solution | Selected source |
|---|---|
| AIOS | [Official header logo, 640×327 PNG](https://aios.hasontech.vn/logo-full.png); also inspected the PWA manifest/512px icon, touch icon and social image. |
| eChatbot | [Official header/favicon SVG](https://echatbot.vn/assets/favicon.svg). |
| Zalo Mini App | [Current eSpace product/touch icon, 360×360 PNG](https://espace.vn/zaloapp/espace-logo.png). |
| HST SEO | [Official 180px touch icon](https://seo.hasontech.vn/apple-touch-icon.png); adequate for the 32px slot at 3×. |
| HST Post | **No verifiable logo found.** `post.hasontech.vn` failed TLS hostname validation. The company HST Content page did not establish a product mark. Used the explicitly permitted typographic wordmark and corporate blue; retained the owner-approved name and URL. |
| AI Dễ Lắm | Exact URL-decoded inline favicon SVG from [aidelam.com](https://aidelam.com). Its social image returned 403; the live vector was selected over the inbox marketing composition. |
| HASON TECH | [Official company PNG](https://hasontech.vn/wp-content/uploads/2026/08/hason-tech-logo.png), retained as a reference. |

The inbox candidates were inspected but `banner-inbox/` is neither copied wholesale nor committed.
No logo was invented or redrawn. Rendering assets are committed independently of the inbox.

## Validation

| Check | Result |
|---|---|
| New banner unit tests | **42 passed**: signature, schema limits, allow-list, image checks, windows, fallback/corruption, offline cache, daily throttle/restart/concurrent claim, UTM, request headers, redirects, signing and nonblocking startup. No real network; throwaway keys only. |
| `scripts/ci-quality.sh` | **54 commands, 0 failures**. **480 tests run: 479 passed, 1 skipped** because the upstream LibreOffice source tree is absent. Native/platform preflights also report their usual unavailable upstream/tarball inputs. |
| `scripts/check-extensions.py` | **PASS** for the built 196-file OXT. |
| `scripts/check-extensions.py --self-test` | **24 invalid packages rejected; 1 valid package accepted**. |
| `scripts/build-extensions.py --verify-reproducible` | **PASS**, byte-identical builds; SHA-256 `f2a2b079cd88c43818667d4860d57968152e1aa3fb39bb896beb687666732140`. |
| Renderer `--check` | **22 outputs reproduced exactly**, no clipping or contrast failures. Both preview images visually reviewed. |
| Real UNO boundary check | **3 scale checks passed** with native NamedValue/JSON/file-URL conversion and injected profile lookup. |
| Native registered service on `/opt/hst` | **PASS in Writer, Calc/Sheets and Impress/Slides**: 9 snapshots (3 apps × 3 scales), **54 PNGs decoded through the native GraphicProvider**, expected pixel sizes and click UTM verified. Isolated user profile; installation untouched. |
| Markdown links / whitespace | PASS. |

The first quality run exposed an existing language-menu test coupled to menu node `m9`,
which now belongs to feature search. A separate conventional commit updates the test to
assert the intended language context (three document apps plus Start Center). No menu
behavior changed. Missing container lint/download dependencies were installed before the
final successful full run.

The native smoke test initially encountered an unavailable/zero-length installed library.
Once the supplied installation became readable, a fresh profile required a normal extension
registry synchronization/restart before its services appeared. The committed runtime checker
handles that first-profile restart; the final full native run passed. This result verifies
service deployment and image decoding, not the future visible ribbon widget.

## Remaining steps

1. **Maintainer: set the separate banner public key** in `banner_verify.PUBLIC_KEY` before
   releasing the client. The explicit empty TODO placeholder rejects online/cached signatures
   and makes no banner requests; installed defaults remain available. Publish signed bytes at
   the documented endpoint after the server is built. No further client code is needed once
   the production public key has shipped.
2. **Next engineer: add the C++ notebookbar widget** in Writer, Sheets and Slides using the
   registered XJob service. Reserve 360×104 logical px, render the selected PNG, rotate with
   the supplied interval, and open `click_url_with_utm` only on activation. Include focus,
   accessibility and DPI behavior described in the integration guide. The current screenshot
   is a placement mockup; this delivery does not claim the native widget already exists.
3. **Brand follow-up:** supply a verified HST Post logo and repair its destination's TLS
   certificate when available. The permitted wordmark fallback is usable now.

The product release stamp was not changed. Nothing was pushed.
