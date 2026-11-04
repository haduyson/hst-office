# HASON TECH solution banners

The shared banner set is available to Writer, Sheets (Calc) and Slides (Impress).
The native ribbon widget is the next implementation step. This change supplies artwork,
bundled content, the signed feed, profile cache and a registered UNO interface.
There is no hide preference, administrator disable policy, per-app selection or telemetry.

## Artwork and regeneration

[Preview at 1× and 2×](design/banners-preview.png) · [Writer placement](design/banner-on-writer.png)
· [Logo sources and hashes](../assets/banners/SOURCES.md).
The Writer image is a placement mockup on the supplied real screenshot: it reserves the
right-hand slot and collapses the style gallery to one complete tile with its overflow
control. It is not evidence of an implemented C++ widget.

Each card is 360×104 CSS px with an 8px corner radius, a thin tinted border and a light
brand-colour background. PNG outputs are 360×104, 720×208 and 1080×312.
Names and taglines come verbatim from [solutions.json](../data/hst/solutions.json).
Be Vietnam Pro is bundled with its [OFL licence](../extensions/hst-vietnamese-tools/banners/fonts/OFL.txt).
Names are 18px, taglines 12.5px, CTA and company endorsement 12px. The renderer asserts
at least 4.5:1 contrast for all added text against both gradient endpoints, font readiness,
loaded logos and a maximum of two tagline lines. Original logo colours are preserved.
HST Post uses the approved typographic fallback because no verifiable product logo was found.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-templates.lock
.venv/bin/pip install playwright==1.64.1
.venv/bin/playwright install --with-deps chromium
.venv/bin/python scripts/brand/render-banners.py
.venv/bin/python scripts/brand/render-banners.py --check
```

The [renderer](../scripts/brand/render-banners.py) uses the committed
[HTML template](../extensions/hst-vietnamese-tools/banners/template.html), logos,
fonts and palette. Rendering itself is offline. It writes 18 PNGs, both previews,
the bundled manifest and the complete online example. `--check` compares regeneration
byte-for-byte (use the pinned Playwright Chromium on Linux for the reference output).
`generatedAt` for bundled artwork is intentionally fixed in the renderer; update it when
revising that set. No image generation or logo tracing is involved.

## Manifest contract (schemaVersion 1)

Production endpoint: `https://system.hasontech.vn/hst-office/banners.json`.
Detached signature: `https://system.hasontech.vn/hst-office/banners.json.sig`.
The `/hst-office/` namespace is fixed; no server implementation is required in this repository.

The [bundled manifest](../data/hst/banners.json) and
[complete online publishing example](../assets/banners/banners-online.example.json)
use the same schema. Only the image locator differs: installed defaults use relative
`banners/<id>@<scale>x.png` paths, while online and cached manifests require absolute HTTPS URLs.
Relative locators are never accepted from the network, even with a valid signature.

| Field | Contract |
|---|---|
| `schemaVersion` | Required integer `1`; booleans are rejected. |
| `generatedAt` | Required real UTC date/time, exactly `YYYY-MM-DDTHH:MM:SSZ`. An online generation older than the verified current cache is rejected. |
| `rotateSeconds` | Optional integer, default `10`, clamped to `5…60`. |
| `items` | Required array, `1…24` entries; IDs unique. An empty feed cannot blank the banner. |
| `items[].id` | Required `1…64` characters, `[a-z0-9][a-z0-9-]*`. |
| `name`, `tagline` | Required nonempty plain strings, at most 80 / 160 characters; no control characters. Publisher must keep artwork copy consistent and fit it within the card. |
| `url` | Required allowed HTTPS click destination. Existing query parameters are removed when building clicks. |
| `image` | Required object with exactly `1x`, `2x`, `3x`. Each is `{ "url": "…", "sha256": "…", "size": 12345 }`. |
| `image.*.url` | Allowed HTTPS URL online; restricted relative PNG path for installed defaults only. At most 2048 characters. |
| `image.*.sha256` | Required 64 lowercase hexadecimal digits over the exact downloaded bytes. |
| `image.*.size` | Required integer byte count, `1…307200` (300 KiB), exact match required. |
| `startAt`, `endAt` | Optional UTC timestamps with the same syntax. Start inclusive; end exclusive; start must precede end. |
| `minVersion`, `maxVersion` | Optional SemVer strings, at most 80 characters; inclusive endpoints, minimum ≤ maximum. Compared to HST product release, not the LibreOffice engine version. |
| `weight` | Optional integer `1…10`, default `1`. Deterministic weighted round robin, not profiling/random targeting. |
| `order` | Required integer `0…9999`; ascending, then ID for ties. |

Manifest limit: 65,536 bytes. Duplicate JSON keys, nonfinite numbers, invalid UTF-8, malformed
objects and unsupported schema versions are rejected. Unknown additional fields are ignored
within schema 1, allowing harmless publishing metadata. All image variants must validate
before the generation is published; no partial replacement of the visible set occurs.

