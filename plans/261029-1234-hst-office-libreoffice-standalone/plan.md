---
title: "HST Office — standalone LibreOffice source build"
description: "Claude implementation plan for a branded Linux suite and Vietnamese features, with explicit desktop platform blockers."
status: pending
priority: P1
effort: "24–38 engineering days; build and unavailable-platform waiting excluded"
branch: main
tags: [feature, infra, docs]
blockedBy: []
blocks: []
created: 2026-10-29
---

# HST Office standalone plan

**Planning delivered; implementation pending.** Owner pivot dated 2026-10-29 12:34, Asia/Ho_Chi_Minh, overrides brief engine/build choices and ADR 0001. Codex plans/reviews; Claude implements. Work in `/home/office`, Ubuntu 24.04, locale `C.UTF-8`; scoped conventional commits directly to `main`, no PRs or force-push. This delivery changes only this plan directory and `docs/BACKLOG.md`.

## Outcome and boundaries

Build LibreOffice **from source** as standalone **HST Office**, with **HST Writer / HST Sheets / HST Slides**, HST splash/About/icons/desktop integration/installer, Tabbed UI by default, and bundled native Vietnamese tools and 18 templates. First deliverable is an Ubuntu 24.04 x86_64 `.deb` set built on this VPS. Windows/macOS pipelines and a macOS latency harness are required; execution stays BLOCKED until suitable machines exist. Linux success never implies macOS success.

Retain the audited-document approach, `assets/brand/*`, its generator, and [ND30 rules](../../docs/VIETNAMESE_OFFICE_SPEC.md). Archive source is `archive/onlyoffice-plugin-first` at `e0517d71c813535087c401b2683bec0784d71fd8`; reuse its ND30 algorithms/data with provenance, not its Asc/CEF/SDK implementation. Current main is `577f620`. No cloud/login/telemetry, separate PDF editor, new office modules, or promised Microsoft Office fidelity. Keep drawing/formula internals required by the three editors.

## Version recommendation and evidence

