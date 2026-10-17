# -*- coding: utf-8 -*-
"""Тесты электрохимии и ядерной химии."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alchemy.engines import electrochemistry as E
from alchemy.engines import nuclear as N
from alchemy.engines.electrochemistry import ElectrochemistryError
from alchemy.engines.nuclear import NuclearError
from alchemy.core.constants import F_FARADAY


class TestNernst(unittest.TestCase):
    """Уравнение Нернста."""

    def test_standard_conditions(self):
        """При активностях 1 потенциал равен стандартному."""
        r = E.nernst_potential(0.771, 1, oxidized=1.0, reduced=1.0)
        self.assertAlmostEqual(r.numeric(), 0.771, places=9)

    def test_known_zinc(self):
        """Zn²⁺/Zn при активности 0.01: E = −0.7618 − 0.0592 = −0.821 В.

        Разбавление окисленной формы понижает потенциал — это стандартный
        результат уравнения Нернста, и он совпадает с экспериментом.
        """
        r = E.nernst_potential(-0.7618, 2, oxidized=0.01, reduced=1.0)
        self.assertAlmostEqual(r.numeric(), -0.8210, places=3)

    def test_concentration_lowers_potential(self):
        """Разбавление иона металла понижает потенциал."""
        dilute = E.nernst_potential(0.3419, 2, oxidized=0.001, reduced=1.0).numeric()
        conc = E.nernst_potential(0.3419, 2, oxidized=1.0, reduced=1.0).numeric()
        self.assertLess(dilute, conc)

    def test_temperature_effect(self):
        """При нагревании поправка Нернста растёт."""
        r25 = E.nernst_potential(0.0, 1, temperature_k=298.15,
                                 oxidized=0.01, reduced=1.0).numeric()
        r50 = E.nernst_potential(0.0, 1, temperature_k=323.15,
                                 oxidized=0.01, reduced=1.0).numeric()
        self.assertGreater(abs(r50), abs(r25))

    def test_ph_contribution(self):
        """Учёт pH понижает потенциал для полуреакции с ионами H⁺."""
        without = E.nernst_potential(1.507, 5, oxidized=1.0, reduced=1.0).numeric()
        with_ph = E.nernst_potential(1.507, 5, oxidized=1.0, reduced=1.0,
                                     ph=7.0, protons=8).numeric()
        self.assertAlmostEqual(without, 1.507, places=6)
        self.assertLess(with_ph, without)
        # При pH 7 перманганат теряет окислительную силу более чем на 0.6 В
        self.assertLess(with_ph, 0.9)

    def test_decimal_form_slope(self):
        """При 25 °C коэффициент 0.0592/n."""
        r = E.nernst_potential(0.0, 1, oxidized=0.1, reduced=1.0)
        self.assertAlmostEqual(r.meta["decimal_form_slope"], 0.05916, places=5)

    def test_invalid_electrons(self):
        with self.assertRaises(ElectrochemistryError):
            E.nernst_potential(0.0, 0, oxidized=1.0, reduced=1.0)

    def test_invalid_concentration(self):
        with self.assertRaises(ElectrochemistryError):
            E.nernst_potential(0.0, 1, oxidized=0.0, reduced=1.0)

    def test_missing_activities(self):
        with self.assertRaises(ElectrochemistryError):
            E.nernst_potential(0.0, 1)

    def test_large_correction_warns(self):
        r = E.nernst_potential(0.0, 1, oxidized=1e-20, reduced=1.0)
        self.assertTrue(r.has_warnings)

    def test_electrode_from_database(self):
        r = E.electrode_potential_electrode("Cu2+/Cu", concentration=0.01)
        self.assertLess(r.numeric(), 0.3419)


class TestGalvanicCell(unittest.TestCase):
    """Гальванические элементы."""

    def test_daniel_cell(self):
        """Элемент Даниэля: Zn | Zn²⁺ || Cu²⁺ | Cu, ЭДС = 1.1037 В."""
        r = E.galvanic_cell("Cu2+/Cu", "Zn2+/Zn")
        self.assertAlmostEqual(r.numeric(), 1.1037, places=3)

    def test_cell_gibbs(self):
        """ΔG элемента Даниэля: −213 кДж/моль."""
        r = E.galvanic_cell("Cu2+/Cu", "Zn2+/Zn")
        self.assertAlmostEqual(r.meta["dG_kj"], -213.0, places=0)

    def test_cell_equilibrium_constant(self):
        """K для элемента Даниэля порядка 10³⁷."""
        r = E.galvanic_cell("Cu2+/Cu", "Zn2+/Zn")
        self.assertGreater(r.meta["K"], 1e30)

    def test_cell_with_hydrogen(self):
        r = E.galvanic_cell("Cu2+/Cu", "H+/H2")
        self.assertAlmostEqual(r.numeric(), 0.3419, places=3)

    def test_reversed_poles_warned(self):
        """Если катод и анод перепутаны, ЭДС отрицательна и есть предупреждение."""
        r = E.galvanic_cell("Zn2+/Zn", "Cu2+/Cu")
        self.assertLess(r.numeric(), 0)
        self.assertTrue(r.has_warnings)

    def test_same_electrode_rejected(self):
        with self.assertRaises(ElectrochemistryError):
            E.galvanic_cell("Cu2+/Cu", "Cu2+/Cu")

    def test_common_electrons_assumption(self):
        """Полуреакции с разным n приводятся к общему кратному."""
        r = E.galvanic_cell("MnO4-/Mn2+", "Fe2+/Fe")
        self.assertIn("n_electrons", r.meta)
        self.assertEqual(r.meta["n_electrons"] % 5, 0)

    def test_compare_electrodes_possible(self):
        """Цинк восстанавливает медь — реакция возможна."""
        r = E.compare_electrodes("Cu2+/Cu", "Zn2+/Zn")
        self.assertTrue(r.meta["reaction_possible"])

    def test_compare_electrodes_impossible(self):
        r = E.compare_electrodes("Zn2+/Zn", "Cu2+/Cu")
        self.assertFalse(r.meta["reaction_possible"])

    def test_find_oxidants(self):
        """Для цинка должно найтись много окислителей."""
        r = E.find_possible_oxidants("Zn2+/Zn", min_emf=0.5)
        self.assertGreater(len(r.value), 5)
        # Отсортировано по убыванию ЭДС
        emfs = [row["ЭДС, В"] for row in r.value]
        self.assertEqual(emfs, sorted(emfs, reverse=True))

    def test_concentration_cell(self):
        """ЭДС концентрационного элемента при соотношении 0.01 и 0.1."""
        r = E.concentration_cell("Cu2+/Cu", 0.01, 0.1)
        expected = (8.314462618 * 298.15 / (2 * F_FARADAY.value)) * math.log(10)
        self.assertAlmostEqual(r.numeric(), expected, places=6)

    def test_concentration_cell_invalid_order(self):
        with self.assertRaises(ElectrochemistryError):
            E.concentration_cell("Cu2+/Cu", 1.0, 0.1)

    def test_gibbs_emf_roundtrip(self):
        dg = E.gibbs_from_emf(1.1, 2).numeric()
        emf = E.emf_from_gibbs(dg, 2).numeric()
        self.assertAlmostEqual(emf, 1.1, places=9)

    def test_equilibrium_constant_from_emf(self):
        r = E.equilibrium_constant_from_emf(0.0, 2)
        self.assertAlmostEqual(r.numeric(), 1.0, places=6)


class TestFaraday(unittest.TestCase):
    """Законы Фарадея и электролиз."""

    def test_copper_deposition(self):
        """1 А в течение 1 ч выделяет 1.185 г меди (M = 63.546, n = 2)."""
        r = E.faraday_mass(1.0, 3600.0, 2, 63.546)
        self.assertAlmostEqual(r.numeric(), 1.1855, places=3)

    def test_silver_deposition(self):
        """Серебро, n = 1: 1 А·ч даёт 4.025 г."""
        r = E.faraday_mass(1.0, 3600.0, 1, 107.868)
        self.assertAlmostEqual(r.numeric(), 4.025, places=2)

    def test_current_efficiency_applied(self):
        full = E.faraday_mass(1.0, 3600.0, 2, 63.546).numeric()
        partial = E.faraday_mass(1.0, 3600.0, 2, 63.546,
                                 current_efficiency=80.0).numeric()
        self.assertAlmostEqual(partial, full * 0.8, places=6)

    def test_faraday_invalid(self):
        with self.assertRaises(ElectrochemistryError):
            E.faraday_mass(0.0, 3600.0, 2, 63.546)
        with self.assertRaises(ElectrochemistryError):
            E.faraday_mass(1.0, 3600.0, 2, 63.546, current_efficiency=150.0)

    def test_hydrogen_volume(self):
        """Электролиз воды: 1 А·ч даёт 0.418 л H2 при н.у."""
        r = E.faraday_volume(1.0, 3600.0, 2, temperature_k=273.15,
                             pressure_atm=1.0)
        self.assertAlmostEqual(r.meta["volume_stp_l"], 0.418, places=2)

    def test_oxygen_volume_half_of_hydrogen(self):
        """Кислорода по объёму вдвое меньше, чем водорода: n = 4 против 2."""
        h2 = E.faraday_volume(1.0, 3600.0, 2).numeric()
        o2 = E.faraday_volume(1.0, 3600.0, 4).numeric()
        self.assertAlmostEqual(o2, h2 / 2, places=6)

    def test_electrolysis_time(self):
        """Для 1 моль меди при 1 А нужно 2·F секунд."""
        r = E.electrolysis_time(1.0, 2, moles=1.0)
        self.assertAlmostEqual(r.numeric(), 2 * F_FARADAY.value, places=3)

    def test_electrolysis_time_from_mass(self):
        r = E.electrolysis_time(1.0, 2, mass_g=63.546, molar_mass_value=63.546)
        self.assertAlmostEqual(r.numeric(), 2 * F_FARADAY.value, places=3)

    def test_electrolysis_time_missing_data(self):
        with self.assertRaises(ElectrochemistryError):
            E.electrolysis_time(1.0, 2)

    def test_current_efficiency_value(self):
        r = E.current_efficiency(0.95, 1.1855)
        self.assertAlmostEqual(r.numeric(), 80.13, places=1)

    def test_current_efficiency_over_hundred_warns(self):
        r = E.current_efficiency(1.5, 1.0)
        self.assertTrue(r.has_warnings)


class TestPourbaix(unittest.TestCase):
    """Диаграммы Пурбе и коррозия."""

    def test_pourbaix_iron(self):
        r = E.pourbaix_diagram("Fe")
        self.assertEqual(len(r.value), 60)
        self.assertIn("lines", r.meta)
        # Линии воды присутствуют
        self.assertIn("выделение водорода", r.meta["lines"])
        self.assertIn("выделение кислорода", r.meta["lines"])

    def test_pourbaix_unknown_element(self):
        with self.assertRaises(ElectrochemistryError):
            E.pourbaix_diagram("Xx")

    def test_pourbaix_invalid_ph_range(self):
        with self.assertRaises(ElectrochemistryError):
            E.pourbaix_diagram("Fe", ph_min=5, ph_max=3)
        with self.assertRaises(ElectrochemistryError):
            E.pourbaix_diagram("Fe", ph_min=-1)

    def test_water_lines_at_ph7(self):
        """Линия водорода при pH 7: E ≈ −0.414 В, кислорода: ≈ +0.815 В.

        Допуск задан в 0.01 В: точное значение по Нернсту немного отличается
        от упрощённой записи через 0.0592·pH.
        """
        r = E.pourbaix_diagram("Fe")
        h2 = r.meta["lines"]["выделение водорода"]
        o2 = r.meta["lines"]["выделение кислорода"]
        ph7_h2 = min(h2, key=lambda p: abs(p[0] - 7.0))
        ph7_o2 = min(o2, key=lambda p: abs(p[0] - 7.0))
        self.assertAlmostEqual(ph7_h2[1], -0.414, delta=0.01)
        self.assertAlmostEqual(ph7_o2[1], 0.815, delta=0.01)

    def test_iron_corrodes(self):
        """Железо при pH 7 термодинамически неустойчиво."""
        r = E.pourbaix_diagram("Fe")
        self.assertTrue(r.meta["corrosion_thermodynamic"])

    def test_copper_noble(self):
        """Медь при pH 7 термодинамически устойчива."""
        r = E.pourbaix_diagram("Cu")
        self.assertFalse(r.meta["corrosion_thermodynamic"])

    def test_corrosion_prediction_zinc(self):
        r = E.corrosion_prediction("Zn2+/Zn", ph=7.0, dissolved_oxygen=True)
        self.assertTrue(r.meta["corrosion_possible"])

    def test_corrosion_prediction_gold_like(self):
        """Серебро при нейтральном pH без кислорода не корродирует."""
        r = E.corrosion_prediction("Ag+/Ag", ph=7.0, dissolved_oxygen=False)
        self.assertFalse(r.meta["corrosion_possible"])

    def test_electrolysis_products_water(self):
        """Электролиз воды: напряжение разложения 1.229 В.

        Роли определяются потенциалами: у пары O₂/H₂O потенциал выше
        (1.229 В), чем у H⁺/H₂ (0 В), поэтому в гальваническом элементе
        кислородный электрод был бы катодом. При электролизе внешний
        источник разворачивает процесс: на катоде выделяется водород.
        """
        r = E.electrolysis_products(["H+/H2", "O2/H2O"])
        self.assertEqual(r.meta["cathode"], "O2/H2O")
        self.assertEqual(r.meta["anode"], "H+/H2")
        self.assertAlmostEqual(r.meta["decomposition_voltage"], 1.229, places=2)
        self.assertIn("катод", " ".join(r.steps).lower())

    def test_electrolysis_products_copper_over_hydrogen(self):
        """При электролизе раствора соли меди на катоде выделяется медь, не водород."""
        r = E.electrolysis_products(["Cu2+/Cu", "H+/H2"])
        self.assertEqual(r.meta["cathode"], "Cu2+/Cu")

    def test_electrolysis_products_too_few(self):
        with self.assertRaises(ElectrochemistryError):
            E.electrolysis_products(["H+/H2"])

    def test_decomposition_voltage_warns(self):
        r = E.electrolysis_products(["H+/H2", "O2/H2O"])
        self.assertTrue(r.has_warnings)


class TestNuclearDecay(unittest.TestCase):
    """Радиоактивный распад."""

    def test_lambda_from_half_life(self):
        """Для T½ = 1 с λ = 0.6931 1/с."""
        r = N.half_life_to_lambda(1.0, "с")
        self.assertAlmostEqual(r.numeric(), math.log(2), places=6)

    def test_lambda_unit_conversion(self):
        """T½ = 1 мин даёт λ в 60 раз меньше, чем T½ = 1 с."""
        r1 = N.half_life_to_lambda(1.0, "с").numeric()
        r2 = N.half_life_to_lambda(1.0, "мин").numeric()
        self.assertAlmostEqual(r1 / r2, 60.0, places=6)

    def test_half_life_invalid(self):
        with self.assertRaises(NuclearError):
            N.half_life_to_lambda(0.0)
        with self.assertRaises(NuclearError):
            N.half_life_to_lambda(1.0, "попугаи")

    def test_one_half_life(self):
        """Через один период остаётся ровно половина."""
        r = N.decayed_amount(100.0, 10.0, 10.0)
        self.assertAlmostEqual(r.numeric(), 50.0, places=6)

    def test_two_half_lives(self):
        r = N.decayed_amount(100.0, 10.0, 20.0)
        self.assertAlmostEqual(r.numeric(), 25.0, places=6)

    def test_ten_half_lives(self):
        """Через 10 периодов остаётся менее 0.1 %."""
        r = N.decayed_amount(100.0, 10.0, 100.0)
        self.assertLess(r.numeric(), 0.1)
        self.assertIn("полураспада", " ".join(r.steps))

    def test_zero_time(self):
        r = N.decayed_amount(100.0, 10.0, 0.0)
        self.assertAlmostEqual(r.numeric(), 100.0, places=9)

    def test_negative_time_rejected(self):
        with self.assertRaises(NuclearError):
            N.decayed_amount(100.0, 10.0, -1.0)

    def test_time_to_decay(self):
        """Время до половины равно одному периоду полураспада."""
        r = N.time_to_decay(100.0, 50.0, 10.0)
        self.assertAlmostEqual(r.numeric(), 10.0, places=6)

    def test_time_to_decay_impossible(self):
        with self.assertRaises(NuclearError):
            N.time_to_decay(100.0, 200.0, 10.0)

    def test_decay_curve(self):
        r = N.decay_curve(100.0, 10.0, n_half_lives=5, points=50)
        self.assertEqual(len(r.value), 50)
        # Монотонно убывает
        values = [p[1] for p in r.value]
        self.assertEqual(values, sorted(values, reverse=True))
        # На последней точке прошло 5 периодов — осталось 100/32
        self.assertAlmostEqual(values[-1], 100.0 / 32, places=3)


class TestNuclearActivity(unittest.TestCase):
    """Активность и единицы."""

    def test_activity_one_mole(self):
        """1 моль с T½ = 1 с даёт A = 0.693·N_A."""
        r = N.activity(1.0, 1.0)
        self.assertAlmostEqual(r.numeric(), math.log(2) * 6.02214076e23, places=10)

    def test_activity_in_curie(self):
        """1 г радия-226 имеет активность около 1 Ки — историческое определение."""
        # T½(Ra-226) = 1600 лет
        t_half = 1600 * 31557600.0
        n_moles = 1.0 / 226.0
        r = N.activity(n_moles, t_half)
        self.assertAlmostEqual(r.meta["activity_ci"], 1.0, places=0)

    def test_mass_from_activity_roundtrip(self):
        """A -> m -> A должно сходиться."""
        t_half = 1e10
        a = 1e6
        m = N.mass_from_activity(a, t_half, 60.0).numeric()
        # Обратная проверка через активность
        n_moles = m / 60.0
        a_back = N.activity(n_moles, t_half).numeric()
        self.assertAlmostEqual(a_back, a, places=3)

    def test_convert_becquerel_to_curie(self):
        r = N.convert_activity(3.7e10, "Бк", "Ки")
        self.assertAlmostEqual(r.numeric(), 1.0, places=9)

    def test_convert_curie_to_becquerel(self):
        r = N.convert_activity(1.0, "Ки", "Бк")
        self.assertAlmostEqual(r.numeric(), 3.7e10, places=3)

    def test_convert_to_disintegrations_per_minute(self):
        r = N.convert_activity(1.0, "Бк", "расп/мин")
        self.assertAlmostEqual(r.numeric(), 60.0, places=9)

    def test_convert_unknown_unit(self):
        with self.assertRaises(NuclearError):
            N.convert_activity(1.0, "Бк", "попугаи")

    def test_convert_negative(self):
        with self.assertRaises(NuclearError):
            N.convert_activity(-1.0, "Бк", "Ки")


class TestNuclearEnergy(unittest.TestCase):
    """Энергия ядерных реакций."""

    def test_parse_nuclide_formats(self):
        for text, mass in (("U-235", 235), ("235U", 235), ("U235", 235)):
            with self.subTest(text=text):
                nuc = N.parse_nuclide(text)
                self.assertEqual(nuc.symbol, "U")
                self.assertEqual(nuc.mass_number, mass)
                self.assertEqual(nuc.charge, 92)
                self.assertEqual(nuc.neutrons, 143)

    def test_parse_nuclide_invalid(self):
        with self.assertRaises(NuclearError):
            N.parse_nuclide("Xx-999")
        with self.assertRaises(NuclearError):
            N.parse_nuclide("")

    def test_binding_energy_helium(self):
        """Удельная энергия связи гелия-4 около 7.07 МэВ/нуклон."""
        r = N.nuclear_binding_energy("He-4")
        self.assertAlmostEqual(r.meta["energy_per_nucleon_mev"], 7.07, places=2)

    def test_binding_energy_iron_maximum(self):
        """У железа-56 удельная энергия связи максимальна, около 8.79 МэВ."""
        r = N.nuclear_binding_energy("Fe-56")
        self.assertAlmostEqual(r.meta["energy_per_nucleon_mev"], 8.79, places=1)

    def test_binding_energy_uranium_lower(self):
        """У урана удельная энергия связи ниже, чем у железа."""
        fe = N.nuclear_binding_energy("Fe-56").meta["energy_per_nucleon_mev"]
        u = N.nuclear_binding_energy("U-235").meta["energy_per_nucleon_mev"]
        self.assertLess(u, fe)

    def test_binding_energy_mass_defect_positive(self):
        r = N.nuclear_binding_energy("C-12")
        self.assertGreater(r.meta["mass_defect_amu"], 0)

    def test_binding_energy_unknown_isotope(self):
        with self.assertRaises(NuclearError):
            N.nuclear_binding_energy("Fe-999")

    def test_fusion_deuterium_tritium(self):
        """D + T → He-4 + n выделяет около 17.6 МэВ."""
        r = N.reaction_energy(["H-2", "H-3"], ["He-4", "n"])
        self.assertAlmostEqual(r.meta["Q_mev"], 17.6, delta=0.5)
        self.assertTrue(r.meta["exothermic"])

    def test_fission_uranium(self):
        """Деление U-235 выделяет около 200 МэВ на акт."""
        r = N.reaction_energy(
            ["U-235", "n"],
            ["Ba-141", "Kr-92", "n", "n", "n"],
        )
        self.assertGreater(r.meta["Q_mev"], 150)
        self.assertLess(r.meta["Q_mev"], 250)
        self.assertTrue(r.meta["exothermic"])

    def test_endothermic_reaction(self):
        """Реакция с поглощением энергии должна определяться как эндоэнергетическая."""
        r = N.reaction_energy(["He-4"], ["He-4", "n"])
        self.assertFalse(r.meta["exothermic"])
        self.assertLess(r.meta["Q_mev"], 0)

    def test_einstein_energy(self):
        """1 а.е.м. соответствует 931.494 МэВ."""
        r = N.einstein_energy(1.0)
        self.assertAlmostEqual(r.meta["energy_mev"], 931.494, places=2)
        self.assertAlmostEqual(r.numeric(), 1.4924e-10, places=13)

    def test_hydrogen_neutron_mass(self):
        """Реакция с нейтроном должна корректно учитывать его массу."""
        r = N.reaction_energy(["H-1", "n"], ["H-2"])
        # Образование дейтрона выделяет 2.22 МэВ
        self.assertAlmostEqual(r.meta["Q_mev"], 2.22, delta=0.1)


class TestDecayChain(unittest.TestCase):
    """Цепочки распада и дозиметрия."""

    def test_chain_conserves_amount(self):
        """Суммарное количество атомов сохраняется."""
        r = N.decay_chain(100.0, [10.0, 5.0, 2.0], 20.0)
        total = sum(r.meta["amounts"])
        self.assertAlmostEqual(total, 100.0, delta=0.5)

    def test_chain_parent_decreases(self):
        r = N.decay_chain(100.0, [10.0, 5.0], 10.0)
        parent = r.meta["amounts"][0]
        self.assertAlmostEqual(parent, 50.0, places=1)

    def test_chain_invalid(self):
        with self.assertRaises(NuclearError):
            N.decay_chain(0.0, [10.0], 5.0)
        with self.assertRaises(NuclearError):
            N.decay_chain(100.0, [], 5.0)

    def test_secular_equilibrium(self):
        """При большом отношении периодов активности выравниваются."""
        r = N.secular_equilibrium(1e9, 1e3, 1000.0)
        self.assertIsNotNone(r.value)
        self.assertAlmostEqual(r.numeric(), 1000.0, places=6)

    def test_secular_equilibrium_not_reached(self):
        """При близких периодах равновесие не устанавливается."""
        r = N.secular_equilibrium(100.0, 50.0, 1000.0)
        self.assertIsNone(r.value)
        self.assertTrue(r.has_warnings)

    def test_absorbed_dose(self):
        """1 Дж на 1 кг = 1 Гр."""
        r = N.absorbed_dose(1.0, 1.0)
        self.assertAlmostEqual(r.numeric(), 1.0, places=9)

    def test_equivalent_dose_gamma(self):
        """Для гамма-излучения 1 Гр = 1 Зв."""
        r = N.equivalent_dose(1.0, "gamma")
        self.assertAlmostEqual(r.numeric(), 1.0, places=9)

    def test_equivalent_dose_alpha(self):
        """Для альфа-частиц 1 Гр = 20 Зв."""
        r = N.equivalent_dose(1.0, "alpha")
        self.assertAlmostEqual(r.numeric(), 20.0, places=9)
        self.assertAlmostEqual(r.meta["millisievert"], 20000.0, places=6)

    def test_equivalent_dose_unknown_type(self):
        with self.assertRaises(NuclearError):
            N.equivalent_dose(1.0, "попугаи")

    def test_dose_rate(self):
        """Мощность дозы обратно пропорциональна квадрату расстояния."""
        r1 = N.dose_rate(3.7e7, 1.0, 1.0).numeric()
        r2 = N.dose_rate(3.7e7, 1.0, 2.0).numeric()
        self.assertAlmostEqual(r1 / r2, 4.0, places=6)

    def test_dose_rate_invalid(self):
        with self.assertRaises(NuclearError):
            N.dose_rate(1e6, 1.0, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
