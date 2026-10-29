# Phase 03 — Tabbed UI, Vietnamese defaults and privacy

**Status:** pending. **Depends on:** 00; runtime 01/02. **Parallelizable:** separate configuration authoring; coordinator owns source integration.

## Context and requirements

Ship defaults through install-time configuration layers, not a copied personal profile. Defaults apply to fresh profiles and new documents; preserve user overrides, document styles and existing documents. Use the pinned registry schema to verify every key.

## Exact files

- Create `config/hst-defaults.xcu`, `config/hst-writer-defaults.xcu`, `config/hst-sheets-defaults.xcu`, `config/hst-autotext-manifest.json`, `config/defaults-manifest.json`, `config/privacy-policy.json`.
- Create `patches/libreoffice/hst-defaults.patch`, `tests/runtime/check-defaults.py`, `tests/runtime/check-network.py`, `tests/fixtures/defaults/cases.json`; append patch to `patches/libreoffice/series` through coordinator.
- Inspect pinned `officecfg/registry/schema/org/openoffice/Office/`, `officecfg/registry/data/org/openoffice/Office/`, `officecfg/registry/data/org/openoffice/Setup.xcu`, `desktop/source/app/`, `sfx2/source/notebookbar/`, `sc/source/ui/dbgui/`. Resolve schema paths before writing registry entries.

## Steps

1. Set NotebookBar **Tabbed** separately for Writer/Calc/Impress's internal services. Verify actual selected UI, not just an XML value. Keep View → User Interface switching to standard/classic UI available; choice survives restart and upgrade. Do not reset it each startup.
2. Build `vi` and `en-US` resources; map Vietnamese OS locale to UI `vi-VN` using upstream system-locale detection. Respect explicit user locale; non-Vietnamese OS uses supported fallback. Test `vi_VN.UTF-8`, `en_US.UTF-8` and `C.UTF-8`. Do not globally force Vietnamese on all operating systems.
3. Use A4 for new Writer documents and print-page defaults. ND30 action/template uses top/bottom/left/right **20/20/30/15 mm**, Times New Roman 14 pt, first indent 1.27 cm, line spacing 1.15, paragraph-after 6 pt; preserve the rest of the specification. Set requested TNR text defaults where appropriate in module styles, without forcing a document-wide size on every slide/table.
4. Do not bundle Microsoft fonts without rights. Detect TNR availability; expose an honest missing-font warning for ND30 output and documented Liberation Serif fallback. A fallback rendering does not prove ND30 font conformity. Template metadata keeps the requested font; record actual rendered font in QA.
5. Set first-use CSV UTF-8 and **text-column/no-formula-evaluation** defaults in both native File → Open CSV and the HST import tool, preserving leading zeros and formula-looking text. Use a minimal native import patch if configuration cannot express the policy. Retain encoding/delimiter/type preview and user's explicit later choices. Test both entry points with the same safety fixtures. Apply Vietnamese VND/date/percent through UNO number formats in 05, preserving values/formulas. Autotext entries for ND30 phrases use the same data source as the wizard, never real names/signatures.
6. Disable telemetry, automatic crash uploads, update checks including TDF and extension update endpoints, and remote content/template fetch at startup. Use verified configure switches and runtime defaults; remove nonfunctional Update UI. Do not replace these with invented HST endpoints. User-initiated local editing/help works offline; preserve normal document security prompts and macro security.

## Validation commands

After 01 provides the binary and this phase implements the runners:

```bash
python3 tests/runtime/check-defaults.py --soffice upstream/libreoffice/instdir/program/soffice --cases tests/fixtures/defaults/cases.json --output tests/output/defaults
python3 tests/runtime/check-network.py --soffice upstream/libreoffice/instdir/program/soffice --policy config/privacy-policy.json --output tests/output/privacy
```

Runners own isolated profiles and Xvfb/DBus processes. Local readiness exercises all modules, fresh profile and changed setting/restart on the build tree; actual package-upgrade preservation belongs to 07/08. Assert effective locale/UI/page/font/CSV settings, not only registry syntax. Network evidence covers startup, idle, About/help, editing, extension discovery and attempted update, with attempted DNS/connect captured (for example process tracing) as well as a network-disabled run. Lack of egress permission alone does not prove no attempts occurred.

## Risks and rollback

Registry keys can change between releases; schema validation and runtime readback are required. Disable only measured offending services, not spellcheck/accessibility or entire networking libraries to hide a delay. Revert shipped defaults/patches without deleting a user's profile; preserve explicit settings and personal documents.
