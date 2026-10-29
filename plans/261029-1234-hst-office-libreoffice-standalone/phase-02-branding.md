# Phase 02 — Complete standalone HST branding

**Status:** pending. **Depends on:** 00; executable checks need 01. **Parallelizable:** assets and patch authoring only; coordinator applies patches serially.

## Context and requirements

Existing seven PNG outputs and immutable owner logo are retained. A configure product name alone does not rename Calc/Impress, desktop launchers, About actions or installer resources. All user-visible product identity must be HST; truthful credits and required license notices remain.

## Exact files

- Modify `scripts/generate-brand-assets.py`, `assets/brand/brand-spec.json`, `tests/brand/test-brand-assets.py`, `docs/BRAND.md`.
- Create `branding/libreoffice/intro.png`, `about.svg`, `logo.svg`, `progress.conf`; `branding/linux/hst-office.desktop`, `hst-writer.desktop`, `hst-sheets.desktop`, `hst-slides.desktop`; `branding/credits.html`, `branding/help/index.html`, `branding/brand-audit-allowlist.json`.
- Generate `assets/brand/icons/hst-office-{16,24,32,48,64,128,256,512}.png` and corresponding `hst-writer-`, `hst-sheets-`, `hst-slides-` sizes; preserve old filenames for existing tests. Create `scripts/check-branding.py`, `patches/libreoffice/series`, `patches/libreoffice/hst-product-branding.patch`.
- Integration request to coordinator: product/vendor/brand path in `build-config/linux-x86_64.conf`. Verified pinned owners: `configure.ac`, `instsetoo_native/util/openoffice.lst.in`, `instsetoo_native/CustomTarget_setup.mk`, `officecfg/registry/data/org/openoffice/Setup.xcu`. Inspect `sysui/desktop/`, `cui/source/dialogs/about.cxx`, `desktop/source/app/`, `sfx2/source/dialog/` (locations require pinned-tree confirmation). Patch manifest records exact changed upstream files after inspection.

## Steps

1. Generate splash/About/logo images from the owner assets without redrawing the mark; preserve original SHA. SVG wrappers may embed the approved raster at suitable resolution. Pinned configure requires `intro.png`, `about.svg`, `logo.svg`; missing files silently fall back to upstream marks, so validate all three. Add desktop/module icon sizes, transparent padding and dark/light contrast tests.
2. Configure `--with-product-name='HST Office'`, `--with-vendor='HASON TECH'`, `--with-branding=/home/office/branding/libreoffice`, and `--enable-release-build` to prevent an unexpected `Dev` suffix. [Pinned configure](https://raw.githubusercontent.com/LibreOffice/core/libreoffice-26.8.1.1/configure.ac) documents `--with-package-version` for custom **macOS** builds; keep the supported numeric engine version and set Linux HST package revision separately in 07. Do not assume that flag determines Debian names/version ordering.
3. Patch resource/config labels for HST Writer/Sheets/Slides, Start Center, title bars, application menus, welcome pages, splash, About, crash/update dialogs and OS metadata in both vi/en. Preserve internal UNO service names, filter IDs and file-format identifiers. Remove extra module launchers without removing internals needed for charts/drawings/equations.
4. About shows HST version, exact engine tag/SHA, **based on LibreOffice**, upstream contributors/licenses, HST changes/source access and HASON TECH contact from the brief. Keep legal attribution offline and readable. Replace TDF donate/get-involved/marketing actions with appropriate local HST help or `https://hasontech.vn`; retain authoritative source/license links inside credits. Never fabricate a support or update service.
5. Use HST executable entry points, desktop filenames, icon names, MIME association declarations and package identifiers. Avoid hijacking upstream `libreoffice` command or existing default MIME choices. Patch bootstrap generation in `instsetoo_native/CustomTarget_setup.mk` and the installer path so Linux `UserInstallation` resolves to `$SYSUSERCONFIG/hst-office/4` (normally `~/.config/hst-office/4`), instead of the product-derived `hst%20office/4`. Preserve explicit test-profile overrides. Verify direct `soffice` and all four launchers use the same isolated profile; do not migrate or modify LibreOffice's profile implicitly.
6. Audit rendered screens and installed resources; textual scan allowlist covers only legal credits and necessary internals, not broad directories. Verify all .deb components and language packs share HST identity. Platform-specific .ico/.icns and installer graphics are generated when preparing 09, but are not claimed tested on their OS.

## Validation commands

Existing checks work now; expanded checks run after implementation:

```bash
python3 scripts/generate-brand-assets.py --check
python3 tests/brand/test-brand-assets.py
desktop-file-validate branding/linux/hst-office.desktop branding/linux/hst-writer.desktop branding/linux/hst-sheets.desktop branding/linux/hst-slides.desktop
python3 scripts/check-branding.py --install-root upstream/libreoffice/instdir --allowlist branding/brand-audit-allowlist.json
git -C upstream/libreoffice diff --check
```

Local readiness requires asset/resource checks and build-tree screenshots of splash, Start Center, each module and About/credits. This permits packaging. Final installed screenshots, desktop integration and profile-path assertions belong to 07/08. A string scan alone cannot detect embedded TDF logos. Every visible non-HST product mark has a resolved disposition; license text remains intact.

## Risks and rollback

Aggressive global replacements break identifiers/localization and legal notices. Keep a small reviewed patch and exact image manifest. Revert the branding patch/config/assets together and rebuild only in a test profile; an upstream-branded result is never a releasable HST package. Stop for insufficient asset resolution rather than stretching a visibly damaged logo.
