"""Справочник стандартных электродных потенциалов.

Позволяет собрать гальванический элемент из двух полуреакций, посчитать ЭДС,
энергию Гиббса и константу равновесия, а также оценить, пойдёт ли реакция.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..core.errors import DataNotFoundError
from . import loader

_FILE = "electrodes.json"


@dataclass(frozen=True)
class Electrode:
    """Полуреакция восстановления со стандартным потенциалом."""

    id: str
    half_reaction: str
    E0: float            # В относительно н.в.э.
    n: int               # число электронов
    medium: str          # acid, base, any
    kind: str            # cation, anion, nonmetal, solid, molecule, reference

    @property
    def is_oxidant_strong(self) -> bool:
        """Сильный ли окислитель окисленная форма."""
        return self.E0 > 0.8

    @property
    def is_reductant_strong(self) -> bool:
        """Сильный ли восстановитель восстановленная форма."""
        return self.E0 < -0.5

    def __str__(self) -> str:
        return f"{self.half_reaction}   E° = {self.E0:+.3f} В"


@lru_cache(maxsize=1)
def _electrodes() -> list[Electrode]:
    raw = loader.load(_FILE)["electrodes"]
    return [
        Electrode(
            id=e["id"], half_reaction=e["half_reaction"], E0=e["E0"],
            n=e["n"], medium=e.get("medium", "any"), kind=e.get("kind", "other"),
        )
        for e in raw
    ]


@lru_cache(maxsize=1)
def _index() -> dict[str, Electrode]:
    table: dict[str, Electrode] = {}
    for e in _electrodes():
        table[e.id.lower()] = e
        table[e.half_reaction.lower().replace(" ", "")] = e
    return table


def all_electrodes() -> list[Electrode]:
    """Все полуреакции, отсортированные по убыванию потенциала."""
    return sorted(_electrodes(), key=lambda e: -e.E0)


def find(query: str) -> Electrode:
    """Найти полуреакцию по идентификатору или записи."""
    key = str(query).strip().lower()
    if key in _index():
        return _index()[key]
    key_nospace = key.replace(" ", "")
    if key_nospace in _index():
        return _index()[key_nospace]

    # Поиск по вхождению — удобно для подсказок
    hits = [e for e in _electrodes()
            if key in e.id.lower() or key in e.half_reaction.lower()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        options = ", ".join(e.id for e in hits[:6])
        raise DataNotFoundError(
            f"Под «{query}» подходит несколько полуреакций: {options}. "
            f"Уточните запрос."
        )
    raise DataNotFoundError(f"Полуреакция «{query}» не найдена")


def maybe(query: str) -> Electrode | None:
    try:
        return find(query)
    except DataNotFoundError:
        return None


def by_element(symbol: str) -> list[Electrode]:
    """Полуреакции, содержащие данный элемент."""
    sym = str(symbol).strip()
    result = []
    for e in _electrodes():
        # Ищем символ как отдельный элемент в записи полуреакции
        import re
        if re.search(rf"(?<![A-Za-z]){re.escape(sym)}(?![a-z])", e.half_reaction):
            result.append(e)
    return sorted(result, key=lambda e: -e.E0)


def search(query: str, limit: int = 20) -> list[Electrode]:
    """Нечёткий поиск полуреакций."""
    q = str(query).strip().lower()
    if not q:
        return all_electrodes()[:limit]
    hits = [e for e in _electrodes()
            if q in e.id.lower() or q in e.half_reaction.lower()]
    return sorted(hits, key=lambda e: -e.E0)[:limit]


def strongest_oxidant() -> Electrode:
    """Самая сильная окислительная полуреакция в справочнике."""
    return all_electrodes()[0]


def water_electrolysis() -> dict:
    """Данные по электролизу воды."""
    return loader.load(_FILE).get("water_electrolysis", {})


def source() -> str:
    return loader.source_of(_FILE)


def count() -> int:
    return len(_electrodes())
