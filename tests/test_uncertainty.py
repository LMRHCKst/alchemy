# -*- coding: utf-8 -*-
"""Тесты величин с неопределённостью.

Проверяется главное отличие от прежней реализации: корреляция. Раньше
все величины считались независимыми, поэтому x − x давало √2·σ вместо нуля.
"""

from __future__ import annotations

import math
import unittest

from alchemy.core.results import (
    Measurement,
    apply_function,
    format_measurement,
    m_exp,
    m_ln,
    m_log10,
    m_sqrt,
    sig_figs_from_uncertainty,
)


class TestMeasurementBasics(unittest.TestCase):
    """Создание и свойства."""

    def test_value_and_uncertainty(self):
        m = Measurement(2.5, 0.1, "г")
        self.assertEqual(m.value, 2.5)
        self.assertEqual(m.uncertainty, 0.1)
        self.assertEqual(m.unit, "г")

    def test_defaults_to_exact(self):
        m = Measurement(42.0)
        self.assertEqual(m.uncertainty, 0.0)
        self.assertEqual(m.unit, "")

    def test_negative_uncertainty_rejected(self):
        with self.assertRaises(ValueError):
            Measurement(1.0, -0.1)

    def test_float_conversion(self):
        self.assertEqual(float(Measurement(3.75, 0.02)), 3.75)

    def test_relative(self):
        m = Measurement(200.0, 2.0)
        self.assertAlmostEqual(m.relative, 0.01)

    def test_relative_of_zero(self):
        self.assertEqual(Measurement(0.0, 0.1).relative, 0.0)


class TestMeasurementArithmetic(unittest.TestCase):
    """Арифметика и распространение погрешности."""

    def setUp(self):
        self.x = Measurement(2.0, 0.1, "м")

    def test_addition(self):
        result = self.x + 3
        self.assertAlmostEqual(result.value, 5.0)
        self.assertAlmostEqual(result.uncertainty, 0.1)
        self.assertEqual(result.unit, "м")

    def test_radd(self):
        self.assertAlmostEqual((3 + self.x).value, 5.0)

    def test_subtraction(self):
        result = self.x - 1
        self.assertAlmostEqual(result.value, 1.0)
        self.assertAlmostEqual(result.uncertainty, 0.1)

    def test_rsub(self):
        result = 3 - self.x
        self.assertAlmostEqual(result.value, 1.0)
        self.assertAlmostEqual(result.uncertainty, 0.1)

    def test_multiplication_constant(self):
        result = self.x * 3
        self.assertAlmostEqual(result.value, 6.0)
        self.assertAlmostEqual(result.uncertainty, 0.3)

    def test_division_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            self.x / 0

    def test_rdivision(self):
        result = 4 / self.x
        self.assertAlmostEqual(result.value, 2.0)
        # d(4/x) = -4/x² -> 4/4 * 0.1 = 0.1
        self.assertAlmostEqual(result.uncertainty, 0.1, places=6)

    def test_rdivision_by_zero_measurement(self):
        with self.assertRaises(ZeroDivisionError):
            4 / Measurement(0.0, 0.0)

    def test_power(self):
        result = self.x ** 2
        self.assertAlmostEqual(result.value, 4.0)
        # d(x²) = 2x -> 2·2·0.1 = 0.4
        self.assertAlmostEqual(result.uncertainty, 0.4, places=6)

    def test_negation(self):
        result = -self.x
        self.assertAlmostEqual(result.value, -2.0)
        self.assertAlmostEqual(result.uncertainty, 0.1)

    def test_absolute(self):
        result = abs(-self.x)
        self.assertAlmostEqual(result.value, 2.0)
        self.assertAlmostEqual(result.uncertainty, 0.1)

    def test_zero_power(self):
        result = Measurement(0.0, 0.0) ** 2
        self.assertEqual(result.value, 0.0)
        self.assertEqual(result.uncertainty, 0.0)

    def test_fractional_power_of_negative_rejected(self):
        with self.assertRaises(ValueError):
            Measurement(-2.0, 0.1) ** 0.5

    def test_integer_power_of_negative_allowed(self):
        result = Measurement(-2.0, 0.1) ** 3
        self.assertAlmostEqual(result.value, -8.0)
        self.assertAlmostEqual(result.uncertainty, 1.2, places=6)


class TestCorrelation(unittest.TestCase):
    """Главное приобретение: повторное использование величины учитывается."""

    def test_self_subtraction_gives_zero(self):
        """x − x равно нулю точно, без √2·σ."""
        x = Measurement(2.0, 0.1)
        self.assertEqual((x - x).value, 0.0)
        self.assertAlmostEqual((x - x).uncertainty, 0.0, places=12)

    def test_self_division_gives_one(self):
        x = Measurement(2.0, 0.1)
        self.assertAlmostEqual((x / x).value, 1.0)
        self.assertAlmostEqual((x / x).uncertainty, 0.0, places=12)

    def test_self_multiplication_is_correlated(self):
        """x·x: производная 2x, поэтому σ = 2·x·σₓ, а не √2·x·σₓ."""
        x = Measurement(2.0, 0.1)
        result = x * x
        self.assertAlmostEqual(result.value, 4.0)
        self.assertAlmostEqual(result.uncertainty, 0.4, places=6)

    def test_independent_multiplication(self):
        """Разные величины с теми же значениями независимы.

        σ(xy) = √((y·σₓ)² + (x·σ_y)²) = √(0.2² + 0.2²) = 0.283.
        Для одной и той же величины (проверка выше) было бы 0.4.
        """
        x = Measurement(2.0, 0.1)
        y = Measurement(2.0, 0.1)
        result = x * y
        self.assertAlmostEqual(result.value, 4.0)
        self.assertAlmostEqual(result.uncertainty, math.sqrt(2) * 0.2, places=6)
        # Независимые дают меньшую погрешность, чем коррелированные
        self.assertLess(result.uncertainty, (x * x).uncertainty)

    def test_correlation_survives_chained_operations(self):
        """Корреляция не теряется после промежуточных вычислений."""
        x = Measurement(3.0, 0.2)
        a = x * 2
        b = x + 1
        # (2x) - (x+1) = x - 1, погрешность равна σₓ, а не √(4σ²+σ²)
        result = a - b
        self.assertAlmostEqual(result.value, 2.0)
        self.assertAlmostEqual(result.uncertainty, 0.2, places=6)

    def test_common_factor_cancels(self):
        """Дробь, где числитель и знаменатель делят одну величину."""
        stock = Measurement(0.5, 0.01)
        diluted = stock / 10
        ratio = diluted / stock
        self.assertAlmostEqual(ratio.value, 0.1)
        self.assertAlmostEqual(ratio.uncertainty, 0.0, places=12)


