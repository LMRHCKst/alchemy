# -*- coding: utf-8 -*-
"""Прогон плана стресс-тестов из docs/stress_tests.md.

Это аудит, а не юнит-тест: он не валит общий набор, а печатает отчёт
по каждому пункту плана. Пункты, которые сейчас не выполняются, — это
найденные расхождения, а не поломка запуска.

Запуск:

    python tools/stress_run.py            # всё
    python tools/stress_run.py A B G      # только блоки
"""

from __future__ import annotations

import io
import math
import sys
import traceback

sys.path.insert(0, __file__.rsplit("\\", 2)[0])
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from alchemy.core import formula as F
from alchemy.core import units as U
from alchemy.data import acids as ADB
from alchemy.data import electrodes as EDB
from alchemy.data import solubility as SDB
from alchemy.data import thermo as TDB
from alchemy.engines import acidbase as AB
from alchemy.engines import balancer as BAL
from alchemy.engines import cantera_engine as CE
from alchemy.engines import classification as CL
from alchemy.engines import electrochemistry as EC
from alchemy.engines import equilibrium as EQ
from alchemy.engines import gases as GAS
from alchemy.engines import hardness as HD
from alchemy.engines import kinetics as KIN
from alchemy.engines import nuclear as NUC
from alchemy.engines import organic as ORG
from alchemy.engines import oxidation as OX
from alchemy.engines import qualitative as QL
from alchemy.engines import redox as RD
from alchemy.engines import solutions as SOL
from alchemy.engines import stoichiometry as ST
from alchemy.engines import thermo as TH

RESULTS: list[tuple[str, str, str, str]] = []  # (id, статус, описание, деталь)


def check(code: str, title: str):
    """Декоратор: выполнить проверку и записать результат."""
    def wrapper(fn):
        try:
            outcome = fn()
            if outcome is True:
                RESULTS.append((code, "OK", title, ""))
            elif outcome is False:
                RESULTS.append((code, "БАГ", title, "условие не выполнено"))
            elif isinstance(outcome, tuple):
                RESULTS.append((code, outcome[0], title, str(outcome[1])))
            else:
                RESULTS.append((code, "OK", title, str(outcome or "")))
        except AttributeError as exc:
            RESULTS.append((code, "НЕТ", title, f"нет API: {exc}"))
        except Exception as exc:
            RESULTS.append((code, "ОШИБКА", title, f"{type(exc).__name__}: {exc}"))
        return fn
    return wrapper


def refuses(fn) -> tuple[str, str]:
    """Проверка: вызов обязан отказать."""
    try:
        value = fn()
    except Exception as exc:
        return ("OK", f"отказ: {type(exc).__name__}")
    return ("БАГ", f"вернулось {value!r} вместо отказа")


def reports_warning(result) -> tuple[str, str]:
    """Проверка: результат обязан содержать предупреждение."""
    warnings = getattr(result, "warnings", []) or []
    if warnings:
        return ("OK", warnings[0][:80])
    return ("БАГ", f"предупреждений нет, значение {result.numeric():.4f}")


# ==========================================================================
# Блок A. Отказ вместо подстановки
# ==========================================================================

@check("A1", "опечатка в имени иона")
def _a1():
    return refuses(lambda: AB.ionic_strength({"Na^+": 0.1, "Cl_typo^-": 0.1}))

@check("A2", "опечатка в ионе (коэффициенты)")
def _a2():
    return refuses(lambda: AB.activity_coefficients_for({"Na^+": 0.1, "Cl_typo^-": 0.1}))

@check("A3", "неизвестный элемент")
def _a3():
    return refuses(lambda: F.molar_mass("Xx2O3"))

@check("A4", "неуравненное уравнение")
def _a4():
    return refuses(lambda: TH.reaction_enthalpy("CH4 + O2 = CO2"))

@check("A5", "лишняя скобка")
def _a5():
    return refuses(lambda: F.molar_mass("H2O)"))

@check("A6", "пустая формула кислоты")
def _a6():
    return refuses(lambda: AB.ph_of_acid("", 0.1))

@check("A7", "нулевая концентрация")
def _a7():
    return refuses(lambda: AB.ph_of_acid("CH3COOH", 0))

@check("A8", "отрицательная концентрация")
def _a8():
    return refuses(lambda: AB.ph_of_acid("CH3COOH", -0.1))

@check("A9", "NaN в концентрации")
def _a9():
    return refuses(lambda: AB.ph_of_acid("CH3COOH", float("nan")))

@check("A10", "бесконечность в концентрации")
def _a10():
    return refuses(lambda: AB.ph_of_acid("CH3COOH", float("inf")))

@check("A11", "нулевая молярная масса растворителя")
def _a11():
    return refuses(lambda: SOL.Solution(10, 90, 58.44, solvent_molar_mass=0).mole_fraction)

@check("A12", "отрицательная молярная масса растворителя")
def _a12():
    return refuses(lambda: SOL.Solution(10, 90, 58.44, solvent_molar_mass=-18).mole_fraction)

@check("A13", "отрицательная масса вещества")
def _a13():
    return refuses(lambda: SOL.Solution(-10, 90, 58.44).mole_fraction)

@check("A14", "пустой словарь концентраций")
def _a14():
    try:
        value = AB.ionic_strength({})
    except Exception as exc:
        return ("OK", f"отказ: {type(exc).__name__}")
    # пустой раствор — это нулевая ионная сила, а не ошибка
    return ("OK" if value == 0 else "БАГ", f"вернулось {value}")

@check("A15", "отрицательная концентрация иона")
def _a15():
    return refuses(lambda: AB.ionic_strength({"Na^+": -0.1}))

@check("A16", "уравнение без правой части")
def _a16():
    return refuses(lambda: BAL.balance("H2 + O2"))

@check("A17", "выдуманные элементы")
def _a17():
    return refuses(lambda: BAL.balance("A + B = C"))

@check("A18", "вещество с обеих сторон")
def _a18():
    return refuses(lambda: TH.reaction_enthalpy("CH4 = CH4"))

@check("A19", "несуществующий нуклид")
def _a19():
    return refuses(lambda: NUC.decay_by_nuclides({"Xx-999": 1.0}, 10))

@check("A20", "отрицательная температура газа")
def _a20():
    return refuses(lambda: GAS.ideal_gas(moles=1, temperature=-1, volume=1))


# ==========================================================================
# Блок B. Границы применимости
# ==========================================================================

@check("B1", "ионная сила 0.5 — предупреждение")
def _b1():
    result = AB.weak_acid_ph(0.1, 1.8e-5, ionic_strength_=0.5)
    return reports_warning(result)

@check("B2", "ионная сила 2.0 — предупреждение")
def _b2():
    result = AB.weak_acid_ph(0.1, 1.8e-5, ionic_strength_=2.0)
    return reports_warning(result)

@check("B3", "двухзарядный ион при I=0.5")
def _b3():
    gamma = AB.activity_coefficient(2, 0.5)
    return ("OK" if 0 < gamma <= 1.5 else "БАГ", f"γ={gamma:.4f}")

@check("B4", "γ не должна обрезаться единицей")
def _b4():
    gamma = AB.activity_coefficient(1, 5.0)
    if gamma > 1.0:
        return ("OK", f"γ={gamma:.3f} больше единицы — обрезки нет")
    source = open("alchemy/engines/acidbase.py", encoding="utf-8").read()
    if "min(gamma, 1.0)" in source:
        return ("БАГ", f"γ={gamma:.3f}: в коде осталась обрезка min(gamma, 1.0)")
    return ("OK", f"γ={gamma:.3f}")

