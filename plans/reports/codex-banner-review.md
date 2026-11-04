# Independent banner security and code review

**Verdict: FIX-THEN-SHIP. Findings: 2 high, 5 medium, 1 low.**

Reviewed on 2026-11-04, branch `codex/banner`, at
`304deaf36c2d501a5e3aaf444c89b1fc8c734e2b`, including its parent
`d68a65e2b7ccd95ee9f6fa126b2066a5935bcb4d`. Read
[the delivery report](codex-banner.md) and [the contract](../../docs/BANNERS.md)
before examining implementation and tests. Product source was not changed.
The native checks used isolated profiles; `/opt/hst` was not modified.
Adversarial probes used temporary files and throwaway keys, with no production
feed requests or production private-key access.

The ordinary signature path, URL policy, bundled artwork and startup separation
are sound under the conditions described below. Passing tests do not establish
the stronger cache-integrity, rollback, image-allocation and timeout guarantees.
Fix the findings and add their regression cases before enabling the online feed.
The committed empty public key currently keeps the service on bundled content.
This review covers the delivered service and assets; the visible ribbon widget
remains unimplemented, as the delivery report correctly states.

## High severity

### R1. Verified image paths can later deliver unsigned replacement bytes

**Locations:** `extensions/hst-vietnamese-tools/python/hst_office/banner_cache.py:43`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_feed.py:128`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_uno.py:52`.

`cached_image()` verifies a file's bytes, closes it, and returns its mutable
pathname. Snapshots retain only paths. The UNO service later hands a file URL
to the consumer, which opens the path again. Neither signature verification nor
the filename's digest authenticates the bytes at that later open. An actor able
to replace a cached image after verification can substitute arbitrary artwork;
this is a local cache-write attack, not a remote Ed25519 forgery. Symlinks are
also followed. Atomic manifest publication does not close this image race.

**Reproduced:** loaded a correctly signed feed, replaced its cached AIOS 1× PNG
with the valid bundled HST Post PNG, then called `current()` again. It returned
the replaced path although its contents no longer matched the signed SHA-256.
The replacement is a decodable image with different artwork. A concurrent
replacement between `cached_image()` and native loading has the same result.

**Fix:** carry verified immutable bytes through to native decoding, for example
through a bounded byte sequence/input stream whose exact contents were hashed.
Do not hash one open and decode a second open of the pathname. If paths remain
in the interface, the native consumer must read once, verify those bytes against
authenticated metadata, then decode that same buffer. Rechecking only in
`current()` leaves another race. Keep this I/O off the UI thread. Add tests
replacing the file and a symlink target after verification but before decoding;
reject the substitute and select a usable cache/bundled asset.

### R2. Small signed images can trigger unbounded pixel allocations

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/banner_verify.py:28`.

The verifier enforces compressed byte size, SHA-256 and minimal magic bytes,
but never checks width, height, pixel count or animation/frame limits for PNG,
JPEG or WebP. It therefore passes potentially enormous images to the native
decoder. The signature authenticates the publisher, not the safety of an image
produced by that publisher or a compromised publishing pipeline.

**Reproduced:** constructed a structurally valid, CRC-correct, 1-bit grayscale
PNG with **30,000 × 30,000 = 900,000,000 pixels**, only **109,445 bytes** after
compression. With its correct declared size and digest, `verify_image()`
accepted it as `.png`. No large image was decoded during this review. The
300 KiB limit offers no meaningful bound on decoder allocation or work here.

**Fix:** inspect bounded format headers before cache publication/native loading
and enforce explicit width, height and total-pixel caps, preferably the exact
360×104, 720×208 and 1080×312 scale dimensions. Validate PNG IHDR, JPEG SOF and
WebP dimensions safely; reject unsupported animation or bound its total frames
and pixels. Fail closed on malformed headers. Add signed feed/cache tests for
each format, oversized dimensions, integer boundaries and tiny compressed bombs.
The existing bundled-only dimension assertions do not protect online images.

## Medium severity

### R3. `generatedAt` is not a durable, atomic rollback floor

**Locations:** `extensions/hst-vietnamese-tools/python/hst_office/banner_cache.py:48`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_feed.py:59`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_feed.py:72`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_cache.py:71`.

