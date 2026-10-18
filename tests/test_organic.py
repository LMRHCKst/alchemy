# -*- coding: utf-8 -*-
"""Тесты органической химии: классы, сгорание, реакции.

Проверяются ответы, которые должен давать школьный курс, а не просто
«функция не упала».
"""

from __future__ import annotations

import unittest

from alchemy.core.errors import AlchemyError, DataNotFoundError, InputError
from alchemy.engines import organic as ORG


class TestClasses(unittest.TestCase):
    """Определение класса."""

    def test_alkanes(self):
        for formula in ("CH4", "C2H6", "C3H8", "C8H18"):
            self.assertEqual(ORG.class_of(formula).meta["class_key"], "alkanes")

    def test_alkenes(self):
        self.assertEqual(ORG.class_of("C2H4").meta["class_key"], "alkenes")

    def test_alkynes(self):
        self.assertEqual(ORG.class_of("C2H2").meta["class_key"], "alkynes")

    def test_arenes(self):
        self.assertEqual(ORG.class_of("C6H6").meta["class_key"], "arenes")

    def test_alcohols(self):
        self.assertEqual(ORG.class_of("C2H5OH").meta["class_key"], "alcohols")

    def test_polyols(self):
        self.assertEqual(ORG.class_of("C3H8O3").meta["class_key"], "polyols")

    def test_phenols(self):
        self.assertEqual(ORG.class_of("C6H5OH").meta["class_key"], "phenols")

    def test_aldehydes_structural(self):
        """CH3CHO содержит группу CHO — это альдегид, не кетон."""
        self.assertEqual(ORG.class_of("CH3CHO").meta["class_key"], "aldehydes")

    def test_acids_structural(self):
        """CH3COOH содержит COOH — кислота, а не сложный эфир."""
        self.assertEqual(ORG.class_of("CH3COOH").meta["class_key"], "acids")

    def test_esters_structural(self):
        self.assertEqual(ORG.class_of("CH3COOC2H5").meta["class_key"],
                         "esters")

    def test_carbohydrates(self):
        for formula in ("C6H12O6", "C12H22O11"):
            self.assertEqual(ORG.class_of(formula).meta["class_key"],
                             "carbohydrates")

    def test_aminoacids(self):
        self.assertEqual(ORG.class_of("C2H5NO2").meta["class_key"],
                         "aminoacids")

    def test_by_name(self):
        cases = {"метан": "alkanes", "этанол": "alcohols",
                 "глюкоза": "carbohydrates", "бензол": "arenes",
                 "ацетилен": "alkynes", "уксусная": "acids"}
        for name, key in cases.items():
            self.assertEqual(ORG.class_of(name).meta["class_key"], key,
                             f"неверный класс для «{name}»")

    def test_ambiguity_is_honest(self):
        """C3H6 — и пропен, и циклопропан, по формуле не различить."""
        result = ORG.class_of("C3H6")
        self.assertGreater(len(result.meta["ambiguous"]), 1)
        self.assertTrue(result.warnings)

    def test_alkane_is_not_ambiguous(self):
        self.assertEqual(len(ORG.class_of("C3H8").meta["ambiguous"]), 1)

    def test_not_organic(self):
        with self.assertRaises(AlchemyError):
            ORG.class_of("NaCl")

    def test_empty(self):
        with self.assertRaises(InputError):
            ORG.class_of("")


class TestHomologousSeries(unittest.TestCase):
    """Гомологические ряды."""

    def test_alkanes_count(self):
        result = ORG.homologous_series("Алканы")
        self.assertEqual(len(result.value), 10)

    def test_methane_mass(self):
        result = ORG.homologous_series("alkanes")
        first = result.value[0]
        self.assertEqual(first["Формула"], "CH4")
        self.assertAlmostEqual(float(first["Молярная масса"]), 16.04, places=2)

    def test_difference_is_ch2(self):
        """Каждый следующий гомолог тяжелее на 14.03 г/моль."""
        result = ORG.homologous_series("Алканы")
        masses = [float(row["Молярная масса"]) for row in result.value[:4]]
        for first, second in zip(masses, masses[1:]):
            self.assertAlmostEqual(second - first, 14.03, delta=0.02)

    def test_all_classes_have_members(self):
        for item in ORG._series():
            result = ORG.homologous_series(item["key"])
            self.assertGreater(len(result.value), 0, item["key"])

    def test_unknown_class(self):
        with self.assertRaises(DataNotFoundError):
            ORG.homologous_series("Полимеры")