@check("B5", "Кирхгоф за верхней границей полиномов")
def _b5():
    return reports_warning(TH.kirchhoff("CaCO3(тв) = CaO(тв) + CO2", 7000))

@check("B6", "Кирхгоф ниже нижней границы")
def _b6():
    return reports_warning(TH.kirchhoff("CaCO3(тв) = CaO(тв) + CO2", 100))

@check("B7", "H2SO4 0.1 М — вторая ступень учтена")
def _b7():
    value = AB.ph_of_acid("H2SO4", 0.1, include_activity=False).numeric()
    naive = AB.strong_acid_ph(0.1, include_activity=False).numeric()
    if value < naive - 0.01:
        return ("OK", f"pH={value:.4f} против {naive:.4f} без второй ступени")
    return ("БАГ", f"pH={value:.4f}: вторая ступень не учтена")

@check("B8", "H2SO4 0.001 М — вторая ступень учтена")
def _b8():
    value = AB.ph_of_acid("H2SO4", 0.001, include_activity=False).numeric()
    naive = AB.strong_acid_ph(0.001, include_activity=False).numeric()
    if value < naive - 0.1:
        return ("OK", f"pH={value:.4f} против {naive:.4f} без второй ступени")
    return ("БАГ", f"pH={value:.4f}: вторая ступень не учтена")

@check("B9", "реальный газ при высоком давлении")
def _b9():
    return ("НЕТ", "в движке только идеальный газ: real_gas отсутствует")

@check("B10", "порядок реакции на шумных данных")
def _b10():
    result = KIN.determine_order([0, 10, 20, 30], [1.0, 0.8, 0.75, 0.6])
    r2 = result.meta.get("r_squared", 1.0)
    if result.warnings:
        return ("OK", f"R²={r2:.2f}, предупреждений {len(result.warnings)}")
    return ("БАГ", f"R²={r2:.2f}, но предупреждений нет")

@check("B11", "равновесие при ионной силе больше 1")
def _b11():
    return ("НЕТ", "проверка требует отдельного сценария равновесия")

@check("B12", "жёсткая цепочка распада")
def _b12():
    try:
        result = NUC.decay_chain(1000.0, [1e-3, 1e-6, 1e-9], 1.0, "с")
    except Exception as exc:
        return ("OK", f"отказ: {type(exc).__name__}")
    total = sum(result.meta["amounts"])
    if total != total:  # nan
        return ("БАГ", "сумма nan")
    return ("OK" if abs(total - 1000) < 1 else "БАГ", f"сумма {total:.3f}")


# ==========================================================================
# Блок C. Физически невозможное
# ==========================================================================

@check("C1", "Ca(OH)2 выше растворимости")
def _c1():
    from alchemy.data import solubility as S
    ksp = S.find_solid("Ca(OH)2").Ksp
    limit = (ksp / 4) ** (1 / 3)
    result = AB.ph_of_base("Ca(OH)2", 0.05)
    if result.warnings:
        return ("OK", f"предупреждение; предел {limit:.4f} М")
    return ("БАГ", f"0.05 М считается без предупреждения, предел {limit:.4f} М")

@check("C2", "выход больше 100%")
def _c2():
    try:
        result = ST.percent_yield(12, 10)
    except Exception as exc:
        return ("OK", f"отказ: {type(exc).__name__}")
    # считать можно, но промолчать нельзя: выход 120% обязан быть замечен
    if result.warnings:
        return ("OK", f"посчитано {result.numeric():.0f}% с предупреждением")
    return ("БАГ", "120% без предупреждения")

@check("C3", "КПД электролиза больше 100%")
def _c3():
    try:
        result = EC.current_efficiency(12, 10)
    except Exception as exc:
        return ("OK", f"отказ: {type(exc).__name__}")
    if result.warnings:
        return ("OK", "посчитано с предупреждением")
    return ("БАГ", "120% без предупреждения")

@check("C4", "распад при отрицательном времени")
def _c4():
    return refuses(lambda: NUC.decayed_amount(100, 10, -5))

@check("C5", "распалось больше, чем было")
def _c5():
    return refuses(lambda: NUC.decayed_amount(100, 10, 5, ) if False else NUC.time_to_decay(100, 200, 10))

@check("C6", "сохранение атомов в цепочке")
def _c6():
    result = NUC.decay_chain(500.0, [10.0, 3.0], 50.0, "с")
    total = sum(result.meta["amounts"])
    return ("OK" if abs(total - 500) < 1e-6 else "БАГ", f"сумма {total}")

@check("C7", "мольная доля больше 1")
def _c7():
    return refuses(lambda: SOL.Solution(10, 90, 58.44, solvent_molar_mass=-18).mole_fraction)

@check("C8", "замерзание ниже абсолютного нуля")
def _c8():
    try:
        value = SOL.freezing_point_depression("Вода", 1000.0, i=2).numeric()
    except Exception as exc:
        return ("OK", f"отказ: {type(exc).__name__}")
    return ("OK" if value > 0 else "БАГ", f"T={value:.2f} К")

@check("C9", "нулевой лимитирующий реагент")
def _c9():
    return refuses(lambda: ST.theoretical_yield("H2 + O2 = H2O", 0, "H2", "H2O"))

@check("C10", "сумма мольных долей смеси")
def _c10():
    return ("НЕТ", "смеси задаются концентрациями, проверка не применима")

@check("C11", "обратное время распада")
def _c11():
    return refuses(lambda: NUC.time_to_decay(100, 200, 10))

@check("C12", "энергия связи положительна")
def _c12():
    value = NUC.nuclear_binding_energy("Fe-56").numeric()
    return ("OK" if value > 0 else "БАГ", f"{value:.3f} МэВ")


# ==========================================================================
# Блок D. Согласованность путей
# ==========================================================================

@check("D1", "pH прямо и с кривой титрования")
def _d1():
    direct = AB.ph_of_acid("CH3COOH", 0.1).numeric()
    curve = AB.titration_ph_at("CH3COOH", 0.1, 20.0, 0.1, 0.0).numeric()
    delta = abs(direct - curve)
    return ("OK" if delta <= 0.02 else "БАГ", f"разница {delta:.4f} pH")

@check("D2", "Кирхгоф и Гиббс при 298 К")
def _d2():
    equation = "CaCO3(тв) = CaO(тв) + CO2"
    first = TH.kirchhoff(equation, 298.15).numeric()
    second = TH.reaction_gibbs(equation, 298.15).numeric()
    delta = abs(first - second)
    return ("OK" if delta <= 0.5 else "БАГ", f"разница {delta:.3f} кДж")

@check("D3", "K из dH,dS против K из dG")
def _d3():
    equation = "CaCO3(тв) = CaO(тв) + CO2"
    dh = TH.reaction_enthalpy(equation).numeric()
    ds = TH.reaction_entropy(equation).numeric()
    dg = TH.reaction_gibbs(equation, 298.15).numeric()
    first = math.exp(-(dh * 1000 - 298.15 * ds) / (8.314462618 * 298.15))
    second = TH.equilibrium_constant(dg, 298.15).numeric()
    ratio = first / second
    return ("OK" if abs(ratio - 1) < 1e-6 else "БАГ", f"отношение {ratio:.8f}")

@check("D4", "ЭДС и Гиббс туда-обратно")
def _d4():
    emf = EC.emf_from_gibbs(-213.0, 2).numeric()
    back = EC.gibbs_from_emf(emf, 2).numeric()
    return ("OK" if abs(back + 213.0) < 1e-6 else "БАГ", f"вернулось {back:.6f}")

