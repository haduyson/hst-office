# SPDX-License-Identifier: AGPL-3.0-only
"""ZIP entry times of the built extension (scripts/build-extensions.py entry_time).

The office's Python reuses a cached .pyc from the user profile while the source's mtime and size match
(hst-python-no-bytecode.patch), so an edited module must not keep the time of the previous build."""
import importlib.util
import os
import unittest

import _paths

spec = importlib.util.spec_from_file_location("build_extensions", os.path.join(_paths.ROOT, "scripts", "build-extensions.py"))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class EntryTimes(unittest.TestCase):
    def test_reproducible_and_different_for_an_edit_of_the_same_size(self):
        before, after = b"RETRY_DELAYS = (120, 600)\n", b"RETRY_DELAYS = (180, 600)\n"
        self.assertEqual(len(before), len(after))
        self.assertEqual(build.entry_time(before), build.entry_time(before))
        self.assertNotEqual(build.entry_time(before), build.entry_time(after))

    def test_valid_zip_times_within_the_span(self):
        import datetime
        start = datetime.datetime(*build.FIXED_TIME)
        for data in (b"", b"x", os.urandom(64)):
            when = datetime.datetime(*build.entry_time(data))
            self.assertLessEqual(start, when)
            self.assertLess((when - start).total_seconds(), build.ENTRY_TIME_SPAN)
            self.assertEqual(when.second % 2, 0)  # ZIP stores seconds in 2 s steps


if __name__ == "__main__":
    unittest.main()
