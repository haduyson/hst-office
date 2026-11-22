# SPDX-License-Identifier: LicenseRef-HST-Proprietary
# Copyright (C) 2026 HASON TECH
"""scripts/linux/soffice_gstreamer_env.py: program/soffice ranks GStreamer's dfbvideosink NONE without losing the
user's GST_PLUGIN_FEATURE_RANK (the snippet runs in a real /bin/sh)."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/linux"))
import soffice_gstreamer_env as MOD  # noqa: E402

# the end of the LibreOffice soffice script; the fake oosplash prints what it got
SCRIPT = """#!/bin/sh
sd_prog=$(dirname "$0")
exec $RRCHECK $VALGRINDCHECK $STRACECHECK "$sd_prog/oosplash" "$@"
"""


class SofficeGstreamerEnv(unittest.TestCase):
    def run_soffice(self, env_value):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp) / "opt/hst-office1.0/program"
            prog.mkdir(parents=True)
            (prog / "soffice").write_text(SCRIPT, encoding="utf-8")
            (prog / "soffice").chmod(0o755)
            (prog / "oosplash").write_text('#!/bin/sh\nprintf "%s|%s" "${GST_PLUGIN_FEATURE_RANK-unset}" "$*"\n')
            (prog / "oosplash").chmod(0o755)
            MOD.patch_tree(Path(tmp), "/opt/hst-office1.0")
            self.assertTrue(os.access(prog / "soffice", os.X_OK))  # mode kept
            env = {k: v for k, v in os.environ.items() if k != "GST_PLUGIN_FEATURE_RANK"}
            if env_value is not None:
                env["GST_PLUGIN_FEATURE_RANK"] = env_value
            out = subprocess.run([str(prog / "soffice"), "--writer", "a b.docx"], env=env, capture_output=True,
                                 text=True, check=True).stdout
            return out.split("|")

    def test_unset_gets_none_rank(self):
        self.assertEqual(self.run_soffice(None), ["dfbvideosink:NONE", "--writer a b.docx"])

    def test_empty_gets_none_rank(self):
        self.assertEqual(self.run_soffice("")[0], "dfbvideosink:NONE")

    def test_user_value_is_appended_to(self):
        self.assertEqual(self.run_soffice("xvimagesink:MAX")[0], "xvimagesink:MAX,dfbvideosink:NONE")

    def test_user_rank_of_dfbvideosink_wins(self):
        self.assertEqual(self.run_soffice("dfbvideosink:PRIMARY")[0], "dfbvideosink:PRIMARY")
        self.assertEqual(self.run_soffice("a:1,dfbvideosink:256")[0], "a:1,dfbvideosink:256")

    def test_idempotent_and_before_exec(self):
        once = MOD.add_to_script(SCRIPT)
        self.assertEqual(MOD.add_to_script(once), once)
        self.assertLess(once.index(MOD.MARKER), once.index('exec $RRCHECK'))

    def test_script_without_exec_is_refused(self):
        with self.assertRaises(ValueError):
            MOD.add_to_script("#!/bin/sh\necho no exec\n")

    def test_packages_recommend_x_video_sinks(self):
        import rpm_spec
        import single_deb_control
        self.assertIn("gstreamer1.0-x", Path(single_deb_control.__file__).read_text(encoding="utf-8"))
        self.assertIn("(gstreamer1-plugins-base or gstreamer-plugins-base)", rpm_spec.RECOMMENDS)
        self.assertIn("add_gstreamer_env(stage, INSTALL_ROOT)", (ROOT / "scripts/linux/make-single-deb.py").read_text())


if __name__ == "__main__":
    unittest.main()
