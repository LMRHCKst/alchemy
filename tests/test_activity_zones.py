# -*- coding: utf-8 -*-
"""Гибридная политика активностей: зоны, предупреждения, отказ."""

import unittest

from alchemy.core.errors import DomainError
from alchemy.engines import acidbase as AB


class TestZones(unittest.TestCase):
    def test_zone_boundaries(self):
        self.assertEqual(AB.activity_zone(0.0005), "limiting")
        self.assertEqual(AB.activity_zone(0.05), "extended")
        self.assertEqual(AB.activity_zone(0.3), "davies")
        self.assertEqual(AB.activity_zone(0.5), "davies")
        self.assertEqual(AB.activity_zone(0.6), "beyond")

    def test_error_grows_with_zone(self):
        errors = [AB._expected_error(I) for I in (0.0005, 0.05, 0.3, 1.0, 2.0)]
        self.assertEqual(errors, sorted(errors))
        self.assertLess(errors[0], errors[-1])

    def test_report_on_good_zone(self):
        report = AB.activity_report(1, 0.05)
        self.assertTrue(report["usable"])
        self.assertEqual(report["zone"], "extended")
        self.assertAlmostEqual(report["gamma"], 0.8064, places=3)

    def test_report_when_unusable(self):
        report = AB.activity_report(2, 8.0)
        self.assertFalse(report["usable"])
        self.assertEqual(report["zone"], "beyond")
        self.assertIn("Питцера", report["note"])


class TestWarningsAndSteps(unittest.TestCase):
    def test_quiet_in_good_zone(self):
        result = AB.weak_acid_ph(0.1, 1.8e-5, ionic_strength_=0.05)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.meta["activity_zone"], "extended")

    def test_warns_on_davies(self):
        result = AB.weak_acid_ph(0.1, 1.8e-5, ionic_strength_=0.3)
        self.assertTrue(result.warnings)
        self.assertIn("Дэвиса", result.warnings[0])

    def test_warns_loudly_beyond(self):
        result = AB.weak_acid_ph(0.1, 1.8e-5, ionic_strength_=1.0)
        self.assertTrue(result.warnings)
        self.assertIn("десятков процентов", result.warnings[0])

    def test_model_is_in_steps(self):
        result = AB.weak_acid_ph(0.1, 1.8e-5, ionic_strength_=0.3)
        self.assertTrue(any("Модель активностей" in step
                            for step in result.steps))

    def test_refuses_absurd_value(self):
        with self.assertRaises(DomainError):
            AB.activity_coefficient(2, 8.0)


if __name__ == "__main__":
    unittest.main()
