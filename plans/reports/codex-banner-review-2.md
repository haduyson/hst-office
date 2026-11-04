# Independent banner client review — follow-up

**Verdict: FIX-THEN-SHIP. Remaining findings: 0 high, 1 medium, 0 low.**

All eight findings in [the first review](codex-banner-review.md) are resolved.
The required positive checks pass, with one existing unit-test skip. A new
medium-severity performance defect, R9, prevents SHIP: weighted snapshots duplicate
large image buffers in JSON on the caller's thread.

Reviewed on 2026-11-04, branch `codex/banner`, at
`44acccc4e695602cc00ed9034b59463468c5a42d`. Scope was the complete 69-file diff from
`f560d45`, including `65554ef`, `de5c4ee` and `44acccc`, the existing feed contract,
its consumers, artwork and package validation. The baseline was checked out with
`git worktree add --detach /tmp/hst-banner-review-2/baseline f560d45`.
Product code was not changed in either checkout. Only this report is committed.
Native checks installed extensions in temporary user profiles; this review made
no changes to `/opt/hst`. Network experiments used loopback HTTPS and temporary
certificates; signatures used throwaway keys, with no production feed requests
or production private-key access.

## Findings by severity

### High: none remaining

R1 and R2 are closed with source inspection, positive regressions and behavioral
failures reproduced on the baseline, as detailed below.

### Medium: R9 — weighted snapshots multiply image payloads on the UI path

**Locations:**
[weighted expansion in banner_feed.py](../../extensions/hst-vietnamese-tools/python/hst_office/banner_feed.py),
lines 99–104;
[serialization in banner_uno.py](../../extensions/hst-vietnamese-tools/python/hst_office/banner_uno.py),
lines 47–57.

`_snapshot()` expands each item's weight into repeated `Banner` mappings.
`BannerService.execute()` then base64-encodes and embeds the entire selected
raster separately for every occurrence, followed by a synchronous `json.dumps()`.
Changing the interface from short file URLs to verified buffers correctly fixes
R1, but makes a permitted weighted feed expensive to obtain. This work happens
on the service caller's thread; the documented ribbon integration calls it from
the editing UI. Background fetching does not move this serialization off that path.

**Reproduced through the normal signed refresh and service boundary:** a valid
manifest with 24 distinct IDs, weight 10 each, and shared valid PNGs at all three
required dimensions. The manifest is 16,967 bytes, and image sizes are
112,588 / 260,723 / 294,941 bytes, all within the contract. `BannerFeed.refresh_async()`
verified the signature and images and published the cache normally. No private
feed state was injected. The test uses real UNO `NamedValue` and the product
`BannerService`, injecting only profile lookup so it can call the service locally.

| Measurement, scale 3 | `f560d45` | Reviewed HEAD |
|---|---:|---:|
| Returned weighted entries | 240 | 240 |
| Serialized UTF-8 JSON | 117,532 bytes | **94,442,812 bytes** |
| `execute()` elapsed time | 0.009 s | **1.668 s** |
| Process peak RSS before / immediately after `execute()` | 54,264 / 54,520 KiB | **70,048 / 347,296 KiB** |

These are measurements from this container, not universal timing guarantees.
RSS was recorded immediately after the call, before encoding/counting the result
for reporting. The measured time excludes native UNO marshaling, consumer JSON
parsing and image decoding. The 3× image alone is embedded 240 times. Thus a
schema-valid, correctly signed campaign can introduce substantial pauses and
memory pressure whenever the UI refreshes its snapshot. This is a robustness
problem in permitted first-party content, not an authentication bypass. The
committed empty key currently keeps online delivery inactive.

**Required fix:** avoid serializing one image per weighted occurrence. Carry
rotation order/weights separately from unique image buffers, or retrieve just the
selected item's verified buffer. Prepare reusable encoded data off the UI thread
and impose an aggregate snapshot-size bound. Preserve R1's requirement to decode
the exact verified bytes. Add a regression using the maximum supported item count,
weights and image sizes that asserts bounded payload size and no duplicate image
expansion; measure caller latency as well. The current runtime test exercises six
weight-one bundled entries and therefore does not expose this case.

Reproduction script and outputs:
`/tmp/hst-banner-review-2/snapshot_size.py`, `snapshot-size-head.log` and
`snapshot-size-baseline.log`. Both revisions used the same deterministic PNGs
and test script; each used its own matching bundled manifest as the starting fixture.

### Low: none remaining

