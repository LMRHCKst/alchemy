# -*- coding: utf-8 -*-
"""Тесты разбора зарядов и стехиометрических коэффициентов.

Здесь проверяется то, что раньше работало молча неверно:

* «MnO4-» читался как MnO₁ с зарядом −4 вместо MnO₄⁻, и молярная масса
  выходила 70.9 вместо 118.9 г/моль;
* ионные уравнения «H+ + OH- = H2O» не уравнивались, потому что знак заряда
  принимался за разделитель веществ;
* записанный коэффициент приклеивался к самому себе: «2H2» превращалось
  в «22H2».

Отдельно сверяемся с независимой реализацией — библиотекой periodictable —
на нейтральных формулах, где её модель зарядов не мешает.
"""

from __future__ import annotations

import unittest

from alchemy.core import formula as F
from alchemy.engines import balancer, thermo


class TestChargeResolution(unittest.TestCase):
    """Неоднозначность «Fe3+» против «NO3-» решается по составу."""

    def test_single_element_digits_are_charge(self):
        """Один элемент: цифры перед знаком — величина заряда."""
        cases = {
            "Fe3+": (3, {"Fe": 1}),
            "Fe2+": (2, {"Fe": 1}),
            "Al3+": (3, {"Al": 1}),
            "Ca2+": (2, {"Ca": 1}),
            "Cu2+": (2, {"Cu": 1}),
            "Zn2+": (2, {"Zn": 1}),
            "Ag+": (1, {"Ag": 1}),
            "Na+": (1, {"Na": 1}),
            "Cl-": (-1, {"Cl": 1}),
        }
        for text, (charge, counts) in cases.items():
            with self.subTest(formula=text):
                comp = F.parse(text)
                self.assertEqual(comp.charge, charge)
                self.assertEqual({k: int(v) for k, v in comp.counts.items()},
                                 counts)

    def test_multi_element_single_digit_is_subscript(self):
        """Несколько элементов и одна цифра: цифра — индекс, заряд ±1."""
        cases = {
            "NO3-": (-1, {"N": 1, "O": 3}),
            "NO2-": (-1, {"N": 1, "O": 2}),
            "MnO4-": (-1, {"Mn": 1, "O": 4}),
            "ClO4-": (-1, {"Cl": 1, "O": 4}),
            "ClO3-": (-1, {"Cl": 1, "O": 3}),
            "NH4+": (1, {"N": 1, "H": 4}),
            "HCO3-": (-1, {"H": 1, "C": 1, "O": 3}),
            "H2PO4-": (-1, {"H": 2, "P": 1, "O": 4}),
            "OH-": (-1, {"O": 1, "H": 1}),
            "CN-": (-1, {"C": 1, "N": 1}),
            "SCN-": (-1, {"S": 1, "C": 1, "N": 1}),
            "CH3COO-": (-1, {"C": 2, "H": 3, "O": 2}),
        }
        for text, (charge, counts) in cases.items():
            with self.subTest(formula=text):
                comp = F.parse(text)
                self.assertEqual(comp.charge, charge)
                self.assertEqual({k: int(v) for k, v in comp.counts.items()},
                                 counts)

    def test_multi_element_two_digits_split(self):
        """Несколько элементов и две цифры: последняя — заряд, прочие — индекс."""
        cases = {
            "SO42-": (-2, {"S": 1, "O": 4}),
            "CO32-": (-2, {"C": 1, "O": 3}),
            "PO43-": (-3, {"P": 1, "O": 4}),
            "Cr2O72-": (-2, {"Cr": 2, "O": 7}),
            "S2O32-": (-2, {"S": 2, "O": 3}),
        }
        for text, (charge, counts) in cases.items():
            with self.subTest(formula=text):
                comp = F.parse(text)
                self.assertEqual(comp.charge, charge)
                self.assertEqual({k: int(v) for k, v in comp.counts.items()},
                                 counts)

    def test_caret_notation_unaffected(self):
        """Запись с «^» разбирается независимо от состава."""
        cases = {
            "SO4^2-": (-2, {"S": 1, "O": 4}),
            "Cr2O7^2-": (-2, {"Cr": 2, "O": 7}),
            "PO4^3-": (-3, {"P": 1, "O": 4}),
            "Fe(CN)6^4-": (-4, {"Fe": 1, "C": 6, "N": 6}),
            "H^+": (1, {"H": 1}),
        }
        for text, (charge, counts) in cases.items():
            with self.subTest(formula=text):
                comp = F.parse(text)
                self.assertEqual(comp.charge, charge)
                self.assertEqual({k: int(v) for k, v in comp.counts.items()},
                                 counts)

    def test_brace_notation_is_explicit(self):
        """Фигурные скобки задают заряд однозначно."""
        cases = {
            "SO4{2-}": (-2, {"S": 1, "O": 4}),
            "Fe{3+}": (3, {"Fe": 1}),
            "NH4{+}": (1, {"N": 1, "H": 4}),
            "MnO4{-}": (-1, {"Mn": 1, "O": 4}),
            "PO4{3-}": (-3, {"P": 1, "O": 4}),
            "NO3{-}": (-1, {"N": 1, "O": 3}),
        }
        for text, (charge, counts) in cases.items():
            with self.subTest(formula=text):
                comp = F.parse(text)
                self.assertEqual(comp.charge, charge)
                self.assertEqual({k: int(v) for k, v in comp.counts.items()},
                                 counts)

    def test_brace_beats_heuristic(self):
        """Явная запись сильнее догадки по составу.

        «O2{-}» — это надпероксид с индексом 2, тогда как «O2-» по правилу
        для одного элемента читается как O²⁻.
        """
        explicit = F.parse("O2{-}")
        self.assertEqual(explicit.charge, -1)
        self.assertEqual(int(explicit.counts["O"]), 2)

    def test_superscript_notation(self):
        """Надстрочная запись: SO4²⁻, PO4³⁻."""
        cases = {
            "SO4²⁻": (-2, {"S": 1, "O": 4}),
            "PO4³⁻": (-3, {"P": 1, "O": 4}),
        }
        for text, (charge, counts) in cases.items():
            with self.subTest(formula=text):
                comp = F.parse(text)
                self.assertEqual(comp.charge, charge)
                self.assertEqual({k: int(v) for k, v in comp.counts.items()},
                                 counts)

    def test_molar_mass_of_polyatomic_ions(self):
        """Главное следствие: молярная масса ионов считается верно."""
        cases = {
            "MnO4-": 118.94,
            "NO3-": 62.00,
            "NH4+": 18.04,
            "ClO4-": 99.45,
            "HCO3-": 61.02,
            "SO42-": 96.06,
            "Fe3+": 55.85,
        }
        for text, expected in cases.items():
            with self.subTest(formula=text):
                self.assertAlmostEqual(F.molar_mass(text), expected, places=1)

    def test_regression_mno4_was_wrong(self):
        """Раньше «MnO4-» давало 70.937 г/моль — запомним этот случай."""
        value = F.molar_mass("MnO4-")
        self.assertGreater(value, 118.0)
        self.assertLess(value, 120.0)


