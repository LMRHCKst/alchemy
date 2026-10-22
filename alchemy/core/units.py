"""Единицы измерения: разбор, перевод, форматирование.

Единицы хранятся как множитель к базовой единице СИ внутри своей размерности.
Температура вынесена отдельно, потому что у неё не масштаб, а сдвиг.

Модуль намеренно не тянет внешних зависимостей: только стандартная библиотека.
"""

from __future__ import annotations

import math
import re
from typing import Dict, Tuple

# --------------------------------------------------------------------------
# Размерности и базовые единицы
# --------------------------------------------------------------------------

# Каждая размерность: {единица: множитель к базовой}
# Базовая единица указана первой в комментарии.
DIMENSIONS: Dict[str, Dict[str, float]] = {
    # масса, базовая — г (удобно для химии, не кг)
    "масса": {
        "г": 1.0, "кг": 1000.0, "мг": 1e-3, "мкг": 1e-6, "нг": 1e-9,
        "т": 1e6, "фунт": 453.59237, "унция": 28.349523125, "а.е.м.": 1.66053906660e-24,
    },
    # объём, базовая — л
    "объём": {
        "л": 1.0, "мл": 1e-3, "мкл": 1e-6, "м³": 1000.0, "см³": 1e-3,
        "дм³": 1.0, "галлон(US)": 3.785411784, "пинта(US)": 0.473176473,
    },
    # длина, базовая — м
    "длина": {
        "м": 1.0, "см": 0.01, "мм": 0.001, "мкм": 1e-6, "нм": 1e-9,
        "пм": 1e-12, "км": 1000.0, "Å": 1e-10, "дюйм": 0.0254,
        "фут": 0.3048, "миля": 1609.344,
    },
    # давление, базовая — Па
    "давление": {
        "Па": 1.0, "кПа": 1000.0, "МПа": 1e6, "ГПа": 1e9,
        "бар": 1e5, "мбар": 100.0, "атм": 101325.0, "торр": 133.32236842105263,
        "мм рт.ст.": 133.322387415, "см рт.ст.": 1333.22387415,
        "мм вод.ст.": 9.80665, "psi": 6894.757293168,
    },
    # энергия, базовая — Дж
    "энергия": {
        "Дж": 1.0, "кДж": 1000.0, "МДж": 1e6, "мДж": 1e-3,
        "кал": 4.184, "ккал": 4184.0, "эрг": 1e-7, "эВ": 1.602176634e-19,
        "Вт·ч": 3600.0, "кВт·ч": 3.6e6,
    },
    # количество вещества, базовая — моль
    "количество": {
        "моль": 1.0, "ммоль": 1e-3, "мкмоль": 1e-6, "нмоль": 1e-9,
        "кмоль": 1000.0,
    },
    # время, базовая — с
    "время": {
        "с": 1.0, "мс": 1e-3, "мкс": 1e-6, "нс": 1e-9,
        "мин": 60.0, "ч": 3600.0, "сут": 86400.0, "год": 31557600.0,
    },
    # температура — обрабатывается отдельной функцией (сдвиг, а не множитель)
    "температура": {"К": 1.0, "°C": 1.0, "°F": 1.0, "°R": 1.0},
}

# Удобные синонимы написания
ALIASES: Dict[str, str] = {
    "g": "г", "kg": "кг", "mg": "мг", "ug": "мкг", "µg": "мкг", "ng": "нг",
    "l": "л", "L": "л", "ml": "мл", "mL": "мл", "cm3": "см³", "m3": "м³",
    "m": "м", "cm": "см", "mm": "мм", "nm": "нм", "um": "мкм", "µm": "мкм",
    "pa": "Па", "kpa": "кПа", "mpa": "МПа", "bar": "бар", "mbar": "мбар",
    "atm": "атм", "torr": "торр", "mmhg": "мм рт.ст.", "psi": "psi",
    "j": "Дж", "kj": "кДж", "cal": "кал", "kcal": "ккал", "ev": "эВ",
    "mol": "моль", "mmol": "ммоль", "umol": "мкмоль", "µmol": "мкмоль",
    "s": "с", "sec": "с", "min": "мин", "h": "ч", "hr": "ч", "d": "сут",
    "k": "К", "c": "°C", "f": "°F",
    "angstrom": "Å", "A": "Å",
}

