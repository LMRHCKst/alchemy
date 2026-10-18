"""Термохимия реакций: закон Гесса, энергия Гиббса, закон Кирхгофа.

Возможности, которых не было в прежней версии:
    * расчёт ΔH, ΔS, ΔG реакции по справочным данным, а не по введённым вручную числам;
    * температурная зависимость: если для всех участников есть полиномы Cp(T),
      ΔH и ΔS считаются точно, без допущения о постоянной теплоёмкости;
    * константа равновесия из ΔG° и обратная задача;
    * температура равновесия с проверкой знака и области применимости;
    * энергия Гиббса через ЭДС и обратно.

Данные берутся из двух источников: thermo.json (компактный справочник для
стандартных условий) и thermo_polynomials.json (полиномы NASA из базы Burcat,
дают температурную зависимость). Каждый результат сопровождается ссылкой
на источник.
"""

from __future__ import annotations

import re

import math
from dataclasses import dataclass

from ..core.constants import F_FARADAY, R, STANDARD_TEMPERATURE_K
from ..core.errors import DataNotFoundError, DomainError, InputError
from ..core.formula import split_state
from ..core.results import Result, series_result, table_result
from ..data import polynomials as POLY
from ..data import thermo as TDB
from .balancer import balance

T0 = STANDARD_TEMPERATURE_K   # 298.15 К


class ThermoError(InputError):
    """Термохимический расчёт невозможен."""


# --------------------------------------------------------------------------
# Извлечение стехиометрии из уравнения
# --------------------------------------------------------------------------


@dataclass
class Participant:
    """Вещество реакции с коэффициентом и знаком."""

    text: str                 # как записано в уравнении
    fraction: float           # коэффициент
    sign: int                 # +1 для продуктов, −1 для реагентов
    substance: TDB.Substance | None
    ion: TDB.Ion | None
    body: str                 # формула без обозначения состояния

    @property
    def nu(self) -> float:
        """Стехиометрическое число: положительное у продуктов."""
        return self.fraction * self.sign

    @property
    def key(self) -> str:
        if self.substance is not None:
            return self.substance.key
        return self.body

    @property
    def display(self) -> str:
        if self.fraction == 1:
            return self.text
        if abs(self.fraction - round(self.fraction)) < 1e-9:
            return f"{int(round(self.fraction))}{self.text}"
        return f"{self.fraction:g}{self.text}"

    def data(self) -> tuple[float | None, float | None, float | None]:
        """(ΔH°f, ΔG°f, S°) для вещества или иона."""
        if self.substance is not None:
            return (self.substance.dHf, self.substance.dGf, self.substance.S)
        if self.ion is not None:
            return (self.ion.dHf, self.ion.dGf, self.ion.S)
        return (None, None, None)


def _written_coefficients(equation: str) -> dict[str, float]:
    """Коэффициенты, которые пользователь написал руками.

    Возвращает формула → коэффициент. Пусто, если коэффициентов нет.
    """
    written: dict[str, float] = {}
    for side in str(equation).replace("→", "=").replace("->", "=").split("="):
        for term in side.split("+"):
            text = term.strip()
            if not text:
                continue
            match = re.match(r"^(\d+(?:\.\d+)?)\s*(\S.*)$", text)
            if match:
                written[match.group(2).strip()] = float(match.group(1))
    return written


def _equation_note(equation: str) -> str | None:
    """Пояснение, к какой записи относится тепловой эффект."""
    try:
        balanced_text = balance(equation).value
        balanced = balance(equation)
        scale = _user_scale(equation, balanced.meta["left"], balanced.meta["right"])
    except Exception:
        return None

    written = _written_coefficients(equation)
    if not written:
        return (f"Уравнение было уравнено: {balanced_text}. "
                f"Тепловой эффект относится к этой записи.")
    if abs(scale - 1.0) > 1e-9:
        return (f"Коэффициенты приведены к вашей записи, множитель {scale:g}. "
                f"Уравненный вид: {balanced_text}")
    return None


def _user_scale(equation: str, left: dict, right: dict) -> float:
    """Во сколько раз уравнение пользователя отличается от уравненного.

    Если человек написал «H2 + 0.5O2 = H2O», балансировщик приведёт это
    к «2H2 + O2 = 2H2O». Тепловой эффект относится ко всей записи, поэтому
    ответ надо уменьшить в два раза, иначе он врёт вдвое.

    Если коэффициентов не написано, масштаб 1: расчёт идёт по уравненному
    уравнению, и это ожидаемо.
    """
    written = _written_coefficients(equation)
    if not written:
        return 1.0

    scales = []
    for text, coefficient in written.items():
        balanced = left.get(text, right.get(text))
        if balanced:
            scales.append(coefficient / balanced)

    if not scales:
        return 1.0

    first = scales[0]
    # Если отношения расходятся, доверять нечему: считаем по целым
    if any(abs(scale - first) > 1e-6 for scale in scales):
        return 1.0
    return first