class TestCombustion(unittest.TestCase):
    """Формула по продуктам сгорания."""

    def test_methane(self):
        """1.6 г метана дают 4.4 г CO2 и 3.6 г воды."""
        result = ORG.combustion_formula(1.6, co2_mass=4.4, h2o_mass=3.6)
        self.assertEqual(result.meta["empirical"], "CH4")

    def test_ethanol(self):
        """4.6 г этанола дают 8.8 г CO2 и 5.4 г воды -> C2H6O."""
        result = ORG.combustion_formula(4.6, co2_mass=8.8, h2o_mass=5.4)
        self.assertEqual(result.meta["empirical"], "C2H6O")

    def test_oxygen_by_difference(self):
        """В этаноле кислород есть, в метане нет."""
        methane = ORG.combustion_formula(1.6, co2_mass=4.4, h2o_mass=3.6)
        ethanol = ORG.combustion_formula(4.6, co2_mass=8.8, h2o_mass=5.4)
        self.assertAlmostEqual(methane.meta["oxygens"], 0.0, places=3)
        self.assertGreater(ethanol.meta["oxygens"], 0.05)

    def test_molecular_from_molar_mass(self):
        """Пропан: простейшая C3H8 при M = 44."""
        result = ORG.combustion_formula(4.4, co2_mass=13.2, h2o_mass=7.2,
                                        molar_mass=44)
        self.assertEqual(result.meta["molecular"], "C3H8")

    def test_empirical_differs_from_molecular(self):
        """Этен: простейшая CH2, молекулярная C2H4."""
        result = ORG.combustion_formula(2.8, co2_mass=8.8, h2o_mass=3.6,
                                        molar_mass=28)
        self.assertEqual(result.meta["empirical"], "CH2")
        self.assertEqual(result.meta["molecular"], "C2H4")

    def test_by_volume(self):
        """1.6 г метана дают 0.1 моль CO2, то есть 2.24 л при н.у."""
        result = ORG.combustion_formula(1.6, co2_volume=2.24, h2o_mass=3.6)
        self.assertEqual(result.meta["empirical"], "CH4")

    def test_hydrocarbon_without_oxygen(self):
        result = ORG.combustion_formula(2.6, co2_mass=8.8, h2o_mass=1.8,
                                        molar_mass=26)
        self.assertEqual(result.meta["molecular"], "C2H2")

    def test_impossible_data(self):
        """Массы продуктов не могут дать больше, чем навеска."""
        with self.assertRaises(InputError):
            ORG.combustion_formula(1.0, co2_mass=44.0, h2o_mass=18.0)

    def test_zero_sample(self):
        with self.assertRaises(InputError):
            ORG.combustion_formula(0.0, co2_mass=4.4)

    def test_no_products(self):
        with self.assertRaises(InputError):
            ORG.combustion_formula(1.0, h2o_mass=1.0)

    def test_rounding_tolerance(self):
        """Школьные данные округлены: 1.6 г при точных массах дают 1.604 г."""
        result = ORG.combustion_formula(1.6, co2_mass=4.4, h2o_mass=3.6)
        self.assertEqual(result.meta["empirical"], "CH4")


class TestIsomers(unittest.TestCase):
    """Изомерия."""

    def test_counts(self):
        expected = {"CH4": 1, "C2H6": 1, "C3H8": 1, "C4H10": 2,
                    "C5H12": 3, "C6H14": 5, "C7H16": 9}
        for formula, count in expected.items():
            self.assertEqual(ORG.isomers(formula).meta["count"], count,
                             f"неверное число изомеров для {formula}")

    def test_types_listed(self):
        result = ORG.isomers("C5H12")
        self.assertGreaterEqual(len(result.value), 4)
        types = [row["Тип изомерии"] for row in result.value]
        self.assertTrue(any("скелет" in item for item in types))

    def test_empty(self):
        with self.assertRaises(InputError):
            ORG.isomers("")


