# SPDX-License-Identifier: AGPL-3.0-only
"""The banner's core lets go of its workers without releasing the SolarMutex (hst-banner-detach-no-unlock.patch):
a release inside a window's dispose let the main thread resize a half-disposed border window."""
import re
import unittest

from patch_sections import added, after

PATCH = "hst-banner-detach-no-unlock.patch"
CORE = "vcl/source/control/HstBannerCore.cxx"


class BannerDetach(unittest.TestCase):
    def test_detach_never_waits_or_releases_the_solar_mutex(self):
        text = after(PATCH, CORE)
        body = re.search(r"void Core::Detach\(\)\n\{(.*?)\n\}\n", text, re.S).group(1)
        self.assertNotIn("SolarMutexReleaser", body)
        self.assertNotIn("join()", body)
        self.assertIn("g_aDetached.emplace_back(pThread);", body)
        self.assertIn("Application::PostUserEvent(LINK(nullptr, Core, JoinHdl))", body)

    def test_workers_are_joined_from_the_main_loop_and_at_exit(self):
        core = added(PATCH, CORE)
        self.assertIn("IMPL_STATIC_LINK_NOARG(Core, JoinHdl, void*, void)", core)
        self.assertIn("void JoinDetachedWorkers()", core)
        svmain = added(PATCH, "vcl/source/app/svmain.cxx")
        self.assertIn("hst::banner::JoinDetachedWorkers();", svmain)


if __name__ == "__main__":
    unittest.main()
