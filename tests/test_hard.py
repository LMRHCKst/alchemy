# -*- coding: utf-8 -*-
"""Ультрасложные тесты движков: инварианты, а не отдельные числа.

Обычные тесты проверяют «CH4 даёт −802». Эти проверяют то, что должно
выполняться всегда: закон Гесса коммутирует с Кирхгофом, масса и заряд
сохраняются на любой реакции, два разных пути к одной величине дают одно,
а формула восстанавливается из своих же продуктов сгорания.

Тестов немного намеренно. Каждый ловит класс ошибок, а не один случай.
"""

from __future__ import annotations

import math
import unittest

from alchemy.core import formula as F
from alchemy.data import acids as ADB
from alchemy.engines import acidbase as AB
from alchemy.engines import balancer as BAL
from alchemy.engines import electrochemistry as EC
from alchemy.engines import nuclear as NUC
from alchemy.engines import organic as ORG
from alchemy.engines import solutions as SOL
from alchemy.engines import thermo as TH

#: газовая постоянная, Дж/(моль·К)
R = 8.314462618


class TestHessCommutesWithKirchhoff(unittest.TestCase):
    """Закон Гесса и Кирхгоф должны давать одно и то же.

    Берём три реакции, где третья — сумма первых двух. Если интегрирование
    теплоёмкости где-то нелинейно или коэффициент потерян, равенство
    развалится. Дробный коэффициент 1.5 здесь ещё и страхует от повторного
    появления ошибки масштабирования.
    """

    def setUp(self):
        self.first = "CH4 + 2O2 = CO2 + 2H2O(г)"
        self.second = "CO2 = CO + 0.5O2"
        self.sum = "CH4 + 1.5O2 = CO + 2H2O(г)"

    def test_hess_at_298(self):
        first = TH.reaction_enthalpy(self.first).numeric()
        second = TH.reaction_enthalpy(self.second).numeric()
        total = TH.reaction_enthalpy(self.sum).numeric()
        self.assertAlmostEqual(first + second, total, places=2)

    def test_hess_survives_kirchhoff(self):
        """Равенство должно сохраняться и при 1200 К."""
        for temperature in (500.0, 1200.0, 2000.0):
            first = TH.kirchhoff(self.first, temperature).numeric()
            second = TH.kirchhoff(self.second, temperature).numeric()
            total = TH.kirchhoff(self.sum, temperature).numeric()
            self.assertAlmostEqual(
                first + second, total, places=1,
                msg=f"Гесс разошёлся при {temperature} К")

    def test_kirchhoff_returns_gibbs(self):
        """Кирхгоф возвращает ΔG при температуре, а не ΔH.

        Для разложения карбоната кальция ΔG падает с нагревом и переходит
        через ноль около 1100 К — это и есть причина, по которой известь
        обжигают при высокой температуре.
        """
        cold = TH.kirchhoff("CaCO3(тв) = CaO(тв) + CO2", 500.0).numeric()
        hot = TH.kirchhoff("CaCO3(тв) = CaO(тв) + CO2", 1200.0).numeric()
        self.assertGreater(cold, 0)
        self.assertLess(hot, cold)
        self.assertLess(hot, 0)

    def test_kirchhoff_matches_direct_gibbs_at_reference(self):
        """При 298 К обе модели совпадают: поправка на теплоёмкость нулевая.

        Выше они расходятся законно: `kirchhoff` интегрирует ΔCp,
        а `reaction_gibbs(T)` считает по Вант-Гоффу без поправки. Второй
        путь приближённый, и расхождение растёт с температурой.
        """
        equation = "CaCO3(тв) = CaO(тв) + CO2"
        via_kirchhoff = TH.kirchhoff(equation, 298.15).numeric()
        direct = TH.reaction_gibbs(equation, 298.15).numeric()
        self.assertAlmostEqual(via_kirchhoff, direct, delta=0.5)

    def test_kirchhoff_is_more_accurate_than_van_t_hoff(self):
        """Учёт ΔCp обязан сдвигать ответ относительно приближения.

        Если бы Кирхгоф молча возвращал Вант-Гоффа, этот тест бы упал.
        """
        equation = "CaCO3(тв) = CaO(тв) + CO2"
        van_t_hoff = TH.reaction_gibbs(equation, 1400.0).numeric()
        with_cp = TH.kirchhoff(equation, 1400.0).numeric()
        self.assertGreater(abs(with_cp - van_t_hoff), 1.0)

    def test_kirchhoff_warns_about_missing_polynomials(self):
        """Нехватка данных Cp(T) не должна проходить молча."""
        result = TH.kirchhoff("CaCO3(тв) = CaO(тв) + CO2", 900.0)
        self.assertTrue(result.warnings)
        self.assertIn("CaCO3", " ".join(result.warnings))