class TestReactions(unittest.TestCase):
    """Реакции классов."""

    def test_alkanes_have_reactions(self):
        result = ORG.reactions_of("Алканы")
        self.assertGreaterEqual(len(result.value), 4)
        equations = [row["Уравнение"] for row in result.value]
        self.assertTrue(any("CH4" in item for item in equations))

    def test_every_class_has_reactions(self):
        for item in ORG._series():
            result = ORG.reactions_of(item["key"])
            self.assertGreater(len(result.value), 0, item["key"])

    def test_reactions_are_balanced_syntax(self):
        """Уравнения из справочника должны разбираться балансировщиком."""
        from alchemy.engines import balancer as BAL

        broken = []
        for item in ORG._series():
            for reaction in item["reactions"]:
                equation = reaction["equation"]
                if "=" not in equation:
                    continue
                try:
                    BAL.balance(equation)
                except Exception:
                    broken.append((item["key"], equation))
        # Список допустимых исключений: уравнения с «белок», «n» и подобными
        allowed = [item for item in broken
                   if "белок" not in item[1] and "nC" not in item[1]]
        self.assertEqual(allowed, [], f"не разбираются: {allowed}")

    def test_unknown_class(self):
        with self.assertRaises(DataNotFoundError):
            ORG.reactions_of("Неизвестный класс")


class TestQualitative(unittest.TestCase):
    """Качественные пробы."""

    def test_all_tests(self):
        result = ORG.qualitative_tests()
        self.assertGreaterEqual(len(result.value), 10)

    def test_aldehydes_silver_mirror(self):
        result = ORG.qualitative_tests("Альдегиды")
        effects = " ".join(row["Признак"] for row in result.value)
        self.assertIn("серебряное зеркало", effects)

    def test_carbohydrates_iodine(self):
        result = ORG.qualitative_tests("Углеводы")
        effects = " ".join(row["Признак"] for row in result.value)
        self.assertIn("синее", effects)

    def test_class_without_tests(self):
        with self.assertRaises(DataNotFoundError):
            ORG.qualitative_tests("Алканы")


class TestPolymers(unittest.TestCase):
    """Полимеры."""

    def test_polyethylene(self):
        result = ORG.polymers_table()
        names = [row["Полимер"] for row in result.value]
        self.assertTrue(any("полиэтилен" in name for name in names))

    def test_count(self):
        self.assertGreaterEqual(len(ORG.polymers_table().value), 6)


class TestGeneticLinks(unittest.TestCase):
    """Переходы между классами."""

    def test_alcohol_to_aldehyde(self):
        result = ORG.genetic_link("C2H5OH", "CH3CHO")
        self.assertTrue(result.meta["possible"])

    def test_acid_to_ester(self):
        result = ORG.genetic_link("CH3COOH", "CH3COOC2H5")
        self.assertTrue(result.meta["possible"])

    def test_alkene_to_alcohol(self):
        result = ORG.genetic_link("C2H4", "C2H5OH")
        self.assertTrue(result.meta["possible"])

    def test_impossible_link(self):
        result = ORG.genetic_link("C2H6", "C6H12O6")
        self.assertFalse(result.meta["possible"])


class TestNomenclature(unittest.TestCase):
    """Номенклатура."""

    def test_roots(self):
        result = ORG.nomenclature_help()
        self.assertGreater(len(result.value), 9)
        roots = [row["Корень"] for row in result.value]
        self.assertIn("мет", roots)
        self.assertIn("бут", roots)

    def test_classes_table(self):
        result = ORG.classes_table()
        self.assertEqual(len(result.value), 18)

    def test_classes_have_general_formula(self):
        for row in ORG.classes_table().value:
            self.assertTrue(row["Общая формула"])


if __name__ == "__main__":
    unittest.main()