def participants(equation: str) -> list[Participant]:
    """Разобрать уравненную реакцию в список участников со стехиометрией.

    Коэффициенты приводятся к той записи, которую ввёл пользователь:
    дробные коэффициенты сохраняются, а не раздуваются до целых.
    """
    bal = balance(equation)
    left: dict[str, int] = bal.meta["left"]
    right: dict[str, int] = bal.meta["right"]

    scale = _user_scale(equation, left, right)

    result: list[Participant] = []
    for text, c in left.items():
        result.append(_make_participant(text, c * scale, -1))
    for text, c in right.items():
        result.append(_make_participant(text, c * scale, +1))
    return result


def _make_participant(text: str, coeff: float, sign: int) -> Participant:
    body, state = split_state(text)

    substance = TDB.maybe(body, state)
    if substance is None and state is None:
        # Если состояние не указано, а вещество имеет несколько состояний,
        # берём то, что термодинамически устойчиво при стандартных условиях
        variants = TDB.states_of(body)
        if variants:
            substance = next((v for v in variants if v.state in ("s", "l")), variants[0])
            if len(variants) > 1:
                pass  # неоднозначность отметит вызывающий код

    ion = None
    if substance is None:
        try:
            ion = TDB.find_ion(body)
        except DataNotFoundError:
            ion = None

    return Participant(
        text=text, fraction=coeff, sign=sign,
        substance=substance, ion=ion, body=body,
    )


def _require_data(parts: list[Participant], what: str) -> None:
    """Проверить, что для всех участников есть нужные величины."""
    missing = [p.text for p in parts if p.substance is None and p.ion is None]
    if missing:
        raise ThermoError(
            f"Нет справочных данных для: {', '.join(missing)}. "
            f"Расчёт по закону Гесса невозможен без величин образования."
        )

    no_value = []
    for p in parts:
        dHf, dGf, S = p.data()
        if what == "H" and dHf is None:
            no_value.append(p.text)
        elif what == "G" and dGf is None:
            no_value.append(p.text)
        elif what == "S" and S is None:
            no_value.append(p.text)
    if no_value:
        raise ThermoError(
            f"В справочнике нет нужной величины для: {', '.join(no_value)}"
        )


# --------------------------------------------------------------------------
# Стандартные величины реакции
# --------------------------------------------------------------------------


def reaction_enthalpy(equation: str) -> Result:
    """Стандартная энтальпия реакции ΔH°₂₉₈ по закону Гесса.

    ΔH° = Σ ν·ΔH°f(продукты) − Σ ν·ΔH°f(реагенты)
    """
    parts = participants(equation)
    _require_data(parts, "H")

    total = 0.0
    steps = []
    for p in parts:
        dHf = p.data()[0]
        contribution = p.nu * dHf
        total += contribution
        steps.append(
            f"{p.display}: ν = {p.nu:+g}, ΔH°f = {dHf:+.2f} → вклад {contribution:+.2f} кДж"
        )

    note = _equation_note(equation)
    result = Result(
        value=total,
        unit="кДж/моль",
        label="Стандартная энтальпия реакции ΔH°₂₉₈",
        method="Закон Гесса по стандартным энтальпиям образования",
    )
    for s in steps:
        result.with_step(s)
    result.with_step(f"Итого ΔH° = {total:+.2f} кДж/моль")
    if note:
        result.with_step(note)

    if total < 0:
        result.with_meta("thermal_effect", "экзотермическая")
        result.with_step("ΔH° < 0 — реакция экзотермическая, тепло выделяется")
    elif total > 0:
        result.with_meta("thermal_effect", "эндотермическая")
        result.with_step("ΔH° > 0 — реакция эндотермическая, тепло поглощается")
    else:
        result.with_meta("thermal_effect", "тепловой эффект отсутствует")

    for p in parts:
        if p.substance is not None:
            result.with_source(f"{p.substance.name}: {TDB.source()}")

    _warn_ambiguity(result, parts)
    return result


def reaction_entropy(equation: str) -> Result:
    """Стандартное изменение энтропии реакции ΔS°₂₉₈."""
    parts = participants(equation)
    _require_data(parts, "S")

    total = 0.0
    for p in parts:
        S = p.data()[2]
        total += p.nu * S

    res = Result(
        value=total,
        unit="Дж/(моль·К)",
        label="Изменение энтропии реакции ΔS°₂₉₈",
        method="Σ ν·S°(продукты) − Σ ν·S°(реагенты)",
    )
    for p in parts:
        res.with_step(
            f"{p.display}: ν = {p.nu:+g}, S° = {p.data()[2]:.2f} → вклад "
            f"{p.nu * p.data()[2]:+.2f} Дж/(моль·К)"
        )
    res.with_step(f"Итого ΔS° = {total:+.2f} Дж/(моль·К)")

    if total > 0:
        res.with_step("ΔS° > 0 — беспорядок растёт (обычно так при выделении газа)")
    else:
        res.with_step("ΔS° < 0 — система упорядочивается")
    return res


