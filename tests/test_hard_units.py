# -*- coding: utf-8 -*-
"""Вторая партия ультрасложных тестов: единицы, кинетика, данные.

Первая партия лежит в test_hard.py. Здесь другие пласты: перевод единиц,
устойчивость парсера формул, закон Аррениуса, уравнение Нернста,
согласованность концентраций и целостность самих справочников.
"""

from __future__ import annotations

import math
import unittest

from alchemy.core import formula as F
from alchemy.core import units as U
from alchemy.data import acids as ADB
from alchemy.data import solubility as SDB
from alchemy.data import thermo as TDB
from alchemy.engines import electrochemistry as EC
from alchemy.engines import kinetics as KIN
from alchemy.engines import solutions as SOL
from alchemy.engines import stoichiometry as ST

#: газовая постоянная, Дж/(моль·К)
R = 8.314462618

#: число Фарадея
FARADAY = 96485.33212


class TestUnitsRoundTrip(unittest.TestCase):
    """Перевод единиц туда и обратно должен возвращать исходное."""

    PAIRS = [
        ("атм", "Па"), ("бар", "Па"), ("мм рт.ст.", "Па"),
        ("мл", "л"), ("мг", "г"), ("кДж", "Дж"),
        ("мин", "с"), ("ч", "мин"), ("моль", "ммоль"),
    ]

    def test_round_trip(self):
        for first, second in self.PAIRS:
            value = 3.7
            converted = U.convert(value, first, second)
            back = U.convert(converted, second, first)
            self.assertAlmostEqual(back, value, places=9,
                                   msg=f"не вернулось: {first} -> {second}")

    def test_atmosphere_is_exactly_pascal_standard(self):
        """1 атм = 101325 Па по определению, а не приблизительно."""
        self.assertAlmostEqual(U.convert(1.0, "атм", "Па"), 101325.0, places=6)

    def test_mmhg_matches_atmosphere(self):
        """760 мм рт.ст. — это ровно одна атмосфера."""
        self.assertAlmostEqual(U.convert(760.0, "мм рт.ст.", "Па"),
                               101325.0, delta=0.05)

    def test_temperature_offset(self):
        """Шкала Цельсия сдвинута, а не масштабирована."""
        self.assertAlmostEqual(U.convert(0.0, "°C", "К"), 273.15, places=6)
        self.assertAlmostEqual(U.convert(25.0, "°C", "К"), 298.15, places=6)
        self.assertAlmostEqual(U.convert(-273.15, "°C", "К"), 0.0, places=6)

    def test_temperature_span_is_scaled_not_offset(self):
        """Разность температур переводится без сдвига на 273.15.

        Проверяем через сами величины: 100 °C минус 0 °C дают столько же,
        сколько 373.15 К минус 273.15 К.
        """
        hot_k = U.convert(100.0, "°C", "К")
        cold_k = U.convert(0.0, "°C", "К")
        self.assertAlmostEqual(hot_k - cold_k, 100.0, places=6)

    def test_parse_keeps_unit(self):
        value, unit = U.parse_quantity("760 мм рт.ст.")
        self.assertAlmostEqual(value, 760.0)
        self.assertEqual(unit, "мм рт.ст.")

    def test_parse_rejects_garbage(self):
        with self.assertRaises(Exception):
            U.parse_quantity("много")


class TestFormulaParserInvariants(unittest.TestCase):
    """Парсер формул должен быть предсказуемым на странном входе."""

    CHARGE_FORMS = ["MnO4-", "MnO4^-", "MnO4{-}"]

    def test_all_charge_notations_agree(self):
        masses = [F.molar_mass(form) for form in self.CHARGE_FORMS]
        for mass in masses[1:]:
            self.assertAlmostEqual(mass, masses[0], places=9)

    def test_charge_is_one(self):
        for form in self.CHARGE_FORMS:
            self.assertEqual(F.parse(form).charge, -1, form)

    def test_normalize_is_idempotent(self):
        """Повторная нормализация не должна ничего менять."""
        samples = ["CuSO4*5H2O", "MnO4{-}", "SO4^2-", "Ca(OH)2",
                   "[Cu(NH3)4]SO4", "Fe2O3(тв)", "0.5O2", "SO4²⁻"]
        for sample in samples:
            once = F.normalize_input(sample)
            twice = F.normalize_input(once)
            self.assertEqual(once, twice, f"не идемпотентно: {sample}")

    def test_molar_mass_equals_sum_of_parts(self):
        """Масса формулы равна сумме вкладов элементов."""
        for sample in ["H2SO4", "K4[Fe(CN)6]", "Ca(OH)2", "C12H22O11"]:
            composition = F.parse(sample)
            total = sum(composition.counts[el] * element_mass(el)
                        for el in composition.elements)
            self.assertAlmostEqual(composition.molar_mass, total, places=6,
                                   msg=sample)

    def test_hydrate_mass_adds_up(self):
        """CuSO4·5H2O весит столько же, сколько CuSO4 плюс пять вод."""
        hydrate = F.molar_mass("CuSO4*5H2O")
        anhydrous = F.molar_mass("CuSO4")
        water = 5 * F.molar_mass("H2O")
        self.assertAlmostEqual(hydrate, anhydrous + water, places=6)

    def test_mass_percentages_sum_to_hundred(self):
        for sample in ["H2SO4", "C6H12O6", "K4[Fe(CN)6]", "Al2(SO4)3"]:
            composition = F.parse(sample)
            total = sum(composition.mass_percentages.values())
            self.assertAlmostEqual(total, 100.0, places=6, msg=sample)

    def test_degree_of_unsaturation(self):
        """Бензол: четыре единицы ненасыщенности."""
        self.assertEqual(F.degrees_of_unsaturation("C6H6"), 4)
        self.assertEqual(F.degrees_of_unsaturation("C2H6"), 0)