R8 is resolved. No additional low-severity defect was established in the remaining
diff. The former language catalog assertions were moved intact into their own test
module, and package-checker extraction retains the existing validation rules.

## R1–R8: fix inspection and regression evidence

The committed security/maintenance regression selection ran **26 tests, all passed**.
The complete unit and quality runs also include them. Several tests use newly
introduced APIs such as `banner_store`, `_snapshot()` and `image_bytes_for_scale()`;
merely copying them onto the old revision would produce missing-API errors.

To establish behavioral failures, I ran one unchanged, version-compatible harness
on both checkouts. Its adapters normalize the old pathname/new buffer accessor,
loopback TLS injection and the trace location used to control reader scheduling;
they do not change product behavior or patch the fixes into the baseline.
**HEAD: 17 tests passed. Baseline: all 17 tests failed, with 19 assertion-failure
records because one test has three format subtests; 0 errors or skips.**
Missing imports/attributes are not counted as reproduced defects.

| Item | Fix inspected and committed tests run | Same-harness baseline → HEAD evidence |
|---|---|---|
| **R1 — verified paths reopened** | `banner_cache.cached_image()` returns the bytes it hashes; snapshots retain immutable bytes; `banner_uno.execute()` returns `image_base64`. `CacheSecurityTests.test_replacement_after_verification_cannot_change_decoded_buffer` and `test_symlink_target_replacement_after_verification` pass. | **2 failed → 2 passed.** Replacing a cached file or symlink target after verification changes the consumer's bytes on the baseline. HEAD retains the original digest, and a restarted offline feed rejects the substituted cache and selects bundled AIOS. Native runtime checks decode the returned buffers through `SequenceInputStream`, without reopening paths. |
| **R2 — pixel allocation bombs** | `banner_image` inspects bounded PNG/JPEG/WebP headers, exact scale dimensions, PNG CRCs and static-frame restrictions; verification occurs on download, publication and cache loading. All **6 `ImageSecurityTests`** pass, including valid formats/cache restart, wrong scale, malformed/truncated headers, animation and integer extremes. | **2 failed → 2 passed** (the second has PNG/JPEG/WebP subtests). The baseline accepts the 30,000×30,000 compressed PNG and publishes signed 1081×312 images in all three formats. HEAD rejects the bomb and publishes none of the oversized images. The bomb was never decoded. |
| **R3 — rollback floor** | `banner_store.metadata()` authenticates current/previous metadata independently of image availability. `publish()` rereads the floor inside the OS publication lock; equal timestamps require identical raw manifest bytes. The four missing-image, previous-only, equal-timestamp and overlapping-worker tests in `CacheSecurityTests` pass; `test_publication_lock_serializes_threads` also passes. | **4 failed → 4 passed.** Baseline replay succeeds after deleting an image or corrupting current metadata with previous metadata intact; equal-timestamp changed content replaces the cache; a delayed November 4 worker overwrites November 5. HEAD rejects each publication, preserving the recoverable floor and newest committed generation. |
| **R4 — future campaigns erase fallback** | `publish()` embeds a separately signed eligible fallback in the current envelope, commits it atomically with the newest metadata, and retains its image hashes during cleanup. `test_repeated_and_distinct_future_campaigns_preserve_eligible_cache` and `test_idempotent_poll_keeps_metadata_and_previous` pass. | **2 failed → 2 passed.** Baseline's repeated future poll changes previous metadata and loses the November 4 campaign on day 6. HEAD preserves identical metadata on an idempotent poll, survives restarts and a distinct future generation with different image hashes, and selects the new campaign when November 10 arrives. |
| **R5 — inactivity timeout** | `banner_fetch` supervises the fixed isolated `banner_http.py` helper under one monotonic budget, kills/reaps it on expiry, and releases the feed worker in `finally`. All **4 `DeadlineTests`** pass: slow body/recovery, redirects, blocked DNS and refresh-lock recovery. | **2 failed → 2 passed.** With the same shortened one-second budget, baseline slow-body and redirect requests last **3.818 s / 3.965 s**; HEAD raises `TimeoutError` at **1.004 s / 1.004 s**, reaps/closes the child and completes a subsequent request. An additional probe inside the actual HST Python runtime used the unmodified five-second deadline: **5.007 s**, followed by successful recovery. |
| **R6 — incoherent snapshot** | Workers assign one `_state` tuple; readers capture it once without the network/publication lock. `get_banners()` contains acquisition errors with bundled fallback. Both **`SnapshotSecurityTests`** pass. | **2 failed → 2 passed.** An event/trace-controlled reader pauses at candidate capture while a real worker publishes. Baseline raises `cannot unpack non-iterable NoneType object`; HEAD returns the coherent previous campaign. A separately injected snapshot failure escapes on the baseline but returns all six usable bundled entries on HEAD. |
| **R7 — malformed public keys** | `valid_key()` requires a canonical, nonidentity prime-order point before cache/network access. Both **`KeySecurityTests`** and both **`ReleaseGateTests`** pass: empty/wrong-length, noncanonical, identity, small-/mixed-order keys, valid signatures and release validation. The signing script checks validity before private-seed access. | **2 failed → 2 passed.** The baseline authenticates the identity-point constant-signature forgery and makes requests with that invalid configured key. HEAD rejects the forged manifest and makes **zero requests**. The separate release-gate negative check rejects the committed empty placeholder as intended. |
| **R8 — authored line limit** | Package validation moved into `extension_content.py` / `extension_contract.py`; language catalog tests moved into `test_ui_language_catalog.py`. `AuthoredLinesTests` verifies committed, edited and untracked files, explicit/event base, and untouched-legacy exclusion. CI fetches full history and supplies the event base. | **1 failed → 1 passed.** Using the repository's newline-plus-one convention, checker/language-test counts fall from **280/215** to **117/167**. Extracted helpers/catalog are **147/73/60** lines. The branch gate checks **37 changed authored Python files, 0 violations**. |