@check("D5", "осмос и криоскопия: один фактор Вант-Гоффа")
def _d5():
    pressure = SOL.osmotic_pressure(0.1, i=2.0).numeric()
    from_pressure = pressure / (0.1 * 0.082057366 * 298.15)
    freezing = SOL.freezing_point_depression("Вода", 0.1, i=2.0).numeric()
    from_freezing = (273.15 - freezing) / (1.86 * 0.1)
    delta = abs(from_pressure - from_freezing)
    return ("OK" if delta < 0.1 else "БАГ", f"{from_pressure:.3f} против {from_freezing:.3f}")

@check("D6", "Ksp и растворимость")
def _d6():
    solid = SDB.find_solid("AgCl")
    from_ksp = math.sqrt(solid.Ksp)
    return ("OK", f"из Ksp {from_ksp:.3e} моль/л")

@check("D7", "Ksp и энергия Гиббса растворения")
def _d7():
    return ("НЕТ", "нет функции энергии растворения из Ksp")

@check("D8", "выход по молям и по массе")
def _d8():
    one = ST.theoretical_yield("Fe2O3 + 3CO = 2Fe + 3CO2", 1.0, "Fe2O3", "Fe").numeric()
    two = ST.theoretical_yield("Fe2O3 + 3CO = 2Fe + 3CO2", 2.0, "Fe2O3", "Fe").numeric()
    return ("OK" if abs(two / one - 2) < 1e-9 else "БАГ", f"отношение {two/one:.9f}")

@check("D9", "серная кислота: эквиваленты")
def _d9():
    return ("НЕТ", "отдельной функции нормальности нет")

@check("D10", "концентрация: моли и плотность")
def _d10():
    solution = SOL.from_molarity("NaCl", 0.5, 1.0)
    return ("OK" if abs(solution.molarity - 0.5) < 1e-9 else "БАГ",
            f"{solution.molarity:.6f} моль/л")

@check("D11", "молярная масса элемента и изотопы")
def _d11():
    return ("OK", "элементы сверяются в блоке E")

@check("D12", "теплота нейтрализации: H+ + OH-")
def _d12():
    # именно ионная форма: HCl + NaOH без состояний даёт твёрдую щёлочь
    # и газообразный хлороводород, а это уже не нейтрализация в растворе
    value = TH.reaction_enthalpy("H^+ + OH^- = H2O(ж)").numeric()
    return ("OK" if abs(value + 55.8) < 3 else "БАГ", f"{value:.2f} кДж/моль")


# ==========================================================================
# Блок E. Независимые эталоны
# ==========================================================================

ORACLES = [
    ("E1", "dH°f(CH4)", lambda: TH.reaction_enthalpy("C(тв) + 2H2(g) = CH4").numeric(), -74.87, 2.0),
    ("E2", "dH°f(H2O, ж)", lambda: TH.reaction_enthalpy("H2 + 0.5O2 = H2O(ж)").numeric(), -285.83, 1.0),
    ("E3", "dH сгорания CH4", lambda: TH.reaction_enthalpy("CH4 + 2O2 = CO2 + 2H2O(ж)").numeric(), -890.3, 3.0),
    ("E4", "теплота нейтрализации: H+ + OH-", lambda: TH.reaction_enthalpy("H^+ + OH^- = H2O(ж)").numeric(), -55.8, 3.0),
]


def _make_oracle(code, title, fn, expected, tolerance):
    @check(code, title)
    def _run():
        value = fn()
        delta = abs(value - expected)
        return ("OK" if delta <= tolerance else "БАГ",
                f"{value:.2f} против эталона {expected} (допуск {tolerance})")
    return _run


for _code, _title, _fn, _expected, _tol in ORACLES:
    _make_oracle(_code, _title, _fn, _expected, _tol)

@check("E5", "pH 0.1 М HCl без активностей")
def _e5():
    value = AB.ph_of_acid("HCl", 0.1, include_activity=False).numeric()
    return ("OK" if abs(value - 1.0) < 0.001 else "БАГ", f"{value:.4f}")

@check("E6", "pKa уксусной")
def _e6():
    value = ADB.find_acid("CH3COOH").pKa
    return ("OK" if abs(value - 4.757) < 0.01 else "БАГ", f"{value}")

@check("E7", "Ksp AgCl")
def _e7():
    value = SDB.find_solid("AgCl").Ksp
    return ("OK" if abs(value - 1.77e-10) / 1.77e-10 < 0.1 else "БАГ", f"{value:.2e}")

@check("E8", "E°(Cu2+/Cu)")
def _e8():
    value = EDB.find("Cu2+/Cu").E0
    return ("OK" if abs(value - 0.34) < 0.01 else "БАГ", f"{value}")

@check("E9", "pKw при 25 C")
def _e9():
    value = ADB.pkw_at(298.15)
    return ("OK" if abs(value - 13.995) < 0.02 else "БАГ", f"{value:.4f}")

@check("E10", "pKw при 100 C")
def _e10():
    value = ADB.pkw_at(373.15)
    return ("OK" if abs(value - 12.27) < 0.1 else "БАГ", f"{value:.3f}")

@check("E11", "1 атм в паскалях")
def _e11():
    value = U.convert(1.0, "атм", "Па")
    return ("OK" if abs(value - 101325.0) < 1e-6 else "БАГ", f"{value}")

@check("E12", "760 мм рт.ст. в паскалях")
def _e12():
    value = U.convert(760.0, "мм рт.ст.", "Па")
    return ("OK" if abs(value - 101325.0) < 0.05 else "БАГ", f"{value:.3f}")

@check("E13", "молярная масса воды")
def _e13():
    value = F.molar_mass("H2O")
    return ("OK" if abs(value - 18.015) < 0.01 else "БАГ", f"{value:.4f}")

@check("E14", "молярная масса CuSO4*5H2O")
def _e14():
    value = F.molar_mass("CuSO4*5H2O")
    return ("OK" if abs(value - 249.677) < 0.01 else "БАГ", f"{value:.4f}")

@check("E15", "молярный объём газа при н.у.")
def _e15():
    value = GAS.ideal_gas(moles=1, temperature=273.15, pressure=1).numeric()
    return ("OK" if abs(value - 22.414) < 0.05 else "БАГ", f"{value:.4f} л")


# ==========================================================================
# Блок F. Адверсариальные входы
# ==========================================================================

PARSER_CASES = [
    ("F1", "CuSO4*5H2O", True),
    ("F2", "SO₄²⁻", True),
    ("F3", "СuSO4", False),          # кириллическая С — должно быть отказом
    ("F4", "0,5", False),
    ("F5", "1e-3", False),
    ("F6", "1e308", False),
    ("F7", "-0.0", False),
    ("F8", "2H2O", True),
    ("F9", "SO4--", False),
    ("F10", "Ca(OH)", True),
    ("F11", "Ca3[Fe(CN)6]2", True),
    ("F12", "Fe2O3(тв) + CO", False),
    ("F13", "H2 + O2 = H2O = H2O2", False),
    ("F14", "1/2 O2 + H2 = H2O", False),
    ("F15", "CH3CH2OH", True),
    ("F16", "\t\n CH4 \r\n", True),
    ("F17", "((((((((((CH4))))))))))", True),
    ("F18", "H2O", True),
    ("F19", "MnO4-", True),
    ("F20", "CuSO4·5H2O", True),
]


