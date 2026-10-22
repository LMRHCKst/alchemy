"""Уравнивание химических реакций методом Гаусса в точной арифметике.

Принципиальное отличие от типичных реализаций: коэффициенты ищутся в рациональных
числах (fractions.Fraction), а не в числах с плавающей точкой. Поэтому результат
точный, а не «примерно целый», и не зависит от того, установлена ли внешняя
библиотека. Стехиометрия, заряд и баланс массы проверяются явно, а не
предполагаются выполненными.

Поддерживается:
    H2 + O2 = H2O
    KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O          (окислительно-восстановительная)
    MnO4^- + H+ + e^- = Mn^2+ + H2O               (в ионной форме, с электроном)
    Cr2O7^2- + H+ + e^- = Cr^3+ + H2O             (с сохранением заряда)
"""

from __future__ import annotations

import re
from fractions import Fraction
from functools import reduce
from math import gcd
from typing import Iterable

from ..core import formula as F
from ..core.errors import DomainError, InputError
from ..core.results import Result, table_result


class BalanceError(InputError):
    """Реакцию уравнять нельзя."""


# --------------------------------------------------------------------------
# Разбор записи реакции
# --------------------------------------------------------------------------

_SPLIT_RE = re.compile(r"\s*(?:\+|→|⇄|⇌|<=>|->|=>|=)\s*")


def parse_side(side: str | Iterable[str]) -> list[str]:
    """Разобрать одну сторону реакции в список веществ.

    Принимает строку «H2 + O2» или готовый список.

    Разделитель «+» не должен разрывать ионы: «H^+ + e^-» — это два вещества,
    а не три. Поэтому знак, стоящий сразу после цифры или после «^», считается
    частью заряда, а не разделителем.
    """
    if isinstance(side, str):
        clean = side.strip()
        if not clean:
            raise BalanceError("Пустая часть уравнения реакции")

        # Разделяем по «+» только там, где он не является знаком заряда
        parts = _split_species(clean)
    else:
        parts = [str(p).strip() for p in side if str(p).strip()]

    if not parts:
        raise BalanceError("Не найдено ни одного вещества")
    return parts


def _split_species(text: str) -> list[str]:
    """Разбить строку на вещества, не задевая знаки зарядов.

    Главная трудность: символ «+» в химической записи означает и знак заряда
    («Ag+»), и разделитель между веществами («Ag+ + Cl-»). Различить их
    можно по окружению:

    * разделитель всегда стоит после пробела («H2 + O2») либо вплотную
      к началу следующей формулы («H2+O2»);
    * знак заряда всегда приклеен к своей формуле и отделён от следующего
      вещества пробелом («Ag+ + Cl-»).

    Раньше знак заряда распознавался только в записи с «^» («H^+»), поэтому
    обычные «H+», «Ag+», «Fe2+» считались разделителями, и ионные уравнения
    в общепринятой записи не уравнивались.
    """
    normalized = text.strip()

    for arrow in ("→", "->", "=>"):
        if arrow in normalized:
            raise BalanceError(
                "В одной части уравнения найдена стрелка. "
                "Уравнение должно быть вида «реагенты = продукты»"
            )

    parts: list[str] = []
    buffer: list[str] = []
    i = 0
    n = len(normalized)

    while i < n:
        ch = normalized[i]

        if ch == "+":
            prev = buffer[-1] if buffer else ""
            # Символ сразу после плюса, без пропуска пробелов
            immediate = normalized[i + 1] if i + 1 < n else ""

            # Разделитель: плюс стоит после пробела или вплотную перед
            # началом следующей формулы
            starts_next = bool(immediate) and (
                immediate.isalnum() or immediate in "([{")
            is_separator = (not prev) or prev.isspace() or starts_next

            if is_separator:
                token = "".join(buffer).strip()
                if token:
                    parts.append(token)
                buffer = []
            else:
                buffer.append(ch)
            i += 1
            continue

        buffer.append(ch)
        i += 1

    token = "".join(buffer).strip()
    if token:
        parts.append(token)

    return parts