Allowed item/image hosts: `hasontech.vn` and dot-separated subdomains (including
`system.hasontech.vn`), plus **exact** `echatbot.vn`, `espace.vn`, `aidelam.com`.
HTTPS only, port omitted or 443, no credentials, backslashes, whitespace/control characters
or fragments. Similar suffixes and subdomains of the three exact hosts are rejected.
Transport follows redirects only within the original scheme/host/port.
PNG, JPEG and WebP are identified by magic bytes, never the filename or Content-Type;
size and SHA-256 are checked before the widget receives a local image path. Native image
loading must handle decoder failures gracefully. PNG is recommended for VCL compatibility.
Publish at the three standard dimensions and retain ≥12px Vietnamese copy at 1×.

## Publishing to system.hasontech.vn

The online example already contains correct sizes and hashes for the committed PNGs:
copy `extensions/hst-vietnamese-tools/banners/*@?x.png` to the server's
`/hst-office/banners/` directory, and use the example as `banners.json`.
It lists all six current solutions; e.g. AIOS `image.2x.url` is
`https://system.hasontech.vn/hst-office/banners/aios@2x.png`.
To change a campaign, update images, hashes, sizes, copy, order and optional windows together;
set `generatedAt` to the new UTC publication timestamp. Upload immutable images first,
then publish the manifest/signature pair atomically. Serve raw bytes without compression
or JSON rewriting. A temporary mismatch is rejected and local content continues.

A **separate banner public key must be set before releasing the client** in
[banner_verify.py](../extensions/hst-vietnamese-tools/python/hst_office/banner_verify.py),
replacing the explicit empty placeholder with `bytes.fromhex("<64 hex digits>")`.
Until then the client shows installed defaults and rejects all online/cache signatures;
it makes no banner network requests. This intentional release prerequisite is not an
administrator switch. Once the key is embedded, the future server can publish without
any further client code changes.

The owner maintains the matching Ed25519 private seed outside the repository, separate
from the update key. The signing tool has **no default key path or environment fallback**,
requires an explicit path, checks permissions (0600 on POSIX), refuses the update key and
refuses a key that differs from the embedded banner public key. No real private key was
created or read for this implementation; tests generate throwaway keys in temporary directories.

```sh
python3 scripts/release/sign-banner-manifest.py /publishing/banners.json --key /secure/banner-signing.key
python3 scripts/release/sign-banner-manifest.py /publishing/banners.json --verify
```

Signature format matches the update mechanism: Ed25519 over the **exact UTF-8 manifest
bytes**, detached base64 ASCII, one line with an optional trailing newline. The signature
response is limited to 128 bytes. Verification precedes JSON/schema parsing. Installed
defaults are trusted via the packaged application, not signed with a fake/test key.

## Runtime, cache and privacy

`onFirstVisibleTask` starts the `org.hst.office.BannerStartup` job. It captures the
profile path and proxy/config settings on the main thread, then starts a daemon worker.
The widget API also starts a due refresh, so later daily checks happen in long-running
sessions. Neither path performs network access or cache signature/image verification
on the UI thread. The small installed manifest is read locally when the shared feed is created.

One attempt per 86,400 seconds, including failed attempts, across apps and processes
sharing the profile. A short directory lock protects an atomically written attempt stamp
**before** any request. A lock abandoned by a crashed process can be recovered after
60 seconds. A clock rollback does not trigger extra requests. HTTPS timeout is five seconds
per request; the UI receives the available snapshot immediately. A read-only/unavailable
profile prevents refresh and leaves installed defaults usable.

Only the expert config key `/org.hasontech.hstoffice.Banners/FeedURL` can override the
manifest endpoint for testing. Empty, non-HTTPS, credentialed, nonstandard-port or query-bearing
values are ignored. A valid HTTPS override may use a testing origin outside the content
allow-list, but signatures and every item/image URL still obey production rules.
There are no environment overrides, hide keys, administrator disable keys, app-specific
feeds or dependencies on update-check enable/disable preferences. Standard office proxy
settings are reused solely for transport.

Requests carry the plain `User-Agent: HSTOffice/<release>` and a generic Accept header.
No OS, device ID, account, document details, cookies, Referer or analytics events are sent.
No click request is made by the feed. The widget opens the system browser only on a click.
The destination query contains exactly the `source` and `campaign` from the shared
`solutions.json` UTM block plus `utm_medium=banner`; previous query parameters are removed.
Failures log a fixed generic message, without exception details, URLs or profile paths.

Cache location: `$(user)/hst-banners/`, where `$(user)` is the office's user profile
(normally the `user` directory inside the installation profile). No writes go to the installation.
`current.json` preserves exact manifest bytes (base64) and the detached signature;
`previous.json` retains the prior signed generation for overlapping schedules;
`images/<sha256>.<png|jpg|webp>` holds verified image bytes. `last-attempt` stores only a timestamp.
Images are installed before the atomic manifest swap. Successful publication retains current
and previous image generations (up to 144 × 300 KiB); normal failed downloads remove their
new partial images. Crash leftovers are collected on the next successful publication.
The cache signature, schema, sizes, hashes and magic bytes are checked on loading.

