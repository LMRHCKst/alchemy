# -*- coding: utf-8 -*-
"""Тесты: парсер после сверки ввода, сернистая кислота, Питцер, полиморфы."""

import unittest

from alchemy.core import formula as F
from alchemy.core.errors import InputError
from alchemy.data import acids as ADB
from alchemy.data import solubility as SDB
from alchemy.engines import activity_pitzer as AP
from alchemy.engines import acidbase as AB


class TestParserFromAudit(unittest.TestCase):
    """Записи из внешней сверки пользовательского ввода."""

    def test_hyphen_hydrate(self):
        """CuSO4-5H2O — дефис вместо точки."""
        self.assertAlmostEqual(F.molar_mass("CuSO4-5H2O"), 249.677, places=2)

    def test_charge_sign_before_digits(self):
        """SO4-2 — знак перед цифрой."""
        parsed = F.parse("SO4-2")
        self.assertEqual(parsed.charge, -2)
        self.assertEqual(parsed.counts["O"], 4.0)

    def test_charge_in_parentheses(self):
        """SO4(2-) — заряд в скобках."""
        parsed = F.parse("SO4(2-)")
        self.assertEqual(parsed.charge, -2)

    def test_arrow_states(self):
        """Fe(OH)3↓ и CO2↑ — стрелки как состояние."""
        self.assertEqual(F.parse("Fe(OH)3↓").state, "s")
        self.assertEqual(F.parse("CO2↑").state, "g")

    def test_complex_charge_still_ok(self):
        self.assertAlmostEqual(F.molar_mass("[Cu(NH3)4]2+"), 131.67, places=2)


class TestSulfurousAcid(unittest.TestCase):
    def test_present(self):
        acid = ADB.maybe_acid("H2SO3")
        self.assertIsNotNone(acid)
        self.assertAlmostEqual(acid.pKa, 1.92, places=2)
        self.assertEqual(acid.protons, 2)

    def test_stages(self):
        stages = AB._related_pka("H2SO3", 2)
        self.assertEqual(len(stages), 2)
        self.assertAlmostEqual(stages[0], 1.92, places=2)
        self.assertAlmostEqual(stages[1], 7.20, places=1)

    def test_ph_is_acidic(self):
        result = AB.ph_of_acid("H2SO3", 0.1)
        self.assertLess(result.numeric(), 2.0)


class TestPitzer(unittest.TestCase):
    """Сверка со справочными средними коэффициентами активности."""

    def test_nacl_reference(self):
        for molality, expected in ((0.1, 0.778), (0.5, 0.681),
                                   (1.0, 0.657), (2.0, 0.668)):
            gamma = AP.mean_activity_coefficient("Na+", "Cl-", molality)
            self.assertAlmostEqual(gamma / expected, 1.0, delta=0.01,
                                   msg=f"NaCl при {molality} моль/кг")

    def test_kcl_reference(self):
        gamma = AP.mean_activity_coefficient("K+", "Cl-", 1.0)
        self.assertAlmostEqual(gamma, 0.604, delta=0.01)

    def test_two_to_two_refused(self):
        """Для 2:2 электролитов движок честно отказывает."""
        with self.assertRaises(InputError):
            AP.mean_activity_coefficient("Mg2+", "SO4^2-", 0.1)

    def test_unknown_electrolyte_refused(self):
        with self.assertRaises(InputError):
            AP.mean_activity_coefficient("Li+", "Cl-", 0.1)

    def test_davies_differs_at_one_molar(self):
        """Дэвис на 1 моль/кг завышает примерно на 20 %."""
        pitzer = AP.mean_activity_coefficient("Na+", "Cl-", 1.0)
        davies = AP.Davies_gamma(1.0, 1.0)
        self.assertGreater(davies / pitzer, 1.1)

    def test_verified_zone_has_no_warning(self):
        result = AP.pitzer_gamma("Na+", "Cl-", 1.0)
        self.assertEqual(len(result.warnings), 0)

    def test_beyond_verified_warns(self):
        result = AP.pitzer_gamma("Na+", "Cl-", 3.0)
        self.assertGreater(len(result.warnings), 0)


class TestPolymorphNotes(unittest.TestCase):
    def test_zns_has_note(self):
        self.assertIsNotNone(SDB.note_for("ZnS"))

    def test_agcl_has_no_note(self):
        self.assertIsNone(SDB.note_for("AgCl"))

    def test_note_reaches_result(self):
        from alchemy.engines import solubility as SLB

        result = SLB.solubility_pure_water("ZnS")
        self.assertTrue(any("сфалерит" in text.lower()
                            for text in result.assumptions))


if __name__ == "__main__":
    unittest.main()
