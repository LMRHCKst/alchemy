"""Периодическая таблица и справочные данные об элементах.

Данные лежат в alchemy/data/elements.json — снимок, сгенерированный из
библиотеки mendeleev (см. tools/build_elements.py). Приложение читает снимок
и в самой библиотеке не нуждается, поэтому работает офлайн и даёт
воспроизводимые результаты независимо от того, что установлено у пользователя.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from ..core.errors import DataNotFoundError

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_ELEMENTS_FILE = os.path.join(_DATA_DIR, "elements.json")

# --------------------------------------------------------------------------
# Модель элемента
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Isotope:
    """Изотоп элемента."""

    mass_number: int
    abundance: float | None      # доля в природной смеси, 0..1
    mass: float | None           # атомная масса изотопа, а.е.м.
    half_life: float | None
    half_life_unit: str | None
    is_radioactive: bool

    @property
    def is_stable(self) -> bool:
        """Стабилен ли изотоп (по существу — есть ли период полураспада)."""
        return not self.is_radioactive

    @property
    def half_life_seconds(self) -> float | None:
        """Период полураспада в секундах, если известен."""
        if self.half_life is None:
            return None
        factors = {
            "y": 31557600.0, "year": 31557600.0, "kyear": 31557600e3,
            "Myear": 31557600e6, "Gyear": 31557600e9,
            "d": 86400.0, "day": 86400.0, "h": 3600.0, "hour": 3600.0,
            "min": 60.0, "minute": 60.0, "s": 1.0, "second": 1.0,
            "ms": 1e-3, "us": 1e-6, "ns": 1e-9,
            "ky": 31557600e3, "My": 31557600e6,
        }
        unit = (self.half_life_unit or "s").strip().lower()
        factor = factors.get(unit)
        if factor is None:
            # Неизвестная единица — не делаем вид, что знаем ответ
            return None
        return self.half_life * factor

    def pretty_half_life(self) -> str:
        """Человекочитаемый период полураспада."""
        if self.half_life is None:
            return "стабилен"
        unit_map = {
            "y": "лет", "year": "лет", "kyear": "тыс. лет", "Myear": "млн лет",
            "Gyear": "млрд лет", "d": "сут", "day": "сут", "h": "ч",
            "hour": "ч", "min": "мин", "minute": "мин", "s": "с",
            "second": "с", "ms": "мс", "us": "мкс", "ns": "нс",
        }
        unit = unit_map.get((self.half_life_unit or "").lower(),
                            self.half_life_unit or "")
        return f"{self.half_life:g} {unit}".strip()


@dataclass(frozen=True)
class Element:
    """Химический элемент со справочными свойствами."""

    z: int
    symbol: str
    name_ru: str
    name_en: str
    mass: float | None
    mass_uncertainty: float | None
    is_radioactive: bool
    category: str
    category_color: str
    group: int | None
    period: int | None
    block: str | None
    row: int
    col: int
    electron_config: str | None
    electronegativity: float | None
    density: float | None
    melting_point: float | None
    boiling_point: float | None
    fusion_heat: float | None
    evaporation_heat: float | None
    specific_heat: float | None
    molar_heat_capacity: float | None
    thermal_conductivity: float | None
    heat_of_formation: float | None
    atomic_radius: float | None
    covalent_radius: float | None
    vdw_radius: float | None
    electron_affinity: float | None
    ionization_energies: tuple[float, ...] = ()
    oxidation_states: tuple[int, ...] = ()
    isotopes: tuple[Isotope, ...] = ()

    @property
    def atomic_mass(self) -> float:
        """Атомная масса. Ошибка, если для элемента её нет.

        Для элементов без устойчивых изотопов (Tc, Pm, трансураны) в базе
        стоит масса наиболее долгоживущего изотопа — это стандартная практика,
        но пользователь должен об этом знать, поэтому вызывающий код может
        проверить поле mass_uncertainty.
        """
        if self.mass is None:
            raise DataNotFoundError(f"Нет атомной массы для элемента {self.symbol}")
        return self.mass

    @property
    def has_standard_mass(self) -> bool:
        """Есть ли у элемента стандартная атомная масса IUPAC.

        У технеция, прометия и всех элементов от полония и тяжелее стандартной
        массы нет: в таблице приведена масса наиболее долгоживущего изотопа.
        """
        return self.mass_uncertainty is not None

    @property
    def mass_note(self) -> str:
        """Пояснение к атомной массе."""
        if self.has_standard_mass:
            return ""
        return "стандартной атомной массы нет, приведена масса наиболее долгоживущего изотопа"

    @property
    def stable_isotopes(self) -> tuple[Isotope, ...]:
        return tuple(i for i in self.isotopes if i.is_stable)

    @property
    def natural_isotopes(self) -> tuple[Isotope, ...]:
        """Изотопы с ненулевым содержанием в природной смеси."""
        return tuple(i for i in self.isotopes if i.abundance)

    def isotope(self, mass_number: int) -> Isotope | None:
        for i in self.isotopes:
            if i.mass_number == mass_number:
                return i
        return None

    @property
    def valence_electrons(self) -> int | None:
        """Число валентных электронов по номеру группы (упрощённо)."""
        if self.group is None:
            return None
        if self.group <= 2:
            return self.group
        if self.group <= 12:
            return 2
        if self.group <= 18:
            return self.group - 10
        return None

    def pretty_row(self) -> dict[str, str]:
        """Основные свойства строкой — для карточки в интерфейсе."""
        from ..core.units import format_value

        def f(v, unit=""):
            if v is None:
                return "—"
            return f"{format_value(v)} {unit}".strip()

        return {
            "Порядковый номер": str(self.z),
            "Символ": self.symbol,
            "Название": self.name_ru,
            "Атомная масса": (f(self.mass, "а.е.м.") +
                              (" *" if not self.has_standard_mass else "")),
            "Категория": self.category,
            "Группа": str(self.group) if self.group else "—",
            "Период": str(self.period) if self.period else "—",
            "Электронная конфигурация": self.electron_config or "—",
            "Электроотрицательность": f(self.electronegativity),
            "Плотность": f(self.density, "г/см³"),
            "T плавления": f(self.melting_point, "K"),
            "T кипения": f(self.boiling_point, "K"),
            "Теплота плавления": f(self.fusion_heat, "кДж/моль"),
            "Теплота испарения": f(self.evaporation_heat, "кДж/моль"),
            "Удельная теплоёмкость": f(self.specific_heat, "Дж/(г·К)"),
            "Степени окисления": ", ".join(
                f"{s:+d}" for s in self.oxidation_states if s != 0) or "—",
            "Радиоактивен": "да" if self.is_radioactive else "нет",
        }


# --------------------------------------------------------------------------
# Загрузка данных
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load() -> dict:
    if not os.path.exists(_ELEMENTS_FILE):
        raise DataNotFoundError(
            f"Не найден справочник элементов: {_ELEMENTS_FILE}\n"
            f"Сгенерируйте его командой: python tools/build_elements.py"
        )
    with open(_ELEMENTS_FILE, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _elements() -> dict[int, Element]:
    raw = _load()["elements"]
    result: dict[int, Element] = {}
    for key, e in raw.items():
        result[int(key)] = Element(
            z=e["z"],
            symbol=e["symbol"],
            name_ru=e["name_ru"],
            name_en=e["name_en"],
            mass=e["mass"],
            mass_uncertainty=e["mass_uncertainty"],
            is_radioactive=e["is_radioactive"],
            category=e["category"],
            category_color=e["category_color"],
            group=e["group"],
            period=e["period"],
            block=e["block"],
            row=e["row"],
            col=e["col"],
            electron_config=e["electron_config"],
            electronegativity=e["electronegativity"],
            density=e["density"],
            melting_point=e["melting_point"],
            boiling_point=e["boiling_point"],
            fusion_heat=e["fusion_heat"],
            evaporation_heat=e["evaporation_heat"],
            specific_heat=e["specific_heat"],
            molar_heat_capacity=e["molar_heat_capacity"],
            thermal_conductivity=e["thermal_conductivity"],
            heat_of_formation=e["heat_of_formation"],
            atomic_radius=e["atomic_radius"],
            covalent_radius=e["covalent_radius"],
            vdw_radius=e["vdw_radius"],
            electron_affinity=e["electron_affinity"],
            ionization_energies=tuple(e["ionization_energies"]),
            oxidation_states=tuple(e["oxidation_states"]),
            isotopes=tuple(
                Isotope(
                    mass_number=i["mass_number"],
                    abundance=i["abundance"],
                    mass=i["mass"],
                    half_life=i["half_life"],
                    half_life_unit=i["half_life_unit"],
                    is_radioactive=i["is_radioactive"],
                )
                for i in e["isotopes"]
            ),
        )
    return result


@lru_cache(maxsize=1)
def _by_symbol() -> dict[str, Element]:
    return {el.symbol: el for el in _elements().values()}


@lru_cache(maxsize=1)
def _by_name() -> dict[str, Element]:
    table: dict[str, Element] = {}
    for el in _elements().values():
        table[el.name_ru.lower()] = el
        table[el.name_en.lower()] = el
        table[el.symbol.lower()] = el
    return table


# --------------------------------------------------------------------------
# Публичный интерфейс
# --------------------------------------------------------------------------


def all_elements() -> list[Element]:
    """Все элементы по возрастанию порядкового номера."""
    return [_elements()[z] for z in sorted(_elements())]


def by_number(z: int) -> Element:
    """Элемент по порядковому номеру."""
    try:
        return _elements()[int(z)]
    except (KeyError, ValueError) as exc:
        raise DataNotFoundError(f"Нет элемента с номером {z}") from exc


def by_symbol(symbol: str) -> Element:
    """Элемент по символу. Регистр не важен."""
    key = str(symbol).strip()
    # Приводим к каноническому виду: первая заглавная, вторая строчная
    if len(key) >= 2:
        key = key[0].upper() + key[1:].lower()
    elif key:
        key = key.upper()

    el = _by_symbol().get(key)
    if el is None:
        raise DataNotFoundError(f"Неизвестный элемент: {symbol!r}")
    return el


def by_name(name: str) -> Element:
    """Элемент по названию (русскому, английскому или символу)."""
    el = _by_name().get(str(name).strip().lower())
    if el is None:
        raise DataNotFoundError(f"Неизвестный элемент: {name!r}")
    return el


def find(query: str) -> Element | None:
    """Найти элемент, вернуть None вместо исключения."""
    try:
        return by_name(query)
    except DataNotFoundError:
        return None


def exists(symbol: str) -> bool:
    """Существует ли такой символ элемента."""
    key = str(symbol).strip()
    if len(key) >= 2:
        key = key[0].upper() + key[1:].lower()
    elif key:
        key = key.upper()
    return key in _by_symbol()


def atomic_mass(symbol: str) -> float:
    """Атомная масса элемента."""
    return by_symbol(symbol).atomic_mass


def mass_with_uncertainty(symbol: str) -> tuple[float, float]:
    """Атомная масса и её неопределённость."""
    el = by_symbol(symbol)
    return el.atomic_mass, (el.mass_uncertainty or 0.0)


def standard_mass(symbol: str) -> float | None:
    """Стандартная атомная масса IUPAC или None, если её нет."""
    el = by_symbol(symbol)
    return el.mass if el.has_standard_mass else None


def electronegativity(symbol: str) -> float | None:
    return by_symbol(symbol).electronegativity


def electronegativity_difference(a: str, b: str) -> float | None:
    """Разница электроотрицательностей по Полингу."""
    ea, eb = electronegativity(a), electronegativity(b)
    if ea is None or eb is None:
        return None
    return abs(ea - eb)


def bond_type(delta_en: float) -> tuple[str, str]:
    """Тип связи по разнице электроотрицательностей.

    Returns:
        (название типа, короткое пояснение)
    """
    if delta_en < 0.4:
        return ("ковалентная неполярная",
                "электронная плотность распределена практически симметрично")
    if delta_en < 1.7:
        return ("ковалентная полярная",
                "общая электронная пара смещена к более электроотрицательному атому")
    if delta_en < 2.0:
        return ("ионная (сильнополярная)",
                "связь близка к ионной, электронная пара почти полностью смещена")
    return ("ионная",
            "происходит практически полный переход электрона")


def formula_of_oxide(symbol: str) -> str | None:
    """Простейшая формула высшего оксида по номеру группы."""
    el = by_symbol(symbol)
    if el.group is None:
        return None
    g = el.group
    if g <= 2:
        return None
    if g <= 4:
        n = g
        return f"{el.symbol}O{n // 2}" if n % 2 == 0 else f"{el.symbol}2O{n}"
    if g <= 7:
        n = 8 - g
        return f"{el.symbol}O{n}" if n != 1 else f"{el.symbol}O"
    if g == 8:
        return None
    return None


def isotope_mass(symbol: str, mass_number: int) -> float | None:
    """Масса конкретного изотопа."""
    iso = by_symbol(symbol).isotope(mass_number)
    return iso.mass if iso else None


def average_mass_from_isotopes(symbol: str) -> float | None:
    """Средняя атомная масса, посчитанная по природным изотопам.

    Полезно как проверка: сходится ли табличная масса с расчётом по изотопам.
    """
    el = by_symbol(symbol)
    weighted = 0.0
    total_abundance = 0.0
    for iso in el.isotopes:
        if iso.abundance and iso.mass:
            weighted += iso.abundance * iso.mass
            total_abundance += iso.abundance
    if total_abundance == 0:
        return None
    return weighted / total_abundance


def categories() -> list[str]:
    """Список категорий элементов в порядке появления."""
    seen = []
    for el in all_elements():
        if el.category not in seen:
            seen.append(el.category)
    return seen


def source_info() -> str:
    """Откуда взяты данные."""
    return _load().get("source", "неизвестно")


def grid_layout(include_f_block: bool = True) -> list[list[Element | None]]:
    """Таблица для отрисовки: список строк по 18 ячеек.

    Args:
        include_f_block: включать ли строки лантаноидов и актиноидов.
    """
    max_row = 10 if include_f_block else 7
    grid: list[list[Element | None]] = [[None] * 18 for _ in range(max_row)]
    for el in all_elements():
        if not include_f_block and el.row > 7:
            continue
        if 1 <= el.row <= max_row and 1 <= el.col <= 18:
            grid[el.row - 1][el.col - 1] = el
    return grid


def count() -> int:
    """Сколько элементов в базе."""
    return len(_elements())