class TestArrheniusInvariants(unittest.TestCase):
    """Закон Аррениуса: энергия активации должна восстанавливаться."""

    def test_energy_round_trip(self):
        """Ea из двух констант, затем обратно в k — и вернулись."""
        k1, t1, k2, t2 = 0.001, 300.0, 0.01, 400.0
        energy = KIN.activation_energy(k1, t1, k2, t2).numeric()
        back = KIN.arrhenius_k2(k1, t1, energy, t2).numeric()
        self.assertAlmostEqual(back / k2, 1.0, places=6)

    def test_energy_matches_analytic_formula(self):
        k1, t1, k2, t2 = 0.5, 310.0, 4.0, 350.0
        expected = R * math.log(k2 / k1) / (1 / t1 - 1 / t2)
        result = KIN.activation_energy(k1, t1, k2, t2).numeric()
        self.assertAlmostEqual(result / expected, 1.0, places=6)

    def test_rate_grows_with_temperature(self):
        value = KIN.arrhenius_k2(0.1, 300.0, 50000.0, 400.0).numeric()
        self.assertGreater(value, 0.1)

    def test_first_order_half_life_is_independent_of_start(self):
        """У первого порядка период полупревращения не зависит от C₀."""
        first = KIN.half_life(1, 0.1, 1.0).numeric()
        second = KIN.half_life(1, 0.1, 100.0).numeric()
        self.assertAlmostEqual(first, second, places=9)

    def test_half_life_matches_ln2_over_k(self):
        self.assertAlmostEqual(KIN.half_life(1, 0.1).numeric(),
                               math.log(2) / 0.1, places=6)

    def test_second_order_half_life_scales_inversely(self):
        """У второго порядка период полупревращения обратен C₀."""
        first = KIN.half_life(2, 0.1, 0.1).numeric()
        second = KIN.half_life(2, 0.1, 0.2).numeric()
        self.assertAlmostEqual(first / second, 2.0, places=6)

    def test_order_recovered_from_clean_data(self):
        """Из идеальных данных первый порядок определяется уверенно."""
        times = [0.0, 10.0, 20.0, 30.0, 40.0]
        concentrations = [1.0 * math.exp(-0.07 * t) for t in times]
        result = KIN.determine_order(times, concentrations)
        self.assertEqual(result.meta["order"], 1)
        self.assertGreater(result.meta["r_squared"], 0.999)

    def test_order_discriminated(self):
        """Нулевой порядок не должен путаться с первым."""
        times = [0.0, 10.0, 20.0, 30.0]
        concentrations = [1.0 - 0.02 * t for t in times]
        result = KIN.determine_order(times, concentrations)
        self.assertEqual(result.meta["order"], 0)


