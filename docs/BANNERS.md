# HASON TECH solution banners

The shared banner set is available to Writer, Sheets (Calc) and Slides (Impress).
It consists of artwork, bundled content, the signed feed, profile cache, a registered UNO interface
and the [native ribbon widget](#ribbon-widget).
There is no hide preference, administrator disable policy or per-app selection. Clicks and displays are counted
per banner and day, without any machine ID ([Click counting](#click-counting), [Display counting](#display-counting)).

## Artwork and regeneration

[Preview at 1× and 2×](design/banners-preview.png) · [Writer placement](design/banner-on-writer.png)
· [Logo sources and hashes](../assets/banners/SOURCES.md).
The Writer image is the approved placement mockup on a real screenshot; the implemented widget
follows it, see [Ribbon widget](#ribbon-widget).

Each card is 360×104 CSS px with an 8px corner radius, a thin tinted border and a light
brand-colour background. PNG outputs are 360×104, 720×208 and 1080×312.
The six product names and taglines come verbatim from [solutions.json](../data/hst/solutions.json).
The seventh card, HASON TECH itself, uses owner-approved copy and homepage palette tokens recorded in
[brands.json](../extensions/hst-vietnamese-tools/banners/brands.json) and the logo sources document.
It uses the family layout: a small, unmodified logo beside “HASON TECH”, followed by
“Công nghệ tạo giá trị” and “Giải pháp chuyển đổi số toàn diện” on separate lines.
“Khám phá hệ sinh thái →” sits bottom-left and “hasontech.vn” bottom-right;
the minimum added-text contrast is 5.93:1.
Be Vietnam Pro is bundled with its [OFL licence](../extensions/hst-vietnamese-tools/banners/fonts/OFL.txt).
Names are 18px, taglines 12.5px, CTA and company endorsement 12px. The renderer asserts
at least 4.5:1 contrast for all added text against both gradient endpoints, font readiness,
loaded logos and a maximum of two tagline lines. Original logo colours are preserved.
HST Post uses the square HS mark beside its large name and a deep forest green `#245c2a`
palette (7.96:1 on white, 7.29:1 on the pale-moss `#f2f7e8` background). All added text
achieves at least 5.88:1. Its warm green hue is 80.60° away from eChatbot's blue
`#0b6fc1`. eChatbot uses the official robot PNG with navy `#172b3f` ink and pale
blue-grey `#f3f6f9` tint (13.32:1 ink contrast); the logo sources document records
its similarity to HST SEO blue and the visual-review recommendation. The eChatbot
source update requires regeneration of the banner PNGs, manifests and preview.
Wide cards opt into artwork through the `illustration` filename in `brands.json`, resolved
under `banners/logos/`. eChatbot keeps its official chibi mascot unchanged. The other six
cards use original glossy 3D `<id>-illustration.png` assets: 312×312 RGBA PNGs with transparent
backgrounds, each under 110 KB. Each illustration occupies a 104px square at the right,
with a 10px gap from the 230px text column. The new illustrated cards balance tagline lines;
the company CTA uses slightly tighter letter spacing to retain its footer gap.
The renderer checks text/illustration separation. The 160×104 compact cards omit illustrations
to preserve readable text. Regenerate the PNGs, manifests and previews after changing these inputs.
HST Post's full logo derives
from the owner-supplied official 476×393 file, with extracted all-caps dark lettering.
[Logo comparison](design/hst-post-logo-preview.png) shows the logo, square icon and original together.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-templates.lock
.venv/bin/pip install playwright==1.64.1
.venv/bin/playwright install --with-deps chromium
.venv/bin/python scripts/brand/render-hst-post-logo.py
.venv/bin/python scripts/brand/render-hst-post-logo.py --check
.venv/bin/python scripts/brand/render-banners.py
.venv/bin/python scripts/brand/render-banners.py --check
```

The [renderer](../scripts/brand/render-banners.py) uses the committed
[HTML template](../extensions/hst-vietnamese-tools/banners/template.html), logos,
fonts and palette. Rendering itself is offline. It writes 42 PNGs (wide and compact), both previews,
the bundled manifest and the complete online example. `--check` compares regeneration
byte-for-byte (use the pinned Playwright Chromium on Linux for the reference output).
`generatedAt` for bundled artwork is intentionally fixed in the renderer; update it when
revising that set. The separate logo renderer reproduces the owner-requested vector trace and outlined replacement lettering.

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
| `generatedAt` | Required real UTC date/time, exactly `YYYY-MM-DDTHH:MM:SSZ`. A generation below the highest authenticated current/previous metadata is rejected, independent of image availability. Equal timestamps require identical manifest bytes. |
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
PNG, JPEG and WebP are identified from bounded headers, never the filename or Content-Type.
Size, SHA-256 and exact per-scale dimensions (360×104, 720×208, 1080×312) are checked before
publication and cache loading. Malformed headers, APNG/animated WebP and unsupported JPEG frames
are rejected. The widget receives the exact verified immutable bytes, with no cache pathname to reopen.
Native image loading must handle decoder failures gracefully. PNG is recommended for VCL compatibility.
Publish at the three standard dimensions and retain ≥12px Vietnamese copy at 1×.

## Publishing to system.hasontech.vn

The online example already contains correct sizes and hashes for the committed PNGs:
copy `extensions/hst-vietnamese-tools/banners/*@?x.png` to the server's
`/hst-office/banners/` directory, and use the example as `banners.json`.
It lists all six current solutions followed by the company card; e.g. AIOS `image.2x.url` is
`https://system.hasontech.vn/hst-office/banners/aios@2x.png`.
To change a campaign, update images, hashes, sizes, copy, order and optional windows together;
set `generatedAt` to the new UTC publication timestamp. Upload immutable images first,
then publish the manifest/signature pair atomically. Serve raw bytes without compression
or JSON rewriting. A temporary mismatch is rejected and local content continues.

A **separate banner public key must be set before releasing the client** in
[banner_verify.py](../extensions/hst-vietnamese-tools/python/hst_office/banner_verify.py),
replacing the explicit empty placeholder with `bytes.fromhex("<64 hex digits>")`.
Until then the client shows installed defaults and rejects all online/cache signatures;
it makes no banner network requests. Noncanonical, identity, small-order or mixed-order keys also
follow that bundled-only path. The signing tool validates the public key before reading any private seed.
The package release gate is `python3 scripts/check-extensions.py --require-banner-key`; it rejects
the empty placeholder as well as invalid keys. Normal development checks allow the empty placeholder. This intentional release prerequisite is not an
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

## Click counting

Every banner `url`, bundled and online, is `https://system.hasontech.vn/hst-office/go/<id>`. The server adds to a total per banner and day, stores no IP address, and answers 302 to the solution page with the three UTM parameters. Only a user click opens this link in the browser. Displays are counted separately, see [Display counting](#display-counting). `data/hst/solutions.json` keeps the direct page for the welcome dialog and Start Center, which are not counted. An id added to the bundled set must be published on the server first, or its clicks go to https://hasontech.vn/ uncounted.

A click first checks that the counter answers, because the server-side fallback needs nginx to be up. Off the UI
thread, [banner_click.py](../extensions/hst-vietnamese-tools/python/hst_office/banner_click.py) sends one HTTPS HEAD to
`https://system.hasontech.vn/hst-office/banners.json`, never to `/go/<id>`, which would count a click. The deadline is
1.5 seconds in total, with the feed's proxy settings and plain `User-Agent`. **This probe is sent only on a user click
and carries no identifiers.** Any status below 500 opens the click URL. A connection, DNS or TLS failure, a timeout or
a 5xx opens `https://hasontech.vn` with the same three UTM parameters. Hosts other than system.hasontech.vn open
directly, without a probe. If the Python service is unavailable, the widget opens the URL as it is, so a click then
fails in the browser when the server is down. No error dialog appears, and clicks within one second of each other
open one browser tab.

## Display counting

Owner decision of 12/11/2026, from HST Office 1.0.2. The report below is contract v1 with the server.

**What one display is.** A card is drawn in a visible window (not minimized, the banner slot of the ribbon shown, its
image decoded) and stays there for at least one second. Each rotation to another card is a new display; a window that
keeps one card counts it once until the card changes. Redrawing the same card (rescaling, the switch between wide and
compact artwork, a one-item rotation) does not count again; a card replaced within the second is not counted. The
[widget](#ribbon-widget) checks at the start and at the end of the second, and again every second while a card waits
in a hidden slot or a minimized window. It then calls `org.hst.office.BannerFeed` with `NamedValue("Shown", id)` on a
short worker thread, so the UI thread never calls Python.

**Local counts.** [banner_impressions.py](../extensions/hst-vietnamese-tools/python/hst_office/banner_impressions.py)
adds the display in memory and merges the counts into `$(user)/hst-banners/impressions.json` at most every 60 seconds
(on that worker thread) and once when the office terminates. The file holds only the local day of the machine, the
banner id and a number: `{"schemaVersion":1,"days":{"2026-11-12":{"aios":34,"hst-post":12}}}`. It keeps at most 7 days
(today − 6 … today + 1, so a clock that was set back leaves no far-future day), 24 ids per day and 5000 per id and day.
Writes are atomic under the kernel lock `impressions.lock`, shared by every office process of the profile; a read-only
profile keeps the counts in memory only. While `SendInstallId` is off nothing is counted.

**Report.** [banner_impressions_report.py](../extensions/hst-vietnamese-tools/python/hst_office/banner_impressions_report.py)
sends the stored counts within the feed's attempt of at most once per 86,400 seconds (the same stamp and lock, after
the stamp is claimed and before the manifest request), on the feed worker, through the private helper with the same
five-second deadline and proxy settings:

```http
POST https://system.hasontech.vn/hst-office/impressions
Content-Type: application/json
User-Agent: HSTOffice/1.0.2

{"schemaVersion":1,"release":"1.0.2","days":[{"day":"2026-11-12","counts":{"aios":34,"hst-post":12}}]}
```

This is the whole report: the release, days and counts. It carries no install ID or other machine ID, no account,
OS (other than the User-Agent), document, window or time of day, and no cookie or Referer. The body is at most 8 KiB;
the oldest days are left out until it fits. Redirects are not followed. The server keeps totals per banner and day and
does not store the IP address. Answer handling:

| Answer | Stored counts |
|---|---|
| 2xx (received; unknown ids are ignored by the server) or 400 (schema refused) | the sent counts are removed; displays counted meanwhile stay |
| 413 | the oldest sent day is removed |
| 429, 5xx, any other status, no answer (DNS, TLS, timeout, redirect) | kept for the next daily attempt, until they are 7 days old |

**When nothing is sent.** No report is made when `SendInstallId` is false, without a valid banner public key (the
bundled-only path, which makes no banner requests at all), from test-stamped packages or with a `FeedURL` testing
override (counts stay local and expire), or when there is nothing to send.

**How to stop it.** Untick **Gửi mã máy ẩn danh khi kiểm tra cập nhật** in Công cụ ▸ Tùy chọn ▸ HST Office ▸ Cập nhật
(`/org.openoffice.Office.HSTUpdate/SendInstallId` = `false`; administrators can lock it, [UPDATE_ADMIN](UPDATE_ADMIN.md)).
Unticking stops counting and sending at once; ticking it again takes effect at the next start at the latest. Counts stored earlier
stay in `impressions.json` and are not sent while the box is unticked; they expire after 7 days, or delete the file.

## Runtime, cache and privacy

`onFirstVisibleTask` starts the `org.hst.office.BannerStartup` job. It captures the
profile path and proxy/config settings on the main thread, then starts a daemon worker.
The widget API also starts a due refresh, so later daily checks happen in long-running
sessions. Neither path performs network access or cache signature/image verification
on the UI thread. Installed content is read locally when the shared feed is created.
The package builder pre-serializes bundled images; workers pre-serialize verified remote/cache
images before publishing their state. Snapshot selection never base64-encodes images or runs
JSON serialization over their payloads. Uninstalled source-tree Python callers prepare the fixed
bundled set once during construction; installed UI callers load the prepared package data.

One attempt per 86,400 seconds, including failed attempts, across apps and processes
sharing the profile. A short directory lock protects an atomically written attempt stamp
**before** any request. A lock abandoned by a crashed process can be recovered after
60 seconds. A clock rollback does not trigger extra requests. HTTPS has a five-second monotonic total deadline
per request, including DNS, TLS, all redirects and body reads. A private Python subprocess performs
the request; at expiry the supervisor kills and reaps it, closing its connections and releasing
the feed worker. The child receives only URL, bounded limit, version and proxy configuration over
stdin, with no shell, user-site imports or command-line credentials. If the runtime has no usable
Python executable, refresh fails closed to local content; the UI receives the available snapshot immediately. A read-only/unavailable
profile prevents refresh and leaves installed defaults usable.

Only the expert config key `/org.hasontech.hstoffice.Banners/FeedURL` can override the
manifest endpoint for testing. Empty, non-HTTPS, credentialed, nonstandard-port or query-bearing
values are ignored. A valid HTTPS override may use a testing origin outside the content
allow-list, but signatures and every item/image URL still obey production rules.
There are no environment overrides, hide keys, administrator disable keys, app-specific
feeds or dependencies on update-check enable/disable preferences; only the display report follows `SendInstallId`
([Display counting](#display-counting)). Standard office proxy
settings are reused solely for transport.

Requests carry the plain `User-Agent: HSTOffice/<release>` and a generic Accept header.
No OS, device ID, account, document details, cookies, Referer or analytics events are sent.
The only report is the daily display counts ([Display counting](#display-counting)).
No click request is made by the feed. The widget opens the system browser only on a click.
The destination query contains exactly the `source` and `campaign` from the shared
`solutions.json` UTM block plus `utm_medium=banner`; previous query parameters are removed.
Failures log a fixed generic message, without exception details, URLs or profile paths.

Cache location: `$(user)/hst-banners/`, where `$(user)` is the office's user profile
(normally the `user` directory inside the installation profile). No writes go to the installation.
`current.json` atomically preserves exact manifest bytes (base64), the detached signature and
a separately signed last-eligible `fallback` envelope. Its authenticated generation is the rollback
floor even when images are missing. `previous.json` retains the prior authenticated generation
for metadata recovery;
`images/<sha256>.<png|jpg|webp>` holds verified image bytes. `last-attempt` stores only a timestamp.
`impressions.json` holds the display counts and `impressions.lock` is its kernel lock ([Display counting](#display-counting)).
Publication takes a kernel file lock shared across processes, rereads authenticated current/previous
metadata, compares the candidate with the highest generation, installs its verified images and
atomically replaces the current envelope (floor and fallback together). Equal timestamps with
different bytes are rejected; identical polls do not rotate away the eligible fallback. Consecutive
future-only generations preserve the last usable campaign and its images until superseded or
ineligible. Garbage collection retains current, previous and last-eligible image sets (up to
216 × 300 KiB). Downloads stay in memory until publication, so a failed worker cannot delete another
publisher's files. Kernel locks are released on process exit, never expired while a publisher is suspended.

The floor trusts the persistence of local profile metadata: an attacker able to delete/reset all
state can reset it. A second ordinary file cannot protect against that threat. Signatures still
protect authenticity, and downloaded/cache bytes are hashed and decoded from the same immutable buffer.
No signature, hash or cache read is performed by `current()`; workers publish a single state tuple,
which each snapshot captures once. A service snapshot failure selects installed content.

Selection is: eligible fresh online generation → eligible last verified cached generation
→ installed defaults. A verified online generation older than 24 hours can still act as
an offline cache. Time/version windows are re-evaluated on every snapshot. Expired or
ineligible content cannot blank the banner: selection proceeds to the next source.
Bundled defaults have no eligibility windows. Within a generation, sorted items appear once
in round one, then items with `weight≥2` in round two, etc., up to ten rounds (240 slots maximum).
Slots reference shared banners and immutable image buffers; weighting never duplicates payloads.
The service returns only the requested slot, with an aggregate **432 KiB** JSON response limit,
including its one base64 image and all metadata. This bound is independent of item count and
weights. The header uses fixed-width JSON whitespace, so changing only weights does not change
the response size for the same selected banner and scale.

## Ribbon widget

Implemented by [hst-ribbon-banner.patch](../patches/libreoffice/hst-ribbon-banner.patch)
(`sfx2/source/notebookbar/HstRibbonBanner.cxx`, `HstBannerGeometry.hxx`), a plain VCL control owned by
`NotebookbarTabControl`, for `notebookbar.ui` of Writer, Calc and Impress only (not Draw or the compact variants).

- **The slot adapts to the ribbon, never the reverse.** It is not part of the ribbon layout: height = height of
  the tab page that already holds the 2-row groups minus 2 px margins per scale step; width = height × 360/104,
  capped at 360 logical px; at the right end of the page, 4 px from the edge. The current page gets the remaining
  width minus an 8 px gap, so groups fold into their `»` menu as usual; the right-hand block of the tab folds first (`hst-ribbon-fold.patch`). Ribbon and group heights do not change.
- **Images never change the slot.** Any pixel size is aspect-fitted, centred, with a high-quality downscale cached
  per device size. The requested variant is the exact @1x/@2x/@3x for the device height, else the next larger one.
  Device scale = VCL DPI factor × cairo surface scale on gtk; 2 on macOS, where it cannot be queried from sfx2.
- **Hidden below 1280 logical px of window width**; the page gets its full width back and rotation stops.
- **Data:** a worker thread reads the installed defaults once for the first paint, then calls
  `org.hst.office.BannerFeed`; the UI thread never touches Python, the cache or the network. Results are posted to
  the main thread, which decodes the image. If the service fails, the widget reads `data/banners.json`,
  `data/solutions.json` and `banners/*` of the installed extension directly, applying the same UTM rule.
  A decoder error skips to the next entry, at most three times in a row.
- **Rotation:** a main-thread timer requests `Slot + 1` every `rotateSeconds`; paused while hovered or focused; 300 ms
  cross-fade, or a plain switch when `MiscSettings::IsAnimatedOthersAllowed()` is false (reduced motion).
- **Display counting:** a card change starts a one-second main-thread timer; a card that stood the whole second in
  view is reported once through `NamedValue("Shown", id)` on a worker thread ([Display counting](#display-counting);
  [hst-ribbon-banner-impressions.patch](../patches/libreoffice/hst-ribbon-banner-impressions.patch)).
- **Activation:** click, Enter or Space opens `click_url_with_utm` through `SystemShellExecute`, after the check in [Click counting](#click-counting).
- **Accessibility:** focusable with a focus ring; role `HYPER_LINK`; accessible name and tooltip `<name> — <tagline>`.
  VCL did not expose the notebookbar to assistive technology at all, so the patch reports it as a child of the
  work window, like the menu bar (`vcl/source/window/accessibility.cxx`), and appends a link child after the page
  tabs of a tab control (`vclxaccessibletabcontrol.cxx`). The whole ribbon is now reachable by screen readers.
- **Dark mode:** when the window or dialog colour is dark, the artwork sits on a light rounded card (`#F4F6F9`).

Checks: `tests/unit/test_ribbon_banner_geometry.py` compiles the geometry header from the patch.
`tests/runtime/check-ribbon-banner.py` drives the real GUI under Xvfb and gtk3 (needs a running display, and a second
one of at least 3000×1820 for `--display-hidpi`; `--baseline-instdir` compares with a build without the banner):

```sh
python3 tests/runtime/check-ribbon-banner.py --baseline-instdir /path/to/instdir-without-banner --display :93 --display-hidpi :94
```

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
    {u"Scale"_ustr, css::uno::Any(fDeviceScale)},
    {u"Slot"_ustr, css::uno::Any(nSlot)}}; // integer, initially zero
OUString json;
feed->execute(args) >>= json;
// Decode image_base64 to a bounded byte sequence; initialize SequenceInputStream.
// Pass that stream as InputStream to XGraphicProvider. Never reopen a cache pathname.
```

Input: optional `NamedValue("Scale", double)`, default 1. Selects the smallest raster
scale ≥ requested scale, clamped to 1…3 (1.25 selects 2×; 2.5 selects 3×).
Optional `NamedValue("Slot", integer)` selects one weighted rotation slot, default 0.
Nonnegative integers wrap modulo the current slot count; negative/noninteger values select 0.
Eligibility and slot selection use one coherent snapshot, including after campaign changes.
With `NamedValue("ClickUrl", string)`, the service instead returns the URL to open as a plain string
(see [Click counting](#click-counting)); it can wait 1.5 seconds, so call it on a worker thread.
With `NamedValue("Shown", string)` (a banner id), it counts one display and returns an empty string
(see [Display counting](#display-counting)); call it on a worker thread as well.
Otherwise the output is a UNO string containing JSON:

```json
{
  "rotateSeconds": 10,
  "slot": 0,
  "slotCount": 7,
  "items": [{
    "id": "aios",
    "name": "AIOS",
    "tagline": "Trợ lý AI cá nhân, như một trợ lý thực thụ",
    "click_url_with_utm": "https://aios.hasontech.vn?utm_source=hst-office&utm_medium=banner&utm_campaign=hst-office-1-0",
    "image_base64": "iVBORw0KGgo..."
  }]
}
```

`items` contains exactly one selected banner, regardless of weight. `slotCount` is the total
number of weighted slots and `slot` is the normalized requested index. This selected-slot
interface supersedes the earlier service response that embedded the entire weighted list.
The base64 string is abbreviated above; decode the complete value into the exact verified bytes.
Its decoded length is at most 300 KiB. Use `com.sun.star.io.SequenceInputStream.initialize` with
a byte sequence, then `GraphicProvider.queryGraphic` with an `InputStream` property. There are no
image paths or file URLs in the service output. Draw the selected
image inside a **360×104 logical px** slot on the far right beside the two-row notebookbar;
respect DPI, retain aspect ratio, and let the ribbon manage overflow of its existing controls.
Provide an accessible name/tooltip from `name` and `tagline`, a keyboard focus target and activation.
Use a normal main-thread timer with `rotateSeconds`; request `Slot = slot + 1` on each tick.
The service wraps the index against the current eligible rotation. Requery the same slot on
scale changes. No modal dialogs,
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
    data = banner.image_bytes_for_scale(1.5)  # immutable verified bytes, no filesystem reopen
    # banner["name"], banner["tagline"], banner["click_url_with_utm"]
```

`get_banners` retains the pure Python ordered list API. Each snapshot has one `Banner` mapping
and copied `images` map per unique eligible item; repeated weighted slots reference that same
mapping. Separate snapshots have independent maps, sharing immutable buffers and serialized variants;
`image_bytes_for_scale(scale)` is their Python method. `BannerFeed.current()` returns the
same snapshot without scheduling a refresh. Constructor injection of key/fetcher/clock is
for unit tests only; it is not exposed by UNO or office configuration.

Validation is in `tests/unit/test_banner_*.py`; tests use mocked fetches and throwaway keys.
The extension builder packages `data/banners.json` and the whole `banners/` tree. The package
validator rejects missing/corrupt images, stale manifests and missing font licensing, and
`banner_http.py` gets the narrow HTTPS-import exception; `banner_fetch.py` alone may spawn
its fixed private Python helper. Both remain forbidden to import raw sockets. Authored Python files
changed on the branch are also gated at 199 lines by `scripts/check-authored-lines.py`.

Runtime check (uses an isolated user profile; does not modify the office installation).
The full check allows one restart for first-profile extension registry synchronization
and decodes all returned PNGs using the native GraphicProvider:

```sh
URE_BOOTSTRAP=vnd.sun.star.pathname:/opt/hst/program/fundamentalrc PYTHONPATH=/opt/hst/program \
  python3 tests/runtime/check-banner-service.py --soffice /opt/hst/program/soffice
URE_BOOTSTRAP=vnd.sun.star.pathname:/opt/hst/program/fundamentalrc PYTHONPATH=/opt/hst/program \
  python3 tests/runtime/check-banner-service.py --boundary-only
```

The second command verifies real UNO NamedValue/JSON/verified byte-buffer conversion with injected profile
lookup; it does not replace the full native service registration check.
