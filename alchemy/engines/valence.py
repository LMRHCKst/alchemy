"""Валентность: определить по формуле и составить формулу по валентностям.

8 класс, самая первая тема. Работает для бинарных соединений: валентность
одного элемента известна, второго вычисляется из соотношения атомов.

Для сложных веществ (кислоты, соли) валентность — это заряд остатка,
и там честнее говорить о степени окисления; движок об этом предупреждает.
"""

from __future__ import annotations

import math
import re

from ..core import formula as F
from ..core import periodic
from ..core.errors import InputError
from ..core.results import Result

#: возможные валентности элементов по школьной программе
VALENCES: dict[str, tuple[int, ...]] = {
    "H": (1,), "Li": (1,), "Na": (1,), "K": (1,), "Rb": (1,), "Cs": (1,),
    "Ag": (1,), "Be": (2,), "Mg": (2,), "Ca": (2,), "Sr": (2,), "Ba": (2,),
    "Zn": (2,), "Cd": (2,), "Cu": (1, 2), "Fe": (2, 3), "Co": (2, 3),
    "Ni": (2, 3), "Sn": (2, 4), "Pb": (2, 4), "Hg": (1, 2),
    "Al": (3,), "B": (3,), "Cr": (2, 3, 6), "Mn": (2, 4, 6, 7),
    "C": (2, 4), "Si": (4,), "N": (3, 5), "P": (3, 5),
    "S": (2, 4, 6), "Se": (2, 4, 6), "Te": (2, 4, 6),
    "F": (1,), "Cl": (1, 3, 5, 7), "Br": (1, 3, 5, 7), "I": (1, 3, 5, 7),
    "O": (2,),
}

#: элементы, которые в бинарном соединении пишутся первыми
METAL_FIRST = True


def valency_options(symbol: str) -> tuple[int, ...]:
    """Какие валентности бывают у элемента."""
    try:
        return VALENCES[symbol]
    except KeyError:
        raise InputError(
            f"Для элемента «{symbol}» таблицы валентностей нет. "
            f"Она составлена для элементов, которые проходят в школе."
        ) from None


def _binary(formula: str) -> tuple[str, str, int, int]:
    """Разобрать бинарное соединение: элементы и числа атомов."""
    clean = F.split_state(formula)[0]
    counts = F.parse(clean).counts
    if len(counts) != 2:
        raise InputError(
            f"«{formula}» — не бинарное соединение: в нём "
            f"{len(counts)} элементов. Валентность по формуле определяется "
            f"для двух элементов; для остальных смотрите степени окисления."
        )
    first, second = list(counts)
    return first, second, int(counts[first]), int(counts[second])


def valences(formula: str) -> Result:
    """Определить валентности двух элементов по формуле."""
    first, second, n_first, n_second = _binary(formula)

    options_first = VALENCES.get(first, ())
    options_second = VALENCES.get(second, ())
    if not options_first or not options_second:
        raise InputError(
            f"Не знаю валентностей для {first if not options_first else second}. "
            f"Таблица составлена для школьного набора элементов."
        )

    found: tuple[int, int] | None = None
    for factor in range(1, 13):
        v_first = factor * n_second
        v_second = factor * n_first
        if v_first in options_first and v_second in options_second:
            found = (v_first, v_second)
            break

    if found is None:
        raise InputError(
            f"Не удалось подобрать валентности для «{formula}»: перебор "
            f"дал {first} {n_second} и {second} {n_first}, но таких "
            f"валентностей у этих элементов нет. Проверьте формулу."
        )

    v_first, v_second = found
    res = Result(
        value=f"{first} — {v_first}, {second} — {v_second}",
        unit="",
        label="Валентности элементов",
        method="Произведение числа атомов на валентность одинаково у обоих элементов",
    )
    res.with_step(f"Формула: {first}{n_first or ''}{second}{n_second or ''}")
    res.with_step(
        f"{n_first}·V({first}) = {n_second}·V({second})")
    res.with_step(f"V({first}) = {v_first}, V({second}) = {v_second}")
    res.with_step(
        f"Проверка: {n_first}·{v_first} = {n_second}·{v_second} = "
        f"{n_first * v_first}")
    res.with_meta("first", first)
    res.with_meta("second", second)
    res.with_meta("valency_first", v_first)
    res.with_meta("valency_second", v_second)
    res.with_assumption(
        "Для одного и того же элемента валентность бывает разной "
        "(у железа 2 и 3, у серы 2, 4, 6). Здесь выбраны значения, "
        "при которых выполняется соотношение атомов."
    )
    return res


def formula_from_valence(first: str, valency_first: int,
                         second: str, valency_second: int) -> Result:
    """Составить формулу по валентностям: Al(III) и O(II) → Al2O3."""
    if valency_first <= 0 or valency_second <= 0:
        raise InputError("Валентности должны быть положительными")

    options_first = VALENCES.get(first, ())
    options_second = VALENCES.get(second, ())
    if options_first and valency_first not in options_first:
        raise InputError(
            f"У {first} не бывает валентности {valency_first}. "
            f"Бывает: {', '.join(str(v) for v in options_first)}."
        )
    if options_second and valency_second not in options_second:
        raise InputError(
            f"У {second} не бывает валентности {valency_second}. "
            f"Бывает: {', '.join(str(v) for v in options_second)}."
        )

    divisor = math.gcd(valency_first, valency_second)
    first_count = valency_second // divisor
    second_count = valency_first // divisor

    # металл пишется первым
    try:
        first_is_metal = periodic.by_symbol(first).category in (
            "Переходный металл", "Постпереходный металл", "Щелочной металл",
            "Щёлочноземельный металл", "Лантаноид", "Актиноид")
        second_is_metal = periodic.by_symbol(second).category in (
            "Переходный металл", "Постпереходный металл", "Щелочной металл",
            "Щёлочноземельный металл", "Лантаноид", "Актиноид")
    except Exception:
        first_is_metal = second_is_metal = False

    order = (first, second)
    counts = (first_count, second_count)
    if not first_is_metal and second_is_metal:
        order = (second, first)
        counts = (second_count, first_count)

    def part(symbol: str, amount: int) -> str:
        return symbol if amount == 1 else f"{symbol}{amount}"

    built = part(order[0], counts[0]) + part(order[1], counts[1])

    res = Result(
        value=built,
        unit="",
        label="Формула по валентностям",
        method="Индексы обратны валентностям: число атомов = валентность "
               "другого элемента, сокращённое на общий делитель",
    )
    res.with_step(f"V({first}) = {valency_first}, V({second}) = {valency_second}")
    res.with_step(
        f"Индексы: {valency_second}:{valency_first} → "
        f"{first_count}:{second_count}")
    if divisor > 1:
        res.with_step(f"Сократили на {divisor}")
    res.with_step(f"Формула: {built}")
    res.with_meta("formula", built)
    res.with_meta("count_first", counts[0] if order[0] == first else counts[1])
    res.with_assumption(
        "Способ работает, когда валентности известны и не сокращаются "
        "до единицы по ошибке."
    )
    return res
