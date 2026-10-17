# -*- coding: utf-8 -*-
"""Тесты справочных данных: целостность, физический смысл, соответствие источникам."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alchemy.data import acids, electrodes, loader, solubility, thermo
from alchemy.core.errors import DataNotFoundError


class TestDataIntegrity(unittest.TestCase):
    """Целостность справочников."""

    def test_all_files_present(self):
        files = loader.available_files()
        for expected in ("elements.json", "thermo.json", "electrodes.json",
                         "acids.json", "solubility.json", "solvents.json"):
            with self.subTest(file=expected):
                self.assertIn(expected, files)

    def test_every_file_has_source(self):
        """У каждого справочника обязан быть указан источник."""
        for f in loader.available_files():
            with self.subTest(file=f):
                self.assertTrue(loader.source_of(f).strip())

    def test_stats_nonzero(self):
        s = loader.stats()
        for key, value in s.items():
            with self.subTest(entry=key):
                self.assertGreater(value, 0, f"{key} пуст")


class TestThermoData(unittest.TestCase):
    """Термохимический справочник."""

    def test_find_by_key(self):
        water = thermo.find("H2O(ж)")
        self.assertEqual(water.state, "l")
        self.assertAlmostEqual(water.dHf, -285.83, places=1)

    def test_find_by_formula(self):
        """Формула без состояния: если вариант один, он и возвращается."""
        co2 = thermo.find("CO2")
        self.assertAlmostEqual(co2.dHf, -393.51, places=1)

    def test_ambiguous_state_raises(self):
        """У воды три состояния — программа обязана потребовать уточнения."""
        with self.assertRaises(DataNotFoundError):
            thermo.find("H2O")

    def test_state_disambiguation(self):
        gas = thermo.find("H2O", state="g")
        liquid = thermo.find("H2O", state="l")
        self.assertGreater(gas.dHf, liquid.dHf)  # пар менее устойчив

    def test_formation_of_elements_is_zero(self):
        """У простых веществ в стандартном состоянии ΔH°f = 0."""
        for key in ("O2", "N2", "H2", "Cl2", "Fe", "Al"):
            with self.subTest(substance=key):
                self.assertAlmostEqual(thermo.find(key).dHf, 0.0, places=6)

    def test_entropy_of_gas_exceeds_liquid(self):
        """Энтропия газа всегда больше энтропии жидкости того же вещества."""
        self.assertGreater(thermo.find("H2O(г)").S, thermo.find("H2O(ж)").S)

    def test_ions(self):
        h_plus = thermo.find_ion("H+")
        self.assertEqual(h_plus.dHf, 0.0)   # шкала привязана к H+
        self.assertAlmostEqual(thermo.find_ion("OH-").dGf, -157.244, places=3)

    def test_states_of(self):
        states = thermo.states_of("H2O")
        self.assertEqual(len(states), 3)

    def test_search(self):
        hits = thermo.search("серн")
        self.assertTrue(hits)
        self.assertTrue(any("серн" in s.name.lower() for s in hits))

    def test_phase_transitions(self):
        water = thermo.transition("H2O")
        self.assertAlmostEqual(water.T_кип, 373.15, places=2)
        self.assertAlmostEqual(water.dH_исп, 40.66, places=2)

    def test_molar_masses_consistent_with_formula(self):
        """Молярная масса в справочнике должна сходиться с расчётом по формуле."""
        from alchemy.core import formula
        checked = 0
        for sub in thermo.all_substances():
            if sub.M is None:
                continue
            # Ключ может содержать обозначение состояния — его надо отделить
            body, _ = formula.split_state(sub.key)
            try:
                calc = formula.molar_mass(body)
            except Exception:
                continue
            if abs(calc - sub.M) / sub.M < 0.01:
                checked += 1
            else:
                self.fail(
                    f"{sub.key}: в справочнике M = {sub.M}, "
                    f"по формуле {calc:.3f}"
                )
        self.assertGreater(checked, 30)

    def test_water_formation_enthalpy_consistency(self):
        """ΔH реакции 2H2 + O2 = 2H2O(ж) должна быть −571.66 кДж."""
        h2 = thermo.find("H2").dHf
        o2 = thermo.find("O2").dHf
        water = thermo.find("H2O(ж)").dHf
        dh = 2 * water - (2 * h2 + o2)
        self.assertAlmostEqual(dh, -571.66, places=1)


class TestElectrodeData(unittest.TestCase):
    """Электродные потенциалы."""

    def test_counts(self):
        self.assertGreater(electrodes.count(), 30)

    def test_sorted_descending(self):
        values = [e.E0 for e in electrodes.all_electrodes()]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_hydrogen_reference_is_zero(self):
        h = electrodes.find("H+/H2")
        self.assertEqual(h.E0, 0.0)
        self.assertEqual(h.n, 2)

    def test_known_values(self):
        """Сверка с табличными значениями CRC."""
        expected = {
            "Li+/Li": -3.0401,
            "K+/K": -2.931,
            "Zn2+/Zn": -0.7618,
            "Fe2+/Fe": -0.447,
            "Cu2+/Cu": 0.3419,
            "Ag+/Ag": 0.7996,
            "Cl2/Cl-": 1.358,
            "MnO4-/Mn2+": 1.507,
            "F2/F-": 2.866,
        }
        for eid, e0 in expected.items():
            with self.subTest(electrode=eid):
                self.assertAlmostEqual(electrodes.find(eid).E0, e0, places=3)

    def test_strongest_oxidant(self):
        strongest = electrodes.strongest_oxidant()
        self.assertEqual(strongest.id, "F2/F-")

    def test_electron_counts_positive(self):
        for e in electrodes.all_electrodes():
            with self.subTest(electrode=e.id):
                self.assertGreaterEqual(e.n, 1)
                self.assertLessEqual(e.n, 8)

    def test_by_element(self):
        zinc = electrodes.by_element("Zn")
        self.assertTrue(any(e.id == "Zn2+/Zn" for e in zinc))

    def test_fluorine_is_strong_oxidant(self):
        self.assertTrue(electrodes.find("F2/F-").is_oxidant_strong)
        self.assertTrue(electrodes.find("Li+/Li").is_reductant_strong)


class TestAcidData(unittest.TestCase):
    """Кислоты и основания."""

    def test_find_acid(self):
        acetic = acids.find_acid("CH3COOH")
        self.assertAlmostEqual(acetic.pKa, 4.757, places=3)
        self.assertFalse(acetic.is_strong)

    def test_find_by_name(self):
        self.assertEqual(acids.find_acid("Уксусная").formula, "CH3COOH")

    def test_strong_acids(self):
        for name in ("HCl", "HNO3", "HClO4"):
            with self.subTest(acid=name):
                self.assertTrue(acids.find_acid(name).is_strong)

    def test_ka_from_pka(self):
        acetic = acids.find_acid("CH3COOH")
        self.assertAlmostEqual(acetic.Ka, 1.75e-5, places=7)

    def test_find_base(self):
        ammonia = acids.find_base("NH3")
        self.assertAlmostEqual(ammonia.pKb, 4.75, places=2)
        self.assertAlmostEqual(ammonia.pKa_conj, 9.25, places=2)

    def test_strong_bases(self):
        self.assertTrue(acids.find_base("NaOH").is_strong)
        self.assertTrue(acids.find_base("KOH").is_strong)
        self.assertFalse(acids.find_base("NH3").is_strong)

    def test_calcium_hydroxide_two_groups(self):
        self.assertEqual(acids.find_base("Ca(OH)2").OH, 2)

    def test_unknown_raises(self):
        with self.assertRaises(DataNotFoundError):
            acids.find_acid("H2XxO4")

    # ---------------- температурная зависимость ----------------

    def test_kw_at_25(self):
        self.assertAlmostEqual(acids.pkw_at(298.15), 14.00, places=1)

    def test_kw_decreases_with_temperature(self):
        """С ростом температуры pKw падает — вода сильнее диссоциирует."""
        self.assertLess(acids.pkw_at(373.15), acids.pkw_at(298.15))

    def test_kw_at_100c(self):
        """При 100 °C pKw ≈ 12.27, значит нейтральный pH ≈ 6.14."""
        self.assertAlmostEqual(acids.pkw_at(373.15), 12.27, places=1)
        self.assertAlmostEqual(acids.neutral_ph(373.15), 6.14, places=1)

    def test_neutral_ph_at_25(self):
        self.assertAlmostEqual(acids.neutral_ph(298.15), 7.0, places=2)

    def test_pka_temperature_shift(self):
        """pKa уксусной кислоты при 100 °C заметно отличается от табличного."""
        acetic = acids.find_acid("CH3COOH")
        self.assertNotAlmostEqual(acetic.pKa_at(373.15), acetic.pKa, places=2)

    def test_acetate_has_temperature_data(self):
        self.assertTrue(acids.find_acid("CH3COOH").has_temperature_data)

    # ---------------- индикаторы ----------------

    def test_indicators_present(self):
        self.assertGreaterEqual(len(acids.all_indicators()), 5)

    def test_phenolphthalein_transition(self):
        ph = acids.find_indicator("Фенолфталеин")
        self.assertLess(ph.transition_low, ph.transition_high)

    def test_indicator_color(self):
        ph = acids.find_indicator("Фенолфталеин")
        self.assertEqual(ph.color_at(3.0), ph.color_acid)
        self.assertEqual(ph.color_at(12.0), ph.color_base)
        self.assertTrue(ph.is_transition(9.0))

    def test_indicators_for_ph(self):
        """Для точки эквивалентности сильная кислота + сильное основание (pH 7)."""
        suitable = acids.indicators_for_ph(7.0)
        names = [i.name for i in suitable]
        self.assertTrue(any("Бромтимоловый" in n for n in names))


class TestSolubilityData(unittest.TestCase):
    """Растворимость."""

    def test_find_solid(self):
        agcl = solubility.find_solid("AgCl")
        self.assertAlmostEqual(agcl.Ksp, 1.77e-10, places=12)
        self.assertEqual(agcl.cation_n, 1)
        self.assertEqual(agcl.anion_n, 1)

    def test_find_by_name(self):
        self.assertEqual(solubility.find_solid("Сульфат бария").formula, "BaSO4")

    def test_solubility_calculation_1_1(self):
        """AgCl: S = sqrt(Ks) = 1.33e-5 моль/л."""
        agcl = solubility.find_solid("AgCl")
        self.assertAlmostEqual(agcl.solubility_pure_water(), math.sqrt(1.77e-10),
                               places=12)

    def test_solubility_calculation_2_1(self):
        """Ag2CrO4: S = (Ks/4)^(1/3)."""
        ag2cro4 = solubility.find_solid("Ag2CrO4")
        expected = (1.12e-12 / 4) ** (1 / 3)
        self.assertAlmostEqual(ag2cro4.solubility_pure_water(), expected, places=12)

    def test_solubility_calculation_3_2(self):
        """Ca3(PO4)2: S = (Ks/(27·4))^(1/5)."""
        ca3po4 = solubility.find_solid("Ca3(PO4)2")
        expected = (2.07e-33 / (27 * 4)) ** (1 / 5)
        self.assertAlmostEqual(ca3po4.solubility_pure_water(), expected, places=15)

    def test_solubility_in_grams(self):
        baso4 = solubility.find_solid("BaSO4")
        s_gl = baso4.solubility_g_per_l()
        self.assertIsNotNone(s_gl)
        # 1.05e-5 моль/л × 233.39 г/моль ≈ 2.4e-3 г/л
        self.assertLess(s_gl, 0.01)

    def test_relative_solubility_makes_sense(self):
        """AgI растворяется хуже AgCl — это классический факт аналитики."""
        agcl = solubility.find_solid("AgCl").solubility_pure_water()
        agi = solubility.find_solid("AgI").solubility_pure_water()
        self.assertLess(agi, agcl)

    def test_charge_balance_in_formulas(self):
        """Числа катионов и анионов должны обеспечивать электронейтральность."""
        from alchemy.core import formula
        for solid in solubility.all_solids():
            with self.subTest(solid=solid.formula):
                cat = formula.parse(solid.cation).charge
                an = formula.parse(solid.anion).charge
                total = solid.cation_n * cat + solid.anion_n * an
                self.assertEqual(total, 0,
                                 f"{solid.formula}: заряд не сходится ({total})")

    def test_amphoteric_present(self):
        amp = solubility.amphoteric()
        self.assertIn("Zn(OH)2", amp)
        self.assertIn("Al(OH)3", amp)


class TestSolventData(unittest.TestCase):
    """Растворители и плотность растворов."""

    def test_water_properties(self):
        water = solubility.water()
        self.assertAlmostEqual(water.M, 18.015, places=2)
        self.assertAlmostEqual(water.Kb, 0.512, places=3)
        self.assertAlmostEqual(water.Kf, 1.86, places=2)
        self.assertAlmostEqual(water.Tb, 373.15, places=2)

    def test_find_solvent_by_formula(self):
        ethanol = solubility.find_solvent("C2H5OH")
        self.assertEqual(ethanol.name, "Этанол")
        self.assertAlmostEqual(ethanol.Tb_C, 78.35, places=1)

    def test_polarity_classification(self):
        self.assertTrue(solubility.water().is_polar)
        self.assertFalse(solubility.find_solvent("Бензол").is_polar)

    def test_unknown_solvent(self):
        with self.assertRaises(DataNotFoundError):
            solubility.find_solvent("Жидкий азот")

    # ---------------- плотность растворов ----------------

    def test_density_water_zero_fraction(self):
        d = solubility.density_of_solution("NaOH", 0.0)
        self.assertAlmostEqual(d, 0.9982, places=3)

    def test_density_naoh_table_point(self):
        d = solubility.density_of_solution("NaOH", 20.0)
        self.assertAlmostEqual(d, 1.2220, places=3)

    def test_density_interpolation(self):
        """Между точками 10 % и 12 % должно быть промежуточное значение."""
        d10 = solubility.density_of_solution("NaOH", 10.0)
        d11 = solubility.density_of_solution("NaOH", 11.0)
        d12 = solubility.density_of_solution("NaOH", 12.0)
        self.assertTrue(d10 < d11 < d12)

    def test_density_out_of_range_returns_none(self):
        """Экстраполировать плотность нельзя — возвращается None."""
        self.assertIsNone(solubility.density_of_solution("NaOH", 60.0))
        self.assertIsNone(solubility.density_of_solution("NaOH", -5.0))

    def test_sulfuric_acid_nonmonotonic(self):
        """У серной кислоты максимум плотности около 98 % — это проверка
        корректности таблицы, а не гладкой подгонки."""
        d95 = solubility.density_of_solution("H2SO4", 95.0)
        d98 = solubility.density_of_solution("H2SO4", 98.0)
        d100 = solubility.density_of_solution("H2SO4", 100.0)
        self.assertGreater(d98, d95)
        self.assertGreater(d98, d100)

    def test_mass_fraction_from_density_roundtrip(self):
        """Плотность -> состав -> плотность должны сходиться."""
        d = solubility.density_of_solution("NaOH", 15.0)
        w = solubility.mass_fraction_from_density("NaOH", d)
        self.assertIsNotNone(w)
        self.assertAlmostEqual(w, 15.0, places=2)

    def test_density_temperature_correction(self):
        d20 = solubility.density_of_solution("NaCl", 10.0, temperature_c=20.0)
        d30 = solubility.density_of_solution("NaCl", 10.0, temperature_c=30.0)
        self.assertLess(d30, d20)

    def test_unknown_solute_density(self):
        self.assertIsNone(solubility.density_of_solution("XxCl", 10.0))
        self.assertFalse(solubility.has_density_table("XxCl"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