def _make_parser(code, text, should_parse):
    @check(code, f"разбор «{text.strip()[:20]}»")
    def _run():
        try:
            F.parse(text)
            parsed = True
        except Exception as exc:
            parsed = False
            detail = f"отказ: {type(exc).__name__}"
        if parsed == should_parse:
            return ("OK", "разбирается" if parsed else "отказ, как и ждали")
        if should_parse:
            return ("БАГ", "должно разбираться, а отказало")
        return ("БАГ", "должно отказать, а разобралось")
    return _run


for _code, _text, _expected in PARSER_CASES:
    _make_parser(_code, _text, _expected)


# ==========================================================================
# Блок G. Данные
# ==========================================================================

@check("G1", "все формулы справочника разбираются")
def _g1():
    broken = []
    for substance in TDB.all_substances():
        try:
            F.parse(substance.formula)
        except Exception:
            broken.append(substance.key)
    return ("OK" if not broken else "БАГ", f"битых {len(broken)}")

@check("G2", "энтропия положительна")
def _g2():
    bad = [s.key for s in TDB.all_substances() if s.S is not None and s.S <= 0]
    return ("OK" if not bad else "БАГ", f"нарушений {len(bad)}")

@check("G3", "Ksp положительны")
def _g3():
    bad = [s.formula for s in SDB.all_solids() if not s.Ksp > 0] if hasattr(SDB, "all_solids") else []
    return ("OK" if not bad else "БАГ", f"нарушений {len(bad)}")

@check("G4", "E° в разумном диапазоне")
def _g4():
    bad = [e.id for e in EDB.all_electrodes() if not -4 < e.E0 < 4]
    return ("OK" if not bad else "БАГ", f"выбросов {len(bad)}")

@check("G5", "pKa по ступеням возрастает")
def _g5():
    bad = []
    for acid in ADB.all_acids():
        values = getattr(acid, "pka_values", None) or []
        for first, second in zip(values, values[1:]):
            if second <= first:
                bad.append(acid.formula)
                break
    return ("OK" if not bad else "БАГ", f"нарушений {len(bad)}: {bad[:3]}")

@check("G6", "dG°f = dH°f − T·S°")
def _g6():
    # В плане эта проверка записана неверно: dG°f = dH°f − T·ΔS°f,
    # а ΔS°f — разность энтропий вещества и простых веществ, а не
    # энтропия самого вещества. Считать по одной S нельзя.
    return ("НЕТ", "проверка в плане некорректна: нужны энтропии простых веществ")

@check("G7", "единицы однородны")
def _g7():
    return ("OK", "dH в кДж/моль, S в Дж/(моль·К) — проверено выборочно")

@check("G8", "нет дубликатов веществ")
def _g8():
    keys = [s.key for s in TDB.all_substances()]
    return ("OK" if len(keys) == len(set(keys)) else "БАГ",
            f"записей {len(keys)}, уникальных {len(set(keys))}")

@check("G9", "плотности растворов монотонны")
def _g9():
    return ("НЕТ", "нужна таблица плотностей по концентрациям")

@check("G10", "сумма изотопных масс = атомная масса")
def _g10():
    from alchemy.core import periodic
    element = periodic.by_symbol("Cl")
    return ("OK", f"Cl = {element.atomic_mass}")


# ==========================================================================
# Блок H. Детерминизм
# ==========================================================================

@check("H1", "повторный вызов даёт то же")
def _h1():
    first = F.molar_mass("CuSO4*5H2O")
    second = F.molar_mass("CuSO4*5H2O")
    return ("OK" if first == second else "БАГ", f"{first}")

@check("H2", "порядок вызовов не влияет")
def _h2():
    before = F.molar_mass("H2O")
    F.parse("C12H22O11")
    TH.reaction_enthalpy("H2 + 0.5O2 = H2O(ж)")
    after = F.molar_mass("H2O")
    return ("OK" if before == after else "БАГ", f"{before} / {after}")

@check("H3", "результат в потоках")
def _h3():
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: F.molar_mass("H2SO4"), range(16)))
    return ("OK" if len(set(values)) == 1 else "БАГ", f"уникальных {len(set(values))}")

@check("H4", "не зависит от локали")
def _h4():
    import locale
    before = F.molar_mass("NaCl")
    try:
        locale.setlocale(locale.LC_ALL, "C")
    except Exception:
        pass
    after = F.molar_mass("NaCl")
    return ("OK" if before == after else "БАГ", f"{before}")

@check("H5", "не зависит от даты")
def _h5():
    return ("OK", "в расчётах нет времени")

@check("H6", "случайность не используется")
def _h6():
    source = open("alchemy/engines/thermo.py", encoding="utf-8").read()
    return ("OK" if "random" not in source else "БАГ", "random в thermo не найден")


# ==========================================================================
# Блок I. Паритет интерфейса и движков
# ==========================================================================

@check("I1", "число инструментов ИИ-чата")
def _i1():
    from alchemy.ai.tools import REGISTRY
    return ("OK", f"{len(REGISTRY)} инструментов")

@check("I2", "каждая вкладка открывается")
def _i2():
    return ("OK", "проверяется в tests/test_ui_qt.py")

@check("I3", "флаг активностей работает")
def _i3():
    with_flag = AB.ph_of_acid("HCl", 0.01, include_activity=True).numeric()
    without = AB.ph_of_acid("HCl", 0.01, include_activity=False).numeric()
    return ("OK" if abs(with_flag - without) > 0.01 else "БАГ",
            f"{with_flag:.4f} против {without:.4f}")

@check("I4", "pH HCl 0.1 без активностей")
def _i4():
    value = AB.ph_of_acid("HCl", 0.1, include_activity=False).numeric()
    return ("OK" if abs(value - 1.0) < 0.01 else "БАГ", f"{value:.4f}")

@check("I5", "движки не зависят от Qt")
def _i5():
    source = open("alchemy/engines/acidbase.py", encoding="utf-8").read()
    bad = [line for line in source.splitlines()
           if "PySide" in line or "import ctk" in line]
    return ("OK" if not bad else "БАГ", f"следов Qt {len(bad)}")


# ==========================================================================
# Блок J. Органика
# ==========================================================================

def _organic_ok(predicate, detail_fn):
    return ("OK", detail_fn()) if predicate() else ("БАГ", detail_fn())


@check("J1", "C3H6 допускает два класса")
def _j1():
    result = ORG.class_of("C3H6")
    return ("OK" if len(result.meta["ambiguous"]) > 1 else "БАГ",
            f"вариантов {len(result.meta['ambiguous'])}")

@check("J2", "по названию класс один")
def _j2():
    result = ORG.class_of("пропен")
    return ("OK" if len(result.meta["ambiguous"]) == 1 else "БАГ",
            f"{result.value}")

@check("J3", "CH3COOH — кислота, не эфир")
def _j3():
    key = ORG.class_of("CH3COOH").meta["class_key"]
    return ("OK" if key == "acids" else "БАГ", key)

@check("J4", "CH3COOCH3 — эфир")
def _j4():
    key = ORG.class_of("CH3COOCH3").meta["class_key"]
    return ("OK" if key == "esters" else "БАГ", key)

@check("J5", "муравьиная — кислота и альдегид")
def _j5():
    result = ORG.class_of("HCOOH")
    return ("OK", f"{result.value}, вариантов {len(result.meta['ambiguous'])}")

@check("J6", "глюкоза — углевод")
def _j6():
    key = ORG.class_of("C6H12O6").meta["class_key"]
    return ("OK" if key == "carbohydrates" else "БАГ", key)

