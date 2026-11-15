# SPDX-License-Identifier: AGPL-3.0-only
"""`soffice --version` prints "HST Office <release>" only: a build from the release tarball has no git commit,
so the installer's buildid is the upstream fallback "680(Build:1)" and the version line must not show it."""
import unittest

from test_hst_version_everywhere import code, file_lines


class CommandLineVersion(unittest.TestCase):
    def test_version_line_is_the_release_without_a_build_id(self):
        added, _removed = file_lines("desktop/source/app/cmdlinehelp.cxx")
        body = code(added)
        self.assertIn('        u"%PRODUCTNAME " HST_RELEASE "\\n"', body)
        self.assertNotIn("%BUILDID", body)


if __name__ == "__main__":
    unittest.main()
