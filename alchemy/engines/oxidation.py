"""Степени окисления, тип химической реакции и окислитель с восстановителем.

Это школьная часть программы: 8 класс, тема «Окислительно-восстановительные
реакции», и 9 класс, классификация реакций. Логика нарочно простая и
объяснимая, чтобы результат можно было разобрать на уроке: сначала
постоянные степени окисления, потом единственное неизвестное.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core import formula as F
from ..core import periodic
from ..core.errors import AlchemyError, InputError
from ..core.results import Result, table_result

#: реакции по числу и составу веществ
REACTION_TYPES = {
    "connection": "Соединение",
    "decomposition": "Разложение",
    "substitution": "Замещение",
    "exchange": "Обмен",
}

#: постоянные степени окисления в соединениях
FIXED_STATES = {
    "F": -1,
    "Li": 1, "Na": 1, "K": 1, "Rb": 1, "Cs": 1, "Fr": 1,
    "Be": 2, "Mg": 2, "Ca": 2, "Sr": 2, "Ba": 2, "Ra": 2,
    "Al": 3,
    "Zn": 2,
    "Ag": 1,
    "Sc": 3, "Y": 3, "La": 3,
}

#: элементы, чья степень окисления в соединении обычно постоянна
_HALOGENS = ("Cl", "Br", "I")

#: кислотные остатки и их заряды. Школьный метод: сначала узнаём остаток,
#: потом считаем степень окисления его центрального элемента.
RADICALS = {
    "SO4": -2, "SO3": -2, "S2O3": -2, "HSO4": -1, "HSO3": -1,
    "NO3": -1, "NO2": -1,
    "CO3": -2, "HCO3": -1,
    "PO4": -3, "HPO4": -2, "H2PO4": -1,
    "MnO4": -1, "Cr2O7": -2, "CrO4": -2,
    "ClO4": -1, "ClO3": -1, "ClO": -1, "BrO3": -1, "IO3": -1,
    "OH": -1, "CN": -1, "SCN": -1,
    "SiO3": -2, "C2O4": -2, "CH3COO": -1,
}


def _is_simple(species: str) -> bool:
    """Простое ли вещество: один элемент в формуле."""
    try:
        composition = F.parse(species)
    except AlchemyError:
        return False
    return len(composition.elements) == 1


def _oxygen_state(formula: str) -> float:
    """Степень окисления кислорода с учётом пероксидов и фторидов.

    По умолчанию −2, но в пероксидах −1, в надпероксидах −1/2,
    а в соединениях с фтором кислород положителен.
    """
    normalized = F.normalize_input(formula)

    if normalized.startswith("OF2"):
        return 2.0
    if normalized in ("H2O2", "Na2O2", "K2O2", "BaO2", "CaO2", "Li2O2"):
        return -1.0
    if normalized in ("KO2", "NaO2", "CsO2", "RbO2"):
        return -0.5
    return -2.0


def _hydrogen_state(formula: str, other_elements: list[str]) -> float:
    """Степень окисления водорода: +1, но в гидридах металлов −1."""
    normalized = F.normalize_input(formula)
    metals = [el for el in other_elements
              if (periodic.by_symbol(el).category or "").startswith("Щелочн")
              or el in ("Na", "K", "Li", "Ca", "Mg", "Ba", "Al")]
    if metals and normalized.count("H") and len(other_elements) == 1:
        return -1.0
    return 1.0


def _fmt(state: float) -> str:
    """Степень окисления со знаком, но ноль без плюса."""
    if abs(state) < 1e-9:
        return "0"
    return f"{state:+g}"


def _radical_fixes(formula: str) -> dict[str, float]:
    """Степени окисления элементов внутри известных кислотных остатков.

    Для SO4²⁻ остаток даёт серу +6 даже если иначе её не определить.
    Возвращает только те элементы, которые удалось зафиксировать.
    """
    normalized = F.normalize_input(formula)
    body, _state = F.split_state(normalized)

    fixes: dict[str, float] = {}

    # Длинные остатки проверяем первыми: SO4 раньше, чем SO3
    for radical in sorted(RADICALS, key=len, reverse=True):
        if radical not in body:
            continue

        charge = RADICALS[radical]
        try:
            composition = F.parse(radical)
        except AlchemyError:
            continue

        inner = [el for el in composition.elements if el not in ("O", "H")]
        if len(inner) != 1:
            continue

        element = inner[0]
        count = composition.counts[element]
        oxygen = composition.counts.get("O", 0)
        hydrogen = composition.counts.get("H", 0)

        subtotal = oxygen * (-2) + hydrogen * 1
        state = (charge - subtotal) / count

        # Не перезаписываем то, что уже зафиксировано постоянным правилом
        if element not in FIXED_STATES:
            fixes[element] = state

    return fixes


@dataclass
class OxidationState:
    """Степень окисления одного элемента в веществе."""

    element: str
    count: float
    state: float
    #: откуда взялась: постоянная, из правила или вычислена по балансу
    origin: str
    note: str = ""


def oxidation_states(text: str) -> Result:
    """Степени окисления всех элементов в формуле.

    Постоянные степени подставляются из правил, неизвестная вычисляется
    из условия электронейтральности.
    """
    raw = str(text or "").strip()
    if not raw:
        raise InputError("Введите формулу вещества")

    composition = F.parse(raw)
    elements = list(composition.elements)
    counts = {el: composition.counts[el] for el in elements}
    charge = composition.charge

    if len(elements) == 1:
        state = float(charge)
        res = Result(
            value=state,
            unit="",
            label=f"Степень окисления {raw}",
            method="Простое вещество: степень окисления равна нулю "
                   "или заряду иона",
        )
        res.detailed = [
            OxidationState(elements[0], counts[elements[0]], state,
                           "простое вещество")
        ]
        res.with_step(
            f"В веществе один элемент ({elements[0]}), значит каждый его "
            f"атом имеет степень окисления {state:+g}")
        res.with_meta("states", {elements[0]: state})
        return res

    known: dict[str, float] = {}
    origins: dict[str, str] = {}
    notes: dict[str, str] = {}

    # Сначала кислотные остатки: они снимают неоднозначность в солях
    for element, state in _radical_fixes(raw).items():
        known[element] = state
        origins[element] = "из кислотного остатка"

    for element in elements:
        if element in known:
            continue

        if element == "O":
            state = _oxygen_state(raw)
            known[element] = state
            origins[element] = "правило"
            if state != -2:
                notes[element] = "исключение из правила для кислорода"
        elif element == "H":
            known[element] = _hydrogen_state(raw, elements)
            origins[element] = "правило"
        elif element == "F":
            known[element] = -1.0
            origins[element] = "постоянная"
        elif element in FIXED_STATES:
            known[element] = float(FIXED_STATES[element])
            origins[element] = "постоянная"
        elif element in _HALOGENS:
            # Галоген отрицателен, если нет кислорода и фтора рядом
            if "O" not in elements and "F" not in elements:
                known[element] = -1.0
                origins[element] = "правило"

    unknown = [el for el in elements if el not in known]

    if len(unknown) > 1:
        raise AlchemyError(
            "Нельзя определить степени окисления однозначно: неизвестных "
            f"элементов {len(unknown)} ({', '.join(unknown)}). Школьные "
            f"правила дают только одну неизвестную. Если это соль, проверьте, "
            f"что кислотный остаток известен."
        )

    if unknown:
        element = unknown[0]
        subtotal = sum(known[el] * counts[el] for el in known)
        state = (charge - subtotal) / counts[element]
        known[element] = state
        origins[element] = "вычислена по балансу зарядов"
    else:
        subtotal = sum(known[el] * counts[el] for el in known)
        if abs(subtotal - charge) > 1e-6:
            raise AlchemyError(
                f"Формула {raw} не сходится по заряду: сумма известных "
                f"степеней {subtotal:+g}, а заряд {charge:+d}. "
                f"Возможно, это пероксид или необычное соединение."
            )

    states = {el: known[el] for el in elements}
    rows = []
    for element in elements:
        status = origins.get(element, "вычислена")
        rows.append({
            "Элемент": f"{element} ({periodic.by_symbol(element).name_ru})",
            "Атомов": f"{counts[element]:g}",
            "Степень окисления": f"{states[element]:+g}",
            "Откуда": status,
        })

    res = table_result(rows, label=f"Степени окисления в {composition.display}",
                       columns=["Элемент", "Атомов", "Степень окисления",
                                "Откуда"])
    res.method = ("Постоянные степени окисления из правил, неизвестная "
                  "вычислена из электронейтральности")
    res.with_step(f"Формула: {composition.display}")
    if charge:
        res.with_step(f"Заряд частицы: {charge:+d}")
    res.with_step("")
    res.with_step("Ход расчёта:")

    for element in elements:
        if origins.get(element) in ("постоянная", "правило"):
            res.with_step(
                f"  {element}: {states[element]:+g} — "
                f"{'постоянная' if origins[element] == 'постоянная' else 'по правилу'}")

    res.with_step("")
    for element in elements:
        value = states[element] * counts[element]
        res.with_step(f"  {element}: {counts[element]:g} × "
                      f"({states[element]:+g}) = {value:+g}")

    total = sum(states[el] * counts[el] for el in elements)
    res.with_step(f"  Сумма: {total:+g} (должна равняться заряду {charge:+d})")

    res.detailed = [
        OxidationState(el, counts[el], states[el],
                       origins.get(el, ""), notes.get(el, ""))
        for el in elements
    ]
    res.with_meta("states", states)
    res.with_source("Правила степеней окисления: IUPAC, школьный курс")
    return res


def reaction_type(equation: str) -> Result:
    """Тип реакции по числу и составу веществ."""
    from ..engines import balancer as BAL

    text = str(equation or "").strip()
    if not text:
        raise InputError("Введите уравнение реакции")

    left, right = BAL.parse_equation(text)
    left_simple = [sp for sp in left if _is_simple(sp)]
    right_simple = [sp for sp in right if _is_simple(sp)]

    if len(left) >= 2 and len(right) == 1:
        kind = "connection"
    elif len(left) == 1 and len(right) >= 2:
        kind = "decomposition"
    elif len(left_simple) == 1 and len(right_simple) == 1:
        kind = "substitution"
    elif len(left) >= 2 and len(right) >= 2:
        kind = "exchange"
    else:
        raise AlchemyError(
            "Не удалось отнести реакцию к одному из четырёх типов. "
            "Проверьте запись уравнения."
        )

    name = REACTION_TYPES[kind]
    res = Result(
        value=name,
        unit="",
        label=f"Тип реакции: {name.lower()}",
        method="Классификация по числу и составу исходных веществ и продуктов",
    )
    res.with_step(f"Исходных веществ: {len(left)} — {', '.join(left)}")
    res.with_step(f"Продуктов: {len(right)} — {', '.join(right)}")
    res.with_step("")

    if kind == "connection":
        res.with_step("Несколько веществ соединяются в одно.")
    elif kind == "decomposition":
        res.with_step("Одно вещество распадается на несколько.")
    elif kind == "substitution":
        res.with_step(
            f"Простое вещество ({', '.join(left_simple)}) замещает атомы "
            f"в сложном, образуя новое простое ({', '.join(right_simple)}).")
    else:
        res.with_step("Два сложных вещества обмениваются составными частями.")

    res.with_meta("reaction_kind", kind)
    res.with_meta("left", list(left))
    res.with_meta("right", list(right))
    return res


def _changes(equation: str) -> list[dict]:
    """Какие элементы меняют степень окисления в реакции."""
    from ..engines import balancer as BAL

    left, right = BAL.parse_equation(equation)

    def states_of(species_list):
        result = []
        for species in species_list:
            try:
                res = oxidation_states(species)
            except AlchemyError:
                continue
            result.append((species, res.meta.get("states", {})))
        return result

    left_states = states_of(left)
    right_states = states_of(right)

    # элемент -> набор значений слева и справа
    left_map: dict[str, list[float]] = {}
    right_map: dict[str, list[float]] = {}
    for _species, states in left_states:
        for element, value in states.items():
            left_map.setdefault(element, []).append(value)
    for _species, states in right_states:
        for element, value in states.items():
            right_map.setdefault(element, []).append(value)

    changes = []
    for element in sorted(set(left_map) & set(right_map)):
        before = left_map[element]
        after = right_map[element]
        for value_before in before:
            for value_after in after:
                if abs(value_before - value_after) > 1e-9:
                    changes.append({
                        "element": element,
                        "before": value_before,
                        "after": value_after,
                        "delta": value_after - value_before,
                    })
    return changes


def oxidizer_reducer(equation: str) -> Result:
    """Кто в реакции окислитель, кто восстановитель."""
    text = str(equation or "").strip()
    if not text:
        raise InputError("Введите уравнение реакции")

    changes = _changes(text)
    if not changes:
        raise AlchemyError(
            "В этой реакции степени окисления не меняются, значит она "
            "не окислительно-восстановительная. Примеры таких реакций: "
            "обмен ионов, нейтрализация."
        )

    rows = []
    oxidizers, reducers = [], []
    for change in changes:
        delta = change["delta"]
        if delta > 0:
            role = "Восстановитель (отдаёт электроны)"
            reducers.append(change["element"])
        else:
            role = "Окислитель (принимает электроны)"
            oxidizers.append(change["element"])

        rows.append({
            "Элемент": change["element"],
            "Было": f"{change['before']:+g}",
            "Стало": f"{change['after']:+g}",
            "Электронов": f"{abs(delta):g}",
            "Роль": role,
        })

    res = table_result(rows, label="Окислитель и восстановитель",
                       columns=["Элемент", "Было", "Стало", "Электронов", "Роль"])
    res.method = "Сравнение степеней окисления до и после реакции"
    res.with_step(f"Уравнение: {text}")
    res.with_step("")
    for change in changes:
        delta = change["delta"]
        direction = "отдаёт" if delta > 0 else "принимает"
        res.with_step(
            f"  {change['element']}: {change['before']:+g} → "
            f"{change['after']:+g}, {direction} {abs(delta):g} e⁻")
    res.with_step("")
    if oxidizers:
        res.with_step(f"Окислитель: {', '.join(sorted(set(oxidizers)))}")
    if reducers:
        res.with_step(f"Восстановитель: {', '.join(sorted(set(reducers)))}")

    res.with_assumption(
        "Окислитель принимает электроны и сам восстанавливается. "
        "Восстановитель отдаёт электроны и сам окисляется."
    )
    res.with_meta("changes", changes)
    res.with_meta("oxidizers", sorted(set(oxidizers)))
    res.with_meta("reducers", sorted(set(reducers)))
    return res