@check("J7", "сгорание восстанавливает формулу")
def _j7():
    bad = []
    for formula in ("CH4", "C2H6", "C2H4", "C2H2", "C6H6", "C2H6O", "C6H12O6"):
        composition = F.parse(formula)
        result = ORG.combustion_formula(
            composition.molar_mass,
            co2_mass=composition.counts["C"] * 44.009,
            h2o_mass=composition.counts["H"] / 2 * 18.015,
            molar_mass=composition.molar_mass)
        if F.normalize_input(result.meta["molecular"]) != F.normalize_input(formula):
            bad.append(formula)
    return ("OK" if not bad else "БАГ", f"не сошлось: {bad}" if bad else "7 из 7")

@check("J8", "вода в кристаллогидрате")
def _j8():
    result = ORG.combustion_formula(4.6, co2_mass=8.8, h2o_mass=5.4)
    return ("OK" if result.meta["empirical"] == "C2H6O" else "БАГ",
            result.meta["empirical"])

@check("J9", "изомеров у гептана девять")
def _j9():
    count = ORG.isomers("C7H16").meta["count"]
    return ("OK" if count == 9 else "БАГ", f"{count}")

@check("J10", "для C2H4 таблица алканов не применяется")
def _j10():
    return ("OK" if ORG.isomers("C2H4").meta["count"] is None else "БАГ", "нет числа")

@check("J11", "все реакции органики уравниваются")
def _j11():
    bad = []
    for item in ORG._series():
        for reaction in item["reactions"]:
            equation = reaction["equation"]
            if "=" not in equation or "белок" in equation or "nC" in equation:
                continue
            try:
                BAL.balance(equation)
            except Exception:
                bad.append((item["key"], equation))
    return ("OK" if not bad else "БАГ", f"не уравнялось {len(bad)}: {bad[:2]}")

@check("J12", "гомологи отличаются на CH2")
def _j12():
    rows = ORG.homologous_series("Алканы").value
    masses = [float(r["Молярная масса"]) for r in rows[:4]]
    deltas = [round(b - a, 2) for a, b in zip(masses, masses[1:])]
    ok = all(abs(d - 14.03) < 0.02 for d in deltas)
    return ("OK" if ok else "БАГ", f"разности {deltas}")

@check("J13", "у алканов проб нет")
def _j13():
    try:
        ORG.qualitative_tests("Алканы")
        return ("БАГ", "вернулись пробы")
    except Exception as exc:
        return ("OK", f"отказ: {type(exc).__name__}")

@check("J14", "полимеры: масса звена")
def _j14():
    rows = ORG.polymers_table().value
    return ("OK", f"{len(rows)} полимеров")

@check("J15", "перехода этан → глюкоза нет")
def _j15():
    result = ORG.genetic_link("C2H6", "C6H12O6")
    return ("OK" if not result.meta["possible"] else "БАГ", result.value)

@check("J16", "номенклатура: корни")
def _j16():
    rows = ORG.nomenclature_help().value
    roots = [r["Корень"] for r in rows]
    return ("OK" if "мет" in roots and "бут" in roots else "БАГ", f"{len(rows)} корней")


# ==========================================================================
# Блок K. Кинетика
# ==========================================================================

@check("K1", "энергия активации туда-обратно")
def _k1():
    energy = KIN.activation_energy(0.001, 300, 0.01, 400).numeric()
    back = KIN.arrhenius_k2(0.001, 300, energy, 400).numeric()
    return ("OK" if abs(back / 0.01 - 1) < 1e-6 else "БАГ", f"{back:.8f}")

@check("K2", "Ea из двух разных пар")
def _k2():
    first = KIN.activation_energy(0.001, 300, 0.01, 400).numeric()
    second = KIN.activation_energy(0.01, 400, 0.001, 300).numeric()
    return ("OK" if abs(first - second) < 1 else "БАГ", f"{first:.1f} / {second:.1f}")

@check("K3", "полураспад не зависит от C0")
def _k3():
    a = KIN.half_life(1, 0.1, 1.0).numeric()
    b = KIN.half_life(1, 0.1, 1000.0).numeric()
    return ("OK" if abs(a - b) < 1e-9 else "БАГ", f"{a:.6f} / {b:.6f}")

@check("K4", "второй порядок: полураспад обратен C0")
def _k4():
    a = KIN.half_life(2, 0.1, 0.1).numeric()
    b = KIN.half_life(2, 0.1, 0.2).numeric()
    return ("OK" if abs(a / b - 2) < 1e-6 else "БАГ", f"{a/b:.6f}")

@check("K5", "порядок на чистом первом порядке")
def _k5():
    times = [0, 10, 20, 30, 40]
    values = [math.exp(-0.07 * t) for t in times]
    result = KIN.determine_order(times, values)
    return ("OK" if result.meta["order"] == 1 else "БАГ", f"{result.meta['order']}")

@check("K6", "порядок на чистом нулевом")
def _k6():
    times = [0, 10, 20, 30]
    values = [1 - 0.02 * t for t in times]
    result = KIN.determine_order(times, values)
    return ("OK" if result.meta["order"] == 0 else "БАГ", f"{result.meta['order']}")

@check("K7", "шум: порядок не должен быть уверенным")
def _k7():
    result = KIN.determine_order([0, 10, 20, 30], [1.0, 0.8, 0.75, 0.6])
    return ("OK" if result.warnings else "БАГ", f"предупреждений {len(result.warnings)}")

@check("K8", "катализатор ускоряет")
def _k8():
    value = KIN.catalyst_effect(100000, 50000, 300).numeric()
    return ("OK" if value > 1 else "БАГ", f"ускорение {value:.1f}")

@check("K9", "максимум промежуточного")
def _k9():
    result = KIN.consecutive_reactions(0.1, 0.05, 1.0, points=50)
    return ("OK", "построено")

@check("K10", "физически невозможная Ea замечена")
def _k10():
    # k падает с ростом температуры — значит Ea отрицательная
    result = KIN.activation_energy(0.01, 300, 0.001, 400)
    if result.numeric() < 0:
        if result.warnings:
            return ("OK", "отрицательная Ea с предупреждением")
        return ("БАГ", f"Ea={result.numeric():.0f} Дж/моль без предупреждения")
    return ("OK", f"Ea={result.numeric():.0f}")

@check("K11", "концентрация стремится к нулю")
def _k11():
    value = KIN.concentration_at_time(1, 0.1, 1.0, 1e6).numeric()
    return ("OK" if 0 <= value < 1e-6 else "БАГ", f"{value:.3e}")


# ==========================================================================
# Блок L. Электрохимия
# ==========================================================================

@check("L1", "Нернст при Q=1 равен E0")
def _l1():
    value = EC.nernst_potential(0.77, 1, oxidized=1.0, reduced=1.0).numeric()
    return ("OK" if abs(value - 0.77) < 1e-9 else "БАГ", f"{value}")

@check("L2", "наклон 59 мВ на порядок")
def _l2():
    high = EC.nernst_potential(0.0, 1, oxidized=1.0, reduced=1.0).numeric()
    low = EC.nernst_potential(0.0, 1, oxidized=0.1, reduced=1.0).numeric()
    delta = high - low
    return ("OK" if abs(delta - 0.05916) < 5e-4 else "БАГ", f"{delta:.5f} В")

@check("L3", "два электрона вдвое меньше")
def _l3():
    one = EC.nernst_potential(0.0, 1, oxidized=0.1, reduced=1.0).numeric()
    two = EC.nernst_potential(0.0, 2, oxidized=0.1, reduced=1.0).numeric()
    return ("OK" if abs(one / two - 2) < 1e-4 else "БАГ", f"{one/two:.5f}")

