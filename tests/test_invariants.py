# -*- coding: utf-8 -*-
"""Инвариантные тесты: законы, которые обязаны выполняться на любом входе.

Отличие от обычных тестов программы: здесь не проверяется «функция
вернула такое-то число». Проверяются свойства, которые держатся
независимо от реализации: сохранение заряда и атомов, согласованность
двух путей к одной величине, поведение на границах, обратимость.

Смысл: обычный тест закрепляет формулу, написанную автором. Если
формула неверна, тест зелёный. Инвариант проверяет закон, поэтому
ловит ошибки, которых автор не ожидал.
"""

import math
import unittest

from alchemy.core import formula as F
from alchemy.data import acids as ADB
from alchemy.engines import acidbase as AB
from alchemy.engines import activity_pitzer as AP
from alchemy.engines import balancer as BAL
from alchemy.engines import electrochemistry as EC
from alchemy.engines import gases as GA
from alchemy.engines import ioniceq as IE
from alchemy.engines import oxidation as OX
from alchemy.engines import solubility as SLB
from alchemy.engines import stoichiometry as ST
from alchemy.engines import thermo as TH


def states(formula: str) -> dict[str, float]:
    """Степени окисления по элементам."""
    rows = OX.oxidation_states(formula).value
    result = {}
    for row in rows:
        symbol = row["Элемент"].split()[0]
        result[symbol] = float(row["Степень окисления"].replace("+", ""))
    return result


class TestChargeConservation(unittest.TestCase):
    """Заряд не исчезает и не появляется."""

    def test_oxidation_states_sum_is_charge(self):
        """Сумма степеней окисления равна заряду частицы."""
        cases = [
            ("H2O", 0), ("NaCl", 0), ("H2SO4", 0), ("KMnO4", 0),
            ("Na2CO3", 0), ("Ca(OH)2", 0), ("Fe2O3", 0), ("NH3", 0),
            ("SO4^2-", -2), ("NO3^-", -1), ("NH4^+", 1), ("PO4^3-", -3),
        ]
        for formula, charge in cases:
            with self.subTest(formula=formula):
                parsed = F.parse(formula)
                total = sum(
                    count * states(formula)[element]
                    for element, count in parsed.counts.items())
                self.assertAlmostEqual(
                    total, charge, places=6,
                    msg=f"{formula}: сумма {total}, заряд {charge}")

    def test_ionic_equation_charge_balances(self):
        """Сокращённое ионное уравнение сходится по заряду."""
        cases = [
            "NaOH + HCl = NaCl + H2O",
            "2Al + 6HCl = 2AlCl3 + 3H2",
            "Fe + CuSO4 = FeSO4 + Cu",
            "CaCO3 + 2HCl = CaCl2 + CO2 + H2O",
        ]
        for equation in cases:
            with self.subTest(equation=equation):
                net = IE.ionic_equation(equation).value
                left, _, right = net.partition("=")
                self.assertEqual(self._charge(left), self._charge(right),
                                 f"{equation}: {net}")

    @staticmethod
    def _terms(side: str) -> list[str]:
        """Разбить сторону уравнения, не ломая запись заряда «H^+»."""
        stripped = side.replace("^+", "\u0001").replace("^2+", "\u0002") \
                       .replace("^3+", "\u0003")
        parts = [part.strip() for part in stripped.split("+")]
        return [part.replace("\u0001", "^+").replace("\u0002", "^2+")
                    .replace("\u0003", "^3+") for part in parts if part.strip()]

    @classmethod
    def _charge(cls, side: str) -> int:
        total = 0
        for term in cls._terms(side):
            body = term.lstrip("0123456789")
            coefficient = term[:len(term) - len(body)] or "1"
            total += F.parse(body).charge * int(coefficient)
        return total


