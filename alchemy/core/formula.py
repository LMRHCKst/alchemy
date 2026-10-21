"""Разбор и представление химических формул.

Поддерживается:
    H2SO4, Ca3(PO4)2, [Cu(NH3)4]SO4, K4[Fe(CN)6]
    CuSO4*5H2O, CuSO4·5H2O, CuSO4.5H2O, CaSO4*2H2O   — гидраты
    Na2CO3*10H2O                                      — смешанные гидраты
    SO4^2-, SO4²⁻, Fe^3+, Cu^2+, Cl^-                 — ионы
    (NH4)2SO4, CH3COOH, C6H12O6, Ca(OH)2
    Fe2O3(s), NaCl(aq)                                — агрегатное состояние
    2H2O, 5H2O                                        — коэффициент перед формулой
    e^-                                               — электрон

Запись вида «CuSO4.5H2O» трактуется как гидрат (точка между формулами),
а не как десятичная дробь: в химической практике это общепринято.

Главный принцип: мусор на входе даёт ошибку, а не молча неверный ответ.
Раньше «CuSO4 5H2O» выдавало 833.6 г/моль вместо 249.7 — такой класс ошибок
здесь закрыт.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterator

from ..core.errors import InputError
from ..core.results import Measurement
from . import periodic


class FormulaError(InputError):
    """Ошибка разбора химической формулы."""


# --------------------------------------------------------------------------
# Подстрочные и надстрочные символы
# --------------------------------------------------------------------------

_SUBSCRIPTS = "₀₁₂₃₄₅₆₇₈₉"
_SUP_TO_DIGIT = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁻": "-", "⁺": "+",
}
_SUB_TO_DIGIT = {c: str(i) for i, c in enumerate(_SUBSCRIPTS)}
_DIGIT_TO_SUB = {str(i): c for i, c in enumerate(_SUBSCRIPTS)}


def to_subscript(number: int | float | str) -> str:
    """Записать число подстрочными цифрами."""
    text = str(number)
    return "".join(_DIGIT_TO_SUB.get(c, c) for c in text)


def to_superscript(number: int | float | str) -> str:
    """Записать число надстрочными цифрами."""
    reverse = {v.replace("+", "").replace("-", ""): k for k, v in _SUP_TO_DIGIT.items()}
    reverse["+"] = "⁺"
    reverse["-"] = "⁻"
    return "".join(reverse.get(c, c) for c in str(number))


_SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹"

# Заряд в конце записи: необязательный ^, необязательная цифра, знак
_CHARGE_SUFFIX_RE = re.compile(r"(\^?)(\d*)([+-])\s*$")

# Явная запись заряда в фигурных скобках: SO4{2-}, Fe{3+}, NH4{+}
_BRACE_CHARGE_RE = re.compile(r"\{(\d*)([+-])\}\s*$")

# Голый знак заряда в конце: цифры (могут быть индексом), затем знак
_BARE_CHARGE_RE = re.compile(r"(\d+)([+-])\s*$")

# Символ элемента: заглавная буква и, возможно, строчная
_ELEMENT_SYMBOL_RE = re.compile(r"[A-Z][a-z]?")


def _convert_brace_charge(s: str) -> str:
    """Превратить явную запись заряда в скобках в каноническую.

    «SO4{2-}» -> «SO4^2-», «Fe{3+}» -> «Fe^3+», «NH4{+}» -> «NH4^+».

    Такая запись однозначна: цифры внутри скобок всегда означают величину
    заряда, а не индекс. Это рекомендуемый способ, когда важна точность.
    """
    match = _BRACE_CHARGE_RE.search(s)
    if not match:
        return s
    magnitude, sign = match.group(1), match.group(2)
    head = s[:match.start()].rstrip()
    if not head:
        return s
    return f"{head}^{magnitude}{sign}"


#: многоатомные ионы из одного элемента. Для них цифра перед знаком —
#: индекс, а не заряд: I3- это трииодид, а не иод(III).
_HOMOATOMIC_POLYIONS = {
    "I3-": "I3^-",
    "I3+": "I3^+",
    "N3-": "N3^-",
    "O22-": "O2^2-",
    "S22-": "S2^2-",
    "C22-": "C2^2-",
    "Hg22+": "Hg2^2+",
    "P43-": "P4^3-",
}


def _resolve_bare_charge(s: str) -> str:
    """Разобрать запись «цифры + знак» на конце формулы.

    Здесь заложена настоящая неоднозначность химической записи: «Fe3+» — это
    ион железа(III) с зарядом +3, а «NO3-» — нитрат с индексом 3 и зарядом −1.
    Строки устроены одинаково, различает их только смысл.

    Правило опирается на состав формулы:

    * один элемент — цифры перед знаком это величина заряда:
      «Fe3+» -> Fe³⁺, «Ca2+» -> Ca²⁺;
    * несколько элементов и одна цифра — цифра это индекс, заряд ±1:
      «NO3-» -> NO₃⁻, «MnO4-» -> MnO₄⁻, «NH4+» -> NH₄⁺;
    * несколько элементов и две цифры и более — последняя цифра это заряд,
      остальные индекс: «SO42-» -> SO₄²⁻, «Cr2O72-» -> Cr₂O₇²⁻.

    Это покрывает всю обычную химическую запись. Там, где смысл всё-таки
    неоднозначен (например, «O2-»: то ли O²⁻, то ли надпероксид O₂⁻),
    надёжнее писать явно: «O{2-}» или «O2{-}».
    """
    match = _BARE_CHARGE_RE.search(s)
    if not match:
        return s

    digits, sign = match.group(1), match.group(2)
    head = s[:match.start()]

    # Электрон: «2e-» — это два электрона, а не заряд. Цифра здесь
    # коэффициент, поэтому трогать её нельзя.
    if head.strip() in ("", "e", "ē"):
        return s

    symbols = set(_ELEMENT_SYMBOL_RE.findall(head))

    # Заряд после закрывающей скобки — это заряд комплекса, а не индекс:
    # «[Cu(NH3)4]2+» читалось как удвоенный комплекс, и масса выходила
    # вдвое больше настоящей.
    if head.rstrip().endswith(("]", ")")):
        return f"{head}^{digits}{sign}"

    # Гомоатомные многоатомные ионы: здесь цифра всё-таки индекс, хотя
    # элемент один. Слишком редкие, чтобы угадывать правилом, поэтому
    # перечислены явно.
    polyion = _HOMOATOMIC_POLYIONS.get(s.strip().replace(" ", ""))
    if polyion is not None:
        return polyion

    if len(symbols) == 1:
        # Fe3+, Ca2+ — цифры означают заряд
        return f"{head}^{digits}{sign}"

    if len(digits) == 1:
        # NO3-, MnO4- — цифра это индекс, заряд единичный
        return f"{s[:-1]}^{sign}"

    # SO42-, Cr2O72- — последняя цифра заряд, остальные индекс
    subscript, magnitude = digits[:-1], digits[-1]
    return f"{head}{subscript}^{magnitude}{sign}"


def _replace_hydrate_dots(s: str) -> str:
    """Заменить точку между формулами на звёздочку, не тронув дроби.

    «CuSO4.5H2O» — это кристаллогидрат, а «0.5O2» — коэффициент одна вторая.
    Различить их можно по тому, что стоит перед числом с точкой: если там
    буква элемента или закрывающая скобка, значит формула уже закончилась
    и точка разделяет компоненты. Если перед числом начало строки или знак
    операции, то это десятичная дробь.
    """
    if "." not in s:
        return s

    result: list[str] = []
    i = 0
    length = len(s)

    while i < length:
        ch = s[i]
        if ch == "." and 0 < i < length - 1:
            # Пробегаем назад через цифры и пробелы, чтобы найти, что было
            # перед числом, к которому относится точка
            j = i - 1
            while j >= 0 and (s[j].isdigit() or s[j].isspace()):
                j -= 1
            before = s[j] if j >= 0 else ""
            after_is_formula = bool(
                re.match(r"[0-9]*[A-Z\[\(\{]", s[i + 1:])
            )
            digits_before = s[j + 1:i]
            is_fraction = digits_before.startswith("0")

            if (before and (before.isalpha() or before in ")]")
                    and after_is_formula and not is_fraction):
                result.append("*")
                i += 1
                continue
        result.append(ch)
        i += 1

    return "".join(result)


def _extract_superscript_charge(s: str) -> str:
    """Превратить надстрочную запись заряда в каноническую.

    Без этого «SO4²⁻» превращалось в «SO42-» и давало заряд −42: надстрочная
    двойка склеивалась с индексом четвёрки.
    """
    end = len(s)
    while end > 0 and s[end - 1] in " \t":
        end -= 1

    # Знак заряда стоит последним
    if end == 0 or s[end - 1] not in "⁻⁺":
        # Надстрочных знаков нет — остальное обработает общий конвертер
        return s

    sign = "-" if s[end - 1] == "⁻" else "+"
    i = end - 1

    # Перед знаком идут надстрочные цифры — величина заряда
    digits: list[str] = []
    while i > 0 and s[i - 1] in _SUPERSCRIPTS:
        digits.append(_SUP_TO_DIGIT[s[i - 1]])
        i -= 1

    magnitude = "".join(reversed(digits))
    head = s[:i].rstrip()
    tail = s[end:]
    return f"{head}^{magnitude}{sign}{tail}"


def _normalize_charge(s: str) -> str:
    """Привести запись заряда к единому виду «^N+» / «^N-» / «^+» / «^-»."""
    m = _CHARGE_SUFFIX_RE.search(s)
    if not m:
        return s

    magnitude, sign = m.group(2), m.group(3)
    head = s[:m.start()]

    # Знак в самом начале строки — это не заряд
    if not head:
        return s

    # Перед знаком должна стоять цифра, скобка или буква элемента
    if not (head[-1].isdigit() or head[-1] in ")]}" or head[-1].isalpha()):
        return s

    # Маркер ^ уже мог быть в голове строки: «H^» + «+» не должно дать «H^^+»
    while head.endswith("^"):
        head = head[:-1]

    canonical = f"^{magnitude}{sign}" if magnitude else f"^{sign}"
    return head + canonical


def normalize_input(text: str) -> str:
    """Привести формулу к канонической ASCII-записи."""
    if text is None:
        raise FormulaError("Формула не задана")
    s = str(text).strip()
    if not s:
        raise FormulaError("Формула не может быть пустой")

    # Надстрочный заряд разбирается первым, пока надстрочные цифры
    # не превратились в обычные
    s = _extract_superscript_charge(s)

    # Явная запись заряда: «SO4{2-}» -> «SO4^2-». Разбирается до всего
    # остального, потому что цифры внутри скобок однозначны
    s = _convert_brace_charge(s)

    # Остальные надстрочные символы -> обычные
    if any(c in _SUP_TO_DIGIT for c in s):
        s = "".join(_SUP_TO_DIGIT.get(c, c) for c in s)

    # Подстрочные цифры -> обычные
    s = "".join(_SUB_TO_DIGIT.get(c, c) for c in s)

    # Разные виды средних точек -> звёздочка (гидрат)
    for ch in ("·", "∙", "•", "⋅", "×", "⨯"):
        s = s.replace(ch, "*")

    # Типографские тире -> обычный минус
    for ch in ("–", "—", "−"):
        s = s.replace(ch, "-")

    # Точка между формулами — это гидрат, а не десятичная дробь.
    # «CuSO4.5H2O» -> «CuSO4*5H2O», но «0.5O2» остаётся дробью.
    s = _replace_hydrate_dots(s)

    # Убрать пробелы внутри формулы
    s = s.replace(" ", "")

    if not s:
        raise FormulaError(f"Формула пуста после очистки: {text!r}")

    # Висячий разделитель гидрата — почти всегда потерянная часть записи
    if s[0] == "*" or s[-1] == "*":
        raise FormulaError(
            f"Формула {text!r} начинается или заканчивается разделителем "
            f"гидрата — запись неполная"
        )

    # Голый знак заряда без «^»: «Fe3+» и «NO3-» устроены одинаково, но
    # означают разное. Решается по составу формулы.
    if "^" not in s:
        s = _resolve_bare_charge(s)

    # Заряд приводим к канонической форме
    s = _normalize_charge(s)

    return s


def _split_top_level(s: str) -> list[str]:
    """Разделить запись по звёздочке на верхнем уровне (вне скобок)."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "*" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