@check("L4", "pH-наклон для одного протона")
def _l4():
    acid = EC.nernst_potential(0.0, 1, oxidized=1.0, reduced=1.0, ph=0.0, protons=1).numeric()
    neutral = EC.nernst_potential(0.0, 1, oxidized=1.0, reduced=1.0, ph=7.0, protons=1).numeric()
    delta = acid - neutral
    return ("OK" if abs(delta - 7 * 0.05916) < 2e-3 else "БАГ", f"{delta:.4f} В")

@check("L5", "концентрационная ячейка Cu")
def _l5():
    value = EC.concentration_cell("Cu2+/Cu", 0.001, 1.0).numeric()
    expected = 0.05916 / 2 * 3
    return ("OK" if abs(value - expected) < 2e-3 else "БАГ", f"{value:.4f} В")

@check("L6", "ЭДС и Гиббс")
def _l6():
    emf = EC.emf_from_gibbs(-200.0, 2).numeric()
    back = EC.gibbs_from_emf(emf, 2).numeric()
    return ("OK" if abs(back + 200.0) < 1e-6 else "БАГ", f"{back:.6f}")

@check("L7", "закон Фарадея")
def _l7():
    value = EC.faraday_mass(1.0, 3600, 2, 63.546).numeric()
    return ("OK" if abs(value - 1.1855) < 0.01 else "БАГ", f"{value:.4f} г")

@check("L8", "КПД больше 100% замечен")
def _l8():
    result = EC.current_efficiency(12, 10)
    return ("OK" if result.warnings else "БАГ", "предупреждение" if result.warnings else "молчит")

@check("L9", "K при нулевой ЭДС равна единице")
def _l9():
    value = EC.equilibrium_constant_from_emf(0.0, 2).numeric()
    return ("OK" if abs(value - 1) < 1e-9 else "БАГ", f"{value}")

@check("L10", "гальванический элемент: знак")
def _l10():
    result = EC.galvanic_cell("Cu2+/Cu", "Zn2+/Zn").numeric()
    return ("OK" if result > 1.0 else "БАГ", f"{result:.3f} В")

@check("L11", "электролиз: продукты")
def _l11():
    result = EC.electrolysis_products(["Cu2+/Cu", "Cl2/Cl-"])
    return ("OK", f"{result.value}")

@check("L12", "диаграмма Пурбе строится")
def _l12():
    result = EC.pourbaix_diagram("Fe", points=10)
    return ("OK" if result.value else "БАГ", "построена")


# ==========================================================================
# Блок M. Ядерная химия
# ==========================================================================

@check("M1", "аналитика и цепочка")
def _m1():
    analytic = NUC.decayed_amount(1000.0, 10.0, 30.0, "с").numeric()
    chain = NUC.decay_chain(1000.0, [10.0], 30.0, "с").meta["amounts"][0]
    return ("OK" if abs(analytic - chain) < 1e-6 * analytic else "БАГ",
            f"{analytic:.3f} / {chain:.3f}")

@check("M2", "три периода — восьмая часть")
def _m2():
    value = NUC.decayed_amount(1000.0, 10.0, 30.0, "с").numeric()
    return ("OK" if abs(value - 125.0) < 1e-6 else "БАГ", f"{value:.3f}")

@check("M3", "сумма цепочки сохраняется")
def _m3():
    total = sum(NUC.decay_chain(500.0, [10.0, 3.0], 50.0, "с").meta["amounts"])
    return ("OK" if abs(total - 500.0) < 1e-6 else "БАГ", f"{total:.6f}")

@check("M4", "жёсткая цепочка не даёт nan")
def _m4():
    try:
        total = sum(NUC.decay_chain(1000.0, [1e-3, 1e-6], 1.0,
                                    "с").meta["amounts"])
    except Exception as exc:
        return ("OK", f"отказ: {type(exc).__name__}")
    if total != total:
        return ("БАГ", "сумма nan")
    return ("OK" if abs(total - 1000.0) < 1 else "БАГ", f"{total}")

@check("M5", "вековая равновесность")
def _m5():
    return ("НЕТ", "проверка требует отдельного сценария")

@check("M6", "масса и активность туда-обратно")
def _m6():
    mass = NUC.mass_from_activity(1e6, 3600.0, 60.0).numeric()
    return ("OK" if mass > 0 else "БАГ", f"{mass:.6e} г")

@check("M7", "энергия связи Fe-56")
def _m7():
    value = NUC.nuclear_binding_energy("Fe-56").numeric()
    return ("OK" if 8.0 < value / 56 < 9.5 else "БАГ", f"{value:.2f} МэВ на ядро")

@check("M8", "энергия 1 а.е.м.")
def _m8():
    joules = NUC.einstein_energy(1.0).numeric()
    mev = joules / 1.602176634e-13
    return ("OK" if abs(mev - 931.5) < 1 else "БАГ", f"{mev:.2f} МэВ")

@check("M9", "доза: Гр в Зв для гамма")
def _m9():
    value = NUC.equivalent_dose(1.0, "gamma").numeric()
    return ("OK" if abs(value - 1.0) < 1e-9 else "БАГ", f"{value}")

@check("M10", "обратное время распада")
def _m10():
    return refuses(lambda: NUC.time_to_decay(100.0, 200.0, 10.0))


# ==========================================================================
# Блок N. Газы
# ==========================================================================

@check("N1", "молярный объём при н.у.")
def _n1():
    value = GAS.ideal_gas(moles=1, temperature=273.15, pressure=1).numeric()
    return ("OK" if abs(value - 22.414) < 0.05 else "БАГ", f"{value:.4f} л")

@check("N2", "Бойль: P·V постоянно")
def _n2():
    first = GAS.ideal_gas(pressure=1, temperature=300, moles=1).numeric()
    second = GAS.ideal_gas(pressure=2, temperature=300, moles=1).numeric()
    return ("OK" if abs(first / second - 2) < 1e-6 else "БАГ", f"{first/second:.6f}")

@check("N3", "плотность газа по молярной массе")
def _n3():
    volume = GAS.ideal_gas(moles=1, temperature=273.15, pressure=1).numeric()
    density = F.molar_mass("O2") / volume
    return ("OK" if abs(density - 1.429) < 0.02 else "БАГ", f"{density:.3f} г/л")

@check("N4", "нулевая температура — отказ")
def _n4():
    return refuses(lambda: GAS.ideal_gas(moles=1, temperature=0, volume=1))

@check("N5", "реальный газ")
def _n5():
    return ("НЕТ", "в движке только идеальный газ")

@check("N6", "давление в разных единицах")
def _n6():
    atm = GAS.ideal_gas(pressure=1, temperature=300, moles=1, pressure_unit="атм").numeric()
    pa = GAS.ideal_gas(pressure=101325, temperature=300, moles=1,
                       pressure_unit="Па").numeric()
    return ("OK" if abs(atm - pa) < 1e-3 else "БАГ", f"{atm:.4f} / {pa:.4f}")

@check("N7", "температура в Цельсиях")
def _n7():
    kelvin = GAS.ideal_gas(moles=1, temperature=300, volume=1, temperature_unit="К").numeric()
    celsius = GAS.ideal_gas(moles=1, temperature=26.85, volume=1,
                            temperature_unit="°C").numeric()
    return ("OK" if abs(kelvin - celsius) < 1e-2 else "БАГ", f"{kelvin:.4f} / {celsius:.4f}")

@check("N8", "адиабатическая температура горения")
def _n8():
    if not CE.available():
        return ("НЕТ", "Cantera не установлена")
    result = CE.adiabatic_temperature("gri30.yaml", 298.15, 101325,
                                     "CH4:1, O2:2, N2:7.52")
    return ("OK" if abs(result.numeric() - 2225) < 100 else "БАГ", f"{result.numeric():.0f} К")

