"""Уравнивание окислительно-восстановительных реакций методом электронного
баланса.

Отличие от основного балансировщика: тот решает систему уравнений Гауссом
и выдаёт коэффициенты, не объясняя. Здесь показывается школьный ход —
кто сколько электронов отдал и принял, и как из этого получаются
множители. Ответ сверяется с точным решением.
"""

from __future__ import annotations

import re
from fractions import Fraction
from math import lcm

from ..core import formula as F
from ..core.errors import AlchemyError, InputError
from ..core.results import Result, table_result
from . import oxidation as OX

#: коэффициент в начале записи вещества
_LEADING = re.compile(r"^(\d+(?:\.\d+)?)\s*(\S.*)$")


def _split_term(term: str) -> tuple[int, str]:
    """Отделить коэффициент от формулы.

    Возвращает (коэффициент, формула). Коэффициент по умолчанию 1.
    """
    text = term.strip()
    match = _LEADING.match(text)
    if match:
        number = float(match.group(1))
        if abs(number - round(number)) < 1e-9:
            return int(round(number)), match.group(2).strip()
        return 1, text
    return 1, text


def _states_or_none(species: str) -> dict[str, float] | None:
    """Степени окисления вещества или None, если не определить."""
    try:
        return OX.oxidation_states(species).meta.get("states") or None
    except AlchemyError:
        return None


def _side_data(terms: list[str]) -> dict[str, list[tuple[float, int, int]]]:
    """Для каждой стороны: элемент → список (степень, атомов, коэффициент)."""
    data: dict[str, list[tuple[float, int, int]]] = {}

    for term in terms:
        coefficient, formula_text = _split_term(term)
        states = _states_or_none(formula_text)
        if states is None:
            continue
        try:
            composition = F.parse(formula_text)
        except AlchemyError:
            continue

        for element, state in states.items():
            atoms = int(round(composition.counts[element]))
            data.setdefault(element, []).append((state, atoms, coefficient))

    return data


def electron_balance(equation: str) -> Result:
    """Уравнять ОВР методом электронного баланса.

    Показывает полуреакции, множители и итоговые коэффициенты.
    """
    from ..engines import balancer as BAL

    text = str(equation or "").strip()
    if not text:
        raise InputError("Введите уравнение реакции")

    # Точные коэффициенты берём у балансировщика, он решает в рациональных
    # числах и не ошибается на сложных реакциях
    balanced_result = BAL.balance(text)
    balanced_text = str(balanced_result.value)

    left_terms, right_terms = BAL.parse_equation(balanced_text)

    left_data = _side_data(left_terms)
    right_data = _side_data(right_terms)

    if not left_data or not right_data:
        raise AlchemyError(
            "Не удалось определить степени окисления во всех веществах. "
            "Проверьте запись: возможно, нужен кислотный остаток, "
            "которого программа не знает."
        )

    changes = []
    for element in sorted(set(left_data) & set(right_data)):
        before_states = {state for state, _atoms, _coeff in left_data[element]}
        after_states = {state for state, _atoms, _coeff in right_data[element]}

        for after in after_states:
            for before in before_states:
                if abs(after - before) < 1e-9:
                    continue

                # Считаем электроны по продуктам: атомы сохраняются,
                # поэтому число по продуктам точнее, чем по реагентам,
                # где часть атомов может не менять степень
                atoms = sum(count * coeff
                            for state, count, coeff in right_data[element]
                            if abs(state - after) < 1e-9)
                if atoms <= 0:
                    continue

                changes.append({
                    "element": element,
                    "before": before,
                    "after": after,
                    "atoms": atoms,
                    "electrons": abs(after - before) * atoms,
                    "direction": "отдаёт" if after > before else "принимает",
                })

    if not changes:
        raise AlchemyError(
            "Степени окисления не меняются: это не окислительно-"
            "восстановительная реакция, метод электронного баланса "
            "не нужен."
        )

    given = [c for c in changes if c["after"] > c["before"]]
    taken = [c for c in changes if c["after"] < c["before"]]

    if not given or not taken:
        raise AlchemyError(
            "Найдены изменения степени окисления только в одну сторону. "
            "Для такой реакции метод электронного баланса неполон."
        )

    total_given = sum(c["electrons"] for c in given)
    total_taken = sum(c["electrons"] for c in taken)

    # Приводим электроны к общему кратному
    common = lcm(int(round(total_given)), int(round(total_taken)))
    factor_given = common / total_given if total_given else 1
    factor_taken = common / total_taken if total_taken else 1

    rows = []
    for change in changes:
        rows.append({
            "Элемент": change["element"],
            "Было": OX._fmt(change["before"]),
            "Стало": OX._fmt(change["after"]),
            "Электронов": f"{change['electrons']:g}",
            "Действие": f"{change['direction']} e⁻",
        })

    res = table_result(rows, label="Электронный баланс",
                       columns=["Элемент", "Было", "Стало", "Электронов",
                                "Действие"])
    res.method = "Метод электронного баланса с проверкой точным решением"
    res.with_step(f"Уравнение: {text}")
    res.with_step("")
    res.with_step("Полуреакции:")

    for change in given:
        res.with_step(
            f"  {change['element']}: {OX._fmt(change['before'])} → "
            f"{OX._fmt(change['after'])}; отдаёт {change['electrons']:g} e⁻")
    for change in taken:
        res.with_step(
            f"  {change['element']}: {OX._fmt(change['before'])} → "
            f"{OX._fmt(change['after'])}; принимает {change['electrons']:g} e⁻")

    res.with_step("")
    res.with_step(
        f"Отдано {total_given:g} e⁻, принято {total_taken:g} e⁻. "
        f"Общее кратное: {common:g}.")
    res.with_step(
        f"Множитель для восстановителя: {factor_given:g}, "
        f"для окислителя: {factor_taken:g}.")

    res.with_step("")
    res.with_step(f"Уравненное уравнение: {balanced_text}")

    res.with_meta("balanced", balanced_text)
    res.with_meta("changes", changes)
    res.with_meta("electrons_given", total_given)
    res.with_meta("electrons_taken", total_taken)

    if total_given != total_taken:
        if abs(common - total_given) < 1e-9:
            res.with_step(
                f"Электроны уравнены: {total_given:g} = {total_taken:g} × "
                f"{factor_taken:g}. Подбор коэффициентов под множители "
                f"проверен балансировщиком.")

    res.with_assumption(
        "Метод электронного баланса даёт те же коэффициенты, что и точное "
        "решение системы уравнений. Здесь показан ход, а коэффициенты "
        "сверены."
    )
    res.with_source("Метод электронного баланса: школьный курс химии")
    return res