The rollback floor retains the documented local-storage trust boundary: resetting
all authenticated profile metadata can reset the floor. The fix does not claim a
hardware-backed or server-side monotonic counter.

## Remaining diff, artwork and image-loader boundary

- Independently opened and fully decoded **18/18 banner PNGs**. Their hashes and
  lengths match both manifests, their dimensions are exactly **360×104, 720×208,
  1080×312**, and they are static RGBA PNGs. Sizes range from **20,727 to 147,042
  bytes**, below **307,200 bytes**. All six names, taglines and destinations match
  `solutions.json`, including the revised AIOS copy.
- The committed company logo matches the available owner-supplied
  `banner-inbox/local/hasontech-official-logo.png` byte-for-byte: **476×393 RGBA**,
  SHA-256 `2f77a5fce52a515d52333cca3879a0aec18e582628a7111c00a05714b1c4d2ef`.
  The two provenance documents match. All **6 artwork tests** pass, including mark
  silhouette, extracted lettering, transparent derivatives and palette propagation.
  Visually inspected the banner, logo-comparison and social preview sheets: the
  official blue mark, dark HST POST lettering, Vietnamese accents and wrapping
  are preserved. HST Post uses violet `#6d28d9`, distinct from HST SEO's blue;
  measured renderer contrast remains at least 4.5:1.
- Regeneration passes byte-for-byte: **22 banner outputs**, **6 logo outputs** and
  **9 social outputs**. The social JPEG is **81,127 bytes**, below its separate
  **300,000-byte** limit. Social PNGs have their documented dimensions; the largest
  is **241,785 bytes**. Standalone web JPEG/SVG assets and design preview sheets are
  outside the ribbon PNG contract. The social directory is absent from the OXT.
- SVG logo sources are included for regeneration, but none is a feed image locator.
  Bundled locators are restricted to controlled PNG paths; remote/cache images pass
  the raster inspector before becoming snapshot bytes. SVG, HTML, GIF and fake
  raster headers are rejected by the contract tests. **Only raster bytes reach
  the banner image loader**; the runtime check supplies PNG `InputStream`s and
  verifies hashes and decoded dimensions. The byte-buffer API is reflected in the
  integration documentation and runtime consumer.
- Transport preserves HTTPS, same-origin redirects, bounded reads, generic headers,
  proxy handling and fixed error messages. The helper uses a fixed absolute script,
  `-I -S`, no shell and no user-supplied executable. Package checks limit network
  imports to the transport and subprocess access to its supervisor. An isolated
  native probe confirmed interpreter discovery as `/usr/bin/python3.12`, a real
  loopback HTTPS GET, timeout cancellation and a successful follow-up GET inside
  HST Office. Windows/macOS execution was not available in this Linux container.

## Executed checks and exact counts

Counts overlap: the focused regressions, banner tests and artwork tests are
included in the full unit run; quality reruns the unit and brand suites.
Expected baseline failures and negative release-gate results are not positive
validation failures.