class TestFractionalCoefficients(unittest.TestCase):
    """Дробные коэффициенты должны сохраняться.

    Балансировщик приводит уравнение к целым числам. Если тепловой эффект
    посчитать по этой целой записи, ответ будет вдвое больше, чем просил
    пользователь. Именно так и было, пока коэффициент не начали возвращать
    к исходной записи.
    """

    def test_half_oxygen(self):
        """H2 + 0.5O2 — это реакция на 1 моль воды."""
        value = TH.reaction_enthalpy("H2 + 0.5O2 = H2O(ж)").numeric()
        self.assertAlmostEqual(value, -285.83, places=1)

    def test_double_oxygen(self):
        value = TH.reaction_enthalpy("2H2 + O2 = 2H2O(ж)").numeric()
        self.assertAlmostEqual(value, -571.66, places=1)

    def test_ratio_is_exactly_two(self):
        half = TH.reaction_enthalpy("H2 + 0.5O2 = H2O(ж)").numeric()
        whole = TH.reaction_enthalpy("2H2 + O2 = 2H2O(ж)").numeric()
        self.assertAlmostEqual(whole / half, 2.0, places=6)

    def test_one_and_a_half_oxygen(self):
        value = TH.reaction_enthalpy("CH4 + 1.5O2 = CO + 2H2O(г)").numeric()
        self.assertAlmostEqual(value, -519.4, delta=1.0)

    def test_fraction_is_reported(self):
        """Если уравнение уравнено, результат обязан это сказать."""
        result = TH.reaction_enthalpy("H2 + O2 = H2O(ж)")
        text = " ".join(result.steps)
        self.assertIn("уравнено", text)


class TestActivityFlagIsHonored(unittest.TestCase):
    """Флаг учёта активностей должен что-то менять.

    Он был объявлен в сигнатурах, но никуда не передавался: галочка
    в интерфейсе ничего не переключала.
    """

    def test_strong_acid_concentration_mode(self):
        """Без активностей pH сильной кислоты равен −lg C."""
        value = AB.ph_of_acid("HCl", 0.01, include_activity=False).numeric()
        self.assertAlmostEqual(value, 2.0, places=4)

    def test_strong_acid_with_activity(self):
        """С активностями pH выше: коэффициент активности меньше единицы."""
        plain = AB.ph_of_acid("HCl", 0.01, include_activity=False).numeric()
        active = AB.ph_of_acid("HCl", 0.01, include_activity=True).numeric()
        self.assertGreater(active, plain)

    def test_activity_changes_result(self):
        plain = AB.ph_of_acid("HCl", 0.1, include_activity=False).numeric()
        active = AB.ph_of_acid("HCl", 0.1, include_activity=True).numeric()
        self.assertAlmostEqual(plain, 1.0, places=3)
        self.assertGreater(active - plain, 0.05)

    def test_strong_base_concentration_mode(self):
        """pH основания без активностей = pKw − pOH."""
        pkw = ADB.pkw_at(298.15)
        value = AB.ph_of_base("NaOH", 0.01, include_activity=False).numeric()
        self.assertAlmostEqual(value, pkw - 2.0, places=3)


