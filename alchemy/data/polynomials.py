"""Термохимические полиномы NASA: температурная зависимость свойств.

Данные — снимок локальной базы Burcat (см. tools/build_thermo_polynomials.py).
В отличие от основного справочника, где Cp хранится одним числом при 298 К,
здесь теплоёмкость, энтальпия и энтропия заданы как функции температуры.
Это позволяет считать тепловые эффекты при высоких температурах без грубого
допущения о постоянстве теплоёмкости.

Формат коэффициентов (NASA-7):

    Cp/R = a1 + a2·T + a3·T² + a4·T³ + a5·T⁴
    H/RT = a1 + a2·T/2 + a3·T²/3 + a4·T³/4 + a5·T⁴/5 + a6/T
    S/R  = a1·ln T + a2·T + a3·T²/2 + a4·T³/3 + a5·T⁴/4 + a7

Энтальпия включает энтальпию образования, поэтому при 298.15 К значение
H(298.15) совпадает со стандартной энтальпией образования.

Записи индексируются по составу, а не по названию: в исходной базе поле
«formula» содержит названия вида «CH4   RRHO» или «H2O(L)», по которым
искать вещество нельзя.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from ..core.errors import DataNotFoundError, OutOfRangeError
from .loader import load as _load

# Универсальная газовая постоянная, Дж/(моль·К)
R = 8.314462618

REFERENCE_TEMPERATURE = 298.15

_STATE_RU = {"g": "газ", "l": "жидкость", "s": "твёрдое"}
_STATE_ORDER = ("g", "l", "s")


@dataclass(frozen=True)
class Polynomial:
    """Полиномы свойств одного вещества в одном агрегатном состоянии."""

    name: str
    state: str
    counts: dict[str, int]
    t_min: float
    t_max: float
    molar_mass: float | None
    d_hf: float | None                 # кДж/моль при 298.15 К
    d_hf_uncertainty: float | None
    quality: str
    cas: str | None
    source: str | None
    low: tuple[float, ...]
    high: tuple[float, ...]

    # ---------------- служебное ----------------

    def _coefficients(self, temperature: float) -> tuple[float, ...]:
        """Выбрать набор коэффициентов под температуру."""
        self.check_range(temperature)
        return self.low if temperature <= 1000.0 else self.high

    def check_range(self, temperature: float) -> None:
        """Убедиться, что температура попадает в область применимости."""
        if not (self.t_min <= temperature <= self.t_max):
            raise OutOfRangeError(
                f"Для {self.display} данные применимы от {self.t_min:.0f} "
                f"до {self.t_max:.0f} К, запрошено {temperature:.1f} К")

    @property
    def display(self) -> str:
        """Название с состоянием для вывода."""
        return f"{self.name} ({_STATE_RU.get(self.state, self.state)})"

    @property
    def covers_above_298(self) -> bool:
        return self.t_max > 400.0

    # ---------------- свойства ----------------

    def cp(self, temperature: float) -> float:
        """Теплоёмкость при постоянном давлении, Дж/(моль·К)."""
        a = self._coefficients(temperature)
        t = temperature
        return (a[0] + a[1] * t + a[2] * t ** 2 + a[3] * t ** 3
                + a[4] * t ** 4) * R

    def enthalpy(self, temperature: float) -> float:
        """Энтальпия, кДж/моль. При 298.15 К равна энтальпии образования."""
        a = self._coefficients(temperature)
        t = temperature
        h_over_rt = (a[0] + a[1] * t / 2 + a[2] * t ** 2 / 3
                     + a[3] * t ** 3 / 4 + a[4] * t ** 4 / 5 + a[5] / t)
        return h_over_rt * R * t / 1000.0

    def entropy(self, temperature: float) -> float:
        """Энтропия, Дж/(моль·К)."""
        a = self._coefficients(temperature)
        t = temperature
        s_over_r = (a[0] * math.log(t) + a[1] * t + a[2] * t ** 2 / 2
                    + a[3] * t ** 3 / 3 + a[4] * t ** 4 / 4 + a[6])
        return s_over_r * R

    def gibbs(self, temperature: float) -> float:
        """Энергия Гиббса, кДж/моль."""
        return (self.enthalpy(temperature)
                - temperature * self.entropy(temperature) / 1000.0)

    def sensible_enthalpy(self, temperature: float,
                          reference: float = REFERENCE_TEMPERATURE) -> float:
        """Прирост энтальпии от опорной температуры, кДж/моль."""
        return self.enthalpy(temperature) - self.enthalpy(reference)

    def cp_at_standard(self) -> float | None:
        """Справочная теплоёмкость при 298.15 К, Дж/(моль·К)."""
        try:
            return self.cp(REFERENCE_TEMPERATURE)
        except OutOfRangeError:
            return None


# --------------------------------------------------------------------------
# Ключи по составу
# --------------------------------------------------------------------------


def composition_key(counts: dict[str, float]) -> str:
    """Ключ по составу: элементы по алфавиту, затем количество.

    Дробные количества (гидраты, нецелые коэффициенты) округляются,
    потому что база хранит только целые составы.
    """
    parts = []
    for element in sorted(counts):
        amount = counts[element]
        rounded = int(round(amount))
        if abs(amount - rounded) > 0.01:
            return ""
        if rounded <= 0:
            continue
        parts.append(f"{element}{rounded}")
    return "".join(parts)


def _counts_of(formula: str) -> dict[str, float]:
    """Разобрать формулу в состав, отбросив состояние и заряд."""
    from ..core.formula import parse, split_state

    body, _state = split_state(formula)
    try:
        composition = parse(body, allow_charge=True)
    except Exception:
        return {}
    return dict(composition.counts)


# --------------------------------------------------------------------------
# Загрузка снимка
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _database() -> dict[str, Polynomial]:
    """Прочитать снимок один раз и собрать объекты."""
    raw = _load("thermo_polynomials.json")
    result: dict[str, Polynomial] = {}
    for key, entry in raw["species"].items():
        try:
            result[key] = Polynomial(
                name=entry["name"],
                state=entry["state"],
                counts=dict(entry["counts"]),
                t_min=float(entry["Tmin"]),
                t_max=float(entry["Tmax"]),
                molar_mass=entry.get("M"),
                d_hf=entry.get("dHf"),
                d_hf_uncertainty=entry.get("dHf_unc"),
                quality=entry.get("quality") or "",
                cas=entry.get("cas"),
                source=entry.get("source"),
                low=tuple(entry["low"]),
                high=tuple(entry["high"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return result


@lru_cache(maxsize=1)
def _by_composition() -> dict[str, dict[str, Polynomial]]:
    """Индекс: состав -> состояние -> полиномы."""
    index: dict[str, dict[str, Polynomial]] = {}
    for key, poly in _database().items():
        body = key.split("|")[0]
        index.setdefault(body, {})[poly.state] = poly
    return index


def source() -> str:
    """Описание источника данных."""
    return _load("thermo_polynomials.json").get("_source", "")


def count() -> int:
    """Сколько веществ в снимке."""
    return len(_database())


def find(formula: str, state: str | None = None) -> Polynomial | None:
    """Найти полиномы вещества по формуле.

    Args:
        formula: формула, например «H2O» или «H2O(г)». Состояние можно
            указать и в самой строке.
        state: код состояния «g», «l», «s». Если не задан и состояний
            несколько, предпочитается газ, затем жидкость, затем твёрдое.
    """
    from ..core.formula import split_state

    body, embedded_state = split_state(formula)
    wanted = state or embedded_state

    counts = _counts_of(body)
    key = composition_key(counts)
    if not key:
        return None

    variants = _by_composition().get(key)
    if not variants:
        # Формула может быть записана иначе: пробуем через парсер напрямую
        return None

    if wanted is not None:
        return variants.get(wanted)
    for preferred in _STATE_ORDER:
        found = variants.get(preferred)
        if found is not None:
            return found
    return None


def require(formula: str, state: str | None = None) -> Polynomial:
    """Найти полиномы или сообщить об отсутствии данных."""
    found = find(formula, state)
    if found is None:
        hint = f" в состоянии «{state}»" if state else ""
        raise DataNotFoundError(
            f"Нет полиномов для вещества {formula}{hint}. "
            f"Всего веществ в базе: {count()}."
        )
    return found


def states_of(formula: str) -> list[str]:
    """Какие состояния есть для вещества."""
    body, _ = (formula, None)
    from ..core.formula import split_state
    body, _ = split_state(formula)
    key = composition_key(_counts_of(body))
    variants = _by_composition().get(key, {})
    return [state for state in _STATE_ORDER if state in variants]


def all_formulas() -> list[str]:
    """Все вещества в снимке, по названию."""
    return sorted({poly.name for poly in _database().values()})


def with_formation_enthalpy() -> list[Polynomial]:
    """Записи, у которых известна энтальпия образования."""
    return [p for p in _database().values() if p.d_hf is not None]


def coverage() -> dict[str, int]:
    """Сводка по базе: сколько веществ и состояний."""
    database = _database()
    by_state: dict[str, int] = {}
    for poly in database.values():
        by_state[poly.state] = by_state.get(poly.state, 0) + 1
    return {
        "всего": len(database),
        "с энтальпией образования": len(with_formation_enthalpy()),
        "газ": by_state.get("g", 0),
        "жидкость": by_state.get("l", 0),
        "твёрдое": by_state.get("s", 0),
    }
