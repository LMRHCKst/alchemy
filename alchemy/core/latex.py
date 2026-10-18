r"""Запись химических формул и уравнений в LaTeX.

Программа принимает обычную запись (CuSO4*5H2O, MnO4-, 2H2O). Для отчёта
и статьи то же нужно в LaTeX: индексы, заряды, стрелки.

Два вида вывода:

    обычный   \mathrm{CuSO_{4}} \cdot 5\mathrm{H_{2}O}
    mhchem    \ce{2H2 + O2 -> 2H2O}          (нужен пакет mhchem)

Формулы разбираются тем же парсером, что и в расчётах, поэтому LaTeX
и число всегда относятся к одному и тому же веществу.
"""

from __future__ import annotations

import re

from . import formula as F
from .errors import AlchemyError

#: чем в тексте записывают стрелку
ARROWS = ("=>", "->", "→", "⟶", "=")

#: состояние в скобках → подпись в LaTeX
STATE_LABELS = {
    "s": r"\text{тв}",
    "l": r"\text{ж}",
    "g": r"\text{г}",
    "aq": r"\text{р-р}",
    "cr": r"\text{кр}",
}

_CHARGE_AT_END = re.compile(r"\^(\d*)([+-])$")


def charge_of(normalized: str) -> tuple[str, int]:
    """Отделить заряд от тела формулы.

    Возвращает тело без заряда и сам заряд (0, если заряда нет).
    """
    match = _CHARGE_AT_END.search(normalized)
    if not match:
        return normalized, 0

    magnitude = int(match.group(1) or 1)
    charge = magnitude if match.group(2) == "+" else -magnitude
    return normalized[:match.start()], charge


def _charge_latex(charge: int) -> str:
    """Заряд: −1 → ^{-}, +2 → ^{2+}."""
    if charge == 0:
        return ""
    magnitude = abs(charge)
    sign = "+" if charge > 0 else "-"
    return f"^{sign}" if magnitude == 1 else f"^{{{magnitude}{sign}}}"


def _structure(body: str) -> str:
    """Структура без коэффициента: CuSO4 → CuSO_{4}."""
    out: list[str] = []
    index = 0
    length = len(body)

    while index < length:
        char = body[index]

        if char.isdigit() or char == ".":
            start = index
            while index < length and (body[index].isdigit() or body[index] == "."):
                index += 1
            out.append("_{" + body[start:index] + "}")
            continue

        if char.isalpha():
            start = index
            while index < length and (body[index].isalpha()):
                index += 1
            out.append(body[start:index])
            continue

        if char in "([":
            out.append(char)
        elif char in ")]":
            out.append(char)
        elif char in "*·.":
            out.append(r" \cdot ")
        elif char == " ":
            out.append(r"\, ")
        else:
            out.append(char)
        index += 1

    return "".join(out)


def _split_coefficient(part: str) -> tuple[str, str]:
    """Отделить числовой коэффициент в начале: '5H2O' → ('5', 'H2O')."""
    match = re.match(r"^(\d+(?:\.\d+)?)([A-Za-z(\[].*)$", part)
    if match:
        return match.group(1), match.group(2)
    return "", part


def formula_to_latex(text: str, mhchem: bool = False) -> str:
    """Формула в LaTeX.

    Args:
        text: формула в обычной записи, «CuSO4*5H2O» или «MnO4-».
        mhchem: обернуть в \\ce{...} вместо ручной разметки.
    """
    raw = str(text or "").strip()
    if not raw:
        raise AlchemyError("Пустая формула")

    normalized = F.normalize_input(raw)

    if mhchem:
        # mhchem понимает индексы и заряды сам, ему нужна компактная запись
        body = normalized.replace("^", "").replace("*", ".")
        return r"\ce{" + body + "}"

    body, state = F.split_state(normalized)
    body, charge = charge_of(body)

    parts: list[str] = []
    for chunk in body.split("*"):
        chunk = chunk.strip()
        if not chunk:
            continue
        coefficient, structure = _split_coefficient(chunk)
        rendered = r"\mathrm{" + _structure(structure) + "}"
        parts.append((coefficient + r"\, " if coefficient else "") + rendered)

    result = r" \cdot ".join(parts)
    result += _charge_latex(charge)

    if state:
        label = STATE_LABELS.get(state, r"\text{" + state + "}")
        result += f"\\,({label})"

    return result