class TestEquilibriumConsistency(unittest.TestCase):
    """Три пути к константе равновесия должны сойтись."""

    EQUATION = "CaCO3(тв) = CaO(тв) + CO2"

    def test_constant_from_enthalpy_and_entropy(self):
        """K из (ΔH, ΔS) должен совпасть с K из ΔG."""
        temperature = 298.15
        enthalpy = TH.reaction_enthalpy(self.EQUATION).numeric()
        entropy = TH.reaction_entropy(self.EQUATION).numeric()
        gibbs = TH.reaction_gibbs(self.EQUATION, temperature).numeric()

        from_entropy = math.exp(
            -(enthalpy * 1000 - temperature * entropy) / (R * temperature))
        from_gibbs = TH.equilibrium_constant(gibbs, temperature).numeric()

        self.assertAlmostEqual(from_entropy / from_gibbs, 1.0, places=6)

    def test_equilibrium_temperature_gives_unit_constant(self):
        """При температуре равновесия движущая сила нулевая."""
        temperature = TH.equilibrium_temperature(self.EQUATION).numeric()
        gibbs = TH.reaction_gibbs(self.EQUATION, temperature).numeric()
        self.assertAlmostEqual(gibbs, 0.0, delta=1.0)

    def test_constant_falls_with_temperature(self):
        """У эндотермической реакции K растёт с температурой."""
        cold = TH.equilibrium_constant(
            TH.reaction_gibbs(self.EQUATION, 800).numeric(), 800).numeric()
        hot = TH.equilibrium_constant(
            TH.reaction_gibbs(self.EQUATION, 1200).numeric(), 1200).numeric()
        self.assertGreater(hot, cold)


class TestBalanceInvariants(unittest.TestCase):
    """Масса и заряд должны сохраняться на любой реакции.

    Здесь и легендарная реакция с гигантскими коэффициентами, которую
    вручную уравнивают на доске полчаса.
    """

    HARD = [
        "K4[Fe(CN)6] + KMnO4 + H2SO4 = KHSO4 + Fe2(SO4)3 + MnSO4 + HNO3 + CO2 + H2O",
        "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O",
        "Cr2O7^2- + Fe^2+ + H^+ = Cr^3+ + Fe^3+ + H2O",
        "Cu2S + HNO3 = Cu(NO3)2 + H2SO4 + NO + H2O",
        "P + HNO3 + H2O = H3PO4 + NO",
    ]

    @staticmethod
    def _split(term: str) -> tuple[int, str]:
        """Коэффициент и формула из записи вещества."""
        import re

        text = term.strip()
        match = re.match(r"^(\d+)(\D.*)$", text)
        if match:
            return int(match.group(1)), match.group(2).strip()
        return 1, text

    def _check(self, equation: str):
        balanced = BAL.balance(equation).value
        left, right = BAL.parse_equation(balanced)

        atoms: dict[str, float] = {}
        charge = 0.0
        for sign, terms in ((-1, left), (1, right)):
            for term in terms:
                coefficient, body = self._split(term)
                composition = F.parse(body)
                for element, count in composition.counts.items():
                    atoms[element] = atoms.get(element, 0.0) + \
                        sign * coefficient * count
                charge += sign * coefficient * composition.charge

        drift = {el: value for el, value in atoms.items()
                 if abs(value) > 1e-6}
        return drift, charge, balanced

    def test_atoms_and_charge_conserved(self):
        for equation in self.HARD:
            drift, charge, balanced = self._check(equation)
            self.assertEqual(drift, {},
                             f"не сходится баланс атомов: {balanced}")
            self.assertAlmostEqual(charge, 0.0, places=6,
                                   msg=f"не сходится заряд: {balanced}")

    def test_coefficients_are_integers(self):
        for equation in self.HARD:
            balanced = BAL.balance(equation).value
            for chunk in balanced.replace("→", "=").split("="):
                for term in chunk.split("+"):
                    text = term.strip()
                    if not text:
                        continue
                    coefficient, _body = self._split(text)
                    self.assertGreater(coefficient, 0, text)
                    self.assertAlmostEqual(
                        coefficient, round(coefficient), places=9,
                        msg=f"дробный коэффициент в {balanced}")

    def test_legendary_equation_exact(self):
        """У этой реакции коэффициенты известны и велики."""
        balanced = BAL.balance(self.HARD[0]).value
        for fragment in ("10K4[Fe(CN)6]", "122KMnO4", "299H2SO4",
                         "122MnSO4", "60CO2", "188H2O"):
            self.assertIn(fragment, balanced)


