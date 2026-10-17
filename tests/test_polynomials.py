# -*- coding: utf-8 -*-
"""Тесты термохимических полиномов NASA.

Проверяется, что снимок базы Burcat читается, поиск по составу работает
и полиномы воспроизводят известные значения.
"""

from __future__ import annotations

import unittest

from alchemy.core.errors import DataNotFoundError, OutOfRangeError
from alchemy.data import polynomials as POLY


class TestDatabase(unittest.TestCase):
    """Состав снимка."""

    def test_database_loaded(self):
        self.assertGreater(POLY.count(), 500)

    def test_coverage_reported(self):
        summary = POLY.coverage()
        self.assertGreater(summary["всего"], 0)
        self.assertGreater(summary["газ"], 0)
        self.assertGreater(summary["с энтальпией образования"], 0)

    def test_source_present(self):
        self.assertIn("Burcat", POLY.source())


class TestLookup(unittest.TestCase):
    """Поиск по формуле и состоянию."""

    def test_water_gas(self):
        found = POLY.find("H2O", "g")
        self.assertIsNotNone(found)
        self.assertEqual(found.state, "g")

    def test_state_embedded_in_formula(self):
        """Состояние можно указать прямо в строке: «H2O(ж)»."""
        found = POLY.find("H2O(ж)")
        self.assertIsNotNone(found)
        self.assertEqual(found.state, "l")

    def test_default_prefers_gas(self):
        found = POLY.find("H2O")
        self.assertIsNotNone(found)
        self.assertEqual(found.state, "g")

    def test_unknown_substance(self):
        self.assertIsNone(POLY.find("Xx9Yy8"))

    def test_require_raises(self):
        with self.assertRaises(DataNotFoundError):
            POLY.require("Xx9Yy8")

    def test_states_of(self):
        states = POLY.states_of("H2O")
        self.assertIn("g", states)
        self.assertIn("l", states)

    def test_reference_species(self):
        for formula in ("H2", "O2", "N2", "CO2", "CH4"):
            self.assertIsNotNone(POLY.find(formula, "g"), formula)


class TestPolynomialValues(unittest.TestCase):
    """Числа, которые дают полиномы."""

    def test_enthalpy_at_298_equals_formation_enthalpy(self):
        """H(298.15) обязана совпадать с энтальпией образования."""
        cases = [
            ("H2O", "g", -241.826),
            ("CO2", "g", -393.51),
        ]
        for formula, state, expected in cases:
            poly = POLY.require(formula, state)
            self.assertAlmostEqual(poly.enthalpy(298.15), expected, places=1)

    def test_formation_enthalpy_matches_stored(self):
        poly = POLY.require("H2O", "g")
        self.assertIsNotNone(poly.d_hf)
        self.assertAlmostEqual(poly.enthalpy(298.15), poly.d_hf, places=1)

    def test_cp_at_standard_water(self):
        """Cp воды при 298 К ≈ 33.6 Дж/(моль·К)."""
        poly = POLY.require("H2O", "g")
        self.assertAlmostEqual(poly.cp(298.15), 33.6, delta=0.3)

    def test_cp_at_standard_carbon_dioxide(self):
        poly = POLY.require("CO2", "g")
        self.assertAlmostEqual(poly.cp(298.15), 37.1, delta=0.3)

    def test_cp_grows_with_temperature(self):
        """Теплоёмкость газа растёт с температурой — это и есть Cp(T)."""
        poly = POLY.require("H2O", "g")
        self.assertGreater(poly.cp(1000.0), poly.cp(298.15))
        self.assertGreater(poly.cp(2000.0), poly.cp(1000.0))

    def test_entropy_increases(self):
        poly = POLY.require("H2O", "g")
        self.assertGreater(poly.entropy(1000.0), poly.entropy(298.15))

    def test_entropy_at_standard_water(self):
        poly = POLY.require("H2O", "g")
        self.assertAlmostEqual(poly.entropy(298.15), 188.8, delta=0.5)

    def test_gibbs_decreases_with_temperature(self):
        poly = POLY.require("H2O", "g")
        self.assertLess(poly.gibbs(1500.0), poly.gibbs(298.15))

    def test_sensible_enthalpy_at_reference_is_zero(self):
        poly = POLY.require("CO2", "g")
        self.assertAlmostEqual(poly.sensible_enthalpy(298.15), 0.0, places=6)

    def test_sensible_enthalpy_grows(self):
        poly = POLY.require("CO2", "g")
        self.assertGreater(poly.sensible_enthalpy(1000.0), 0.0)

    def test_two_ranges_join_smoothly(self):
        """На границе 1000 К обе ветви полинома должны давать близкие значения."""
        poly = POLY.require("H2O", "g")
        below = poly.cp(999.9)
        above = poly.cp(1000.1)
        self.assertAlmostEqual(below, above, delta=1.0)


class TestRangeCheck(unittest.TestCase):
    """Область применимости."""

    def test_out_of_range_raises(self):
        poly = POLY.require("H2O", "g")
        with self.assertRaises(OutOfRangeError):
            poly.cp(50.0)

    def test_check_range_reports_limits(self):
        poly = POLY.require("H2O", "g")
        with self.assertRaises(OutOfRangeError) as context:
            poly.check_range(9000.0)
        message = str(context.exception)
        self.assertIn("6000", message)


class TestCompositionKey(unittest.TestCase):
    """Ключ по составу."""

    def test_simple(self):
        self.assertEqual(POLY.composition_key({"H": 2, "O": 1}), "H2O1")

    def test_alphabetical_order(self):
        self.assertEqual(POLY.composition_key({"O": 1, "C": 1}), "C1O1")

    def test_fractional_rejected(self):
        self.assertEqual(POLY.composition_key({"H": 1.5}), "")


class TestReactionUse(unittest.TestCase):
    """Полиномы дают правильный тепловой эффект."""

    def test_water_formation_at_298(self):
        """Теплота образования воды из элементов."""
        h2 = POLY.require("H2", "g")
        o2 = POLY.require("O2", "g")
        water = POLY.require("H2O", "g")
        reaction = 2 * water.enthalpy(298.15) - 2 * h2.enthalpy(298.15) \
            - o2.enthalpy(298.15)
        # На 2 моль воды; эталон −483.6 кДж
        self.assertAlmostEqual(reaction, -483.6, delta=1.0)

    def test_water_formation_at_1000(self):
        """При 1000 К энтальпия образования воды по JANAF ≈ −247.9 кДж/моль."""
        h2 = POLY.require("H2", "g")
        o2 = POLY.require("O2", "g")
        water = POLY.require("H2O", "g")
        per_mole = (water.enthalpy(1000.0)
                    - h2.enthalpy(1000.0)
                    - 0.5 * o2.enthalpy(1000.0))
        self.assertAlmostEqual(per_mole, -247.9, delta=1.0)

    def test_methane_combustion_at_298(self):
        """Теплота сгорания метана −802 кДж/моль при 298 К."""
        ch4 = POLY.require("CH4", "g")
        o2 = POLY.require("O2", "g")
        co2 = POLY.require("CO2", "g")
        water = POLY.require("H2O", "g")
        reaction = (co2.enthalpy(298.15) + 2 * water.enthalpy(298.15)
                    - ch4.enthalpy(298.15) - 2 * o2.enthalpy(298.15))
        self.assertAlmostEqual(reaction, -802.0, delta=2.0)


if __name__ == "__main__":
    unittest.main()
