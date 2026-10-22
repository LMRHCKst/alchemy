# -*- coding: utf-8 -*-
"""Табличные сведения школьного курса: плотности, электролиз, разложение."""

import unittest

from alchemy.core.errors import InputError
from alchemy.engines import gases as G
from alchemy.engines import oxidation as O
from alchemy.engines import tables as T


class TestDensity(unittest.TestCase):
    def test_table_points(self):
        """Точки из таблицы NBS должны воспроизводиться точно."""
        self.assertAlmostEqual(T.solution_density("H2SO4", 0).numeric(),
                               0.99823, places=5)
        self.assertAlmostEqual(T.solution_density("H2SO4", 20).numeric(),
                               1.13943, places=5)
        self.assertAlmostEqual(T.solution_density("H2SO4", 90).numeric(),
                               1.81438, places=5)

    def test_interpolation(self):
        """Между целыми процентами — линейно, ошибка меньше 0.001."""
        value = T.solution_density("H2SO4", 20.5).numeric()
        self.assertGreater(value, 1.13943)
        self.assertLess(value, 1.17830)

    def test_concentrated(self):
        """98 % — плотность 1.8365, молярность около 18.4."""
        self.assertAlmostEqual(T.solution_density("H2SO4", 98).numeric(),
                               1.8365, places=4)
        molarity = T.concentration_from_density("H2SO4", 98).numeric()
        self.assertAlmostEqual(molarity, 18.35, delta=0.2)

    def test_other_substance_refused(self):
        with self.assertRaises(InputError):
            T.solution_density("NaOH", 10)


class TestElectrolysis(unittest.TestCase):
    def test_solution_vs_melt(self):
        melt = T.electrolysis("NaCl", "расплав").value
        solution = T.electrolysis("NaCl", "раствор").value
        self.assertIn("Na", melt)
        self.assertIn("H₂", solution)

    def test_copper_sulfate(self):
        result = T.electrolysis("CuSO4")
        self.assertIn("Cu", result.value)

    def test_unknown(self):
        with self.assertRaises(InputError):
            T.electrolysis("Unobtainium")


class TestDecomposition(unittest.TestCase):
    def test_calcium_carbonate(self):
        rows = T.decomposition("CaCO3").value
        self.assertTrue(any("CaO" in row["Продукты"] for row in rows))

    def test_sodium_nitrate(self):
        rows = T.decomposition("NaNO3").value
        self.assertTrue(any("NaNO₂" in row["Продукты"] for row in rows))

    def test_stable_carbonate(self):
        rows = T.decomposition("Na2CO3").value
        self.assertTrue(any("не разлагается" in row["Продукты"]
                            for row in rows))


class TestQualitative(unittest.TestCase):
    def test_silver(self):
        rows = T.qualitative_reaction("Ag").value
        self.assertGreaterEqual(len(rows), 3)

    def test_ferric_vs_ferrous(self):
        """Fe3+ и Fe2+ не должны путаться."""
        ferric = T.qualitative_reaction("Fe3+", "OH").value
        ferrous = T.qualitative_reaction("Fe2+", "OH").value
        self.assertIn("Fe(OH)₃", " ".join(row["Осадок"] for row in ferric))
        self.assertIn("Fe(OH)₂", " ".join(row["Осадок"] for row in ferrous))

    def test_flame(self):
        self.assertEqual(T.flame_color("Na").value, "жёлтый")
        self.assertEqual(T.flame_color("K").value, "фиолетовый")


class TestAmphoteric(unittest.TestCase):
    def test_zinc(self):
        self.assertEqual(T.amphoteric("Zn(OH)2").value, "[Zn(OH)₄]²⁻")

    def test_aluminium(self):
        self.assertEqual(T.amphoteric("Al(OH)3").value, "[Al(OH)₄]⁻")


class TestComplexAndPolymer(unittest.TestCase):
    def test_complex(self):
        result = T.complex_info("[Cu(NH3)4]SO4")
        self.assertIn("тетраамминмеди", result.value)

    def test_polymer(self):
        self.assertEqual(T.polymer_info("Полиэтилен").value, "CH₂=CH₂")


class TestVanDerWaals(unittest.TestCase):
    def test_water(self):
        self.assertAlmostEqual(T.vdw_constants("вода").numeric(), 5.536,
                               places=3)

    def test_gases_fallback(self):
        """Газы, которых не было в старой таблице, теперь доступны."""
        a, b = G.van_der_waals_constants("Benzene")
        self.assertAlmostEqual(a, 18.24, places=2)

    def test_old_values_kept(self):
        a, b = G.van_der_waals_constants("CO2")
        self.assertAlmostEqual(a, 3.64, places=2)


class TestSolvents(unittest.TestCase):
    def test_benzene(self):
        result = T.solvent_constants("бензол")
        self.assertAlmostEqual(result.numeric(), 5.12, places=2)
        self.assertAlmostEqual(result.meta["kb"], 2.65, places=2)


class TestOxidationExceptions(unittest.TestCase):
    def test_hydrides(self):
        for formula, expected in (("NaH", "-1"), ("CaH2", "-1"),
                                  ("LiAlH4", "-1")):
            rows = O.oxidation_states(formula).value
            hydrogen = [r for r in rows if r["Элемент"].startswith("H")]
            self.assertEqual(hydrogen[0]["Степень окисления"], expected,
                             formula)

    def test_pyrite(self):
        rows = O.oxidation_states("FeS2").value
        states = {r["Элемент"].split()[0]: r["Степень окисления"]
                  for r in rows}
        self.assertEqual(states["Fe"], "+2")
        self.assertEqual(states["S"], "-1")

    def test_peroxide_and_superoxide(self):
        states = {r["Элемент"].split()[0]: r["Степень окисления"]
                  for r in O.oxidation_states("Na2O2").value}
        self.assertEqual(states["O"], "-1")
        states = {r["Элемент"].split()[0]: r["Степень окисления"]
                  for r in O.oxidation_states("KO2").value}
        self.assertEqual(states["O"], "-0.5")


if __name__ == "__main__":
    unittest.main()