def reaction_gibbs(equation: str,
                   temperature: float = T0) -> Result:
    """Энергия Гиббса реакции. ΔG = ΔH − T·ΔS.

    Args:
        equation: уравнение реакции.
        temperature: температура в кельвинах.
    """
    if temperature <= 0:
        raise DomainError("Температура должна быть больше нуля")

    dH = reaction_enthalpy(equation).numeric()
    dS = reaction_entropy(equation).numeric()
    dG = dH - temperature * dS / 1000.0

    res = Result(
        value=dG,
        unit="кДж/моль",
        label=f"Энергия Гиббса реакции при {temperature:g} К",
        method="ΔG = ΔH° − T·ΔS°",
    )
    res.with_step(f"ΔH° = {dH:+.2f} кДж/моль")
    res.with_step(f"ΔS° = {dS:+.2f} Дж/(моль·К) = {dS / 1000:+.4f} кДж/(моль·К)")
    res.with_step(f"ΔG = {dH:+.2f} − {temperature:g}·({dS / 1000:+.4f}) = {dG:+.2f} кДж/моль")

    if dG < -1e-9:
        res.with_meta("spontaneity", "самопроизвольная")
        res.with_step("ΔG < 0 — реакция может идти самопроизвольно в прямом направлении")
    elif dG > 1e-9:
        res.with_meta("spontaneity", "несамопроизвольная")
        res.with_step("ΔG > 0 — прямое направление термодинамически запрещено")
    else:
        res.with_meta("spontaneity", "равновесие")
        res.with_step("ΔG = 0 — система в равновесии")

    res.with_assumption(
        "ΔH и ΔS приняты не зависящими от температуры. Для широкого "
        "интервала температур используйте расчёт с законом Кирхгофа."
    )
    return res


# --------------------------------------------------------------------------
# Температурная зависимость: закон Кирхгофа
# --------------------------------------------------------------------------


def reaction_cp(equation: str) -> Result:
    """Изменение теплоёмкости в реакции ΔCp = Σ ν·Cp."""
    parts = participants(equation)
    no_cp = [p.text for p in parts
             if (p.data()[0] is not None) and _cp_of(p) is None]
    if no_cp:
        raise ThermoError(
            f"Нет значений теплоёмкости Cp для: {', '.join(no_cp)}. "
            f"Закон Кирхгофа применить нельзя."
        )

    total = 0.0
    for p in parts:
        cp = _cp_of(p)
        if cp is None:
            continue
        total += p.nu * cp

    res = Result(
        value=total,
        unit="Дж/(моль·К)",
        label="Изменение теплоёмкости реакции ΔCp",
        method="Σ ν·Cp(продукты) − Σ ν·Cp(реагенты)",
    )
    for p in parts:
        cp = _cp_of(p)
        if cp is not None:
            res.with_step(f"{p.display}: Cp = {cp:.2f} → вклад {p.nu * cp:+.2f}")
    return res


def _cp_of(p: Participant) -> float | None:
    if p.substance is None:
        return None
    cp = p.substance.Cp
    # Нулевая теплоёмкость в справочнике означает «данных нет» для растворов
    if cp is None or cp == 0.0:
        return None
    return cp


def _polynomial_entries(parts: list[Participant]):
    """Подобрать полиномы Cp(T) для всех участников реакции.

    Возвращает (список пар «коэффициент — полином», None) при успехе
    или (None, формула) с указанием первого вещества, для которого
    полиномов нет.
    """
    entries = []
    for participant in parts:
        state = participant.substance.state if participant.substance else None
        poly = POLY.find(participant.body, state)
        if poly is None:
            return None, participant.body
        entries.append((participant.nu, poly))
    return entries, None


def _reaction_properties_at(entries, temperature: float) -> tuple[float, float]:
    """ΔH (кДж/моль) и ΔS (Дж/(моль·К)) реакции при заданной температуре.

    Полиномы дают абсолютные энтальпию и энтропию, включая энтальпию
    образования, поэтому суммирование по стехиометрии сразу даёт
    величины реакции.
    """
    d_h = sum(nu * poly.enthalpy(temperature) for nu, poly in entries)
    d_s = sum(nu * poly.entropy(temperature) for nu, poly in entries)
    return d_h, d_s


