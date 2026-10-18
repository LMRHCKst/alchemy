# -*- coding: utf-8 -*-
"""Тесты режима Cantera.

Cantera — необязательная зависимость, поэтому все тесты пропускаются,
если библиотеки нет: программа должна работать и без неё.
"""

from __future__ import annotations

import unittest

from alchemy.core.errors import DataNotFoundError, InputError
from alchemy.engines import cantera_engine as CE


HAS_CANTERA = CE.available()


class TestAvailability(unittest.TestCase):
    """Проверка установки."""

    def test_available_returns_bool(self):
        self.assertIsInstance(CE.available(), bool)

    @unittest.skipUnless(HAS_CANTERA, "Cantera не установлена")
    def test_version_present(self):
        self.assertTrue(CE.version())

    @unittest.skipUnless(HAS_CANTERA, "Cantera не установлена")
    def test_mechanisms_listed(self):
        rows = CE.list_mechanisms()
        self.assertGreater(len(rows), 3)
        names = [row["Механизм"] for row in rows]
        self.assertIn("gri30.yaml", names)


@unittest.skipUnless(HAS_CANTERA, "Cantera не установлена")
class TestGasProperties(unittest.TestCase):
    """Свойства газовой смеси."""

    def setUp(self):
        self.result = CE.gas_properties(
            "gri30.yaml", 1000.0, 101325.0, "H2O:1, N2:3.76")

    def test_returns_table(self):
        self.assertEqual(self.result.kind, "table")
        self.assertGreater(len(self.result.value), 8)

    def test_has_density(self):
        row = next(r for r in self.result.value if r["Величина"] == "Плотность")
        self.assertAlmostEqual(float(row["Значение"]), 0.3158, places=3)

    def test_has_heat_capacity(self):
        row = next(r for r in self.result.value
                   if r["Величина"].startswith("Теплоёмкость cp"))
        value = float(row["Значение"])
        self.assertGreater(value, 1000)
        self.assertLess(value, 2000)

    def test_method_mentions_cantera(self):
        self.assertIn("Cantera", self.result.method)

    def test_molar_heat_capacity_in_meta(self):
        self.assertIn("cp_molar", self.result.meta)
        self.assertGreater(self.result.meta["cp_molar"], 20)

    def test_ideal_gas_density_consistency(self):
        """Плотность должна согласоваться с уравнением идеального газа."""
        gas_result = CE.gas_properties(
            "gri30.yaml", 500.0, 101325.0, "N2:1")
        row = next(r for r in gas_result.value if r["Величина"] == "Плотность")
        density = float(row["Значение"])
        molar_mass = gas_result.meta["mean_molar_mass"]
        expected = 101325.0 * molar_mass / (8.314462618 * 500.0)
        self.assertAlmostEqual(density, expected, delta=expected * 0.01)


@unittest.skipUnless(HAS_CANTERA, "Cantera не установлена")
class TestEquilibrium(unittest.TestCase):
    """Равновесие газовой смеси."""

    def test_methane_oxidation(self):
        result = CE.equilibrium(
            "gri30.yaml", 1500.0, 101325.0, "CH4:1, O2:2, N2:7.52")
        shares = {row["Вещество"]: float(row["Мольная доля, %"])
                  for row in result.value}
        # При 1500 К метан выгорает почти полностью
        self.assertGreater(shares["H2O"], 15)
        self.assertGreater(shares["CO2"], 8)
        self.assertGreater(shares["N2"], 65)
        # Ниже порога 1e-6 метан в таблицу не попадает — это и есть выгорание
        self.assertLess(shares.get("CH4", 0.0), 0.1)

    def test_shares_sum_to_hundred(self):
        result = CE.equilibrium(
            "gri30.yaml", 1200.0, 101325.0, "CH4:1, O2:2, N2:7.52")
        total = sum(float(row["Мольная доля, %"]) for row in result.value)
        self.assertAlmostEqual(total, 100.0, delta=0.5)

    def test_adiabatic_mode_changes_temperature(self):
        result = CE.equilibrium(
            "gri30.yaml", 300.0, 101325.0, "CH4:1, O2:2, N2:7.52", mode="HP")
        self.assertGreater(result.meta["equilibrium_temperature"], 1500)

    def test_isothermal_mode_keeps_temperature(self):
        result = CE.equilibrium(
            "gri30.yaml", 1500.0, 101325.0, "CH4:1, O2:2, N2:7.52", mode="TP")
        self.assertAlmostEqual(result.meta["equilibrium_temperature"], 1500.0,
                               delta=1.0)


