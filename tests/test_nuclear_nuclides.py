# -*- coding: utf-8 -*-
"""Тесты расчёта распада реальных нуклидов.

Проверяется интеграция с базой radioactivedecay: реальные периоды
полураспада, ветвления и дочерние цепочки.
"""

from __future__ import annotations

import unittest

from alchemy.core.errors import DataNotFoundError
from alchemy.engines import nuclear


class TestNormalization(unittest.TestCase):
    """Приведение обозначений нуклидов к единому виду."""

    def test_standard_form(self):
        self.assertEqual(nuclear._normalize_nuclide("U-238"), "U-238")

    def test_without_hyphen(self):
        self.assertEqual(nuclear._normalize_nuclide("U238"), "U-238")

    def test_mass_first(self):
        self.assertEqual(nuclear._normalize_nuclide("238U"), "U-238")

    def test_lowercase(self):
        self.assertEqual(nuclear._normalize_nuclide("u238"), "U-238")

    def test_metastable_state(self):
        self.assertEqual(nuclear._normalize_nuclide("Tc-99m"), "Tc-99m")

    def test_russian_name(self):
        self.assertEqual(nuclear._normalize_nuclide("уран-238"), "U-238")

    def test_russian_caesium(self):
        self.assertEqual(nuclear._normalize_nuclide("Цезий-137"), "Cs-137")

    def test_two_letter_symbol_case(self):
        self.assertEqual(nuclear._normalize_nuclide("cs137"), "Cs-137")

    def test_empty_rejected(self):
        with self.assertRaises(nuclear.NuclearError):
            nuclear._normalize_nuclide("   ")


class TestNuclideData(unittest.TestCase):
    """Справочные данные изотопов."""

    def test_cobalt_60(self):
        result = nuclear.nuclide_data("Co-60")
        # T½ = 5.271 года
        half_life_years = result.meta["half_life_s"] / 31557600.0
        self.assertAlmostEqual(half_life_years, 5.271, delta=0.01)
        self.assertIn("β-", result.meta["modes"])
        self.assertIn("Ni-60", result.meta["progeny"])

    def test_uranium_235(self):
        result = nuclear.nuclide_data("U-235")
        half_life_years = result.meta["half_life_s"] / 31557600.0
        self.assertAlmostEqual(half_life_years / 1e8, 7.04, delta=0.05)
        self.assertIn("α", result.meta["modes"])

    def test_uranium_238_half_life(self):
        result = nuclear.nuclide_data("U-238")
        half_life_years = result.meta["half_life_s"] / 31557600.0
        self.assertAlmostEqual(half_life_years / 1e9, 4.468, delta=0.01)

    def test_caesium_137(self):
        result = nuclear.nuclide_data("Cs-137")
        half_life_years = result.meta["half_life_s"] / 31557600.0
        self.assertAlmostEqual(half_life_years, 30.08, delta=0.5)

    def test_table_has_rows(self):
        result = nuclear.nuclide_data("Co-60")
        self.assertIsInstance(result.value, list)
        self.assertGreaterEqual(len(result.value), 1)
        self.assertIn("Канал распада", result.value[0])

    def test_unknown_nuclide_rejected(self):
        with self.assertRaises(DataNotFoundError):
            nuclear.nuclide_data("Xx-999")

    def test_source_mentioned(self):
        result = nuclear.nuclide_data("Co-60")
        self.assertTrue(any("radioactivedecay" in s for s in result.sources))


