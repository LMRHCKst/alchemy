"""Растворимость с учётом pH.

Осадок соли слабой кислоты в кислоте растворяется: ионы водорода
связывают анион, равновесие сдвигается, растворимость растёт. Это
школьная задача про «растворится ли осадок в кислоте», и без учёта
protonation она не решается.

Формула одна. Для соли M_m A_a с Ksp:

    Ksp = (m·s)^m · (a·s·α)^a

где s — растворимость соли (моль/л), α — доля аниона, оставшегося
непротонированным при данном pH. Отсюда

    s = ( Ksp / (m^m · a^a · α^a) )^(1/(m+a)).

При pH, где α = 1, получается обычная растворимость в воде.
"""

from __future__ import annotations

import math

from ..core import formula as F
from ..core.errors import InputError
from ..core.results import Result
from ..data import acids as ADB
from ..data import solubility as SDB

#: константы кислот по ступеням для частых анионов.
#: Список идёт от кислоты, сопряжённой аниону, к более протонированным:
#: у карбоната это сначала HCO3⁻ (pKa 10.33), потом H2CO3 (pKa 6.35).
ACID_STAGES: dict[str, list[float]] = {
    "CO3^2-": [10.33, 6.35],
    "PO4^3-": [12.35, 7.198, 2.148],
    "S^2-": [14.0, 7.02],
    "SO3^2-": [7.18, 1.9],
    "SiO3^2-": [9.8, 9.8],
    "F^-": [3.17],
    "CH3COO^-": [4.757],
    "C2O4^2-": [4.27, 1.25],
    "OH^-": [14.0],
    "CrO4^2-": [6.5, 0.74],
    "HSO4^-": [1.99],
    "CO3": [10.33, 6.35],
    "S": [14.0, 7.02],
    "F": [3.17],
}


def _ion_charge(ion: str) -> int:
    """Заряд иона из записи."""
    import re

    match = re.search(r"\^?(\d*)([+-])$", ion.strip())
    if not match:
        return -1
    digits, sign = match.group(1), match.group(2)
    value = int(digits) if digits else 1
    return value if sign == "+" else -value


def _stages(anion: str) -> list[float]:
    """Ступени кислоты для аниона: от сопряжённой к более протонированным."""
    clean = anion.strip()
    if clean in ACID_STAGES:
        return ACID_STAGES[clean]
    # кислотный остаток мог прийти без заряда
    for key, value in ACID_STAGES.items():
        if key.rstrip("^0123456789+-") == clean.rstrip("^0123456789+-"):
            return value
    return []


def alpha_unprotonated(anion: str, ph: float) -> float:
    """Доля аниона, оставшегося непротонированным при данном pH.

    α = 1 / (1 + H/Ka₁ + H²/(Ka₁·Ka₂) + …), где Ka₁ — константа кислоты,
    сопряжённой аниону. При pH много ниже pKa₁ анион почти весь связан
    в кислоту, α стремится к нулю — и растворимость растёт.
    """
    stages = _stages(anion)
    if not stages:
        return 1.0

    h = 10.0 ** (-ph)
    total = 1.0
    product = 1.0
    for number, pka in enumerate(stages, start=1):
        ka = 10.0 ** (-pka)
        product *= ka
        total += (h ** number) / product
    return 1.0 / total


def _add_polymorph_note(res: Result, formula: str) -> None:
    """Предупредить, что Ksp зависит от формы осадка."""
    try:
        note = SDB.note_for(formula)
    except Exception:
        note = None
    if note:
        res.with_assumption(note)


def _solubility_from_alpha(ksp: float, m: int, a: int, alpha: float) -> float:
    """Растворимость соли при заданной доле непротонированного аниона."""
    denominator = (m ** m) * (a ** a) * (alpha ** a)
    return (ksp / denominator) ** (1.0 / (m + a))


def solubility_pure_water(salt: str) -> Result:
    """Растворимость в чистой воде, моль/л."""
    solid = SDB.find_solid(salt)
    if not solid.Ksp:
        raise InputError(f"Для «{salt}» нет произведения растворимости")

    m = int(solid.cation_n or 1)
    a = int(solid.anion_n or 1)
    s = _solubility_from_alpha(solid.Ksp, m, a, 1.0)

    res = Result(
        value=s,
        unit="моль/л",
        label=f"Растворимость {F.split_state(salt)[0]} в воде",
        method="s = (Ksp / (m^m · a^a))^(1/(m+a))",
    )
    res.with_step(f"Ksp({solid.formula}) = {solid.Ksp:.3g}")
    res.with_step(f"Схема диссоциации: {m} катион(ов), {a} анион(ов)")
    res.with_step(f"s = ({solid.Ksp:.3g} / ({m}^{m}·{a}^{a}))^"
                  f"(1/{m + a}) = {s:.3e} моль/л")
    res.with_meta("ksp", solid.Ksp)
    _add_polymorph_note(res, salt)
    res.with_source("Справочник произведений растворимости")
    return res