def parse_equation(equation: str) -> tuple[list[str], list[str]]:
    """Разобрать полное уравнение «реагенты = продукты»."""
    text = str(equation).strip()
    if not text:
        raise BalanceError("Уравнение реакции не задано")

    # Ищем разделитель между левой и правой частью. Обратимые стрелки
    # (⇄, ⇌, <=>) школьники пишут так же часто, как «=», поэтому они
    # здесь тоже разделители: для уравнивания направление не важно.
    for sep in ("<=>", "⇄", "⇌", "=>", "->", "→", "="):
        if sep in text:
            left, _, right = text.partition(sep)
            return parse_side(left), parse_side(right)

    raise BalanceError(
        "В уравнении не найден разделитель сторон. "
        "Используйте «=», «->», «→» или «⇄»"
    )


# --------------------------------------------------------------------------
# Матрица состава
# --------------------------------------------------------------------------


def _strip_written_coefficient(text: str) -> str:
    """Убрать записанный коэффициент из текста вещества.

    «2H2O» -> «H2O». Коэффициент при этом не теряется: он хранится
    в составе и проверяется отдельно. Нужно это для вывода: иначе
    формат «коэффициент + текст» даёт «22H2O».

    Электрон записывается строчной буквой, поэтому его коэффициент
    отрезается отдельным правилом.
    """
    stripped = text.strip()
    match = re.match(r"^(\d+(?:\.\d+)?)(?=[A-Z\[\(])", stripped)
    if match:
        return stripped[match.end():]
    match = re.match(r"^(\d+)(?=e\^?-?\s*$)", stripped)
    if match:
        return stripped[match.end():]
    return stripped


class _Species:
    """Вещество реакции с разобранным составом."""

    __slots__ = ("text", "comp", "side", "index")

    def __init__(self, text: str, side: str, index: int):
        self.side = side          # 'left' или 'right'
        self.index = index
        self.comp = F.parse(text, allow_charge=True)
        # Записанный пользователем коэффициент уже учтён в составе, поэтому
        # из текста его убираем: иначе при выводе он приклеится к самому себе
        # и «2H2» превратится в «22H2».
        self.text = _strip_written_coefficient(text)

    @property
    def charge(self) -> int:
        # Коэффициент здесь не применяется: в балансировщике он неизвестная
        # величина, которую как раз и надо найти.
        return int(self.comp.charge)

    @property
    def counts(self) -> dict[str, float]:
        # Коэффициент не применяется — см. пояснение выше.
        return self.comp.counts

    @property
    def is_electron(self) -> bool:
        return not self.comp.counts and self.charge != 0

    def __repr__(self) -> str:
        return f"<{self.text} ({self.side})>"


def _build_matrix(species: list[_Species]) -> tuple[list[str], list[list[Fraction]]]:
    """Построить матрицу: строки — элементы и заряд, столбцы — вещества.

    Продукты входят со знаком минус, чтобы уравнение A = B превратилось в
    однородную систему: сумма по реагентам минус сумма по продуктам = 0.
    """
    elements: list[str] = []
    for sp in species:
        for el in sp.counts:
            if el not in elements:
                elements.append(el)
    elements.sort()

    rows: list[list[Fraction]] = []
    sign = {"left": 1, "right": -1}

    for el in elements:
        row = []
        for sp in species:
            value = sp.counts.get(el, 0.0)
            row.append(_to_fraction(value) * sign[sp.side])
        rows.append(row)

    # Баланс заряда — отдельная строка, если среди веществ есть ионы
    if any(sp.charge for sp in species):
        row = []
        for sp in species:
            row.append(Fraction(sp.charge) * sign[sp.side])
        rows.append(row)
        elements.append("заряд")

    return elements, rows


def _to_fraction(value: float) -> Fraction:
    """Перевести число атомов в точную дробь без потери смысла."""
    if float(value).is_integer():
        return Fraction(int(value))
    return Fraction(value).limit_denominator(1000)


# --------------------------------------------------------------------------
# Линейная алгебра в точной арифметике
# --------------------------------------------------------------------------


