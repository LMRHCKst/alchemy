"""Справочник кислот, оснований и индикаторов.

Ключевая возможность, которой не было раньше: pKa зависит от температуры.
При 100 °C нейтральным является pH 6.14, а не 7, и программа теперь это знает.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from ..core.errors import DataNotFoundError
from . import loader

_FILE = "acids.json"
T0 = 298.15


@dataclass(frozen=True)
class Acid:
    """Кислота со ступенчатой диссоциацией."""

    formula: str
    name: str
    pKa: float
    type: str            # strong / weak
    protons: int
    A: float = 0.0       # коэффициент температурной зависимости
    B: float = 0.0

    @property
    def Ka(self) -> float:
        return 10.0 ** (-self.pKa)

    @property
    def is_strong(self) -> bool:
        return self.type == "strong"

    @property
    def has_temperature_data(self) -> bool:
        return self.A != 0.0 or self.B != 0.0

    def pKa_at(self, temperature_k: float) -> float:
        """pKa при заданной температуре.

        Используется приближение pKa(T) = pKa(298) + A·(T−298) + B·(T−298)².
        Если коэффициентов нет, возвращается табличное значение: движок
        обязан в этом случае предупредить пользователя.
        """
        if not self.has_temperature_data:
            return self.pKa
        dt = temperature_k - T0
        return self.pKa + self.A * dt + self.B * dt * dt

    def Ka_at(self, temperature_k: float) -> float:
        return 10.0 ** (-self.pKa_at(temperature_k))

    def __str__(self) -> str:
        return f"{self.name} ({self.formula}), pKa = {self.pKa:g}"


@dataclass(frozen=True)
class Base:
    """Основание. pKa сопряжённой кислоты удобнее для расчёта pH."""

    formula: str
    name: str
    pKb: float
    pKa_conj: float
    type: str            # strong / weak
    OH: int              # число гидроксид-ионов в формульной единице

    @property
    def Kb(self) -> float:
        return 10.0 ** (-self.pKb)

    @property
    def is_strong(self) -> bool:
        return self.type == "strong"

    @property
    def is_hydroxide(self) -> bool:
        return self.OH > 0

    def __str__(self) -> str:
        return f"{self.name} ({self.formula}), pKb = {self.pKb:g}"


@dataclass(frozen=True)
class Indicator:
    """Кислотно-основный индикатор."""

    name: str
    formula: str
    pKa: float
    transition_low: float
    transition_high: float
    color_acid: str
    color_base: str

    @property
    def transition_range(self) -> tuple[float, float]:
        return (self.transition_low, self.transition_high)

    def color_at(self, ph: float) -> str:
        """Цвет индикатора при данном pH.

        Внутри интервала перехода цвет смешанный, поэтому возвращается
        описание переходного состояния, а не один из крайних цветов.
        """
        if ph < self.transition_low:
            return self.color_acid
        if ph > self.transition_high:
            return self.color_base
        # Середина интервала — наиболее неопределённая зона
        return f"переходный ({self.color_acid} → {self.color_base})"

    def is_transition(self, ph: float) -> bool:
        return self.transition_low <= ph <= self.transition_high

    @property
    def titration_error_hint(self) -> float:
        """Ориентировочная систематическая погрешность титрования, %.

        Возникает из-за того, что индикатор меняет окраску не строго при
        pH точки эквивалентности.
        """
        return abs(10 ** (-self.pKa)) * 100.0


# --------------------------------------------------------------------------
# Загрузка
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _acids() -> list[Acid]:
    raw = loader.load(_FILE)["acids"]
    return [
        Acid(
            formula=a["formula"], name=a["name"], pKa=a["pKa"],
            type=a.get("type", "weak"), protons=a.get("protons", 1),
            A=a.get("A", 0.0), B=a.get("B", 0.0),
        )
        for a in raw
    ]


@lru_cache(maxsize=1)
def _bases() -> list[Base]:
    raw = loader.load(_FILE)["bases"]
    return [
        Base(
            formula=b["formula"], name=b["name"], pKb=b["pKb"],
            pKa_conj=b["pKa_conj"], type=b.get("type", "weak"),
            OH=b.get("OH", 0),
        )
        for b in raw
    ]


@lru_cache(maxsize=1)
def _indicators() -> list[Indicator]:
    raw = loader.load(_FILE)["ph_indicators"]
    return [
        Indicator(
            name=i["name"], formula=i.get("formula", ""), pKa=i["pKa"],
            transition_low=i["transition_low"], transition_high=i["transition_high"],
            color_acid=i["color_acid"], color_base=i["color_base"],
        )
        for i in raw
    ]


def _key(text: str) -> str:
    return str(text).strip().replace(" ", "").lower()


@lru_cache(maxsize=1)
def _acid_index() -> dict[str, Acid]:
    table: dict[str, Acid] = {}
    for a in _acids():
        table[_key(a.formula)] = a
        table[_key(a.name)] = a
    return table


@lru_cache(maxsize=1)
def _base_index() -> dict[str, Base]:
    table: dict[str, Base] = {}
    for b in _bases():
        table[_key(b.formula)] = b
        table[_key(b.name)] = b
    return table


# --------------------------------------------------------------------------
# Публичный интерфейс
# --------------------------------------------------------------------------


def find_acid(query: str) -> Acid:
    """Найти кислоту по формуле или названию."""
    acid = _acid_index().get(_key(query))
    if acid is None:
        raise DataNotFoundError(
            f"Кислота «{query}» не найдена в справочнике "
            f"({len(_acids())} записей)"
        )
    return acid


def find_base(query: str) -> Base:
    """Найти основание по формуле или названию."""
    base = _base_index().get(_key(query))
    if base is None:
        raise DataNotFoundError(
            f"Основание «{query}» не найдено в справочнике "
            f"({len(_bases())} записей)"
        )
    return base


def maybe_acid(query: str) -> Acid | None:
    return _acid_index().get(_key(query))


def maybe_base(query: str) -> Base | None:
    return _base_index().get(_key(query))


def all_acids() -> list[Acid]:
    return list(_acids())


def all_bases() -> list[Base]:
    return list(_bases())


def all_indicators() -> list[Indicator]:
    return list(_indicators())


def find_indicator(query: str) -> Indicator:
    """Найти индикатор по названию."""
    q = _key(query)
    for i in _indicators():
        if _key(i.name) == q or (_key(i.formula) and _key(i.formula) == q):
            return i
    raise DataNotFoundError(f"Индикатор «{query}» не найден")


def indicators_for_ph(ph: float) -> list[Indicator]:
    """Индикаторы, подходящие для данного pH точки эквивалентности."""
    return [i for i in _indicators() if i.transition_low <= ph <= i.transition_high]


# --------------------------------------------------------------------------
# Ионное произведение воды и его температурная зависимость
# --------------------------------------------------------------------------


def kw_at(temperature_k: float = 298.15) -> float:
    """Ионное произведение воды при заданной температуре.

    Используется аппроксимация по справочным данным Harned & Owen:
        pKw(T) = 4470.99/T − 6.0875 + 0.01706·T
    Формула даёт pKw = 14.00 при 298.15 К, 13.26 при 323 К,
    12.26 при 348 К и 6.14 для нейтрального pH при 373 К.
    """
    if temperature_k <= 0:
        raise ValueError("Температура должна быть больше нуля")
    pkw = 4470.99 / temperature_k - 6.0875 + 0.01706 * temperature_k
    return 10.0 ** (-pkw)


def pkw_at(temperature_k: float = 298.15) -> float:
    """Показатель ионного произведения воды при заданной температуре."""
    return -math.log10(kw_at(temperature_k))


def neutral_ph(temperature_k: float = 298.15) -> float:
    """pH нейтральной среды при заданной температуре."""
    return pkw_at(temperature_k) / 2.0


def source() -> str:
    return loader.source_of(_FILE)


def count() -> int:
    return len(_acids()) + len(_bases()) + len(_indicators())