class TestElectrochemistryRoundTrip(unittest.TestCase):
    """ЭДС, энергия Гиббса и константа равновесия — один и тот же факт."""

    def test_gibbs_to_emf_and_back(self):
        for energy in (-100.0, -213.0, -400.0):
            emf = EC.emf_from_gibbs(energy, 2).numeric()
            back = EC.gibbs_from_emf(emf, 2).numeric()
            self.assertAlmostEqual(back, energy, places=6)

    def test_emf_uses_n(self):
        """Для двух электронов ЭДС вдвое меньше, чем для одного."""
        one = EC.emf_from_gibbs(-200.0, 1).numeric()
        two = EC.emf_from_gibbs(-200.0, 2).numeric()
        self.assertAlmostEqual(one / two, 2.0, places=6)

    def test_constant_from_emf_matches_nernst(self):
        emf = 1.10
        electrons = 2
        temperature = 298.15
        expected = math.exp(electrons * 96485.33212 * emf
                            / (R * temperature))
        result = EC.equilibrium_constant_from_emf(
            emf, electrons, temperature).numeric()
        self.assertAlmostEqual(result / expected, 1.0, places=4)

    def test_spontaneous_has_negative_gibbs(self):
        energy = EC.gibbs_from_emf(1.10, 2).numeric()
        self.assertLess(energy, 0)


class TestColligativeConsistency(unittest.TestCase):
    """Осмос и криоскопия — два взгляда на одно число частиц."""

    def test_same_vant_hoff_from_both(self):
        """Из осмотического давления и понижения температуры замерзания
        должен получиться один фактор Вант-Гоффа."""
        molarity = 0.1
        temperature = 298.15
        expected_i = 2.0

        pressure = SOL.osmotic_pressure(
            molarity, temperature_k=temperature, i=expected_i).numeric()
        # π = i·C·R·T, давление в атмосферах
        i_from_pressure = pressure / (molarity * 0.082057366 * temperature)
        self.assertAlmostEqual(i_from_pressure, expected_i, places=2)

        freezing = SOL.freezing_point_depression(
            "Вода", molarity, expected_i).numeric()
        # Функция возвращает температуру замерзания, а не понижение
        depression = 273.15 - freezing
        i_from_freezing = depression / (1.86 * molarity)
        self.assertAlmostEqual(i_from_freezing, expected_i, delta=0.05)

    def test_pressure_linear_in_concentration(self):
        first = SOL.osmotic_pressure(0.1, i=1.0).numeric()
        second = SOL.osmotic_pressure(0.2, i=1.0).numeric()
        self.assertAlmostEqual(second / first, 2.0, places=6)

    def test_pressure_linear_in_factor(self):
        one = SOL.osmotic_pressure(0.1, i=1.0).numeric()
        three = SOL.osmotic_pressure(0.1, i=3.0).numeric()
        self.assertAlmostEqual(three / one, 3.0, places=6)


