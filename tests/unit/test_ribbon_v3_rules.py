# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests of the v3 layout-dump rules (tests/runtime/ribbon_v3_rules.py) on synthetic dumps; no display needed."""
import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests", "runtime"))
import ribbon_v3_rules as R  # noqa: E402
from ribbon_v3_rules import RULES, dump_findings, dump_summary, dump_width, summarize  # noqa: E402


def rect(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def item(item_id, kind, x, y, w, h, label_cut=False):
    return {"id": item_id, "kind": kind, "rect": rect(x, y, w, h), "label_cut": label_cut}


def block(kind, *items):
    return {"type": kind, "items": list(items)}


def group(group_id, x, w, blocks, state="L"):
    """A group whose rect spans the body to the caption's bottom (y 0..104) and whose caption sits on the shared line."""
    return {"id": group_id, "caption": group_id, "state": state, "rect": rect(x, 0, w, 104),
            "caption_rect": rect(x, 86, w, 18), "caption_needed": 40, "blocks": blocks}


def dump(groups, banner="default", scale=1.0, body_h=106, wide=False, more=False, app="writer", tab="Trang đầu"):
    """A layout dump; banner=None is a tab without a banner (a rule 7 violation)."""
    if banner == "default":
        banner = rect(210, 6, 360, 96)
    return {"app": app, "tab": tab, "box": "pmhbHome", "scale": scale, "window": {"w": 1920, "h": 1040},
            "body": rect(0, 0, 1500, body_h), "track_width": 1000, "banner": banner,
            "more": more, "wide": wide, "sparse": "0000", "groups": groups}


def baseline():
    """A tab that passes every rule: a large group at x 0..100 and a 2 + 2 group of small boxes at x 100..200."""
    large = group("gdA", 0, 100, [block("large", item("bxA", "L", 0, 6, 100, 76))])
    small = group("gdB", 100, 100, [
        block("col", item("bxB1", "M", 100, 6, 45, 24), item("bxB2", "M", 100, 32, 45, 24)),
        block("col", item("bxB3", "M", 150, 6, 45, 24), item("bxB4", "M", 150, 32, 45, 24))], state="M")
    return dump([large, small])


def to_device(node, scale):
    """The same dump in device px at `scale`: every rect, caption width, track width and window size is multiplied."""
    out = copy.deepcopy(node)
    _scale(out, scale)
    out["scale"] = scale
    out["track_width"] = out["track_width"] * scale
    return out


def _scale(node, scale):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("x", "y", "w", "h", "caption_needed") and isinstance(value, (int, float)):
                node[key] = value * scale
            else:
                _scale(value, scale)
    elif isinstance(node, list):
        for value in node:
            _scale(value, scale)


def failed(d, rule):
    return [detail for name, ok, detail in dump_findings(d) if name == rule and ok is False]


def infos(d, rule):
    return [detail for name, ok, detail in dump_findings(d) if name == rule and ok is None]


class Baseline(unittest.TestCase):
    def test_baseline_has_no_violation(self):
        self.assertEqual([f for f in dump_findings(baseline()) if f[1] is False], [])

    def test_baseline_passes_at_a_device_scale(self):
        for scale in (1.25, 1.5):
            self.assertEqual([f for f in dump_findings(to_device(baseline(), scale)) if f[1] is False], [], scale)

    def test_every_rule_reports_at_least_one_result(self):
        names = {name for name, _ok, _detail in dump_findings(baseline())}
        self.assertEqual(names, set(RULES))

    def test_the_spec_example_at_125_percent_passes_the_banner_rule(self):
        d = dump([], banner=rect(1460, 8, 450, 120), scale=1.25)
        self.assertEqual(failed(d, "banner"), [])

    def test_dump_width_is_the_logical_window_width(self):
        d = dump([], scale=1.25)
        d["window"] = {"w": 1920, "h": 1040}
        self.assertEqual(dump_width(d), 1536)
        self.assertEqual(dump_width(to_device(baseline(), 1.25)), 1920)


class Body(unittest.TestCase):
    def test_a_body_under_106_fails(self):
        self.assertTrue(failed(dump([], body_h=100), "body"))

    def test_a_body_of_106_passes(self):
        self.assertEqual(failed(dump([], body_h=106), "body"), [])


class Band(unittest.TestCase):
    def test_a_small_item_off_its_row_fails(self):
        d = baseline()
        d["groups"][1]["blocks"][0]["items"][0]["rect"]["y"] = 10
        self.assertTrue(failed(d, "band"))

    def test_a_large_item_not_spanning_6_to_82_fails(self):
        d = baseline()
        d["groups"][0]["blocks"][0]["items"][0]["rect"]["h"] = 74
        self.assertTrue(failed(d, "band"))

    def test_one_pixel_of_toolkit_rounding_passes(self):
        d = baseline()
        d["groups"][1]["blocks"][0]["items"][0]["rect"].update(y=7, h=24)  # top 7, bottom 31
        self.assertEqual(failed(d, "band"), [])


class Edge(unittest.TestCase):
    def test_a_block_beside_a_large_button_must_span_6_to_82(self):
        d = baseline()
        d["groups"][0]["blocks"].append(block("col", item("bxA2", "S", 0, 32, 45, 24), item("bxA3", "S", 0, 58, 45, 24)))
        self.assertEqual(len(failed(d, "edge")), 1)

    def test_a_group_without_large_items_is_not_checked(self):
        d = baseline()
        d["groups"][1]["blocks"].append(block("col", item("bxB5", "S", 100, 6, 45, 24)))
        self.assertEqual(failed(d, "edge"), [])


class OneSize(unittest.TestCase):
    def test_a_group_with_large_and_small_items_fails(self):
        d = baseline()
        d["groups"][1]["blocks"].append(block("large", item("bxB9", "L", 100, 6, 100, 76)))
        self.assertTrue(failed(d, "one_size"))

    def test_the_clipboard_group_is_allowed_and_reported_apart(self):
        clip = group("gdHomeClipboard", 0, 100, [block("large", item("bxP", "L", 0, 6, 45, 76)),
                                                 block("col", item("bxC1", "S", 50, 6, 24, 24),
                                                       item("bxC2", "S", 50, 32, 24, 24),
                                                       item("bxC3", "S", 50, 58, 24, 24))])
        d = dump([clip])
        self.assertEqual(failed(d, "one_size"), [])
        self.assertTrue(infos(d, "one_size"))


class EqualWidth(unittest.TestCase):
    def test_large_items_of_one_group_must_share_a_width(self):
        d = baseline()
        d["groups"][0]["blocks"][0]["items"] = [item("bxA", "L", 0, 6, 40, 76), item("bxA2", "L", 40, 6, 60, 76)]
        self.assertTrue(failed(d, "equal_width"))

    def test_large_items_of_two_groups_must_share_a_width_on_the_tab(self):
        other = group("gdC", 100, 90, [block("large", item("bxC", "L", 100, 6, 90, 76))])
        d = dump([group("gdA", 0, 100, [block("large", item("bxA", "L", 0, 6, 100, 76))]), other])
        details = failed(d, "equal_width")
        self.assertEqual(len(details), 1)
        self.assertIn("tab", details[0])

    def test_small_boxes_in_columns_must_share_a_width(self):
        d = baseline()
        d["groups"][1]["blocks"][1]["items"][1]["rect"]["w"] = 40
        self.assertTrue(failed(d, "equal_width"))

    def test_equal_widths_pass(self):
        self.assertEqual(failed(baseline(), "equal_width"), [])


class Columns(unittest.TestCase):
    def test_a_column_of_one_item_fails(self):
        d = baseline()
        del d["groups"][1]["blocks"][1]["items"][1]
        self.assertTrue(failed(d, "lone_col"))
        self.assertEqual(failed(d, "cols_3plus1"), [])

    def test_three_plus_one_fails_as_a_mixed_column_count(self):
        d = baseline()
        d["groups"][1]["blocks"] = [block("col", item("a", "M", 100, 6, 45, 24), item("b", "M", 100, 32, 45, 24),
                                          item("c", "M", 100, 58, 45, 24)),
                                    block("col", item("d", "M", 150, 6, 45, 24))]
        self.assertTrue(failed(d, "cols_3plus1"))
        self.assertTrue(failed(d, "lone_col"))

    def test_two_plus_two_passes(self):
        self.assertEqual(failed(baseline(), "cols_3plus1"), [])


class Banner(unittest.TestCase):
    def test_a_missing_banner_fails(self):
        self.assertTrue(failed(dump([group("gdA", 0, 100, [])], banner=None), "banner"))

    def test_width_limits_are_360_to_960(self):
        for width, ok in ((358, False), (360, True), (960, True), (962, False)):
            d = dump([], banner=rect(0, 6, width, 96))
            self.assertEqual(not failed(d, "banner"), ok, width)

    def test_height_must_be_96(self):
        self.assertTrue(failed(dump([], banner=rect(0, 6, 360, 104)), "banner"))

    def test_top_must_be_6(self):
        self.assertTrue(failed(dump([], banner=rect(0, 20, 360, 96)), "banner"))


class ElasticFill(unittest.TestCase):
    def test_free_room_up_to_34_px_passes(self):  # gap 8, the collapse chevron's 22, slack 4
        self.assertEqual(failed(dump(baseline()["groups"], banner=rect(234, 6, 360, 96)), "elastic_fill"), [])

    def test_more_than_34_px_free_fails(self):
        self.assertTrue(failed(dump(baseline()["groups"], banner=rect(240, 6, 360, 96)), "elastic_fill"))

    def test_at_960_the_free_room_is_information_only(self):
        d = dump(baseline()["groups"], banner=rect(260, 6, 960, 96))
        self.assertEqual(failed(d, "elastic_fill"), [])
        self.assertTrue(infos(d, "elastic_fill"))


class Captions(unittest.TestCase):
    def test_captions_must_share_one_bottom_line(self):
        d = baseline()
        d["groups"][1]["caption_rect"]["y"] = 84
        self.assertTrue(failed(d, "captions"))

    def test_a_caption_wider_than_its_rect_is_cut(self):
        d = baseline()
        d["groups"][1]["caption_needed"] = 150
        self.assertTrue(failed(d, "captions"))

    def test_a_caption_below_the_body_fails(self):
        d = baseline()
        d["groups"][0]["caption_rect"]["y"] = 95
        self.assertTrue(failed(d, "captions"))

    def test_a_missing_caption_rect_fails(self):
        d = baseline()
        del d["groups"][0]["caption_rect"]
        self.assertTrue(failed(d, "captions"))


class Clip(unittest.TestCase):
    def test_an_item_past_the_body_bottom_fails(self):
        d = baseline()
        d["groups"][0]["blocks"][0]["items"][0]["rect"]["h"] = 104
        self.assertTrue(failed(d, "clip"))

    def test_a_group_past_the_banner_minus_8_fails(self):
        d = dump(baseline()["groups"], banner=rect(205, 6, 360, 96))
        self.assertTrue(failed(d, "clip"))

    def test_a_group_inside_the_banner_gap_passes(self):
        self.assertEqual(failed(baseline(), "clip"), [])


class LabelAndWidening(unittest.TestCase):
    def test_a_cut_label_fails(self):
        d = baseline()
        d["groups"][1]["blocks"][0]["items"][0]["label_cut"] = True
        self.assertTrue(failed(d, "label_cut"))

    @staticmethod
    def cut_box(extra_w, extra_h, scale=1):
        """The baseline with a box whose size request is its rect plus extra_w, extra_h device px."""
        d = baseline()
        d["scale"] = scale
        box = d["groups"][1]["blocks"][0]["items"][0]
        box.update(label_cut=True, want={"w": box["rect"]["w"] + extra_w, "h": box["rect"]["h"] + extra_h})
        return d

    def test_a_box_asking_a_little_more_height_than_its_row_passes(self):
        self.assertEqual(failed(self.cut_box(0, 3), "label_cut"), [])

    def test_a_box_asking_much_more_height_than_its_row_fails(self):
        self.assertTrue(failed(self.cut_box(0, 5), "label_cut"))

    def test_a_box_asking_more_width_fails(self):
        self.assertTrue(failed(self.cut_box(1, 0), "label_cut"))

    def test_a_native_box_asking_only_more_height_is_information(self):
        d = self.cut_box(0, 7)  # Table Design's fill style at 125 %: asks 31 px in a 24 px row
        d["groups"][1]["blocks"][0]["items"][0]["native_cut"] = True
        self.assertEqual(failed(d, "label_cut"), [])

    def test_a_native_box_asking_more_width_fails(self):
        d = self.cut_box(1, 7)
        d["groups"][1]["blocks"][0]["items"][0]["native_cut"] = True
        self.assertTrue(failed(d, "label_cut"))

    def test_the_slack_is_in_logical_px(self):
        self.assertEqual(failed(self.cut_box(0, 8, scale=2), "label_cut"), [])
        self.assertTrue(failed(self.cut_box(0, 9, scale=2), "label_cut"))

    def test_a_box_drawing_its_native_frame_cut_is_only_information(self):
        d = baseline()
        d["groups"][1]["blocks"][0]["items"][0]["native_cut"] = True
        self.assertEqual(failed(d, "label_cut"), [])
        self.assertEqual(dump_summary(d)["native_cut"], ["gdB bxB1"])
        self.assertEqual(summarize([d])["native_cut"], [f"{d['app']} {d['tab']} @{dump_width(d)}: gdB bxB1"])

    def test_a_box_with_its_frame_whole_passes(self):
        d = baseline()
        d["groups"][1]["blocks"][0]["items"][0]["native_cut"] = False
        self.assertEqual(failed(d, "label_cut"), [])

    def test_a_box_shown_in_part_fails(self):
        d = baseline()
        d["groups"][1]["blocks"][0]["items"][0]["box_clip"] = {"h": 24, "shown": 20, "by": "toolbox"}
        self.assertEqual(failed(d, "label_cut"), ["gdB bxB1 box shown 20 of 24 px (cut by toolbox)"])

    def test_a_box_shown_whole_passes(self):
        d = baseline()
        d["groups"][1]["blocks"][0]["items"][0]["box_clip"] = {"h": 24, "shown": 24, "by": ""}
        self.assertEqual(failed(d, "label_cut"), [])

    def test_a_wide_dump_needs_large_items_of_96(self):
        d = baseline()
        d["wide"] = True
        self.assertTrue(failed(d, "widening"))  # the baseline large item is 100 wide
        d["groups"][0]["blocks"][0]["items"][0]["rect"]["w"] = 96
        self.assertEqual(failed(d, "widening"), [])

    def test_a_wide_tab_whose_widest_label_needs_more_than_96_widens_to_it(self):
        d = baseline()
        d["wide"] = True
        d["large_natural"] = 97  # Writer's Help on Linux at 125 %: rounded up to 98
        d["groups"][0]["blocks"][0]["items"][0]["rect"]["w"] = 98
        self.assertEqual(failed(d, "widening"), [])
        d["groups"][0]["blocks"][0]["items"][0]["rect"]["w"] = 96
        self.assertTrue(failed(d, "widening"))

    def test_a_narrow_natural_keeps_96(self):
        d = baseline()
        d["wide"] = True
        d["large_natural"] = 60
        d["groups"][0]["blocks"][0]["items"][0]["rect"]["w"] = 96
        self.assertEqual(failed(d, "widening"), [])

    def test_a_dump_that_is_not_wide_is_not_checked(self):
        d = baseline()
        d["groups"][0]["blocks"][0]["items"][0]["rect"]["w"] = 90
        self.assertEqual(failed(d, "widening"), [])
        self.assertTrue(infos(d, "widening"))


class FoldedGroups(unittest.TestCase):
    def test_a_folded_group_skips_the_size_and_band_rules(self):
        folded = group("gdF", 100, 100, [block("fold", item("fold", "C", 100, 10, 100, 40))], state="C")
        d = dump([group("gdA", 0, 100, [block("large", item("bxA", "L", 0, 6, 100, 76))]), folded])
        self.assertEqual([f for f in dump_findings(d) if f[1] is False], [])
        self.assertEqual(dump_summary(d)["folded"], 1)


class Summary(unittest.TestCase):
    def test_dump_summary_reports_the_used_share_and_banner(self):
        s = dump_summary(baseline())
        self.assertEqual((s["width"], s["folded"], s["more"], s["banner_w"], s["used_pct"]), (1920, 0, False, 360, 20.0))

    def test_summarize_counts_violations_per_rule(self):
        bad = baseline()
        del bad["groups"][1]["blocks"][1]["items"][1]
        none = dump(baseline()["groups"], banner=None)
        wide_banner = dump(baseline()["groups"], banner=rect(210, 6, 500, 96))
        s = summarize([baseline(), bad, none, wide_banner])
        self.assertEqual(s["dumps"], 4)
        self.assertEqual(s["rules"]["lone_col"], 1)
        self.assertEqual(s["rules"]["banner"], 1)
        self.assertEqual(s["rules"]["band"], 0)
        self.assertEqual(s["banner"], {"min": 360, "median": 360, "max": 500})

    def test_summarize_lists_folded_and_overflow_tabs(self):
        folded = group("gdF", 100, 100, [block("fold", item("fold", "C", 100, 10, 100, 40))], state="C")
        d = dump([folded], more=True)
        s = summarize([d])
        self.assertEqual(s["folded"], ["writer Trang đầu @1920"])
        self.assertEqual(s["more"], ["writer Trang đầu @1920"])

    def test_summarize_of_no_dump_has_no_banner_statistics(self):
        self.assertIsNone(summarize([])["banner"])


class OrderRuleTest(unittest.TestCase):
    """The groups stand left to right in the design's order."""

    @staticmethod
    def dump(ids_by_x):
        return {"app": "draw", "groups": [{"id": g, "rect": {"x": x}} for g, x in ids_by_x]}

    def test_design_order_passes(self):
        dump = self.dump([("gdEdit", 0), ("gdPdf", 130), ("gdSign", 390)])
        self.assertEqual(R._order(dump, [["gdEdit", "gdPdf", "gdSign", "gdHst"]]), [("order", True, "pass")])

    def test_a_group_shown_first_out_of_order_fails(self):
        dump = self.dump([("gdSign", 0), ("gdHst", 176), ("gdEdit", 268), ("gdPdf", 398)])
        (rule, ok, detail), = R._order(dump, [["gdEdit", "gdPdf", "gdSign", "gdHst"]])
        self.assertEqual((rule, ok), ("order", False))
        self.assertIn("gdSign", detail)

    def test_a_tab_missing_from_the_data_is_information(self):
        self.assertEqual(R._order(self.dump([("gdOther", 0)]), [["gdEdit"]])[0][1], None)

    def test_the_real_data_knows_every_app(self):
        for app in ("writer", "calc", "impress", "draw"):
            self.assertTrue(R._tab_orders(app), app)


if __name__ == "__main__":
    unittest.main()
