# opus-05w: welcome dialog + "Giải pháp HASON TECH…" menu entry

## Done
- `welcome.xcs` (flag `/org.hasontech.hstoffice.Welcome/Shown`), `Jobs.xcu` (onFirstVisibleTask -> `org.hst.office.vi.WelcomeJob`), manifest entries (xcs media type added to check-extensions).
- `python/hst_office/welcome_content.py` (pure: `build_utm_url`, `display_url`, `build_model`), `welcome_dialog.py` (native dialog, FixedHyperlink w/o URL, SystemShellExecute only on click), `welcome_job.py` (flag + XJob), registered in `hst_office_component.py`; `dispatch.py` handles `ShowSolutions` without Host (works with no document); `data_files.py` also finds `data/hst/`.
- Menu m7 "Giải pháp HASON TECH…" / "HASON TECH solutions…"; HST menu + m7 Context = Writer, Calc, Impress, StartModule (other items keep their own contexts). locales vi/en: `menu.solutions`, `welcome.*`.
- Build copies `data/hst/solutions.json` -> `data/solutions.json`; check-extensions requires it + stale check + self-test case.
- Docs: `docs/EXTENSION_CONTRACT.md` (new section), `docs/PRIVACY.md`.

## Behaviour decisions
- "Không hiển thị lại" = checkbox, ticked by default (not a button); only button is "Đóng". Flag set when window shown (windowShown listener). Close with tick = never again; untick + close = Shown=false (shows again next start). Tell me if you want two real buttons.
- UTM: https only; existing utm_* replaced; query/fragment kept. Built with `re` (no urllib: check-extensions bans it).
- UI language from `ooLocale` (vi -> Vietnamese, else English).

## Verification
| Command | Result |
|---|---|
| `python3 -m unittest discover -s tests/unit -p 'test_*.py'` | 72 OK (test_welcome.py: UTM w/ and w/o query, fragment, dup utm, bad schemes/medium, model order/links/services/contact, locale parity) |
| `.venv/bin/python scripts/build-extensions.py --verify-reproducible` | reproducible: yes (42 files) |
| `scripts/check-extensions.py` / `--self-test` | PASS / all cases rejected incl. stale solutions |
| `tests/runtime/check-extensions.py --mode bundled --allow-modify-install --display :99` on lo-full (o5, LibreOffice 24.2) | **111 checks, 0 failed, 0 blocked** (25 in new `welcome` group; `--only welcome` runs it alone) |

Welcome group (fresh profile, real job): flag default false; first visible doc -> dialog shown with exact content/order; flag true once shown; no URL opened before click; 6 solution + website clicks -> URLs with `utm_medium=welcome`; close; restart same profile -> no dialog; menu command `org.hst.office.vi:ShowSolutions` -> dialog (English fallback title), links `utm_medium=menu`; unticking re-arms flag; Addons context contains the 4 contexts. Browser launcher replaced by recorder in the probe (`hst_probe_macro.welcome_*`); clicks fire the dialog's real click handler, not an X mouse click.

Screenshots (Xvfb :99, viewed): `/home/office/tests/output/extensions/welcome-dialog.png` (vi), `.../welcome-dialog-en.png`. Diacritics and layout OK, links underlined blue, all text fits. Under Xvfb without window manager/theme the checkbox box glyph is not drawn (label only) and there is no title bar; not verified on a themed desktop.

## Not verified / concerns
- Start Center: context registered in Addons, but menu display in the real Start Center and ShowSolutions dispatch there are UNVERIFIED.
- LibreOffice 26.8.1 (HST build): not run.
- No window-manager Z-order / focus behaviour checked for the first-start dialog at real startup (headed desktop).
- Xvfb :99 stopped; no soffice left of mine (a defunct pid 1782591 predates this run).

Status: DONE_WITH_CONCERNS
Summary: Welcome dialog (once, flag-based), HST menu entry, UTM links, tests, docs implemented; full runtime harness on LO 24.2 passes 111/111. Start Center display and 26.8.1 unverified.