class TestNernstInvariants(unittest.TestCase):
    """Уравнение Нернста: ноль при Q = 1 и наклон 59 мВ."""

    def test_unit_activity_gives_standard_potential(self):
        value = EC.nernst_potential(0.77, 1, oxidized=1.0,
                                    reduced=1.0).numeric()
        self.assertAlmostEqual(value, 0.77, places=9)

    def test_tenfold_change_gives_59_millivolts(self):
        """На каждый порядок активности — 59.16 мВ при одном электроне."""
        high = EC.nernst_potential(0.0, 1, oxidized=1.0, reduced=1.0).numeric()
        low = EC.nernst_potential(0.0, 1, oxidized=0.1, reduced=1.0).numeric()
        expected = 0.05916
        self.assertAlmostEqual(high - low, expected, delta=5e-4)

    def test_two_electrons_halve_the_slope(self):
        one = EC.nernst_potential(0.0, 1, oxidized=0.1, reduced=1.0).numeric()
        two = EC.nernst_potential(0.0, 2, oxidized=0.1, reduced=1.0).numeric()
        self.assertAlmostEqual(one / two, 2.0, places=4)

    def test_ph_slope_for_one_proton(self):
        """Один протон на один электрон даёт 59 мВ на единицу pH."""
        acid = EC.nernst_potential(0.0, 1, oxidized=1.0, reduced=1.0,
                                   ph=0.0, protons=1).numeric()
        neutral = EC.nernst_potential(0.0, 1, oxidized=1.0, reduced=1.0,
                                      ph=7.0, protons=1).numeric()
        self.assertAlmostEqual(acid - neutral, 7 * 0.05916, delta=2e-3)

    def test_concentration_cell_follows_nernst(self):
        """ЭДС концентрационной ячейки считается по Нернсту.

        Перестановку концентраций движок отвергает: разбавленный раствор
        обязан быть разбавленным. Поэтому проверяем саму величину.
        """
        emf = EC.concentration_cell("Cu2+/Cu", 0.001, 1.0).numeric()
        expected = 0.05916 / 2 * 3      # два электрона, три порядка
        self.assertAlmostEqual(emf, expected, delta=2e-3)

    def test_concentration_cell_rejects_inverted_input(self):
        with self.assertRaises(Exception):
            EC.concentration_cell("Cu2+/Cu", 1.0, 0.001)


class TestSolutionConsistency(unittest.TestCase):
    """Концентрации должны пересчитываться без потерь."""

    def test_mass_fraction_matches_masses(self):
        solution = SOL.from_molarity("NaCl", 0.5, 1.0)
        total = solution.solute_mass + solution.solute_mass * (
            1 - solution.mass_fraction) / solution.mass_fraction
        self.assertAlmostEqual(solution.solute_mass / total,
                               solution.mass_fraction, places=9)

    def test_mass_percent_is_hundred_times_fraction(self):
        solution = SOL.from_molarity("NaCl", 0.5, 1.0)
        self.assertAlmostEqual(solution.mass_percent,
                               solution.mass_fraction * 100, places=9)

    def test_molality_exceeds_molarity_for_dense_solution(self):
        """Для водного раствора моляльность больше молярности."""
        solution = SOL.from_molarity("NaCl", 1.0, 1.0)
        self.assertGreater(solution.molality, solution.molarity)

    def test_dilution_conserves_amount(self):
        """При разбавлении количество вещества сохраняется."""
        result = SOL.dilution(c_initial=2.0, v_initial=0.1,
                              c_final=0.5)
        self.assertAlmostEqual(result.numeric(), 0.4, places=6)

    def test_serial_dilution_is_geometric(self):
        """Три переноса по 1 мл в колбу 10 мл дают тысячное разбавление."""
        result = SOL.serial_dilution(1.0, 1.0, 10.0, 3)
        last = result.value[-1]
        self.assertAlmostEqual(last["Концентрация, моль/л"], 1e-3, delta=1e-9)

    def test_osmotic_pressure_proportional_to_molarity(self):
        first = SOL.osmotic_pressure(0.1).numeric()
        second = SOL.osmotic_pressure(0.3).numeric()
        self.assertAlmostEqual(second / first, 3.0, places=6)


class TestStoichiometryInvariants(unittest.TestCase):
    """Лимитирующий реагент должен переключаться при обмене количеств."""

    EQUATION = "Fe2O3 + CO = Fe + CO2"

    def test_limiting_switches_with_amounts(self):
        first = ST.limiting_reagent(self.EQUATION,
                                    {"Fe2O3": 0.1, "CO": 10.0}).value
        second = ST.limiting_reagent(self.EQUATION,
                                     {"Fe2O3": 10.0, "CO": 0.1}).value
        self.assertNotEqual(first, second)

    def test_excess_pairs_with_limiting(self):
        """Тот, кто не лимитирует, должен оказаться в избытке."""
        amounts = {"Fe2O3": 0.1, "CO": 10.0}
        limiting = ST.limiting_reagent(self.EQUATION, amounts).value
        excess = ST.excess_reagent(self.EQUATION, amounts).value
        self.assertNotEqual(limiting, excess)

    def test_yield_scales_linearly(self):
        """Удвоение лимитирующего реагента удваивает продукт."""
        one = ST.theoretical_yield(self.EQUATION, 1.0, "Fe2O3", "Fe").numeric()
        two = ST.theoretical_yield(self.EQUATION, 2.0, "Fe2O3", "Fe").numeric()
        self.assertAlmostEqual(two / one, 2.0, places=6)

    def test_percent_yield_is_ratio(self):
        value = ST.percent_yield(8.0, 10.0).numeric()
        self.assertAlmostEqual(value, 80.0, places=6)