# --------------------------------------------------------------------------
# Состав
# --------------------------------------------------------------------------


@dataclass
class Composition:
    """Результат разбора формулы.

    Attributes:
        parts: список (формула части, коэффициент) для гидратов и аддуктов.
               Для простой формулы содержит один элемент.
        charge: суммарный заряд (в единицах элементарного заряда).
        state: агрегатное состояние (s, l, g, aq) или None.
        coefficient: коэффициент перед формулой, если был указан.
        raw: исходная строка.
        normalized: нормализованная строка, по которой шёл разбор.
    """

    counts: dict[str, float] = field(default_factory=dict)
    charge: int = 0
    state: str | None = None
    coefficient: int | float = 1
    parts: list[tuple[str, float]] = field(default_factory=list)
    raw: str = ""
    normalized: str = ""
    _molar_mass: float | None = field(default=None, repr=False)
    _mass_uncertainty: float | None = field(default=None, repr=False)

    # ---------------- состав ----------------

    @property
    def elements(self) -> list[str]:
        """Список элементов в порядке появления в формуле."""
        return [el for el in self._order if el in self.counts]

    _order: list[str] = field(default_factory=list, repr=False)

    @property
    def total_atoms(self) -> float:
        """Общее число атомов (без учёта коэффициента перед формулой)."""
        return sum(self.counts.values())

    def count(self, symbol: str) -> float:
        """Число атомов элемента."""
        return self.counts.get(symbol, 0.0)

    def __getitem__(self, symbol: str) -> float:
        return self.count(symbol)

    def __contains__(self, symbol: str) -> bool:
        return symbol in self.counts

    # ---------------- масса ----------------

    @property
    def molar_mass(self) -> float:
        """Молярная масса, г/моль."""
        if self._molar_mass is None:
            self._compute_mass()
        return self._molar_mass

    @property
    def mass_uncertainty(self) -> float:
        """Неопределённость молярной массы, г/моль."""
        if self._mass_uncertainty is None:
            self._compute_mass()
        return self._mass_uncertainty

    @property
    def molar_mass_measurement(self) -> Measurement:
        """Молярная масса как величина с погрешностью."""
        return Measurement(self.molar_mass, self.mass_uncertainty, "г/моль")

    def _compute_mass(self) -> None:
        total = 0.0
        variance = 0.0
        for symbol, n in self.counts.items():
            el = periodic.by_symbol(symbol)
            if el.mass is None:
                raise FormulaError(
                    f"Для элемента {symbol} нет атомной массы — молярную массу "
                    f"посчитать нельзя"
                )
            total += el.mass * n
            if el.mass_uncertainty:
                # Дисперсии складываются, коэффициенты входят квадратично
                variance += (n * el.mass_uncertainty) ** 2
        self._molar_mass = total
        self._mass_uncertainty = math.sqrt(variance)

    @property
    def mass_percentages(self) -> dict[str, float]:
        """Массовые доли элементов в процентах."""
        total = self.molar_mass
        if total <= 0:
            raise FormulaError("Молярная масса равна нулю, доли посчитать нельзя")
        result: dict[str, float] = {}
        for symbol in self.elements:
            el = periodic.by_symbol(symbol)
            if el.mass is None:
                continue
            result[symbol] = el.mass * self.counts[symbol] / total * 100.0
        return result

    @property
    def mass_fractions(self) -> dict[str, float]:
        """Массовые доли элементов (0..1)."""
        return {k: v / 100.0 for k, v in self.mass_percentages.items()}

    def mass_of(self, symbol: str) -> float:
        """Масса элемента в одной формульной единице, г/моль."""
        el = periodic.by_symbol(symbol)
        return el.atomic_mass * self.count(symbol)

    def element_fraction(self, symbol: str) -> float:
        """Мольная доля элемента в соединении."""
        if self.total_atoms == 0:
            return 0.0
        return self.count(symbol) / self.total_atoms

    # ---------------- запись ----------------

    @property
    def hill_formula(self) -> str:
        """Формула в нотации Хилла: C, H, затем остальные по алфавиту."""
        order: list[str] = []
        if "C" in self.counts:
            order.append("C")
            if "H" in self.counts:
                order.append("H")
            rest = sorted(el for el in self.counts if el not in ("C", "H"))
        else:
            rest = sorted(self.counts)
        order.extend(rest)
        return "".join(_format_part(el, self.counts[el]) for el in order)

    @property
    def display(self) -> str:
        """Формула с подстрочными индексами для показа."""
        if self.parts and len(self.parts) > 1:
            chunks = []
            for part, mult in self.parts:
                text = _pretty_from_counts(_parse_counts(part))
                if mult != 1:
                    chunks.append(f"{_fmt_num(mult)}{text}")
                else:
                    chunks.append(text)
            base = "·".join(chunks)
        else:
            base = _pretty_from_counts(self.counts)

        if not self.counts and self.charge == -1:
            # Электрон: без этой ветки он печатался одним знаком «−»,
            # и обратный разбор падал.
            base = "e"
            if self.coefficient != 1:
                base = f"{_fmt_num(self.coefficient)}{base}"

        if self.charge:
            sign = "+" if self.charge > 0 else "−"
            mag = abs(self.charge)
            base += (sign if mag == 1 else f"{to_superscript(mag)}{sign}")

        if self.coefficient != 1:
            base = f"{_fmt_num(self.coefficient)}{base}"

        if self.state:
            base += f"({self.state})"
        return base

    def __str__(self) -> str:
        return self.display

    def __repr__(self) -> str:
        return f"Composition({self.display!r}, M={self.molar_mass:.4f})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Composition):
            return NotImplemented
        return (self.counts == other.counts and self.charge == other.charge)

    def __hash__(self) -> int:
        return hash((tuple(sorted(self.counts.items())), self.charge))

    # ---------------- экспорт ----------------

    def as_dict(self) -> dict:
        """Словарь для интерфейса и сохранения."""
        return {
            "formula": self.display,
            "normalized": self.normalized,
            "molar_mass": round(self.molar_mass, 6),
            "mass_uncertainty": round(self.mass_uncertainty, 6),
            "charge": self.charge,
            "state": self.state,
            "coefficient": self.coefficient,
            "elements": {
                el: {
                    "count": self.counts[el],
                    "name_ru": periodic.by_symbol(el).name_ru,
                    "atomic_mass": periodic.by_symbol(el).mass,
                    "mass_percent": round(self.mass_percentages.get(el, 0.0), 4),
                    "mass_contribution": round(self.mass_of(el), 6),
                }
                for el in self.elements
            },
            "total_atoms": self.total_atoms,
            "parts": [{"formula": p, "coefficient": c} for p, c in self.parts],
        }