def _rref(matrix: list[list[Fraction]]) -> tuple[list[list[Fraction]], list[int]]:
    """Приведённая ступенчатая форма. Возвращает матрицу и номера ведущих столбцов."""
    m = [row[:] for row in matrix]
    if not m:
        return m, []

    rows = len(m)
    cols = len(m[0])
    pivots: list[int] = []
    r = 0

    for c in range(cols):
        # Ищем ведущий элемент
        pivot = None
        for i in range(r, rows):
            if m[i][c] != 0:
                pivot = i
                break
        if pivot is None:
            continue

        m[r], m[pivot] = m[pivot], m[r]

        # Нормируем строку
        lead = m[r][c]
        m[r] = [x / lead for x in m[r]]

        # Обнуляем столбец во всех остальных строках
        for i in range(rows):
            if i != r and m[i][c] != 0:
                factor = m[i][c]
                m[i] = [a - factor * b for a, b in zip(m[i], m[r])]

        pivots.append(c)
        r += 1
        if r == rows:
            break

    return m, pivots


def _nullspace(matrix: list[list[Fraction]], n_cols: int) -> list[list[Fraction]] | None:
    """Найти базис ядра матрицы.

    Возвращает None, если решение не единственно с точностью до множителя
    (ядро размерности больше единицы) — тогда реакцию уравнять однозначно
    нельзя, и об этом надо сказать честно.
    """
    if not matrix:
        return None

    m, pivots = _rref(matrix)
    free = [c for c in range(n_cols) if c not in pivots]

    if len(free) != 1:
        return None

    free_col = free[0]
    vector = [Fraction(0)] * n_cols
    vector[free_col] = Fraction(1)

    # Обратная подстановка
    for i, pc in enumerate(pivots):
        if pc == free_col:
            continue
        # m[i][pc] = 1, свободная переменная даёт вклад -m[i][free_col]
        vector[pc] = -m[i][free_col]

    return [vector]