def split_equation(equation: str) -> tuple[str, str, str]:
    """Разделить уравнение на левую часть, стрелку и правую."""
    text = str(equation or "").strip()
    if not text:
        raise AlchemyError("Пустое уравнение")

    for arrow in ARROWS:
        if arrow in text:
            left, _, right = text.partition(arrow)
            if left.strip() and right.strip():
                return left.strip(), arrow, right.strip()

    raise AlchemyError(
        "В уравнении нет стрелки. Пишите «реагенты = продукты» "
        "или «реагенты -> продукты»")


def split_terms(side: str) -> list[str]:
    """Разбить сторону уравнения на вещества.

    Плюс разделяет вещества, если перед ним пробел или начало строки.
    Иначе это заряд иона: Fe2+.
    """
    terms: list[str] = []
    current = ""

    for char in side:
        if char == "+" and current and current[-1].isspace():
            terms.append(current.strip())
            current = ""
            continue
        current += char

    if current.strip():
        terms.append(current.strip())
    return [term for term in terms if term]


def term_to_latex(term: str, mhchem: bool = False) -> str:
    """Одно вещество с коэффициентом."""
    text = term.strip()

    coefficient = ""
    match = re.match(r"^(\d+(?:\.\d+)?)\s+?(.*)$", text)
    if match and match.group(2):
        coefficient = match.group(1)
        text = match.group(2).strip()

    body = formula_to_latex(text, mhchem=mhchem)
    if not coefficient:
        return body
    return (f"{coefficient} {body}" if mhchem
            else coefficient + r"\, " + body)


def reaction_to_latex(equation: str, mhchem: bool = False) -> str:
    """Уравнение реакции в LaTeX.

    Args:
        equation: уравнение в обычной записи, «2H2 + O2 = 2H2O».
        mhchem: использовать \\ce{...} (нужен пакет mhchem).
    """
    left, arrow, right = split_equation(equation)
    left_terms = split_terms(left)
    right_terms = split_terms(right)

    if not left_terms or not right_terms:
        raise AlchemyError("Не удалось разобрать уравнение на вещества")

    if mhchem:
        def bare(term: str) -> str:
            text = term.strip()
            match = re.match(r"^(\d+(?:\.\d+)?)\s+?(.*)$", text)
            coefficient, rest = ("", text) if not match else (
                match.group(1), match.group(2).strip())
            body = F.normalize_input(rest).replace("^", "").replace("*", ".")
            return (f"{coefficient} {body}" if coefficient else body)

        left_text = " + ".join(bare(term) for term in left_terms)
        right_text = " + ".join(bare(term) for term in right_terms)
        return r"\ce{" + f"{left_text} -> {right_text}" + "}"

    arrow_latex = (r"\longrightarrow" if arrow in ("->", "→", "⟶")
                   else r"\rightarrow")
    left_latex = " + ".join(term_to_latex(term) for term in left_terms)
    right_latex = " + ".join(term_to_latex(term) for term in right_terms)
    return f"{left_latex} {arrow_latex} {right_latex}"


def looks_like_equation(text: str) -> bool:
    """Похоже ли значение на уравнение реакции."""
    try:
        split_equation(text)
    except AlchemyError:
        return False
    return True


def to_latex(value, mhchem: bool = False) -> str:
    """Универсальный вход: уравнение, формула или произвольный текст."""
    text = str(value or "").strip()
    if not text:
        return ""

    if looks_like_equation(text):
        try:
            return reaction_to_latex(text, mhchem=mhchem)
        except AlchemyError:
            pass

    if re.search(r"[A-Z][a-z]?\d|\^|[-+)]$", text):
        try:
            return formula_to_latex(text, mhchem=mhchem)
        except AlchemyError:
            pass

    return r"\text{" + text + "}"


def document_snippet(equations, mhchem: bool = False) -> str:
    """Кусок документа с уравнениями — для вставки в отчёт."""
    lines = [r"\begin{align*}"]
    for equation in equations:
        body = to_latex(equation, mhchem=mhchem)
        lines.append(f"  {body} \\\\")
    lines.append(r"\end{align*}")
    if mhchem:
        lines.insert(0, r"% Нужен пакет mhchem: \usepackage{mhchem}")
    return "\n".join(lines)