def kirchhoff(equation: str, temperature: float,
              t_reference: float = T0) -> Result:
    """Расчёт ΔH(T), ΔS(T) и ΔG(T) с учётом температурной зависимости.

    Если для всех участников есть полиномы Cp(T), теплоёмкость
    интегрируется точно: ΔH и ΔS берутся как суммы абсолютных значений
    при нужной температуре. Это убирает допущение о постоянстве ΔCp,
    которое при широком интервале температур давало ошибку в десятки
    кДж/моль.

    Если полиномов не хватает, используется прежнее приближение
    с постоянной ΔCp, и результат сопровождается предупреждением.

    Args:
        equation: уравнение реакции.
        temperature: целевая температура, К.
        t_reference: температура, для которой взяты справочные данные.
    """
    if temperature <= 0 or t_reference <= 0:
        raise DomainError("Температуры должны быть больше нуля")

    parts = participants(equation)
    _require_data(parts, "H")
    _require_data(parts, "S")

    entries, missing = _polynomial_entries(parts)

    if entries is not None:
        return _kirchhoff_polynomial(parts, entries, temperature, t_reference)
    return _kirchhoff_constant(
        equation, parts, temperature, t_reference, missing)


def _kirchhoff_polynomial(parts: list[Participant], entries, temperature: float,
                          t_reference: float) -> Result:
    """Точный путь: интегрирование Cp(T) по полиномам NASA."""
    # Проверяем область применимости до расчёта: экстраполировать полином
    # далеко за границу нельзя, ошибка растёт быстро и незаметно
    outside = []
    for _nu, poly in entries:
        if not (poly.t_min <= temperature <= poly.t_max):
            outside.append(poly)
    if outside:
        worst = outside[0]
        names = ", ".join(p.display for p in outside[:3])
        more = "" if len(outside) <= 3 else f" и ещё {len(outside) - 3}"
        raise DomainError(
            f"Полиномы Cp(T) для {names}{more} применимы в диапазоне "
            f"{worst.t_min:.0f}–{worst.t_max:.0f} К, запрошено "
            f"{temperature:g} К. За этой границей расчёт не выполняется, "
            f"чтобы не выдать экстраполированное значение за достоверное."
        )

    d_h, d_s = _reaction_properties_at(entries, temperature)
    d_h_ref, d_s_ref = _reaction_properties_at(entries, t_reference)
    d_g = d_h - temperature * d_s / 1000.0

    res = Result(
        value=d_g,
        unit="кДж/моль",
        label=f"Энергия Гиббса при {temperature:g} К",
        method="Полиномы Cp(T) NASA: ΔH и ΔS интегрируются по температуре",
    )
    res.with_step(f"ΔH°({t_reference:g} К) = {d_h_ref:+.2f} кДж/моль")
    res.with_step(f"ΔS°({t_reference:g} К) = {d_s_ref:+.2f} Дж/(моль·К)")
    res.with_step(f"ΔH({temperature:g} К) = {d_h:+.2f} кДж/моль "
                  f"(с учётом Cp(T))")
    res.with_step(f"ΔS({temperature:g} К) = {d_s:+.2f} Дж/(моль·К) "
                  f"(с учётом Cp(T))")
    res.with_step(f"ΔG = {d_h:+.2f} − {temperature:g}·({d_s / 1000:+.4f}) "
                  f"= {d_g:+.2f} кДж/моль")
    res.with_source("Alexander Burcat, Branko Ruscic. Thermodynamic Data "
                    "for Combustion and Air-Pollution Use (NASA-полиномы)")

    res.with_meta("dH", d_h)
    res.with_meta("dS", d_s)
    res.with_meta("dG", d_g)
    res.with_meta("dCp", None)
    res.with_meta("method", "polynomial")

    res.with_assumption(
        "Теплоёмкость учитывается как функция температуры по полиномам NASA. "
        "Фазовых переходов между опорной и целевой температурой нет: "
        "вещество остаётся в том состоянии, которое указано в уравнении."
    )

    return res


