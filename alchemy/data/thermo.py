"""Термохимический справочник: ΔH°f, ΔG°f, S°, Cp, фазовые переходы.

Данные взяты из alchemy/data/thermo.json. Каждая величина снабжена источником,
чтобы результат расчёта можно было проверить.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..core.errors import DataNotFoundError
from . import loader

_FILE = "thermo.json"


@dataclass(frozen=True)
class Substance:
    """Вещество со стандартными термодинамическими величинами при 298.15 К."""

    key: str                 # ключ в справочнике, например «H2O(ж)»
    name: str
    state: str               # g, l, s, aq
    dHf: float | None        # кДж/моль
    dGf: float | None        # кДж/моль
    S: float | None          # Дж/(моль·К)
    Cp: float | None         # Дж/(моль·К)
    M: float | None          # г/моль

    @property
    def state_ru(self) -> str:
        return {"g": "газ", "l": "жидкость", "s": "кристалл", "aq": "раствор"}.get(
            self.state, self.state)

    @property
    def formula(self) -> str:
        """Формула без указания состояния: «H2O(ж)» -> «H2O»."""
        if "(" in self.key:
            return self.key.split("(")[0]
        return self.key

    def __str__(self) -> str:
        return f"{self.name} [{self.key}]"


@dataclass(frozen=True)
class Ion:
    """Ион со стандартными величинами (шкала ΔH°f(H⁺) = 0)."""

    key: str
    name: str
    dHf: float
    dGf: float
    S: float


@dataclass(frozen=True)
class PhaseTransition:
    """Фазовый переход вещества."""

    key: str
    T_плав: float | None = None
    dH_плав: float | None = None
    T_кип: float | None = None
    dH_исп: float | None = None
    T_субл: float | None = None
    dH_субл: float | None = None


# --------------------------------------------------------------------------
# Загрузка
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _substances() -> dict[str, Substance]:
    raw = loader.load(_FILE)["substances"]
    result: dict[str, Substance] = {}
    for key, v in raw.items():
        result[key] = Substance(
            key=key,
            name=v.get("name", key),
            state=v.get("state", ""),
            dHf=v.get("dHf"),
            dGf=v.get("dGf"),
            S=v.get("S"),
            Cp=v.get("Cp"),
            M=v.get("M"),
        )
    return result


@lru_cache(maxsize=1)
def _by_formula() -> dict[str, list[Substance]]:
    """Формула без состояния -> список веществ во всех состояниях."""
    table: dict[str, list[Substance]] = {}
    for sub in _substances().values():
        table.setdefault(sub.formula, []).append(sub)
    return table


@lru_cache(maxsize=1)
def _ions() -> dict[str, Ion]:
    raw = loader.load(_FILE)["ions"]
    return {
        key: Ion(key=key, name=v.get("name", key),
                 dHf=v["dHf"], dGf=v["dGf"], S=v["S"])
        for key, v in raw.items()
    }


@lru_cache(maxsize=1)
def _transitions() -> dict[str, PhaseTransition]:
    raw = loader.load(_FILE)["phase_transitions"]
    return {
        key: PhaseTransition(
            key=key,
            T_плав=v.get("T_плав"), dH_плав=v.get("dH_плав"),
            T_кип=v.get("T_кип"), dH_исп=v.get("dH_исп"),
            T_субл=v.get("T_субл"), dH_субл=v.get("dH_субл"),
        )
        for key, v in raw.items()
    }


# --------------------------------------------------------------------------
# Поиск
# --------------------------------------------------------------------------


def _normalize_key(text: str) -> str:
    return str(text).strip().replace(" ", "")


def find(substance: str, state: str | None = None) -> Substance:
    """Найти вещество в справочнике.

    Args:
        substance: ключ («H2O(ж)»), формула («H2O») или название («Вода»).
        state: желаемое агрегатное состояние, если задана только формула.

    Raises:
        DataNotFoundError: если вещества нет в справочнике.
    """
    key = _normalize_key(substance)

    # Точное совпадение по ключу
    if key in _substances():
        return _substances()[key]

    # По формуле без состояния
    if key in _by_formula():
        variants = _by_formula()[key]
        if state:
            for v in variants:
                if v.state == state:
                    return v
        if len(variants) == 1:
            return variants[0]
        # Состояние не задано, а вариантов несколько — это неоднозначность,
        # о которой надо сказать честно
        options = ", ".join(v.key for v in variants)
        raise DataNotFoundError(
            f"Для «{substance}» есть несколько агрегатных состояний: {options}. "
            f"Укажите состояние, например {variants[0].key}"
        )

    # По названию
    lowered = str(substance).strip().lower()
    for sub in _substances().values():
        if sub.name.lower() == lowered:
            return sub

    raise DataNotFoundError(
        f"Вещества «{substance}» нет в термохимическом справочнике. "
        f"Всего в базе {len(_substances())} веществ."
    )


def maybe(substance: str, state: str | None = None) -> Substance | None:
    """Найти вещество, вернуть None вместо исключения."""
    try:
        return find(substance, state)
    except DataNotFoundError:
        return None


def find_ion(ion: str) -> Ion:
    """Найти ион в справочнике.

    Запись заряда может различаться: «Cu^2+», «Cu2+», «Cu⁺²» — всё это один
    и тот же ион. Поэтому сравнение идёт по нормализованному виду.
    """
    key = _normalize_key(ion)

    if key in _ions():
        return _ions()[key]

    target = _canonical_ion(key)
    for k, v in _ions().items():
        if _canonical_ion(k) == target:
            return v

    raise DataNotFoundError(
        f"Иона «{ion}» нет в справочнике. Всего ионов: {len(_ions())}"
    )


def _canonical_ion(text: str) -> tuple:
    """Канонический вид иона: (элементный состав, заряд).

    Позволяет сопоставить «Cu^2+», «Cu2+» и «Cu²⁺».
    """
    from ..core import formula as F
    from ..core.errors import InputError

    body = str(text).strip().replace(" ", "")
    try:
        comp = F.parse(body, allow_charge=True)
        return (tuple(sorted(comp.counts.items())), int(comp.charge))
    except (InputError, ValueError):
        # Не удалось разобрать как формулу — сравниваем как есть
        return (body.lower(), 0)


def states_of(substance: str) -> list[Substance]:
    """Все агрегатные состояния вещества, если они есть."""
    return _by_formula().get(_normalize_key(substance), [])


def has(substance: str) -> bool:
    return maybe(substance) is not None


def transition(substance: str) -> PhaseTransition | None:
    """Фазовые переходы вещества."""
    return _transitions().get(_normalize_key(substance))


def all_substances() -> list[Substance]:
    """Все вещества справочника."""
    return list(_substances().values())


def all_ions() -> list[Ion]:
    """Все ионы справочника."""
    return list(_ions().values())


def count() -> int:
    return len(_substances()) + len(_ions())


def search(query: str, limit: int = 20) -> list[Substance]:
    """Нечёткий поиск по названию и формуле — для подсказок в интерфейсе."""
    q = str(query).strip().lower()
    if not q:
        return []
    hits: list[tuple[int, Substance]] = []
    for sub in _substances().values():
        score = 0
        if sub.formula.lower() == q or sub.name.lower() == q:
            score = 100
        elif sub.formula.lower().startswith(q) or sub.name.lower().startswith(q):
            score = 60
        elif q in sub.formula.lower() or q in sub.name.lower():
            score = 30
        if score:
            hits.append((score, sub))
    hits.sort(key=lambda t: (-t[0], t[1].key))
    return [s for _, s in hits[:limit]]


def source() -> str:
    """Источник данных."""
    return loader.source_of(_FILE)


def get_meta() -> dict:
    return loader.get_meta(_FILE)
