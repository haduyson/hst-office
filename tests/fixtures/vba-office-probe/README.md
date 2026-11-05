# VBA probe files for real Microsoft Office

The files that were here are probes for a human test in real Excel and Word: each one is an HST export, an
Office-made file, or a mix of the two, made to tell which part Office accepts. They are not files known to
work, and no automated check reads them. They were removed when testing in real Office was postponed.

Where to get them: the last commit that holds them is
`16d044d6642351bdbf60a6216726127f8747f4cc`.

    git archive 16d044d6642351bdbf60a6216726127f8747f4cc tests/fixtures/vba-office-probe | tar -x

`.github/workflows/windows-vba-form-probe.yml` fetches them the same way.

Where they come from:

- HST exports (`1`, `3` to `6`, `f*`, `n*`, `w8`, `w9`, `z1`, and the HST parts of the mixes): saved by HST
  Office from the fixtures in `tests/runtime/vba_form_fixture.py`.
- Office-made parts: test documents of the pinned upstream source, saved by Word or Excel:
  `sw/qa/core/data/docm/testFind.docm` (`w1`, `w2`, `w3`),
  `sw/qa/extras/ooxmlexport/data/tdf108269.docm` (`w4` to `w7`, Word 15),
  `sc/qa/extras/testdocuments/MiscControlTests.xls` (`x1`, `x3`, `x4`).
  A check that needs them reads them from `upstream/libreoffice` at test time.
- Mixes (`w2`, `w3`, `w5` to `w7`, `x2` to `x5`, `y1` to `y3`): one part swapped or changed, by the
  scripts kept with the investigation (see `plans/reports/vba-261104-1224-vba-authoring-writer-sheets.md`).

What real Office showed is recorded in that report.