def _kirchhoff_constant(equation: str, parts: list[Participant],
                        temperature: float, t_reference: float,
                        missing: str | None) -> Result:
    """Приближённый путь: постоянная ΔCp при опорной температуре."""
    d_h0 = reaction_enthalpy(equation).numeric()
    d_s0 = reaction_entropy(equation).numeric()

    d_cp_result = reaction_cp(equation)
    d_cp = d_cp_result.numeric()

    dt = temperature - t_reference
    d_h = d_h0 + d_cp * dt / 1000.0                       # кДж/моль
    d_s = d_s0 + d_cp * math.log(temperature / t_reference)  # Дж/(моль·К)
    d_g = d_h - temperature * d_s / 1000.0

    res = Result(
        value=d_g,
        unit="кДж/моль",
        label=f"Энергия Гиббса при {temperature:g} К (закон Кирхгофа)",
        method="Закон Кирхгофа с постоянной ΔCp",
    )
    res.with_step(f"ΔH°({t_reference:g} К) = {d_h0:+.2f} кДж/моль")
    res.with_step(f"ΔS°({t_reference:g} К) = {d_s0:+.2f} Дж/(моль·К)")
    res.with_step(f"ΔCp = {d_cp:+.2f} Дж/(моль·К)")
    res.with_step(f"ΔH({temperature:g} К) = {d_h0:+.2f} + {d_cp:+.2f}·{dt:+.2f}/1000 = {d_h:+.2f} кДж/моль")
    res.with_step(f"ΔS({temperature:g} К) = {d_s0:+.2f} + {d_cp:+.2f}·ln({temperature:g}/{t_reference:g}) = {d_s:+.2f} Дж/(моль·К)")
    res.with_step(f"ΔG = {d_h:+.2f} − {temperature:g}·({d_s / 1000:+.4f}) = {d_g:+.2f} кДж/моль")

    res.with_meta("dH", d_h)
    res.with_meta("dS", d_s)
    res.with_meta("dCp", d_cp)
    res.with_meta("dG", d_g)
    res.with_meta("method", "constant_cp")

    res.with_assumption(
        "ΔCp принята постоянной в интервале температур. В справочнике "
        "хранится значение при 298 К, поэтому при отклонении более чем на "
        "100 К результат приближённый."
    )
    if missing:
        res.with_warning(
            f"Полиномы Cp(T) есть не для всех участников: нет данных для "
            f"{missing}. Поэтому теплоёмкость принята постоянной, и это "
            f"основной источник погрешности при нагреве."
        )
    if abs(dt) > 300:
        res.with_warning(
            f"Интервал {abs(dt):.0f} К слишком широк для постоянной ΔCp — "
            f"погрешность может достигать десятков кДж/моль"
        )

    return res


def equilibrium_temperature(equation: str) -> Result:
    """Температура, при которой ΔG = 0.

    Решение T = ΔH°/ΔS° существует тогда и только тогда, когда ΔH и ΔS
    одного знака. Если знаки разные, знак ΔG не меняется ни при какой
    температуре, и решение отсутствует.

    Направление реакции относительно этой температуры зависит от знака ΔS:
        ΔS > 0 (эндотермический случай): выше T равновесия идёт прямая реакция;
        ΔS < 0 (экзотермический случай): выше T равновесия идёт обратная.
    Это следует прямо из ΔG = ΔH − T·ΔS.
    """
    dH = reaction_enthalpy(equation).numeric()
    dS = reaction_entropy(equation).numeric()

    res = Result(
        label="Температура термодинамического равновесия",
        method="T = ΔH°/ΔS° при условии постоянства ΔH и ΔS",
    )

    if abs(dS) < 1e-12:
        res.value = None
        res.with_warning(
            "ΔS° близка к нулю — температура равновесия не определена. "
            "Реакция либо идёт, либо не идёт во всём интервале температур."
        )
        return res

    if (dH > 0) != (dS > 0):
        res.value = None
        res.with_warning(
            f"ΔH° = {dH:+.2f} кДж/моль и ΔS° = {dS:+.2f} Дж/(моль·К) имеют "
            f"разные знаки. Знак ΔG не меняется ни при какой температуре: "
            f"направление реакции температурой не переключить."
        )
        return res

    t_eq = dH * 1000.0 / dS

    if t_eq <= 0:
        res.value = None
        res.with_warning("Расчётная температура равновесия отрицательна — решения нет")
        return res

    res.value = t_eq
    res.unit = "К"
    res.with_step(f"ΔH° = {dH:+.2f} кДж/моль = {dH * 1000:+.1f} Дж/моль")
    res.with_step(f"ΔS° = {dS:+.2f} Дж/(моль·К)")
    res.with_step(f"T = {dH * 1000:+.1f} / {dS:+.2f} = {t_eq:.2f} К = {t_eq - 273.15:.2f} °C")

    if dS > 0:
        res.with_step(
            f"ΔS° > 0, поэтому выше {t_eq:.0f} К самопроизвольно идёт прямая "
            f"реакция, ниже — обратная"
        )
        res.with_meta("forward_above", True)
    else:
        res.with_step(
            f"ΔS° < 0, поэтому ниже {t_eq:.0f} К самопроизвольно идёт прямая "
            f"реакция, выше — обратная"
        )
        res.with_meta("forward_above", False)

    res.with_assumption(
        "ΔH° и ΔS° приняты постоянными. С учётом закона Кирхгофа "
        "температура равновесия сместится."
    )
    return res


