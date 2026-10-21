"""Инструменты для модели: обёртки над движками.

Правила, по которым собран этот набор:

1. **Один инструмент — одна задача.** Модель должна понимать из названия,
   что он делает, без чтения кода.
2. **Отказ передаётся как отказ.** Если движок не может посчитать, модель
   получает текст причины, а не ноль и не пустоту.
3. **Ответ короткий, но полный.** Значение, единица, метод, предупреждения
   и пара шагов — этого хватает, чтобы объяснить, и не хватает, чтобы
   утонуть.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from ..core import formula as F
from ..core.errors import AlchemyError
from ..core.results import Result
from ..engines import acidbase, balancer, classification, electrochemistry
from ..engines import equilibrium, gases, hardness, kinetics, organic, oxidation
from ..engines import qualitative, redox, solutions, stoichiometry, thermo

#: сколько шагов расчёта показывать модели
MAX_STEPS = 4

#: сколько символов отдавать по одному вызову
MAX_CHARS = 1600


@dataclass
class ToolResult:
    """Что вернул инструмент."""

    ok: bool
    text: str
    raw: Any = None
    meta: dict = field(default_factory=dict)


def _format_result(result: Result, note: str = "") -> str:
    """Привести Result к тексту, понятному модели и достаточному для ответа."""
    lines: list[str] = []

    value = result.value
    if isinstance(value, (list, dict)):
        summary = f"строк: {len(value)}"
        if note:
            summary = f"{note}; {summary}"
        lines.append(f"РЕЗУЛЬТАТ: {summary}")
    else:
        numeric = ""
        try:
            numeric = f"{float(value):.6g}"
        except (TypeError, ValueError):
            numeric = str(value)
        unit = f" {result.unit}" if result.unit else ""
        lines.append(f"ЗНАЧЕНИЕ: {numeric}{unit}")

    if result.method:
        lines.append(f"МЕТОД: {result.method}")

    if result.warnings:
        lines.append("ПРЕДУПРЕЖДЕНИЯ:")
        for warning in result.warnings[:3]:
            lines.append(f"  - {warning}")

    if result.assumptions:
        lines.append("ДОПУЩЕНИЯ:")
        for assumption in result.assumptions[:2]:
            lines.append(f"  - {assumption}")

    steps = [s for s in (result.steps or []) if s]
    if steps:
        lines.append("ХОД РАСЧЁТА:")
        for step in steps[:MAX_STEPS]:
            lines.append(f"  {step}")

    if result.sources:
        lines.append("ИСТОЧНИК: " + "; ".join(str(s) for s in result.sources[:2]))

    if note:
        lines.insert(0, f"ПОЯСНЕНИЕ: {note}")

    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n… (обрезано)"
    return text


def _as_result(value: Any) -> Result:
    """Привести ответ движка к Result, если это число или словарь."""
    if isinstance(value, Result):
        return value
    if isinstance(value, dict):
        res = Result(value=None, unit="", label="Результат")
        res.with_meta("данные", value)
        res.value = value
        return res
    res = Result(value=value, unit="", label="Результат")
    return res


def _call(func: Callable, **kwargs) -> ToolResult:
    """Вызвать движок и превратить любой его ответ в ToolResult."""
    try:
        raw = func(**kwargs)
    except AlchemyError as exc:
        return ToolResult(
            ok=False,
            text=f"ОТКАЗ: {exc}\nЭто не ошибка программы, а граница применимости. "
                 f"Передай причину пользователю, не выдумывай ответ.",
            meta={"refused": True},
        )
    except TypeError as exc:
        return ToolResult(ok=False, text=f"НЕВЕРНЫЕ АРГУМЕНТЫ: {exc}")
    except Exception as exc:  # pragma: no cover - неожиданный сбой
        return ToolResult(ok=False, text=f"СБОЙ ИНСТРУМЕНТА: {type(exc).__name__}: {exc}")

    result = _as_result(raw)
    return ToolResult(ok=True, text=_format_result(result), raw=raw)


# --------------------------------------------------------------------------
# Сами инструменты
# --------------------------------------------------------------------------


def molar_mass(formula: str) -> ToolResult:
    """Молярная масса, состав и массовые доли."""
    try:
        composition = F.parse(formula)
    except AlchemyError as exc:
        return ToolResult(ok=False, text=f"ОТКАЗ: {exc}")

    res = Result(
        value=composition.molar_mass,
        unit="г/моль",
        label=f"Молярная масса {formula}",
        method="Сумма атомных масс по стандартным значениям IUPAC",
    )
    counts = ", ".join(f"{el}{n}" for el, n in composition.counts.items())
    res.with_step(f"Состав: {counts}")
    if composition.charge:
        res.with_step(f"Заряд: {composition.charge:+d}")
    percentages = composition.mass_percentages
    if percentages:
        top = sorted(percentages.items(), key=lambda kv: -kv[1])[:4]
        res.with_step("Массовые доли: " + ", ".join(f"{el} {v:.2f}%" for el, v in top))
    return ToolResult(ok=True, text=_format_result(res), raw=res)


def balance_equation(equation: str) -> ToolResult:
    """Уравнять реакцию."""
    return _call(balancer.balance, equation=equation)


def reaction_enthalpy(equation: str) -> ToolResult:
    """Стандартная энтальпия реакции."""
    return _call(thermo.reaction_enthalpy, equation=equation)


def reaction_entropy(equation: str) -> ToolResult:
    """Изменение энтропии реакции."""
    return _call(thermo.reaction_entropy, equation=equation)


def reaction_gibbs(equation: str, temperature: float = 298.15) -> ToolResult:
    """Энергия Гиббса реакции при температуре."""
    return _call(thermo.reaction_gibbs, equation=equation, temperature=temperature)


def ph_of_acid(acid: str, concentration: float, temperature: float = 298.15) -> ToolResult:
    """pH раствора кислоты."""
    return _call(acidbase.ph_of_acid, acid_query=acid,
                 concentration=concentration, temperature_k=temperature)


def ph_of_base(base: str, concentration: float, temperature: float = 298.15) -> ToolResult:
    """pH раствора основания."""
    return _call(acidbase.ph_of_base, base_query=base,
                 concentration=concentration, temperature_k=temperature)


def buffer_ph(acid: str, acid_concentration: float, salt_concentration: float) -> ToolResult:
    """pH буферного раствора."""
    return _call(acidbase.buffer_ph, acid_query=acid,
                 c_acid=acid_concentration, c_salt=salt_concentration)


def limiting_reagent(equation: str, amounts: dict) -> ToolResult:
    """Лимитирующий реагент по количествам (моли)."""
    return _call(stoichiometry.limiting_reagent, equation=equation, amounts=amounts)


def theoretical_yield(equation: str, limiting_amount: float,
                      limiting_species: str, target_species: str) -> ToolResult:
    """Теоретический выход продукта."""
    return _call(stoichiometry.theoretical_yield, equation=equation,
                 limiting_amount=limiting_amount, limiting_species=limiting_species,
                 target_species=target_species)


def water_of_crystallization(formula: str) -> ToolResult:
    """Сколько воды в кристаллогидрате и какая у неё массовая доля."""
    import re

    text = str(formula or "").strip()
    if not text:
        return ToolResult(ok=False, text="ОТКАЗ: пустая формула")

    parts = [p.strip() for p in re.split(r"[*·]", text) if p.strip()]
    if len(parts) < 2:
        # точка как разделитель: CuSO4.5H2O, но не десятичная дробь
        parts = [p.strip() for p in re.split(r"\.(?=\d*[A-Za-z(])", text) if p.strip()]
    if len(parts) < 2:
        return ToolResult(
            ok=False,
            text="ОТКАЗ: это не гидрат. Воды в составе нет, либо формула "
                 "записана без разделителя (нужно CuSO4*5H2O).",
        )

    try:
        F.parse(text)  # проверка, что формула вообще разбирается
    except AlchemyError as exc:
        return ToolResult(ok=False, text=f"ОТКАЗ: {exc}")

    water_moles = 0.0
    anhydrous_mass = 0.0
    for part in parts:
        match = re.match(r"^(\d+(?:\.\d+)?)?\s*(.+)$", part)
        if not match:
            continue
        coefficient = float(match.group(1) or 1)
        body = match.group(2)
        try:
            composition = F.parse(body)
        except AlchemyError as exc:
            return ToolResult(ok=False, text=f"ОТКАЗ в части «{part}»: {exc}")

        counts = {el: float(n) for el, n in composition.counts.items()}
        is_water = counts == {"H": 2.0, "O": 1.0}
        if is_water:
            water_moles += coefficient
        else:
            anhydrous_mass += coefficient * composition.molar_mass

    if water_moles <= 0:
        return ToolResult(ok=False, text="ОТКАЗ: в формуле не нашлось воды H2O")

    water_mass = water_moles * F.molar_mass("H2O")
    full_mass = anhydrous_mass + water_mass
    percent = water_mass / full_mass * 100 if full_mass else 0.0

    res = Result(
        value=percent,
        unit="%",
        label="Массовая доля воды в кристаллогидрате",
        method="По молярным массам безводной соли и воды",
    )
    res.with_step(f"Молей воды на формульную единицу: {water_moles:g}")
    res.with_step(f"Молярная масса воды: {water_mass:.3f} г/моль")
    res.with_step(f"Безводная часть: {anhydrous_mass:.3f} г/моль")
    res.with_step(f"Вся формульная единица: {full_mass:.3f} г/моль")
    res.with_step(f"Доля воды: {water_mass:.3f} / {full_mass:.3f} · 100 = {percent:.2f}%")
    return ToolResult(ok=True, text=_format_result(res), raw=res)


def osmotic_pressure(molarity: float, temperature: float = 298.15, i: float = 1.0) -> ToolResult:
    """Осмотическое давление."""
    return _call(solutions.osmotic_pressure, molarity=molarity,
                 temperature_k=temperature, i=i)


def freezing_point(solvent: str, molality: float, i: float = 1.0) -> ToolResult:
    """Температура замерзания раствора."""
    return _call(solutions.freezing_point_depression, solvent_name=solvent,
                 molality=molality, i=i)


def ideal_gas(pressure: float | None = None, volume: float | None = None,
              moles: float | None = None, temperature: float | None = None,
              pressure_unit: str = "атм", volume_unit: str = "л",
              temperature_unit: str = "К") -> ToolResult:
    """Газовые законы: найти одну величину по остальным."""
    return _call(gases.ideal_gas, pressure=pressure, volume=volume, moles=moles,
                 temperature=temperature, pressure_unit=pressure_unit,
                 volume_unit=volume_unit, temperature_unit=temperature_unit)


def organic_class(substance: str) -> ToolResult:
    """Класс органического вещества по формуле или названию."""
    return _call(organic.class_of, text=substance)


def combustion_formula(sample_mass: float, co2_mass: float = 0.0,
                       h2o_mass: float = 0.0, co2_volume: float = 0.0,
                       molar_mass: float = 0.0) -> ToolResult:
    """Формула вещества по продуктам сгорания."""
    return _call(organic.combustion_formula, sample_mass=sample_mass,
                 co2_mass=co2_mass, h2o_mass=h2o_mass, co2_volume=co2_volume,
                 molar_mass=molar_mass)


def oxidation_states(substance: str) -> ToolResult:
    """Степени окисления элементов в веществе."""
    return _call(oxidation.oxidation_states, text=substance)


def electron_balance(equation: str) -> ToolResult:
    """Электронный баланс окислительно-восстановительной реакции."""
    return _call(redox.electron_balance, equation=equation)


def classify_substance(substance: str) -> ToolResult:
    """Класс неорганического вещества и его название."""
    return _call(classification.classify, text=substance)


def water_hardness(calcium: float, magnesium: float,
                   hydrocarbonate: float = 0.0) -> ToolResult:
    """Жёсткость воды по концентрациям в мг/л."""
    return _call(hardness.water_hardness, calcium=calcium,
                 magnesium=magnesium, hydrocarbonate=hydrocarbonate)


def identify_ion(ion: str) -> ToolResult:
    """Качественные реакции на ион."""
    return _call(qualitative.identify_ion, ion=ion)


def equilibrium_shift(equation: str) -> ToolResult:
    """Смещение равновесия по Ле Шателье."""
    return _call(equilibrium.equilibrium_shift, equation=equation)


def nernst_potential(e0: float, n: int, oxidized: float = 1.0,
                     reduced: float = 1.0, temperature: float = 298.15) -> ToolResult:
    """Потенциал по уравнению Нернста."""
    return _call(electrochemistry.nernst_potential, e0=e0, n=n,
                 temperature_k=temperature, oxidized=oxidized, reduced=reduced)


def galvanic_cell(cathode: str, anode: str) -> ToolResult:
    """ЭДС гальванического элемента."""
    return _call(electrochemistry.galvanic_cell, cathode=cathode, anode=anode)


def half_life(order: int, k: float, c0: float | None = None) -> ToolResult:
    """Период полупревращения."""
    return _call(kinetics.half_life, order=order, k=k, c0=c0)


# --------------------------------------------------------------------------
# Схемы для модели
# --------------------------------------------------------------------------

_S = {"type": "string"}
_N = {"type": "number"}
_I = {"type": "integer"}


def _schema(name: str, description: str, properties: dict,
            required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOLS: list[dict] = [
    _schema("molar_mass", "Молярная масса, состав, массовые доли. "
            "Гидраты, ионы, комплексы.",
            {"formula": {**_S, "description": "формула"}}, ["formula"]),

    _schema("water_of_crystallization", "Сколько воды в кристаллогидрате: моли и массовая доля.",
            {"formula": {**_S, "description": "формула, например CuSO4*5H2O"}},
            ["formula"]),

    _schema("balance_equation", "Уравнять реакцию, в том числе ОВР и ионные.",
            {"equation": {**_S, "description": "уравнение"}}, ["equation"]),

    _schema("reaction_enthalpy", "Энтальпия реакции при 298 К, кДж/моль.",
            {"equation": {**_S, "description": "уравнение"}}, ["equation"]),

    _schema("reaction_entropy", "Энтропия реакции, Дж/(моль·К).",
            {"equation": {**_S, "description": "уравнение"}}, ["equation"]),

    _schema("reaction_gibbs", "Энергия Гиббса при T, кДж/моль.",
            {"equation": {**_S, "description": "уравнение"},
             "temperature": {**_N, "description": "К"}}, ["equation"]),

    _schema("ph_of_acid", "pH кислоты с активностями.",
            {"acid": {**_S, "description": "кислота"},
             "concentration": {**_N, "description": "моль/л"},
             "temperature": {**_N, "description": "К"}},
            ["acid", "concentration"]),

    _schema("ph_of_base", "pH основания с активностями.",
            {"base": {**_S, "description": "основание"},
             "concentration": {**_N, "description": "моль/л"},
             "temperature": {**_N, "description": "К"}},
            ["base", "concentration"]),

    _schema("buffer_ph", "pH буфера.",
            {"acid": {**_S, "description": "кислота"},
             "acid_concentration": {**_N, "description": "моль/л"},
             "salt_concentration": {**_N, "description": "моль/л"}},
            ["acid", "acid_concentration", "salt_concentration"]),

    _schema("limiting_reagent", "Лимитирующий реагент, количества в молях.",
            {"equation": {**_S, "description": "уравнение"},
             "amounts": {"type": "object", "description":
                         "вещество → моли, например {\"Fe2O3\": 0.1}"}},
            ["equation", "amounts"]),

    _schema("theoretical_yield", "Выход продукта по лимитирующему, моль.",
            {"equation": {**_S, "description": "уравнение"},
             "limiting_amount": {**_N, "description": "моль"},
             "limiting_species": {**_S, "description": "вещество"},
             "target_species": {**_S, "description": "продукт"}},
            ["equation", "limiting_amount", "limiting_species", "target_species"]),

    _schema("osmotic_pressure", "Осмотическое давление, атм.",
            {"molarity": {**_N, "description": "моль/л"},
             "temperature": {**_N, "description": "К"},
             "i": {**_N, "description": "фактор Вант-Гоффа"}},
            ["molarity"]),

    _schema("freezing_point", "Температура замерзания, К.",
            {"solvent": {**_S, "description": "растворитель"},
             "molality": {**_N, "description": "моль/кг"},
             "i": {**_N, "description": "фактор Вант-Гоффа"}},
            ["solvent", "molality"]),

    _schema("ideal_gas", "P, V, n, T: найти неизвестную.",
            {"pressure": _N, "volume": _N, "moles": _N, "temperature": _N,
             "pressure_unit": {**_S, "description": "атм, Па, бар, мм рт.ст."},
             "volume_unit": {**_S, "description": "л, мл"},
             "temperature_unit": {**_S, "description": "К, °C"}},
            []),

    _schema("organic_class", "Класс органики. Если формула допускает два — вернёт оба.",
            {"substance": {**_S, "description": "формула или название"}},
            ["substance"]),

    _schema("combustion_formula", "Формула по продуктам сгорания.",
            {"sample_mass": {**_N, "description": "г"},
             "co2_mass": {**_N, "description": "г"},
             "h2o_mass": {**_N, "description": "г"},
             "co2_volume": {**_N, "description": "л при н.у."},
             "molar_mass": {**_N, "description": "г/моль"}},
            ["sample_mass"]),

    _schema("oxidation_states", "Степени окисления элементов.",
            {"substance": {**_S, "description": "формула"}}, ["substance"]),

    _schema("electron_balance", "Электронный баланс ОВР.",
            {"equation": {**_S, "description": "уравнение"}}, ["equation"]),

    _schema("classify_substance", "Класс вещества и название.",
            {"substance": {**_S, "description": "формула"}}, ["substance"]),

    _schema("water_hardness", "Жёсткость воды, градусы и ммоль/л.",
            {"calcium": {**_N, "description": "Ca2+, мг/л"},
             "magnesium": {**_N, "description": "Mg2+, мг/л"},
             "hydrocarbonate": {**_N, "description": "HCO3-, мг/л"}},
            ["calcium", "magnesium"]),

    _schema("identify_ion", "Качественные реакции на ион.",
            {"ion": {**_S, "description": "ион"}}, ["ion"]),

    _schema("equilibrium_shift", "Смещение равновесия по Ле Шателье.",
            {"equation": {**_S, "description": "уравнение"}}, ["equation"]),

    _schema("nernst_potential", "Потенциал по Нернсту, В.",
            {"e0": {**_N, "description": "В"},
             "n": {**_I, "description": "электронов"},
             "oxidized": _N, "reduced": _N,
             "temperature": {**_N, "description": "К"}},
            ["e0", "n"]),

    _schema("galvanic_cell", "ЭДС элемента.",
            {"cathode": {**_S, "description": "катод"},
             "anode": {**_S, "description": "анод"}},
            ["cathode", "anode"]),

    _schema("half_life", "Период полупревращения.",
            {"order": {**_I, "description": "0, 1 или 2"},
             "k": {**_N, "description": "константа скорости"},
             "c0": {**_N, "description": "начальная концентрация"}},
            ["order", "k"]),
]

#: имя → функция
REGISTRY: dict[str, Callable[..., ToolResult]] = {
    "molar_mass": molar_mass,
    "water_of_crystallization": water_of_crystallization,
    "balance_equation": balance_equation,
    "reaction_enthalpy": reaction_enthalpy,
    "reaction_entropy": reaction_entropy,
    "reaction_gibbs": reaction_gibbs,
    "ph_of_acid": ph_of_acid,
    "ph_of_base": ph_of_base,
    "buffer_ph": buffer_ph,
    "limiting_reagent": limiting_reagent,
    "theoretical_yield": theoretical_yield,
    "osmotic_pressure": osmotic_pressure,
    "freezing_point": freezing_point,
    "ideal_gas": ideal_gas,
    "organic_class": organic_class,
    "combustion_formula": combustion_formula,
    "oxidation_states": oxidation_states,
    "electron_balance": electron_balance,
    "classify_substance": classify_substance,
    "water_hardness": water_hardness,
    "identify_ion": identify_ion,
    "equilibrium_shift": equilibrium_shift,
    "nernst_potential": nernst_potential,
    "galvanic_cell": galvanic_cell,
    "half_life": half_life,
}


def call_tool(name: str, arguments: str | dict) -> ToolResult:
    """Выполнить инструмент по имени и аргументам от модели."""
    if name not in REGISTRY:
        return ToolResult(
            ok=False,
            text=f"НЕТ ТАКОГО ИНСТРУМЕНТА: {name}. Доступные: "
                 + ", ".join(sorted(REGISTRY)),
        )

    if isinstance(arguments, str):
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError as exc:
            return ToolResult(ok=False, text=f"НЕ РАЗОБРАТЬ АРГУМЕНТЫ: {exc}")
    else:
        args = dict(arguments or {})

    try:
        return REGISTRY[name](**args)
    except TypeError as exc:
        return ToolResult(
            ok=False,
            text=f"НЕВЕРНЫЕ АРГУМЕНТЫ для {name}: {exc}. "
                 f"Проверь обязательные параметры в описании инструмента.",
        )
    except Exception as exc:  # pragma: no cover
        return ToolResult(ok=False, text=f"СБОЙ ИНСТРУМЕНТА {name}: {exc}")