class TestDataIntegrity(unittest.TestCase):
    """Справочники должны быть внутренне согласованы.

    Это не тест движка, а тест данных: если в JSON попадёт битая формула
    или невозможная величина, узнать об этом надо здесь, а не на расчёте.
    """

    def test_all_thermo_formulas_parse(self):
        broken = []
        for substance in TDB.all_substances():
            try:
                F.parse(substance.formula)
            except Exception:
                broken.append((substance.key, substance.formula))
        self.assertEqual(broken, [], f"не разбираются: {broken}")

    def test_entropy_is_positive(self):
        """Третий закон: энтропия вещества при 298 К положительна."""
        broken = [(s.key, s.S) for s in TDB.all_substances()
                  if s.S is not None and s.S <= 0]
        self.assertEqual(broken, [], f"отрицательная энтропия: {broken}")

    def test_formation_energies_are_finite(self):
        broken = []
        for substance in TDB.all_substances():
            if substance.dHf is None:
                continue
            if not math.isfinite(substance.dHf):
                broken.append(substance.key)
        self.assertEqual(broken, [])

    def test_truly_strong_acids_are_fully_dissociated(self):
        """При pKa ниже −1 диссоциация полная: pH = −lg C."""
        from alchemy.engines import acidbase as AB

        for formula in ("HCl", "HBr", "HI", "HClO4", "HNO3", "H2SO4"):
            value = AB.ph_of_acid(formula, 0.1,
                                  include_activity=False).numeric()
            self.assertAlmostEqual(value, 1.0, places=2, msg=formula)

    def test_strong_label_does_not_override_pka(self):
        """Ярлык «сильная» не должен отменять константу.

        У иодоводородной HIO3 pKa 0.80, у роданистоводородной HSCN 0.85,
        у трифторуксусной 0.23. В справочнике они помечены сильными, но
        при 0.1 М диссоциируют не полностью: pH выше единицы.
        """
        from alchemy.engines import acidbase as AB

        for formula in ("HIO3", "HSCN", "CF3COOH", "CCl3COOH"):
            acid = ADB.find_acid(formula)
            self.assertTrue(acid.is_strong, formula)
            self.assertGreater(acid.pKa, 0, formula)

            value = AB.ph_of_acid(formula, 0.1,
                                  include_activity=False).numeric()
            self.assertGreater(value, 1.0, formula)
            self.assertLess(value, 1.5, formula)

    def test_weak_acids_have_positive_pka(self):
        weak = [a for a in ADB.all_acids() if not a.is_strong]
        self.assertGreater(len(weak), 0)
        for acid in weak:
            self.assertGreater(acid.pKa, 0, acid.formula)
            self.assertLess(acid.pKa, 40, acid.formula)

    def test_all_ksp_positive(self):
        broken = [(s.formula, s.Ksp) for s in SDB.all_solids()
                  if not s.Ksp > 0]
        self.assertEqual(broken, [], f"неположительные Ksp: {broken}")

    def test_acid_masses_match_formula_parser(self):
        """Молярная масса кислоты в справочнике совпадает с расчётом."""
        broken = []
        for acid in ADB.all_acids():
            try:
                parsed = F.molar_mass(acid.formula)
            except Exception:
                continue
            stored = getattr(acid, "M", None)
            if stored and abs(stored - parsed) > 0.5:
                broken.append((acid.formula, stored, round(parsed, 2)))
        self.assertEqual(broken, [], f"расхождение масс: {broken}")


class TestDeterminism(unittest.TestCase):
    """Повторный вызов не должен менять ответ."""

    def test_repeated_calls_identical(self):
        calls = [
            lambda: F.molar_mass("CuSO4*5H2O"),
            lambda: F.parse("K4[Fe(CN)6]").molar_mass,
            lambda: U.convert(1.0, "атм", "Па"),
            lambda: KIN.half_life(1, 0.1).numeric(),
            lambda: SOL.osmotic_pressure(0.1, i=2.0).numeric(),
            lambda: EC.nernst_potential(0.77, 1, oxidized=1.0,
                                        reduced=1.0).numeric(),
        ]
        for call in calls:
            first = call()
            for _ in range(3):
                self.assertEqual(call(), first)

    def test_parser_is_pure(self):
        """Разбор одного вещества не влияет на разбор другого."""
        first = F.molar_mass("H2O")
        F.molar_mass("K4[Fe(CN)6]")
        F.parse("C12H22O11")
        self.assertEqual(F.molar_mass("H2O"), first)


def element_mass(symbol: str) -> float:
    """Атомная масса элемента из справочника."""
    from alchemy.core import periodic

    return periodic.by_symbol(symbol).atomic_mass


if __name__ == "__main__":
    unittest.main()