# --------------------------------------------------------------------------
# Константа равновесия
# --------------------------------------------------------------------------


def equilibrium_constant(dG: float, temperature: float = T0) -> Result:
    """Константа равновесия из стандартной энергии Гиббса.

    ΔG° = −R·T·ln K,  откуда K = exp(−ΔG°/(R·T))
    """
    if temperature <= 0:
        raise DomainError("Температура должна быть больше нуля")

    exponent = -dG * 1000.0 / (R.value * temperature)

    res = Result(
        label=f"Константа равновесия при {temperature:g} К",
        method="ΔG° = −R·T·ln K",
    )
    res.with_step(f"ΔG° = {dG:+.4f} кДж/моль = {dG * 1000:+.2f} Дж/моль")
    res.with_step(f"ln K = −ΔG°/(R·T) = −({dG * 1000:+.2f})/({R.value:g}·{temperature:g}) = {exponent:+.4f}")

    if exponent > 700:
        res.value = float("inf")
        res.with_warning(
            "Показатель степени слишком велик: равновесие практически "
            "полностью смещено в сторону продуктов. Численное значение "
            "константы теряет смысл."
        )
        return res
    if exponent < -700:
        res.value = 0.0
        res.with_warning(
            "Показатель степени слишком мал: реакция практически не идёт. "
            "Численное значение константы теряет смысл."
        )
        return res

    K = math.exp(exponent)
    res.value = K
    res.with_step(f"K = e^{exponent:+.4f} = {K:.6g}")
    res.with_meta("lnK", exponent)
    res.with_meta("pK", -exponent / math.log(10))

    if K > 1e5:
        res.with_step("K ≫ 1 — равновесие смещено в сторону продуктов")
    elif K < 1e-5:
        res.with_step("K ≪ 1 — равновесие смещено в сторону исходных веществ")
    else:
        res.with_step("K близка к единице — в равновесной смеси есть всё")

    return res


def dG_from_equilibrium_constant(K: float, temperature: float = T0) -> Result:
    """Стандартная энергия Гиббса из константы равновесия. ΔG° = −R·T·ln K."""
    if K <= 0:
        raise DomainError("Константа равновесия должна быть больше нуля")
    if temperature <= 0:
        raise DomainError("Температура должна быть больше нуля")

    dg = -R.value * temperature * math.log(K) / 1000.0

    res = Result(
        value=dg,
        unit="кДж/моль",
        label=f"Стандартная энергия Гиббса при {temperature:g} К",
        method="ΔG° = −R·T·ln K",
    )
    res.with_step(f"ln K = ln({K:g}) = {math.log(K):+.4f}")
    res.with_step(
        f"ΔG° = −{R.value:g}·{temperature:g}·({math.log(K):+.4f})/1000 = {dg:+.4f} кДж/моль"
    )
    return res


def equilibrium_constant_from_reaction(equation: str,
                                       temperature: float = T0) -> Result:
    """Константа равновесия реакции по справочным данным."""
    dG_res = reaction_gibbs(equation, temperature)
    K_res = equilibrium_constant(dG_res.numeric(), temperature)

    K_res.label = f"Константа равновесия реакции при {temperature:g} К"
    K_res.with_step(f"Уравнение: {equation}")
    for step in dG_res.steps:
        K_res.with_step(step)
    K_res.with_step(f"Результат: K = {K_res.value:.6g}")
    K_res.with_source(f"Термохимические данные: {TDB.source()}")
    K_res.with_assumption(
        "Константа записана через активности. Для разбавленных растворов "
        "активности можно приближённо заменить концентрациями."
    )
    return K_res


# --------------------------------------------------------------------------
# Энергия Гиббса и ЭДС
# --------------------------------------------------------------------------


def dG_from_emf(emf: float, n_electrons: int) -> Result:
    """Энергия Гиббса реакции из ЭДС гальванического элемента. ΔG = −n·F·E."""
    if n_electrons <= 0:
        raise DomainError("Число электронов должно быть больше нуля")

    dg = -n_electrons * F_FARADAY.value * emf / 1000.0

    res = Result(
        value=dg,
        unit="кДж/моль",
        label="Энергия Гиббса реакции из ЭДС",
        method="ΔG = −n·F·E",
    )
    res.with_step(f"ΔG = −{n_electrons}·{F_FARADAY.value:g}·{emf:+.4f}/1000 = {dg:+.4f} кДж/моль")
    res.with_source(F_FARADAY.pretty())
    if dg < 0:
        res.with_step("ΔG < 0 — реакция в элементе идёт самопроизвольно")
    return res


