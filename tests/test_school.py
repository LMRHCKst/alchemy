# -*- coding: utf-8 -*-
"""Тесты школьных движков: степени окисления, баланс, строение, равновесие,
жёсткость, качественные реакции, классы веществ.

Проверяются не «функция не упала», а конкретные числа и формулировки,
которые должен давать школьный курс.
"""

from __future__ import annotations

import unittest

from alchemy.core.errors import AlchemyError, DataNotFoundError, InputError
from alchemy.engines import bonding as B
from alchemy.engines import classification as CL
from alchemy.engines import equilibrium as EQ
from alchemy.engines import hardness as H
from alchemy.engines import oxidation as OX
from alchemy.engines import qualitative as Q
from alchemy.engines import redox as RX


class TestOxidationStates(unittest.TestCase):
    """Степени окисления."""

    def states(self, formula):
        return OX.oxidation_states(formula).meta["states"]

    def test_water(self):
        self.assertEqual(self.states("H2O"), {"H": 1.0, "O": -2.0})

    def test_sulfuric_acid(self):
        self.assertEqual(self.states("H2SO4")["S"], 6.0)

    def test_permanganate(self):
        self.assertEqual(self.states("KMnO4")["Mn"], 7.0)

    def test_dichromate(self):
        self.assertEqual(self.states("K2Cr2O7")["Cr"], 6.0)

    def test_peroxide_exception(self):
        self.assertEqual(self.states("Na2O2")["O"], -1.0)

    def test_oxygen_difluoride(self):
        """В OF2 кислород положителен, фтор всегда −1."""
        states = self.states("OF2")
        self.assertEqual(states["O"], 2.0)
        self.assertEqual(states["F"], -1.0)

    def test_ammonia(self):
        self.assertEqual(self.states("NH3")["N"], -3.0)

    def test_salt_with_radical(self):
        """CuSO4: медь +2, сера +6 — через кислотный остаток."""
        states = self.states("CuSO4")
        self.assertEqual(states["Cu"], 2.0)
        self.assertEqual(states["S"], 6.0)

    def test_aluminium_sulfate(self):
        states = self.states("Al2(SO4)3")
        self.assertEqual(states["Al"], 3.0)
        self.assertEqual(states["S"], 6.0)

    def test_simple_substance_is_zero(self):
        self.assertEqual(OX.oxidation_states("Cl2").numeric(), 0.0)

    def test_unknown_raises(self):
        """Два неизвестных элемента сразу — честный отказ."""
        with self.assertRaises(AlchemyError):
            OX.oxidation_states("CuS")

    def test_empty_raises(self):
        with self.assertRaises(InputError):
            OX.oxidation_states("")

    def test_sum_equals_charge(self):
        """Сумма степеней окисления равна заряду частицы."""
        for formula in ("H2O", "KMnO4", "CaCO3", "Fe2(SO4)3"):
            result = OX.oxidation_states(formula)
            states = result.meta["states"]
            from alchemy.core import formula as F

            composition = F.parse(formula)
            total = sum(states[el] * composition.counts[el]
                        for el in composition.elements)
            self.assertAlmostEqual(total, composition.charge, places=6)


class TestReactionType(unittest.TestCase):
    """Классификация реакций."""

    def test_connection(self):
        result = OX.reaction_type("2H2 + O2 = 2H2O")
        self.assertEqual(result.meta["reaction_kind"], "connection")

    def test_decomposition(self):
        result = OX.reaction_type("CaCO3 = CaO + CO2")
        self.assertEqual(result.meta["reaction_kind"], "decomposition")

    def test_substitution(self):
        result = OX.reaction_type("Zn + CuSO4 = ZnSO4 + Cu")
        self.assertEqual(result.meta["reaction_kind"], "substitution")

    def test_exchange(self):
        result = OX.reaction_type("NaOH + HCl = NaCl + H2O")
        self.assertEqual(result.meta["reaction_kind"], "exchange")

    def test_russian_name_shown(self):
        self.assertEqual(OX.reaction_type("2H2 + O2 = 2H2O").value,
                         "Соединение")


class TestOxidizerReducer(unittest.TestCase):
    """Окислитель и восстановитель."""

    def test_permanganate_chloride(self):
        result = OX.oxidizer_reducer(
            "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O")
        self.assertIn("Mn", result.meta["oxidizers"])
        self.assertIn("Cl", result.meta["reducers"])

    def test_not_redox(self):
        with self.assertRaises(AlchemyError):
            OX.oxidizer_reducer("NaOH + HCl = NaCl + H2O")


