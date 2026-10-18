"""Химическая связь и кристаллические решётки.

8 класс: ковалентная неполярная и полярная, ионная.
9 класс: типы кристаллических решёток и зависимость свойств от них.
11 класс: плюс металлическая и водородная связь.

Тип связи определяется по разнице электроотрицательностей, тип решётки —
по составу и классу вещества. Оба правила взяты из школьного курса,
поэтому результат можно разобрать на уроке.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core import formula as F
from ..core import periodic
from ..core.errors import AlchemyError, InputError
from ..core.results import Result, table_result

#: пороги разницы электроотрицательностей по Полингу
COVALENT_NONPOLAR_MAX = 0.4
COVALENT_POLAR_MAX = 1.7

#: вещества с атомной кристаллической решёткой
ATOMIC_LATTICE = {
    "C", "Si", "B", "Ge", "SiC", "SiO2", "BN", "AlN", "Si3N4",
    "B4C", "WC", "TiC",
}

#: вещества с молекулярной решёткой
MOLECULAR_LATTICE = {
    "H2", "N2", "O2", "F2", "Cl2", "Br2", "I2", "O3", "P4", "S8",
    "H2O", "H2S", "NH3", "CO2", "SO2", "SO3", "NO", "NO2", "N2O",
    "HCl", "HBr", "HI", "HF", "CH4", "C2H6", "C2H4", "C2H2",
    "C6H6", "CH3OH", "C2H5OH", "CH3COOH", "H2O2", "PCl3", "PCl5",
    "SF6", "CCl4", "SiF4",
}

#: благородные газы
NOBLE = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}

#: решётки и их свойства
LATTICE_TABLE = [
    ("ионная", "Ионы", "высокая", "хрупкие", "не проводят",
     "растворы и расплавы проводят"),
    ("атомная", "Атомы", "очень высокая", "очень твёрдые", "не проводят",
     "не проводят"),
    ("молекулярная", "Молекулы", "низкая", "мягкие, легкоплавкие",
     "не проводят", "не проводят"),
    ("металлическая", "Атом-ионы и электроны", "разная", "пластичные",
     "проводят", "проводят"),
]


@dataclass
class BondPair:
    """Связь между двумя элементами."""

    first: str
    second: str
    difference: float
    kind: str
    explanation: str


def _is_metal(symbol: str) -> bool:
    category = periodic.by_symbol(symbol).category or ""
    return category.startswith(("Щелочн", "Переходн", "Постпереходн",
                                "Лантаноид", "Актиноид"))


def _pairs(elements: list[str]) -> list[tuple[str, str]]:
    """Все пары элементов в веществе, включая связь элемента с собой."""
    result = []
    for index, first in enumerate(elements):
        for second in elements[index:]:
            result.append((first, second))
    return result


def bond_analysis(text: str) -> Result:
    """Определить тип химической связи в веществе."""
    raw = str(text or "").strip()
    if not raw:
        raise InputError("Введите формулу вещества")

    composition = F.parse(raw)
    elements = list(composition.elements)

    if len(elements) == 1:
        symbol = elements[0]
        if symbol in NOBLE:
            kind = "ковалентная неполярная"
            explanation = "одноатомный газ, связи между атомами нет"
        elif _is_metal(symbol):
            kind = "металлическая"
            explanation = "простое вещество-металл, электроны общие"
        else:
            kind = "ковалентная неполярная"
            explanation = "неметалл, электронная пара общая и симметричная"

        res = Result(
            value=kind,
            unit="",
            label=f"Тип связи в {composition.display}",
            method="Определение по составу простого вещества",
        )
        res.with_step(f"{composition.display} — простое вещество")
        res.with_step(f"Тип связи: {kind} ({explanation})")
        res.with_step("Разница электроотрицательностей равна нулю: "
                      "атомы одного элемента")
        res.with_meta("bond_kind", kind)
        res.with_meta("pairs", [])
        res.with_source("Электроотрицательность: шкала Полинга")
        return res

    pairs: list[BondPair] = []
    for first, second in _pairs(elements):
        difference = periodic.electronegativity_difference(first, second)
        if difference is None:
            continue
        kind, explanation = periodic.bond_type(difference)
        pairs.append(BondPair(first, second, difference, kind, explanation))

    if not pairs:
        raise AlchemyError(
            "Не удалось определить электроотрицательность для элементов "
            "в этой формуле")

    # Общий тип связи — по самой полярной связи в молекуле
    strongest = max(pairs, key=lambda item: item.difference)

    rows = []
    for pair in pairs:
        name = (pair.first if pair.first == pair.second
                else f"{pair.first}—{pair.second}")
        rows.append({
            "Связь": name,
            "ΔЭО": f"{pair.difference:.2f}",
            "Тип": pair.kind,
        })

    res = table_result(rows, label=f"Тип связи в {composition.display}",
                       columns=["Связь", "ΔЭО", "Тип"])
    res.method = ("Тип связи по разнице электроотрицательностей "
                  "(шкала Полинга)")
    res.with_step(f"Формула: {composition.display}")
    res.with_step("")
    res.with_step("Шкала разницы электроотрицательностей:")
    res.with_step(f"  до {COVALENT_NONPOLAR_MAX} — ковалентная неполярная")
    res.with_step(f"  от {COVALENT_NONPOLAR_MAX} до {COVALENT_POLAR_MAX} — "
                  f"ковалентная полярная")
    res.with_step(f"  больше {COVALENT_POLAR_MAX} — ионная")
    res.with_step("")
    res.with_step(
        f"Самая полярная связь: {strongest.first}—{strongest.second}, "
        f"ΔЭО = {strongest.difference:.2f}")
    res.with_step(f"Общий тип связи: {strongest.kind}")
    res.with_step(f"Пояснение: {strongest.explanation}")

    # Пограничные значения: C—H даёт 0.35, и школьные учебники обычно
    # считают такую связь полярной, хотя формальный порог 0.4
    if COVALENT_NONPOLAR_MAX - 0.12 <= strongest.difference \
            <= COVALENT_NONPOLAR_MAX + 0.02:
        res.with_warning(
            f"ΔЭО = {strongest.difference:.2f} — пограничное значение. "
            f"Формально связь попадает в неполярную, но многие учебники "
            f"считают связи C—H и подобные полярными.")

    # Для простых случаев полезно указать, куда смещается плотность
    if strongest.kind == "ковалентная полярная":
        first_en = periodic.electronegativity(strongest.first) or 0
        second_en = periodic.electronegativity(strongest.second) or 0
        to = (strongest.first if first_en > second_en
              else strongest.second)
        res.with_step(f"Электронная плотность смещена к атому {to}")

    res.with_meta("bond_kind", strongest.kind)
    res.with_meta("pairs", [(p.first, p.second, p.difference, p.kind)
                            for p in pairs])
    res.with_source("Электроотрицательность: шкала Полинга")
    return res


def crystal_lattice(text: str) -> Result:
    """Тип кристаллической решётки по составу и классу вещества."""
    raw = str(text or "").strip()
    if not raw:
        raise InputError("Введите формулу вещества")

    composition = F.parse(raw)
    normalized = F.normalize_input(raw)
    body, _state = F.split_state(normalized)
    elements = list(composition.elements)

    # Металл или сплав
    if len(elements) == 1 and _is_metal(elements[0]):
        kind = "металлическая"
        reason = "простое вещество-металл"
    elif len(elements) == 1 and elements[0] in NOBLE:
        kind = "молекулярная"
        reason = "благородный газ, отдельные атомы"
    elif body in ATOMIC_LATTICE:
        kind = "атомная"
        reason = "вещество с ковалентной сеткой из атомов"
    elif body in MOLECULAR_LATTICE:
        kind = "молекулярная"
        reason = "вещество состоит из отдельных молекул"
    elif len(elements) == 1:
        kind = "молекулярная"
        reason = "неметалл, простое вещество из молекул"
    else:
        # Соль или соединение металла с неметаллом
        metals = [el for el in elements if _is_metal(el)]
        if metals and len(elements) >= 2:
            difference = max(
                (periodic.electronegativity_difference(el, other) or 0
                 for el in metals for other in elements if other != el),
                default=0)
            if difference > COVALENT_POLAR_MAX:
                kind = "ионная"
                reason = (f"металл с неметаллом, ΔЭО до {difference:.2f}: "
                          f"связь ионная")
            else:
                kind = "молекулярная"
                reason = "ковалентное соединение"
        else:
            kind = "молекулярная"
            reason = "неметаллы, ковалентные молекулы"

    properties = next((row for row in LATTICE_TABLE if row[0] == kind),
                      None)

    res = Result(
        value=kind,
        unit="",
        label=f"Кристаллическая решётка {composition.display}",
        method="Определение по составу и типу химической связи",
    )
    res.with_step(f"Формула: {composition.display}")
    res.with_step(f"Основание: {reason}")
    res.with_step(f"Тип решётки: {kind}")

    if properties:
        res.with_step("")
        res.with_step("Свойства такой решётки:")
        res.with_step(f"  частицы в узлах: {properties[1]}")
        res.with_step(f"  температура плавления: {properties[2]}")
        res.with_step(f"  механические свойства: {properties[3]}")
        res.with_step(f"  электропроводность: {properties[4]}")
        res.with_step(f"  в растворе или расплаве: {properties[5]}")

    res.with_assumption(
        "Тип решётки определяется по составу. Для сложных веществ "
        "(например, слоистых) возможны исключения."
    )
    res.with_meta("lattice", kind)
    res.with_source("Типы кристаллических решёток: школьный курс химии")
    return res


def bond_overview() -> Result:
    """Справочная таблица видов химической связи."""
    rows = [
        {"Вид связи": "Ковалентная неполярная",
         "Как образуется": "общая электронная пара между атомами одного элемента",
         "Примеры": "H2, O2, N2, Cl2",
         "ΔЭО": "до 0.4"},
        {"Вид связи": "Ковалентная полярная",
         "Как образуется": "общая пара смещена к более электроотрицательному атому",
         "Примеры": "H2O, HCl, NH3, CO2",
         "ΔЭО": "0.4 – 1.7"},
        {"Вид связи": "Ионная",
         "Как образуется": "полный переход электрона, образуются ионы",
         "Примеры": "NaCl, KBr, CaO, MgF2",
         "ΔЭО": "больше 1.7"},
        {"Вид связи": "Металлическая",
         "Как образуется": "обобществлённые электроны между атом-ионами",
         "Примеры": "Fe, Cu, Al, сплавы",
         "ΔЭО": "—"},
        {"Вид связи": "Водородная",
         "Как образуется": "атом H связан с F, O или N и притягивает соседний",
         "Примеры": "H2O, HF, NH3, спирты",
         "ΔЭО": "—"},
    ]

    res = table_result(rows, label="Виды химической связи",
                       columns=["Вид связи", "Как образуется", "Примеры", "ΔЭО"])
    res.method = "Справочная таблица школьного курса"
    res.with_step("Разница электроотрицательностей — по шкале Полинга")
    res.with_step("Водородная связь слабее ковалентной примерно в 10 раз, "
                  "но именно она даёт воде высокую температуру кипения")
    res.with_source("Химическая связь: школьный курс, шкала Полинга")
    return res


def lattice_overview() -> Result:
    """Справочная таблица типов кристаллических решёток."""
    rows = [
        {"Тип решётки": kind,
         "Частицы в узлах": particles,
         "Плавление": melting,
         "Механика": mechanical,
         "Ток": current,
         "Раствор": solution}
        for kind, particles, melting, mechanical, current, solution
        in LATTICE_TABLE
    ]

    res = table_result(
        rows, label="Типы кристаллических решёток",
        columns=["Тип решётки", "Частицы в узлах", "Плавление", "Механика",
                 "Ток", "Раствор"])
    res.method = "Справочная таблица школьного курса"
    res.with_step("Металлы проводят ток и в твёрдом виде, и в расплаве")
    res.with_step("Ионные вещества проводят ток только в растворе "
                  "и расплаве, но не в твёрдом виде")
    res.with_source("Кристаллические решётки: школьный курс химии")
    return res