def emf_from_dG(dG_kj: float, n_electrons: int) -> Result:
    """ЭДС из энергии Гиббса. E = −ΔG/(n·F)."""
    if n_electrons <= 0:
        raise DomainError("Число электронов должно быть больше нуля")

    emf = -dG_kj * 1000.0 / (n_electrons * F_FARADAY.value)

    res = Result(
        value=emf,
        unit="В",
        label="ЭДС гальванического элемента",
        method="E = −ΔG/(n·F)",
    )
    res.with_step(f"E = −({dG_kj:+.4f}·1000)/({n_electrons}·{F_FARADAY.value:g}) = {emf:+.4f} В")
    return res


# --------------------------------------------------------------------------
# Калориметрия
# --------------------------------------------------------------------------


def calorimetry(mass_g: float, specific_heat: float, delta_t: float,
                heat_capacity_calorimeter: float = 0.0) -> Result:
    """Теплота процесса q = m·c·ΔT + C_калориметра·ΔT.

    Args:
        mass_g: масса вещества (обычно воды), г.
        specific_heat: удельная теплоёмкость, Дж/(г·К).
        delta_t: изменение температуры, К.
        heat_capacity_calorimeter: теплоёмкость калориметра, Дж/К.
    """
    if mass_g < 0:
        raise DomainError("Масса не может быть отрицательной")
    if specific_heat < 0:
        raise DomainError("Удельная теплоёмкость не может быть отрицательной")
    if heat_capacity_calorimeter < 0:
        raise DomainError("Теплоёмкость калориметра не может быть отрицательной")

    q_substance = mass_g * specific_heat * delta_t
    q_calorimeter = heat_capacity_calorimeter * delta_t
    q_total = q_substance + q_calorimeter

    res = Result(
        value=q_total,
        unit="Дж",
        label="Теплота процесса",
        method="q = m·c·ΔT (+ C·ΔT для калориметра)",
    )
    res.with_step(f"q(вещество) = {mass_g:g}·{specific_heat:g}·{delta_t:+.2f} = {q_substance:+.2f} Дж")
    if heat_capacity_calorimeter:
        res.with_step(f"q(калориметр) = {heat_capacity_calorimeter:g}·{delta_t:+.2f} = {q_calorimeter:+.2f} Дж")
    res.with_step(f"q(общая) = {q_total:+.2f} Дж")
    res.with_meta("q_substance", q_substance)
    res.with_meta("q_calorimeter", q_calorimeter)

    if delta_t > 0:
        res.with_step("Температура выросла — процесс экзотермический")
    elif delta_t < 0:
        res.with_step("Температура упала — процесс эндотермический")
    return res


def molar_heat_of_reaction(q_j: float, moles: float) -> Result:
    """Мольная теплота реакции по измеренной теплоте и количеству вещества."""
    if moles <= 0:
        raise DomainError("Количество вещества должно быть больше нуля")

    dh = -q_j / moles / 1000.0   # знак: теплота, выделенная системой, уходит в минус

    res = Result(
        value=dh,
        unit="кДж/моль",
        label="Мольная теплота реакции",
        method="ΔH = −q/n",
    )
    res.with_step(f"ΔH = −({q_j:+.2f})/{moles:g}/1000 = {dh:+.4f} кДж/моль")
    res.with_assumption(
        "Знак энтальпии дан для реакции в прямом направлении: "
        "выделение тепла соответствует отрицательной ΔH"
    )
    return res


def hess_law(terms: list[tuple[float, float]]) -> Result:
    """Закон Гесса для произвольного набора стадий.

    Args:
        terms: список пар (ΔH стадии в кДж/моль, множитель). Множитель
               отрицательный, если стадию нужно обратить.
    """
    if not terms:
        raise InputError("Список стадий не может быть пустым")

    total = 0.0
    res = Result(
        label="Тепловой эффект по закону Гесса",
        method="Σ (ΔHᵢ · nᵢ)",
    )
    for i, (dh, factor) in enumerate(terms, 1):
        contribution = dh * factor
        total += contribution
        res.with_step(
            f"Стадия {i}: ΔH = {dh:+.2f} кДж/моль, множитель {factor:+g} "
            f"→ вклад {contribution:+.2f} кДж/моль"
        )

    res.value = total
    res.unit = "кДж/моль"
    res.with_step(f"Итого ΔH = {total:+.2f} кДж/моль")

    for dh, factor in terms:
        if factor < 0:
            res.with_assumption("Стадии с отрицательным множителем обращены")
            break
    return res


