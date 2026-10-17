"""Справочник малорастворимых соединений и растворителей.

Плотность растворов задана табличными точками с линейной интерполяцией —
это важно, потому что плотность серной кислоты немонотонна, и полиномиальная
подгонка дала бы ложный максимум.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..core.errors import DataNotFoundError
from . import loader

_SOL_FILE = "solubility.json"
_SOLV_FILE = "solvents.json"


# --------------------------------------------------------------------------
# Малорастворимые соединения
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Solid:
    """Малорастворимое соединение с произведением растворимости."""

    formula: str
    name: str
    cation: str
    cation_n: int
    anion: str
    anion_n: int
    Ksp: float
    M: float | None

    @property
    def ion_counts(self) -> tuple[int, int]:
        return (self.cation_n, self.anion_n)

    @property
    def total_ions(self) -> int:
        return self.cation_n + self.anion_n

    @property
    def pKsp(self) -> float:
        import math
        return -math.log10(self.Ksp)

    def solubility_pure_water(self) -> float:
        """Растворимость в чистой воде, моль/л.

        Для MxAy: Ksp = (x·S)^x · (y·S)^y  =>  S = (Ksp / (x^x · y^y))^(1/(x+y))
        """
        x, y = self.cation_n, self.anion_n
        denom = (x ** x) * (y ** y)
        return (self.Ksp / denom) ** (1.0 / (x + y))

    def solubility_g_per_l(self) -> float | None:
        """Растворимость в г/л, если известна молярная масса."""
        if self.M is None:
            return None
        return self.solubility_pure_water() * self.M

    def __str__(self) -> str:
        return f"{self.name} ({self.formula}), Ks = {self.Ksp:.2e}"


@lru_cache(maxsize=1)
def _solids() -> list[Solid]:
    raw = loader.load(_SOL_FILE)["solids"]
    return [
        Solid(
            formula=s["formula"], name=s["name"],
            cation=s["cation"], cation_n=s["cation_n"],
            anion=s["anion"], anion_n=s["anion_n"],
            Ksp=s["Ksp"], M=s.get("M"),
        )
        for s in raw
    ]


@lru_cache(maxsize=1)
def _solid_index() -> dict[str, Solid]:
    table: dict[str, Solid] = {}
    for s in _solids():
        table[s.formula.lower().replace(" ", "")] = s
        table[s.name.lower()] = s
    return table


def all_solids() -> list[Solid]:
    return list(_solids())


def find_solid(query: str) -> Solid:
    """Найти соединение по формуле или названию."""
    key = str(query).strip().lower().replace(" ", "")
    solid = _solid_index().get(key)
    if solid is None:
        solid = _solid_index().get(str(query).strip().lower())
    if solid is None:
        # Поиск по вхождению
        hits = [s for s in _solids()
                if key in s.formula.lower() or key in s.name.lower()]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            options = ", ".join(s.formula for s in hits[:8])
            raise DataNotFoundError(
                f"Под «{query}» подходит несколько соединений: {options}"
            )
        raise DataNotFoundError(
            f"Соединение «{query}» не найдено в справочнике "
            f"({len(_solids())} записей)"
        )
    return solid


def maybe_solid(query: str) -> Solid | None:
    try:
        return find_solid(query)
    except DataNotFoundError:
        return None


def solids_with_ion(ion: str) -> list[Solid]:
    """Соединения, содержащие данный ион."""
    key = str(ion).strip().lower().replace(" ", "")
    return [s for s in _solids()
            if s.cation.lower() == key or s.anion.lower() == key]


def amphoteric() -> dict:
    """Амфотерные гидроксиды с константами образования комплексов."""
    raw = loader.load(_SOL_FILE).get("hydroxide_amphoteric", {})
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def search(query: str, limit: int = 20) -> list[Solid]:
    q = str(query).strip().lower()
    if not q:
        return all_solids()[:limit]
    hits = [s for s in _solids()
            if q in s.formula.lower() or q in s.name.lower()]
    return hits[:limit]


def solubility_source() -> str:
    return loader.source_of(_SOL_FILE)


def solids_count() -> int:
    return len(_solids())


# --------------------------------------------------------------------------
# Растворители
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Solvent:
    """Растворитель с физическими свойствами."""

    name: str
    formula: str
    M: float | None
    density: float | None       # г/см³ при 20 °C
    Tb: float | None            # температура кипения, К
    Tf: float | None            # температура плавления, К
    Kb: float | None            # эбуллиоскопическая константа
    Kf: float | None            # криоскопическая константа
    dipole: float | None
    eps: float | None           # диэлектрическая проницаемость
    viscosity: float | None     # мПа·с

    @property
    def Tb_C(self) -> float | None:
        return None if self.Tb is None else self.Tb - 273.15

    @property
    def Tf_C(self) -> float | None:
        return None if self.Tf is None else self.Tf - 273.15

    @property
    def is_polar(self) -> bool:
        return self.eps is not None and self.eps > 15

    @property
    def polarity_note(self) -> str:
        if self.eps is None:
            return "диэлектрическая проницаемость неизвестна"
        if self.eps > 30:
            return "полярный, растворяет ионные соединения"
        if self.eps > 10:
            return "средней полярности"
        return "неполярный, ионные соединения не растворяет"

    def __str__(self) -> str:
        return f"{self.name} ({self.formula})"


@lru_cache(maxsize=1)
def _solvents() -> list[Solvent]:
    raw = loader.load(_SOLV_FILE)["solvents"]
    return [
        Solvent(
            name=s["name"], formula=s["formula"], M=s.get("M"),
            density=s.get("density"), Tb=s.get("Tb"), Tf=s.get("Tf"),
            Kb=s.get("Kb"), Kf=s.get("Kf"), dipole=s.get("dipole"),
            eps=s.get("eps"), viscosity=s.get("viscosity"),
        )
        for s in raw
    ]


@lru_cache(maxsize=1)
def _solvent_index() -> dict[str, Solvent]:
    table: dict[str, Solvent] = {}
    for s in _solvents():
        table[s.name.lower()] = s
        table[s.formula.lower()] = s
    return table


def all_solvents() -> list[Solvent]:
    return list(_solvents())


def find_solvent(query: str) -> Solvent:
    """Найти растворитель по названию или формуле."""
    key = str(query).strip().lower()
    solvent = _solvent_index().get(key)
    if solvent is None:
        hits = [s for s in _solvents()
                if key in s.name.lower() or key in s.formula.lower()]
        if len(hits) == 1:
            return hits[0]
        raise DataNotFoundError(
            f"Растворитель «{query}» не найден. "
            f"Доступны: {', '.join(s.name for s in _solvents())}"
        )
    return solvent


def water() -> Solvent:
    return find_solvent("Вода")


# --------------------------------------------------------------------------
# Плотность растворов
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _density_tables() -> dict[str, list[tuple[float, float]]]:
    raw = loader.load(_SOLV_FILE)["solution_density"]
    tables: dict[str, list[tuple[float, float]]] = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        points = [(float(p[0]), float(p[1])) for p in value["points"]]
        points.sort(key=lambda p: p[0])
        tables[key] = points
    return tables


def density_table_names() -> list[str]:
    """Вещества, для которых есть таблица плотности растворов."""
    return sorted(_density_tables())


def density_of_solution(solute: str, mass_fraction_percent: float,
                        temperature_c: float = 20.0) -> float | None:
    """Плотность водного раствора, г/см³.

    Между табличными точками выполняется линейная интерполяция. За пределами
    таблицы возвращается None: экстраполировать плотность нельзя, это даёт
    неверные результаты.

    Args:
        solute: формула растворённого вещества, например «H2SO4».
        mass_fraction_percent: массовая доля в процентах.
        temperature_c: температура в градусах Цельсия.
    """
    key = None
    for name in _density_tables():
        if name.lower() == str(solute).strip().lower():
            key = name
            break
    if key is None:
        return None

    w = float(mass_fraction_percent)
    if w < 0:
        return None

    points = _density_tables()[key]
    if w < points[0][0] or w > points[-1][0]:
        return None

    # Линейная интерполяция
    density = None
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= w <= x1:
            if x1 == x0:
                density = y0
            else:
                density = y0 + (y1 - y0) * (w - x0) / (x1 - x0)
            break
    if density is None:
        return None

    # Температурная поправка (приближение для 15–30 °C)
    dt = float(temperature_c) - 20.0
    return density * (1.0 - 0.00035 * dt)


def has_density_table(solute: str) -> bool:
    """Есть ли таблица плотности для этого вещества."""
    return any(name.lower() == str(solute).strip().lower()
               for name in _density_tables())


def density_range(solute: str) -> tuple[float, float] | None:
    """Диапазон массовых долей, для которого есть таблица плотности.

    Верхняя граница соответствует наибольшей концентрации, для которой
    справочник даёт данные, то есть практически предельной растворимости.
    Возвращает None, если таблицы для вещества нет.
    """
    key = None
    for name in _density_tables():
        if name.lower() == str(solute).strip().lower():
            key = name
            break
    if key is None:
        return None
    fractions = [p[0] for p in _density_tables()[key]]
    return (min(fractions), max(fractions))


def max_mass_fraction(solute: str) -> float | None:
    """Наибольшая массовая доля, для которой есть справочные данные."""
    rng = density_range(solute)
    return None if rng is None else rng[1]


def mass_fraction_from_density(solute: str, density: float,
                               temperature_c: float = 20.0,
                               tolerance: float = 1e-6) -> float | None:
    """Обратная задача: массовая доля по плотности раствора.

    Нужна, например, когда известен показатель ареометра для товарной кислоты
    и требуется узнать её концентрацию.

    Возвращает None, если соответствие неоднозначно. Так бывает у серной
    кислоты: плотность 1.80 г/мл отвечает и 85 %, и примерно 92 % — без
    дополнительной информации выбрать нельзя, и выдумывать ответ нельзя тоже.
    """
    key = None
    for name in _density_tables():
        if name.lower() == str(solute).strip().lower():
            key = name
            break
    if key is None:
        return None

    points = _density_tables()[key]

    # Температурная поправка должна быть строго обратимой:
    # при 20 °C множитель равен ровно единице.
    factor = 1.0 - 0.00035 * (float(temperature_c) - 20.0)
    if factor <= 0:
        return None
    target = density / factor

    # Совпадение с табличной точкой
    for x, y in points:
        if abs(target - y) <= tolerance:
            return x

    values = [y for _, y in points]
    lo_bound, hi_bound = min(values), max(values)
    # Сравнение с допуском: значения в таблице округлены
    if target < lo_bound * (1 - 1e-6) or target > hi_bound * (1 + 1e-6):
        return None

    # Считаем число пересечений уровня с ломаной
    crossings: list[float] = []
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if y1 == y0:
            continue
        lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
        if lo < target < hi:
            fraction = (target - y0) / (y1 - y0)
            crossings.append(x0 + (x1 - x0) * fraction)

    if len(crossings) != 1:
        return None
    return crossings[0]


def solvents_source() -> str:
    return loader.source_of(_SOLV_FILE)


def solvents_count() -> int:
    return len(_solvents())
