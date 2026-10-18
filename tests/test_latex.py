# -*- coding: utf-8 -*-
"""Тесты записи формул и уравнений в LaTeX."""

from __future__ import annotations

import unittest

from alchemy.core import formula as F
from alchemy.core import latex as LX
from alchemy.core.errors import AlchemyError


class TestFormulaLatex(unittest.TestCase):
    """Формулы."""

    def test_simple(self):
        self.assertEqual(LX.formula_to_latex("H2O"),
                         r"\mathrm{H_{2}O}")

    def test_sulfate(self):
        self.assertEqual(LX.formula_to_latex("H2SO4"),
                         r"\mathrm{H_{2}SO_{4}}")

    def test_parentheses(self):
        self.assertEqual(LX.formula_to_latex("Ca(OH)2"),
                         r"\mathrm{Ca(OH)_{2}}")

    def test_hydrate(self):
        result = LX.formula_to_latex("CuSO4*5H2O")
        self.assertIn(r"\cdot", result)
        self.assertIn(r"5\,", result)
        self.assertIn(r"\mathrm{H_{2}O}", result)

    def test_charge_minus(self):
        self.assertEqual(LX.formula_to_latex("MnO4-"),
                         r"\mathrm{MnO_{4}}^-")

    def test_charge_plus(self):
        self.assertEqual(LX.formula_to_latex("Fe2+"),
                         r"\mathrm{Fe}^{2+}")

    def test_charge_two_minus(self):
        self.assertEqual(LX.formula_to_latex("SO4{2-}"),
                         r"\mathrm{SO_{4}}^{2-}")

    def test_state_russian(self):
        result = LX.formula_to_latex("Fe2O3(тв)")
        self.assertIn(r"\mathrm{Fe_{2}O_{3}}", result)
        self.assertIn(r"(\text{тв})", result)

    def test_state_liquid(self):
        result = LX.formula_to_latex("H2O(ж)")
        self.assertIn(r"(\text{ж})", result)

    def test_coefficient(self):
        result = LX.formula_to_latex("0.5O2")
        self.assertTrue(result.startswith("0.5"))
        self.assertIn(r"\mathrm{O_{2}}", result)

    def test_complex(self):
        result = LX.formula_to_latex("[Cu(NH3)4]SO4")
        self.assertIn("Cu", result)
        self.assertIn("NH", result)

    def test_no_double_subscript(self):
        """Двойной подстрочный индекс — ошибка LaTeX."""
        for text in ("Fe2O3(тв)", "H2O(ж)", "CuSO4*5H2O"):
            result = LX.formula_to_latex(text)
            self.assertNotIn("}_{", result.replace(r"_{", "_{"))
            self.assertEqual(result.count("^"), result.count("^{")
                             + result.count("^-") + result.count("^+"))

    def test_empty_raises(self):
        with self.assertRaises(AlchemyError):
            LX.formula_to_latex("")

    def test_mhchem_wraps(self):
        self.assertTrue(LX.formula_to_latex("H2O", mhchem=True)
                        .startswith(r"\ce{"))

    def test_mhchem_hydrate_dot(self):
        result = LX.formula_to_latex("CuSO4*5H2O", mhchem=True)
        self.assertIn(".", result)
        self.assertNotIn("*", result)


class TestReactionLatex(unittest.TestCase):
    """Уравнения."""

    def test_simple_reaction(self):
        result = LX.reaction_to_latex("2H2 + O2 = 2H2O")
        self.assertIn(r"\rightarrow", result)
        self.assertIn(r"\mathrm{H_{2}}", result)
        self.assertIn(r"\mathrm{O_{2}}", result)
        self.assertEqual(result.count("+"), 1)

    def test_ionic_reaction_keeps_charges(self):
        """Плюс заряда не должен считаться разделителем."""
        result = LX.reaction_to_latex("MnO4- + Fe2+ + H+ = Mn2+ + Fe3+ + H2O")
        # три вещества слева и три справа — значит два плюса с каждой стороны
        self.assertEqual(result.count(" + "), 4)
        self.assertIn(r"\mathrm{Fe}^{2+}", result)
        self.assertIn(r"\mathrm{H}^+", result)

    def test_arrow_styles(self):
        for arrow in ("=", "->", "→"):
            result = LX.reaction_to_latex(f"H2 + O2 {arrow} H2O")
            self.assertTrue(r"\rightarrow" in result
                            or r"\longrightarrow" in result)

    def test_coefficients_kept(self):
        result = LX.reaction_to_latex("2H2 + O2 = 2H2O")
        self.assertTrue(result.startswith("2"))
        self.assertIn("2\\, \\mathrm{H_{2}O}", result)

    def test_states_in_reaction(self):
        result = LX.reaction_to_latex("CaCO3(тв) = CaO(тв) + CO2")
        self.assertEqual(result.count(r"(\text{тв})"), 2)

    def test_mhchem_whole_reaction(self):
        result = LX.reaction_to_latex("2H2 + O2 = 2H2O", mhchem=True)
        self.assertEqual(result.count(r"\ce{"), 1)
        self.assertIn("->", result)

    def test_no_arrow_raises(self):
        with self.assertRaises(AlchemyError):
            LX.reaction_to_latex("H2 O2 H2O")

    def test_empty_side_raises(self):
        with self.assertRaises(AlchemyError):
            LX.reaction_to_latex(" = 2H2O")


class TestUniversals(unittest.TestCase):
    """Разбор входа и сборка документа."""

    def test_detects_equation(self):
        self.assertTrue(LX.looks_like_equation("2H2 + O2 = 2H2O"))
        self.assertFalse(LX.looks_like_equation("CuSO4*5H2O"))

    def test_to_latex_equation(self):
        self.assertIn(r"\rightarrow", LX.to_latex("2H2 + O2 = 2H2O"))

    def test_to_latex_formula(self):
        self.assertIn(r"\mathrm", LX.to_latex("CuSO4"))

    def test_to_latex_plain_text(self):
        self.assertIn(r"\text{", LX.to_latex("плотность раствора"))

    def test_to_latex_empty(self):
        self.assertEqual(LX.to_latex(""), "")

    def test_document_snippet(self):
        snippet = LX.document_snippet(["2H2 + O2 = 2H2O",
                                       "N2 + 3H2 = 2NH3"])
        self.assertIn(r"\begin{align*}", snippet)
        self.assertIn(r"\end{align*}", snippet)
        self.assertEqual(snippet.count(r"\\"), 2)

    def test_document_snippet_mhchem_comment(self):
        snippet = LX.document_snippet(["H2 + O2 = H2O"], mhchem=True)
        self.assertIn("mhchem", snippet)


class TestAgainstParser(unittest.TestCase):
    """LaTeX должен описывать то же вещество, что и парсер."""

    def test_elements_preserved(self):
        for text in ("CuSO4*5H2O", "Ca(OH)2", "K4[Fe(CN)6]", "MnO4-"):
            composition = F.parse(text)
            latex_text = LX.formula_to_latex(text)
            for symbol in composition.elements:
                self.assertIn(symbol, latex_text,
                              f"{symbol} потерян в LaTeX для {text}")


if __name__ == "__main__":
    unittest.main()
