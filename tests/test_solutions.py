# -*- coding: utf-8 -*-
"""Тесты движка растворов: концентрации, разбавление, коллигативные свойства."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alchemy.engines import solutions as S
from alchemy.engines.solutions import SolutionError


class TestConcentrationConversions(unittest.TestCase):
    """Пересчёты между способами выражения концентрации."""

    def test_mass_fraction_basic(self):
        """18 г NaCl в 180 г раствора дают 10 %."""
        sol = S.from_mass_fraction("NaCl", 10.0, solution_mass=180.0)
        self.assertAlmostEqual(sol.mass_percent, 10.0, places=9)
        self.assertAlmostEqual(sol.solute_mass, 18.0, places=9)
        self.assertAlmostEqual(sol.solvent_mass, 162.0, places=9)

    def test_molality_from_mass_fraction(self):
        """10 % NaCl: в 100 г раствора 10 г соли и 90 г воды.

        b = (10/M(NaCl))/0.090. Значение молярной массы берётся из справочника
        элементов, поэтому сверяем с той же точностью, что даёт расчёт.
        """
        from alchemy.core.formula import molar_mass
        M = molar_mass("NaCl")
        sol = S.from_mass_fraction("NaCl", 10.0, solution_mass=100.0)
        expected = (10.0 / M) / 0.090
        self.assertAlmostEqual(sol.molality, expected, places=9)

    def test_mole_fraction(self):
        """Мольная доля в 10 % растворе NaCl."""
        from alchemy.core.formula import molar_mass
        M = molar_mass("NaCl")
        sol = S.from_mass_fraction("NaCl", 10.0, solution_mass=100.0)
        n1 = 10.0 / M
        n0 = 90.0 / 18.015
        self.assertAlmostEqual(sol.mole_fraction, n1 / (n1 + n0), places=12)

    def test_molarity_requires_volume_or_density(self):
        """Без плотности и объёма молярность посчитать нельзя."""
        sol = S.from_mass_fraction("NaCl", 10.0, solution_mass=100.0)
        # Плотность для NaCl есть в справочнике, поэтому объём определён
        self.assertIsNotNone(sol.volume_l)
        self.assertGreater(sol.molarity, 0)

    def test_molality_to_molarity_exact(self):
        """Строгий пересчёт моляльности в молярность.

        Для 1 моль/кг NaCl при плотности 1.04 г/мл:
        C = 1·1.04/(1 + 1·58.443/1000) = 0.9826 моль/л.
        Прежняя версия давала 1.04 — ошибка около 6 %.
        """
        sol = S.from_molality("NaCl", 1.0, solvent_mass=1000.0, density=1.04)
        self.assertAlmostEqual(sol.molality_to_molarity(), 0.98259, places=4)
        self.assertAlmostEqual(sol.molarity, 0.98259, places=4)

    def test_molarity_from_molarity_roundtrip(self):
        """Молярность -> моляльность -> молярность должно сходиться."""
        sol = S.from_molarity("NaCl", 0.5, 1.0, density=1.0192)
        b = sol.molality
        back = S.from_molality("NaCl", b, sol.solvent_mass, density=1.0192)
        self.assertAlmostEqual(back.molarity, 0.5, places=6)

    def test_ppm_and_ppb(self):
        sol = S.from_mass_fraction("NaCl", 0.0001, solution_mass=1000.0)
        self.assertAlmostEqual(sol.ppm, 1.0, places=6)
        self.assertAlmostEqual(sol.ppb, 1000.0, places=3)

    def test_mass_concentration(self):
        sol = S.from_mass_concentration("NaCl", 58.443, volume_l=1.0, density=1.0)
        self.assertAlmostEqual(sol.mass_concentration, 58.443, places=6)
        # При плотности 1.0 г/мл 1 л весит 1000 г, значит около 1 моль/л
        self.assertAlmostEqual(sol.molarity, 1.0, places=3)

    def test_mass_concentration_unknown_density(self):
        """Без справочной плотности плотность не выдумывается."""
        sol = S.from_mass_concentration("KCl", 50.0, volume_l=1.0)
        self.assertIsNone(sol.density)
        # Объём задан явно, поэтому молярность посчитать можно
        self.assertAlmostEqual(sol.molarity, 50.0 / 74.551, places=4)
        res = S.describe(sol)
        self.assertTrue(res.has_warnings)

    def test_invalid_mass_fraction(self):
        for bad in (0.0, 100.0, -5.0, 150.0):
            with self.subTest(value=bad):
                with self.assertRaises(SolutionError):
                    S.from_mass_fraction("NaCl", bad, solution_mass=100.0)

    def test_negative_and_zero_masses_rejected(self):
        """Отрицательная масса вещества и нулевая масса растворителя недопустимы."""
        with self.assertRaises(SolutionError):
            S.Solution(solute_mass=-10.0, solvent_mass=100.0, solute_molar_mass=58.44)
        with self.assertRaises(SolutionError):
            S.Solution(solute_mass=10.0, solvent_mass=0.0, solute_molar_mass=58.44)
        with self.assertRaises(SolutionError):
            S.Solution(solute_mass=10.0, solvent_mass=100.0, solute_molar_mass=0.0)

    def test_concentrated_solution_allowed(self):
        """Раствор, где вещества больше, чем растворителя, физически возможен."""
        sol = S.Solution(solute_mass=300.0, solvent_mass=100.0, solute_molar_mass=58.44)
        self.assertAlmostEqual(sol.mass_percent, 75.0, places=9)
    def test_negative_values_rejected(self):
        with self.assertRaises(SolutionError):
            S.from_molarity("NaCl", -1.0, 1.0)
        with self.assertRaises(SolutionError):
            S.from_molarity("NaCl", 1.0, -1.0)

    def test_impossible_concentration_rejected(self):
        """5 моль/л NaCl при плотности 1.0 г/мл невозможно: 292 г на литр."""
        with self.assertRaises(SolutionError):
            S.from_molarity("NaCl", 6.0, 1.0, density=1.0)

    def test_hydrate_concentration(self):
        """CuSO4*5H2O: молярная масса 249.68, а не 159.61."""
        sol = S.from_mass_fraction("CuSO4*5H2O", 10.0, solution_mass=100.0)
        self.assertAlmostEqual(sol.solute_molar_mass, 249.68, places=1)

    def test_density_taken_from_reference(self):
        """Для NaOH справочник должен дать плотность, а не подставить 1.0."""
        sol = S.from_mass_fraction("NaOH", 20.0, solution_mass=1000.0)
        self.assertIsNotNone(sol.density)
        self.assertAlmostEqual(sol.density, 1.2220, places=3)
        self.assertIn("справочник", sol.density_source)

    def test_density_unknown_warns(self):
        """Для вещества без таблицы плотности объёмные величины не выдумываются."""
        sol = S.from_mass_fraction("KCl", 10.0, solution_mass=1000.0)
        self.assertIsNone(sol.density)
        self.assertIsNone(sol.volume_l)
        res = S.describe(sol)
        self.assertTrue(res.has_warnings)
        # Объём неизвестен, значит молярность посчитать нельзя
        self.assertNotIn("молярность, моль/л", res.value)
    def test_describe_report(self):
        sol = S.from_mass_fraction("NaOH", 20.0, solution_mass=1000.0)
        res = S.describe(sol)
        self.assertIn("массовая доля, %", res.value)
        self.assertIn("моляльность, моль/кг", res.value)
        self.assertTrue(res.steps)


class TestRecipe(unittest.TestCase):
    """Приготовление растворов."""

    def test_simple_recipe(self):
        """0.5 л 0.1 М NaCl требует 2.922 г."""
        r = S.recipe("NaCl", 0.1, 500.0)
        self.assertAlmostEqual(r.numeric(), 2.9222, places=3)

    def test_recipe_volume_and_moles(self):
        r = S.recipe("NaOH", 1.0, 1000.0)
        self.assertAlmostEqual(r.numeric(), 39.997, places=2)
        self.assertAlmostEqual(r.meta["moles"], 1.0, places=9)

    def test_recipe_with_impurity(self):
        """Технический реактив 95 % требует больше навески."""
        pure = S.recipe("NaCl", 0.1, 500.0).numeric()
        impure = S.recipe("NaCl", 0.1, 500.0, purity=95.0).numeric()
        self.assertAlmostEqual(impure, pure / 0.95, places=6)

    def test_recipe_hydrate(self):
        """Чтобы получить безводный CuSO4, берут кристаллогидрат."""
        r = S.recipe("CuSO4", 0.1, 100.0, hydrate_water=5)
        self.assertAlmostEqual(r.meta["molar_mass"], 249.68, places=1)

    def test_recipe_by_volume(self):
        """Если задана плотность, считается объём для отмеривания."""
        r = S.recipe("H2SO4", 1.0, 1000.0, density=1.84)
        self.assertIn("volume_to_measure_ml", r.meta)
        self.assertGreater(r.meta["volume_to_measure_ml"], 0)

    def test_recipe_invalid(self):
        with self.assertRaises(SolutionError):
            S.recipe("NaCl", 0.0, 100.0)
        with self.assertRaises(SolutionError):
            S.recipe("NaCl", 1.0, 0.0)
        with self.assertRaises(SolutionError):
            S.recipe("NaCl", 1.0, 100.0, purity=0.0)

    def test_recipe_warns_low_purity(self):
        r = S.recipe("NaCl", 1.0, 100.0, purity=90.0)
        self.assertTrue(r.has_warnings)


class TestDilution(unittest.TestCase):
    """Разбавление и смешивание."""

    def test_find_volume_to_take(self):
        """Из 1 М нужно 100 мл 0.1 М: отобрать 10 мл."""
        r = S.dilution(c_initial=1.0, c_final=0.1, v_final=0.1)
        self.assertAlmostEqual(r.numeric(), 0.01, places=9)
        self.assertAlmostEqual(r.meta["volume_to_take_ml"], 10.0, places=6)
        self.assertAlmostEqual(r.meta["solvent_to_add_ml"], 90.0, places=6)

    def test_find_final_concentration(self):
        r = S.dilution(c_initial=2.0, v_initial=0.025, v_final=0.1)
        self.assertAlmostEqual(r.numeric(), 0.5, places=6)

    def test_find_initial_concentration(self):
        r = S.dilution(v_initial=0.05, c_final=0.2, v_final=0.25)
        self.assertAlmostEqual(r.numeric(), 1.0, places=6)

    def test_find_final_volume(self):
        r = S.dilution(c_initial=1.0, v_initial=0.01, c_final=0.05)
        self.assertAlmostEqual(r.numeric(), 0.2, places=6)

    def test_requires_exactly_one_unknown(self):
        with self.assertRaises(SolutionError):
            S.dilution(c_initial=1.0, v_initial=0.1)
        with self.assertRaises(SolutionError):
            S.dilution(1.0, 0.1, 0.5, 0.2)

    def test_warns_insufficient_stock(self):
        """Требуется 10 мл, а в наличии только 5 мл — должно быть предупреждение."""
        r = S.dilution(c_initial=1.0, c_final=0.01, v_final=1.0, stock_volume_l=0.005)
        self.assertTrue(r.has_warnings)

    def test_assumption_stated(self):
        r = S.dilution(c_initial=1.0, c_final=0.1, v_final=0.1)
        self.assertTrue(r.assumptions)

    # ---------------- серийное разбавление ----------------

    def test_serial_dilution_factor(self):
        """Из 1 мл в 10 мл: за 3 шага концентрация падает в 1000 раз."""
        r = S.serial_dilution(1.0, transfer_volume_ml=1.0, flask_volume_ml=10.0,
                              n_steps=3)
        final = r.value[-1]["Концентрация, моль/л"]
        self.assertAlmostEqual(final, 1e-3, places=12)

    def test_serial_dilution_first_step(self):
        r = S.serial_dilution(1.0, 2.0, 10.0, 1)
        self.assertAlmostEqual(r.value[1]["Концентрация, моль/л"], 0.2, places=12)

    def test_serial_dilution_invalid(self):
        with self.assertRaises(SolutionError):
            S.serial_dilution(1.0, 20.0, 10.0, 1)     # перенос больше колбы
        with self.assertRaises(SolutionError):
            S.serial_dilution(1.0, 1.0, 10.0, 0)      # нет шагов
        with self.assertRaises(SolutionError):
            S.serial_dilution(1.0, 1.0, 10.0, 2.5)    # дробное число шагов

    # ---------------- смешивание ----------------

    def test_mixing_equal_volumes(self):
        r = S.mixing([
            {"concentration": 1.0, "volume_l": 0.1},
            {"concentration": 0.5, "volume_l": 0.1},
        ])
        self.assertAlmostEqual(r.numeric(), 0.75, places=9)

    def test_mixing_weighted(self):
        r = S.mixing([
            {"concentration": 2.0, "volume_l": 0.3},
            {"concentration": 0.0, "volume_l": 0.1},
        ])
        self.assertAlmostEqual(r.numeric(), 1.5, places=9)

    def test_mixing_by_mass(self):
        r = S.mixing([
            {"mass_percent": 10.0, "mass_g": 100.0},
            {"mass_percent": 20.0, "mass_g": 300.0},
        ])
        self.assertAlmostEqual(r.numeric(), 17.5, places=6)

    def test_mixing_invalid(self):
        with self.assertRaises(SolutionError):
            S.mixing([])
        with self.assertRaises(SolutionError):
            S.mixing([{"concentration": 1.0, "volume_l": 0.1}])
        with self.assertRaises(SolutionError):
            S.mixing([{"что-то": 1}])

    def test_mixing_rule(self):
        """Смешать 10 % и 20 %, получить 15 % — отношение 1:1."""
        r = S.mixing_rule(10.0, 20.0, 15.0)
        self.assertAlmostEqual(r.numeric(), 1.0, places=9)
        self.assertAlmostEqual(r.meta["fractions"][0], 0.5, places=9)

    def test_mixing_rule_asymmetric(self):
        """Смешать 0 % и 10 %, получить 2 % — отношение 8:2."""
        r = S.mixing_rule(0.0, 10.0, 2.0)
        self.assertAlmostEqual(r.numeric(), 8.0 / 2.0, places=9)

    def test_mixing_rule_out_of_range(self):
        with self.assertRaises(SolutionError):
            S.mixing_rule(10.0, 20.0, 30.0)


class TestColligative(unittest.TestCase):
    """Коллигативные свойства."""

    def test_vant_hoff_simple(self):
        r = S.vant_hoff_factor(2, 1)
        self.assertAlmostEqual(r.numeric(), 2.0, places=9)

    def test_vant_hoff_from_dissociation(self):
        """NaCl при полной диссоциации: i = 2."""
        r = S.vant_hoff_from_dissociation(1.0, 2)
        self.assertAlmostEqual(r.numeric(), 2.0, places=9)
        r2 = S.vant_hoff_from_dissociation(0.8, 2)
        self.assertAlmostEqual(r2.numeric(), 1.8, places=9)

    def test_dissociation_from_i(self):
        r = S.dissociation_from_vant_hoff(1.8, 2)
        self.assertAlmostEqual(r.numeric(), 0.8, places=9)

    def test_dissociation_roundtrip(self):
        for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
            with self.subTest(alpha=alpha):
                i = S.vant_hoff_from_dissociation(alpha, 3).numeric()
                back = S.dissociation_from_vant_hoff(i, 3).numeric()
                self.assertAlmostEqual(back, alpha, places=9)

    def test_boiling_point_nonelectrolyte(self):
        """0.5 моль/кг неэлектролита в воде: +0.256 К."""
        r = S.boiling_point_elevation("Вода", 0.5, i=1.0)
        self.assertAlmostEqual(r.meta["delta_T"], 0.256, places=4)
        self.assertAlmostEqual(r.numeric(), 373.406, places=3)

    def test_boiling_point_electrolyte(self):
        """0.5 моль/кг NaCl (i = 2): +0.512 К.

        Прежняя версия давала 0.256 К — вдвое меньше истинного.
        """
        r = S.boiling_point_elevation("Вода", 0.5, i=2.0)
        self.assertAlmostEqual(r.meta["delta_T"], 0.512, places=4)
        self.assertAlmostEqual(r.numeric(), 373.662, places=3)

    def test_freezing_point(self):
        """0.5 моль/кг неэлектролита: −0.93 К."""
        r = S.freezing_point_depression("Вода", 0.5, i=1.0)
        self.assertAlmostEqual(r.meta["delta_T"], 0.93, places=3)

    def test_freezing_point_electrolyte(self):
        r = S.freezing_point_depression("Вода", 0.5, i=2.0)
        self.assertAlmostEqual(r.meta["delta_T"], 1.86, places=3)

    def test_boiling_warns_without_i(self):
        r = S.boiling_point_elevation("Вода", 0.5, i=1.0)
        self.assertTrue(r.has_warnings)

    def test_boiling_in_ethanol(self):
        r = S.boiling_point_elevation("Этанол", 1.0, i=1.0)
        self.assertAlmostEqual(r.meta["delta_T"], 1.22, places=4)

    def test_acetone_has_no_kf(self):
        with self.assertRaises(SolutionError):
            S.freezing_point_depression("Ацетон", 1.0)

    def test_osmotic_pressure(self):
        """1 моль/л при 298.15 К: π = 0.08206·298.15 = 24.46 атм."""
        r = S.osmotic_pressure(1.0, 298.15, i=1.0)
        self.assertAlmostEqual(r.numeric(), 24.465, places=2)

    def test_osmotic_pressure_electrolyte(self):
        r = S.osmotic_pressure(0.1, 298.15, i=2.0)
        self.assertAlmostEqual(r.numeric(), 4.893, places=2)

    def test_molar_mass_from_freezing(self):
        """Проверка метода криоскопии.

        1.00 г вещества в 100 г воды даёт ΔT = 0.31 К.
        M = 1.86·1.00/(0.31·0.1) = 60.0 г/моль.
        """
        r = S.molar_mass_from_freezing("Вода", 0.31, 1.0, 100.0)
        self.assertAlmostEqual(r.numeric(), 60.0, places=1)

    def test_molar_mass_from_freezing_invalid(self):
        with self.assertRaises(SolutionError):
            S.molar_mass_from_freezing("Вода", 0.0, 1.0, 100.0)
        with self.assertRaises(SolutionError):
            S.molar_mass_from_freezing("Вода", 0.5, -1.0, 100.0)

    def test_colligative_report(self):
        r = S.colligative_report("Вода", 0.5, i=2.0, molarity=0.48)
        properties = [row["Свойство"] for row in r.value]
        self.assertIn("Повышение температуры кипения", properties)
        self.assertIn("Понижение температуры замерзания", properties)
        self.assertIn("Осмотическое давление", properties)
        self.assertTrue(r.assumptions)


class TestDensityBasedConcentration(unittest.TestCase):
    """Практическая задача: концентрация по измеренной плотности."""

    def test_sulfuric_acid_density(self):
        """Товарная серная кислота 1.84 г/мл — это примерно 98 %."""
        r = S.concentration_from_density("H2SO4", 1.8361)
        self.assertAlmostEqual(r.numeric(), 98.0, places=1)
        # 98 % серная кислота: около 18.4 моль/л
        self.assertGreater(r.meta["molarity"], 18.0)
        self.assertLess(r.meta["molarity"], 18.8)

    def test_sodium_hydroxide_density(self):
        r = S.concentration_from_density("NaOH", 1.2220)
        self.assertAlmostEqual(r.numeric(), 20.0, places=2)

    def test_ambiguous_density_rejected(self):
        """Плотность 1.832 г/мл отвечает и 95 %, и 99 % серной кислоты.

        На нисходящем участке таблицы (после максимума около 98 %)
        однозначно восстановить состав нельзя — программа обязана отказать,
        а не выбрать одно из двух значений наугад.
        """
        with self.assertRaises(SolutionError):
            S.concentration_from_density("H2SO4", 1.8320)

    def test_no_table_for_substance(self):
        with self.assertRaises(SolutionError):
            S.concentration_from_density("KCl", 1.05)

    def test_invalid_density(self):
        with self.assertRaises(SolutionError):
            S.concentration_from_density("NaOH", 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