class TestDecayConservation(unittest.TestCase):
    """Распад: аналитика, численная цепочка и сохранение атомов."""

    def test_analytic_matches_chain(self):
        analytic = NUC.decayed_amount(1000.0, 10.0, 30.0, "с").numeric()
        chain = NUC.decay_chain(1000.0, [10.0], 30.0, "с")
        numeric = chain.meta["amounts"][0]
        self.assertAlmostEqual(analytic, numeric, delta=abs(analytic) * 1e-6)

    def test_chain_conserves_atoms(self):
        """Сумма по всем звеньям цепочки равна начальному количеству."""
        result = NUC.decay_chain(1000.0, [10.0, 5.0], 37.0, "с")
        total = sum(result.meta["amounts"])
        self.assertAlmostEqual(total, 1000.0, delta=1e-6)

    def test_three_half_lives(self):
        """За три периода остаётся ровно восьмая часть."""
        left = NUC.decayed_amount(1000.0, 10.0, 30.0, "с").numeric()
        self.assertAlmostEqual(left, 125.0, places=6)

    def test_long_chain_also_conserves(self):
        result = NUC.decay_chain(500.0, [10.0, 3.0, 1.0, 0.5], 120.0, "с")
        self.assertAlmostEqual(sum(result.meta["amounts"]), 500.0, delta=1e-6)


class TestCombustionRoundTrip(unittest.TestCase):
    """Формула должна восстанавливаться из своих же продуктов сгорания.

    Для каждого вещества считаем, сколько даст CO2 и H2O при сгорании
    одного моля, затем скармливаем эти массы обратно и требуем исходную
    формулу. Это проверяет весь путь: разбор формулы, пересчёт молей,
    кислород по разности, подбор целых отношений.
    """

    FORMULAS = [
        "CH4", "C2H6", "C3H8", "C2H4", "C2H2", "C6H6",
        "C2H6O", "C3H6O", "C2H4O2", "C6H12O6", "C12H22O11",
    ]

    def test_round_trip(self):
        for formula in self.FORMULAS:
            composition = F.parse(formula)
            molar = composition.molar_mass
            carbons = composition.counts.get("C", 0)
            hydrogens = composition.counts.get("H", 0)

            co2_mass = carbons * 44.009
            h2o_mass = hydrogens / 2 * 18.015

            result = ORG.combustion_formula(
                molar, co2_mass=co2_mass, h2o_mass=h2o_mass,
                molar_mass=molar)

            expected = F.normalize_input(formula)
            self.assertEqual(
                F.normalize_input(result.meta["molecular"]), expected,
                f"{formula}: получено {result.meta['molecular']}")

    def test_hydrocarbon_has_no_oxygen(self):
        for formula in ("CH4", "C2H4", "C6H6", "C8H18"):
            composition = F.parse(formula)
            result = ORG.combustion_formula(
                composition.molar_mass,
                co2_mass=composition.counts["C"] * 44.009,
                h2o_mass=composition.counts["H"] / 2 * 18.015)
            self.assertAlmostEqual(result.meta["oxygens"], 0.0, places=6)


class TestPHCrossChecks(unittest.TestCase):
    """Два пути к одному pH должны согласоваться."""

    def test_titration_start_matches_acid_ph(self):
        """Кривая титрования при V=0 и прямой расчёт pH дают близкое."""
        direct = AB.ph_of_acid("CH3COOH", 0.1).numeric()
        curve = AB.titration_ph_at("CH3COOH", 0.1, 20.0, 0.1, 0.0).numeric()
        self.assertAlmostEqual(direct, curve, delta=0.05)

    def test_strong_acid_paths_agree(self):
        direct = AB.ph_of_acid("HCl", 0.1).numeric()
        curve = AB.titration_ph_at("HCl", 0.1, 20.0, 0.1, 0.0).numeric()
        self.assertAlmostEqual(direct, curve, places=6)

    def test_buffer_at_equal_concentrations_is_pka(self):
        """При равных концентрациях pH буфера равен pKa."""
        plain = AB.buffer_ph("CH3COOH", 0.1, 0.1,
                             include_activity=False).numeric()
        self.assertAlmostEqual(plain, 4.757, places=3)

    def test_ph_of_very_dilute_acid_tends_to_neutral(self):
        """В пределе бесконечного разбавления pH стремится к нейтральному."""
        pkw = ADB.pkw_at(298.15)
        value = AB.ph_of_acid("HCl", 1e-8).numeric()
        self.assertAlmostEqual(value, pkw / 2, delta=0.1)


if __name__ == "__main__":
    unittest.main()