Recommend **26.8.1**, exact tag `libreoffice-26.8.1.1`, peeled commit `bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1`. Comparator: **26.2.6**, `libreoffice-26.2.6.3`, `8221e31b3ac356a1623c672912a3d2b492f7e3d1`. References were resolved through `git ls-remote --tags https://git.libreoffice.org/core`; Phase 00 must recheck and write the lock before fetching. [Official release notes](https://pt-br.libreoffice.org/novidades/) describe the fresh/mature distinction. The mature branch offers more maintenance history, but [TDF gives 26.2 an end-of-life date of 30 November 2026](https://blog.documentfoundation.org/blog/2026/08/26/libreoffice-26-8/). A new distribution should avoid that near-term upgrade burden. Newer macOS fixes are a research hypothesis, not the justification for claiming the delay fixed. A demonstrated 26.8 regression triggers a documented backport/version decision and rerun, not an unnoticed downgrade.

## Phases and dependencies

All phases are **pending**. Estimates include implementation and focused verification. Phase 04 has an explicit blocked macOS portion; Phase 09 has blocked native desktop execution.

| Phase | Deliverable | Depends on | Estimate | Parallel work |
|---|---|---|---|---|
| [00](phase-00-audit-adr.md) | Audit, license split, ADR 0002, pin | — | 1–2d | Single decision owner |
| [01](phase-01-source-build-environment.md) | Resource-guarded source build | 00 | 3–5d | Light work only during build |
| [02](phase-02-branding.md) | Complete HST identity | 00; runtime 01 | 2–3d | Asset authoring with 01 |
| [03](phase-03-default-configuration.md) | Tabbed, locale, fonts, privacy | 00; runtime 01/02 | 1–2d | Config authoring with 05 |
| [04](phase-04-context-menu-latency.md) | Delay research, harness, evidenced fix | 01; final comparison 02/03/05 | 2–4d + Mac wait | Research/harness early |
| [05](phase-05-vietnamese-extensions.md) | Bundled Python-UNO Vietnamese tools | 00; runtime 01/03 | 5–7d | Logic with 02; no shared-source edits |
| [06](phase-06-vietnamese-templates.md) | 7 Writer + 6 Sheets + 5 Slides templates | 05 data contract; runtime 01/03 | 2–3d | Content after contract freeze |
| [07](phase-07-debian-packaging.md) | `.deb`, clean-container lifecycle | 02/03/05/06; applicable 04 patch | 2–3d | Package metadata early |
| [08](phase-08-runtime-qa.md) | Headless/GUI/data-safety evidence | 07; Linux 04 | 3–4d | Fixture authoring early |
| [09](phase-09-ci-platform-pipelines.md) | Quality CI, measured Linux feasibility, blocked Win/Mac | 01; quality 05/06; artifact checks 07/08 | 1–2d | Quality workflow early |
| [10](phase-10-docs-handoff.md) | Build/release/compatibility docs, review/handoff | 00–09 with blockers preserved | 2–3d | Draft docs; final integration serial |

Dependencies consume each phase's **local readiness gate** (build-tree/config/OXT/template checks). Final installed acceptance is owned by 07/08 and does not block producing their inputs. One Claude coordinator owns the upstream checkout, patch application, source lock, `.gitignore`, and integration. Parallelizable means disjoint authoring; never simultaneous builds, source mutation, staging, or fixed-port GUI sessions. File paths are relative to `/home/office`; grouped filenames expand to exact paths. Upstream inspection paths are not permission for blanket replacements.

## Acceptance

- A pinned, source-built Linux `.deb` installs on a clean Ubuntu 24.04 container; all three branded modules open, edit, save, reopen and export local documents. Uninstall/purge/upgrade preserve user documents and unrelated profiles.
- Branding covers first launch, launcher, About, icons, package names and help/support. Credits truthfully say **“based on LibreOffice”**; required upstream notices remain. No TDF marks act as HST product identity.
- Fresh profiles use Tabbed UI, A4 and requested font defaults; Vietnamese OS selects Vietnamese UI. English and classic UI remain selectable and survive restart/upgrade. No telemetry or automatic TDF update requests.
- ND30 wizard, preview/Undo converter, number/date/percent formats, UTF-8 CSV safety, autotext/config, all 18 templates, and a license-approved Vietnamese dictionary have evidence or a named dictionary licensing blocker.
- Linux latency has baseline/candidate measurements and functional checks. A macOS fix requires Mac reproduction and before/after evidence; until then that requirement stays open with an executable harness and owner.
- Every heavy job preserves **at least 10 GiB free**, records CPU/RSS/time/disk, and stops safely before exhausting space. CI cannot convert missing hardware, permissions, artifacts or skipped tests into PASS.
- Runtime results record exact source/HST SHAs, package hashes, OS/backend/font/locale and PASS/FAIL/BLOCKED/NOT RUN. Microsoft Office compatibility claims require actual Office evidence.

## Validation contract and current evidence

Commands in phase files are Claude's future acceptance commands, **not executed implementation evidence**. Existing read-only commands are labeled “now”; new script names are required interfaces to implement in that phase. Run from `/home/office` unless stated. Missing executable, fixture, display or runtime must fail with a named blocker, never silently skip. Tool outputs go to ignored `tests/output/` and `build/`; concise sanitized evidence goes to `plans/reports/` at implementation time.

Observed 2026-10-29: Ubuntu 24.04.4, 32 vCPU, 47 GiB total RAM, about **18 GiB available**, 57,440,092,160 free bytes (**53.5 GiB**). ONLYOFFICE cache is about 1.4 GiB. Docker CLI exists but socket access returns permission denied. `gh api` cannot connect to `api.github.com`; official upstream git refs were accessible through the research session. Session filesystem rules make repository Git metadata read-only; publication requires a normally writable authenticated session. These are environment blockers, not reasons to change the chosen product.

Existing brand regeneration check and all five brand tests pass; tests emit pre-existing unclosed-image `ResourceWarning`s. No engine fetch/build/container/native-platform test was run during planning. Planning validation covers linked phase files, dependency order, full requested scope and concrete commands; it does not certify future scripts.

Read-only reviews corrected release-mode comparability, EPM packaging, bootstrap profile isolation, generated-license locations, phase acceptance cycles, docs-checker ownership and native CSV safety. Local links, phase structure and the 42-item backlog dependency graph were checked; all implementation statuses remain pending or explicitly blocked.

## Unresolved questions and unblock owners

1. **Environment administrator:** provide Git writes/network, apt/build privileges and Docker daemon access for Claude. Do not loosen socket permissions or install a second daemon as a workaround.
2. **Owner:** provide a Mac, macOS version/architecture, affected LibreOffice version, representative non-sensitive document and reproduction steps; a logged-in GUI session and measurement permissions are needed. Windows build/test hardware and signing credentials remain separate blockers.
3. **Claude + owner/legal reviewer:** verify per-component licenses, dictionary provenance and present ND30 legal status. Preserve AGPL-3.0 for separate new HST code; do not relicense upstream files globally.
4. **Claude:** measure whether the source build and packaging fit the 40 GiB working envelope. If they do not, record required extra storage or arrange approved artifact offload; never consume the 10 GiB reserve or silently drop requested features.
5. **Owner/release lead:** validate candidate latency targets and affected-Mac results before claiming that issue resolved. Use `https://hasontech.vn` and bundled HST help until a specific support/update service exists; no invented update endpoint.
