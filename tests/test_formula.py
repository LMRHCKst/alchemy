# -*- coding: utf-8 -*-
"""Тесты парсера формул и периодической таблицы.

Эталонные значения молярных масс взяты из таблицы IUPAC и проверены
независимым расчётом по атомным массам.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alchemy.core import formula, periodic
from alchemy.core.formula import FormulaError
from alchemy.core.errors import DataNotFoundError


class TestPeriodic(unittest.TestCase):
    """Периодическая таблица."""

    def test_count(self):
        self.assertEqual(periodic.count(), 118)

    def test_symbol_lookup(self):
        self.assertEqual(periodic.by_symbol("H").z, 1)
        self.assertEqual(periodic.by_symbol("Fe").z, 26)
        self.assertEqual(periodic.by_symbol("Og").z, 118)
        # Регистр не важен
        self.assertEqual(periodic.by_symbol("fe").z, 26)
        self.assertEqual(periodic.by_symbol("FE").z, 26)

    def test_russian_names(self):
        self.assertEqual(periodic.by_symbol("Fe").name_ru, "Железо")
        self.assertEqual(periodic.by_symbol("Zr").name_ru, "Цирконий")
        self.assertEqual(periodic.by_symbol("Hf").name_ru, "Гафний")

    def test_by_name(self):
        self.assertEqual(periodic.by_name("Железо").symbol, "Fe")
        self.assertEqual(periodic.by_name("iron").symbol, "Fe")
        self.assertEqual(periodic.by_name("Fe").symbol, "Fe")

    def test_unknown_element(self):
        with self.assertRaises(DataNotFoundError):
            periodic.by_symbol("Xx")
        with self.assertRaises(DataNotFoundError):
            periodic.by_number(200)

    def test_atomic_masses_iupac(self):
        """Сверка с таблицей IUPAC 2021."""
        expected = {
            "H": 1.008, "He": 4.0026, "C": 12.011, "N": 14.007, "O": 15.999,
            "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085,
            "P": 30.974, "S": 32.06, "Cl": 35.45, "K": 39.098, "Ca": 40.078,
            "Fe": 55.845, "Cu": 63.546, "Zn": 65.38, "Ag": 107.8682,
            "Zr": 91.224, "Hf": 178.49, "U": 238.029,
        }
        for symbol, mass in expected.items():
            with self.subTest(element=symbol):
                self.assertAlmostEqual(periodic.atomic_mass(symbol), mass, places=2)

    def test_standard_mass_absence(self):
        """У технеция нет стандартной атомной массы."""
        self.assertFalse(periodic.by_symbol("Tc").has_standard_mass)
        self.assertTrue(periodic.by_symbol("Fe").has_standard_mass)

    def test_isotopes(self):
        h = periodic.by_symbol("H")
        self.assertTrue(len(h.isotopes) >= 2)
        u = periodic.by_symbol("U")
        self.assertTrue(any(i.mass_number == 235 for i in u.isotopes))

    def test_average_mass_matches_table(self):
        """Средняя масса по изотопам должна сходиться с табличной."""
        for symbol in ("Cl", "Cu", "Fe", "Mg", "Si"):
            with self.subTest(element=symbol):
                avg = periodic.average_mass_from_isotopes(symbol)
                table = periodic.atomic_mass(symbol)
                if avg is not None:
                    self.assertLess(abs(avg - table), 0.05)

    def test_electronegativity_and_bond_type(self):
        d = periodic.electronegativity_difference("Na", "Cl")
        self.assertAlmostEqual(d, 2.23, places=2)
        name, _ = periodic.bond_type(d)
        self.assertEqual(name, "ионная")

        d2 = periodic.electronegativity_difference("H", "H")
        self.assertEqual(d2, 0.0)
        self.assertEqual(periodic.bond_type(d2)[0], "ковалентная неполярная")

    def test_grid_layout(self):
        grid = periodic.grid_layout()
        self.assertEqual(len(grid), 10)
        self.assertEqual(len(grid[0]), 18)
        # Водород — первая строка, первая колонка
        self.assertEqual(grid[0][0].symbol, "H")
        # Гелий — первая строка, 18-я колонка
        self.assertEqual(grid[0][17].symbol, "He")

    def test_valence_electrons(self):
        self.assertEqual(periodic.by_symbol("Na").valence_electrons, 1)
        self.assertEqual(periodic.by_symbol("Cl").valence_electrons, 7)
        self.assertEqual(periodic.by_symbol("C").valence_electrons, 4)


class TestFormulaParser(unittest.TestCase):
    """Разбор формул."""

    def test_simple(self):
        c = formula.parse("H2O")
        self.assertEqual(c.counts, {"H": 2.0, "O": 1.0})
        self.assertAlmostEqual(c.molar_mass, 18.015, places=2)

    def test_no_subscript(self):
        self.assertAlmostEqual(formula.molar_mass("NaCl"), 58.44, places=1)

    def test_parentheses(self):
        c = formula.parse("Ca(OH)2")
        self.assertEqual(c.counts, {"Ca": 1.0, "O": 2.0, "H": 2.0})
        self.assertAlmostEqual(c.molar_mass, 74.093, places=2)

    def test_nested_brackets(self):
        c = formula.parse("K4[Fe(CN)6]")
        self.assertEqual(c.counts, {"K": 4.0, "Fe": 1.0, "C": 6.0, "N": 6.0})
        self.assertAlmostEqual(c.molar_mass, 368.35, places=1)

    def test_complex_salt(self):
        c = formula.parse("[Cu(NH3)4]SO4")
        self.assertEqual(c.counts, {"Cu": 1.0, "N": 4.0, "H": 12.0, "S": 1.0, "O": 4.0})
        self.assertAlmostEqual(c.molar_mass, 227.73, places=1)

    def test_common_salts(self):
        expected = {
            "Ca3(PO4)2": 310.18,
            "(NH4)2SO4": 132.14,
            "KMnO4": 158.03,
            "K2Cr2O7": 294.18,
            "NaHCO3": 84.007,
            "C6H12O6": 180.16,
            "CH3COOH": 60.052,
            "H2SO4": 98.079,
            "NaOH": 39.997,
        }
        for f, m in expected.items():
            with self.subTest(formula=f):
                self.assertAlmostEqual(formula.molar_mass(f), m, places=1)

    # ---------------- гидраты ----------------

    def test_hydrate_asterisk(self):
        self.assertAlmostEqual(formula.molar_mass("CuSO4*5H2O"), 249.68, places=1)

    def test_hydrate_middle_dot(self):
        self.assertAlmostEqual(formula.molar_mass("CuSO4·5H2O"), 249.68, places=1)

    def test_hydrate_plain_dot(self):
        """CuSO4.5H2O — общепринятая запись, не десятичная дробь."""
        self.assertAlmostEqual(formula.molar_mass("CuSO4.5H2O"), 249.68, places=1)

    def test_hydrate_without_coefficient(self):
        """CaSO4*2H2O — гипс."""
        self.assertAlmostEqual(formula.molar_mass("CaSO4*2H2O"), 172.17, places=1)

    def test_hydrate_ten_waters(self):
        """Na2CO3*10H2O — кристаллическая сода."""
        self.assertAlmostEqual(formula.molar_mass("Na2CO3*10H2O"), 286.14, places=1)

    def test_hydrate_composition(self):
        c = formula.parse("CuSO4*5H2O")
        self.assertEqual(c.count("H"), 10.0)
        self.assertEqual(c.count("O"), 9.0)
        self.assertEqual(len(c.parts), 2)

    # ---------------- ионы ----------------

    def test_charge_caret(self):
        c = formula.parse("SO4^2-")
        self.assertEqual(c.charge, -2)
        self.assertAlmostEqual(c.molar_mass, 96.06, places=1)

    def test_charge_unicode(self):
        c = formula.parse("SO4²⁻")
        self.assertEqual(c.charge, -2)

    def test_charge_single(self):
        self.assertEqual(formula.parse("Cl^-").charge, -1)
        self.assertEqual(formula.parse("Na^+").charge, 1)
        self.assertEqual(formula.parse("Fe^3+").charge, 3)
        self.assertEqual(formula.parse("Fe^2+").charge, 2)

    def test_charge_without_caret(self):
        self.assertEqual(formula.parse("Cl-").charge, -1)
        self.assertEqual(formula.parse("Na+").charge, 1)

    def test_ammonium(self):
        c = formula.parse("NH4^+")
        self.assertEqual(c.charge, 1)
        self.assertAlmostEqual(c.molar_mass, 18.039, places=2)

    def test_electron(self):
        c = formula.parse("e^-")
        self.assertEqual(c.charge, -1)
        self.assertLess(c.molar_mass, 0.001)

    # ---------------- состояния и коэффициенты ----------------

    def test_state(self):
        c = formula.parse("Fe2O3(s)")
        self.assertEqual(c.state, "s")
        self.assertAlmostEqual(c.molar_mass, 159.69, places=1)

    def test_state_aq(self):
        c = formula.parse("NaCl(aq)")
        self.assertEqual(c.state, "aq")

    def test_leading_coefficient(self):
        c = formula.parse("2H2O")
        self.assertEqual(c.coefficient, 2)
        # Коэффициент не входит в молярную массу
        self.assertAlmostEqual(c.molar_mass, 18.015, places=2)

    # ---------------- ошибки вместо мусора ----------------

    def test_garbage_raises(self):
        """Мусор должен давать ошибку, а не молча неверный ответ."""
        cases = {
            "h2o": "строчные символы элементов",
            "H2O!": "недопустимый символ",
            "H2O)": "лишняя закрывающая скобка",
            "!!": "не буквы и не цифры",
            "": "пустая строка",
            "   ": "только пробелы",
            "5": "число без элемента",
            "H2O·": "висячий разделитель гидрата",
        }
        for bad, reason in cases.items():
            with self.subTest(formula=bad, reason=reason):
                with self.assertRaises(FormulaError):
                    formula.parse(bad)

    def test_unknown_element_raises(self):
        with self.assertRaises(FormulaError):
            formula.parse("Xx2O3")
        with self.assertRaises(FormulaError):
            formula.parse("H2O2O3XYZ")

    def test_unclosed_bracket_raises(self):
        with self.assertRaises(FormulaError):
            formula.parse("Ca(OH2")

    def test_implausible_subscript_raises(self):
        """Слипшаяся запись гидрата без разделителя — почти всегда ошибка."""
        for bad in ["Na2CO310H2O", "CuSO425H2O"]:
            with self.subTest(formula=bad):
                with self.assertRaises(FormulaError):
                    formula.parse(bad)

    def test_space_is_component_separator(self):
        """«CuSO4 5H2O» — медный купорос, а не соединение с S45.

        Раньше такая запись молча давала 833.576 г/моль вместо 249.68.
        """
        c = formula.parse("CuSO4 5H2O")
        self.assertEqual(c.count("S"), 1.0)
        self.assertEqual(c.count("H"), 10.0)
        self.assertAlmostEqual(c.molar_mass, 249.68, places=1)

    def test_spaces_inside_formula_ignored(self):
        """Пробелы внутри одной формулы не мешают: «H2 O» = «H2O»."""
        self.assertAlmostEqual(formula.molar_mass("H2 O"), 18.015, places=2)

    def test_empty_brackets(self):
        with self.assertRaises(FormulaError):
            formula.parse("Ca()2")

    def test_lowercase_rejected(self):
        """Строчные буквы в начале — почти всегда опечатка."""
        with self.assertRaises(FormulaError):
            formula.parse("na2co3")

    # ---------------- состав и доли ----------------

    def test_mass_percentages(self):
        pct = formula.mass_percentages("H2O")
        self.assertAlmostEqual(pct["H"], 11.19, places=1)
        self.assertAlmostEqual(pct["O"], 88.81, places=1)

    def test_mass_percentages_sum_to_100(self):
        for f in ("H2SO4", "C6H12O6", "KMnO4", "Fe2O3", "CuSO4*5H2O"):
            with self.subTest(formula=f):
                self.assertAlmostEqual(sum(formula.mass_percentages(f).values()),
                                       100.0, places=4)

    def test_total_atoms(self):
        self.assertEqual(formula.parse("C6H12O6").total_atoms, 24.0)

    def test_hill_formula(self):
        self.assertEqual(formula.parse("CH3COOH").hill_formula, "C2H4O2")
        self.assertEqual(formula.parse("H2O").hill_formula, "H2O")

    def test_element_fraction(self):
        c = formula.parse("H2O")
        self.assertAlmostEqual(c.element_fraction("H"), 2 / 3, places=6)

    # ---------------- эмпирическая формула ----------------

    def test_empirical_from_percentages(self):
        self.assertEqual(
            formula.empirical_formula(percentages={"C": 40.0, "H": 6.7, "O": 53.3}),
            "CH2O",
        )

    def test_empirical_iron_oxide(self):
        self.assertEqual(
            formula.empirical_formula(percentages={"Fe": 69.94, "O": 30.06}),
            "Fe2O3",
        )

    def test_empirical_dichromate(self):
        """Дикромат калия. Порядок элементов в записи не важен."""
        result = formula.empirical_formula(
            percentages={"K": 26.58, "Cr": 35.35, "O": 38.07}
        )
        self.assertTrue(formula.compare_formulas(result, "K2Cr2O7"),
                        f"получено {result}, ожидался состав K2Cr2O7")

    def test_empirical_from_masses(self):
        """1.008 г H и 8.0 г O дают H2O."""
        self.assertEqual(formula.empirical_formula(masses={"H": 1.008, "O": 8.0}), "H2O")

    def test_empirical_impossible(self):
        with self.assertRaises(FormulaError):
            formula.empirical_formula(percentages={})

    def test_molecular_from_empirical(self):
        """CH2O при M = 180 г/моль даёт C6H12O6."""
        self.assertEqual(
            formula.molecular_formula_from_empirical("CH2O", 180.16), "C6H12O6"
        )

    def test_molecular_contradiction(self):
        with self.assertRaises(FormulaError):
            formula.molecular_formula_from_empirical("CH2O", 45.0)

    # ---------------- прочее ----------------

    def test_hydrate_mass_larger(self):
        """Масса гидрата обязана быть больше массы безводной соли."""
        self.assertGreater(formula.molar_mass("CuSO4*5H2O"),
                           formula.molar_mass("CuSO4"))

    def test_degrees_of_unsaturation(self):
        self.assertEqual(formula.degrees_of_unsaturation("C6H6"), 4)
        self.assertEqual(formula.degrees_of_unsaturation("C2H6"), 0)
        self.assertIsNone(formula.degrees_of_unsaturation("H2O"))

    def test_equiv_mass(self):
        self.assertAlmostEqual(formula.equivalent_mass("H2SO4", 2), 49.04, places=1)

    def test_compare(self):
        self.assertTrue(formula.compare_formulas("H2SO4", "SO4H2"))
        self.assertFalse(formula.compare_formulas("H2SO4", "H2SO3"))

    def test_unicode_subscript_input(self):
        """Пользователь может вставить формулу с подстрочными цифрами."""
        self.assertAlmostEqual(formula.molar_mass("H₂SO₄"), 98.079, places=1)

    def test_uncertainty_positive(self):
        m = formula.molar_mass_measurement("NaCl")
        self.assertGreater(m.uncertainty, 0)
        self.assertGreater(m.value, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