@unittest.skipUnless(HAS_CANTERA, "Cantera не установлена")
class TestAdiabaticTemperature(unittest.TestCase):
    """Адиабатическая температура горения."""

    def test_methane_in_air(self):
        """Метан в воздухе — около 2220 К."""
        result = CE.adiabatic_temperature(
            "gri30.yaml", 300.0, 101325.0, "CH4:1, O2:2, N2:7.52")
        self.assertAlmostEqual(result.numeric(), 2220, delta=40)

    def test_hydrogen_in_air(self):
        """Водород в воздухе — около 2380 К."""
        result = CE.adiabatic_temperature(
            "gri30.yaml", 300.0, 101325.0, "H2:2, O2:1, N2:3.76")
        self.assertAlmostEqual(result.numeric(), 2380, delta=60)

    def test_hydrogen_hotter_than_methane(self):
        methane = CE.adiabatic_temperature(
            "gri30.yaml", 300.0, 101325.0, "CH4:1, O2:2, N2:7.52").numeric()
        hydrogen = CE.adiabatic_temperature(
            "gri30.yaml", 300.0, 101325.0, "H2:2, O2:1, N2:3.76").numeric()
        self.assertGreater(hydrogen, methane)

    def test_non_flammable_mix_warns(self):
        result = CE.adiabatic_temperature(
            "gri30.yaml", 300.0, 101325.0, "N2:1")
        self.assertLess(result.numeric() - 300.0, 5)


@unittest.skipUnless(HAS_CANTERA, "Cantera не установлена")
class TestReactor(unittest.TestCase):
    """Кинетика в реакторе."""

    def test_temperature_rises(self):
        result = CE.reactor_kinetics(
            "gri30.yaml", 1500.0, 101325.0, "CH4:1, O2:2, N2:7.52",
            0.01, points=20)
        points = result.value
        self.assertGreater(points[-1][1], points[0][1])

    def test_series_has_requested_points(self):
        result = CE.reactor_kinetics(
            "gri30.yaml", 1500.0, 101325.0, "CH4:1, O2:2, N2:7.52",
            0.005, points=15)
        self.assertEqual(len(result.value), 16)

    def test_time_monotonic(self):
        result = CE.reactor_kinetics(
            "gri30.yaml", 1500.0, 101325.0, "CH4:1, O2:2, N2:7.52",
            0.002, points=10)
        times = [p[0] for p in result.value]
        self.assertEqual(times, sorted(times))

    def test_reports_consumed_species(self):
        result = CE.reactor_kinetics(
            "gri30.yaml", 1500.0, 101325.0, "CH4:1, O2:2, N2:7.52",
            0.01, points=20)
        self.assertIn(result.meta["main_species"], ("CH4", "O2"))
        self.assertLess(result.meta["main_share_final"],
                        result.meta["main_share_initial"])


@unittest.skipUnless(HAS_CANTERA, "Cantera не установлена")
class TestValidation(unittest.TestCase):
    """Проверка входных данных."""

    def test_empty_composition(self):
        with self.assertRaises(InputError):
            CE.gas_properties("gri30.yaml", 300.0, 101325.0, "")

    def test_unknown_mechanism(self):
        with self.assertRaises(DataNotFoundError):
            CE.equilibrium("nope.yaml", 300.0, 101325.0, "N2:1")

    def test_unknown_species(self):
        with self.assertRaises(InputError):
            CE.equilibrium("gri30.yaml", 300.0, 101325.0, "XX:1")

    def test_negative_temperature(self):
        with self.assertRaises(InputError):
            CE.gas_properties("gri30.yaml", -5.0, 101325.0, "N2:1")

    def test_negative_pressure(self):
        with self.assertRaises(InputError):
            CE.gas_properties("gri30.yaml", 300.0, -1.0, "N2:1")

    def test_negative_time(self):
        with self.assertRaises(InputError):
            CE.reactor_kinetics(
                "gri30.yaml", 1500.0, 101325.0, "CH4:1, O2:2", -1.0)


@unittest.skipUnless(HAS_CANTERA, "Cantera не установлена")
class TestMechanismInfo(unittest.TestCase):
    """Сведения о механизме."""

    def test_gri30_has_species(self):
        result = CE.mechanism_info("gri30.yaml")
        self.assertGreater(len(result.value), 40)

    def test_unknown_mechanism(self):
        with self.assertRaises(DataNotFoundError):
            CE.mechanism_info("nope.yaml")


if __name__ == "__main__":
    unittest.main()