Selection is: eligible fresh online generation → eligible last verified cached generation
→ installed defaults. A verified online generation older than 24 hours can still act as
an offline cache. Time/version windows are re-evaluated on every snapshot. Expired or
ineligible content cannot blank the banner: selection proceeds to the next source.
Bundled defaults have no eligibility windows. Within a generation, sorted items appear once
in round one, then items with `weight≥2` in round two, etc., up to ten rounds (240 slots maximum).

## Integration for the ribbon widget

Use the already registered service **`org.hst.office.BannerFeed`**, implementing
`com.sun.star.task.XJob`. No new IDL or Python script-provider installation is needed.
Create it with the normal office component context and call `execute` on the main thread.
It shares the same feed instance with the startup job and all Writer/Calc/Impress frames.

```cpp
// With normal UNO headers and namespace alias css = com::sun::star.
css::uno::Reference<css::task::XJob> feed(
    xContext->getServiceManager()->createInstanceWithContext(
        u"org.hst.office.BannerFeed"_ustr, xContext), css::uno::UNO_QUERY_THROW);
css::uno::Sequence<css::beans::NamedValue> args{
    {u"Scale"_ustr, css::uno::Any(fDeviceScale)}};
OUString json;
feed->execute(args) >>= json;
// Parse JSON; load image_url into VCL/XGraphicProvider; keep all network work in the service.
```

Input: optional `NamedValue("Scale", double)`, default 1. Selects the smallest raster
scale ≥ requested scale, clamped to 1…3 (1.25 selects 2×; 2.5 selects 3×).
Output is a UNO string containing JSON:

```json
{
  "rotateSeconds": 10,
  "items": [{
    "id": "aios",
    "name": "AIOS",
    "tagline": "Trợ lý AI cho cá nhân, như một trợ lý thực thụ",
    "click_url_with_utm": "https://aios.hasontech.vn?utm_source=hst-office&utm_medium=banner&utm_campaign=hst-office-1-0",
    "image_path": "/installed/extension/banners/aios@2x.png",
    "image_url": "file:///installed/extension/banners/aios@2x.png"
  }]
}
```

Paths are illustrative; never hard-code an installation or profile path. `image_url` is a
proper UNO file URL; prefer it for native loading, particularly on Windows. Draw the selected
image inside a **360×104 logical px** slot on the far right beside the two-row notebookbar;
respect DPI, retain aspect ratio, and let the ribbon manage overflow of its existing controls.
Provide an accessible name/tooltip from `name` and `tagline`, a keyboard focus target and activation.
Use a normal main-thread timer with `rotateSeconds`, refresh the snapshot before choosing each
slot, keep index modulo the new list length, and requery on scale changes. No modal dialogs,
network activity on clicks, close button or hide preference. Handle native image decoder errors
without disturbing editing; retry another entry or the installed fallback asset.
The initial snapshot may be bundled while the worker checks cache/network; subsequent calls
pick up the new set automatically. There is no callback into UNO from the worker.

Python UNO callers use the same XJob service. Pure Python extension callers can use:

```python
from hst_office.banner_feed import BannerFeed, get_banners
feed = BannerFeed(profile_directory, installed_release)  # retain one instance per profile
snapshot = get_banners(feed)  # immediately returns {items, rotateSeconds}; starts due worker
for banner in snapshot["items"]:
    path = banner.image_path_for_scale(1.5)
    # banner["name"], banner["tagline"], banner["click_url_with_utm"]
```

`get_banners` returns a fresh ordered list of `Banner` mappings with copied `images` maps;
`image_path_for_scale(scale)` is their Python method. `BannerFeed.current()` returns the
same snapshot without scheduling a refresh. Constructor injection of key/fetcher/clock is
for unit tests only; it is not exposed by UNO or office configuration.

Validation is in `tests/unit/test_banner_*.py`; tests use mocked fetches and throwaway keys.
The extension builder packages `data/banners.json` and the whole `banners/` tree. The package
validator rejects missing/corrupt images, stale manifests and missing font licensing, and
only `banner_fetch.py` gets the narrow network-import exception for this feature.

Runtime check (uses an isolated user profile; does not modify the office installation).
The full check allows one restart for first-profile extension registry synchronization
and decodes all returned PNGs using the native GraphicProvider:

```sh
URE_BOOTSTRAP=vnd.sun.star.pathname:/opt/hst/program/fundamentalrc PYTHONPATH=/opt/hst/program \
  python3 tests/runtime/check-banner-service.py --soffice /opt/hst/program/soffice
URE_BOOTSTRAP=vnd.sun.star.pathname:/opt/hst/program/fundamentalrc PYTHONPATH=/opt/hst/program \
  python3 tests/runtime/check-banner-service.py --boundary-only
```

The second command verifies real UNO NamedValue/JSON/file URL conversion with injected profile
lookup; it does not replace the full native service registration check.