class TestElectronBalance(unittest.TestCase):
    """Метод электронного баланса."""

    def test_permanganate(self):
        result = RX.electron_balance(
            "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O")
        self.assertIn("2KMnO4", result.meta["balanced"])
        self.assertIn("16HCl", result.meta["balanced"])
        self.assertEqual(result.meta["electrons_given"], 10)
        self.assertEqual(result.meta["electrons_taken"], 10)

    def test_iron_oxidation(self):
        result = RX.electron_balance("Fe + O2 + H2O = Fe(OH)3")
        self.assertIn("4Fe", result.meta["balanced"])
        self.assertIn("3O2", result.meta["balanced"])

    def test_electrons_match(self):
        for equation in ("Zn + H2SO4 = ZnSO4 + H2S + H2O",
                         "Mn + HNO3 = Mn(NO3)2 + N2O + H2O"):
            result = RX.electron_balance(equation)
            self.assertEqual(result.meta["electrons_given"],
                             result.meta["electrons_taken"])

    def test_not_redox_raises(self):
        with self.assertRaises(AlchemyError):
            RX.electron_balance("NaOH + HCl = NaCl + H2O")

    def test_half_reactions_table(self):
        result = RX.half_reactions_table()
        self.assertGreater(len(result.value), 10)
        names = [row["Полуреакция"] for row in result.value]
        self.assertTrue(any("MnO4" in name for name in names))


class TestBonding(unittest.TestCase):
    """Химическая связь и решётки."""

    def test_ionic(self):
        self.assertEqual(B.bond_analysis("NaCl").meta["bond_kind"], "ионная")

    def test_polar_covalent(self):
        self.assertEqual(B.bond_analysis("H2O").meta["bond_kind"],
                         "ковалентная полярная")

    def test_nonpolar_covalent(self):
        self.assertEqual(B.bond_analysis("H2").meta["bond_kind"],
                         "ковалентная неполярная")

    def test_metal(self):
        self.assertEqual(B.bond_analysis("Fe").meta["bond_kind"],
                         "металлическая")

    def test_lattice_ionic(self):
        self.assertEqual(B.crystal_lattice("NaCl").meta["lattice"], "ионная")

    def test_lattice_atomic(self):
        for formula in ("C", "SiO2"):
            self.assertEqual(B.crystal_lattice(formula).meta["lattice"],
                             "атомная")

    def test_lattice_molecular(self):
        for formula in ("H2O", "CO2", "O2"):
            self.assertEqual(B.crystal_lattice(formula).meta["lattice"],
                             "молекулярная")

    def test_lattice_metal(self):
        self.assertEqual(B.crystal_lattice("Cu").meta["lattice"],
                         "металлическая")

    def test_overviews(self):
        self.assertGreaterEqual(len(B.bond_overview().value), 5)
        self.assertEqual(len(B.lattice_overview().value), 4)


class TestEquilibriumShift(unittest.TestCase):
    """Принцип Ле Шателье."""

    def test_gas_moles(self):
        self.assertEqual(EQ.gas_moles("N2 + 3H2 = 2NH3"), (4, 2))

    def test_gas_moles_with_states(self):
        self.assertEqual(EQ.gas_moles("CaCO3(тв) = CaO(тв) + CO2(г)"), (0, 1))

    def test_ammonia_exothermic(self):
        """Синтез аммиака экзотермичен: нагрев смещает влево."""
        result = EQ.equilibrium_shift("N2 + 3H2 = 2NH3")
        table = {row["Фактор"]: row["Смещение"] for row in result.value}
        self.assertIn("влево", table["Повышение температуры"])
        self.assertIn("вправо", table["Понижение температуры"])

    def test_pressure_towards_fewer_moles(self):
        result = EQ.equilibrium_shift("N2 + 3H2 = 2NH3")
        table = {row["Фактор"]: row["Смещение"] for row in result.value}
        self.assertIn("вправо", table["Повышение давления"])

    def test_equal_gas_moles_no_shift(self):
        result = EQ.equilibrium_shift("H2 + Cl2 = 2HCl")
        shifts = [row["Смещение"] for row in result.value]
        self.assertIn("не смещается", shifts)

    def test_concentration(self):
        result = EQ.equilibrium_shift("N2 + 3H2 = 2NH3")
        table = {row["Фактор"]: row["Смещение"] for row in result.value}
        self.assertIn("вправо", table["Больше исходных веществ"])
        self.assertIn("влево", table["Больше продуктов"])