class TestElectron(unittest.TestCase):
    """Электрон как участник полуреакции."""

    def test_bare_electron(self):
        comp = F.parse("e-")
        self.assertEqual(comp.charge, -1)
        self.assertEqual(comp.counts, {})

    def test_electron_with_coefficient(self):
        for text, coefficient in [("2e-", 2.0), ("5e-", 5.0), ("10e^-", 10.0)]:
            with self.subTest(formula=text):
                comp = F.parse(text)
                self.assertEqual(comp.charge, -1)
                self.assertEqual(comp.coefficient, coefficient)

    def test_electron_is_recognised_by_balancer(self):
        species = balancer._Species("5e-", "left", 0)
        self.assertTrue(species.is_electron)


class TestCoefficients(unittest.TestCase):
    """Стехиометрические коэффициенты в записи вещества."""

    def test_simple_coefficient(self):
        comp = F.parse("2H2O")
        self.assertEqual(comp.coefficient, 2.0)
        self.assertEqual(int(comp.counts["H"]), 2)
        self.assertEqual(int(comp.counts["O"]), 1)

    def test_fractional_coefficient(self):
        comp = F.parse("0.5O2")
        self.assertEqual(comp.coefficient, 0.5)
        self.assertEqual(F.molar_mass("0.5O2"), F.molar_mass("O2"))

    def test_hydrate_dot_still_works(self):
        """Точка как разделитель гидрата не должна путаться с дробью."""
        dotted = F.molar_mass("CuSO4.5H2O")
        starred = F.molar_mass("CuSO4*5H2O")
        self.assertAlmostEqual(dotted, starred, places=6)
        self.assertAlmostEqual(dotted, 249.677, places=2)

    def test_decimal_in_hydrate(self):
        """Дробное количество воды после звёздочки читается как число."""
        comp = F.parse("CuSO4*2.5H2O")
        self.assertAlmostEqual(comp.molar_mass, 204.64, places=1)


