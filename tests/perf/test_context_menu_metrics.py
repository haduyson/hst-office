# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests for the context-menu latency analyzer, matrix expansion and fixtures."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "perf"))
import context_menu_env as cenv  # noqa: E402
import context_menu_fixtures as cfix  # noqa: E402
import context_menu_metrics as m  # noqa: E402

# Hand-written snippet in the layout of macOS `sample` output (format sample, NOT measured data).
SAMPLE_TEXT = """Call graph:
    900 Thread_1   DispatchQueue_1: com.apple.main-thread  (serial)
    + 900 -[NSCell performClickWithFrame:inView:]  (in AppKit) + 12  [0x1]
    +   ! 700 CreateNSImage(Image const&)  (in libvclplug_osxlo.dylib) + 40  [0x2]
    +   ! : 650 -[NSImage lockFocusFlipped:]  (in AppKit) + 8  [0x3]

Total number in stack (recursive counted multiple, when >=5):

Sort by top of stack, same collapsed (when >= 5):
        mach_msg2_trap  (in libsystem_kernel.dylib)        500
        -[NSImage lockFocusFlipped:]  (in AppKit)        120
        framework::MenuBarManager::Activate(Menu*)  (in libfwklo.dylib)        30

"""


def doc(cell_id, start, values, timeouts=0):
    trials = [{"i": i + 1, "ms": v, "timeout": False} for i, v in enumerate(values)]
    trials += [{"i": len(trials) + k + 1, "ms": None, "timeout": True} for k in range(timeouts)]
    return {"cell": {"id": cell_id, "start": start}, "trials": trials}


class StatsTests(unittest.TestCase):
    def test_percentile_nearest_rank(self):
        vals = list(range(1, 101))
        self.assertEqual(m.percentile(vals, 95), 95)
        self.assertEqual(m.percentile(vals, 90), 90)
        self.assertEqual(m.percentile([5], 99), 5)
        self.assertIsNone(m.percentile([], 50))

    def test_median(self):
        self.assertEqual(m.median([3, 1, 2]), 2)
        self.assertEqual(m.median([4, 1, 2, 3]), 2.5)

    def test_summary_counts_timeouts_separately(self):
        s = m.summarize_trials(doc("c", "warm", [10, 20, 30], timeouts=1)["trials"])
        self.assertEqual((s["n"], s["ok"], s["timeouts"]), (4, 3, 1))
        self.assertEqual(s["max_ms"], 30)


class CompareTests(unittest.TestCase):
    targets = {"warm_p95_ms": 150.0, "cold_p95_ms": 400.0}

    def test_regression_needs_both_percent_and_floor(self):
        base = {"p95_ms": 100.0}
        self.assertFalse(m.regression(base, {"p95_ms": 115.0}, 10, 20))  # +15%, only 15 ms
        self.assertFalse(m.regression({"p95_ms": 400.0}, {"p95_ms": 425.0}, 10, 20))  # 25 ms but 6%
        self.assertTrue(m.regression(base, {"p95_ms": 125.0}, 10, 20))

    def test_missing_baseline_fails(self):
        with self.assertRaises(ValueError):
            m.compare_runs({}, {"a": doc("a", "warm", [1])}, self.targets, 10, 20)

    def test_missing_cell_and_target_violations(self):
        base = {"a": doc("a", "warm", [50] * 20), "b": doc("b", "cold", [100] * 5)}
        cand = {"a": doc("a", "warm", [200] * 20), "c": doc("c", "warm", [10])}
        res = m.compare_runs(base, cand, self.targets, 10, 20)
        text = "\n".join(res["failures"])
        self.assertFalse(res["passed"])
        self.assertIn("b: missing in candidate", text)
        self.assertIn("c: missing in baseline", text)
        self.assertIn("a: p95 200.0 ms > 150 ms", text)
        self.assertIn("a: regression", text)

    def test_pass_and_timeout_failure(self):
        base = {"a": doc("a", "warm", [50] * 10)}
        ok = m.compare_runs(base, {"a": doc("a", "warm", [52] * 10)}, self.targets, 10, 20)
        self.assertTrue(ok["passed"])
        bad = m.compare_runs(base, {"a": doc("a", "warm", [52] * 10, timeouts=1)}, self.targets, 10, 20)
        self.assertIn("timeout", "\n".join(bad["failures"]))

    def test_load_runs_roundtrip_and_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.json").write_text(json.dumps(doc("a", "warm", [1, 2])), encoding="utf-8")
            Path(tmp, "env.json").write_text("{}", encoding="utf-8")
            self.assertEqual(list(m.load_runs(Path(tmp))), ["a"])
        with self.assertRaises(FileNotFoundError):
            m.load_runs(Path(tmp) / "nope")


class SampleParseTests(unittest.TestCase):
    def test_top_of_stack_section(self):
        frames = m.parse_sample_top(SAMPLE_TEXT)
        self.assertEqual(frames[0]["symbol"], "mach_msg2_trap")
        self.assertEqual(frames[1]["samples"], 120)
        self.assertIn("lockFocus", m.flag_suspects(frames))
        self.assertIn("MenuBarManager::Activate", m.flag_suspects(frames))

    def test_call_graph_fallback(self):
        frames = m.parse_sample_top(SAMPLE_TEXT.split("Total number")[0])
        self.assertTrue(frames[0].get("inclusive"))
        symbols = " ".join(f["symbol"] for f in frames)
        self.assertIn("CreateNSImage", symbols)
        self.assertEqual(max(f["samples"] for f in frames), 900)


class MatrixAndFixtureTests(unittest.TestCase):
    def setUp(self):
        self.matrix = json.loads((ROOT / "scripts/perf/context-menu-matrix.json").read_text(encoding="utf-8"))

    def test_presets_expand_unique_ids(self):
        for name in self.matrix["presets"]:
            ids = [c["id"] for c in cenv.expand_preset(self.matrix, name)]
            self.assertEqual(len(ids), len(set(ids)), name)
        self.assertEqual(len(cenv.expand_preset(self.matrix, "full")), 3 * 2 * 2 * 2 * 2)
        self.assertEqual(len(cenv.expand_preset(self.matrix, "linux-parity")), 6)

    def test_unknown_preset(self):
        with self.assertRaises(ValueError):
            cenv.expand_preset(self.matrix, "nope")

    def test_fixtures_match_manifest(self):
        manifest = json.loads((ROOT / "tests/fixtures/perf/manifest.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            entries = cfix.write_fixtures(Path(tmp))
        self.assertEqual(entries, manifest["fixtures"])

    def test_profile_sets_autospell(self):
        with tempfile.TemporaryDirectory() as tmp:
            prof = cenv.prepare_profile({"profile": "clean", "autospell": "off"}, Path(tmp), None)
            xcu = (prof / "user" / "registrymodifications.xcu").read_text(encoding="utf-8")
        self.assertIn('IsSpellAuto" oor:op="fuse"><value>false', xcu)


if __name__ == "__main__":
    unittest.main()