def _fmt_num(value: float) -> str:
    """Число без хвостового нуля."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_part(symbol: str, n: float) -> str:
    if n == 1:
        return symbol
    return f"{symbol}{_fmt_num(n)}"


def _pretty_from_counts(counts: dict[str, float]) -> str:
    return "".join(_format_part(el, counts[el]) for el in counts)


def _parse_counts(formula: str) -> dict[str, float]:
    """Разобрать простую формулу в состав (без гидратов и заряда).

    Используется для отрисовки частей гидрата.
    """
    return _Parser(formula).parse().counts


# --------------------------------------------------------------------------
# Парсер
# --------------------------------------------------------------------------

_ELEMENT_RE = re.compile(r"([A-Z][a-z]?)")
_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")
_STATE_SUFFIX_RE = re.compile(r"\(([^()]*)\)\s*$")

# Русские обозначения состояний -> латинские
STATE_ALIASES = {
    "g": "g", "г": "g", "газ": "g",
    "l": "l", "ж": "l", "жидк": "l", "жидкость": "l",
    "s": "s", "кр": "s", "тв": "s", "т": "s",
    "графит": "s", "алмаз": "s", "ромб": "s", "ромбическая": "s",
    "монокл": "s", "моноклинная": "s", "гексагональная": "s",
    "белый": "s", "красный": "s", "чёрный": "s", "аморфный": "s",
    "aq": "aq", "р-р": "aq", "р": "aq", "раствор": "aq",
}


def split_state(text: str) -> tuple[str, str | None]:
    """Отделить обозначение агрегатного состояния от формулы.

    «H2O(ж)» -> («H2O», «l»), «Fe2O3(тв)» -> («Fe2O3», «s»).
    Состояние влияет на выбор термодинамических данных, но не на состав.
    """
    s = str(text).strip()
    m = _STATE_SUFFIX_RE.search(s)
    if not m:
        return s, None
    state = STATE_ALIASES.get(m.group(1).strip().lower())
    if state is None:
        # в скобках не состояние, а часть формулы: Cu(OH)2, Al2(SO4)3
        return s, None
    return s[:m.start()].strip(), state
_LEADING_COEFF_RE = re.compile(r"^(\d+(?:\.\d+)?)(?=[A-Z\[\(])")
_CHARGE_TAIL_RE = re.compile(r"\^?(\d*)([+-])$")


# Разумный предел индекса в формуле. Реальные соединения не содержат
# сотен атомов одного элемента в одной формульной единице (полимеры
# записывают иначе), поэтому большое число — почти всегда слипшаяся запись
# вида «Na2CO310H2O» вместо «Na2CO3*10H2O».
MAX_SUBSCRIPT = 200
MAX_COEFFICIENT = 100


class _Parser:
    """Рекурсивный разбор одной формулы без гидратов и заряда."""

    def __init__(self, formula: str):
        self.s = formula
        self.pos = 0
        self.counts: dict[str, float] = {}
        self.order: list[str] = []
        self.charge = 0

    # ---------- служебное ----------

    def _peek(self) -> str:
        return self.s[self.pos] if self.pos < len(self.s) else ""

    def _advance(self, n: int = 1) -> None:
        self.pos += n

    def _read_number(self) -> float:
        """Прочитать коэффициент после группы или элемента."""
        # Дробный индекс означает нестехиометрическое соединение
        # (Fe0.95O, YBa2Cu3O7). Такие записи не считаем: раньше из них
        # молча получалось Fe:0 и O:95, а масса 1519 г/моль.
        if (self._peek() == "." and self.pos + 1 < len(self.s)
                and self.s[self.pos + 1].isdigit()):
            raise FormulaError(
                f"Дробный индекс в формуле {self.s!r}: нестехиометрические "
                f"соединения не поддерживаются. Укажите целые индексы."
            )
        if self._peek().isdigit():
            m = _NUMBER_RE.match(self.s, self.pos)
            if m:
                self._advance(len(m.group(1)))
                value = float(m.group(1))
                # Две группы цифр подряд — признак слипшейся записи
                # вида «H2O3Na», где потерян разделитель.
                if self._peek().isdigit():
                    raise FormulaError(
                        f"Две группы цифр подряд в формуле {self.s!r} — "
                        f"вероятно, пропущен разделитель или элемент"
                    )
                if not float(value).is_integer():
                    raise FormulaError(
                        f"Дробный индекс {value:g} в формуле {self.s!r}: "
                        f"нестехиометрические соединения не поддерживаются. "
                        f"Укажите целые индексы."
                    )
                if value > MAX_SUBSCRIPT:
                    raise FormulaError(
                        f"Индекс {value:g} в формуле {self.s!r} неправдоподобно "
                        f"велик (предел {MAX_SUBSCRIPT}). Возможно, потерян "
                        f"разделитель гидрата: пишите Na2CO3*10H2O, а не Na2CO310H2O"
                    )
                return value
        # Дробные коэффициенты вида «1/2» не поддерживаем намеренно
        return 1.0

    def _add(self, symbol: str, n: float) -> None:
        if symbol not in self.counts:
            self.counts[symbol] = 0.0
            self.order.append(symbol)
        self.counts[symbol] += n

    # ---------- разбор ----------

    def parse(self) -> Composition:
        if not self.s:
            raise FormulaError("Пустая формула")

        self._parse_group(top=True)

        if self.pos < len(self.s):
            leftover = self.s[self.pos:]
            raise FormulaError(
                f"Не удалось разобрать формулу: неожиданный фрагмент {leftover!r} "
                f"в {self.s!r}"
            )
        if not self.counts:
            raise FormulaError(f"В формуле {self.s!r} не найдено ни одного элемента")

        return Composition(
            counts=self.counts,
            charge=self.charge,
            normalized=self.s,
            _order=self.order,
        )

    def _parse_group(self, top: bool = False) -> None:
        """Разобрать последовательность элементов и групп."""
        while self.pos < len(self.s):
            ch = self._peek()

            if ch == "(":
                self._parse_bracket("(", ")")
            elif ch == "[":
                self._parse_bracket("[", "]")
            elif ch == "{":
                self._parse_bracket("{", "}")
            elif ch.isupper():
                self._parse_element()
            elif ch == "^":
                # Заряд разбирается отдельно, на верхнем уровне
                self._parse_charge()
                break
            elif ch in "+-":
                # «+» и «-» в конце — знак заряда; иначе ошибка
                if self._looks_like_charge():
                    self._parse_charge(without_caret=True)
                    break
                raise FormulaError(
                    f"Неожиданный символ {ch!r} в формуле {self.s!r}"
                )
            elif ch.isdigit():
                raise FormulaError(
                    f"Число не может стоять в этом месте формулы {self.s!r} "
                    f"(позиция {self.pos + 1})"
                )
            elif ch == "*":
                if top:
                    raise FormulaError(
                        f"Гидрат разбирается отдельно, звёздочка не должна "
                        f"попасть в разбор части: {self.s!r}"
                    )
                raise FormulaError(f"Неожиданная звёздочка в {self.s!r}")
            else:
                raise FormulaError(
                    f"Недопустимый символ {ch!r} в формуле {self.s!r} "
                    f"(позиция {self.pos + 1})"
                )

    def _parse_element(self) -> None:
        m = _ELEMENT_RE.match(self.s, self.pos)
        if not m:
            raise FormulaError(f"Ошибка чтения элемента в {self.s!r}")
        symbol = m.group(1)
        self._advance(len(symbol))

        if not periodic.exists(symbol):
            raise FormulaError(f"Неизвестный элемент: {symbol}")

        n = self._read_number()
        self._add(symbol, n)

    def _parse_bracket(self, open_ch: str, close_ch: str) -> None:
        start = self.pos
        depth = 0
        # Находим парную закрывающую скобку
        i = self.pos
        while i < len(self.s):
            if self.s[i] == open_ch:
                depth += 1
            elif self.s[i] == close_ch:
                depth -= 1
                if depth == 0:
                    break
            i += 1

        if depth != 0:
            raise FormulaError(
                f"Не закрыта скобка {open_ch!r} в формуле {self.s!r}"
            )

        inner = self.s[start + 1:i]
        if not inner:
            raise FormulaError(f"Пустые скобки в формуле {self.s!r}")

        self.pos = i + 1
        mult = self._read_number()

        if mult == 0:
            raise FormulaError(f"Нулевой индекс у группы ({inner}) — это бессмыслица")

        # Разбираем содержимое отдельным парсером и умножаем
        inner_comp = _Parser(inner).parse()
        for symbol, n in inner_comp.counts.items():
            self._add(symbol, n * mult)
        # Заряд внутри группы (например, в комплексном ионе)
        self.charge += int(inner_comp.charge * mult)

    def _looks_like_charge(self) -> bool:
        """Похоже ли на знак заряда, а не на дефис в названии."""
        tail = self.s[self.pos:]
        # Знак заряда — в самом конце строки, возможно с цифрой
        return bool(re.fullmatch(r"\^?\d*[+-]", tail))

    def _parse_charge(self, without_caret: bool = False) -> None:
        """Разобрать заряд в конце формулы."""
        tail = self.s[self.pos:]
        m = _CHARGE_TAIL_RE.fullmatch(tail)
        if not m:
            raise FormulaError(f"Не удалось разобрать заряд в {self.s!r}: {tail!r}")
        magnitude = int(m.group(1)) if m.group(1) else 1
        sign = 1 if m.group(2) == "+" else -1
        self.charge += sign * magnitude
        self.pos = len(self.s)


# --------------------------------------------------------------------------
# Публичный интерфейс
# --------------------------------------------------------------------------


def parse(formula: str, allow_charge: bool = True) -> Composition:
    """Разобрать химическую формулу.

    Пробел трактуется как разделитель компонентов смеси: «CuSO4 5H2O» — это
    медный купорос, а не формула с элементом из 45 атомов серы. Раньше такая
    запись молча давала 833.6 г/моль вместо 249.7.

    Args:
        formula: строка формулы.
        allow_charge: разрешать ли запись ионов.

    Returns:
        Composition с составом, зарядом и молярной массой.

    Raises:
        FormulaError: если формулу разобрать нельзя.
    """
    raw = str(formula)

    # Пробел на верхнем уровне — разделитель компонентов
    tokens = _split_top_level_words(raw)
    if len(tokens) > 1:
        return _combine_tokens(tokens, raw, allow_charge)

    return _parse_single(raw, allow_charge)


def _split_top_level_words(text: str) -> list[str]:
    """Разделить запись по пробелам вне скобок."""
    tokens: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text.strip():
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def _combine_tokens(tokens: list[str], raw: str, allow_charge: bool) -> Composition:
    """Сложить несколько компонентов записи в один состав.

    Коэффициент каждого компонента учитывается: «CuSO4 5H2O» — это
    CuSO4 + 5·H2O, а не CuSO4 + H2O.
    """
    total: dict[str, float] = {}
    order: list[str] = []
    total_charge = 0
    parts: list[tuple[str, float]] = []

    for token in tokens:
        comp = _parse_single(token, allow_charge)
        mult = comp.coefficient if comp.coefficient else 1
        for symbol, n in comp.counts.items():
            if symbol not in total:
                total[symbol] = 0.0
                order.append(symbol)
            total[symbol] += n * mult
        total_charge += comp.charge * mult
        for part, part_mult in (comp.parts or [(token, 1)]):
            parts.append((part, part_mult * mult))

    result = Composition(
        counts=total,
        charge=int(total_charge) if float(total_charge).is_integer() else total_charge,
        parts=parts,
        raw=raw,
        normalized=" ".join(tokens),
        _order=order,
    )
    return result


def _parse_single(raw: str, allow_charge: bool = True) -> Composition:
    """Разобрать один компонент записи (без пробелов верхнего уровня)."""
    # Состояние отделяется до нормализации, пока скобки ещё на месте
    body, state = split_state(raw)
    s = normalize_input(body)

    if not s:
        raise FormulaError(f"Формула пуста после очистки: {raw!r}")

    # Электрон, возможно с коэффициентом: «e-», «2e-», «5e^-».
    # Разбирается до общего коэффициента, потому что символ элемента
    # начинается с заглавной буквы, а «e» — строчная.
    m_electron = re.fullmatch(r"(\d*)(e|ē)(\^?-?)", s)
    if m_electron:
        coefficient = float(m_electron.group(1) or 1)
        return Composition(
            counts={}, charge=-1, coefficient=coefficient, raw=raw,
            normalized=s, parts=[("e", 1)],
            _molar_mass=0.000548579909065,
            _mass_uncertainty=0.0,
        )

    # Коэффициент перед формулой
    coefficient: float = 1
    m_coeff = _LEADING_COEFF_RE.match(s)
    if m_coeff:
        coefficient = float(m_coeff.group(1))
        if coefficient > MAX_COEFFICIENT:
            raise FormulaError(
                f"Коэффициент {coefficient:g} перед формулой неправдоподобно велик "
                f"(предел {MAX_COEFFICIENT})"
            )
        s = s[m_coeff.end():]

    # Электрон
    if re.fullmatch(r"e\^?-?", s) or s in ("e", "ē"):
        return Composition(
            counts={}, charge=-1, coefficient=coefficient, raw=raw,
            normalized=s, parts=[("e", 1)],
            _molar_mass=0.000548579909065,
            _mass_uncertainty=0.0,
        )

    # Гидраты и аддукты: делим по звёздочке на верхнем уровне
    if "*" in s:
        return _parse_hydrate(s, coefficient, state, raw, allow_charge)

    comp = _Parser(s).parse()
    comp.coefficient = coefficient
    comp.state = state
    comp.raw = raw
    comp.parts = [(s, 1)]

    if comp.charge and not allow_charge:
        raise FormulaError(f"Заряд не ожидается в формуле {raw!r}")

    return comp


def _parse_hydrate(s: str, coefficient: float, state: str | None,
                   raw: str, allow_charge: bool) -> Composition:
    """Разобрать запись с гидратной водой: CuSO4*5H2O."""
    chunks = [c for c in s.split("*") if c]
    if not chunks:
        raise FormulaError(f"Пустая запись гидрата: {raw!r}")

    total: dict[str, float] = {}
    order: list[str] = []
    total_charge = 0
    parts: list[tuple[str, float]] = []
    main_part: str | None = None

    for chunk in chunks:
        mult: float = 1
        m = re.match(r"^(\d+(?:\.\d+)?)(?=[A-Z\[\(\{])", chunk)
        if m:
            mult = float(m.group(1))
            chunk_body = chunk[m.end():]
        else:
            chunk_body = chunk

        if not chunk_body:
            raise FormulaError(f"Пустая часть в записи гидрата: {raw!r}")

        # Заряд может стоять в конце всей записи, а не отдельной части
        charge = 0
        m_ch = _CHARGE_TAIL_RE.search(chunk_body)
        if m_ch:
            magnitude = int(m_ch.group(1)) if m_ch.group(1) else 1
            sign = 1 if m_ch.group(2) == "+" else -1
            charge = sign * magnitude
            chunk_body = chunk_body[:m_ch.start()]
            if not chunk_body:
                raise FormulaError(f"Не найдена формула перед зарядом в {raw!r}")

        if not allow_charge and charge:
            raise FormulaError(f"Заряд не ожидается в формуле {raw!r}")

        sub = _Parser(chunk_body).parse()
        for symbol, n in sub.counts.items():
            if symbol not in total:
                total[symbol] = 0.0
                order.append(symbol)
            total[symbol] += n * mult

        total_charge += charge
        parts.append((chunk_body, mult))
        if main_part is None:
            main_part = chunk_body

    comp = Composition(
        counts=total,
        charge=total_charge,
        state=state,
        coefficient=coefficient,
        parts=parts,
        raw=raw,
        normalized=s,
        _order=order,
    )
    return comp


def molar_mass(formula: str) -> float:
    """Молярная масса по формуле, г/моль."""
    return parse(formula).molar_mass


def molar_mass_measurement(formula: str) -> Measurement:
    """Молярная масса с неопределённостью."""
    return parse(formula).molar_mass_measurement


def composition(formula: str) -> dict[str, float]:
    """Состав: {элемент: число атомов}."""
    return dict(parse(formula).counts)


def mass_percentages(formula: str) -> dict[str, float]:
    """Массовые доли элементов, %."""
    return parse(formula).mass_percentages


def empirical_formula(percentages: dict[str, float] | None = None,
                      masses: dict[str, float] | None = None,
                      tolerance: float = 0.02) -> str:
    """Простейшая (эмпирическая) формула по составу.

    Принимает либо массовые проценты, либо массы элементов. Возвращает строку
    формулы. Метод: делим на атомные массы, нормируем на минимум, подбираем
    наименьшие целые множители.

    Args:
        percentages: {элемент: массовый процент}
        masses: {элемент: масса}
        tolerance: допуск отклонения от целого при подборе множителя

    Raises:
        FormulaError: если данные некорректны или формула не подбирается.
    """
    if percentages is not None:
        data = {k: float(v) for k, v in percentages.items() if v}
    elif masses is not None:
        data = {k: float(v) for k, v in masses.items() if v}
    else:
        raise FormulaError("Нужно передать массовые проценты или массы элементов")

    if not data:
        raise FormulaError("Нет данных для расчёта формулы")
    if any(v < 0 for v in data.values()):
        raise FormulaError("Массы и проценты не могут быть отрицательными")

    # Моли
    moles: dict[str, float] = {}
    for symbol, value in data.items():
        el = periodic.by_symbol(symbol)
        if el.mass is None:
            raise FormulaError(f"Нет атомной массы для {symbol}")
        moles[symbol] = value / el.mass

    min_moles = min(moles.values())
    if min_moles <= 0:
        raise FormulaError("Минимальное количество вещества равно нулю")

    ratios = {k: v / min_moles for k, v in moles.items()}

    # Подбор множителя, при котором все отношения близки к целым
    best = None
    for mult in range(1, 101):
        rounded = {k: round(r * mult) for k, r in ratios.items()}
        if any(v <= 0 for v in rounded.values()):
            continue
        # Приведём к взаимно простым
        divisor = _gcd_list(list(rounded.values()))
        reduced = {k: v // divisor for k, v in rounded.items()}
        error = max(abs(r * mult / divisor - reduced[k]) for k, r in ratios.items())
        if error <= tolerance:
            if best is None or max(reduced.values()) < max(best.values()):
                best = reduced
            break

    if best is None:
        # Не удалось подобрать целые — сообщаем честно
        text = ", ".join(f"{k}: {v:.3f}" for k, v in ratios.items())
        raise FormulaError(
            f"Не удалось подобрать целочисленную формулу. "
            f"Мольные отношения: {text}"
        )

    # Порядок по Хиллу для органики, иначе по исходному порядку
    symbols = list(best.keys())
    if "C" in best and "H" in best:
        symbols = ["C", "H"] + sorted(s for s in best if s not in ("C", "H"))
    else:
        symbols = sorted(symbols)

    return "".join(_format_part(s, best[s]) for s in symbols)


def _gcd_list(values: list[int]) -> int:
    g = 0
    for v in values:
        g = math.gcd(g, abs(int(v)))
    return max(1, g)


def molecular_formula_from_empirical(empirical: str, molar_mass: float) -> str:
    """Молекулярная формула по простейшей и известной молярной массе."""
    comp = parse(empirical)
    emp_mass = comp.molar_mass
    if emp_mass <= 0:
        raise FormulaError("Молярная масса простейшей формулы равна нулю")
    n = molar_mass / emp_mass
    rounded = round(n)
    if rounded < 1:
        raise FormulaError(
            f"Молярная масса {molar_mass:g} меньше массы простейшей формулы "
            f"{emp_mass:g} — данные противоречивы"
        )
    if abs(n - rounded) > 0.05:
        raise FormulaError(
            f"Отношение масс {n:.3f} не является целым числом. "
            f"Проверьте молярную массу или состав."
        )
    return "".join(_format_part(el, comp.counts[el] * rounded) for el in comp.elements)


def degrees_of_unsaturation(formula: str) -> int | None:
    """Число ненасыщенности (индекс дефицита водорода) для органики.

    Формула: Ω = (2·C + 2 + N − H − X) / 2, где X — галогены.

    Понятие применимо только к соединениям углерода: для воды или серной
    кислоты результат не имеет смысла, поэтому возвращается None.
    """
    comp = parse(formula)
    if comp.count("C") == 0:
        return None
    allowed = {"C", "H", "N", "O", "S", "P"}
    halogens = {"F", "Cl", "Br", "I"}
    if not set(comp.counts) <= (allowed | halogens):
        return None
    c = comp.count("C")
    h = comp.count("H")
    n = comp.count("N")
    x = sum(comp.count(hal) for hal in halogens)
    value = (2 * c + 2 + n - h - x) / 2
    if abs(value - round(value)) > 1e-9:
        return None
    return int(round(value))


def molar_volume_of_gas(n_moles: float, temperature_k: float = 273.15,
                        pressure_pa: float = 101325.0) -> float:
    """Объём газа по уравнению состояния идеального газа, л."""
    from ..core.constants import R
    return n_moles * R.value * temperature_k / pressure_pa * 1000.0


def equivalent_mass(formula: str, n_equivalents: float) -> float:
    """Молярная масса эквивалента, г/моль-экв."""
    if n_equivalents <= 0:
        raise FormulaError("Число эквивалентов должно быть больше нуля")
    return parse(formula).molar_mass / n_equivalents


def compare_formulas(a: str, b: str) -> bool:
    """Одинаков ли состав двух записей (независимо от порядка элементов)."""
    ca, cb = parse(a), parse(b)
    return ca.counts == cb.counts and ca.charge == cb.charge


def iter_elements(formula: str) -> Iterator[tuple[str, float]]:
    """Пройти по элементам формулы."""
    comp = parse(formula)
    for el in comp.elements:
        yield el, comp.counts[el]
