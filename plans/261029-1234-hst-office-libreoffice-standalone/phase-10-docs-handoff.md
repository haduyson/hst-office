# Phase 10 — Documentation, review and implementation handoff

**Status:** pending. **Depends on:** 00–09 with native-platform blockers carried forward. **Parallelizable:** drafting; final claims and main integration have one owner.

## Context and requirements

Replace plugin-first user guidance with the actual standalone installation/build flow. Plans record work state; evergreen documents describe verified product behavior. Keep Linux readiness separate from cross-platform completion and macOS delay resolution. Owner has already selected direct pushes to main, with no PRs.

## Exact files

- Modify root `README.md` (explicitly requested by owner), `docs/ARCHITECTURE.md`, `docs/UPSTREAM_BASELINE.md`, `docs/BUILD_MATRIX.md`, `docs/BLOCKERS.md`, `docs/LICENSE_AUDIT.md`, `docs/BRAND.md`, `docs/BACKLOG.md`, `NOTICE.md`, `THIRD_PARTY_NOTICES.md` through their owners.
- Create `docs/README.md`, `docs/BUILD.md`, `docs/RELEASE_CHECKLIST.md`, `docs/INSTALLATION.md`; finalize `docs/COMPATIBILITY_MATRIX.md`, `docs/CI.md`, `docs/CONTEXT_MENU_PERFORMANCE.md`, `docs/EXTENSION_CONTRACT.md`, `docs/TEMPLATES.md` from owning phases.
- Consume Phase 09's `scripts/check-doc-links.py`; update this plan's phase statuses from evidence. Historical plan remains historical; add a superseded notice to `plans/261029-1118-hst-office-phase0-plugin-first/plan.md` during implementation.

## Steps

1. README leads with standalone HST Office and three modules, real Linux install prerequisites/artifact status and source-built lineage; remove active ONLYOFFICE plugin installation commands. Link docs index, native features, license split and honest platform availability. Do not advertise a download that has not been built/published.
2. BUILD documents immutable source/dependency pins, exact executed configure/make/package commands, resource envelope/measurements, cache and disk-stop behavior, source/patch update procedure and Windows/macOS prerequisites/blockers. Link machine-owned manifests instead of duplicating package lists. Include clean reproduction and rollback steps.
3. RELEASE_CHECKLIST covers notices/corresponding source, license/trademark/dictionary/font evidence, identity/privacy audit, package hashes, clean install/upgrade/uninstall, core OOXML and all-feature QA, measured latency, unresolved platform limits, signing and owner release authority. Linux-only delivery may proceed with explicit unavailable-platform blockers; global “Mac issue fixed” may not.
4. COMPATIBILITY_MATRIX reports actual case/OS/arch/runtime/hash evidence with PASS/FAIL/BLOCKED/NOT RUN. Record font substitution, unsupported OOXML/macros/features and Microsoft Office comparison limitations. Persist small sanitized reports plus artifact manifests; no personal files in logs/screenshots.
5. Codex reviews high-risk/public contracts: licenses/brand notices, source pin/build reproducibility, package deletion behavior, Undo/data preservation, privacy and performance claims. Claude fixes verified findings without reversing owner decisions. Re-run affected checks; compare every acceptance item in the index before declaring Linux delivery complete.
6. Stage only scoped work, inspect for secrets/artifacts, use conventional commits and push `main` without force or PR. If Git metadata is read-only or authentication/network fails, report the exact blocker and leave reviewable files; do not bypass environment controls. Follow remote checks for the same pushed SHA. Stop all owned build/Xvfb/UNO/container processes and record remaining platform work.

## Validation commands

After implementation:

```bash
python3 scripts/check-doc-links.py
bash scripts/ci-quality.sh
git diff --check
git status --short
rg -n 'ONLYOFFICE|plugin-first|LibreOffice|BLOCKED|NOT RUN' README.md docs
```

Review search results in context: historical attribution remains valid; active installation/build instructions must match artifacts. Validate commands in BUILD against a recorded clean run; do not imply a second full engine build happened unless measured. For authorized publication in a writable session, stage an explicit reviewed file list, commit, then `git push origin main`; confirm `gh run list --branch main` identifies the same commit.

## Risks and rollback

Stale docs can falsely claim Mac fixes, CI builds or available installers. Block such claims until evidence exists. Revert a faulty doc/commit with a focused follow-up on main; no history rewrite. Keep previous tested release/source manifests and never delete evidence just to make the checklist green.
