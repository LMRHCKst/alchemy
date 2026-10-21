# -*- coding: utf-8 -*-
"""Тесты трёх новых школьных движков: валентность, ионы, гидролиз."""

import unittest

from alchemy.core.errors import InputError
from alchemy.engines import hydrolysis as HD
from alchemy.engines import ioniceq as IE
from alchemy.engines import valence as VL


class TestValence(unittest.TestCase):
    def test_oxides(self):
        cases = {
            "H2O": (1, 2), "CO2": (4, 2), "SO3": (6, 2), "N2O5": (5, 2),
            "P2O5": (5, 2), "Fe2O3": (3, 2), "MnO2": (4, 2),
        }
        for formula, expected in cases.items():
            result = VL.valences(formula)
            self.assertEqual(
                (result.meta["valency_first"], result.meta["valency_second"]),
                expected, formula)

    def test_chlorides(self):
        self.assertEqual(VL.valences("CaCl2").meta["valency_first"], 2)
        self.assertEqual(VL.valences("CuCl").meta["valency_second"], 1)
        self.assertEqual(VL.valences("Al4C3").meta["valency_second"], 4)

    def test_not_binary(self):
        with self.assertRaises(InputError):
            VL.valences("H2SO4")

    def test_formula_from_valence(self):
        cases = [
            ("Al", 3, "O", 2, "Al2O3"),
            ("Ca", 2, "Cl", 1, "CaCl2"),
            ("H", 1, "S", 2, "H2S"),
            ("P", 5, "O", 2, "P2O5"),
            ("Na", 1, "O", 2, "Na2O"),
        ]
        for first, v1, second, v2, expected in cases:
            self.assertEqual(
                VL.formula_from_valence(first, v1, second, v2).value,
                expected)

    def test_reduces_indices(self):
        """Ca(II) и O(II) дают CaO, а не Ca2O2."""
        self.assertEqual(VL.formula_from_valence("Ca", 2, "O", 2).value, "CaO")

    def test_impossible_valency(self):
        with self.assertRaises(InputError):
            VL.formula_from_valence("Na", 3, "O", 2)


class TestIonic(unittest.TestCase):
    def test_neutralisation(self):
        result = IE.ionic_equation("NaOH + HCl = NaCl + H2O")
        self.assertEqual(result.value, "H^+ + OH^- = H2O")

    def test_precipitation(self):
        result = IE.ionic_equation("BaCl2 + Na2SO4 = BaSO4 + 2NaCl")
        self.assertEqual(result.value, "Ba^2+ + SO4^2- = BaSO4")

    def test_weak_acid_stays_molecular(self):
        result = IE.ionic_equation("CaCO3 + 2HCl = CaCl2 + CO2 + H2O")
        self.assertIn("CaCO3", result.value)
        self.assertIn("CO2", result.value)

    def test_insoluble_base(self):
        result = IE.ionic_equation("Fe(OH)3 + 3HNO3 = Fe(NO3)3 + 3H2O")
        self.assertIn("Fe(OH)3", result.value)
        self.assertIn("Fe^3+", result.value)

    def test_coefficients_are_reduced(self):
        result = IE.ionic_equation("H2SO4 + 2KOH = K2SO4 + 2H2O")
        self.assertEqual(result.value, "H^+ + OH^- = H2O")

    def test_steps_present(self):
        result = IE.ionic_equation("AgNO3 + NaCl = AgCl + NaNO3")
        text = " ".join(result.steps)
        self.assertIn("Молекулярное", text)
        self.assertIn("Полное ионное", text)


class TestHydrolysis(unittest.TestCase):
    def test_no_hydrolysis(self):
        for salt in ("NaCl", "KNO3", "Na2SO4"):
            self.assertEqual(HD.salt_type(salt)["kind"], "none", salt)

    def test_anion_hydrolysis_is_alkaline(self):
        result = HD.hydrolysis("Na2CO3", 0.1)
        self.assertAlmostEqual(result.meta["ph"], 11.67, places=1)
        self.assertIn("щелочная", result.value)

    def test_acetate(self):
        result = HD.hydrolysis("CH3COONa", 0.1)
        self.assertAlmostEqual(result.meta["ph"], 8.88, places=1)

    def test_cation_hydrolysis_is_acidic(self):
        result = HD.hydrolysis("NH4Cl", 0.1)
        self.assertAlmostEqual(result.meta["ph"], 5.12, places=1)
        self.assertIn("кислая", result.value)

    def test_both_weak(self):
        result = HD.hydrolysis("CH3COONH4", 0.1)
        self.assertAlmostEqual(result.meta["ph"], 7.0, places=1)

    def test_ammonium_sulfate(self):
        self.assertEqual(HD.salt_type("(NH4)2SO4")["kind"], "cation")

    def test_unknown_constant_is_honest(self):
        """FeCl3: Kb нет, значит тип и среда есть, а pH — нет."""
        result = HD.hydrolysis("FeCl3", 0.1)
        self.assertIn("кислая", result.value)
        self.assertNotIn("ph", result.meta)
        self.assertTrue(result.warnings)

    def test_not_a_salt(self):
        with self.assertRaises(InputError):
            HD.hydrolysis("H2O")


if __name__ == "__main__":
    unittest.main()
