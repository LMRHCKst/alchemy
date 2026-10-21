# -*- coding: utf-8 -*-
"""Проверка предела коэффициента активности и заметная разница моделей."""

import unittest

from alchemy.core.errors import DomainError
from alchemy.engines import acidbase as AB


class TestActivityLimits(unittest.TestCase):
    """Где наша модель работает, а где уже врёт."""

    def test_moderate_strength_is_fine(self):
        """До I = 0.5 расхождение с Питцером в пределах 8 %."""
        for ionic in (0.01, 0.1, 0.5):
            gamma = AB.activity_coefficient(1, ionic)
            self.assertGreater(gamma, 0.5)
            self.assertLess(gamma, 1.05)

    def test_gamma_may_exceed_one(self):
        """При высокой ионной силе γ больше единицы — это не ошибка."""
        self.assertGreater(AB.activity_coefficient(1, 2.0), 1.0)

    def test_absurd_gamma_is_refused(self):
        """При I = 8 формула даёт 2456 — такое отдавать нельзя."""
        with self.assertRaises(DomainError):
            AB.activity_coefficient(2, 8.0)

    def test_acid_ph_still_works_when_concentrated(self):
        """Концентрированная соляная кислота считается, а не падает."""
        value = AB.ph_of_acid("HCl", 2.0, include_activity=True).numeric()
        self.assertLess(value, 0.0)
        self.assertGreater(value, -0.5)

    def test_two_two_salt_at_low_strength(self):
        """Сульфат магния 0.1 моль/кг: ионная сила 0.4, расчёт идёт."""
        gamma = AB.activity_coefficient(2, 0.4)
        self.assertLess(gamma, 0.4)


if __name__ == "__main__":
    unittest.main()
