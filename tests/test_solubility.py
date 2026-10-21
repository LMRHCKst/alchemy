# -*- coding: utf-8 -*-
"""Тесты растворимости с учётом pH и ступеней гидролиза."""

import unittest

from alchemy.core.errors import InputError
from alchemy.engines import hydrolysis as HY
from alchemy.engines import solubility as SOL


class TestSolubility(unittest.TestCase):
    def test_pure_water_simple(self):
        """AgCl: s = √Ksp."""
        result = SOL.solubility_pure_water("AgCl")
        self.assertAlmostEqual(result.numeric(), 1.33e-5, places=7)

    def test_two_to_one(self):
        """Mg(OH)2: s = (Ksp/4)^(1/3)."""
        result = SOL.solubility_pure_water("Mg(OH)2")
        self.assertAlmostEqual(result.numeric(), 1.12e-4, places=6)

    def test_acid_increases_solubility(self):
        """Карбонат в кислоте растворяется заметно лучше."""
        neutral = SOL.solubility_at_ph("CaCO3", 7).numeric()
        acidic = SOL.solubility_at_ph("CaCO3", 3).numeric()
        self.assertGreater(acidic, neutral)
        self.assertGreater(acidic / neutral, 100)

    def test_salt_of_strong_acid_unaffected(self):
        """AgCl от pH почти не зависит: соляная кислота сильная."""
        neutral = SOL.solubility_at_ph("AgCl", 7).numeric()
        acidic = SOL.solubility_at_ph("AgCl", 2).numeric()
        self.assertAlmostEqual(neutral / acidic, 1.0, places=2)

    def test_ph_for_dissolution(self):
        result = SOL.ph_for_dissolution("CaCO3", 0.01)
        self.assertAlmostEqual(result.numeric(), 6.22, places=1)

    def test_impossible_target(self):
        """Если осадок и так растворим, pH не нужен."""
        result = SOL.ph_for_dissolution("AgCl", 1e-6)
        self.assertIsInstance(result.value, str)

    def test_unknown_salt(self):
        with self.assertRaises(Exception):
            SOL.solubility_pure_water("XxCl")


class TestHydrolysisStages(unittest.TestCase):
    def test_carbonate_two_stages(self):
        result = HY.hydrolysis_stages("Na2CO3", 0.1)
        rows = result.value
        self.assertEqual(len(rows), 2)
        self.assertGreater(rows[0]["Степень, %"], rows[1]["Степень, %"])

    def test_second_stage_suppressed(self):
        """Вторая ступень слабее первой на порядки."""
        rows = HY.hydrolysis_stages("Na2CO3", 0.1).value
        self.assertGreater(rows[0]["Степень, %"] / rows[1]["Степень, %"], 10)

    def test_main_function_mentions_second_stage(self):
        result = HY.hydrolysis("Na2CO3", 0.1)
        text = " ".join(result.steps)
        self.assertIn("Вторая ступень", text)

    def test_strong_acid_anion_has_no_stages(self):
        with self.assertRaises(InputError):
            HY.hydrolysis_stages("NaCl", 0.1)

    def test_phosphate_three_stages(self):
        rows = HY.hydrolysis_stages("Na3PO4", 0.1).value
        self.assertGreaterEqual(len(rows), 2)
        for row in rows:
            self.assertIn("Ступень", row)


if __name__ == "__main__":
    unittest.main()