def bond_energy_estimate(broken: list[float], formed: list[float]) -> Result:
    """Оценка энтальпии реакции по энергиям разрываемых и образуемых связей.

    ΔH ≈ Σ E(разорванных) − Σ E(образованных)
    """
    if not broken and not formed:
        raise InputError("Нужно указать энергии хотя бы одной связи")

    sum_broken = sum(broken)
    sum_formed = sum(formed)
    dh = sum_broken - sum_formed

    res = Result(
        value=dh,
        unit="кДж/моль",
        label="Оценка энтальпии реакции по энергиям связей",
        method="ΔH ≈ Σ E(разорванных) − Σ E(образованных)",
    )
    res.with_step(f"Σ E(разорванных) = {sum_broken:+.2f} кДж/моль")
    res.with_step(f"Σ E(образованных) = {sum_formed:+.2f} кДж/моль")
    res.with_step(f"ΔH ≈ {dh:+.2f} кДж/моль")
    res.with_assumption(
        "Метод даёт оценку, а не точное значение: энергии связей усреднены "
        "по разным соединениям, не учтены межмолекулярные взаимодействия "
        "и фазовые переходы. Погрешность обычно 20–50 кДж/моль."
    )
    return res


# --------------------------------------------------------------------------
# График зависимости ΔG от температуры
# --------------------------------------------------------------------------


def gibbs_vs_temperature(equation: str, t_min: float = 273.15,
                         t_max: float = 1000.0, points: int = 60) -> Result:
    """Построить зависимость ΔG(T) с учётом закона Кирхгофа."""
    if t_min <= 0 or t_max <= 0 or t_min >= t_max:
        raise DomainError("Температуры должны удовлетворять 0 < Tмин < Tмакс")
    if points < 2:
        raise InputError("Нужно хотя бы две точки")

    data: list[tuple[float, float]] = []
    step = (t_max - t_min) / (points - 1)
    for i in range(points):
        t = t_min + i * step
        try:
            dg = kirchhoff(equation, t).numeric()
        except ThermoError:
            # Без Cp работает приближение с постоянными ΔH и ΔS
            dg = reaction_gibbs(equation, t).numeric()
        data.append((t, dg))

    res = series_result(
        data,
        x_label="Температура, К",
        y_label="ΔG, кДж/моль",
        label=f"Зависимость ΔG от температуры для реакции {equation}",
    )
    res.method = "Закон Кирхгофа в каждой точке"

    crossings = []
    for i in range(len(data) - 1):
        y1, y2 = data[i][1], data[i + 1][1]
        if y1 == 0 or (y1 < 0 < y2) or (y1 > 0 > y2):
            x1, x2 = data[i][0], data[i + 1][0]
            if y2 != y1:
                x0 = x1 - y1 * (x2 - x1) / (y2 - y1)
                crossings.append(x0)

    if crossings:
        res.with_meta("equilibrium_temperatures", crossings)
        res.with_step(
            "Смена знака ΔG при T ≈ "
            + ", ".join(f"{t:.1f} К" for t in crossings)
        )
    else:
        res.with_step("В заданном интервале температур знак ΔG не меняется")
    return res


def compare_reactions(equations: list[str],
                      temperature: float = T0) -> Result:
    """Сравнить несколько реакций по ΔH, ΔS и ΔG — для выбора маршрута."""
    from ..core.errors import AlchemyError

    rows = []
    for eq in equations:
        try:
            dH = reaction_enthalpy(eq).numeric()
            dS = reaction_entropy(eq).numeric()
            dG = reaction_gibbs(eq, temperature).numeric()
            rows.append({
                "Реакция": eq,
                "ΔH°, кДж/моль": round(dH, 2),
                "ΔS°, Дж/(моль·К)": round(dS, 2),
                f"ΔG°({temperature:g} К), кДж/моль": round(dG, 2),
                "Направление": ("прямое" if dG < 0 else "обратное" if dG > 0 else "равновесие"),
            })
        except (AlchemyError, ValueError) as exc:
            rows.append({
                "Реакция": eq,
                "ΔH°, кДж/моль": None,
                "ΔS°, Дж/(моль·К)": None,
                f"ΔG°({temperature:g} К), кДж/моль": None,
                "Направление": f"ошибка: {exc}",
            })

    res = table_result(rows, label="Сравнение реакций")
    res.method = "Закон Гесса для каждой реакции"
    return res


def _warn_ambiguity(result: Result, parts: list[Participant]) -> None:
    """Предупредить, если для вещества выбрано состояние по умолчанию."""
    ambiguous = []
    for p in parts:
        if p.substance is None:
            continue
        variants = TDB.states_of(p.body)
        if len(variants) > 1 and "(" not in p.text:
            ambiguous.append(p.body)
    if ambiguous:
        names = ", ".join(sorted(set(ambiguous)))
        result.with_warning(
            f"Для {names} в справочнике несколько агрегатных состояний. "
            f"Выбрано устойчивое при 298 К. Чтобы задать явно, пишите "
            f"например «H2O(ж)» или «H2O(г)»."
        )