# --------------------------------------------------------------------------
# Исключения
# --------------------------------------------------------------------------


class UnitError(ValueError):
    """Ошибка работы с единицами."""


# --------------------------------------------------------------------------
# Основные операции
# --------------------------------------------------------------------------


def normalize(unit: str) -> str:
    """Привести написание единицы к каноническому виду."""
    u = unit.strip()
    if u in ALIASES:
        return ALIASES[u]
    # Регистронезависимый поиск по канону
    for dim in DIMENSIONS.values():
        for canon in dim:
            if canon.lower() == u.lower():
                return canon
    for alias, canon in ALIASES.items():
        if alias.lower() == u.lower():
            return canon
    return u


def dimension_of(unit: str) -> str | None:
    """Вернуть размерность единицы или None, если единица неизвестна."""
    u = normalize(unit)
    for dim_name, table in DIMENSIONS.items():
        if u in table:
            return dim_name
    return None


def is_known(unit: str) -> bool:
    return dimension_of(unit) is not None


def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Перевод температуры. Здесь сдвиг, поэтому отдельная функция."""
    f = normalize(from_unit)
    t = normalize(to_unit)

    # Сначала в кельвины
    if f == "К":
        k = value
    elif f == "°C":
        k = value + 273.15
    elif f == "°F":
        k = (value - 32.0) * 5.0 / 9.0 + 273.15
    elif f == "°R":
        k = value * 5.0 / 9.0
    else:
        raise UnitError(f"Неизвестная единица температуры: {from_unit}")

    # Затем из кельвинов
    if t == "К":
        return k
    if t == "°C":
        return k - 273.15
    if t == "°F":
        return (k - 273.15) * 9.0 / 5.0 + 32.0
    if t == "°R":
        return k * 9.0 / 5.0
    raise UnitError(f"Неизвестная единица температуры: {to_unit}")


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Перевести значение из одной единицы в другую.

    Единицы обязаны принадлежать одной размерности. Молчаливый пересчёт между
    размерностями запрещён: именно так появляются ошибки на порядки.
    """
    f = normalize(from_unit)
    t = normalize(to_unit)

    # Сначала проверяем, что обе единицы известны, и только потом
    # разрешаем частный случай «единица в ту же единицу». Иначе
    # convert(1, «попугай», «попугай») молча возвращал 1.0, хотя такой
    # единицы не существует.
    dim_f = dimension_of(f)
    dim_t = dimension_of(t)

    # dimension_of возвращает None для неизвестной единицы, а не бросает.
    # Без этой проверки convert(1, «попугай», «попугай») отвечал 1.0.
    if dim_f is None or dim_t is None:
        unknown = f if dim_f is None else t
        raise UnitError(f"Неизвестная единица: {unknown}")

    if f == t:
        return value

    if dim_f is None:
        raise UnitError(f"Неизвестная единица: {from_unit}")
    if dim_t is None:
        raise UnitError(f"Неизвестная единица: {to_unit}")

    if dim_f != dim_t:
        raise UnitError(
            f"Нельзя перевести {from_unit} в {to_unit}: "
            f"разные размерности ({dim_f} → {dim_t})"
        )

    if dim_f == "температура":
        return convert_temperature(value, f, t)

    table = DIMENSIONS[dim_f]
    return value * table[f] / table[t]


def to_base(value: float, unit: str) -> Tuple[float, str]:
    """Перевести в базовую единицу размерности."""
    u = normalize(unit)
    dim = dimension_of(u)
    if dim is None:
        raise UnitError(f"Неизвестная единица: {unit}")
    if dim == "температура":
        return convert_temperature(value, u, "К"), "К"
    base_unit = next(iter(DIMENSIONS[dim]))
    factor = DIMENSIONS[dim][u]
    return value * factor, base_unit


