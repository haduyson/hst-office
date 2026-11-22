# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""Licence policy: HASON TECH's own files are proprietary, LibreOffice files keep their MPL notices.

- Files written by HST carry `SPDX-License-Identifier: LicenseRef-HST-Proprietary` with the HASON TECH copyright
  line (artwork keeps CC-BY-4.0); no tracked file carries the former AGPL-3.0 identifier.
- In patches/libreoffice, an upstream file that a patch modifies keeps every licence line it had and never gets the
  HST identifier; a new file is either MPL (copied or derived from LibreOffice) or LicenseRef-HST-Proprietary.
- The root LICENSE is the HST Office Software Terms of Use; the AGPL text applies to 1.0.0-1.0.3 only and is kept
  under LICENSES/historical. Package metadata and the in-app licence document follow the same split.
"""
import importlib.util
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCHES = os.path.join(ROOT, "patches", "libreoffice")
HST_ID = "SPDX-License-Identifier: LicenseRef-HST-Proprietary"
HST_COPYRIGHT = "Copyright (C) 2026 HASON TECH"
# Trees whose files are not HST's own code: upstream sources and licence texts, plans (dated records) and the
# patch series (checked hunk by hunk below).
NOT_HST = ("upstream/", "LICENSES/", "plans/", "patches/")
LICENCE_LINE = re.compile(r"SPDX-License-Identifier|Mozilla Public|GNU (Lesser )?General Public License|Apache License")


def tracked():
    out = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [p for p in out.decode("utf-8").split("\0") if p and os.path.isfile(os.path.join(ROOT, p))]


def head(path, lines=4):
    with open(os.path.join(ROOT, path), "rb") as handle:
        return handle.read(4096).decode("utf-8", "replace").splitlines()[:lines]


def patch_files(text):
    """[(path, kind, added lines, removed lines)] of one patch; kind is "new" (created, also "@@ -0,0"), "deleted"
    or "modified"."""
    files, lines = [], text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            deleted = lines[i + 1].startswith("+++ /dev/null")
            path = (line[6:] if deleted else lines[i + 1][6:]).split("\t")[0]
            new = line.startswith("--- /dev/null") or (i + 2 < len(lines) and lines[i + 2].startswith("@@ -0,0 "))
            files.append([path, "deleted" if deleted else "new" if new else "modified", [], []])
        elif files and not lines[i - 1].startswith("--- "):
            if line.startswith("+"):
                files[-1][2].append(line[1:])
            elif line.startswith("-") and not line.startswith("--- "):
                files[-1][3].append(line[1:])
    return files


def series():
    with open(os.path.join(PATCHES, "series"), encoding="utf-8") as handle:
        names = [n.strip() for n in handle if n.strip() and not n.startswith("#")]
    for name in names:
        with open(os.path.join(PATCHES, name), encoding="utf-8", errors="replace") as handle:
            yield name, handle.read()


def load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HstFiles(unittest.TestCase):
    def test_no_agpl_identifier_left(self):
        old = "SPDX-License-Identifier: " + "AGPL"
        offenders = []
        for path in tracked():
            if path.startswith(("upstream/", "LICENSES/")):
                continue
            with open(os.path.join(ROOT, path), "rb") as handle:
                if old.encode() in handle.read():
                    offenders.append(path)
        self.assertEqual(offenders, [])

    def test_hst_headers_are_proprietary_with_copyright(self):
        checked, bad = 0, []
        for path in tracked():
            if path.startswith(NOT_HST):
                continue
            top = head(path)
            spdx = next((i for i, line in enumerate(top[:3]) if "SPDX-License-Identifier:" in line), None)
            if spdx is None:
                continue
            checked += 1
            if HST_ID in top[spdx]:
                if not any(HST_COPYRIGHT in line for line in top[spdx + 1:spdx + 2]):
                    bad.append(path + ": no copyright line under the SPDX header")
            elif "SPDX-License-Identifier: CC-BY-4.0" not in top[spdx]:
                bad.append(path + ": " + top[spdx].strip())
        self.assertGreater(checked, 2500)
        self.assertEqual(bad, [])

    def test_extension_check_requires_the_hst_header(self):
        with open(os.path.join(ROOT, "scripts", "extension_content.py"), encoding="utf-8") as handle:
            self.assertIn('"%s" not in text[:300]' % HST_ID, handle.read())


class PatchSeries(unittest.TestCase):
    def test_modified_upstream_files_keep_their_licence_lines(self):
        problems, modified, hst_made = [], 0, set()
        for name, text in series():
            for path, kind, added, removed in patch_files(text):
                if kind != "modified" or path in hst_made:  # files created by an earlier HST patch are HST's own
                    hst_made.update([path] if kind == "new" else [])
                    continue
                modified += 1
                if any(HST_ID in line for line in added):
                    problems.append(f"{name}: {path} gets the HST identifier")
                lost = [line for line in removed if LICENCE_LINE.search(line) and line not in added]
                if lost:
                    problems.append(f"{name}: {path} drops licence line {lost[0].strip()!r}")
        self.assertGreater(modified, 1000)
        self.assertEqual(problems, [])

    def test_new_files_are_mpl_or_hst(self):
        problems, kinds = [], {"mpl": 0, "hst": 0}
        for name, text in series():
            for path, kind, added, _removed in patch_files(text):
                if kind != "new":
                    continue
                top = "\n".join(added[:20])
                mpl, hst = "Mozilla Public" in top, HST_ID in top
                if mpl and hst:
                    problems.append(f"{name}: {path} has both an MPL and the HST header")
                if "AGPL" in top or "Affero" in top:
                    problems.append(f"{name}: {path} has an AGPL header")
                kinds["mpl"] += mpl
                kinds["hst"] += hst
        self.assertEqual(problems, [])
        self.assertGreater(kinds["mpl"], 100)
        self.assertGreater(kinds["hst"], 100)

    def test_licence_document_section(self):
        files = dict((p, a) for n, t in series() if n == "hst-debrand.patch" for p, c, a, r in patch_files(t))
        section = "\n".join(files["readlicense_oo/license/license.xml"])
        dialog = "\n".join(files["sfx2/source/appl/appserv.cxx"])
        for text in (section, dialog):
            self.assertIn("lienhe@hasontech.vn", text)
            self.assertIn("proprietary software of HASON TECH", text)
            self.assertIn("MPL, LGPL or GPL", text)
            self.assertNotIn("open-source software;", text)
            self.assertNotRegex(text, r"https?://|github")
        self.assertIn("Điều khoản sử dụng phần mềm HST Office", section)
        self.assertIn("HST Office Software Terms of Use", section)
        self.assertIn("1.0.0 đến 1.0.3", section)


class LicenceTexts(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as handle:
            return handle.read()

    def test_root_licence_is_the_terms_of_use(self):
        text = self.read("LICENSE")
        for needle in ("ĐIỀU KHOẢN SỬ DỤNG PHẦN MỀM HST OFFICE", "HST OFFICE SOFTWARE TERMS OF USE",
                       "Copyright (C) 2026 Công ty TNHH Công nghệ Hà Sơn (HASON TECH)", "THIRD_PARTY_NOTICES.md",
                       "Mozilla Public License", "lienhe@hasontech.vn", "1.0.0 đến 1.0.3", "1.0.0 to 1.0.3"):
            self.assertIn(needle, text)
        self.assertNotIn("GNU AFFERO GENERAL PUBLIC LICENSE", text)
        self.assertNotRegex(text, r"(?i)bản nháp|draft")

    def test_agpl_text_is_kept_for_the_released_versions(self):
        self.assertTrue(self.read("LICENSES/historical/AGPL-3.0.txt").lstrip().startswith("GNU AFFERO GENERAL PUBLIC LICENSE"))
        note = self.read("LICENSES/historical/README.md")
        self.assertIn("1.0.0 đến 1.0.3", note)
        self.assertIn("1.0.0 to 1.0.3", note)

    def test_package_metadata(self):
        rpm = load("scripts/linux/rpm_spec.py", "rpm_spec_policy")
        deb = load("scripts/linux/single_deb_texts.py", "single_deb_texts_policy")
        self.assertEqual(rpm.LICENSE, "MPL-2.0 AND LicenseRef-HST-Proprietary")
        self.assertIn("\nLicense: LicenseRef-HST-Proprietary\n HST Office Software Terms of Use.", deb.COPYRIGHT)
        self.assertIn("License: MPL-2.0 and LicenseRef-HST-Proprietary", deb.COPYRIGHT)
        self.assertIn("<project_license>MPL-2.0 AND LicenseRef-proprietary</project_license>", deb.METAINFO)
        self.assertNotIn("AGPL", deb.COPYRIGHT + deb.METAINFO + rpm.LICENSE)

    def test_extension_notices(self):
        files = load("scripts/extension_package_files.py", "extension_package_files_policy")
        text = files.notices_text()
        self.assertIn("proprietary; HST Office Software Terms of Use (license/LICENSE.txt)", text)
        self.assertNotIn("Affero", text)


if __name__ == "__main__":
    unittest.main()