class TestDecayByNuclides(unittest.TestCase):
    """Распад с учётом дочерних цепочек."""

    def test_one_half_life_leaves_half(self):
        """За один период полураспада остаётся ровно половина."""
        result = nuclear.decay_by_nuclides({"Co-60": 1e20}, 5.271, "год")
        remaining = result.meta["numbers"]["Co-60"]
        self.assertAlmostEqual(remaining / 1e20, 0.5, places=3)

    def test_daughter_accumulates(self):
        """Дочерний нуклид накапливается в том же количестве."""
        result = nuclear.decay_by_nuclides({"Co-60": 1e20}, 5.271, "год")
        numbers = result.meta["numbers"]
        self.assertAlmostEqual(numbers["Ni-60"] / 1e20, 0.5, places=3)

    def test_two_half_lives_leave_quarter(self):
        result = nuclear.decay_by_nuclides({"Co-60": 1e20}, 10.542, "год")
        remaining = result.meta["numbers"]["Co-60"]
        self.assertAlmostEqual(remaining / 1e20, 0.25, places=3)

    def test_chain_produces_daughters(self):
        """У урана в цепочке появляются промежуточные нуклиды."""
        result = nuclear.decay_by_nuclides({"U-238": 1e20}, 4.468e9, "год")
        self.assertGreater(len(result.meta["numbers"]), 5)
        self.assertIn("Pb-206", result.meta["numbers"])

    def test_stable_endpoint_receives_all(self):
        """Стабильный свинец получает всё, что успело распасться."""
        result = nuclear.decay_by_nuclides({"U-238": 1e20}, 1e10, "год")
        numbers = result.meta["numbers"]
        remaining = numbers["U-238"] / 1e20
        self.assertAlmostEqual(numbers["Pb-206"] / 1e20, 1.0 - remaining,
                               places=4)

    def test_metastable_daughter(self):
        """У цезия дочерний барий образуется в метастабильном состоянии."""
        result = nuclear.decay_by_nuclides({"Cs-137": 1e15}, 30, "год")
        self.assertIn("Ba-137m", result.meta["numbers"])

    def test_activity_reported(self):
        result = nuclear.decay_by_nuclides({"Co-60": 1e20}, 1, "год")
        self.assertGreater(result.meta["activities"]["Co-60"], 0)

    def test_zero_time_changes_nothing(self):
        result = nuclear.decay_by_nuclides({"Co-60": 1e20}, 0, "год")
        self.assertAlmostEqual(result.meta["numbers"]["Co-60"] / 1e20, 1.0,
                               places=6)

    def test_negative_amount_rejected(self):
        with self.assertRaises(nuclear.NuclearError):
            nuclear.decay_by_nuclides({"Co-60": -1.0}, 1, "год")

    def test_empty_composition_rejected(self):
        with self.assertRaises(nuclear.NuclearError):
            nuclear.decay_by_nuclides({}, 1, "год")

    def test_bad_time_unit_rejected(self):
        with self.assertRaises(nuclear.NuclearError):
            nuclear.decay_by_nuclides({"Co-60": 1.0}, 1, "парсек")

    def test_negative_time_rejected(self):
        with self.assertRaises(nuclear.NuclearError):
            nuclear.decay_by_nuclides({"Co-60": 1.0}, -1, "год")

    def test_initial_activity_units(self):
        """Начальное количество можно задать в беккерелях."""
        result = nuclear.decay_by_nuclides({"Co-60": 1e10}, 5.271, "год", "Бк")
        self.assertAlmostEqual(
            result.meta["activities"]["Co-60"] / 1e10, 0.5, places=3)


class TestNaturalSeries(unittest.TestCase):
    """Природные радиоактивные ряды."""

    def test_all_series(self):
        result = nuclear.natural_series()
        self.assertEqual(len(result.value), 3)

    def test_uranium_series(self):
        result = nuclear.natural_series("ряд урана (U-238)")
        self.assertEqual(len(result.value), 1)
        self.assertEqual(result.value[0]["Материнский нуклид"], "U-238")

    def test_unknown_series_rejected(self):
        with self.assertRaises(nuclear.NuclearError):
            nuclear.natural_series("ряд плутония")


class TestConsistencyWithNumerical(unittest.TestCase):
    """Сверка библиотечного расчёта с собственными формулами."""

    def _half_life_years(self, nuclide: str) -> float:
        """Точный период полураспада из базы, в годах."""
        return nuclear.nuclide_data(nuclide).meta["half_life_s"] / 31557600.0

    def test_single_stage_matches_analytical(self):
        """Один нуклид: распад совпадает с формулой N = N₀·2^(−t/T½).

        Библиотека переводит годы в секунды своим коэффициентом, поэтому
        полного совпадения с ручным пересчётом нет — расхождение порядка
        миллионных долей. Для физики это несущественно.
        """
        half_life = self._half_life_years("Co-60")
        years = 12.0
        result = nuclear.decay_by_nuclides({"Co-60": 1.0}, years, "год")
        expected = 2 ** (-years / half_life)
        self.assertAlmostEqual(result.meta["numbers"]["Co-60"], expected,
                               places=4)

    def test_matches_decayed_amount_function(self):
        """Совпадение с собственной функцией распада для одного звена."""
        half_life_years = self._half_life_years("Co-60")
        half_life_days = half_life_years * 365.25
        years = 3.0
        library = nuclear.decay_by_nuclides({"Co-60": 1.0}, years, "год")
        own = nuclear.decayed_amount(1.0, half_life_days, years * 365.25, "сут")
        self.assertAlmostEqual(library.meta["numbers"]["Co-60"],
                               own.numeric(), places=4)


if __name__ == "__main__":
    unittest.main()