| Executed check | Exact result |
|---|---|
| `.venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py' -v` | **485 run: 484 passed, 1 skipped, 0 failures/errors.** |
| Unit suites inside `bash scripts/ci-quality.sh` | **49 suites; 485 run: 484 passed, 1 skipped.** Includes **73 banner tests**, all passed. |
| Brand suites inside quality | **2 suites; 27 run, 27 passed.** |
| `bash scripts/ci-quality.sh` | **64 commands, 0 command failures; 512 tests run = 511 passed + 1 skipped.** |
| Focused committed R1–R8 regression suites | **26 run, 26 passed, 0 failures/errors/skips.** |
| Shared behavioral harness on HEAD / baseline | **17/17 passed on HEAD; 17/17 failed on baseline (19 assertion records), 0 errors/skips.** |
| Full `check-banner-service.py --soffice /opt/hst/program/soffice` | **3 applications passed; 9 snapshots passed; 54 native PNG decodes passed.** |
| Same runtime checker with `--boundary-only` | **3 snapshots passed; 18 verified buffers checked.** No native decodes in this mode. |
| `scripts/check-extensions.py` | **1 package passed**, **204 entries**, **65 Python modules**, maximum **198 lines** by checker convention. |
| `scripts/check-extensions.py --self-test` | **27 invalid packages rejected; 1 valid package accepted; 0 unexpected outcomes.** |
| `scripts/check-extensions.py --require-banner-key` | **1 expected rejection:** empty development key; confirms the release gate. |
| Renderer checks | **22 + 6 + 9 = 37 outputs reproduced; 0 differences.** |
| Authored Python gate / whitespace | **37 changed files, 0 line violations; `git diff --check` passed.** |

The tested rebuilt OXT SHA-256 is
`599b6135e8233e4bc51322cb95210584a6bb9e3651f8cd44ba600f92ab96bbeb`.
These independently observed package/count results supersede the earlier delivery
report's recorded build. The installed HST executable identifies as
**1.0.0-beta.4.1**; the reviewed extension carries the repository's
**1.0.0-beta.5** release data.

The sole skipped unit test is `test_shipped_dictionary_is_complete_after_merge`
(upstream LibreOffice source tree absent). Quality preflights also explicitly skip
unavailable pinned tarballs/upstream checks and the macOS background dependency
check; these are not completed native platform validations.

Initial renderer attempts lacked Chromium and `libasound.so.2`; installing those
container-only dependencies allowed all final renderer checks to pass without
changing generated assets. Initial native attempts encountered a connection failure
and a temporarily unreadable `/opt/hst/program/libmergedlo.so` (`file too short`).
The installation subsequently became readable without reviewer changes, and the
final full runtime and native transport runs passed. Both failed attempts and
successful final logs are retained; no native success is inferred from a unit mock.

The empty banner public key intentionally restricts this revision to bundled
content. Configuring the separate production public key and passing the release
key gate remains the documented release prerequisite. The visible C++ ribbon widget
also remains a separate implementation; service tests do not claim it exists.
Neither point is a newly introduced defect. **R9 must be fixed and regression-tested
before this client receives a SHIP verdict.**

## Reproduction artifacts

Temporary scripts, logs and baseline worktree remain in
`/tmp/hst-banner-review-2/`. The shared regression harness SHA-256 is
`782452fac5f5427e1665ec7807a28ec1506886086853b0097df61b9054623409`.

```sh
# The exact same test file against each checkout:
REVIEW_ROOT=/work /work/.venv/bin/python /tmp/hst-banner-review-2/regressions.py
REVIEW_ROOT=/tmp/hst-banner-review-2/baseline /work/.venv/bin/python /tmp/hst-banner-review-2/regressions.py

# Committed focused regressions (run from /work):
PYTHONPATH=tests/unit .venv/bin/python -m unittest \
  test_banner_cache_security test_banner_image_security test_banner_deadline \
  test_banner_snapshot_security test_banner_key_security test_banner_release_gate \
  test_authored_lines -v

# R9 measurement; substitute the baseline directory for REVIEW_ROOT to compare:
REVIEW_ROOT=/work URE_BOOTSTRAP=vnd.sun.star.pathname:/opt/hst/program/fundamentalrc \
  PYTHONPATH=/opt/hst/program .venv/bin/python /tmp/hst-banner-review-2/snapshot_size.py
```

Main logs: `unit-discover.log`, `quality.log`, `committed-regressions.log`,
`regressions-{head,baseline}.log`, `runtime-final.log`, `boundary.log`,
`native-transport-final.log`, `extensions.log`, `extensions-self-test.log`,
`assets.log`, `*-render.log` and `snapshot-size-{head,baseline}.log`.