def solubility_at_ph(salt: str, ph: float) -> Result:
    """Растворимость соли при заданном pH."""
    solid = SDB.find_solid(salt)
    if not solid.Ksp:
        raise InputError(f"Для «{salt}» нет произведения растворимости")

    m = int(solid.cation_n or 1)
    a = int(solid.anion_n or 1)
    anion = solid.anion or ""
    alpha = alpha_unprotonated(anion, ph)
    s = _solubility_from_alpha(solid.Ksp, m, a, alpha)
    base = _solubility_from_alpha(solid.Ksp, m, a, 1.0)

    res = Result(
        value=s,
        unit="моль/л",
        label=f"Растворимость {F.split_state(salt)[0]} при pH {ph:g}",
        method="Учтено связывание аниона ионами водорода",
    )
    res.with_step(f"Ksp = {solid.Ksp:.3g}")
    res.with_step(f"Анион {anion}, ступени кислоты: "
                  f"{', '.join(f'{p:g}' for p in _stages(anion)) or 'нет данных'}")
    res.with_step(f"Доля непротонированного аниона α = {alpha:.3e}")
    res.with_step(f"Растворимость {s:.3e} моль/л "
                  f"(в воде {base:.3e}, рост в {s / base:.1f} раза)")

    if not _stages(anion):
        res.with_warning(
            f"Для аниона {anion} нет констант кислоты: растворимость "
            f"посчитана как в воде, влияние pH не учтено.")
    if s > 1.0:
        res.with_warning(
            f"Растворимость {s:.2f} моль/л — модель Дебая и понятие Ksp "
            f"здесь уже не работают: раствор неидеальный, нужны опытные данные.")
    res.with_meta("alpha", alpha)
    _add_polymorph_note(res, salt)
    res.with_meta("pure_water", base)
    res.with_meta("ratio", s / base if base else 0.0)
    res.with_source("Справочник Ksp и констант кислотности")
    return res


def ph_for_dissolution(salt: str, target: float) -> Result:
    """До какого pH нужно подкислить, чтобы растворимость достигла target."""
    if target <= 0:
        raise InputError("Целевая растворимость должна быть больше нуля")

    solid = SDB.find_solid(salt)
    if not solid.Ksp:
        raise InputError(f"Для «{salt}» нет произведения растворимости")

    m = int(solid.cation_n or 1)
    a = int(solid.anion_n or 1)
    anion = solid.anion or ""

    # нужная доля α из формулы растворимости
    denominator = (m ** m) * (a ** a) * (target ** (m + a))
    alpha_needed = (solid.Ksp / denominator) ** (1.0 / a)
    if alpha_needed >= 1.0:
        res = Result(
            value="осадок растворяется и без подкисления",
            unit="",
            label="Условия растворения осадка",
            method="Обратный расчёт из Ksp",
        )
        res.with_step(
            f"Целевая растворимость {target:g} моль/л достигается в воде: "
            f"α = {alpha_needed:.3g} ≥ 1")
        return res

    stages = _stages(anion)
    if not stages:
        raise InputError(
            f"Для аниона {anion} нет констант кислоты: нельзя посчитать, "
            f"при каком pH осадок растворится")

    # α монотонно растёт с pH, ищем бисекцией
    low, high = -2.0, 14.0
    for _ in range(80):
        middle = (low + high) / 2
        if alpha_unprotonated(anion, middle) < alpha_needed:
            low = middle
        else:
            high = middle
    ph = (low + high) / 2

    res = Result(
        value=ph,
        unit="pH",
        label=f"pH, при котором {F.split_state(salt)[0]} растворяется",
        method="Обратный расчёт из Ksp и констант кислоты",
    )
    res.with_step(f"Ksp = {solid.Ksp:.3g}, схема {m}:{a}")
    res.with_step(f"Нужная доля α = {alpha_needed:.3e}")
    res.with_step(f"pH = {ph:.2f}")
    res.with_meta("ph", ph)
    res.with_meta("alpha_needed", alpha_needed)
    _add_polymorph_note(res, salt)
    res.with_source("Справочник Ksp и констант кислотности")
    return res