The comparison uses only `self._cached`, which is assigned only after every
cached image validates. A missing/corrupt image therefore erases the comparison
baseline on restart even when the current signed manifest remains intact.
`_previous` is not consulted for the maximum generation. The comparison also
uses a snapshot captured before downloading, without a publication lock or a
second comparison against the latest on-disk generation.

**Reproduced two paths:**

1. Cached the signed `2026-11-04` manifest, deleted one PNG, restarted at the
   next daily check, and served a valid signed `2026-11-03` manifest. The older
   manifest was accepted, displayed by the snapshot and written to `current.json`.
2. Paused worker A after its attempt claim, started worker B with the clock
   advanced by 86,400 seconds, let B publish `2026-11-05`, then released A's
   `2026-11-04` response. A overwrote B's newer generation. The probe simulated
   elapsed time; a suspended process or R5's unbounded transfer can create the
   corresponding real overlap. The attempt lock does not serialize publication.

**Fix:** retain the highest authenticated generation independently of image
availability and eligibility. Recover it from verified current/previous metadata
even when an image is missing. Under a publication lock, re-read the floor,
compare, and commit the new metadata/floor together. Define equal timestamps:
accept an identical manifest idempotently, reject different bytes with the same
generation. Test missing images, invalid current with valid previous, restart,
replay and overlapping workers. Deliberately selecting older eligible cached
content remains permissible; accepting it as a new generation must not lower
the floor. Protect/document the floor's storage trust boundary: an attacker who
can reset every local state file cannot be resisted by another ordinary file
in that same directory alone.

### R4. Repeated future campaigns erase the last eligible cached campaign

