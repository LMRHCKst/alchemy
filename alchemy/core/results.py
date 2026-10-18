"""Единый формат результата, неопределённости и значимые цифры.

Каждый расчёт в программе возвращает объект Result. Он несёт не только число,
но и единицу, неопределённость, использованную модель, её допущения,
предупреждения и ссылки на источники данных. Это делает результат проверяемым
и защищает от молчаливо неверного ответа.

Здесь же живёт Measurement — величина с погрешностью. Распространение
неопределённости выполняет библиотека uncertainties: каждое значение хранит
свою внутреннюю переменную, поэтому повторное использование одной и той же
величины учитывается как корреляция. Например, x − x даёт ровно ноль,
а не √2·σ, как было бы при независимом рассмотрении.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Iterable

from uncertainties import ufloat

# --------------------------------------------------------------------------
# Типы результата
# --------------------------------------------------------------------------

KIND_VALUE = "value"        # одно число с единицей
KIND_TABLE = "table"        # таблица строк
KIND_SERIES = "series"      # набор точек (для графиков)
KIND_TEXT = "text"          # текстовый вывод
KIND_MIXED = "mixed"        # комбинированный


@dataclass
class Result:
    """Результат расчёта с полным контекстом.

    Attributes:
        value: основное значение (число, словарь или список).
        unit: единица основного значения.
        label: человекочитаемое название величины.
        kind: тип результата из набора KIND_*.
        method: какой моделью получен результат.
        assumptions: допущения модели, о которых обязан знать пользователь.
        warnings: предупреждения о качестве и границах применимости.
        sources: источники справочных данных.
        steps: расшифровка хода расчёта для проверки руками.
        uncertainty: абсолютная неопределённость, если известна.
        meta: любые дополнительные поля конкретного расчёта.
    """

    value: Any = None
    unit: str = ""
    label: str = ""
    kind: str = KIND_VALUE
    method: str = ""
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    uncertainty: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    # ---------------- построение ----------------

    def with_step(self, text: str) -> "Result":
        """Добавить шаг расчёта (для проверки вручную)."""
        self.steps.append(text)
        return self

    def with_assumption(self, text: str) -> "Result":
        self.assumptions.append(text)
        return self

    def with_warning(self, text: str) -> "Result":
        if text not in self.warnings:
            self.warnings.append(text)
        return self

    def with_source(self, text: str) -> "Result":
        if text not in self.sources:
            self.sources.append(text)
        return self

    def with_meta(self, key: str, val: Any) -> "Result":
        self.meta[key] = val
        return self

    # ---------------- свойства ----------------

    @property
    def is_ok(self) -> bool:
        """Есть ли результат и нет ли предупреждений."""
        return self.value is not None and not self.warnings

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    def numeric(self) -> float:
        """Значение как число. Ошибка, если результат не число."""
        if isinstance(self.value, (int, float)):
            return float(self.value)
        raise TypeError(f"Результат не является числом: {type(self.value).__name__}")

    # ---------------- вывод ----------------

    def formatted(self, digits: int = 4) -> str:
        """Основное значение строкой с единицей."""
        from .units import format_value, format_with_unit

        if isinstance(self.value, (int, float)):
            if self.uncertainty is not None and self.uncertainty > 0:
                return format_measurement(float(self.value), self.uncertainty, self.unit)
            return format_with_unit(float(self.value), self.unit, digits)
        if self.kind == KIND_TABLE and isinstance(self.value, list):
            return f"таблица, строк: {len(self.value)}"
        if self.kind == KIND_SERIES and isinstance(self.value, list):
            return f"набор точек: {len(self.value)}"
        return str(self.value)

    def summary(self) -> str:
        """Многострочная сводка для панели деталей."""
        lines: list[str] = []
        if self.label:
            lines.append(self.label)

        lines.append(self.formatted())

        if self.uncertainty is not None and isinstance(self.value, (int, float)):
            lines.append(f"относительная погрешность: {self.rel_uncertainty() * 100:.2f} %"
                         if self.rel_uncertainty() is not None else "")

        if self.unit:
            lines.append(f"единица: {self.unit}")

        if self.method:
            lines.append("")
            lines.append(f"Модель: {self.method}")

        if self.assumptions:
            lines.append("")
            lines.append("Допущения:")
            lines.extend(f"  • {a}" for a in self.assumptions)

        if self.steps:
            lines.append("")
            lines.append("Ход расчёта:")
            # Пустые шаги — разделители между блоками. Номер им не нужен,
            # иначе в списке появляются строки «2.» без текста.
            number = 0
            for step in self.steps:
                if str(step).strip():
                    number += 1
                    lines.append(f"  {number}. {step}")
                else:
                    lines.append("")

        if self.warnings:
            lines.append("")
            lines.append("Предупреждения:")
            lines.extend(f"  ! {w}" for w in self.warnings)

        if self.sources:
            lines.append("")
            lines.append("Источники данных:")
            lines.extend(f"  — {s}" for s in self.sources)

        return "\n".join(line for line in lines if line is not None)

    def rel_uncertainty(self) -> float | None:
        """Относительная неопределённость, если её можно вычислить."""
        if self.uncertainty is None or not isinstance(self.value, (int, float)):
            return None
        if self.value == 0:
            return None
        return abs(self.uncertainty / self.value)


# --------------------------------------------------------------------------
# Значимые цифры
# --------------------------------------------------------------------------


def count_significant(text: str) -> int:
    """Число значащих цифр в записи числа.

    Правила:
        «0.00450» → 3 (ведущие нули не значащие, хвостовой — значащий)
        «1500»    → 2 (хвостовые нули без точки не значащие)
        «1500.»   → 4 (точка делает хвостовые нули значащими)
        «1.500e3» → 4
        «0»       → 1
    """
    s = str(text).strip().replace(",", ".").replace(" ", "")
    if not s:
        return 1

    sign_stripped = s.lstrip("+-")
    if not sign_stripped:
        return 1

    # Отделяем экспоненту
    mantissa = sign_stripped
    for marker in ("e", "E", "·10^", "x10^"):
        if marker in sign_stripped:
            mantissa = sign_stripped.split(marker)[0]
            break

    if mantissa in ("", "."):
        return 1

    has_point = "." in mantissa
    digits_only = mantissa.replace(".", "")

    if not digits_only.isdigit():
        # Нестандартная запись (например, дробь) — считаем все цифры
        return sum(c.isdigit() for c in mantissa) or 1

    if mantissa == "0" or set(digits_only) == {"0"}:
        return 1

    stripped = digits_only.lstrip("0")
    if not stripped:
        return 1

    if has_point:
        return len(stripped)

    # Без точки: хвостовые нули не значащие
    trailing_zeros = len(stripped) - len(stripped.rstrip("0"))
    if trailing_zeros and len(stripped) == trailing_zeros:
        return 1
    return len(stripped) - trailing_zeros


def round_sig(value: float, sig: int) -> float:
    """Округлить число до заданного количества значащих цифр."""
    if value == 0:
        return 0.0
    if not math.isfinite(value):
        return value
    sig = max(1, int(sig))
    exponent = math.floor(math.log10(abs(value)))
    factor = 10 ** (sig - 1 - exponent)
    return round(value * factor) / factor


def format_sig(value: float, sig: int) -> str:
    """Записать число с заданным количеством значащих цифр."""
    if value == 0:
        return "0"
    if not math.isfinite(value):
        return str(value)

    sig = max(1, int(sig))
    exponent = math.floor(math.log10(abs(value)))

    if exponent < -4 or exponent >= sig + 4:
        mantissa = value / (10 ** exponent)
        text = f"{mantissa:.{sig - 1}f}"
        return f"{text}·10^{exponent}"

    decimals = max(0, sig - 1 - exponent)
    return f"{value:.{decimals}f}"


def significant_result(values: Iterable[float], op: str) -> int:
    """Сколько значащих цифр оставить после операции.

    Для умножения и деления — по наименьшему числу значащих цифр среди
    сомножителей. Для сложения и вычитания — по наименьшему числу знаков
    после запятой. Здесь реализован упрощённый вариант для умножения
    и деления, который используется чаще всего.
    """
    counts = []
    for v in values:
        if v is None:
            continue
        counts.append(count_significant(repr(float(v))))
    if not counts:
        return 3
    if op in ("*", "/"):
        return max(1, min(counts))
    return max(1, max(counts))


# --------------------------------------------------------------------------
# Величина с неопределённостью
# --------------------------------------------------------------------------


def _make_variable(value: float, uncertainty: float):
    """Создать внутреннюю переменную с погрешностью.

    Библиотека предупреждает, что нулевая погрешность может вести себя
    неожиданно. Для нас это обычная ситуация (точная константа), поэтому
    предупреждение подавляется локально и не засоряет вывод программы.
    """
    value = float(value)
    uncertainty = float(uncertainty)
    if uncertainty == 0.0:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return ufloat(value, 0.0)
    return ufloat(value, uncertainty)


@dataclass(frozen=True)
class Measurement:
    """Величина с абсолютной неопределённостью.

    Распространение выполняет библиотека uncertainties по закону Гаусса
    в линейном приближении. В отличие от независимого расчёта каждой
    величины, здесь сохраняется корреляция: если одна и та же величина
    встречается в формуле дважды, это учитывается.

        >>> x = Measurement(2.0, 0.1)
        >>> round((x - x).uncertainty, 12)
        0.0
        >>> round((x * x).uncertainty, 6)
        0.4
        >>> round((x * x).value, 6)
        4.0
    """

    value: float
    uncertainty: float = 0.0
    unit: str = ""
    # Внутренняя переменная uncertainties хранит историю вычисления,
    # поэтому повторное использование величины даёт корреляцию.
    _var: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.uncertainty < 0:
            raise ValueError("Неопределённость не может быть отрицательной")
        if self._var is None:
            object.__setattr__(self, "_var",
                               _make_variable(self.value, self.uncertainty))

    @classmethod
    def from_variable(cls, var, unit: str = "") -> "Measurement":
        """Собрать величину вокруг готовой переменной, сохранив корреляцию."""
        obj = object.__new__(cls)
        object.__setattr__(obj, "value", var.nominal_value)
        object.__setattr__(obj, "uncertainty", var.std_dev)
        object.__setattr__(obj, "unit", unit)
        object.__setattr__(obj, "_var", var)
        return obj

    # ---------------- вспомогательное ----------------

    def _as_variable(self, other):
        """Привести второй операнд к переменной или обычному числу."""
        if isinstance(other, Measurement):
            return other._var
        return float(other)

    def _unit_of(self, other) -> str:
        if isinstance(other, Measurement):
            return self.unit or other.unit
        return self.unit

    # ---------------- арифметика ----------------

    def __add__(self, other) -> "Measurement":
        return Measurement.from_variable(
            self._var + self._as_variable(other), self._unit_of(other))

    def __radd__(self, other) -> "Measurement":
        return Measurement.from_variable(
            self._as_variable(other) + self._var, self.unit)

    def __sub__(self, other) -> "Measurement":
        return Measurement.from_variable(
            self._var - self._as_variable(other), self._unit_of(other))

    def __rsub__(self, other) -> "Measurement":
        return Measurement.from_variable(
            self._as_variable(other) - self._var, self.unit)

    def __mul__(self, other) -> "Measurement":
        return Measurement.from_variable(
            self._var * self._as_variable(other), self._unit_of(other))

    def __rmul__(self, other) -> "Measurement":
        return Measurement.from_variable(
            self._as_variable(other) * self._var, self.unit)

    def __truediv__(self, other) -> "Measurement":
        divisor = other.value if isinstance(other, Measurement) else float(other)
        if divisor == 0:
            raise ZeroDivisionError("Деление на ноль")
        return Measurement.from_variable(
            self._var / self._as_variable(other), self._unit_of(other))

    def __rtruediv__(self, other) -> "Measurement":
        if self.value == 0:
            raise ZeroDivisionError("Деление на ноль")
        return Measurement.from_variable(
            self._as_variable(other) / self._var, self.unit)

    def __pow__(self, power) -> "Measurement":
        exponent = power.value if isinstance(power, Measurement) else float(power)
        # Отрицательное основание с дробной степенью даёт комплексный
        # результат, который библиотека не поддерживает. Говорим понятно.
        if self.value < 0 and not float(exponent).is_integer():
            raise ValueError(
                "Дробная степень отрицательного числа даёт комплексный "
                "результат — в расчёте такой величины нет смысла")
        return Measurement.from_variable(
            self._var ** self._as_variable(power), self.unit)

    def __neg__(self) -> "Measurement":
        return Measurement(-self.value, self.uncertainty, self.unit)

    def __abs__(self) -> "Measurement":
        return Measurement(abs(self.value), self.uncertainty, self.unit)

    # ---------------- свойства ----------------

    @property
    def relative(self) -> float:
        """Относительная неопределённость."""
        if self.value == 0:
            return 0.0
        return abs(self.uncertainty / self.value)

    @property
    def sig_figs(self) -> int:
        """Сколько значащих цифр уместно оставить."""
        if self.uncertainty == 0:
            return 15
        return sig_figs_from_uncertainty(self.uncertainty)

    def formatted(self, sig: int | None = None) -> str:
        return format_measurement(self.value, self.uncertainty, self.unit, sig)

    def __float__(self) -> float:
        return self.value

    def __str__(self) -> str:
        return self.formatted()

    def __repr__(self) -> str:
        return f"Measurement({self.value!r}, {self.uncertainty!r}, {self.unit!r})"


# --------------------------------------------------------------------------
# Функции для Measurement
# --------------------------------------------------------------------------


def apply_function(m: Measurement, func, derivative, unit: str = "") -> Measurement:
    """Применить функцию к величине с распространением неопределённости.

    Результат линеаризуется вокруг значения: f(x) ≈ f(x₀) + f'(x₀)·(x − x₀).
    Отклонение берётся от внутренней переменной, поэтому корреляция
    с другими величинами сохраняется.

    Args:
        m: исходная величина.
        func: функция значения.
        derivative: производная функции по значению.
        unit: единица результата.
    """
    base = float(func(m.value))
    slope = float(derivative(m.value))
    linearized = base + slope * (m._var - m.value)
    return Measurement.from_variable(linearized, unit)


def m_log10(m: Measurement) -> Measurement:
    """lg с корректным распространением погрешности."""
    if m.value <= 0:
        raise ValueError("Логарифм определён только для положительных чисел")
    return Measurement(math.log10(m.value),
                       m.uncertainty / (m.value * math.ln10 if hasattr(m.value, 'ln10') else m.value * math.log(10)))


def m_ln(m: Measurement) -> Measurement:
    if m.value <= 0:
        raise ValueError("Логарифм определён только для положительных чисел")
    return Measurement(math.log(m.value), m.uncertainty / m.value)


def m_sqrt(m: Measurement) -> Measurement:
    if m.value < 0:
        raise ValueError("Корень из отрицательного числа")
    root = math.sqrt(m.value)
    if root == 0:
        return Measurement(0.0, 0.0, m.unit)
    return Measurement(root, m.uncertainty / (2 * root), m.unit)


def m_exp(m: Measurement) -> Measurement:
    val = math.exp(m.value)
    return Measurement(val, val * m.uncertainty)


# --------------------------------------------------------------------------
# Округление и запись с погрешностью
# --------------------------------------------------------------------------


def sig_figs_from_uncertainty(uncertainty: float) -> int:
    """Сколько значащих цифр оставить в значении при данной погрешности.

    Общепринятое правило: погрешность записывают одной-двумя значащими
    цифрами, значение округляют до того же разряда.
    """
    if uncertainty <= 0 or not math.isfinite(uncertainty):
        return 15
    exponent = math.floor(math.log10(abs(uncertainty)))
    # Две значащие цифры в погрешности, если старшая цифра 1 или 2
    leading = abs(uncertainty) / (10 ** exponent)
    digits_in_unc = 2 if leading < 3 else 1
    # Разряд значения, до которого округляем
    last_sig_place = exponent + digits_in_unc - 1
    return max(1, last_sig_place)


def format_measurement(value: float, uncertainty: float, unit: str = "",
                       sig: int | None = None) -> str:
    """Записать величину с погрешностью, округлив согласованно.

    Пример: 9.81 ± 0.02 м/с²
    """
    if uncertainty is None or uncertainty <= 0:
        from .units import format_value
        text = format_value(value)
        return f"{text}\u00a0{unit}".strip() if unit else text

    if not math.isfinite(value) or not math.isfinite(uncertainty):
        return f"{value} ± {uncertainty}" + (f"\u00a0{unit}" if unit else "")

    exponent = math.floor(math.log10(abs(uncertainty)))
    leading = abs(uncertainty) / (10 ** exponent)
    digits_in_unc = 2 if leading < 3 else 1

    # Разряд последней значащей цифры
    place = exponent - (digits_in_unc - 1)
    decimals = max(0, -place)

    unc_text = f"{uncertainty:.{decimals}f}"
    val_text = f"{value:.{decimals}f}"

    if place > 0:
        # Округляем до десятков, сотен и т.д.
        factor = 10 ** place
        val_text = f"{round(value / factor) * factor:.0f}"
        unc_text = f"{round(uncertainty / factor) * factor:.0f}"

    if unit:
        return f"{val_text} ± {unc_text}\u00a0{unit}"
    return f"{val_text} ± {unc_text}"


# --------------------------------------------------------------------------
# Помощники построения результатов
# --------------------------------------------------------------------------


def value_result(value: float, unit: str = "", label: str = "",
                 method: str = "") -> Result:
    """Быстрый конструктор простого числового результата."""
    return Result(value=value, unit=unit, label=label, method=method)


def text_result(text: str, label: str = "") -> Result:
    """Результат в виде текста."""
    return Result(value=text, label=label, kind=KIND_TEXT)


def table_result(rows: list[dict], label: str = "",
                 columns: list[str] | None = None) -> Result:
    """Результат в виде таблицы."""
    res = Result(value=rows, label=label, kind=KIND_TABLE)
    if columns is not None:
        res.meta["columns"] = columns
    elif rows:
        res.meta["columns"] = list(rows[0].keys())
    return res


def series_result(points: list[tuple[float, float]], x_label: str = "x",
                  y_label: str = "y", label: str = "") -> Result:
    """Результат в виде набора точек для графика."""
    return Result(
        value=points,
        label=label,
        kind=KIND_SERIES,
        meta={"x_label": x_label, "y_label": y_label},
    )


def merge_warnings(result: Result, messages: Iterable[str]) -> Result:
    """Добавить несколько предупреждений сразу."""
    for m in messages:
        result.with_warning(m)
    return result


def error_result(exc: Exception) -> Result:
    """Превратить исключение в результат с предупреждением.

    Используется в UI: вместо падения показывает понятное сообщение.
    """
    return Result(
        value=None,
        label="Ошибка расчёта",
        warnings=[str(exc)],
        meta={"error_type": type(exc).__name__},
    )
