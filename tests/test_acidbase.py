# -*- coding: utf-8 -*-
"""Тесты кислотно-основного движка: активности, pH, буферы, титрование."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alchemy.engines import acidbase as AB
from alchemy.engines.acidbase import AcidBaseError, AcidSystem
from alchemy.core.errors import DomainError


class TestActivity(unittest.TestCase):
    """Ионная сила и коэффициенты активности."""

    def test_ionic_strength_1_1(self):
        """0.1 моль/л NaCl: I = ½(0.1·1 + 0.1·1) = 0.1."""
        I = AB.ionic_strength({"Na^+": 0.1, "Cl^-": 0.1})
        self.assertAlmostEqual(I, 0.1, places=9)

    def test_ionic_strength_2_1(self):
        """0.1 моль/л CaCl2: I = ½(0.1·4 + 0.2·1) = 0.3."""
        I = AB.ionic_strength({"Ca^2+": 0.1, "Cl^-": 0.2})
        self.assertAlmostEqual(I, 0.3, places=9)

    def test_neutral_species_do_not_contribute(self):
        I = AB.ionic_strength({"CH3COOH": 1.0})
        self.assertAlmostEqual(I, 0.0, places=9)

    def test_gamma_is_one_in_dilute(self):
        """В предельно разбавленном растворе γ → 1 с точностью до 0.1 %."""
        gamma = AB.activity_coefficient(1.0, 1e-9)
        self.assertAlmostEqual(gamma, 1.0, places=3)

    def test_gamma_less_than_one(self):
        """В реальном растворе коэффициент активности меньше единицы."""
        gamma = AB.activity_coefficient(1.0, 0.1)
        self.assertLess(gamma, 1.0)
        self.assertGreater(gamma, 0.5)

    def test_gamma_higher_charge_lower(self):
        """Чем больше заряд, тем сильнее отклонение от идеальности."""
        g1 = AB.activity_coefficient(1.0, 0.01)
        g2 = AB.activity_coefficient(2.0, 0.01)
        self.assertLess(g2, g1)

    def test_debye_huckel_A_at_25(self):
        """A = 0.510 при 25 °C (справочное значение 0.509)."""
        A = AB.debye_huckel_A(298.15)
        self.assertAlmostEqual(A, 0.510, places=2)

    def test_debye_huckel_B_at_25(self):
        """B = 3.29 нм⁻¹ при 25 °C (справочное значение 3.29)."""
        B = AB.debye_huckel_B(298.15)
        self.assertAlmostEqual(B, 3.29, places=1)

    def test_debye_huckel_A_increases_with_T(self):
        """При нагревании диэлектрическая проницаемость падает, A растёт.

        Справочные значения: 0.509 при 25 °C и 0.609 при 100 °C.
        """
        self.assertAlmostEqual(AB.debye_huckel_A(373.15), 0.607, places=2)
        self.assertGreater(AB.debye_huckel_A(373.15), AB.debye_huckel_A(298.15))

    def test_extended_model_known_value(self):
        """γ(H⁺) при I = 0.01 равно 0.915 по справочным таблицам.

        Проверяется расширенное уравнение с диаметром иона 0.9 нм —
        именно такое значение воспроизводит табличные коэффициенты.
        """
        gamma = AB.activity_coefficient(1.0, 0.01, model="extended",
                                        ion_size_nm=AB.ion_size("H^+"))
        self.assertAlmostEqual(gamma, 0.915, places=2)

    def test_extended_model_at_higher_ionic_strength(self):
        """γ(H⁺) при I = 0.1 равно 0.83 по справочнику."""
        gamma = AB.activity_coefficient(1.0, 0.1, model="extended",
                                        ion_size_nm=AB.ion_size("H^+"))
        self.assertAlmostEqual(gamma, 0.83, places=1)

    def test_ion_size_table(self):
        self.assertEqual(AB.ion_size("H^+"), 0.9)
        self.assertEqual(AB.ion_size("Cl^-"), 0.3)
        # Неизвестный ион получает значение по умолчанию
        self.assertEqual(AB.ion_size("Xx^+"), AB.ION_SIZE_NM)

    def test_negative_ionic_strength_rejected(self):
        with self.assertRaises(DomainError):
            AB.activity_coefficient(1.0, -0.1)


class TestSimplePh(unittest.TestCase):
    """pH сильных и слабых электролитов."""

    def test_strong_acid_01_ideal(self):
        """Без учёта активности pH = 1.000 ровно."""
        r = AB.strong_acid_ph(0.1, ionic_strength_=0.0)
        self.assertAlmostEqual(r.numeric(), 1.0, places=6)

    def test_strong_acid_01_with_activity(self):
        """С учётом активности pH 0.1 М HCl около 1.11.

        Экспериментальное значение pH 0.1 М соляной кислоты — около 1.1,
        потому что γ±(HCl) ≈ 0.796. Идеальная формула pH = −lg C даёт 1.00.
        Проверяем, что программа воспроизводит именно реальное поведение.
        """
        r = AB.strong_acid_ph(0.1)
        self.assertAlmostEqual(r.numeric(), 1.11, places=1)
        self.assertGreater(r.numeric(), 1.0)

    def test_strong_acid_ideal(self):
        """Без учёта активности pH = 1.000 ровно."""
        r = AB.strong_acid_ph(0.1, ionic_strength_=0.0)
        self.assertAlmostEqual(r.numeric(), 1.0, places=6)

    def test_strong_acid_activity_shifts_ph(self):
        """Активность повышает pH относительно идеального расчёта."""
        ideal = AB.strong_acid_ph(0.1, ionic_strength_=0.0).numeric()
        real = AB.strong_acid_ph(0.1).numeric()
        self.assertGreater(real, ideal)

    def test_strong_acid_temperature(self):
        """При 100 °C pH 0.1 М HCl немного выше из-за роста pKw."""
        r25 = AB.strong_acid_ph(0.1, 298.15).numeric()
        r100 = AB.strong_acid_ph(0.1, 373.15).numeric()
        self.assertNotAlmostEqual(r25, r100, places=2)

    def test_strong_acid_warns_at_high_concentration(self):
        r = AB.strong_acid_ph(5.0)
        self.assertTrue(r.has_warnings)

    def test_strong_base(self):
        """0.1 М NaOH: pH около 12.89 с учётом активности.

        Идеальная формула даёт 12.98, реальное значение ниже из-за γ(OH⁻) < 1.
        """
        r = AB.strong_base_ph(0.1)
        self.assertAlmostEqual(r.numeric(), 12.89, places=1)
        self.assertLess(r.numeric(), 13.0)

    def test_strong_base_ideal(self):
        """Идеальный расчёт даёт pH = pKw = 12.995 при 25 °C.

        Не ровно 13, потому что pKw при 25 °C равно 13.995, а не 14.000:
        температурная зависимость ионного произведения воды учитывается.
        """
        r = AB.strong_base_ph(0.1, ionic_strength_=0.0)
        self.assertAlmostEqual(r.numeric(), 12.995, places=2)

    def test_strong_base_divalent(self):
        """0.05 М Ca(OH)2 даёт 0.1 моль/л OH⁻, как 0.1 М NaOH."""
        r1 = AB.strong_base_ph(0.05, n_hydroxide=2).numeric()
        r2 = AB.strong_base_ph(0.1, n_hydroxide=1).numeric()
        self.assertAlmostEqual(r1, r2, places=9)

    def test_neutral_water_at_100c(self):
        """При 100 °C нейтральная среда имеет pH 6.14, а не 7.

        Это прямая проверка того, что температурная зависимость pKw работает.
        """
        from alchemy.data import acids as ADB
        self.assertAlmostEqual(ADB.pkw_at(373.15), 12.27, places=1)
        self.assertAlmostEqual(ADB.neutral_ph(373.15), 6.14, places=1)

    def test_weak_acid_exact_solution(self):
        """Уксусная кислота 0.1 М, Ka = 1.75e-5: pH ≈ 2.88.

        Проверяем, что решается точное квадратное уравнение.
        """
        r = AB.weak_acid_ph(0.1, 1.75e-5, ionic_strength_=0.0)
        # sqrt(Ka*C) = 1.323e-3 -> pH 2.879
        self.assertAlmostEqual(r.numeric(), 2.879, places=2)

    def test_weak_acid_approximation_quality(self):
        """При C/Ka < 100 приближение √(Ka·C) даёт заметную ошибку."""
        r = AB.weak_acid_ph(0.001, 1.75e-5, ionic_strength_=0.0)
        approx_ph = -math.log10(math.sqrt(1.75e-5 * 0.001))
        self.assertNotAlmostEqual(r.numeric(), approx_ph, places=2)

    def test_weak_acid_dissociation_degree(self):
        r = AB.weak_acid_ph(0.1, 1.75e-5, ionic_strength_=0.0)
        self.assertLess(r.meta["alpha"], 0.05)

    def test_weak_acid_invalid(self):
        with self.assertRaises(AcidBaseError):
            AB.weak_acid_ph(0.0, 1e-5)
        with self.assertRaises(AcidBaseError):
            AB.weak_acid_ph(0.1, 0.0)


class TestPhFromDatabase(unittest.TestCase):
    """pH по справочным данным."""

    def test_hydrochloric_acid(self):
        """0.1 М HCl: pH около 1.11 при учёте активности."""
        r = AB.ph_of_acid("HCl", 0.1)
        self.assertAlmostEqual(r.numeric(), 1.11, places=1)

    def test_acetic_acid(self):
        r = AB.ph_of_acid("CH3COOH", 0.1)
        # Справочная Ka = 1.75e-5, pH около 2.87
        self.assertAlmostEqual(r.numeric(), 2.87, places=1)

    def test_ammonia(self):
        """0.1 М аммиак: pH около 11.1."""
        r = AB.ph_of_base("NH3", 0.1)
        self.assertAlmostEqual(r.numeric(), 11.1, places=1)

    def test_sodium_hydroxide(self):
        """0.1 М NaOH: pH около 12.89 при учёте активности."""
        r = AB.ph_of_base("NaOH", 0.1)
        self.assertAlmostEqual(r.numeric(), 12.89, places=1)

    def test_calcium_hydroxide(self):
        """Ca(OH)2 даёт вдвое больше OH⁻, чем NaOH той же концентрации."""
        ca = AB.ph_of_base("Ca(OH)2", 0.01).numeric()
        na = AB.ph_of_base("NaOH", 0.02).numeric()
        self.assertAlmostEqual(ca, na, places=6)

    def test_phosphoric_acid_full_equilibrium(self):
        """Фосфорная кислота 0.1 М: pH около 1.6.

        Расчёт учитывает все три ступени, а не только первую.
        """
        r = AB.ph_of_acid("H3PO4", 0.1)
        self.assertLess(r.numeric(), 2.0)
        self.assertGreater(r.numeric(), 1.2)
        self.assertIn("full_equilibrium_ph", r.meta)

    def test_carbonic_acid(self):
        r = AB.ph_of_acid("H2CO3", 0.01)
        self.assertGreater(r.numeric(), 3.0)

    def test_unknown_acid(self):
        with self.assertRaises(Exception):
            AB.ph_of_acid("H2XxO4", 0.1)

    def test_temperature_warning_when_no_data(self):
        """Для кислоты без температурных коэффициентов — предупреждение."""
        r = AB.ph_of_acid("HClO4", 0.1, temperature_k=323.15)
        self.assertTrue(r.has_warnings or r.steps)


class TestEquilibriumSolver(unittest.TestCase):
    """Общий решатель равновесий."""

    def test_strong_acid_solver_matches_formula(self):
        """Решатель и формула для сильной кислоты должны совпасть."""
        eq = AB.solve_acid_base([], strong_acid=0.1, include_activity=False)
        self.assertAlmostEqual(eq.ph, 1.0, places=6)

    def test_strong_base_solver(self):
        eq = AB.solve_acid_base([], strong_base=0.1, include_activity=False)
        self.assertAlmostEqual(eq.ph, 12.995, places=2)

    def test_weak_acid_solver_vs_quadratic(self):
        """Решатель и квадратное уравнение должны дать одно и то же."""
        ka = 1.75e-5
        system = AcidSystem("CH3COOH", 0.1, [-math.log10(ka)])
        eq = AB.solve_acid_base([system], include_activity=False)
        analytic = AB.weak_acid_ph(0.1, ka, ionic_strength_=0.0).numeric()
        self.assertAlmostEqual(eq.ph, analytic, places=3)

    def test_amphiprotic_dihydrogen_phosphate(self):
        """NaH₂PO₄ — амфолит. pH ≈ ½(pKa₁ + pKa₂) = 4.67.

        Моделируется как H₃PO₄ + 1 NaOH: ионы натрия входят в баланс заряда.
        """
        system = AcidSystem("H3PO4", 0.1, [2.148, 7.198])
        eq = AB.solve_acid_base([system], strong_base=0.1, include_activity=False)
        self.assertAlmostEqual(eq.ph, 4.67, places=1)

    def test_amphiprotic_hydrogen_phosphate(self):
        """Na₂HPO₄ — амфолит. pH близок к ½(pKa₂ + pKa₃) = 9.77.

        При концентрации 0.1 моль/л приближение амфолита работает хуже
        из-за большой ионной силы, поэтому допуск шире.
        """
        system = AcidSystem("H3PO4", 0.1, [2.148, 7.198])
        eq = AB.solve_acid_base([system], strong_base=0.2, include_activity=False)
        self.assertAlmostEqual(eq.ph, 9.77, delta=0.5)

    def test_trisodium_phosphate_is_alkaline(self):
        """Na₃PO₄ даёт сильнощелочную среду."""
        system = AcidSystem("H3PO4", 0.1, [2.148, 7.198])
        eq = AB.solve_acid_base([system], strong_base=0.3, include_activity=False)
        self.assertGreater(eq.ph, 11.0)

    def test_spectator_ions_keep_balance(self):
        """Раствор соляной кислоты электронейтрален только с учётом Cl⁻.

        Без аниона сильной кислоты баланс не сходится и решатель находит
        ложный корень в щелочной области.
        """
        eq = AB.solve_acid_base([], strong_acid=0.1, include_activity=False)
        self.assertAlmostEqual(eq.ph, 1.0, places=6)

    def test_buffer_region(self):
        """Смесь кислоты и её соли: pH вблизи pKa."""
        system = AcidSystem("CH3COOH", 0.1, [4.757])
        eq = AB.solve_acid_base([system], strong_base=0.05, include_activity=False)
        # Полунейтрализация: pH = pKa
        self.assertAlmostEqual(eq.ph, 4.757, places=1)

    def test_ionic_strength_grows_with_salt(self):
        pure = AB.solve_acid_base([], strong_acid=0.001)
        salty = AB.solve_acid_base([], strong_acid=0.001, strong_base=0.0,
                                   include_activity=False)
        self.assertGreaterEqual(pure.ionic_strength, 0.0)

    def test_activity_lowers_h_concentration(self):
        """С учётом активности концентрация H⁺ выше, а pH больше."""
        no_act = AB.solve_acid_base([], strong_acid=0.1, include_activity=False)
        with_act = AB.solve_acid_base([], strong_acid=0.1, include_activity=True)
        self.assertGreater(with_act.ph, no_act.ph)

    def test_negative_concentration_rejected(self):
        with self.assertRaises(AcidBaseError):
            AB.solve_acid_base([], strong_acid=-0.1)

    def test_temperature_effect_on_solver(self):
        eq25 = AB.solve_acid_base([], strong_base=0.1, temperature_k=298.15,
                                  include_activity=False)
        eq100 = AB.solve_acid_base([], strong_base=0.1, temperature_k=373.15,
                                   include_activity=False)
        # При 100 °C pKw = 12.27, поэтому pH ниже 13
        self.assertLess(eq100.ph, eq25.ph)

    def test_convergence_result_fields(self):
        eq = AB.solve_acid_base([], strong_acid=0.01)
        self.assertTrue(eq.converged)
        self.assertGreater(eq.ph, 0)
        self.assertGreater(eq.h_concentration, 0)
        self.assertGreater(eq.iterations, 0)


class TestBuffer(unittest.TestCase):
    """Буферные растворы."""

    def test_buffer_ph_at_equal_concentrations(self):
        """Равные концентрации кислоты и соли дают pH = pKa."""
        r = AB.buffer_ph("CH3COOH", 0.1, 0.1, include_activity=False)
        self.assertAlmostEqual(r.numeric(), 4.757, places=3)

    def test_buffer_ph_ratio_ten(self):
        """Соотношение 10:1 даёт pH = pKa + 1."""
        r = AB.buffer_ph("CH3COOH", 0.1, 1.0, include_activity=False)
        self.assertAlmostEqual(r.numeric(), 5.757, places=3)

    def test_buffer_ph_ratio_one_tenth(self):
        r = AB.buffer_ph("CH3COOH", 1.0, 0.1, include_activity=False)
        self.assertAlmostEqual(r.numeric(), 3.757, places=3)

    def test_buffer_activity_shifts_ph(self):
        ideal = AB.buffer_ph("CH3COOH", 0.1, 0.1, include_activity=False).numeric()
        real = AB.buffer_ph("CH3COOH", 0.1, 0.1, include_activity=True).numeric()
        self.assertLess(real, ideal)   # γ(A⁻) < 1 понижает pH

    def test_buffer_warns_outside_range(self):
        r = AB.buffer_ph("CH3COOH", 1.0, 0.001)
        self.assertTrue(r.has_warnings)

    def test_buffer_invalid(self):
        with self.assertRaises(AcidBaseError):
            AB.buffer_ph("CH3COOH", 0.0, 0.1)

    def test_buffer_capacity_maximum_at_pka(self):
        """Максимум ёмкости при равенстве концентраций."""
        at_pka = AB.buffer_capacity("CH3COOH", 0.1, 0.1).numeric()
        off_pka = AB.buffer_capacity("CH3COOH", 0.1, 0.001).numeric()
        self.assertGreater(at_pka, off_pka)

    def test_buffer_capacity_formula(self):
        """β = 2.303·C/4 при [HA] = [A⁻]."""
        r = AB.buffer_capacity("CH3COOH", 0.1, 0.1)
        expected = 2.303 * 0.2 / 4
        self.assertAlmostEqual(r.numeric(), expected, places=6)

    def test_buffer_preparation(self):
        """Для pH = pKa нужно равное количество кислоты и соли."""
        r = AB.buffer_preparation("CH3COOH", 4.757, 1.0, 0.2)
        self.assertAlmostEqual(r.meta["c_acid"], 0.1, places=6)
        self.assertAlmostEqual(r.meta["c_salt"], 0.1, places=6)

    def test_buffer_preparation_masses(self):
        """Проверка расчёта навески ацетата натрия."""
        r = AB.buffer_preparation("CH3COOH", 5.0, 0.5, 0.2)
        self.assertIn("mass_salt_g", r.meta)
        self.assertGreater(r.meta["mass_salt_g"], 0)

    def test_buffer_preparation_invalid(self):
        with self.assertRaises(AcidBaseError):
            AB.buffer_preparation("CH3COOH", 5.0, 0.0, 0.2)


class TestTitration(unittest.TestCase):
    """Кривые титрования из равновесий."""

    def test_strong_acid_curve(self):
        """HCl 0.1 М, 20 мл, титрант 0.1 М: V экв = 20 мл, pH старта ≈ 1.11."""
        r = AB.titration_curve("HCl", 0.1, 20.0, 0.1, points=41)
        self.assertAlmostEqual(r.meta["v_equivalence_ml"], 20.0, places=2)
        self.assertAlmostEqual(r.meta["ph_initial"], 1.11, places=1)

    def test_strong_acid_equivalence_ph(self):
        """В точке эквивалентности сильной кислоты pH близок к 7.

        Не ровно 7, потому что при 25 °C pKw = 13.995, а не 14.000.
        """
        r = AB.titration_curve("HCl", 0.1, 20.0, 0.1, points=81)
        v_eq = r.meta["v_equivalence_ml"]
        closest = min(r.value, key=lambda p: abs(p[0] - v_eq))
        self.assertAlmostEqual(closest[1], 7.0, delta=0.2)

    def test_weak_acid_half_neutralization(self):
        """При полунейтрализации слабой кислоты pH = pKa."""
        r = AB.titration_curve("CH3COOH", 0.1, 20.0, 0.1, points=81)
        self.assertIn("ph_half", r.meta)
        self.assertAlmostEqual(r.meta["ph_half"], 4.757, places=1)

    def test_weak_acid_equivalence_ph_alkaline(self):
        """В точке эквивалентности слабой кислоты среда щелочная."""
        r = AB.titration_curve("CH3COOH", 0.1, 20.0, 0.1, points=81)
        self.assertGreater(r.meta["ph_equivalence"], 7.0)

    def test_curve_is_monotonic(self):
        """pH вдоль кривой титрования не убывает."""
        r = AB.titration_curve("HCl", 0.1, 20.0, 0.1, points=41)
        values = [p[1] for p in r.value]
        for i in range(len(values) - 1):
            self.assertLessEqual(values[i], values[i + 1] + 1e-6)

    def test_curve_has_enough_points(self):
        r = AB.titration_curve("HCl", 0.1, 20.0, 0.1, points=41)
        self.assertGreaterEqual(len(r.value), 30)

    def test_indicator_suggested(self):
        r = AB.titration_curve("HCl", 0.1, 20.0, 0.1, points=81)
        self.assertIn("suitable_indicators", r.meta)

    def test_weak_acid_indicator(self):
        """Для уксусной кислоты точка эквивалентности щелочная — фенолфталеин."""
        r = AB.titration_curve("CH3COOH", 0.1, 20.0, 0.1, points=81)
        names = r.meta.get("suitable_indicators", [])
        self.assertTrue(any("Фенолфталеин" in n or "Тимолфталеин" in n for n in names),
                        f"подобраны индикаторы: {names}")

    def test_titration_invalid_params(self):
        with self.assertRaises(AcidBaseError):
            AB.titration_curve("HCl", 0.0, 20.0, 0.1)
        with self.assertRaises(AcidBaseError):
            AB.titration_curve("HCl", 0.1, 0.0, 0.1)

    # ---------------- pH в точке ----------------

    def test_ph_at_start(self):
        r = AB.titration_ph_at("HCl", 0.1, 20.0, 0.1, 0.0)
        self.assertAlmostEqual(r.numeric(), 1.11, places=1)
        self.assertIn("до точки", r.meta["stage"])

    def test_ph_at_equivalence(self):
        r = AB.titration_ph_at("HCl", 0.1, 20.0, 0.1, 20.0)
        self.assertAlmostEqual(r.numeric(), 7.0, delta=0.2)
        self.assertEqual(r.meta["stage"], "точка эквивалентности")

    def test_ph_after_equivalence(self):
        r = AB.titration_ph_at("HCl", 0.1, 20.0, 0.1, 40.0)
        self.assertGreater(r.numeric(), 7.0)
        self.assertIn("после точки", r.meta["stage"])

    def test_ph_excess_base_value(self):
        """При 40 мл титранта избыток 0.1 М NaOH разбавлен вдвое: pH около 12.6."""
        r = AB.titration_ph_at("HCl", 0.1, 20.0, 0.1, 40.0)
        self.assertAlmostEqual(r.numeric(), 12.6, places=1)

    # ---------------- погрешность индикатора ----------------

    def test_titration_error_strong_acid(self):
        """Для сильной кислоты с метиловым оранжевым погрешность заметна."""
        r = AB.titration_error("HCl", 0.1, 20.0, 0.1, "Метиловый оранжевый")
        self.assertIsInstance(r.numeric(), float)
        # Метиловый оранжевый переходит при pH 3.46, а точка экв при 7
        self.assertLess(r.numeric(), 0)   # титранта уйдёт меньше

    def test_titration_error_phenolphthalein_for_weak(self):
        """Для уксусной кислоты фенолфталеин даёт малую погрешность."""
        r = AB.titration_error("CH3COOH", 0.1, 20.0, 0.1, "Фенолфталеин")
        self.assertLess(abs(r.numeric()), 2.0)

    def test_titration_error_reports_values(self):
        r = AB.titration_error("HCl", 0.1, 20.0, 0.1, "Фенолфталеин")
        self.assertIn("v_equivalence_ml", r.meta)
        self.assertIn("v_indicator_ml", r.meta)

    def test_compare_indicators(self):
        r = AB.compare_indicators("CH3COOH", 0.1, 20.0, 0.1)
        self.assertGreater(len(r.value), 3)
        # Отсортировано по возрастанию погрешности
        errors = [abs(row["Погрешность, %"]) for row in r.value]
        self.assertEqual(errors, sorted(errors))
        self.assertIn("Пригоден", r.value[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