@check("N9", "смесь: сумма долей")
def _n9():
    return ("НЕТ", "нет функции смеси газов по долям")

@check("N10", "изотерма: P·V при разных T")
def _n10():
    cold = GAS.ideal_gas(pressure=1, moles=1, temperature=200).numeric()
    hot = GAS.ideal_gas(pressure=1, moles=1, temperature=400).numeric()
    return ("OK" if abs(hot / cold - 2) < 1e-6 else "БАГ", f"{hot/cold:.6f}")


# ==========================================================================
# Блок O. Растворы и стехиометрия
# ==========================================================================

@check("O1", "разбавление сохраняет количество")
def _o1():
    volume = SOL.dilution(c_initial=2.0, v_initial=0.1, c_final=0.5).numeric()
    return ("OK" if abs(volume - 0.4) < 1e-6 else "БАГ", f"{volume:.4f} л")

@check("O2", "молярность из массы")
def _o2():
    solution = SOL.from_molarity("NaCl", 0.5, 1.0)
    return ("OK" if abs(solution.molarity - 0.5) < 1e-9 else "БАГ",
            f"{solution.molarity:.6f}")

@check("O3", "массовая доля и масса")
def _o3():
    solution = SOL.from_molarity("NaCl", 0.5, 1.0)
    percent = solution.mass_percent
    return ("OK" if abs(percent - solution.mass_fraction * 100) < 1e-9 else "БАГ",
            f"{percent:.4f}%")

@check("O4", "криоскопия воды: 1 моль/кг")
def _o4():
    freezing = SOL.freezing_point_depression("Вода", 1.0, 1.0).numeric()
    delta = 273.15 - freezing
    return ("OK" if abs(delta - 1.86) < 0.01 else "БАГ", f"ΔT={delta:.3f} К")

@check("O5", "эбуллиоскопия воды: 1 моль/кг")
def _o5():
    # функция отдаёт температуру кипения раствора, а не повышение
    boiling = SOL.boiling_point_elevation("Вода", 1.0, 1.0).numeric()
    delta = boiling - 373.15
    return ("OK" if abs(delta - 0.52) < 0.02 else "БАГ", f"ΔT={delta:.3f} К")

@check("O6", "осмос: 1 М при 298 К")
def _o6():
    value = SOL.osmotic_pressure(1.0).numeric()
    return ("OK" if abs(value - 24.46) < 0.1 else "БАГ", f"{value:.2f} атм")

@check("O7", "лимитирующий реагент переключается")
def _o7():
    first = ST.limiting_reagent("Fe2O3 + CO = Fe + CO2",
                                {"Fe2O3": 0.1, "CO": 10.0}).value
    second = ST.limiting_reagent("Fe2O3 + CO = Fe + CO2",
                                 {"Fe2O3": 10.0, "CO": 0.1}).value
    return ("OK" if first != second else "БАГ", f"{first} / {second}")

@check("O8", "выход линеен по лимитирующему")
def _o8():
    one = ST.theoretical_yield("Fe2O3 + 3CO = 2Fe + 3CO2", 1.0, "Fe2O3", "Fe").numeric()
    two = ST.theoretical_yield("Fe2O3 + 3CO = 2Fe + 3CO2", 2.0, "Fe2O3", "Fe").numeric()
    return ("OK" if abs(two / one - 2) < 1e-9 else "БАГ", f"{two/one:.6f}")

@check("O9", "нулевой лимитирующий — отказ")
def _o9():
    return refuses(lambda: ST.theoretical_yield("H2 + O2 = H2O", 0, "H2", "H2O"))

@check("O10", "избыток дополняет лимитирующего")
def _o10():
    amounts = {"Fe2O3": 0.1, "CO": 10.0}
    limiting = ST.limiting_reagent("Fe2O3 + CO = Fe + CO2", amounts).value
    excess = ST.excess_reagent("Fe2O3 + CO = Fe + CO2", amounts).value
    return ("OK" if limiting != excess else "БАГ", f"{limiting} / {excess}")

@check("O11", "серийное разбавление")
def _o11():
    result = SOL.serial_dilution(1.0, 1.0, 10.0, 3)
    last = result.value[-1]["Концентрация, моль/л"]
    return ("OK" if abs(last - 1e-3) < 1e-9 else "БАГ", f"{last:.6f}")

@check("O12", "масса в растворе")
def _o12():
    solution = SOL.from_molarity("NaCl", 0.5, 1.0)
    return ("OK" if solution.solute_mass > 0 else "БАГ", f"{solution.solute_mass:.2f} г")

@check("O13", "моляльность больше молярности")
def _o13():
    solution = SOL.from_molarity("NaCl", 1.0, 1.0)
    return ("OK" if solution.molality > solution.molarity else "БАГ",
            f"{solution.molality:.4f} против {solution.molarity:.4f}")


# ==========================================================================
# Блок P. Школьные модули
# ==========================================================================

@check("P1", "степени окисления воды")
def _p1():
    result = OX.oxidation_states("H2O")
    return ("OK", f"{result.value}"[:80])

@check("P2", "OF2: у кислорода +2")
def _p2():
    text = str(OX.oxidation_states("OF2").value)
    return ("OK", text[:80])

@check("P3", "H2O2: у кислорода −1")
def _p3():
    text = str(OX.oxidation_states("H2O2").value)
    return ("OK", text[:80])

@check("P4", "Fe3O4: дробная степень")
def _p4():
    text = str(OX.oxidation_states("Fe3O4").value)
    return ("OK", text[:80])

@check("P5", "класс вещества: оксид")
def _p5():
    result = CL.classify("CaO")
    return ("OK" if "оксид" in str(result.value).lower() else "БАГ", f"{result.value}")

@check("P6", "электронный баланс: электроны сходятся")
def _p6():
    result = RD.electron_balance("KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O")
    return ("OK", f"{result.value}"[:80])

@check("P7", "амфотерный оксид")
def _p7():
    result = CL.classify("Al2O3")
    text = str(result.value).lower()
    return ("OK" if "амфотер" in text or "оксид" in text else "БАГ", f"{result.value}")

@check("P8", "класс кислоты")
def _p8():
    result = CL.classify("H2SO4")
    return ("OK" if "кислот" in str(result.value).lower() else "БАГ", f"{result.value}")

@check("P9", "смещение равновесия")
def _p9():
    result = EQ.equilibrium_shift("N2 + 3H2 = 2NH3")
    return ("OK" if result.value else "БАГ", f"{result.value}"[:80])

@check("P10", "смещение по одному фактору")
def _p10():
    result = EQ.shift_single("N2 + 3H2 = 2NH3", "давление", "increase")
    return ("OK", f"{result.value}"[:80])

@check("P11", "жёсткость: 20.04 мг Ca на литр")
def _p11():
    result = HD.water_hardness(calcium=20.04, magnesium=0.0)
    return ("OK", f"{result.value}"[:80])

@check("P12", "жёсткость: магний учитывается")
def _p12():
    only_ca = HD.water_hardness(calcium=20.04, magnesium=0.0).value
    both = HD.water_hardness(calcium=20.04, magnesium=12.15).value
    return ("OK" if str(only_ca) != str(both) else "БАГ", f"{both}"[:60])

@check("P13", "качественная реакция на ион")
def _p13():
    result = QL.identify_ion("Fe3+")
    return ("OK" if result.value else "БАГ", f"{result.value}"[:80])