class TestHardness(unittest.TestCase):
    """Жёсткость воды."""

    def test_one_degree_calcium(self):
        """1 °Ж — это 20.04 мг Ca²⁺ на литр."""
        result = H.water_hardness(20.039, 0.0)
        self.assertAlmostEqual(result.meta["total_degrees"], 1.0, places=3)

    def test_one_degree_magnesium(self):
        result = H.water_hardness(0.0, 12.1525)
        self.assertAlmostEqual(result.meta["total_degrees"], 1.0, places=3)

    def test_additivity(self):
        result = H.water_hardness(20.039, 12.1525)
        self.assertAlmostEqual(result.meta["total_degrees"], 2.0, places=3)

    def test_carbonate_split(self):
        """Карбонатная жёсткость ограничена содержанием гидрокарбоната."""
        result = H.water_hardness(80.0, 24.0, 122.0, 1.0)
        self.assertLessEqual(result.meta["carbonate"],
                             result.meta["total_degrees"] + 1e-9)

    def test_classification(self):
        self.assertEqual(H.water_hardness(10.0, 0.0).meta["classification"],
                         "очень мягкая")
        self.assertEqual(H.water_hardness(400.0, 0.0).meta["classification"],
                         "очень жёсткая")

    def test_negative_raises(self):
        with self.assertRaises(InputError):
            H.water_hardness(-5.0, 0.0)

    def test_salt_conversion(self):
        """162.11 мг/л Ca(HCO3)2 — это 1 ммоль/л, то есть 2 мг-экв, 2 °Ж."""
        result = H.hardness_from_salts("Ca(HCO3)2", 162.11)
        self.assertAlmostEqual(result.numeric(), 2.0, places=2)

    def test_unknown_salt(self):
        with self.assertRaises(InputError):
            H.hardness_from_salts("NaCl", 100.0)

    def test_scale_table(self):
        self.assertEqual(len(H.hardness_scale_table().value), 5)


class TestQualitative(unittest.TestCase):
    """Качественные реакции на ионы."""

    def test_all_ions(self):
        result = Q.ions_list()
        self.assertGreater(len(result.value), 20)

    def test_sulfate(self):
        result = Q.ion_reactions("SO4^2-")
        reagents = [row["Реагент"] for row in result.value]
        self.assertTrue(any("бария" in reagent for reagent in reagents))

    def test_ion_by_simplified_notation(self):
        """SO4-2 и SO4^2- должны означать одно и то же."""
        first = Q.ion_reactions("SO4^2-").meta["ion"]
        second = Q.ion_reactions("SO4-2").meta["ion"]
        self.assertEqual(first, second)

    def test_silver_nitrate(self):
        result = Q.by_reagent("AgNO3")
        self.assertGreaterEqual(result.meta["count"], 3)

    def test_by_effect(self):
        result = Q.by_effect("бурый осадок")
        ions = [row["Ион"] for row in result.value]
        self.assertIn("Fe3+", ions)

    def test_identify_warns_about_similar(self):
        """Хлорид и бромид с нитратом серебра дают похожий осадок."""
        result = Q.identify_ion("Cl-")
        self.assertTrue(result.warnings)

    def test_unknown_ion(self):
        with self.assertRaises(DataNotFoundError):
            Q.ion_reactions("Xx+")


class TestClassification(unittest.TestCase):
    """Классы веществ и названия."""

    def test_basic_oxide(self):
        self.assertEqual(CL.classify("CaO").meta["class_key"], "basic_oxide")

    def test_acidic_oxide(self):
        self.assertEqual(CL.classify("CO2").meta["class_key"], "acidic_oxide")

    def test_amphoteric_oxide(self):
        self.assertEqual(CL.classify("Al2O3").meta["class_key"],
                         "amphoteric_oxide")

    def test_non_salt_oxide(self):
        self.assertEqual(CL.classify("CO").meta["class_key"],
                         "non_salt_oxide")

    def test_base(self):
        self.assertEqual(CL.classify("NaOH").meta["class_key"], "base")

    def test_insoluble_base(self):
        self.assertEqual(CL.classify("Cu(OH)2").meta["class_key"],
                         "insoluble_base")

    def test_acid(self):
        self.assertEqual(CL.classify("H2SO4").meta["class_key"], "acid")

    def test_salt_with_parentheses(self):
        """Fe2(SO4)3 — соль, остаток SO4."""
        result = CL.classify("Fe2(SO4)3")
        self.assertEqual(result.meta["class_key"], "salt")

    def test_names(self):
        expected = {
            "CaO": "оксид кальция",
            "CO2": "оксид углерода(IV)",
            "NaOH": "гидроксид натрия",
            "Cu(OH)2": "гидроксид меди(II)",
            "H2SO4": "серная кислота",
            "NaCl": "хлорид натрия",
            "CuSO4": "сульфат меди(II)",
            "Fe2(SO4)3": "сульфат железа(III)",
            "CaCO3": "карбонат кальция",
            "NH4NO3": "нитрат аммония",
        }
        for formula, name in expected.items():
            self.assertEqual(CL.name_of(formula).value, name,
                             f"неверное название для {formula}")

    def test_genetic_link(self):
        self.assertTrue(CL.genetic_link("CaO", "Ca(OH)2").meta["possible"])
        self.assertTrue(CL.genetic_link("Ca", "CaO").meta["possible"])

    def test_classes_table(self):
        self.assertEqual(len(CL.classes_table().value), 7)

    def test_metal_detection_handles_yo(self):
        """Категория «Щёлочноземельный металл» пишется через ё."""
        self.assertTrue(CL.is_metal("Ca"))
        self.assertTrue(CL.is_metal("Na"))
        self.assertFalse(CL.is_metal("O"))


if __name__ == "__main__":
    unittest.main()
