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

## Review fixes

Owner follow-up and security review addressed on 2026-11-04. This revision includes the
requested HST Post derivative, updated shared copy, and fixes for all eight findings in
[the security review](codex-banner-review.md). The sections above record the original delivery;
the interface, artwork and validation results below describe this revision.

### Artwork and copy

- Corrected the company reference to the official owner-supplied 476×393 RGBA file,
  copied unchanged to `banners/logos/hasontech.png`. Both SOURCES.md copies record
  its provenance and pinned hash. This supersedes the earlier website-logo selection.
- Rebuilt `hst-post.svg`, transparent 512px/1024px PNGs, and the mark-only square SVG
  and 512×512 PNG from that source. The triangle keeps its original blue and geometry;
  regression tests require over 99.8% normalized silhouette overlap with the official file.
- Extracted H/S/T/O from the official all-caps italic wordmark and constructed P from
  O's bowl and H's stem. All lettering uses the source's single dark `#322e2e` colour,
  stroke weight, slant and spacing. Removed the superseded substitute font.
- The HST Post banner uses the square icon beside the product name, with a distinct
  violet `#6d28d9` accent. Banner and social renderers share one palette; violet text
  passes 7.10:1 on white and 6.36:1 on the pale violet tint.
- Regenerated all 18 banners, both manifests, logo/social assets and review sheets.
  The [Writer placement](../../docs/design/banner-on-writer.png) now shows HST Post;
  it remains a mockup, with the native ribbon widget a separate implementation step.

### Security and maintenance

| Finding | Change and regression evidence |
|---|---|
| R1 — mutable cached paths | Cache reads return the exact verified immutable bytes. Snapshots retain those bytes; UNO returns `image_base64`, and consumers decode that buffer through `SequenceInputStream` / `GraphicProvider.InputStream`. No cached pathname is reopened. Tests replace both a cached file and a symlink target after verification, confirm the in-memory bytes stay authentic, and confirm a restarted feed rejects the substitute. Native runtime checks decode the buffers in all three applications. |
| R2 — pixel allocations | Added bounded PNG IHDR/chunk/CRC, JPEG SOF/scan and WebP header inspection. Exact per-scale dimensions are mandatory. Malformed/truncated headers, unsupported frames and animation fail closed. Tests cover all three formats in signed feeds and cache, scale mismatch, integer extremes and a 900-million-pixel PNG compressed below 300 KiB, without decoding the bomb. |
| R3 — rollback floor | Recover the highest generation from signed current/previous metadata independently of images. Publication rereads that floor under a kernel file lock after downloads. An atomic current envelope commits the floor and eligible fallback together. Equal timestamps require identical bytes. Tests cover missing images, invalid current with valid previous, restart/replay, conflicting equal timestamps and overlapping workers publishing out of order. Documentation states that resetting all profile metadata can reset the floor. |
| R4 — scheduled fallback | The current envelope retains a separately signed last-eligible campaign. Identical polls do not rotate it away; distinct future-only generations preserve its metadata and image hashes. Tests poll across multiple days, restart offline, use differing artwork hashes and verify activation when the future window opens. |
| R5 — total deadline | A private Python HTTPS helper isolates DNS, connection, TLS, redirects and body reads under one monotonic five-second supervisor deadline. Timeout kills and reaps the child, closes connections and releases the feed worker. Real loopback HTTPS tests exercise slow bodies, redirect chains, blocked DNS and subsequent recovery. Package exceptions allow HTTPS only in the helper and subprocess only in its fixed-command supervisor; neither permits raw sockets. |
| R6 — snapshot race | Workers publish a single immutable state tuple and readers capture it once. Snapshot reads never acquire the network/publication lock. Errors in snapshot acquisition return installed content. An event-controlled concurrent publication test pauses a reader after capture, publishes a future campaign and resumes the reader successfully. |
| R7 — invalid keys | Validate canonical, nonidentity, prime-order public points before any cache/network use. Tests cover empty/wrong-length, noncanonical, identity, small-order and mixed-order keys, forged signatures and valid generated keys. Signing validates before reading a private seed. Package validation rejects invalid/non-separate keys; `check-extensions.py --require-banner-key` additionally rejects the development placeholder for release. |
| R8 — authored line limit | Extracted package content/contract helpers and split the language catalog tests while retaining their assertions. Added a gate for all changed authored Python, including scripts and tests, using the existing newline-plus-one convention. Its regression covers committed, edited and untracked files while excluding untouched legacy files. Quality CI fetches history and supplies the PR/push base so the gate covers the actual changes. |

### Revision validation

Counts overlap: the banner tests are part of the unit suites, and quality runs both unit and brand suites.
Unit, brand, quality and artwork regeneration checks were rerun after the official-source correction.
The native runtime rows below record the earlier integration checks; runtime code is unchanged.

| Executed check | Result |
|---|---|
| Unit suites in `scripts/ci-quality.sh` | **49 suites; 485 tests run, 484 passed, 1 skipped, 0 failures/errors**. Existing skip: upstream source tree absent. |
| Brand suites in the same run | **2 suites; 27 passed**. |
| `bash scripts/ci-quality.sh` | **64 commands, 0 failures; 512 tests run = 511 passed + 1 skipped**. Platform preflights report unavailable upstream/tarball inputs as before. |
| Full banner runtime check on `/opt/hst` | **3 applications, 9 snapshots, 54 native image decodes passed**, using verified byte streams; exact dimensions, hashes, taglines and UTM checked. Installation untouched. |
| Banner boundary-only check | **3 snapshots, 18 buffers checked**, using real UNO types with injected profile lookup. |
| `scripts/check-extensions.py` | **1 package passed**, 206 bundled files. |
| Package checker `--self-test` | **27 invalid packages rejected; 1 valid package accepted**. |
| Reproducible extension build | **PASS**, byte-identical SHA-256 `d1ac033d06688a9e99b12211ebe6a4f5140b112c67097fe7f9002c076cb7dc86`. |
| Banner renderer `--check` | **22 outputs identical**, contrast ≥4.5, no clipping. |
| Logo renderer `--check` | **6 outputs identical**. All three preview images visually inspected. |
| Authored Python gate | **36 changed files, 0 violations**. |