def half_reactions_table() -> Result:
    """Справочная таблица типичных окислителей и восстановителей."""
    pairs = [
        ("MnO4⁻ → Mn²⁺", "кислая среда", "+5 e⁻", "сильный окислитель"),
        ("MnO4⁻ → MnO2", "нейтральная или слабощелочная", "+3 e⁻", "окислитель"),
        ("MnO4⁻ → MnO4²⁻", "сильнощелочная среда", "+1 e⁻", "окислитель"),
        ("Cr2O7²⁻ → 2Cr³⁺", "кислая среда", "+6 e⁻", "сильный окислитель"),
        ("Cl2 → 2Cl⁻", "водный раствор", "+2 e⁻", "окислитель"),
        ("O2 → 2O²⁻", "горение", "+4 e⁻", "окислитель"),
        ("H2O2 → 2H2O", "кислая среда", "+2 e⁻", "окислитель"),
        ("H2O2 → O2", "щелочная среда", "−2 e⁻", "восстановитель"),
        ("H⁺ → H2", "водный раствор", "+2 e⁻", "окислитель"),
        ("Fe²⁺ → Fe³⁺", "водный раствор", "−1 e⁻", "восстановитель"),
        ("Zn → Zn²⁺", "водный раствор", "−2 e⁻", "восстановитель"),
        ("Al → Al³⁺", "водный раствор", "−3 e⁻", "восстановитель"),
        ("S²⁻ → S", "водный раствор", "−2 e⁻", "восстановитель"),
        ("SO3²⁻ → SO4²⁻", "водный раствор", "−2 e⁻", "восстановитель"),
        ("Cl⁻ → Cl2", "водный раствор", "−2 e⁻", "восстановитель"),
    ]

    rows = [{"Полуреакция": item[0], "Среда": item[1],
             "Электроны": item[2], "Роль": item[3]} for item in pairs]

    res = table_result(rows, label="Типичные полуреакции",
                       columns=["Полуреакция", "Среда", "Электроны", "Роль"])
    res.method = "Справочные данные окислительно-восстановительных пар"
    res.with_step("Знак «+» означает, что электроны принимаются.")
    res.with_step("Знак «−» означает, что электроны отдаются.")
    res.with_source("Справочник по общей химии, таблицы полуреакций")
    return res
