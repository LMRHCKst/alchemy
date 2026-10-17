# -*- coding: utf-8 -*-
"""Тесты уравнивания реакций и термохимии.

Эталонные тепловые эффекты взяты из справочников и проверены независимым
расчётом по закону Гесса.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alchemy.engines import balancer, thermo
from alchemy.engines.balancer import BalanceError
from alchemy.engines.thermo import ThermoError
from alchemy.core.errors import DomainError, InputError


class TestBalancer(unittest.TestCase):
    """Уравнивание реакций."""

    def test_simple(self):
        r = balancer.balance("H2 + O2 = H2O")
        self.assertEqual(r.value, "2H2 + O2 → 2H2O")
        self.assertEqual(r.meta["left"], {"H2": 2, "O2": 1})
        self.assertEqual(r.meta["right"], {"H2O": 2})

    def test_combustion_propane(self):
        r = balancer.balance("C3H8 + O2 = CO2 + H2O")
        self.assertEqual(r.meta["left"], {"C3H8": 1, "O2": 5})
        self.assertEqual(r.meta["right"], {"CO2": 3, "H2O": 4})

    def test_iron_oxide(self):
        r = balancer.balance("Fe + O2 = Fe2O3")
        self.assertEqual(r.meta["left"], {"Fe": 4, "O2": 3})
        self.assertEqual(r.meta["right"], {"Fe2O3": 2})

    def test_redox_permanganate(self):
        """Классическая окислительно-восстановительная реакция."""
        r = balancer.balance("KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O")
        self.assertEqual(r.meta["left"]["KMnO4"], 2)
        self.assertEqual(r.meta["left"]["HCl"], 16)
        self.assertEqual(r.meta["right"]["Cl2"], 5)
        self.assertEqual(r.meta["right"]["H2O"], 8)

    def test_redox_copper_nitric(self):
        r = balancer.balance("Cu + HNO3 = Cu(NO3)2 + NO + H2O")
        self.assertEqual(r.meta["left"], {"Cu": 3, "HNO3": 8})
        self.assertEqual(r.meta["right"]["NO"], 2)
        self.assertEqual(r.meta["right"]["H2O"], 4)

    def test_ionic_charge_balance(self):
        """В ионной форме баланс заряда обязателен."""
        r = balancer.balance("MnO4^- + H^+ + e^- = Mn^2+ + H2O")
        self.assertEqual(r.meta["left"]["MnO4^-"], 1)
        self.assertEqual(r.meta["left"]["H^+"], 8)
        self.assertEqual(r.meta["left"]["e^-"], 5)
        self.assertEqual(r.meta["right"]["Mn^2+"], 1)
        self.assertEqual(r.meta["right"]["H2O"], 4)

    def test_ionic_dichromate(self):
        r = balancer.balance("Cr2O7^2- + H^+ + e^- = Cr^3+ + H2O")
        self.assertEqual(r.meta["left"]["Cr2O7^2-"], 1)
        self.assertEqual(r.meta["left"]["H^+"], 14)
        self.assertEqual(r.meta["left"]["e^-"], 6)
        self.assertEqual(r.meta["right"]["Cr^3+"], 2)
        self.assertEqual(r.meta["right"]["H2O"], 7)

    def test_charge_row_in_verification(self):
        """Проверка заряда должна попасть в отчёт."""
        r = balancer.balance("Fe^2+ + Ce^4+ = Fe^3+ + Ce^3+")
        self.assertIn("заряд", r.meta["elements"])

    def test_arrow_variants(self):
        """Все варианты записи стрелки должны работать."""
        for sep in (" = ", " -> ", " → ", " => "):
            with self.subTest(separator=sep):
                r = balancer.balance(f"H2 + O2{sep}H2O")
                self.assertEqual(r.meta["right"]["H2O"], 2)

    def test_arrow_inside_side_rejected(self):
        """Стрелка внутри одной части уравнения — ошибка записи."""
        with self.assertRaises(ValueError):
            balancer.balance("H2 -> O2 = H2O")

    def test_unsolvable_equation(self):
        """H2 = O2 уравнять нельзя: это две разные реакции, а не одна."""
        with self.assertRaises(BalanceError):
            balancer.balance("H2 = O2")

    def test_list_input(self):
        r = balancer.balance((["H2", "O2"], ["H2O"]))
        self.assertEqual(r.meta["right"]["H2O"], 2)

    def test_balanced_check_on_unbalanced(self):
        self.assertFalse(balancer.is_balanced("H2 + O2 = H2O"))
        self.assertTrue(balancer.is_balanced("2H2 + O2 = 2H2O"))

    def test_impossible_reaction(self):
        """Из NaCl нельзя получить Na и Cl2 в одном уравнении с O2."""
        with self.assertRaises(BalanceError):
            balancer.balance("NaCl = Na + Cl2 + O2")

    def test_duplicate_species_rejected(self):
        with self.assertRaises(BalanceError):
            balancer.balance("H2 + H2 = H2O")

    def test_wrong_side_rejected(self):
        """Если вещество записано не на своей стороне — должна быть ошибка."""
        with self.assertRaises(BalanceError):
            balancer.balance("H2O = H2 + O2 + H2O")

    def test_no_separator(self):
        with self.assertRaises(BalanceError):
            balancer.balance("H2 + O2")

    def test_empty(self):
        with self.assertRaises(BalanceError):
            balancer.balance("")

    def test_unknown_element(self):
        """Неизвестный элемент — ошибка разбора формулы, а не молчаливый результат."""
        with self.assertRaises(ValueError):
            balancer.balance("Xx2 + O2 = XxO")

    def test_large_coefficients_warn(self):
        """Горение октана даёт большие коэффициенты — предупреждение уместно."""
        r = balancer.balance("C8H18 + O2 = CO2 + H2O")
        self.assertEqual(r.meta["left"]["C8H18"], 2)
        self.assertEqual(r.meta["left"]["O2"], 25)

    def test_molar_ratio(self):
        r = balancer.molar_ratio("N2 + H2 = NH3", "N2", "NH3")
        self.assertAlmostEqual(r.numeric(), 2.0, places=6)
        self.assertEqual(r.meta["ratio_exact"], "2:1")

    def test_molar_ratio_fraction(self):
        """1 моль O2 даёт 2 моль H2O."""
        r = balancer.molar_ratio("H2 + O2 = H2O", "O2", "H2O")
        self.assertAlmostEqual(r.numeric(), 2.0, places=6)

    def test_molar_ratio_missing_species(self):
        with self.assertRaises(BalanceError):
            balancer.molar_ratio("H2 + O2 = H2O", "N2", "H2O")

    def test_balance_many(self):
        r = balancer.balance_many(["H2 + O2 = H2O", "N2 + H2 = NH3", "мусор"])
        self.assertEqual(len(r.value), 3)
        self.assertEqual(r.value[0]["Проверка"], "сошлась")
        self.assertIn("ошибка", r.value[2]["Проверка"])

    def test_hydrate_reaction(self):
        """Разложение медного купороса при нагревании."""
        r = balancer.balance("CuSO4*5H2O = CuSO4 + H2O")
        self.assertEqual(r.meta["left"]["CuSO4*5H2O"], 1)
        self.assertEqual(r.meta["right"]["H2O"], 5)


class TestThermoReactions(unittest.TestCase):
    """Термохимия реакций."""

    def test_water_formation_enthalpy(self):
        """2H2 + O2 = 2H2O(ж): ΔH = −571.66 кДж/моль."""
        r = thermo.reaction_enthalpy("H2 + O2 = H2O(ж)")
        self.assertAlmostEqual(r.numeric(), -571.66, places=1)

    def test_water_formation_gas(self):
        """2H2 + O2 = 2H2O(г): ΔH = −483.65 кДж/моль."""
        r = thermo.reaction_enthalpy("H2 + O2 = H2O(г)")
        self.assertAlmostEqual(r.numeric(), -483.65, places=1)

    def test_haber_enthalpy(self):
        """N2 + 3H2 = 2NH3: ΔH = −91.88 кДж/моль."""
        r = thermo.reaction_enthalpy("N2 + H2 = NH3(г)")
        self.assertAlmostEqual(r.numeric(), -91.88, places=1)

    def test_methane_combustion(self):
        """CH4 + 2O2 = CO2 + 2H2O(ж): ΔH = −890.36 кДж/моль."""
        r = thermo.reaction_enthalpy("CH4 + O2 = CO2 + H2O(ж)")
        self.assertAlmostEqual(r.numeric(), -890.36, places=1)

    def test_exothermic_label(self):
        r = thermo.reaction_enthalpy("H2 + O2 = H2O(ж)")
        self.assertEqual(r.meta["thermal_effect"], "экзотермическая")

    def test_endothermic_reaction(self):
        """Разложение карбоната кальция эндотермично."""
        r = thermo.reaction_enthalpy("CaCO3(тв) = CaO(тв) + CO2")
        self.assertGreater(r.numeric(), 0)
        self.assertEqual(r.meta["thermal_effect"], "эндотермическая")
        self.assertAlmostEqual(r.numeric(), 178.3, places=1)

    def test_entropy_increases_with_gas(self):
        """Выделение газа увеличивает энтропию."""
        r = thermo.reaction_entropy("CaCO3(тв) = CaO(тв) + CO2")
        self.assertGreater(r.numeric(), 0)

    def test_gibbs_calcium_carbonate(self):
        """Разложение CaCO3 при 298 К термодинамически запрещено."""
        r = thermo.reaction_gibbs("CaCO3(тв) = CaO(тв) + CO2")
        self.assertGreater(r.numeric(), 0)
        self.assertEqual(r.meta["spontaneity"], "несамопроизвольная")

    def test_equilibrium_temperature_calcite(self):
        """T равновесия для разложения кальцита ≈ 1100 К."""
        r = thermo.equilibrium_temperature("CaCO3(тв) = CaO(тв) + CO2")
        self.assertIsNotNone(r.value)
        self.assertTrue(800 < r.value < 1400)

    def test_equilibrium_temperature_ammonia(self):
        """Синтез аммиака: ΔH < 0 и ΔS < 0.

        Температура равновесия ≈ 464 К. Поскольку ΔS < 0, прямая реакция
        идёт НИЖЕ этой температуры — потому промышленный синтез и ведут
        при умеренной температуре под давлением.
        """
        r = thermo.equilibrium_temperature("N2 + H2 = NH3(г)")
        self.assertIsNotNone(r.value)
        self.assertAlmostEqual(r.value, 463.8, places=0)
        self.assertFalse(r.meta["forward_above"])

    def test_equilibrium_temperature_calcite_direction(self):
        """У кальцита ΔS > 0, значит прямая реакция идёт ВЫШЕ T равновесия."""
        r = thermo.equilibrium_temperature("CaCO3(тв) = CaO(тв) + CO2")
        self.assertTrue(r.meta["forward_above"])

    def test_equilibrium_temperature_opposite_signs_rejected(self):
        """ΔH > 0 при ΔS < 0 — знак ΔG не меняется ни при какой температуре."""
        from unittest.mock import patch

        # Обратный синтез аммиака даёт ΔH > 0 и ΔS > 0, поэтому берём
        # искусственный случай: подменяем справочные значения
        with patch.object(thermo, "reaction_enthalpy") as h, \
             patch.object(thermo, "reaction_entropy") as s:
            h.return_value = thermo.Result(value=50.0, unit="кДж/моль")
            s.return_value = thermo.Result(value=-100.0, unit="Дж/(моль·К)")
            r = thermo.equilibrium_temperature("H2 + O2 = H2O(ж)")
        self.assertIsNone(r.value)
        self.assertTrue(r.has_warnings)

    def test_gibbs_temperature_dependence(self):
        """ΔG разложения кальцита падает с ростом температуры."""
        g_low = thermo.reaction_gibbs("CaCO3(тв) = CaO(тв) + CO2", 400).numeric()
        g_high = thermo.reaction_gibbs("CaCO3(тв) = CaO(тв) + CO2", 1200).numeric()
        self.assertGreater(g_low, g_high)

    def test_missing_data_raises(self):
        """Нет данных в справочнике — расчёт должен отказать, а не выдумать числа."""
        # H2O2(ж) есть в базе, а вот пероксодисерная кислота — нет
        with self.assertRaises((ThermoError, ValueError)):
            thermo.reaction_enthalpy("H2S2O8 = H2SO4 + H2O2")

    def test_ionic_reaction_enthalpy(self):
        """Нейтрализация сильной кислоты щёлочью: ΔH ≈ −57.3 кДж/моль.

        Это классический результат: теплота нейтрализации сильных кислот
        и оснований практически постоянна, потому что сводится к H+ + OH- = H2O.
        """
        r = thermo.reaction_enthalpy("H^+ + OH^- = H2O(ж)")
        self.assertAlmostEqual(r.numeric(), -55.8, places=0)

    # ---------------- закон Кирхгофа ----------------

    def test_reaction_cp(self):
        r = thermo.reaction_cp("N2 + H2 = NH3(г)")
        self.assertIsInstance(r.numeric(), float)

    def test_kirchhoff_differs_from_constant_dH(self):
        """С учётом ΔCp результат при 800 К отличается от простой формулы."""
        plain = thermo.reaction_gibbs("N2 + H2 = NH3(г)", 800).numeric()
        kirch = thermo.kirchhoff("N2 + H2 = NH3(г)", 800).numeric()
        self.assertNotAlmostEqual(plain, kirch, places=1)

    def test_kirchhoff_at_reference_temperature(self):
        """При T = T₀ закон Кирхгофа даёт то же, что обычная формула.

        Значения приходят из двух независимых источников: компактного
        справочника и полиномов NASA. Они сходятся до тысячных, но не
        совпадают побитово, поэтому сравнение с допуском.
        """
        kirch = thermo.kirchhoff("N2 + H2 = NH3(г)", thermo.T0).numeric()
        plain = thermo.reaction_gibbs("N2 + H2 = NH3(г)", thermo.T0).numeric()
        self.assertAlmostEqual(kirch, plain, places=2)
        self.assertLess(abs(kirch - plain), 0.05)

    def test_kirchhoff_wide_range_is_accurate(self):
        """При полиномах Cp(T) широкий интервал не требует предупреждения.

        Раньше здесь стояло предупреждение о постоянной ΔCp. Теперь
        теплоёмкость интегрируется по температуре, поэтому 1500 К
        считается точно и предупреждать не о чем.
        """
        r = thermo.kirchhoff("N2 + H2 = NH3(г)", 1500)
        self.assertEqual(r.meta.get("method"), "polynomial")
        self.assertFalse(r.has_warnings)

    def test_kirchhoff_outside_data_range_refused(self):
        """За верхней границей полиномов расчёт не выполняется."""
        with self.assertRaises(DomainError):
            thermo.kirchhoff("N2 + H2 = NH3(г)", 9000)

    def test_kirchhoff_negative_temperature(self):
        with self.assertRaises(DomainError):
            thermo.kirchhoff("N2 + H2 = NH3(г)", -10)

    def test_cp_missing_raises(self):
        """Реакция с ионами без Cp не должна считаться по Кирхгофу."""
        with self.assertRaises((ThermoError, ValueError)):
            thermo.reaction_cp("Cu^2+ + Zn = Zn^2+ + Cu")

    # ---------------- константа равновесия ----------------

    def test_equilibrium_constant_from_dG(self):
        """ΔG = 0 даёт K = 1."""
        r = thermo.equilibrium_constant(0.0, 298.15)
        self.assertAlmostEqual(r.numeric(), 1.0, places=6)

    def test_equilibrium_constant_negative_dG(self):
        r = thermo.equilibrium_constant(-20.0, 298.15)
        self.assertGreater(r.numeric(), 1)

    def test_equilibrium_constant_positive_dG(self):
        r = thermo.equilibrium_constant(20.0, 298.15)
        self.assertLess(r.numeric(), 1)

    def test_dG_roundtrip(self):
        """K -> ΔG -> K должно возвращать исходное значение."""
        K = 1.5e5
        dg = thermo.dG_from_equilibrium_constant(K, 350).numeric()
        back = thermo.equilibrium_constant(dg, 350).numeric()
        self.assertAlmostEqual(back, K, places=3)

    def test_dG_from_K_invalid(self):
        with self.assertRaises(DomainError):
            thermo.dG_from_equilibrium_constant(0.0)
        with self.assertRaises(DomainError):
            thermo.dG_from_equilibrium_constant(-5.0)

    def test_equilibrium_constant_from_reaction(self):
        r = thermo.equilibrium_constant_from_reaction("N2 + H2 = NH3(г)", 298.15)
        # Для синтеза аммиака при 298 К K велика
        self.assertGreater(r.numeric(), 1e4)

    def test_huge_exponent_warns(self):
        """При экстремальной ΔG показатель степени теряет смысл — нужно предупредить."""
        r = thermo.equilibrium_constant(-2500.0, 298.15)
        self.assertTrue(r.has_warnings)

    def test_tiny_exponent_warns(self):
        r = thermo.equilibrium_constant(2500.0, 298.15)
        self.assertTrue(r.has_warnings)

    # ---------------- ЭДС и энергия Гиббса ----------------

    def test_dG_from_emf(self):
        """ΔG = −nFE. Для E = 1.10 В, n = 2: −212.27 кДж/моль."""
        r = thermo.dG_from_emf(1.10, 2)
        self.assertAlmostEqual(r.numeric(), -212.27, places=1)

    def test_emf_from_dG_roundtrip(self):
        emf = 1.234
        dg = thermo.dG_from_emf(emf, 3).numeric()
        back = thermo.emf_from_dG(dg, 3).numeric()
        self.assertAlmostEqual(back, emf, places=9)

    def test_dG_from_emf_invalid_n(self):
        with self.assertRaises(DomainError):
            thermo.dG_from_emf(1.0, 0)

    # ---------------- калориметрия ----------------

    def test_calorimetry_basic(self):
        """100 г воды, c = 4.18, ΔT = 10 К даёт 4180 Дж."""
        r = thermo.calorimetry(100.0, 4.18, 10.0)
        self.assertAlmostEqual(r.numeric(), 4180.0, places=1)

    def test_calorimetry_with_vessel(self):
        r = thermo.calorimetry(100.0, 4.18, 10.0, heat_capacity_calorimeter=50.0)
        self.assertAlmostEqual(r.numeric(), 4180.0 + 500.0, places=1)

    def test_calorimetry_negative_dT(self):
        r = thermo.calorimetry(100.0, 4.18, -10.0)
        self.assertLess(r.numeric(), 0)

    def test_calorimetry_invalid_mass(self):
        with self.assertRaises(DomainError):
            thermo.calorimetry(-5.0, 4.18, 10.0)

    def test_molar_heat_of_reaction(self):
        """Выделилось 5000 Дж на 0.1 моль — значит ΔH = −50 кДж/моль."""
        r = thermo.molar_heat_of_reaction(5000.0, 0.1)
        self.assertAlmostEqual(r.numeric(), -50.0, places=3)

    def test_hess_law(self):
        r = thermo.hess_law([(-393.51, 1), (-285.83, 1), (-393.51, -1)])
        self.assertAlmostEqual(r.numeric(), -285.83, places=2)

    def test_hess_law_empty(self):
        with self.assertRaises(InputError):
            thermo.hess_law([])

    def test_bond_energy(self):
        """Разорвать 1 моль H–H (436) и полмоля O=O (498/2), образовать 2 O–H (463×2)."""
        r = thermo.bond_energy_estimate([436.0, 249.0], [2 * 463.0])
        self.assertAlmostEqual(r.numeric(), -241.0, places=1)
        self.assertTrue(r.assumptions)

    # ---------------- графики и сравнение ----------------

    def test_gibbs_vs_temperature(self):
        r = thermo.gibbs_vs_temperature("CaCO3(тв) = CaO(тв) + CO2",
                                        t_min=300, t_max=1400, points=30)
        self.assertEqual(len(r.value), 30)
        self.assertIn("equilibrium_temperatures", r.meta)
        self.assertTrue(r.meta["equilibrium_temperatures"])

    def test_gibbs_vs_temperature_no_crossing(self):
        r = thermo.gibbs_vs_temperature("H2 + O2 = H2O(ж)", t_min=300, t_max=400,
                                        points=10)
        self.assertFalse(r.meta.get("equilibrium_temperatures"))

    def test_gibbs_vs_temperature_invalid_range(self):
        with self.assertRaises(DomainError):
            thermo.gibbs_vs_temperature("H2 + O2 = H2O(ж)", t_min=500, t_max=400)

    def test_compare_reactions(self):
        r = thermo.compare_reactions([
            "CaCO3(тв) = CaO(тв) + CO2",
            "H2 + O2 = H2O(ж)",
        ])
        self.assertEqual(len(r.value), 2)
        self.assertEqual(r.value[0]["Направление"], "обратное")
        self.assertEqual(r.value[1]["Направление"], "прямое")

    def test_compare_reactions_with_error(self):
        r = thermo.compare_reactions(["Xx + O2 = XxO", "H2 + O2 = H2O(ж)"])
        self.assertIn("ошибка", r.value[0]["Направление"])
        self.assertEqual(r.value[1]["Направление"], "прямое")

    # ---------------- согласованность со справочником ЭДС ----------------

    def test_emf_consistency_with_electrode_table(self):
        """Проверка сходимости: ЭДС элемента из ΔG°f должна совпасть с таблицей.

        Реакция Zn + Cu^2+ = Zn^2+ + Cu имеет табличную ЭДС 1.1037 В
        (E°(Cu2+/Cu) − E°(Zn2+/Zn) = 0.3419 − (−0.7618)).
        """
        from alchemy.data import electrodes
        r = thermo.reaction_gibbs("Zn(тв) + Cu^2+ = Zn^2+ + Cu(тв)", 298.15)
        emf_calc = thermo.emf_from_dG(r.numeric(), 2).numeric()

        cu = electrodes.find("Cu2+/Cu").E0
        zn = electrodes.find("Zn2+/Zn").E0
        emf_table = cu - zn

        # Справочные данные разных источников сходятся в пределах 0.15 В
        self.assertLess(abs(emf_calc - emf_table), 0.15,
                        f"расчёт {emf_calc:.3f} В против таблицы {emf_table:.3f} В")


if __name__ == "__main__":
    unittest.main(verbosity=2)