### Upstream availability

`git fetch` was attempted before implementation and retried. The configured origin is
`/home/office`, which does not exist in this isolated container; fetch fails with “does not
appear to be a git repository.” `git rebase origin/main` against the supplied local reference
`c22775b` reported the branch already up to date. No newer main reference or matching updated
copy was found among the local objects. The exact owner-supplied tagline was therefore applied
to `data/hst/solutions.json` locally and all generated content follows that file.

**Rebasing onto a freshly fetched main remains blocked on a reachable origin URL/path.**
The configured remote was not replaced with a guessed repository, and nothing was pushed.

## Review 2 fix

R9 addressed on 2026-11-04. Weighted rotation now references one banner and image map
per eligible item; repeated slots share immutable verified buffers and prepared responses.
Separate Python snapshots retain independent maps. Sorting, weighted round robin,
eligibility windows, fallback selection and coherent state capture are preserved.

The UNO service accepts an optional integer `Slot` (default zero) and returns exactly one
selected banner, its normalized `slot`, `slotCount` and `rotateSeconds`. Nonnegative slots
wrap against the current eligible rotation. The complete response is capped at **432 KiB
(442,368 bytes)**, independent of item count and weight. Fixed-width header whitespace
makes the same banner/scale response exactly equal in size when only weights change.
The integration guide and runtime consumer now use this selected-slot interface.

Workers prepare reusable JSON/base64 variants from the exact verified bytes before
publishing their state. The package builder prepares installed defaults, and package
validation rejects missing or stale prepared data. Uninstalled source-tree callers prepare
the fixed bundled set during construction. UI selection neither encodes images nor serializes
their payloads again; native decoding still consumes the verified buffer without reopening
cache paths. The earlier security regressions remain in the passing full suite.

### Regression evidence

The fixture uses a normally signed refresh with **24 distinct IDs, weight 10, and 72
distinct valid PNGs of exactly 307,200 bytes each**, at all three required dimensions.
Only fetch transport/profile lookup is substituted; no private feed state is injected.
Two behavioral regressions were run before product edits against starting HEAD `2478a78`:
**2 failed, 0 errors**. They detected a **98,365,232-byte** UI response and **240** separate
banner/image-map objects. The same assertions now pass: **24** unique objects, one image
per service response, and **409,937 bytes** at both weights 1 and 10, across all three scales.

The complete new suite has **6 passing tests**, also covering worker-only encoding for
remote/cache content, prepared installed defaults, rotation/wrapping/windows, fractional
scale selection, replacement of a verified cache file, independent snapshot maps and
enforcement of the aggregate response limit. Existing security tests cover the remaining
signature, cache, deadline and concurrency guarantees.

Measured scale-1 caller time for the regression fell from **1.028826 s to 0.001622 s**.
A separate real-UNO boundary probe passed **6/6** maximum-campaign cases, all **409,937
bytes**, with caller times **0.000469–0.004995 s**. These are container measurements,
excluding native marshaling and decoding, not universal timing guarantees. Tests gate
payload sizes, reference identity and absence of UI encoding rather than wall-clock thresholds.

### Validation counts

Counts overlap: the new regressions and banner suites are included in unit and quality runs.

| Check | Result |
|---|---|
| Full unit discovery | **491 run: 490 passed, 1 skipped, 0 failures/errors.** The existing skip is the absent upstream dictionary source tree. |
| New R9 regression suite | **6 run, 6 passed.** The two pre-fix behavioral tests both failed on the original HEAD. |
| `bash scripts/ci-quality.sh` | **65 commands, 0 failures; 518 tests run = 517 passed + 1 skipped.** Unit: **50 suites, 491 run**. Brand: **2 suites, 27 passed**. |
| Full native banner runtime | **3 applications, 54 bounded snapshots, 54 native image decodes passed.** Isolated profile; installation untouched. |
| Maximum-campaign real-UNO boundary | **6 snapshots passed**, weights 1/10 × scales 1/2/3; exact verified bytes preserved. |
| Package validation | **1 package passed; 206 entries, 66 Python modules, maximum 198 lines.** |
| Package checker self-test | **29 invalid packages rejected; 1 valid package accepted.** Includes missing/stale prepared snapshots. |
| Reproducible extension build | **2 builds byte-identical.** SHA-256 `505a9b61557fe199ba77349ad9d6b2125b47cd55e1f49ce5ad7c484c4fb182f9`. |
| Authored Python line gate | **40 changed files, 0 violations; maximum 184 lines.** All packaged modules remain below 200 lines. |
| Markdown links / whitespace | **99 Markdown files checked, 0 broken relative file links; `git diff --check` passed.** |

Quality retains its existing unavailable-input skips for pinned tarballs, upstream platform
checks and the macOS background dependencies. These are not native platform validations.

Logs for this fix are retained under `/tmp/hst-banner-r9/`, including
`regression-before.log`, `regression-after.log`, `unit.log`, `maximum-uno.log`,
`runtime.log`, `extensions.log`, `extensions-self-test.log` and `quality.log`.