**Locations:** `extensions/hst-vietnamese-tools/python/hst_office/banner_cache.py:61`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_feed.py:88`.

Every successful poll copies `current.json` to `previous.json`, including an
identical current generation. After a future-only campaign becomes current,
the next successful poll overwrites the eligible previous campaign with that
same future-only campaign. `_previous = self._cached` repeats the loss in memory.
Garbage collection can then remove the useful older images too.

**Reproduced:** A is eligible on November 4; B is generated November 5 but all
items start November 10. Polling B on November 5 correctly keeps A visible.
Polling the identical B on November 6 replaces `previous.json` with B and the
snapshot falls back to bundled AIOS, although the formerly cached Online AIOS
campaign A is still eligible. This violates the documented last-eligible-cache
fallback order.

**Fix:** make publication of identical bytes idempotent, and track the last
usable generation separately from the newest scheduled generation. Preserve its
metadata and images until it is superseded by another usable generation or is
no longer eligible. Test multiple daily polls and restarts before a future
campaign starts, including distinct consecutive future-only generations and
different image hashes.

### R5. Five seconds is a socket inactivity timeout, not a request deadline

**Location:** `extensions/hst-vietnamese-tools/python/hst_office/banner_fetch.py:29`.

`opener.open(timeout=5)` followed by `response.read(limit + 1)` does not impose
a five-second total deadline. A server can keep the operation alive by sending
bytes at intervals below the socket timeout. Redirects and connection stages
can also consume separate timeout periods. The background worker retains its
refresh lock throughout, so a sufficiently slow response prevents later refreshes.
The UI does not wait on this network lock, which limits the direct UI impact.

**Reproduced:** a loopback HTTPS server with a temporary trusted test certificate
sent seven body bytes one second apart. The real `fetch()` returned successfully
after **7.011 seconds** with `TIMEOUT = 5`. This was not a mocked `read()`.

**Fix:** enforce a monotonic total request deadline across connection, redirects
and body reads, with cancellation/connection closure at expiry. Bound individual
reads by the remaining budget; a deadline check only after a blocking full-body
read is insufficient. If the transport cannot bound DNS/connection work, isolate
and cancel that work appropriately. Add slow-body and redirect-chain tests that
assert elapsed time and worker recovery. Update the documentation only if a
different, explicitly approved timeout contract is intended.

### R6. Snapshot reads race with worker publication and can raise into UNO

**Locations:** `extensions/hst-vietnamese-tools/python/hst_office/banner_feed.py:88`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_feed.py:113`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_uno.py:49`.

`current()` reads shared fields repeatedly without taking a coherent snapshot.
If current cache loading fails but previous cache loading succeeds, `_cached`
is `None` and `_previous` is a valid tuple. A successful refresh then assigns
`_previous = None`. Between the reader's truth test and its append, that change
can put `None` into `candidates`; tuple unpacking raises `TypeError`. The GIL
does not make these separate reads atomic, and `BannerService.execute()` does
not contain the exception.

**Reproduced:** used a real worker plus events and a Python line trace to pause
`current()` at line 114, after its truth test. Let the worker publish a future
generation and clear `_previous`, then resumed the reader. It raised
`cannot unpack non-iterable NoneType object`. The trace controlled scheduling;
product code was unchanged.

**Fix:** publish a single immutable state object and capture it once per
snapshot, or copy state under a separate, very short lock held only for state
reads/swaps. Never acquire the long network-worker lock on the UI path. Preserve
the fallback state as in R4 and contain service errors with a valid bundled
snapshot. Add a deterministic concurrent publication/snapshot regression test.
No UNO calls from the network worker were found; this is a shared Python state
race at the UNO boundary.

### R7. Key length alone does not make every invalid key fail closed

**Locations:** `extensions/hst-vietnamese-tools/python/hst_office/banner_verify.py:17`,
`extensions/hst-vietnamese-tools/python/hst_office/banner_feed.py:67`;
inherited verifier: `extensions/hst-vietnamese-tools/python/hst_office/ed25519.py:149`.

**The actual `PUBLIC_KEY = b""` placeholder is safe.** It rejects signed cache
and online content and makes zero requests. However, the new banner guards
accept any 32-byte value as a configured key. The reused verifier does not reject
small-order public points. Replacing the empty placeholder with an invalid
32-byte all-zero or identity-point value would enable unauthenticated feeds.
This is conditional on a bad embedded key, not an attack against a correctly
generated production key or the currently committed empty value.

**Reproduced:** with public key `01` followed by 31 zero bytes, the constant
64-byte signature `identity_point || 32_zero_bytes` authenticated **16/16**
arbitrary test manifests without a private key. An all-zero public key accepted
**2/16** in the recorded corpus. A full `BannerFeed` with the identity key
accepted and exposed an arbitrary manifest using the same forged signature.

**Fix:** validate configured keys as canonical, non-identity points in the
prime-order subgroup before any cache/network use; invalid keys must follow
the same bundled-only/no-request path as the empty placeholder. Keep the banner
key separate from the update key and add a release-time key-validation gate.
Test empty, wrong length, noncanonical, identity and other small-order keys,
alongside valid generated keys. Do not merely replace the empty placeholder
with 32 zero bytes to satisfy the length check.

## Low severity

### R8. Two touched authored Python files exceed the requested 199-line limit

**Locations:** `scripts/check-extensions.py:157`, `tests/unit/test_ui_language.py:74`.

The seven new production banner modules comply, but the package checker is
**279 physical lines** and the changed language test is **214**. The package
checker's own counting convention (`text.count("\n") + 1`) makes those **280**
and **215**. Both files already exceeded the limit before these commits
(254/212 physical lines); the reviewed changes enlarge them rather than
introduce the original threshold violations. CI only applies its line gate to
packaged Python, so it does not catch these authoring-limit exceptions.

**Fix:** extract package validation helpers and split the language test classes
into focused modules of at most 199 lines. Apply the gate to touched authored
scripts/tests as well, retaining all current assertions. This is a maintenance
finding, not a runtime security defect. The behavior change in `d68a65e` is
otherwise appropriate: it asserts the language menu's four intended contexts
instead of deriving them from the unrelated feature-search node.

## Checks that held and their limits

| Area | Review result |
|---|---|
| Manifest authenticity | Exact bytes are verified before schema parsing; no unsigned network manifest bypass with a valid generated key was found. Cached base64 manifest and signature share one atomic envelope. A mismatched old/new signature pair fails closed. R1 concerns reopening image files, not a split manifest/signature cache. |
| URL and redirects | `banner_urls.py:9` rejects non-HTTPS, credentials, bad ports, ASCII controls, backslashes and non-ASCII hosts. Dot-suffix matching is anchored; the other three domains are exact. A Unicode homograph and unrelated punycode host are rejected; punycode under a legitimate `hasontech.vn` subdomain remains inside that allowed domain. Each redirect and the final response must retain the initial scheme/host/port (`banner_fetch.py:14,30`), so an allowed image origin cannot redirect outside the allow-list. The documented expert feed-origin override is separate from image/click policy. No bypass found in 27 URL cases and 22 rejected redirect targets. Browser navigation after a user click is outside this feed transport's redirect enforcement. |
| Image bytes and paths | Compressed size and exact SHA-256 are enforced before initial publication/load. Format is identified by bytes rather than URL suffix or Content-Type. Network schema permits only 64 lowercase hex digest filenames plus a fixed verified extension; item IDs cannot supply traversal. Bundled locators use an anchored restricted PNG path. Pixel limits and later file replacement remain R2/R1. |
| Throttle | Stamp precedes network, includes failed attempts, and is guarded by atomic directory creation. An additional four-process probe produced exactly one claim; clock rollback and 86,399 seconds were denied, 86,400 allowed. Existing tests also cover restart/failure. This is attempt throttling, not a publication transaction lock (R3). |
| Startup and UNO | Network, cache reads and verification run in a daemon worker. The caller takes only a nonblocking worker lock. Profile/config/proxy access occurs on the calling UNO thread, and the worker does not call UNO. Existing blocked-fetch test passes. Initial small bundled-data/config reads are synchronous; this does not prove an absolute latency bound on arbitrary filesystem/config delays. R6 covers the snapshot race. |
| Privacy | Banner fetch sets `HSTOffice/<release>` and generic Accept, does not import the update mechanism's OS-bearing User-Agent, and has no cookies, Referer, identifiers, document/account data or telemetry hooks. Standard proxy settings are reused. Click construction replaces the entire query with exactly the shared source/campaign and `utm_medium=banner`. Fixed failure logging excludes exception details/paths. |
| Eligibility | Start inclusive, end exclusive, valid UTC calendar timestamps; inclusive SemVer bounds with prerelease comparison and reversed-range rejection. Every snapshot reevaluates windows, with installed defaults available. Fresh/cache/bundle selection works in the covered basic cases; repeated scheduled generations fail R4. `generatedAt` is publication ordering metadata, not an item activation window. |
| Empty placeholder | Direct verification, cached-content fallback test and an independent feed probe all fail closed: six bundled entries and zero requests. A forgotten empty placeholder disables online delivery, not authentication. Malformed 32-byte replacements are R7. |
| Module sizes | Physical lines for cache/feed/fetch/schema/UNO/URLs/verify: **105/136/37/106/71/41/41**; each also passes the checker's newline-plus-one convention. The built OXT has **62 Python modules**, maximum **198** by that convention. Authored script/test exceptions are R8. |
| Artwork and Vietnamese | All six names, taglines and URLs match `solutions.json` exactly. Visually checked the 1×/2× sheet: diacritics, “Tìm hiểu thêm →”, “AI Dễ Lắm”, wrapping and company endorsement are correct. All 18 PNGs have the declared hashes, sizes and scale dimensions. Offline regeneration reproduces all 22 outputs, linking the pixels to the source copy; no textual discrepancy found. |

## Test coverage and exact results

All commands completed at the reviewed code revision. Counts below overlap:
the standalone banner run repeats 42 tests included in the full quality run.

| Executed check | Exact result |
|---|---|
| `.venv/bin/python -m unittest discover -s tests/unit -p 'test_banner_*.py' -v` | **42 run, 42 passed, 0 failed/errors/skipped.** |
| All unit suites, executed individually by `bash scripts/ci-quality.sh` | **40 suites; 453 run, 452 passed, 1 skipped, 0 failed/errors.** |
| Brand suites, executed by the same quality run | **2 suites; 27 run, 27 passed, 0 failed/errors/skipped.** |
| `bash scripts/ci-quality.sh` | **54 commands, 0 command failures; 480 tests run = 479 passed + 1 skipped.** |
| Full `tests/runtime/check-banner-service.py --soffice /opt/hst/program/soffice` | **3 apps passed; 9 snapshots passed; 54 native GraphicProvider PNG decodes passed.** Each app checked scales 1, 1.5 and 3, six images per snapshot, file URLs, dimensions and banner UTM. |
| Same checker with `--boundary-only` | **3 scale snapshots passed; 18 local image paths checked.** Real UNO types with injected profile lookup; no native decodes in this mode. |
| `.venv/bin/python scripts/brand/render-banners.py --check` | **22 outputs reproduced byte-for-byte; 0 differences.** Contrast/font/layout checks passed. |
| `.venv/bin/python scripts/check-extensions.py --self-test` | **24 invalid packages rejected; 1 valid package accepted.** |

Native commands used
`URE_BOOTSTRAP=vnd.sun.star.pathname:/opt/hst/program/fundamentalrc`
and `PYTHONPATH=/opt/hst/program`. The OXT contains **196 entries**; its SHA-256
is `f2a2b079cd88c43818667d4860d57968152e1aa3fb39bb896beb687666732140`.

The one skipped unit test is
`test_shipped_dictionary_is_complete_after_merge`: the upstream LibreOffice
tree is absent. Successful platform preflights also report unavailable pinned
tarballs/upstream-tree checks and a macOS background dependency check; they are
not completed native platform validation. Renderer setup initially lacked
Playwright's Chromium and `libasound.so.2`; installing those container-only
dependencies allowed the final 22-output check to pass without asset changes.

The 42 banner tests cover normal signatures, malformed manifests, byte/hash/magic
checks, basic URL restrictions, time/version windows, basic cache fallback,
daily claims, offline behavior, UTM, signing and nonblocking fetch startup.
They do **not** cover any of R1–R7's reproduced failing cases:

| Existing test | Gap to close |
|---|---|
| `test_tampered_cached_image_rejected` | Tampers before constructing/loading a new feed; misses replacement after validation and before consumer decode. |
| `test_image_magic_types`, `test_bundle_copy_and_images` | Validates dimensions only for bundled PNGs; no hostile online dimensions, malformed format headers or frame limits. |
| `test_rollback_rejected` | Requires a wholly intact current cache; misses missing images, previous-only state and overlapping publication. |
| `test_future_generation_preserves_last_eligible_cache_on_restart` | Downloads one future generation, then makes the next fetch offline; never repeats a successful future-only response. |
| `test_plain_user_agent_timeout_bounded_read` | Asserts the mocked `timeout=5` argument, not elapsed time with slow network I/O. |
| `test_start_never_waits_for_network` | Proves nonblocking fetching, not a coherent concurrent state snapshot. |
| `test_placeholder_fails_closed`, `test_cached_signature_rechecked` | Tests the empty key only, not invalid 32-byte/low-order keys. |

`test_signature_before_schema` signs a malformed schema and observes schema
rejection; it does not instrument the parser to prove it is never called for
an invalid signature. The implementation order is correct on inspection, and
the additional altered-byte/mismatched-pair probes reject all three cases.
Future regression tests should assert that ordering directly.

Temporary review scripts/logs are under `/tmp/hst-banner-review/`:
`probes.py`, `overlap.py`, `race.py`, `slow_tls.py`, `policy_probes.py` and the
unit/quality/runtime/render logs. They are supplemental experiments, not added
repository tests and not included in the 480-test count. R1–R7 were reproduced
against unchanged code; R8 was established by source and package line counts.
Only this report is committed.
