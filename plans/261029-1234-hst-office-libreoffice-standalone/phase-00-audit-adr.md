# Phase 00 — Audit, licensing and ADR 0002

**Status:** pending. **Owner:** Claude; Codex reviews. **Depends on:** none. **Parallelizable:** no for decisions/lock; read-only research may run separately.

## Context and requirements

The old audit method is useful; its ONLYOFFICE conclusion is superseded. Record the owner's source-built standalone decision without asking again to choose an engine. GitHub's GPL-3.0 metadata is not a license inventory. Audit actual files at the resolved tag, bundled third parties, translation/help/dictionary sources and generated installer notices.

## Exact files

- Modify `docs/ADR/0001-plugin-first-unmodified-upstream.md` (superseded banner), `docs/HST_OFFICE_IMPLEMENTATION_BRIEF.md` (pivot overlay), `docs/ARCHITECTURE.md`, `docs/LICENSE_AUDIT.md`, `docs/UPSTREAM_BASELINE.md`, `docs/BLOCKERS.md`, `docs/PLUGIN_CONTRACT.md` (historical banner).
- Create `docs/ADR/0002-libreoffice-standalone.md`, `docs/EXTENSION_CONTRACT.md`, `upstream/libreoffice-lock.json`, `LICENSES/upstream/libreoffice/COPYING`, `LICENSES/upstream/libreoffice/COPYING.MPL`, `LICENSES/upstream/libreoffice/license.xml`, `LICENSES/upstream/libreoffice/provenance.json`. Capture other referenced COPYING files if present; do not manufacture absent upstream files.
- Modify `NOTICE.md`, `THIRD_PARTY_NOTICES.md` when the audited split is known. Retain root `LICENSE` for new HST code, with explicit scope in the notices. Remove obsolete ONLYOFFICE SDK shipping references; preserve historical notices with archived artifacts.
- Create `scripts/check-source-lock.py`, `scripts/check-license-inventory.py`; machine inventory `LICENSES/component-inventory.json` includes each actually shipped third-party notice/source. Read archive `extensions/vn-admin-documents/logic/nd30-data.js`, `nd30-layout.js`, `nd30-validation.js` at the archive SHA in the index.

## Steps

1. Record old main/archive SHAs; compare brief against pivot. ADR 0002 supersedes 0001 with standalone source build, minimal maintained patches, Python-UNO `.oxt`, native templates, Linux-first release and explicit native-platform blockers. Document upgrade/rebase and corresponding-source process.
2. Resolve both exact tags/peeled commits, correlate tag with official released source archives, and record URLs, SHA-256, verification method, UTC date and companion gitlinks/archive versions. No moving branch or `26.8.1.x` wildcard in the final lock. Recheck current security/release advisories before release; no silent version upgrade.
3. Read [pinned COPYING](https://raw.githubusercontent.com/LibreOffice/core/libreoffice-26.8.1.1/COPYING), COPYING.MPL, per-file headers and [readlicense_oo/license/license.xml](https://raw.githubusercontent.com/LibreOffice/core/libreoffice-26.8.1.1/readlicense_oo/license/license.xml). COPYING contains GPLv3, while license.xml identifies the product as MPL-2.0 and enumerates third parties. `readlicense_oo/CustomTarget_license.mk` generates upstream `workdir/CustomTarget/readlicense_oo/license/LICENSE` and `LICENSE.html`; preserve these build-filtered outputs without replacing the HST repository root LICENSE. Preserve MPL on covered edits and LGPL/other applicable grants. Recommend **AGPL-3.0 for independently authored HST extension/build/test files**, existing CC BY 4.0 for template content, and original licenses for dependencies/assets. Do not label the combined suite exclusively AGPL or strip notices to meet branding.
4. Check MPL §3.3/secondary-license conditions, Exhibit B restrictions and third-party exceptions before combining code. Prefer separate UNO components; separation is an architecture choice, not automatic legal clearance. Record evidence for the permitted distribution and source obligations; unresolved component-specific incompatibility blocks that component/release, not the already chosen engine. Sources: [Mozilla MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/), [MPL text](https://www.mozilla.org/en-US/MPL/2.0/), [GNU license compatibility](https://www.gnu.org/licenses/license-list.html#MPL-2.0).
5. Audit [TDF trademark policy](https://wiki.documentfoundation.org/TDF/Policies/Trademark_Policy) and distinguish HST identity from truthful credits/legal text. The policy page denied automated access during planning; detailed exceptions remain unverified. Record an explicit branding allowlist: legal notices, attribution and necessary internal format/UNO identifiers. No TDF/LibreOffice product marks on HST splash/icons/installer.
6. Preserve ND30 values and source evidence. Audit TCVN3/VNI mapping and Vietnamese dictionary licenses independently. Establish native extension contract: identifiers, language strings, command dispatch, configuration precedence, one-step Undo, fixture manifest and evidence schema.

## Validation commands

Now, read-only (network failure must be recorded):

```bash
git rev-parse HEAD archive/onlyoffice-plugin-first
git ls-remote --tags https://git.libreoffice.org/core 'refs/tags/libreoffice-26.8.1*' 'refs/tags/libreoffice-26.2.6*'
git show archive/onlyoffice-plugin-first:extensions/vn-admin-documents/logic/nd30-data.js
```

After this phase implements the validators:

```bash
python3 scripts/check-source-lock.py upstream/libreoffice-lock.json --verify-remote-metadata
python3 scripts/check-license-inventory.py --inventory LICENSES/component-inventory.json
git diff --check
```

Pass: immutable verified pin; license files/hashes and component scope agree; ADR supersession is unambiguous; archive algorithm provenance is retained. A missing license/tag/archive is a blocker, not an invented value.

## Risks and rollback

Trademark/wiki sites can reject automated access; capture official policy through a permitted reader and record access gaps. An incompatible dictionary is omitted with an explicit blocker, not relicensed. Revert only this phase's documents/lock before consumers use it; after a build, changing a pin invalidates all downstream evidence. Keep ADR 0001 as historical evidence.