def _to_integers(vector: list[Fraction]) -> list[int]:
    """Привести вектор дробей к наименьшим целым числам.

    Общий знаменатель умножается, затем делится на НОД числителей.
    """
    denoms = [f.denominator for f in vector]
    lcm = reduce(lambda a, b: a * b // gcd(a, b), denoms, 1)
    ints = [int(f * lcm) for f in vector]

    g = reduce(gcd, (abs(i) for i in ints), 0)
    if g > 1:
        ints = [i // g for i in ints]

    return ints


# --------------------------------------------------------------------------
# Основная функция
# --------------------------------------------------------------------------


def balance(equation: str | tuple[Iterable[str], Iterable[str]]) -> Result:
    """Уравнять химическую реакцию.

    Args:
        equation: строка «H2 + O2 = H2O» либо пара (реагенты, продукты).

    Returns:
        Result со значением-строкой, коэффициентами и проверкой баланса.
    """
    if isinstance(equation, tuple):
        left_raw, right_raw = equation
        left = parse_side(left_raw)
        right = parse_side(right_raw)
    else:
        left, right = parse_equation(equation)

    if not left or not right:
        raise BalanceError("В реакции должны быть и реагенты, и продукты")

    # Дубликаты веществ ломают линейную систему: это разные столбцы
    # с одинаковым составом, и решение становится неоднозначным
    all_texts = [_canonical(t) for t in left + right]
    if len(set(all_texts)) != len(all_texts):
        seen = set()
        for t in all_texts:
            if t in seen:
                raise BalanceError(
                    f"Вещество «{t}» встречается в уравнении дважды. "
                    f"Объедините его в одну часть уравнения."
                )
            seen.add(t)

    species = (
        [_Species(t, "left", i) for i, t in enumerate(left)]
        + [_Species(t, "right", i) for i, t in enumerate(right)]
    )

    elements, matrix = _build_matrix(species)

    if all(all(v == 0 for v in row) for row in matrix):
        raise BalanceError("В реакции не участвует ни один элемент")

    solution = _nullspace(matrix, len(species))
    if solution is None:
        raise BalanceError(
            "Не удалось уравнять реакцию однозначно. Возможные причины: "
            "реакция записана неверно, либо она допускает несколько "
            "независимых решений (например, параллельные маршруты)."
        )

    coeffs = _to_integers(solution[0])

    # Отрицательные коэффициенты означают, что вещество попало не на ту сторону
    if all(c < 0 for c in coeffs):
        coeffs = [-c for c in coeffs]
    if any(c < 0 for c in coeffs):
        negatives = [species[i].text for i, c in enumerate(coeffs) if c < 0]
        raise BalanceError(
            f"Отрицательные коэффициенты у: {', '.join(negatives)}. "
            f"Скорее всего, эти вещества записаны не в своей части уравнения."
        )
    if any(c == 0 for c in coeffs):
        zeros = [species[i].text for i, c in enumerate(coeffs) if c == 0]
        raise BalanceError(
            f"Вещества {', '.join(zeros)} не участвуют в реакции — "
            f"их coefficients равны нулю. Проверьте запись."
        )

    n_left = len(left)
    left_coeffs = {species[i].text: coeffs[i] for i in range(n_left)}
    right_coeffs = {species[i].text: coeffs[i] for i in range(n_left, len(species))}

    # ---------------- проверка баланса ----------------

    check = _verify(species, coeffs, elements)

    equation_text = _format_equation(species, coeffs, n_left)

    result = Result(
        value=equation_text,
        unit="",
        label="Уравнение реакции",
        method="Метод Гаусса в рациональной арифметике с балансом заряда",
    )
    result.with_meta("left", left_coeffs)
    result.with_meta("right", right_coeffs)
    result.with_meta("coefficients", {sp.text: coeffs[i] for i, sp in enumerate(species)})
    result.with_meta("elements", check)

    for el, data in check.items():
        result.with_step(
            f"{el}: слева {data['left']:g}, справа {data['right']:g} — сходится"
        )

    if any(sp.charge for sp in species):
        result.with_assumption(
            "Учтён баланс заряда: суммарный заряд слева равен суммарному справа"
        )

    if any(sp.is_electron for sp in species):
        result.with_assumption(
            "Электрон учтён как частица с зарядом −1 и пренебрежимо малой массой"
        )

    max_coeff = max(coeffs)
    if max_coeff > 50:
        result.with_warning(
            f"Наибольший коэффициент равен {max_coeff} — проверьте, "
            f"не потеряно ли вещество в записи реакции"
        )

    return result


def _canonical(text: str) -> str:
    """Привести запись вещества к каноническому виду для сравнения."""
    try:
        body, _ = F.split_state(text)
        comp = F.parse(body)
        return comp.hill_formula + (f"^{comp.charge:+d}" if comp.charge else "")
    except Exception:
        return str(text).strip()


def _verify(species: list[_Species], coeffs: list[int],
            elements: list[str]) -> dict[str, dict[str, float]]:
    """Проверить, что баланс по каждому элементу и по заряду выполняется."""
    check: dict[str, dict[str, float]] = {}

    for el in elements:
        if el == "заряд":
            left = sum(coeffs[i] * species[i].charge
                       for i in range(len(species)) if species[i].side == "left")
            right = sum(coeffs[i] * species[i].charge
                        for i in range(len(species)) if species[i].side == "right")
        else:
            left = sum(coeffs[i] * species[i].counts.get(el, 0.0)
                       for i in range(len(species)) if species[i].side == "left")
            right = sum(coeffs[i] * species[i].counts.get(el, 0.0)
                        for i in range(len(species)) if species[i].side == "right")

        if abs(left - right) > 1e-9:
            raise BalanceError(
                f"Баланс по «{el}» не сходится: слева {left:g}, справа {right:g}. "
                f"Это внутренняя ошибка метода."
            )
        check[el] = {"left": left, "right": right}

    return check


def _format_equation(species: list[_Species], coeffs: list[int], n_left: int) -> str:
    """Собрать уравнение в читаемую строку."""

    def side_text(indices: Iterable[int]) -> str:
        chunks = []
        for i in indices:
            sp = species[i]
            c = coeffs[i]
            prefix = "" if c == 1 else f"{c}"
            chunks.append(f"{prefix}{sp.text}")
        return " + ".join(chunks)

    left = side_text(range(n_left))
    right = side_text(range(n_left, len(species)))
    return f"{left} → {right}"


# --------------------------------------------------------------------------
# Дополнительные возможности
# --------------------------------------------------------------------------


def molar_ratio(equation: str, from_species: str, to_species: str) -> Result:
    """Мольное соотношение между двумя веществами уравнения.

    Нужно для стехиометрических задач: сколько моль продукта получается
    из одного моля реагента.
    """
    bal = balance(equation)
    coeffs: dict[str, int] = bal.meta["coefficients"]

    def pick(query: str) -> tuple[str, int]:
        for text, c in coeffs.items():
            if _canonical(text) == _canonical(query):
                return text, c
        raise BalanceError(f"Вещества «{query}» нет в уравнении")

    from_text, c_from = pick(from_species)
    to_text, c_to = pick(to_species)

    ratio = Fraction(c_to, c_from)

    result = Result(
        value=float(ratio),
        label=f"Мольное соотношение {to_species} : {from_species}",
        method="По коэффициентам уравненной реакции",
    )
    result.with_step(
        f"{c_from} моль {from_text} даёт {c_to} моль {to_text}"
    )
    result.with_meta("from", from_text)
    result.with_meta("to", to_text)
    result.with_meta("ratio_exact", f"{ratio.numerator}:{ratio.denominator}")
    result.with_meta("equation", bal.value)
    result.with_meta("coefficients", coeffs)
    return result


def is_balanced(equation: str) -> bool:
    """Проверить, уравнено ли уравнение (без попытки его уравнять).

    Коэффициент, записанный перед формулой, здесь учитывается: «2H2 + O2 = 2H2O»
    уравнено. Отличие от функции balance в том, что balance коэффициенты ищет,
    а is_balanced их проверяет.
    """
    try:
        left, right = parse_equation(equation)
        species = (
            [_Species(t, "left", i) for i, t in enumerate(left)]
            + [_Species(t, "right", i) for i, t in enumerate(right)]
        )
    except Exception:
        return False

    n_left = len(left)

    def coeff_of(sp: _Species) -> float:
        """Коэффициент как он записан; если не записан — единица."""
        return float(sp.comp.coefficient or 1)

    elements = sorted({el for sp in species for el in sp.counts})
    if not elements:
        return False

    def side_vector(indices) -> list[Fraction]:
        result: list[Fraction] = []
        for el in elements:
            total = Fraction(0)
            for i in indices:
                total += (_to_fraction(species[i].counts.get(el, 0.0))
                          * _to_fraction(coeff_of(species[i])))
            result.append(total)
        return result

    left_vec = side_vector(range(n_left))
    right_vec = side_vector(range(n_left, len(species)))

    # Сравниваем векторы напрямую. Раньше каждая сторона нормировалась на
    # свой первый ненулевой элемент, и «2H2 + O2 = H2O» считалось уравненным:
    # отношения совпадали, а количества — нет. Единственная допустимая
    # вольность в записи — общий множитель для всей реакции сразу.
    if all(v == 0 for v in left_vec) or all(v == 0 for v in right_vec):
        return False
    if left_vec != right_vec:
        return False

    # Отдельно проверяем заряд
    if any(species[i].charge for i in range(len(species))):
        q_left = sum(species[i].charge * coeff_of(species[i]) for i in range(n_left))
        q_right = sum(species[i].charge * coeff_of(species[i])
                      for i in range(n_left, len(species)))
        if q_left != q_right:
            return False

    return True


def balance_many(equations: Iterable[str]) -> Result:
    """Уравнять сразу несколько реакций — для массовых операций."""
    rows = []
    for eq in equations:
        try:
            bal = balance(eq)
            rows.append({
                "Исходная запись": eq,
                "Уравнение": bal.value,
                "Проверка": "сошлась",
            })
        except (BalanceError, DomainError) as exc:
            rows.append({
                "Исходная запись": eq,
                "Уравнение": "—",
                "Проверка": f"ошибка: {exc}",
            })

    result = table_result(rows, label="Уравнивание списка реакций",
                          columns=["Исходная запись", "Уравнение", "Проверка"])
    result.method = "Последованое уравнивание методом Гаусса"
    return result
