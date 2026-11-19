# SPDX-License-Identifier: AGPL-3.0-only
"""Centimetres are the default measurement unit in all four apps, whatever the locale (hst-measure-unit-cm.patch).

Sheets, Slides and Draw read Layout/Other/MeasureUnit/Metric for metric locales (vi-VN) and .../NonMetric for the
others (en-US). Writer and Writer/Web read Layout/Other/MeasureUnit and, when it has no value, pick cm or inch from
the locale. The test resolves the value each app reads under en_US and vi_VN from the patch's new side and expects
centimetres (2) for every one.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches" / "libreoffice" / "hst-measure-unit-cm.patch"
SERIES = ROOT / "patches" / "libreoffice" / "series"
CENTIMETRE = 2  # FieldUnit::CM in the schema enumerations
METRIC_LOCALES = {"en_US": False, "vi_VN": True}  # LocaleData measurement system of each locale


def new_sides():
    """{schema file name: text of the patch's new side} for every file the patch touches."""
    sides, name, lines = {}, None, []
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ b/"):
            if name:
                sides[name] = "\n".join(lines)
            name, lines = line[len("+++ b/"):].rsplit("/", 1)[-1], []
        elif name and line[:1] in (" ", "+"):
            lines.append(line[1:])
    if name:
        sides[name] = "\n".join(lines)
    return sides


def prop_value(text, prop):
    """The default <value> of the prop, None when it has none."""
    match = re.search(r'<prop oor:name="%s"[^>]*>(.*?)</prop>' % prop, text, re.S)
    if not match:
        raise AssertionError(f"{prop} not in the patch")
    value = re.search(r"\n\s*<value>(\d+)</value>\s*$", match.group(1))
    return int(value.group(1)) if value else None


def metric_value(text):
    """Metric's default, which ends right before the NonMetric prop in the patch's context."""
    match = re.search(r'<value>(\d+)</value>\s*</prop>\s*<prop oor:name="NonMetric"', text)
    return int(match.group(1)) if match else None


class MeasureUnitCentimetres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sides = new_sides()

    def test_patch_is_in_the_series(self):
        self.assertIn("hst-measure-unit-cm.patch", SERIES.read_text(encoding="utf-8").split())

    def test_sheets_slides_draw_use_cm_in_every_locale(self):
        for schema in ("Calc.xcs", "Impress.xcs", "Draw.xcs"):
            text = self.sides[schema]
            for locale, metric in METRIC_LOCALES.items():
                with self.subTest(schema=schema, locale=locale):
                    value = metric_value(text) if metric else prop_value(text, "NonMetric")
                    self.assertEqual(value, CENTIMETRE)

    def test_writer_and_writer_web_use_cm_in_every_locale(self):
        # With a default value the locale fallback (cm or inch) is never reached.
        for schema in ("Writer.xcs", "WriterWeb.xcs"):
            for locale in METRIC_LOCALES:
                with self.subTest(schema=schema, locale=locale):
                    self.assertEqual(prop_value(self.sides[schema], "MeasureUnit"), CENTIMETRE)

    def test_only_defaults_change(self):
        # Schema defaults only: a unit the user picked lives in registrymodifications.xcu and still wins.
        changed = [line for line in PATCH.read_text(encoding="utf-8").splitlines()
                   if line[:1] in ("+", "-") and not line.startswith(("+++", "---"))]
        self.assertTrue(changed)
        for line in changed:
            self.assertRegex(line.strip(), r"^[+-]\s*<value>\d+</value>$")


if __name__ == "__main__":
    unittest.main()