class TestFunctions(unittest.TestCase):
    """Функции поверх величин с погрешностью."""

    def test_log10(self):
        m = Measurement(2.0, 0.1)
        result = m_log10(m)
        self.assertAlmostEqual(result.value, math.log10(2.0))
        # d(lg x) = 1/(x·ln10) -> 0.1/(2·2.3026)
        self.assertAlmostEqual(result.uncertainty, 0.1 / (2.0 * math.log(10)),
                               places=8)

    def test_log10_of_negative_rejected(self):
        with self.assertRaises(ValueError):
            m_log10(Measurement(-1.0, 0.1))

    def test_ln(self):
        m = Measurement(2.0, 0.1)
        result = m_ln(m)
        self.assertAlmostEqual(result.value, math.log(2.0))
        self.assertAlmostEqual(result.uncertainty, 0.05, places=8)

    def test_sqrt(self):
        m = Measurement(4.0, 0.1)
        result = m_sqrt(m)
        self.assertAlmostEqual(result.value, 2.0)
        # d(√x) = 1/(2√x) -> 0.1/4
        self.assertAlmostEqual(result.uncertainty, 0.025, places=8)

    def test_sqrt_of_negative_rejected(self):
        with self.assertRaises(ValueError):
            m_sqrt(Measurement(-4.0, 0.1))

    def test_exp(self):
        m = Measurement(2.0, 0.1)
        result = m_exp(m)
        self.assertAlmostEqual(result.value, math.exp(2.0))
        self.assertAlmostEqual(result.uncertainty, math.exp(2.0) * 0.1, places=6)

    def test_apply_function(self):
        m = Measurement(2.0, 0.1)
        result = apply_function(m, lambda v: v ** 3, lambda v: 3 * v ** 2)
        self.assertAlmostEqual(result.value, 8.0)
        self.assertAlmostEqual(result.uncertainty, 1.2, places=6)

    def test_apply_function_preserves_correlation(self):
        m = Measurement(2.0, 0.1)
        cubed = apply_function(m, lambda v: v ** 3, lambda v: 3 * v ** 2)
        # Разность не должна складывать погрешности: куб и исходная
        # величина зависят от одной переменной
        result = cubed - m
        self.assertAlmostEqual(result.value, 6.0)
        self.assertLess(result.uncertainty, 1.5)


class TestFormatting(unittest.TestCase):
    """Запись значения с погрешностью."""

    def test_sig_figs_from_uncertainty(self):
        # Функция возвращает число значащих цифр и не опускается ниже единицы
        self.assertEqual(sig_figs_from_uncertainty(0.012), 1)
        self.assertEqual(sig_figs_from_uncertainty(0.12), 1)
        self.assertEqual(sig_figs_from_uncertainty(1.2), 1)
        # Для крупной погрешности разряд уходит в целые
        self.assertEqual(sig_figs_from_uncertainty(12.0), 2)

    def test_sig_figs_grows_with_uncertainty(self):
        """Чем грубее погрешность, тем левее разряд округления."""
        self.assertLessEqual(sig_figs_from_uncertainty(0.005),
                             sig_figs_from_uncertainty(50.0))

    def test_sig_figs_of_exact_value(self):
        self.assertEqual(Measurement(5.0).sig_figs, 15)

    def test_format_measurement(self):
        text = format_measurement(9.81, 0.02)
        self.assertIn("9.81", text)
        self.assertIn("±", text)

    def test_format_without_uncertainty(self):
        text = format_measurement(9.81, 0.0)
        self.assertNotIn("±", text)

    def test_formatted_method(self):
        m = Measurement(249.677, 0.005, "г/моль")
        text = m.formatted()
        self.assertIn("249.677", text)
        self.assertIn("г/моль", text)


class TestFormulaUncertainty(unittest.TestCase):
    """Погрешность молярной массы приходит из атомных масс."""

    def test_molar_mass_has_uncertainty(self):
        from alchemy.core import formula
        m = formula.molar_mass_measurement("NaCl")
        self.assertGreater(m.uncertainty, 0)
        self.assertAlmostEqual(m.value, 58.44, places=1)

    def test_hydrate_uncertainty(self):
        from alchemy.core import formula
        m = formula.molar_mass_measurement("CuSO4*5H2O")
        self.assertAlmostEqual(m.value, 249.677, places=2)
        self.assertGreater(m.uncertainty, 0)
        # Относительная погрешность мала: атомные массы известны точно
        self.assertLess(m.relative, 1e-3)


if __name__ == "__main__":
    unittest.main()