class TestAtomConservation(unittest.TestCase):
    """Атомы не исчезают при уравнивании."""

    def test_balance_preserves_atoms(self):
        cases = [
            "H2 + O2 = H2O",
            "Fe + O2 = Fe2O3",
            "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O",
            "C3H8 + O2 = CO2 + H2O",
            "Na2CO3 + HCl = NaCl + CO2 + H2O",
        ]
        for equation in cases:
            with self.subTest(equation=equation):
                balanced = BAL.balance(equation).value
                left, _, right = balanced.partition("→")
                self.assertEqual(self._counts(left), self._counts(right),
                                 balanced)

    @staticmethod
    def _counts(side: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for term in TestChargeConservation._terms(side):
            if not term:
                continue
            body = term.lstrip("0123456789")
            coefficient = int(term[:len(term) - len(body)] or 1)
            parsed = F.parse(body)
            for element, count in parsed.counts.items():
                result[element] = result.get(element, 0) + count * coefficient
        return result

    def test_is_balanced_accepts_balanced(self):
        for equation in ("2H2 + O2 = 2H2O", "CH4 + 2O2 = CO2 + 2H2O",
                         "Fe + S = FeS", "H2 + O2 = H2O2"):
            with self.subTest(equation=equation):
                self.assertTrue(BAL.is_balanced(equation), equation)

    def test_is_balanced_rejects_proportional(self):
        """Пропорционально неуравненное — не уравнено."""
        for equation in ("2H2 + O2 = H2O", "H2 + O2 = H2O",
                         "CH4 + O2 = CO2 + H2O"):
            with self.subTest(equation=equation):
                self.assertFalse(BAL.is_balanced(equation), equation)


class TestWaterEquilibrium(unittest.TestCase):
    """pH + pOH = pKw при любой температуре."""

    def test_sum_equals_pkw(self):
        """pH кислоты + pH основания той же концентрации = pKw(T)."""
        for temperature in (273.15, 283.15, 298.15, 323.15, 348.15, 373.15):
            with self.subTest(t=temperature):
                pkw = ADB.pkw_at(temperature)
                acid = AB.strong_acid_ph(0.01, temperature_k=temperature,
                                         include_activity=False).numeric()
                base = AB.strong_base_ph(0.01, temperature_k=temperature,
                                         include_activity=False).numeric()
                self.assertAlmostEqual(acid + base, pkw, places=6)

    def test_strong_acid_limit(self):
        """При разбавлении pH сильной кислоты стремится к pKw/2, а не к 0."""
        for concentration in (1e-6, 1e-7, 1e-8):
            with self.subTest(c=concentration):
                ph = AB.strong_acid_ph(concentration,
                                       include_activity=False).numeric()
                # при 1e-6 М pH чуть ниже 6, при 1e-8 — около 7
                self.assertGreater(ph, 5.9)
                self.assertLess(ph, 7.1)

    def test_strong_acid_and_base_symmetry(self):
        """pH кислоты и основания одной концентрации дополняют друг друга."""
        for concentration in (0.001, 0.01, 0.1):
            with self.subTest(c=concentration):
                acid = AB.strong_acid_ph(concentration,
                                         include_activity=False).numeric()
                base = AB.strong_base_ph(concentration,
                                         include_activity=False).numeric()
                pkw = ADB.pkw_at(298.15)
                self.assertAlmostEqual(acid + base, pkw, places=6)


class TestAcidBaseLimits(unittest.TestCase):
    def test_activity_tends_to_one(self):
        """Коэффициент активности стремится к 1 при I → 0."""
        far = abs(AP.Davies_gamma(1, 1e-9) - 1.0)
        near = abs(AP.Davies_gamma(1, 1e-12) - 1.0)
        self.assertLess(far, 1e-3)
        self.assertLess(near, far)          # ближе к нулю — ближе к единице
        self.assertLess(near, 1e-5)

    def test_dilution_raises_ph(self):
        """Разбавление кислоты повышает pH."""
        previous = None
        for concentration in (0.1, 0.01, 0.001, 0.0001):
            ph = AB.strong_acid_ph(concentration,
                                   include_activity=False).numeric()
            if previous is not None:
                self.assertGreater(ph, previous)
            previous = ph

    def test_weak_acid_ph_between_limits(self):
        """pH слабой кислоты лежит между сильной кислотой и водой."""
        concentration = 0.1
        strong = AB.strong_acid_ph(concentration,
                                   include_activity=False).numeric()
        weak = AB.weak_acid_ph(concentration, 1.75e-5,
                               include_activity=False).numeric()
        self.assertGreater(weak, strong)
        self.assertLess(weak, 7.0)

    def test_buffer_equal_concentrations(self):
        """При равных концентрациях буфер даёт pKa."""
        result = AB.buffer_ph("CH3COOH", 0.1, 0.1, include_activity=False)
        self.assertAlmostEqual(result.numeric(), 4.757, places=2)


class TestActivityMonotonicity(unittest.TestCase):
    def test_gamma_decreases_with_ionic_strength(self):
        """На малых ионных силах γ падает с ростом I."""
        previous = 1.0
        for ionic in (0.001, 0.01, 0.05, 0.1):
            gamma = AP.Davies_gamma(1, ionic)
            self.assertLess(gamma, previous)
            previous = gamma

    def test_pitzer_tends_to_one(self):
        """При стремлении моляльности к нулю γ стремится к 1."""
        for molality, delta in ((1e-5, 0.005), (1e-4, 0.02), (1e-3, 0.05)):
            with self.subTest(m=molality):
                gamma = AP.mean_activity_coefficient("Na+", "Cl-", molality)
                self.assertAlmostEqual(gamma, 1.0, delta=delta)


class TestSolubilityInvariants(unittest.TestCase):
    def test_one_to_one_is_sqrt(self):
        """Для соли 1:1 растворимость равна корню из Ksp."""
        for salt in ("AgCl", "AgBr", "BaSO4"):
            with self.subTest(salt=salt):
                from alchemy.data import solubility as SDB

                ksp = SDB.find_solid(salt).Ksp
                s = SLB.solubility_pure_water(salt).numeric()
                self.assertAlmostEqual(s / math.sqrt(ksp), 1.0, places=2)

    def test_two_to_one_formula(self):
        """Для соли 2:1 s = (Ksp/4)^(1/3)."""
        from alchemy.data import solubility as SDB

        ksp = SDB.find_solid("Mg(OH)2").Ksp
        s = SLB.solubility_pure_water("Mg(OH)2").numeric()
        expected = (ksp / 4.0) ** (1.0 / 3.0)
        self.assertAlmostEqual(s / expected, 1.0, places=3)

    def test_alpha_between_zero_and_one(self):
        for ph in (0.0, 2.0, 5.0, 7.0, 10.0, 14.0):
            with self.subTest(ph=ph):
                alpha = SLB.alpha_unprotonated("CO3^2-", ph)
                self.assertGreater(alpha, 0.0)
                self.assertLessEqual(alpha, 1.0)

    def test_alpha_grows_with_ph(self):
        previous = 0.0
        for ph in (2.0, 4.0, 6.0, 8.0, 10.0, 12.0):
            alpha = SLB.alpha_unprotonated("CO3^2-", ph)
            self.assertGreater(alpha, previous)
            previous = alpha

    def test_acid_increases_solubility(self):
        neutral = SLB.solubility_at_ph("CaCO3", 8.0).numeric()
        acidic = SLB.solubility_at_ph("CaCO3", 4.0).numeric()
        self.assertGreater(acidic, neutral)


class TestThermoInvariants(unittest.TestCase):
    def test_gibbs_from_enthalpy_and_entropy(self):
        """ΔG = ΔH − T·ΔS."""
        equation = "C(тв) + O2 = CO2"
        enthalpy = TH.reaction_enthalpy(equation).numeric()
        entropy = TH.reaction_entropy(equation).numeric()
        gibbs = TH.reaction_gibbs(equation).numeric()
        expected = enthalpy - 298.15 * entropy / 1000.0
        self.assertAlmostEqual(gibbs, expected, delta=1.0)

    def test_hess_law_path_independence(self):
        """Одна и та же реакция двумя путями даёт одну энтальпию."""
        direct = TH.reaction_enthalpy("C(тв) + O2 = CO2").numeric()
        two_steps = (TH.reaction_enthalpy("C(тв) + 0.5O2 = CO").numeric()
                     + TH.reaction_enthalpy("CO + 0.5O2 = CO2").numeric())
        self.assertAlmostEqual(direct, two_steps, delta=2.0)

    def test_equilibrium_constant_positive(self):
        for equation in ("H2 + I2 = 2HI", "N2 + 3H2 = 2NH3"):
            with self.subTest(equation=equation):
                value = TH.equilibrium_constant_from_reaction(equation).numeric()
                self.assertGreater(value, 0.0)


class TestGasInvariants(unittest.TestCase):
    def test_ideal_gas_limit(self):
        """При малом давлении Ван-дер-Ваальс совпадает с идеальным газом."""
        pressure = 0.001
        ideal = GA.ideal_gas(pressure=pressure, temperature=298.15,
                             moles=1.0).numeric()
        real = GA.van_der_waals(gas="CO2", pressure=pressure,
                                temperature=298.15, moles=1.0).numeric()
        self.assertAlmostEqual(real / ideal, 1.0, delta=0.01)

    def test_volume_grows_with_temperature(self):
        previous = 0.0
        for temperature in (250.0, 300.0, 350.0, 400.0):
            volume = GA.ideal_gas(pressure=1.0, temperature=temperature,
                                  moles=1.0).numeric()
            self.assertGreater(volume, previous)
            previous = volume

    def test_boyle(self):
        """P·V постоянно при изотерме."""
        first = GA.boyle(p1=1.0, v1=10.0, p2=2.0).numeric()
        self.assertAlmostEqual(first * 2.0, 10.0, places=6)


class TestStoichiometryInvariants(unittest.TestCase):
    def test_yield_not_above_hundred(self):
        result = ST.percent_yield(actual=1.0, theoretical=2.0).numeric()
        self.assertLessEqual(result, 100.0)

    def test_limiting_reagent(self):
        """Расчёт по реагенту, которого не хватает."""
        result = ST.limiting_reagent("2H2 + O2 = 2H2O", {"H2": 4.0, "O2": 1.0})
        text = str(result.value).lower()
        self.assertIn("o2", text)

    def test_mass_not_created(self):
        """Масса продукта не больше массы реагентов."""
        product = ST.theoretical_yield("Fe2O3 + 3CO = 2Fe + 3CO2",
                                       1.0, "Fe2O3", "Fe").numeric()
        mass_fe2o3 = F.parse("Fe2O3").molar_mass
        self.assertLess(product, mass_fe2o3)


class TestElectrochemistryInvariants(unittest.TestCase):
    def test_nernst_at_unit_activity(self):
        """При активности 1 уравнение Нернста даёт стандартный потенциал."""
        result = EC.nernst_potential(e0=0.34, n=2, oxidized=1.0,
                                     reduced=1.0)
        self.assertAlmostEqual(result.numeric(), 0.34, places=3)

    def test_nernst_slope_grows_with_temperature(self):
        """Наклон Нернста растёт с температурой."""
        previous = None
        for temperature in (280.0, 298.15, 320.0, 350.0):
            result = EC.nernst_potential(
                e0=0.0, n=1, oxidized=1.0, reduced=0.1,
                temperature_k=temperature)
            drop = abs(result.numeric())
            if previous is not None:
                self.assertGreater(drop, previous)
            previous = drop

    def test_faraday_mass_proportional_to_charge(self):
        """Масса по Фарадею пропорциональна заряду."""
        first = EC.faraday_mass(current_a=1.0, time_s=1000, n=2,
                                molar_mass_value=63.546).numeric()
        second = EC.faraday_mass(current_a=1.0, time_s=2000, n=2,
                                 molar_mass_value=63.546).numeric()
        self.assertAlmostEqual(second / first, 2.0, places=3)


class TestParserInvariants(unittest.TestCase):
    def test_round_trip(self):
        """Разбор и обратная печать устойчивы."""
        for text in ("H2O", "H2SO4", "Ca(OH)2", "CuSO4*5H2O",
                     "[Cu(NH3)4]SO4", "K3[Fe(CN)6]"):
            with self.subTest(text=text):
                first = F.parse(text)
                second = F.parse(str(first))
                self.assertEqual(first.counts, second.counts)
                self.assertEqual(first.charge, second.charge)

    def test_molar_mass_additive(self):
        """Молярная масса гидрата аддитивна."""
        salt = F.parse("CuSO4").molar_mass
        water = F.parse("H2O").molar_mass
        hydrate = F.parse("CuSO4*5H2O").molar_mass
        self.assertAlmostEqual(hydrate, salt + 5 * water, places=2)

    def test_charge_composition_additivity(self):
        """Заряд суммы равен сумме зарядов частей."""
        parts = ["Na^+", "Cl^-"]
        total = sum(F.parse(part).charge for part in parts)
        self.assertEqual(total, 0)


if __name__ == "__main__":
    unittest.main()

class TestUnitConversion(unittest.TestCase):
    """Единицы: обратимость, транзитивность, запрет чужих размерностей."""

    def test_round_trip(self):
        from alchemy.core import units as U

        for value, first, second in ((1.0, "кг", "г"), (2.5, "л", "мл"),
                                     (0.5, "км", "м")):
            with self.subTest(unit=first):
                forward = U.convert(value, first, second)
                back = U.convert(forward, second, first)
                self.assertAlmostEqual(back / value, 1.0, places=6)

    def test_transitivity(self):
        """Через промежуточную единицу — тот же результат."""
        from alchemy.core import units as U

        direct = U.convert(1.0, "кг", "мг")
        stepwise = U.convert(U.convert(1.0, "кг", "г"), "г", "мг")
        self.assertAlmostEqual(direct / stepwise, 1.0, places=6)

    def test_unknown_unit_rejected(self):
        """Неизвестная единица отклоняется, даже если она «та же самая»."""
        from alchemy.core import units as U

        with self.assertRaises(U.UnitError):
            U.convert(1.0, "попугай", "попугай")

    def test_different_dimensions_rejected(self):
        from alchemy.core import units as U

        with self.assertRaises(U.UnitError):
            U.convert(1.0, "кг", "л")


class TestBalanceCoefficients(unittest.TestCase):
    """Коэффициенты взаимно просты, и balance согласован с is_balanced."""

    def test_gcd_is_one(self):
        cases = ["H2 + O2 = H2O", "Fe + O2 = Fe2O3",
                 "C3H8 + O2 = CO2 + H2O", "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O"]
        for equation in cases:
            with self.subTest(equation=equation):
                result = BAL.balance(equation)
                values = list(result.meta["coefficients"].values())
                divisor = values[0]
                for value in values[1:]:
                    divisor = math.gcd(divisor, value)
                self.assertEqual(divisor, 1, result.value)

    def test_balance_then_is_balanced(self):
        for equation in ("H2 + O2 = H2O", "C3H8 + O2 = CO2 + H2O",
                         "NaOH + H2SO4 = Na2SO4 + H2O"):
            with self.subTest(equation=equation):
                balanced = BAL.balance(equation).value
                self.assertTrue(BAL.is_balanced(balanced))


class TestRedoxElectronBalance(unittest.TestCase):
    """Сколько электронов отдано — столько и принято."""

    def test_electrons_match(self):
        """Сумма отданных электронов равна сумме принятых."""
        from alchemy.engines import redox as RX

        for equation in ("Zn + 2HCl = ZnCl2 + H2",
                         "2Al + 6HCl = 2AlCl3 + 3H2",
                         "Fe + CuSO4 = FeSO4 + Cu",
                         "2Na + Cl2 = 2NaCl"):
            with self.subTest(equation=equation):
                rows = RX.electron_balance(equation).value
                self.assertTrue(rows, equation)
                given = sum(int(row["Электронов"]) for row in rows
                            if "отдаёт" in row["Действие"])
                taken = sum(int(row["Электронов"]) for row in rows
                            if "принимает" in row["Действие"])
                self.assertEqual(given, taken, f"{equation}: {given} ≠ {taken}")


class TestThermoDirection(unittest.TestCase):
    """Разворот реакции меняет знак энтальпии."""

    def test_enthalpy_sign_changes(self):
        forward = TH.reaction_enthalpy("C(тв) + O2 = CO2").numeric()
        backward = TH.reaction_enthalpy("CO2 = C(тв) + O2").numeric()
        self.assertAlmostEqual(forward, -backward, delta=1.0)

    def test_equilibrium_constant_from_gibbs(self):
        """K = exp(−ΔG/(RT)): при ΔG = 0 константа равна единице."""
        value = TH.equilibrium_constant(0.0).numeric()
        self.assertAlmostEqual(value, 1.0, places=6)


class TestEquilibriumShift(unittest.TestCase):
    """Принцип Ле Шателье: направление сдвига при изменении температуры."""

    def test_endothermic_shifts_right_on_heating(self):
        from alchemy.engines import equilibrium as EQ

        result = EQ.shift_single("N2 + 3H2 = 2NH3", "температура", "increase")
        text = (str(result.value) + " " + " ".join(result.steps)).lower()
        # синтез аммиака экзотермичен: нагревание смещает влево
        self.assertIn("влево", text)

    def test_pressure_shifts_to_fewer_moles(self):
        from alchemy.engines import equilibrium as EQ

        result = EQ.shift_single("N2 + 3H2 = 2NH3", "давление", "increase")
        text = (str(result.value) + " " + " ".join(result.steps)).lower()
        self.assertIn("вправо", text)


class TestSolutionMass(unittest.TestCase):
    """Масса раствора складывается из массы вещества и растворителя."""

    def test_mass_additivity(self):
        from alchemy.engines import solutions as SO

        solution = SO.from_mass_fraction("NaCl", 10.0, solution_mass=200.0)
        self.assertAlmostEqual(solution.solute_mass + solution.solvent_mass,
                               solution.total_mass, places=6)

    def test_dilution_keeps_amount(self):
        from alchemy.engines import solutions as SO

        result = SO.dilution(c_initial=2.0, v_initial=0.1,
                             v_final=1.0).numeric()
        self.assertAlmostEqual(result * 1.0, 2.0 * 0.1, places=6)