def from_base(value: float, dimension: str) -> Tuple[float, str]:
    """Перевести из базовой единицы размерности."""
    if dimension not in DIMENSIONS:
        raise UnitError(f"Неизвестная размерность: {dimension}")
    base_unit = next(iter(DIMENSIONS[dimension]))
    return value, base_unit


def compatible(a: str, b: str) -> bool:
    """Совместимы ли две единицы (одна размерность)."""
    da, db = dimension_of(a), dimension_of(b)
    return da is not None and da == db


# --------------------------------------------------------------------------
# Концентрации — отдельная логика, потому что зависит от вещества и плотности
# --------------------------------------------------------------------------

# Допустимые способы выражения концентрации
CONCENTRATION_UNITS = (
    "М",          # молярность, моль/л
    "мМ",         # миллимолярность
    "мкМ",        # микромолярность
    "нМ",         # наномолярность
    "моляльность",  # моль/кг растворителя
    "N",          # нормальность, моль-экв/л
    "%(масс.)",   # массовая доля, % масс.
    "%(об.)",     # объёмная доля, % об.
    "ppm",        # миллионная доля (массовая для растворов)
    "ppb",        # миллиардная доля
    "г/л",        # массовая концентрация
    "мг/л",       # массовая концентрация
    "моль/кг",    # моляльность, синоним
    "моль/л",     # молярность, синоним
)

# Множитель к моль/л для «прямых» единиц (без плотности и молярной массы)
_MOLARITY_FACTORS = {
    "М": 1.0,
    "моль/л": 1.0,
    "мМ": 1e-3,
    "мкМ": 1e-6,
    "нМ": 1e-9,
}


def is_concentration_unit(unit: str) -> bool:
    return unit.strip() in CONCENTRATION_UNITS


# --------------------------------------------------------------------------
# Форматирование чисел
# --------------------------------------------------------------------------


def format_value(value: float, digits: int = 4) -> str:
    """Компактное представление числа: без хвостовых нулей, с экспонентой
    для очень больших и очень малых величин.
    """
    if value is None:
        return "—"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return str(value)

    av = abs(value)
    if av == 0:
        return "0"
    if av >= 1e6 or av < 1e-4:
        s = f"{value:.{digits - 1}e}"
        mantissa, exp = s.split("e")
        mantissa = mantissa.rstrip("0").rstrip(".")
        return f"{mantissa}·10^{int(exp)}"
    s = f"{value:.{digits}g}"
    if "e" in s:
        return s
    return s


def format_with_unit(value: float, unit: str, digits: int = 4) -> str:
    """Число с единицей, с неразрывным пробелом по правилам СИ."""
    if not unit:
        return format_value(value, digits)
    return f"{format_value(value, digits)}\u00a0{unit}"


# --------------------------------------------------------------------------
# Разбор строки «число + единица»
# --------------------------------------------------------------------------

_NUMBER_UNIT_RE = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)\s*([^\d\s].*?)?\s*$"
)


def parse_quantity(text: str) -> Tuple[float, str]:
    """Разобрать строку вида «25.5 мл» в пару (значение, единица).

    Запятая как десятичный разделитель поддерживается — привычная
    отечественная запись.

    Raises:
        UnitError: если число не распознано.
    """
    if text is None:
        raise UnitError("Пустая величина")
    raw = str(text).strip()
    if not raw:
        raise UnitError("Пустая величина")

    m = _NUMBER_UNIT_RE.match(raw)
    if not m:
        raise UnitError(f"Не удалось разобрать величину: {text!r}")

    num_str, unit = m.group(1), (m.group(2) or "")
    num_str = num_str.replace(",", ".")
    try:
        value = float(num_str)
    except ValueError as exc:
        raise UnitError(f"Не удалось разобрать число: {text!r}") from exc

    return value, unit.strip()


def parse_and_convert(text: str, target_unit: str) -> float:
    """Разобрать «значение + единица» и сразу привести к целевой единице."""
    value, unit = parse_quantity(text)
    if not unit:
        # Без единицы считаем, что пользователь уже вводит целевые единицы
        return value
    return convert(value, unit, target_unit)