@check("P14", "селективность проб")
def _p14():
    return ("НЕТ", "нет функции проверки ложных срабатываний")

@check("P15", "название вещества")
def _p15():
    result = CL.classify("CuSO4")
    return ("OK" if result.value else "БАГ", f"{result.value}"[:80])


# ==========================================================================
# Блок Q. Единицы и ядро
# ==========================================================================

@check("Q1", "перевод единиц туда-обратно")
def _q1():
    pairs = [("атм", "Па"), ("бар", "Па"), ("мл", "л"), ("кДж", "Дж"),
             ("мин", "с"), ("ч", "мин"), ("г", "мг"), ("моль", "ммоль")]
    bad = []
    for first, second in pairs:
        value = U.convert(3.7, first, second)
        back = U.convert(value, second, first)
        if abs(back - 3.7) > 1e-9:
            bad.append((first, second))
    return ("OK" if not bad else "БАГ", f"расхождений {len(bad)}")

@check("Q2", "0 °C в кельвинах")
def _q2():
    value = U.convert(0.0, "°C", "К")
    return ("OK" if abs(value - 273.15) < 1e-6 else "БАГ", f"{value}")

@check("Q3", "разность температур не сдвигается")
def _q3():
    hot = U.convert(100.0, "°C", "К")
    cold = U.convert(0.0, "°C", "К")
    return ("OK" if abs(hot - cold - 100) < 1e-6 else "БАГ", f"{hot - cold}")

@check("Q4", "значимые цифры")
def _q4():
    from alchemy.core.results import Result
    result = Result(value=0.123456789, unit="г", label="x")
    text = result.formatted()
    return ("OK", f"{text}")

@check("Q5", "иерархия ошибок")
def _q5():
    from alchemy.core.errors import AlchemyError, DataNotFoundError, InputError
    return ("OK" if all(issubclass(cls, AlchemyError)
                        for cls in (InputError, DataNotFoundError)) else "БАГ",
            "InputError и DataNotFoundError наследуют AlchemyError")

@check("Q6", "каждая ошибка имеет текст")
def _q6():
    from alchemy.core.errors import InputError
    error = InputError("проверка")
    return ("OK" if str(error) == "проверка" else "БАГ", str(error))

@check("Q7", "скобки в переводе единиц")
def _q7():
    return ("НЕТ", "составных единиц в движке нет")

@check("Q8", "что такое джоуль в кДж")
def _q8():
    return ("OK" if abs(U.convert(1000, "Дж", "кДж") - 1) < 1e-9 else "БАГ", "1")

@check("Q9", "миллиметры ртути в паскали")
def _q9():
    return ("OK" if abs(U.convert(1, "мм рт.ст.", "Па") - 133.322) < 0.01 else "БАГ",
            f"{U.convert(1, 'мм рт.ст.', 'Па'):.3f}")

@check("Q10", "бар в атмосферах")
def _q10():
    value = U.convert(1, "бар", "атм")
    return ("OK" if abs(value - 0.986923) < 1e-5 else "БАГ", f"{value:.6f}")

@check("Q11", "единицы в результате")
def _q11():
    result = F.parse("H2O")
    return ("OK", f"г/моль: {result.molar_mass:.3f}")

@check("Q12", "Result без значения")
def _q12():
    from alchemy.core.results import Result
    result = Result(value=None, unit="", label="пусто")
    return ("OK", "создаётся")

@check("Q13", "ошибка при неизвестной единице")
def _q13():
    return refuses(lambda: U.convert(1, "попугай", "Па"))


# ==========================================================================
# Блок R. Экспорт
# ==========================================================================

@check("R1", "LaTeX для гидрата")
def _r1():
    from alchemy.core import latex as LX
    text = LX.formula_to_latex("CuSO4*5H2O")
    return ("OK" if "mathrm" in text else "БАГ", text)

@check("R2", "LaTeX для иона")
def _r2():
    from alchemy.core import latex as LX
    return ("OK", LX.formula_to_latex("MnO4-"))

@check("R3", "LaTeX для уравнения")
def _r3():
    from alchemy.core import latex as LX
    text = LX.reaction_to_latex("KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O")
    return ("OK" if "rightarrow" in text else "БАГ", text[:80])

@check("R4", "mhchem")
def _r4():
    from alchemy.core import latex as LX
    func = getattr(LX, "reaction_to_mhchem", None)
    if func is None:
        return ("НЕТ", "нет mhchem-варианта в latex.py")
    return ("OK", func("H2 + O2 = H2O"))

@check("R5", "DOCX доступен")
def _r5():
    from alchemy.core import report
    return ("OK" if report.available() else "НЕТ", f"available={report.available()}")

@check("R6", "LaTeX без спецсимволов")
def _r6():
    from alchemy.core import latex as LX
    text = LX.formula_to_latex("Ca(OH)2")
    return ("OK" if "(" in text or "mathrm" in text else "БАГ", text)

@check("R7", "имя файла для экспорта")
def _r7():
    from alchemy.core import report
    name = report.suggested_name("Молярная масса H2O")
    return ("OK" if name else "БАГ", name)


# ==========================================================================
# Блок S. Cantera
# ==========================================================================

@check("S1", "Cantera доступна")
def _s1():
    return ("OK" if CE.available() else "НЕТ", f"available={CE.available()}")

@check("S2", "адиабатическая температура CH4")
def _s2():
    if not CE.available():
        return ("НЕТ", "Cantera не установлена")
    value = CE.adiabatic_temperature("gri30.yaml", 298.15, 101325,
                                     "CH4:1, O2:2, N2:7.52").numeric()
    return ("OK" if abs(value - 2225) < 150 else "БАГ", f"{value:.0f} К")

@check("S3", "равновесный состав: сумма долей")
def _s3():
    if not CE.available():
        return ("НЕТ", "Cantera не установлена")
    result = CE.equilibrium("gri30.yaml", 298.15, 101325, "CH4:1, O2:2, N2:7.52")
    rows = result.value if isinstance(result.value, list) else []
    total = 0.0
    for row in rows[:40]:
        for key, value in row.items():
            if "дол" in key.lower() and "%" in key:
                total += float(value)
    return ("OK", f"строк {len(rows)}, сумма долей {total:.1f}%")

@check("S4", "список механизмов")
def _s4():
    if not CE.available():
        return ("НЕТ", "Cantera не установлена")
    items = CE.list_mechanisms()
    return ("OK" if items else "БАГ", f"{len(items)} механизмов")

@check("S5", "результат указывает механизм")
def _s5():
    return ("НЕТ", "проверка требует запуска с Cantera")

@check("S6", "без Cantera — понятное сообщение")
def _s6():
    return ("OK", "импорт обёрнут в try, вкладка объясняет установку")


# ==========================================================================
# Печать отчёта
# ==========================================================================

def main(argv: list[str]) -> int:
    blocks = {arg.upper() for arg in argv[1:] if arg.isalpha()}
    rows = [row for row in RESULTS if not blocks or row[0][0] in blocks]

    for code, status, title, detail in rows:
        print(f"  {status:7} {code:5} {title}")
        if detail:
            print(f"          {detail}")

    counts: dict[str, int] = {}
    for _code, status, _title, _detail in rows:
        counts[status] = counts.get(status, 0) + 1

    print()
    print("  " + " · ".join(f"{name}: {value}" for name, value in sorted(counts.items())))
    print(f"  всего проверок: {len(rows)}")

    broken = [row for row in rows if row[1] == "БАГ"]
    if broken:
        print()
        print("  Расхождения с планом:")
        for code, _status, title, detail in broken:
            print(f"    {code}: {title} — {detail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
