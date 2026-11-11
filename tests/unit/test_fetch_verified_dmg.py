# SPDX-License-Identifier: AGPL-3.0-only
"""scripts/macos/fetch-verified-dmg.sh: the old-profile job's beta.5 dmg comes from the cache, then GitHub, then the
published URL once, and only a file with the expected sha256 is accepted."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "macos" / "fetch-verified-dmg.sh"
GOOD = b"beta5 dmg bytes"
SHA = hashlib.sha256(GOOD).hexdigest()

# Stubs log each call; GH_MODE / CURL_MODE choose what they deliver.
GH = """#!/usr/bin/env bash
echo gh >> "$STUB_LOG"
dir=""; while [ $# -gt 0 ]; do [ "$1" = --dir ] && dir="$2"; shift; done
case "$GH_MODE" in
  good) printf 'beta5 dmg bytes' > "$dir/HSTOffice_1.0.0-beta.5_macOS_arm64.dmg" ;;
  other) printf 'other' > "$dir/HSTOffice_1.0.0-beta.5_macOS_arm64.dmg" ;;
  *) exit 1 ;;
esac
"""
CURL = """#!/usr/bin/env bash
echo curl >> "$STUB_LOG"
out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done
[ "$CURL_MODE" = good ] && printf 'beta5 dmg bytes' > "$out" || exit 28
"""


@unittest.skipUnless(shutil.which("shasum") and shutil.which("perl"), "shasum and perl needed")
class FetchVerifiedDmg(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for name, text in (("gh", GH), ("curl", CURL), ("sleep", "#!/usr/bin/env bash\n")):
            (bin_dir / name).write_text(text)
            (bin_dir / name).chmod(0o755)
        self.out = self.tmp / "old" / "beta5.dmg"
        self.log = self.tmp / "calls.log"
        self.env = dict(os.environ, PATH="%s:%s" % (bin_dir, os.environ["PATH"]), STUB_LOG=str(self.log),
                        GITHUB_REPOSITORY="owner/repo")

    def run_script(self, gh="fail", curl="fail", sha=SHA):
        env = dict(self.env, GH_MODE=gh, CURL_MODE=curl)
        done = subprocess.run(["bash", str(SCRIPT), str(self.out), sha, "42264935810", "artifact", "https://x/y.dmg"],
                              env=env, capture_output=True, text=True, timeout=60)
        calls = self.log.read_text().split() if self.log.exists() else []
        return done.returncode, calls

    def test_cached_dmg_needs_no_download(self):
        self.out.parent.mkdir()
        self.out.write_bytes(GOOD)
        self.assertEqual(self.run_script(), (0, []))

    def test_artifact_is_used_before_the_published_url(self):
        self.assertEqual(self.run_script(gh="good"), (0, ["gh"]))
        self.assertEqual(self.out.read_bytes(), GOOD)

    def test_a_different_artifact_is_not_retried_and_falls_back_once(self):
        self.assertEqual(self.run_script(gh="other", curl="good"), (0, ["gh", "curl"]))
        self.assertEqual(self.out.read_bytes(), GOOD)

    def test_failing_artifact_is_retried_then_the_url_is_tried_once(self):
        code, calls = self.run_script()
        self.assertEqual((code, calls), (1, ["gh", "gh", "gh", "curl"]))
        self.assertFalse(self.out.exists())

    def test_wrong_cached_file_is_replaced(self):
        self.out.parent.mkdir()
        self.out.write_bytes(b"stale")
        self.assertEqual(self.run_script(gh="good"), (0, ["gh"]))

    def test_bad_arguments_are_refused(self):
        self.assertEqual(self.run_script(sha="nope")[0], 64)


if __name__ == "__main__":
    unittest.main()
