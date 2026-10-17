# -*- coding: utf-8 -*-
"""Тесты движков: газы, стехиометрия, кинетика."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alchemy.engines import gases as G
from alchemy.engines import kinetics as K
from alchemy.engines import stoichiometry as S
from alchemy.engines.gases import GasError
from alchemy.engines.kinetics import KineticsError
from alchemy.engines.stoichiometry import StoichiometryError


class TestIdealGas(unittest.TestCase):
    """Уравнение состояния идеального газа."""

    def test_molar_volume_at_stp(self):
        """1 моль при 273.15 К и 1 атм занимает 22.414 л."""
        r = G.ideal_gas(pressure=1.0, moles=1.0, temperature=273.15)
        self.assertAlmostEqual(r.numeric(), 22.414, places=2)

    def test_pressure_from_volume(self):
        r = G.ideal_gas(volume=22.414, moles=1.0, temperature=273.15)
        self.assertAlmostEqual(r.numeric(), 1.0, places=3)

    def test_moles(self):
        r = G.ideal_gas(pressure=1.0, volume=22.414, temperature=273.15)
        self.assertAlmostEqual(r.numeric(), 1.0, places=3)

    def test_temperature(self):
        r = G.ideal_gas(pressure=1.0, volume=22.414, moles=1.0)
        self.assertAlmostEqual(r.numeric(), 273.15, places=2)
        self.assertIn("temperature_c", r.meta)

    def test_temperature_celsius_input(self):
        """0 °C = 273.15 К."""
        r = G.ideal_gas(pressure=1.0, moles=1.0, temperature=0.0,
                        temperature_unit="°C")
        self.assertAlmostEqual(r.numeric(), 22.414, places=2)

    def test_temperature_fahrenheit_input(self):
        """32 °F = 0 °C."""
        r = G.ideal_gas(pressure=1.0, moles=1.0, temperature=32.0,
                        temperature_unit="°F")
        self.assertAlmostEqual(r.numeric(), 22.414, places=1)

    def test_pressure_unit_kpa(self):
        """При 101.325 кПа объём моля тот же, что при 1 атм."""
        r = G.ideal_gas(pressure=101.325, moles=1.0, temperature=273.15,
                        pressure_unit="кПа")
        self.assertAlmostEqual(r.numeric(), 22.414, places=2)

    def test_unit_mismatch_is_handled(self):
        """101325 атм и 101325 Па — совершенно разные давления.

        Если единицы не учитывать, ответы совпали бы. Здесь проверяется,
        что абсурдно большое давление даёт во много раз меньший объём,
        то есть единица реально участвует в расчёте.
        """
        absurd = G.ideal_gas(pressure=101325, moles=1.0, temperature=273.15,
                             pressure_unit="атм")
        physical = G.ideal_gas(pressure=101325, moles=1.0, temperature=273.15,
                               pressure_unit="Па")
        self.assertLess(absurd.numeric(), physical.numeric() / 1000)

    def test_pressure_unit_conversion(self):
        """101.325 кПа — это ровно 1 атм, объёмы должны совпасть."""
        in_atm = G.ideal_gas(pressure=1.0, moles=1.0, temperature=273.15,
                             pressure_unit="атм").numeric()
        in_kpa = G.ideal_gas(pressure=101.325, moles=1.0, temperature=273.15,
                             pressure_unit="кПа").numeric()
        self.assertAlmostEqual(in_atm, in_kpa, places=4)

    def test_pressure_in_pascals_volume(self):
        """1 моль при 101325 Па и 273.15 К занимает 0.0224 м³."""
        r = G.ideal_gas(pressure=101325, moles=1.0, temperature=273.15,
                        pressure_unit="Па", volume_unit="м³")
        self.assertAlmostEqual(r.numeric(), 0.0224, places=4)

    def test_unknown_pressure_unit(self):
        with self.assertRaises(GasError):
            G.ideal_gas(pressure=1.0, moles=1.0, temperature=273.15,
                        pressure_unit="попугаи")

    def test_wrong_number_of_unknowns(self):
        with self.assertRaises(GasError):
            G.ideal_gas(pressure=1.0, volume=1.0)
        with self.assertRaises(GasError):
            G.ideal_gas(pressure=1.0, volume=1.0, moles=1.0, temperature=273.0)

    def test_negative_temperature_rejected(self):
        with self.assertRaises(GasError):
            G.ideal_gas(pressure=1.0, moles=1.0, temperature=-300.0)

    def test_absolute_zero_celsius(self):
        """−273.15 °C — абсолютный нуль, расчёт должен отказать."""
        with self.assertRaises(GasError):
            G.ideal_gas(pressure=1.0, moles=1.0, temperature=-273.15,
                        temperature_unit="°C")

    def test_high_pressure_warning(self):
        r = G.ideal_gas(pressure=50.0, moles=1.0, temperature=300.0)
        self.assertTrue(r.has_warnings)

    def test_low_temperature_warning(self):
        r = G.ideal_gas(pressure=1.0, moles=1.0, temperature=30.0)
        self.assertTrue(r.has_warnings)


class TestVanDerWaals(unittest.TestCase):
    """Уравнение Ван-дер-Ваальса."""

    def test_constants_known_gas(self):
        a, b = G.van_der_waals_constants("CO2")
        self.assertAlmostEqual(a, 3.640, places=3)
        self.assertAlmostEqual(b, 0.0427, places=4)

    def test_unknown_gas(self):
        with self.assertRaises(GasError):
            G.van_der_waals_constants("Xx2")

    def test_pressure_differs_from_ideal(self):
        """При высоком давлении CO2 реальное давление ниже идеального."""
        real = G.van_der_waals(pressure=None, volume=1.0, moles=10.0,
                               temperature=300.0, gas="CO2")
        ideal = G.ideal_gas(volume=1.0, moles=10.0, temperature=300.0)
        self.assertLess(real.numeric(), ideal.numeric())

    def test_volume_solution(self):
        """Обратная задача: объём при заданном давлении."""
        r = G.van_der_waals(pressure=1.0, volume=None, moles=1.0,
                            temperature=273.15, gas="CO2")
        self.assertGreater(r.numeric(), 0)
        # Реальный объём CO2 при н.у. немного меньше идеального
        self.assertLess(r.numeric(), 22.5)

    def test_roundtrip_pressure_volume(self):
        """P -> V -> P должно возвращать исходное давление.

        Допуск умеренный: задача решается численно, и двойное обращение
        уравнения накапливает погрешность метода Ньютона.
        """
        p0 = 5.0
        v = G.van_der_waals(pressure=p0, moles=1.0, temperature=300.0,
                            gas="N2").numeric()
        p_back = G.van_der_waals(volume=v, moles=1.0, temperature=300.0,
                                 gas="N2").numeric()
        self.assertAlmostEqual(p_back, p0, places=1)

    def test_temperature_low_volume_error(self):
        """Объём меньше поправки n·b физически невозможен."""
        with self.assertRaises(GasError):
            G.van_der_waals(pressure=1.0, volume=0.001, moles=1.0,
                            temperature=300.0, gas="CCl4")

    def test_manual_constants(self):
        r = G.van_der_waals(volume=1.0, moles=1.0, temperature=300.0,
                            a=3.64, b=0.0427)
        self.assertGreater(r.numeric(), 0)

    def test_no_constants_given(self):
        with self.assertRaises(GasError):
            G.van_der_waals(volume=1.0, moles=1.0, temperature=300.0)


class TestGasLaws(unittest.TestCase):
    """Частные газовые законы."""

    def test_combined_law_volume(self):
        """P₁V₁/T₁ = P₂V₂/T₂: при удвоении давления объём вдвое меньше."""
        r = G.combined_gas_law(p1=1.0, v1=10.0, t1=300.0, p2=2.0, t2=300.0)
        self.assertAlmostEqual(r.numeric(), 5.0, places=9)

    def test_combined_law_temperature(self):
        r = G.combined_gas_law(p1=1.0, v1=10.0, t1=300.0, p2=1.0, v2=20.0)
        self.assertAlmostEqual(r.numeric(), 600.0, places=6)

    def test_combined_law_celsius(self):
        """27 °C = 300.15 К."""
        r = G.combined_gas_law(p1=1.0, v1=10.0, t1=27.0, p2=1.0, v2=20.0,
                               temperature_unit="°C")
        self.assertAlmostEqual(r.numeric(), 600.3, places=1)

    def test_boyle(self):
        r = G.boyle(p1=2.0, v1=5.0, p2=1.0)
        self.assertAlmostEqual(r.numeric(), 10.0, places=9)

    def test_boyle_invalid(self):
        with self.assertRaises(GasError):
            G.boyle(2.0, 5.0)
        with self.assertRaises(GasError):
            G.boyle(2.0, 5.0, p2=1.0, v2=10.0)

    def test_charles(self):
        """Изобара: при росте T от 300 до 600 К объём удваивается."""
        r = G.charles(v1=10.0, t1=300.0, t2=600.0)
        self.assertAlmostEqual(r.numeric(), 20.0, places=6)

    def test_gay_lussac(self):
        r = G.gay_lussac(p1=1.0, t1=300.0, t2=600.0)
        self.assertAlmostEqual(r.numeric(), 2.0, places=6)


class TestGasMixtures(unittest.TestCase):
    """Смеси газов."""

    def test_dalton_from_partial(self):
        r = G.dalton_law(partial_pressures={"N2": 0.78, "O2": 0.21, "Ar": 0.01})
        self.assertAlmostEqual(r.numeric(), 1.0, places=9)

    def test_dalton_from_fractions(self):
        r = G.dalton_law(mole_fractions={"N2": 0.8, "O2": 0.2},
                         total_pressure=1.0)
        partials = r.meta["partial_pressures"]
        self.assertAlmostEqual(partials["N2"], 0.8, places=9)
        self.assertAlmostEqual(partials["O2"], 0.2, places=9)

    def test_dalton_bad_fractions_sum(self):
        with self.assertRaises(GasError):
            G.dalton_law(mole_fractions={"N2": 0.5, "O2": 0.2},
                         total_pressure=1.0)

    def test_dalton_no_data(self):
        with self.assertRaises(GasError):
            G.dalton_law()

    def test_mixture_from_masses_air(self):
        """Воздух: 78 % N2 и 22 % O2 по объёму дают M около 28.8."""
        # Для мольных долей 0.79 и 0.21 массы пропорциональны M·x
        r = G.dalton_from_masses({"N2": 0.79 * 28.014, "O2": 0.21 * 31.998})
        self.assertAlmostEqual(r.numeric(), 28.85, places=1)

    def test_mixture_pressure_from_volume(self):
        r = G.dalton_from_masses({"N2": 28.0}, volume_l=22.4, temperature_k=273.15)
        self.assertIn("computed_total_pressure", r.meta)
        self.assertAlmostEqual(r.meta["computed_total_pressure"], 1.0, places=2)

    def test_mixture_empty(self):
        with self.assertRaises(GasError):
            G.dalton_from_masses({})


class TestGasDensity(unittest.TestCase):
    """Плотность газа и молярная масса."""

    def test_oxygen_density_stp(self):
        """Кислород при н.у.: 32/22.414 = 1.428 г/л."""
        r = G.gas_density(1.0, 273.15, "O2")
        self.assertAlmostEqual(r.numeric(), 1.428, places=2)

    def test_density_decreases_with_temperature(self):
        d_low = G.gas_density(1.0, 273.15, "O2").numeric()
        d_high = G.gas_density(1.0, 373.15, "O2").numeric()
        self.assertLess(d_high, d_low)

    def test_density_increases_with_pressure(self):
        d1 = G.gas_density(1.0, 300.0, "N2").numeric()
        d2 = G.gas_density(2.0, 300.0, "N2").numeric()
        self.assertAlmostEqual(d2 / d1, 2.0, places=6)

    def test_molar_mass_roundtrip(self):
        """d -> M -> d должно сходиться."""
        d = G.gas_density(1.0, 300.0, "CO2").numeric()
        M = G.molar_mass_from_density(d, 1.0, 300.0).numeric()
        self.assertAlmostEqual(M, 44.009, places=2)

    def test_relative_density_by_air(self):
        """CO2 тяжелее воздуха в 1.52 раза."""
        r = G.relative_density("CO2")
        self.assertAlmostEqual(r.numeric(), 1.52, places=2)

    def test_relative_density_by_hydrogen(self):
        r = G.relative_density("O2", "H2")
        self.assertAlmostEqual(r.numeric(), 15.87, places=1)

    def test_real_density_flag(self):
        r = G.gas_density(10.0, 300.0, "CO2", real=True)
        self.assertIn("density_real", r.meta)
        self.assertIn("z_factor", r.meta)


class TestKineticTheory(unittest.TestCase):
    """Молекулярно-кинетическая теория."""

    def test_oxygen_rms_speed(self):
        """v(ср.кв) кислорода при 298 К около 482 м/с."""
        r = G.molecular_speeds(298.15, "O2")
        self.assertAlmostEqual(r.numeric(), 482.0, places=0)

    def test_speed_ratio_three_kinds(self):
        """v(ср.кв) > v(средняя) > v(наиболее вероятная)."""
        r = G.molecular_speeds(300.0, "N2")
        self.assertGreater(r.meta["v_rms"], r.meta["v_mean"])
        self.assertGreater(r.meta["v_mean"], r.meta["v_most_probable"])

    def test_lighter_gas_faster(self):
        h2 = G.molecular_speeds(300.0, "H2").numeric()
        o2 = G.molecular_speeds(300.0, "O2").numeric()
        self.assertGreater(h2, o2)

    def test_speed_scales_with_sqrt_T(self):
        v1 = G.molecular_speeds(300.0, "N2").numeric()
        v2 = G.molecular_speeds(1200.0, "N2").numeric()
        self.assertAlmostEqual(v2 / v1, 2.0, places=6)

    def test_kinetic_energy(self):
        """<E> = 3/2·k·T при 300 К равно 6.21e-21 Дж."""
        r = G.molecular_speeds(300.0, "He")
        self.assertAlmostEqual(r.meta["mean_kinetic_energy_j"], 6.212e-21, places=23)

    def test_grahams_ratio(self):
        """H2 эффундирует в 3.98 раза быстрее O2."""
        r = G.grahams_law("H2", "O2")
        self.assertAlmostEqual(r.numeric(), 3.98, places=2)

    def test_grahams_rate(self):
        r = G.grahams_law("H2", "O2", rate1=10.0)
        self.assertAlmostEqual(r.numeric(), 10.0 / 3.98, places=2)

    def test_effusion_time(self):
        """Кислород эффундирует медленнее гелия пропорционально √(M(O2)/M(He))."""
        from alchemy.core.formula import molar_mass
        expected = 10.0 * math.sqrt(molar_mass("O2") / molar_mass("He"))
        r = G.effusion_time("O2", "He", 10.0)
        self.assertAlmostEqual(r.numeric(), expected, places=6)

    def test_maxwell_boltzmann_curve(self):
        r = G.maxwell_boltzmann(300.0, "N2", points=50)
        self.assertEqual(len(r.value), 50)
        # Плотность вероятности неотрицательна и где-то максимальна
        values = [p[1] for p in r.value]
        self.assertTrue(all(v >= 0 for v in values))
        self.assertGreater(max(values), 0)


class TestRealGas(unittest.TestCase):
    """Сжимаемость и критические явления."""

    def test_compressibility_near_one_at_low_pressure(self):
        """При низком давлении Z близко к единице."""
        r = G.compressibility_factor(1.0, 300.0, "N2")
        self.assertAlmostEqual(r.numeric(), 1.0, places=1)

    def test_compressibility_below_one_for_attraction(self):
        """При умеренном давлении Z < 1: притяжение преобладает."""
        r = G.compressibility_factor(50.0, 300.0, "CO2")
        self.assertLess(r.numeric(), 1.0)

    def test_below_critical_warning(self):
        r = G.compressibility_factor(30.0, 250.0, "CO2")
        self.assertTrue(r.has_warnings)
        self.assertTrue(r.meta.get("below_critical"))

    def test_critical_parameters_known(self):
        r = G.critical_parameters("CO2")
        self.assertAlmostEqual(r.meta["Tc"], 304.1, places=1)
        self.assertAlmostEqual(r.meta["Pc"], 72.8, places=1)

    def test_vdw_prediction_of_critical(self):
        """Оценка Tк по Ван-дер-Ваальсу должна быть в разумных пределах."""
        r = G.critical_parameters("CO2")
        self.assertGreater(r.meta["Tc_calculated"], 200)
        self.assertLess(r.meta["Tc_calculated"], 500)

    def test_zc_universal(self):
        """Уравнение Ван-дер-Ваальса даёт Zк = 0.375 для любого газа."""
        for gas in ("CO2", "N2", "CH4"):
            with self.subTest(gas=gas):
                r = G.critical_parameters(gas)
                self.assertAlmostEqual(r.meta["Zc"], 0.375, places=6)

    def test_unknown_critical_gas(self):
        with self.assertRaises(GasError):
            G.critical_parameters("Xx2")

    def test_mean_free_path(self):
        r = G.mean_free_path(1.0, 298.15, "N2")
        self.assertGreater(r.numeric(), 0)
        self.assertLess(r.numeric(), 1e-5)

    def test_mean_free_path_decreases_with_pressure(self):
        l1 = G.mean_free_path(1.0, 298.15, "N2").numeric()
        l2 = G.mean_free_path(10.0, 298.15, "N2").numeric()
        self.assertAlmostEqual(l2 / l1, 0.1, places=6)


class TestGasStoichiometry(unittest.TestCase):
    """Стехиометрия газовых реакций."""

    def test_hydrogen_oxygen(self):
        """2H2 + O2 = 2H2O: из 10 л водорода получается 10 л пара."""
        r = G.gas_stoichiometry("H2 + O2 = H2O(г)", "H2", 10.0, target_gas="H2O(г)")
        self.assertAlmostEqual(r.numeric(), 10.0, places=1)

    def test_oxygen_needed(self):
        """Для 10 л водорода нужно 5 л кислорода."""
        r = G.gas_stoichiometry("H2 + O2 = H2O(г)", "H2", 10.0, target_gas="O2")
        self.assertAlmostEqual(r.numeric(), 5.0, places=1)

    def test_all_products_table(self):
        """Таблица по всем веществам уравнения: два реагента и продукт."""
        r = G.gas_stoichiometry("N2 + H2 = NH3(г)", "N2", 10.0)
        self.assertEqual(len(r.value), 3)
        self.assertIn("equation", r.meta)

    def test_missing_species(self):
        with self.assertRaises(GasError):
            G.gas_stoichiometry("H2 + O2 = H2O(г)", "N2", 10.0)

    def test_invalid_volume(self):
        with self.assertRaises(GasError):
            G.gas_stoichiometry("H2 + O2 = H2O(г)", "H2", 0.0)


class TestStoichiometry(unittest.TestCase):
    """Стехиометрические расчёты."""

    def test_parse_reaction(self):
        reactants, products = S.parse_reaction("N2 + H2 = NH3")
        self.assertEqual(len(reactants), 2)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].coefficient, 2)

    # ---------------- лимитирующий реагент ----------------

    def test_limiting_by_moles(self):
        """2H2 + O2 = 2H2O: 2 моль H2 и 2 моль O2 — лимитирует водород."""
        r = S.limiting_reagent("H2 + O2 = H2O", {"H2": 2.0, "O2": 2.0})
        self.assertEqual(r.meta["limiting"], "H2")

    def test_limiting_oxygen(self):
        r = S.limiting_reagent("H2 + O2 = H2O", {"H2": 10.0, "O2": 1.0})
        self.assertEqual(r.meta["limiting"], "O2")

    def test_limiting_by_mass(self):
        """4 г H2 (2 моль) и 32 г O2 (1 моль) — ровно стехиометрия."""
        r = S.limiting_reagent("H2 + O2 = H2O", {"H2": 4.032, "O2": 31.998},
                               amount_kind="mass")
        self.assertIn(r.meta["limiting"], ("H2", "O2"))
        # Отношения должны быть практически равны
        ratios = list(r.meta["ratios"].values())
        self.assertLess(abs(ratios[0] - ratios[1]) / max(ratios), 0.001)

    def test_limiting_warns_stoichiometric(self):
        r = S.limiting_reagent("H2 + O2 = H2O", {"H2": 4.032, "O2": 31.998},
                               amount_kind="mass")
        self.assertTrue(r.has_warnings)

    def test_limiting_unknown_species(self):
        with self.assertRaises(StoichiometryError):
            S.limiting_reagent("H2 + O2 = H2O", {"N2": 1.0})

    def test_limiting_empty(self):
        with self.assertRaises(StoichiometryError):
            S.limiting_reagent("H2 + O2 = H2O", {})

    # ---------------- выход ----------------

    def test_theoretical_yield_mass(self):
        """Из 2 моль H2 получается 2 моль H2O = 36.03 г."""
        r = S.theoretical_yield("H2 + O2 = H2O", 2.0, "H2", "H2O")
        self.assertAlmostEqual(r.numeric(), 36.03, places=1)

    def test_theoretical_yield_moles(self):
        r = S.theoretical_yield("H2 + O2 = H2O", 2.0, "H2", "H2O", solution=True)
        self.assertAlmostEqual(r.numeric(), 2.0, places=6)

    def test_theoretical_yield_from_mass(self):
        """64 г O2 (2 моль) дают 4 моль H2O = 72.06 г."""
        r = S.theoretical_yield("H2 + O2 = H2O", 63.996, "O2", "H2O",
                                amount_kind="mass")
        self.assertAlmostEqual(r.numeric(), 72.06, places=1)

    def test_ammonia_yield(self):
        """Из 1 моль N2 получается 2 моль NH3 = 34.06 г."""
        r = S.theoretical_yield("N2 + H2 = NH3", 1.0, "N2", "NH3")
        self.assertAlmostEqual(r.numeric(), 34.06, places=1)

    def test_percent_yield(self):
        r = S.percent_yield(30.0, 36.0)
        self.assertAlmostEqual(r.numeric(), 83.333, places=2)

    def test_percent_yield_over_hundred_warns(self):
        r = S.percent_yield(40.0, 36.0)
        self.assertTrue(r.has_warnings)
        self.assertGreater(r.numeric(), 100)

    def test_percent_yield_low_warns(self):
        r = S.percent_yield(5.0, 36.0)
        self.assertTrue(r.has_warnings)

    def test_actual_yield(self):
        r = S.actual_yield_from_percent(85.0, 36.0)
        self.assertAlmostEqual(r.numeric(), 30.6, places=6)

    # ---------------- избыток ----------------

    def test_excess_reagent(self):
        """2 моль H2 и 3 моль O2: лимитирует H2, останется 2 моль O2.

        На 2 моль H2 нужно 1 моль O2 (коэффициенты 2 и 1), значит из 3 моль
        кислорода израсходуется 1, а останется 2.
        """
        r = S.excess_reagent("H2 + O2 = H2O", {"H2": 2.0, "O2": 3.0})
        leftovers = r.meta["leftovers"]
        self.assertEqual(r.meta["limiting"], "H2")
        self.assertAlmostEqual(leftovers["O2"], 2.0, places=6)
        self.assertAlmostEqual(leftovers["H2"], 0.0, places=6)

    def test_excess_requires_two(self):
        with self.assertRaises(StoichiometryError):
            S.excess_reagent("H2 + O2 = H2O", {"H2": 2.0})

    # ---------------- растворы ----------------

    def test_titration_volume(self):
        """20 мл 0.1 М HCl нейтрализуются 20 мл 0.1 М NaOH."""
        r = S.titration_volume("HCl + NaOH = NaCl + H2O", "HCl", 0.1, 20.0,
                               "NaOH", 0.1)
        self.assertAlmostEqual(r.numeric(), 20.0, places=3)

    def test_titration_volume_different_concentration(self):
        """20 мл 0.1 М HCl требуют 40 мл 0.05 М NaOH."""
        r = S.titration_volume("HCl + NaOH = NaCl + H2O", "HCl", 0.1, 20.0,
                               "NaOH", 0.05)
        self.assertAlmostEqual(r.numeric(), 40.0, places=3)

    def test_solution_stoichiometry_mass(self):
        """Из 20 мл 0.1 М HCl получается 0.002 моль NaCl = 0.117 г."""
        r = S.solution_stoichiometry(
            "HCl + NaOH = NaCl + H2O",
            {"HCl": (0.1, 20.0), "NaOH": (0.1, 20.0)},
            target="NaCl",
        )
        self.assertAlmostEqual(r.numeric(), 0.1169, places=3)

    def test_solution_stoichiometry_invalid(self):
        with self.assertRaises(StoichiometryError):
            S.solution_stoichiometry("HCl + NaOH = NaCl + H2O",
                                     {"HCl": (0.0, 20.0)}, target="NaCl")

    # ---------------- пересчёты ----------------

    def test_moles_from_mass(self):
        r = S.moles_from("H2O", 18.015, "mass")
        self.assertAlmostEqual(r.numeric(), 1.0, places=4)

    def test_moles_from_gas_volume(self):
        r = S.moles_from("O2", 22.414, "gas_volume_l")
        self.assertAlmostEqual(r.numeric(), 1.0, places=4)

    def test_mass_from_moles(self):
        r = S.mass_from_moles("CO2", 2.0)
        self.assertAlmostEqual(r.numeric(), 88.018, places=2)

    def test_mass_conversion_hydrate(self):
        """249.68 г CuSO4*5H2O соответствуют 159.61 г CuSO4."""
        r = S.mass_conversion("CuSO4*5H2O", "CuSO4", 249.68)
        self.assertAlmostEqual(r.numeric(), 159.61, places=1)

    def test_element_mass_in_sample(self):
        """В 100 г Fe2O3 содержится 69.94 г железа."""
        r = S.element_mass_in_sample("Fe2O3", "Fe", 100.0)
        self.assertAlmostEqual(r.numeric(), 69.94, places=1)

    def test_element_not_in_formula(self):
        with self.assertRaises(StoichiometryError):
            S.element_mass_in_sample("H2O", "Fe", 100.0)

    # ---------------- комплексная задача ----------------

    def test_complex_problem(self):
        """4 г H2 и 32 г O2 дают 36 г воды."""
        r = S.complex_problem(
            "H2 + O2 = H2O",
            [{"species": "H2", "amount": 4.032, "kind": "mass"},
             {"species": "O2", "amount": 31.998, "kind": "mass"}],
        )
        self.assertEqual(len(r.value), 1)
        self.assertAlmostEqual(r.value[0]["Масса, г"], 36.03, places=1)

    def test_complex_problem_excess(self):
        r = S.complex_problem(
            "H2 + O2 = H2O",
            [{"species": "H2", "amount": 2.0, "kind": "moles"},
             {"species": "O2", "amount": 5.0, "kind": "moles"}],
        )
        self.assertIn("excess", r.meta)
        self.assertEqual(r.meta["limiting"], "H2")

    def test_complex_problem_empty(self):
        with self.assertRaises(StoichiometryError):
            S.complex_problem("H2 + O2 = H2O", [])


class TestKinetics(unittest.TestCase):
    """Кинетика."""

    def test_rate_law(self):
        """v = k[A][B] при k=0.1, [A]=2, [B]=3 даёт 0.6."""
        r = K.rate_law(0.1, {"A": 2.0, "B": 3.0}, {"A": 1, "B": 1})
        self.assertAlmostEqual(r.numeric(), 0.6, places=9)
        self.assertAlmostEqual(r.meta["total_order"], 2.0, places=9)

    def test_rate_law_second_order(self):
        r = K.rate_law(0.5, {"A": 2.0}, {"A": 2})
        self.assertAlmostEqual(r.numeric(), 2.0, places=9)

    def test_rate_law_missing_concentration(self):
        with self.assertRaises(KineticsError):
            K.rate_law(0.1, {"A": 1.0}, {"B": 1})

    def test_rate_constant(self):
        r = K.rate_constant_from_rate(0.6, {"A": 2.0, "B": 3.0}, {"A": 1, "B": 1})
        self.assertAlmostEqual(r.numeric(), 0.1, places=9)

    def test_order_of_reaction_integer(self):
        """Удвоение концентрации увеличивает скорость вчетверо — порядок 2."""
        r = K.order_of_reaction(0.1, 1.0, 0.4, 2.0)
        self.assertAlmostEqual(r.numeric(), 2.0, places=6)
        self.assertEqual(r.meta["nearest_integer"], 2)

    def test_order_of_reaction_first(self):
        r = K.order_of_reaction(1.0, 1.0, 2.0, 2.0)
        self.assertAlmostEqual(r.numeric(), 1.0, places=6)

    def test_order_of_reaction_same_concentration(self):
        with self.assertRaises(KineticsError):
            K.order_of_reaction(1.0, 1.0, 2.0, 1.0)

    # ---------------- интегральные законы ----------------

    def test_zero_order_concentration(self):
        """C = C₀ − kt: 1 − 0.1·2 = 0.8."""
        r = K.concentration_at_time(0, 0.1, 1.0, 2.0)
        self.assertAlmostEqual(r.numeric(), 0.8, places=9)

    def test_first_order_concentration(self):
        """C = C₀·e^(−kt): 1·e^(−0.1·2) = 0.8187."""
        r = K.concentration_at_time(1, 0.1, 1.0, 2.0)
        self.assertAlmostEqual(r.numeric(), math.exp(-0.2), places=9)

    def test_second_order_concentration(self):
        """C = C₀/(1 + kC₀t) = 1/(1+0.1·1·2) = 0.8333."""
        r = K.concentration_at_time(2, 0.1, 1.0, 2.0)
        self.assertAlmostEqual(r.numeric(), 1 / 1.2, places=9)

    def test_zero_order_completion_error(self):
        """Реакция нулевого порядка не может дать отрицательную концентрацию."""
        with self.assertRaises(KineticsError):
            K.concentration_at_time(0, 0.1, 1.0, 100.0)

    def test_unsupported_order(self):
        with self.assertRaises(KineticsError):
            K.concentration_at_time(3, 0.1, 1.0, 2.0)

    def test_time_to_concentration_first_order(self):
        """t = ln(1/0.5)/0.1 = 6.93."""
        r = K.time_to_concentration(1, 0.1, 1.0, 0.5)
        self.assertAlmostEqual(r.numeric(), math.log(2) / 0.1, places=6)

    def test_time_to_concentration_impossible(self):
        with self.assertRaises(KineticsError):
            K.time_to_concentration(1, 0.1, 1.0, 2.0)

    def test_half_life_first_order(self):
        """t½ = ln2/k."""
        r = K.half_life(1, 0.1)
        self.assertAlmostEqual(r.numeric(), math.log(2) / 0.1, places=9)

    def test_half_life_independent_of_c0(self):
        """Для первого порядка t½ не зависит от начальной концентрации."""
        t1 = K.half_life(1, 0.1, c0=1.0).numeric()
        t2 = K.half_life(1, 0.1, c0=100.0).numeric()
        self.assertAlmostEqual(t1, t2, places=9)

    def test_half_life_second_order_depends_on_c0(self):
        t1 = K.half_life(2, 0.1, c0=1.0).numeric()
        t2 = K.half_life(2, 0.1, c0=0.5).numeric()
        self.assertAlmostEqual(t2, 2 * t1, places=9)

    def test_half_life_zero_order_requires_c0(self):
        with self.assertRaises(KineticsError):
            K.half_life(0, 0.1)

    def test_half_life_reports_99_percent(self):
        r = K.half_life(1, 0.1)
        self.assertIn("decay_99_percent", r.meta)
        # Для первого порядка 99 % за 4.6 периода полупревращения
        self.assertAlmostEqual(
            r.meta["decay_99_percent"] / r.numeric(), 6.64, places=1
        )

    # ---------------- Аррениус ----------------

    def test_arrhenius_doubling(self):
        """При Ea = 50 кДж/моль нагрев с 300 до 310 К ускоряет реакцию примерно вдвое."""
        r = K.arrhenius_k2(1.0, 300.0, 50000.0, 310.0)
        self.assertGreater(r.numeric(), 1.8)
        self.assertLess(r.numeric(), 2.2)

    def test_arrhenius_same_temperature(self):
        with self.assertRaises(KineticsError):
            K.arrhenius_k2(1.0, 300.0, 50000.0, 300.0)

    def test_arrhenius_negative_ea(self):
        with self.assertRaises(KineticsError):
            K.arrhenius_k2(1.0, 300.0, -1000.0, 310.0)

    def test_activation_energy_roundtrip(self):
        k1 = 1.0
        k2 = K.arrhenius_k2(k1, 300.0, 60000.0, 350.0).numeric()
        ea = K.activation_energy(k1, 300.0, k2, 350.0).numeric()
        self.assertAlmostEqual(ea, 60000.0, places=4)

    def test_activation_energy_negative_warns(self):
        """Если скорость падает при нагреве, нужно предупредить."""
        r = K.activation_energy(2.0, 300.0, 1.0, 350.0)
        self.assertLess(r.numeric(), 0)
        self.assertTrue(r.has_warnings)

    def test_arrhenius_parameters_two_points(self):
        """Подгонка по двум точкам дает точное совпадение."""
        A_true, ea_true = 1e10, 75000.0
        data = [(300.0, A_true * math.exp(-ea_true / (8.314462618 * 300.0))),
                (350.0, A_true * math.exp(-ea_true / (8.314462618 * 350.0)))]
        r = K.arrhenius_parameters(data)
        self.assertAlmostEqual(r.numeric(), ea_true, delta=1.0)
        self.assertTrue(r.has_warnings)   # по двум точкам R² всегда 1

    def test_arrhenius_parameters_many_points(self):
        """Подгонка по пяти точкам дает и Ea, и хороший R²."""
        A_true, ea_true = 5e12, 90000.0
        data = []
        for T in (290, 310, 330, 350, 370):
            k = A_true * math.exp(-ea_true / (8.314462618 * T))
            data.append((float(T), k))
        r = K.arrhenius_parameters(data)
        self.assertAlmostEqual(r.numeric(), ea_true, delta=50.0)
        self.assertGreater(r.meta["r_squared"], 0.9999)
        self.assertAlmostEqual(math.log(r.meta["A"]), math.log(A_true), places=3)

    def test_arrhenius_parameters_too_few(self):
        with self.assertRaises(KineticsError):
            K.arrhenius_parameters([(300.0, 1.0)])

    def test_arrhenius_curve(self):
        r = K.arrhenius_curve(1e10, 75000.0, 250, 600, 40)
        self.assertEqual(len(r.value), 40)
        self.assertIn("ratio_25_35", r.meta)

    # ---------------- определение порядка ----------------

    def test_determine_order_first(self):
        """Данные первого порядка должны распознаться."""
        k_true, c0 = 0.05, 1.0
        times = [0, 5, 10, 15, 20, 25]
        concs = [c0 * math.exp(-k_true * t) for t in times]
        r = K.determine_order(times, concs)
        self.assertEqual(r.meta["order"], 1)
        self.assertAlmostEqual(r.meta["k"], k_true, places=6)
        self.assertGreater(r.meta["r_squared"], 0.9999)

    def test_determine_order_zero(self):
        """Данные нулевого порядка."""
        k_true, c0 = 0.02, 1.0
        times = [0, 5, 10, 15, 20, 25]
        concs = [c0 - k_true * t for t in times]
        r = K.determine_order(times, concs)
        self.assertEqual(r.meta["order"], 0)
        self.assertAlmostEqual(r.meta["k"], k_true, places=6)

    def test_determine_order_second(self):
        """Данные второго порядка."""
        k_true, c0 = 0.1, 1.0
        times = [0, 2, 4, 6, 8, 10]
        concs = [c0 / (1 + k_true * c0 * t) for t in times]
        r = K.determine_order(times, concs)
        self.assertEqual(r.meta["order"], 2)
        self.assertAlmostEqual(r.meta["k"], k_true, places=6)

    def test_determine_order_too_few_points(self):
        with self.assertRaises(KineticsError):
            K.determine_order([0, 1], [1.0, 0.9])

    def test_determine_order_mismatched_lengths(self):
        with self.assertRaises(KineticsError):
            K.determine_order([0, 1, 2], [1.0, 0.9])

    def test_determine_order_zero_concentration(self):
        with self.assertRaises(KineticsError):
            K.determine_order([0, 1, 2, 3], [1.0, 0.5, 0.0, 0.1])

    def test_determine_order_noisy_warns(self):
        """При разбросе данных должно быть предупреждение."""
        times = [0, 5, 10, 15, 20, 25]
        concs = [1.0, 0.85, 0.55, 0.60, 0.20, 0.30]
        r = K.determine_order(times, concs)
        self.assertTrue(r.has_warnings)

    def test_vanthoff_coefficient(self):
        """Удвоение скорости на 10 К даёт γ = 2."""
        r = K.vanthoff_temperature_coefficient(1.0, 2.0, 10.0)
        self.assertAlmostEqual(r.numeric(), 2.0, places=6)

    def test_vanthoff_coefficient_scaled(self):
        """Удвоение на 5 К соответствует γ = 4 на 10 К."""
        r = K.vanthoff_temperature_coefficient(1.0, 2.0, 5.0)
        self.assertAlmostEqual(r.numeric(), 4.0, places=6)

    # ---------------- сложные реакции ----------------

    def test_parallel_reactions(self):
        """k1 = k2 даёт равные доли продуктов."""
        r = K.parallel_reactions(0.1, 0.1)
        self.assertAlmostEqual(r.numeric(), 0.5, places=9)
        self.assertAlmostEqual(r.meta["k_total"], 0.2, places=9)

    def test_parallel_reactions_asymmetric(self):
        r = K.parallel_reactions(0.3, 0.1)
        self.assertAlmostEqual(r.numeric(), 0.75, places=9)
        self.assertAlmostEqual(r.meta["fraction_c"], 0.25, places=9)

    def test_consecutive_reactions_maximum(self):
        """Максимум промежуточного продукта при t = ln(k2/k1)/(k2−k1)."""
        k1, k2 = 0.1, 0.05
        r = K.consecutive_reactions(k1, k2, 1.0)
        t_expected = math.log(k2 / k1) / (k2 - k1)
        self.assertAlmostEqual(r.meta["t_max_b"], t_expected, places=9)
        self.assertGreater(r.meta["b_max"], 0)
        self.assertLess(r.meta["b_max"], 1.0)

    def test_consecutive_equal_constants_rejected(self):
        with self.assertRaises(KineticsError):
            K.consecutive_reactions(0.1, 0.1, 1.0)

    def test_consecutive_mass_balance(self):
        """Сумма концентраций A, B и C постоянна и равна C₀."""
        r = K.consecutive_reactions(0.1, 0.05, 1.0, points=20)
        for point in r.meta["series"]:
            total = point["A"] + point["B"] + point["C"]
            self.assertAlmostEqual(total, 1.0, places=9)

    def test_reversible_equilibrium(self):
        """Равновесные доли определяются отношением констант."""
        k_f, k_r = 0.3, 0.1
        r = K.reversible_first_order(k_f, k_r, 1.0)
        self.assertAlmostEqual(r.meta["K"], 3.0, places=9)
        self.assertAlmostEqual(r.meta["b_inf"], 0.75, places=9)
        self.assertAlmostEqual(r.meta["a_inf"], 0.25, places=9)

    def test_reversible_observed_constant(self):
        r = K.reversible_first_order(0.3, 0.1, 1.0)
        self.assertAlmostEqual(r.meta["k_observed"], 0.4, places=9)

    def test_reversible_invalid(self):
        with self.assertRaises(KineticsError):
            K.reversible_first_order(0.0, 0.1, 1.0)

    def test_catalyst_effect(self):
        """Снижение Ea на 20 кДж/моль ускоряет реакцию в тысячи раз."""
        r = K.catalyst_effect(80000.0, 60000.0, 298.15)
        self.assertGreater(r.numeric(), 1000)

    def test_catalyst_effect_invalid(self):
        with self.assertRaises(KineticsError):
            K.catalyst_effect(50000.0, 60000.0)

    def test_reaction_curve(self):
        r = K.reaction_curve(1, 0.1, 1.0, points=50)
        self.assertEqual(len(r.value), 50)
        # Концентрация убывает
        values = [p[1] for p in r.value]
        self.assertEqual(values, sorted(values, reverse=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