class TestSpeciesSplitting(unittest.TestCase):
    """Разделение веществ по плюсу."""

    def test_separator_with_spaces(self):
        self.assertEqual(balancer._split_species("H2 + O2"), ["H2", "O2"])

    def test_separator_without_spaces(self):
        self.assertEqual(balancer._split_species("H2+O2"), ["H2", "O2"])

    def test_charge_is_not_separator(self):
        cases = {
            "Ag+ + Cl-": ["Ag+", "Cl-"],
            "H+ + OH-": ["H+", "OH-"],
            "MnO4- + Fe2+ + H+": ["MnO4-", "Fe2+", "H+"],
            "Fe3+ + e-": ["Fe3+", "e-"],
            "Cr2O7^2- + H^+ + e^-": ["Cr2O7^2-", "H^+", "e^-"],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(balancer._split_species(text), expected)

    def test_charge_at_end_of_string(self):
        self.assertEqual(balancer._split_species("Na+"), ["Na+"])

    def test_compound_with_parentheses(self):
        self.assertEqual(balancer._split_species("Ca(OH)2 + H2SO4"),
                         ["Ca(OH)2", "H2SO4"])


class TestIonicBalancing(unittest.TestCase):
    """Ионные уравнения в общепринятой записи теперь уравниваются."""

    def test_silver_chloride(self):
        result = balancer.balance("Ag+ + Cl- = AgCl")
        self.assertEqual(result.value, "Ag+ + Cl- → AgCl")

    def test_water_formation(self):
        result = balancer.balance("H+ + OH- = H2O")
        self.assertEqual(result.value, "H+ + OH- → H2O")

    def test_barium_sulfate(self):
        result = balancer.balance("Ba2+ + SO4^2- = BaSO4")
        self.assertEqual(result.value, "Ba2+ + SO4^2- → BaSO4")

    def test_permanganate_oxidation(self):
        result = balancer.balance(
            "MnO4- + Fe2+ + H+ = Mn2+ + Fe3+ + H2O")
        self.assertIn("5Fe2+", result.value)
        self.assertIn("8H+", result.value)
        self.assertIn("5Fe3+", result.value)
        self.assertIn("4H2O", result.value)

    def test_dichromate_oxidation(self):
        result = balancer.balance(
            "Cr2O7^2- + Fe2+ + H+ = Cr3+ + Fe3+ + H2O")
        self.assertIn("6Fe2+", result.value)
        self.assertIn("14H+", result.value)
        self.assertIn("2Cr3+", result.value)

    def test_molecular_equation_still_works(self):
        result = balancer.balance(
            "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O")
        self.assertEqual(
            result.value,
            "2KMnO4 + 16HCl → 2KCl + 2MnCl2 + 5Cl2 + 8H2O")


class TestCoefficientInEquation(unittest.TestCase):
    """Записанные коэффициенты не должны удваиваться в выводе."""

    def test_balanced_equation_keeps_its_form(self):
        result = balancer.balance("2H2 + O2 = 2H2O(г)")
        self.assertEqual(result.value, "2H2 + O2 → 2H2O(г)")

    def test_no_double_coefficient(self):
        """Раньше получалось «22H2» из-за склейки коэффициента с текстом."""
        result = balancer.balance("CH4 + 2O2 = CO2 + 2H2O(г)")
        self.assertNotIn("22", result.value)
        self.assertEqual(result.value, "CH4 + 2O2 → CO2 + 2H2O(г)")

    def test_unbalanced_gets_balanced(self):
        result = balancer.balance("H2 + O2 = H2O(г)")
        self.assertEqual(result.value, "2H2 + O2 → 2H2O(г)")


class TestThermoWithCoefficients(unittest.TestCase):
    """Термохимия принимает уравнения как с коэффициентами, так и без."""

    def test_water_same_both_ways(self):
        plain = thermo.reaction_enthalpy("H2 + O2 = H2O(г)").numeric()
        scaled = thermo.reaction_enthalpy("2H2 + O2 = 2H2O(г)").numeric()
        self.assertAlmostEqual(plain, scaled, places=6)
        self.assertAlmostEqual(plain / 2, -241.83, places=1)

    def test_methane_combustion(self):
        result = thermo.reaction_enthalpy("CH4 + 2O2 = CO2 + 2H2O(г)")
        self.assertAlmostEqual(result.numeric(), -802.3, delta=2.0)

    def test_haber(self):
        result = thermo.reaction_enthalpy("N2 + 3H2 = 2NH3(г)")
        # На 2 моль аммиака; эталон −92.4 кДж/моль на моль NH3
        self.assertAlmostEqual(result.numeric() / 2, -46.1, delta=1.0)


class TestAgainstPeriodictable(unittest.TestCase):
    """Сверка с независимой реализацией разбора формул.

    Библиотека periodictable считает заряд по атомам (запись «SO{2-}4»),
    поэтому для ионов она не подходит. На нейтральных формулах её модель
    совпадает с обычной, и это хороший независимый оракул для проверки
    состава и молярной массы.
    """

    @classmethod
    def setUpClass(cls):
        try:
            import periodictable
        except ImportError:
            raise unittest.SkipTest("periodictable не установлен")
        cls.pt = periodictable

    def test_neutral_formulas_match(self):
        formulas = [
            "H2O", "CO2", "CH4", "CaCO3", "CuSO4", "NaCl", "C6H12O6",
            "Ca(OH)2", "Al2(SO4)3", "K2Cr2O7", "Fe2O3", "H2SO4",
            "C2H5OH", "SiO2", "MgCl2", "NH4Cl", "Na2CO3", "KMnO4",
            "AgNO3", "ZnSO4", "BaCl2", "PbO2", "C12H22O11",
        ]
        for text in formulas:
            with self.subTest(formula=text):
                mine = F.molar_mass(text)
                theirs = self.pt.formula(text).mass
                self.assertAlmostEqual(mine, theirs, places=1)

    def test_hydrate_matches(self):
        mine = F.molar_mass("CuSO4*5H2O")
        theirs = self.pt.formula("CuSO4+5H2O").mass
        self.assertAlmostEqual(mine, theirs, places=1)

    def test_composition_matches(self):
        """Состав совпадает поэлементно."""
        formulas = ["H2O", "CaCO3", "K2Cr2O7", "Al2(SO4)3"]
        for text in formulas:
            with self.subTest(formula=text):
                mine = F.parse(text)
                theirs = self.pt.formula(text)
                for element in theirs.atoms:
                    symbol = str(element)
                    self.assertEqual(int(mine.counts.get(symbol, 0)),
                                     theirs.atoms[element],
                                     f"{text}: {symbol}")


if __name__ == "__main__":
    unittest.main()
