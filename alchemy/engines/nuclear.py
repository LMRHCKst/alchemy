"""Ядерная химия: радиоактивный распад, активность, энергия ядерных реакций.

Возможности:
    * кинетика распада с расчётом остатка, времени и активности;
    * перевод единиц активности (Бк, Ки, распадов в минуту);
    * массовый дефект и энергия связи ядра;
    * энергетический выход ядерной реакции по разности масс;
    * цепочки распада и вековое равновесие;
    * дозовые величины: поглощённая и эквивалентная доза;
    * распад реальных нуклидов с ветвлениями — по базе из 1252 изотопов
      библиотеки radioactivedecay (функции decay_by_nuclides, nuclide_data,
      natural_series).

Массы нуклидов берутся из встроенной таблицы атомных масс элементов, а для
расчёта энергии реакции используется точная разность масс.

Два пути расчёта цепочек не дублируют друг друга:
    decay_chain принимает произвольные периоды полураспада и решает систему
    численно — это удобно для учебных задач с придуманной цепочкой;
    decay_by_nuclides работает с настоящими изотопами и учитывает ветвления
    и метастабильные состояния, чего в численной схеме нет.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ..core.constants import C_LIGHT, N_A
from ..core.errors import DataNotFoundError, InputError
from ..core.results import Result, series_result, table_result

# Энергетический эквивалент атомной единицы массы: 931.494 МэВ
AMU_TO_MEV = 931.49410242
AMU_TO_J = AMU_TO_MEV * 1.602176634e-13   # Дж на а.е.м.
# Масса атома водорода-1 в а.е.м. (протон + электрон)
M_H_ATOM = 1.00782503207
# Масса нейтрона в а.е.м.
M_NEUTRON = 1.00866491588
# Постоянная распада связана с периодом полураспада
LN2 = math.log(2.0)

# Единицы активности
ACTIVITY_UNITS = {
    "Бк": 1.0,              # распад в секунду
    "кБк": 1e3,
    "МБк": 1e6,
    "ГБк": 1e9,
    "Ки": 3.7e10,           # кюри
    "мКи": 3.7e7,
    "мкКи": 3.7e4,
    "расп/мин": 1.0 / 60.0,
    "расп/с": 1.0,
}

# Единицы времени, в которых можно задавать период полураспада и время
TIME_UNITS = {
    "с": 1.0, "мин": 60.0, "ч": 3600.0, "сут": 86400.0,
    "год": 31557600.0,      # юлианский год: 365.25 сут
}

# Единицы периода полураспада, которые понимает библиотека радиоактивного
# распада. Отличаются от наших: там «d» — сутки, «y» — год.
_RD_TIME_UNITS = {
    "с": "s", "мин": "min", "ч": "h", "сут": "d", "год": "y",
    "мс": "ms", "мкс": "us", "нс": "ns",
}


class NuclearError(InputError):
    """Ядерный расчёт невозможен."""


# --------------------------------------------------------------------------
# Радиоактивный распад
# --------------------------------------------------------------------------


def half_life_to_lambda(half_life: float,
                        time_unit: str = "с") -> Result:
    """Постоянная распада по периоду полураспада: λ = ln2/T½."""
    if half_life <= 0:
        raise NuclearError("Период полураспада должен быть больше нуля")

    factor = _time_factor(time_unit)
    t_seconds = half_life * factor
    lam = LN2 / t_seconds

    res = Result(
        value=lam,
        unit="1/с",
        label="Постоянная распада",
        method="λ = ln2/T½",
    )
    res.with_step(f"T½ = {half_life:g} {time_unit} = {t_seconds:.6e} с")
    res.with_step(f"λ = {LN2:.6f}/{t_seconds:.6e} = {lam:.6e} 1/с")
    res.with_step(f"Среднее время жизни τ = 1/λ = {1 / lam:.6e} с")
    res.with_meta("lambda", lam)
    res.with_meta("mean_lifetime_s", 1 / lam)
    res.with_meta("half_life_s", t_seconds)
    return res


def _time_factor(unit: str) -> float:
    """Множитель перевода единицы времени в секунды."""
    factors = {
        "с": 1.0, "сек": 1.0, "s": 1.0,
        "мин": 60.0, "min": 60.0,
        "ч": 3600.0, "час": 3600.0, "h": 3600.0,
        "сут": 86400.0, "д": 86400.0, "d": 86400.0,
        "год": 31557600.0, "лет": 31557600.0, "y": 31557600.0,
        "тыс. лет": 31557600e3, "млн лет": 31557600e6, "млрд лет": 31557600e9,
        "мс": 1e-3, "мкс": 1e-6, "нс": 1e-9,
    }
    key = str(unit).strip().lower()
    if key not in factors:
        raise NuclearError(
            f"Неизвестная единица времени «{unit}». "
            f"Допустимые: {', '.join(sorted(set(factors)))}"
        )
    return factors[key]


def decayed_amount(n0: float, half_life: float, time: float,
                   time_unit: str = "с") -> Result:
    """Сколько вещества останется через заданное время.

    N(t) = N₀·exp(−λt), где λ = ln2/T½.
    """
    if n0 <= 0:
        raise NuclearError("Начальное количество должно быть больше нуля")
    if half_life <= 0:
        raise NuclearError("Период полураспада должен быть больше нуля")
    if time < 0:
        raise NuclearError("Время не может быть отрицательным")

    factor = _time_factor(time_unit)
    lam = LN2 / half_life          # half_life и time в одних единицах
    remaining = n0 * math.exp(-lam * time)
    decayed = n0 - remaining

    res = Result(
        value=remaining,
        unit="(та же единица, что и начальное количество)",
        label="Остаток радиоактивного вещества",
        method="N(t) = N₀·exp(−λt)",
    )
    res.with_step(f"N₀ = {n0:g}, T½ = {half_life:g} {time_unit}")
    res.with_step(f"Прошло времени: {time:g} {time_unit} = {time / half_life:.4f} периодов полураспада")
    res.with_step(f"λ = {lam:.6e} 1/{time_unit}")
    res.with_step(f"N(t) = {n0:g}·e^(−{lam:.6e}·{time:g}) = {remaining:.6e}")
    res.with_step(
        f"Распалось: {decayed:.6e} ({(1 - remaining / n0) * 100:.4f} % от начального)"
    )
    res.with_meta("remaining", remaining)
    res.with_meta("decayed", decayed)
    res.with_meta("fraction_remaining", remaining / n0)
    res.with_meta("half_lives_elapsed", time / half_life)

    # Практическое правило: за 10 периодов остаётся менее 0.1 %
    if time / half_life > 10:
        res.with_step(
            f"Прошло более 10 периодов полураспада — осталось менее "
            f"{100 * 0.5 ** 10:.4f} % исходного вещества"
        )
    return res


def time_to_decay(n0: float, target: float, half_life: float,
                  time_unit: str = "с") -> Result:
    """Время, за которое количество уменьшится до заданного."""
    if n0 <= 0:
        raise NuclearError("Начальное количество должно быть больше нуля")
    if target <= 0:
        raise NuclearError("Целевое количество должно быть больше нуля")
    if target > n0:
        raise NuclearError(
            f"Целевое количество {target:g} больше начального {n0:g}: "
            f"распад не может увеличить количество вещества"
        )
    if half_life <= 0:
        raise NuclearError("Период полураспада должен быть больше нуля")

    lam = LN2 / half_life
    t = math.log(n0 / target) / lam

    res = Result(
        value=t,
        unit=time_unit,
        label="Время достижения заданного количества",
        method="t = ln(N₀/N)/λ",
    )
    res.with_step(f"N₀/N = {n0:g}/{target:g} = {n0 / target:.6g}")
    res.with_step(f"t = ln({n0 / target:.6g})/{lam:.6e} = {t:.6e} {time_unit}")
    res.with_step(f"Это {t / half_life:.4f} периодов полураспада")
    res.with_meta("half_lives", t / half_life)
    return res


def activity(n_moles: float, half_life_s: float,
             isotope: str = "") -> Result:
    """Активность образца: A = λ·N.

    Args:
        n_moles: количество вещества, моль.
        half_life_s: период полураспада в секундах.
        isotope: название нуклида для подписи.
    """
    if n_moles <= 0:
        raise NuclearError("Количество вещества должно быть больше нуля")
    if half_life_s <= 0:
        raise NuclearError("Период полураспада должен быть больше нуля")

    N = n_moles * N_A.value
    lam = LN2 / half_life_s
    A = lam * N

    res = Result(
        value=A,
        unit="Бк",
        label=f"Активность образца{' ' + isotope if isotope else ''}",
        method="A = λ·N",
    )
    res.with_step(f"Число атомов: N = {n_moles:.6g}·{N_A.value:.6e} = {N:.6e}")
    res.with_step(f"λ = ln2/{half_life_s:.6e} = {lam:.6e} 1/с")
    res.with_step(f"A = {lam:.6e}·{N:.6e} = {A:.6e} Бк")
    res.with_step(f"В кюри: {A / 3.7e10:.6e} Ки")
    res.with_step(f"В распадах в минуту: {A * 60:.6e} расп/мин")
    res.with_meta("atoms", N)
    res.with_meta("lambda", lam)
    res.with_meta("activity_bq", A)
    res.with_meta("activity_ci", A / 3.7e10)
    res.with_source(N_A.pretty())
    res.with_assumption(
        "Образец содержит только этот нуклид, дочерние продукты активность "
        "не добавляют"
    )
    return res


def mass_from_activity(activity_bq: float, half_life_s: float,
                       molar_mass_value: float) -> Result:
    """Масса нуклида, обладающего заданной активностью.

    Обратная задача к расчёту активности. Нужна, например, чтобы узнать,
    сколько миллиграммов изотопа соответствует 1 МБк.
    """
    if activity_bq <= 0:
        raise NuclearError("Активность должна быть больше нуля")
    if half_life_s <= 0:
        raise NuclearError("Период полураспада должен быть больше нуля")
    if molar_mass_value <= 0:
        raise NuclearError("Молярная масса должна быть больше нуля")

    lam = LN2 / half_life_s
    N = activity_bq / lam
    n = N / N_A.value
    mass = n * molar_mass_value

    res = Result(
        value=mass,
        unit="г",
        label="Масса нуклида с заданной активностью",
        method="N = A/λ, затем m = N·M/N_A",
    )
    res.with_step(f"λ = {lam:.6e} 1/с")
    res.with_step(f"Число атомов: N = {activity_bq:.6e}/{lam:.6e} = {N:.6e}")
    res.with_step(f"Количество вещества: {n:.6e} моль")
    res.with_step(
        f"Масса: {mass:.6e} г = {mass * 1000:.6e} мг = {mass * 1e6:.6e} мкг"
    )
    res.with_meta("atoms", N)
    res.with_meta("moles", n)
    res.with_meta("mass_mg", mass * 1000)
    return res


def convert_activity(value: float, from_unit: str, to_unit: str) -> Result:
    """Перевести активность между единицами (Бк, Ки, расп/мин)."""
    if value < 0:
        raise NuclearError("Активность не может быть отрицательной")

    if from_unit not in ACTIVITY_UNITS:
        raise NuclearError(
            f"Неизвестная единица «{from_unit}». "
            f"Допустимые: {', '.join(ACTIVITY_UNITS)}"
        )
    if to_unit not in ACTIVITY_UNITS:
        raise NuclearError(
            f"Неизвестная единица «{to_unit}». "
            f"Допустимые: {', '.join(ACTIVITY_UNITS)}"
        )

    in_bq = value * ACTIVITY_UNITS[from_unit]
    result = in_bq / ACTIVITY_UNITS[to_unit]

    res = Result(
        value=result,
        unit=to_unit,
        label="Активность после перевода единиц",
        method="Через беккерели",
    )
    res.with_step(f"{value:g} {from_unit} = {in_bq:.6e} Бк")
    res.with_step(f"{in_bq:.6e} Бк = {result:.6e} {to_unit}")
    res.with_step("Соотношение: 1 Ки = 3.7·10¹⁰ Бк")
    res.with_meta("becquerel", in_bq)
    return res


def decay_curve(n0: float, half_life: float, time_unit: str = "с",
                n_half_lives: float = 6.0, points: int = 100) -> Result:
    """Кривая распада для графика."""
    if n0 <= 0 or half_life <= 0:
        raise NuclearError("Количество и период полураспада должны быть больше нуля")
    if n_half_lives <= 0:
        raise NuclearError("Число периодов должно быть больше нуля")

    t_max = half_life * n_half_lives
    lam = LN2 / half_life

    data = []
    step = t_max / (points - 1) if points > 1 else 0
    for i in range(points):
        t = i * step
        data.append((t, n0 * math.exp(-lam * t)))

    res = series_result(
        data,
        x_label=f"Время, {time_unit}",
        y_label="Количество вещества",
        label="Кривая радиоактивного распада",
    )
    res.method = "N(t) = N₀·exp(−λt)"
    res.with_meta("half_life", half_life)
    res.with_meta("n0", n0)
    res.with_step(
        "Через каждый период полураспада количество уменьшается ровно вдвое — "
        "это свойство экспоненциального закона"
    )
    return res


# --------------------------------------------------------------------------
# Энергия ядерных реакций
# --------------------------------------------------------------------------


@dataclass
class Nuclide:
    """Нуклид с массовым числом и зарядом."""

    symbol: str           # символ элемента
    mass_number: int      # A
    charge: int           # Z

    @property
    def neutrons(self) -> int:
        return self.mass_number - self.charge

    @property
    def label(self) -> str:
        return f"{self.symbol}-{self.mass_number}"

    def __str__(self) -> str:
        return self.label


def parse_nuclide(text: str) -> Nuclide:
    """Разобрать запись нуклида: «U-235», «235U», «U235».

    Заряд берётся из периодической таблицы, массовое число — из записи.
    """
    from ..core import periodic

    raw = str(text).strip().replace(" ", "")
    if not raw:
        raise NuclearError("Не задан нуклид")

    # Вариант «U-235»
    if "-" in raw:
        parts = raw.split("-")
        if len(parts) != 2:
            raise NuclearError(f"Не удалось разобрать нуклид «{text}»")
        symbol, mass_str = parts[0], parts[1]
    # Вариант «235U»
    elif raw[0].isdigit():
        i = 0
        while i < len(raw) and raw[i].isdigit():
            i += 1
        mass_str, symbol = raw[:i], raw[i:]
    # Вариант «U235»
    else:
        i = 0
        while i < len(raw) and (raw[i].isalpha()):
            i += 1
        symbol, mass_str = raw[:i], raw[i:]

    if not symbol or not mass_str.isdigit():
        raise NuclearError(
            f"Не удалось разобрать нуклид «{text}». "
            f"Используйте запись вида U-235 или 235U"
        )

    try:
        element = periodic.by_symbol(symbol)
    except Exception as exc:
        raise NuclearError(f"Неизвестный элемент в записи «{text}»") from exc

    return Nuclide(symbol=element.symbol, mass_number=int(mass_str),
                   charge=element.z)


def nuclear_binding_energy(nuclide: str) -> Result:
    """Энергия связи ядра и удельная энергия связи.

    Дефект массы: Δm = Z·m(H) + N·m(n) − M(атом).
    Энергия связи: E = Δm·c² = Δm·931.494 МэВ/а.е.м.
    """
    from ..core import periodic

    nuc = parse_nuclide(nuclide)
    element = periodic.by_symbol(nuc.symbol)

    isotope = element.isotope(nuc.mass_number)
    if isotope is None or isotope.mass is None:
        raise NuclearError(
            f"В справочнике нет массы изотопа {nuc.label}. "
            f"Доступные массовые числа: "
            f"{', '.join(str(i.mass_number) for i in element.isotopes[:15])}"
            f"{' ...' if len(element.isotopes) > 15 else ''}"
        )

    m_atom = isotope.mass
    Z = nuc.charge
    N = nuc.neutrons

    if N < 0:
        raise NuclearError(
            f"У нуклида {nuc.label} массовое число меньше заряда ядра"
        )

    mass_defect = Z * M_H_ATOM + N * M_NEUTRON - m_atom
    if mass_defect <= 0:
        raise NuclearError(
            f"Дефект массы для {nuc.label} получился отрицательным "
            f"({mass_defect:.6f} а.е.м.) — данные о массах противоречивы"
        )

    energy_mev = mass_defect * AMU_TO_MEV
    energy_j = mass_defect * AMU_TO_J
    energy_per_nucleon = energy_mev / nuc.mass_number

    res = Result(
        value=energy_mev,
        unit="МэВ",
        label=f"Энергия связи ядра {nuc.label}",
        method="E = Δm·c², где Δm = Z·m(H) + N·m(n) − M(атом)",
    )
    res.with_step(f"Состав ядра: Z = {Z} протонов, N = {N} нейтронов, A = {nuc.mass_number}")
    res.with_step(f"Масса атома: {m_atom:.8f} а.е.м. (справочник)")
    res.with_step(
        f"Сумма масс частиц: {Z}·{M_H_ATOM:.8f} + {N}·{M_NEUTRON:.8f} "
        f"= {Z * M_H_ATOM + N * M_NEUTRON:.8f} а.е.м."
    )
    res.with_step(f"Дефект массы: Δm = {mass_defect:.8f} а.е.м.")
    res.with_step(f"Энергия связи: {energy_mev:.4f} МэВ = {energy_j:.6e} Дж")
    res.with_step(f"Удельная энергия связи: {energy_per_nucleon:.4f} МэВ/нуклон")
    res.with_meta("mass_defect_amu", mass_defect)
    res.with_meta("energy_mev", energy_mev)
    res.with_meta("energy_j", energy_j)
    res.with_meta("energy_per_nucleon_mev", energy_per_nucleon)
    res.with_meta("Z", Z)
    res.with_meta("N", N)
    res.with_source("Массы изотопов: справочник элементов (CIAAW)")

    res.with_step(
        "Удельная энергия связи максимальна у ядер железа (около 8.8 МэВ/нуклон): "
        "и лёгкие, и тяжёлые ядра могут выделять энергию при переходе к ним"
    )
    return res


def reaction_energy(reactants: list[str], products: list[str]) -> Result:
    """Энергия ядерной реакции по разности масс.

    Q = (Σm(реагенты) − Σm(продукты))·c². Положительная Q — энергия выделяется.

    Args:
        reactants: список нуклидов, например ['U-235', 'n'].
        products: список нуклидов.
    """
    from ..core import periodic

    def mass_of(text: str) -> tuple[float, str]:
        raw = str(text).strip().lower()
        if raw in ("n", "нейтрон", "neutron"):
            return M_NEUTRON, "нейтрон"
        if raw in ("p", "протон", "proton"):
            return M_H_ATOM, "протон (атом водорода)"
        if raw in ("e", "e-", "электрон", "electron"):
            return 0.00054858, "электрон"

        nuc = parse_nuclide(text)
        element = periodic.by_symbol(nuc.symbol)
        iso = element.isotope(nuc.mass_number)
        if iso is None or iso.mass is None:
            raise NuclearError(
                f"Нет массы для нуклида {nuc.label} в справочнике"
            )
        return iso.mass, nuc.label

    m_react = 0.0
    m_prod = 0.0
    react_details = []
    prod_details = []

    for item in reactants:
        m, label = mass_of(item)
        m_react += m
        react_details.append(f"{label} ({m:.6f} а.е.м.)")

    for item in products:
        m, label = mass_of(item)
        m_prod += m
        prod_details.append(f"{label} ({m:.6f} а.е.м.)")

    delta_m = m_react - m_prod
    Q_mev = delta_m * AMU_TO_MEV
    Q_j = delta_m * AMU_TO_J

    res = Result(
        value=Q_mev,
        unit="МэВ",
        label="Энергетический выход ядерной реакции",
        method="Q = (Σm(реагенты) − Σm(продукты))·c²",
    )
    res.with_step("Реагенты: " + " + ".join(react_details))
    res.with_step("Продукты: " + " + ".join(prod_details))
    res.with_step(f"Суммарная масса реагентов: {m_react:.8f} а.е.м.")
    res.with_step(f"Суммарная масса продуктов: {m_prod:.8f} а.е.м.")
    res.with_step(f"Дефект массы: Δm = {delta_m:+.8f} а.е.м.")
    res.with_step(f"Q = {delta_m:+.8f}·931.494 = {Q_mev:+.4f} МэВ")
    res.with_step(f"В джоулях: {Q_j:+.6e} Дж на одну реакцию")
    res.with_step(
        f"На один моль превращений: {Q_j * N_A.value / 1000:+.6e} кДж/моль"
    )
    res.with_meta("delta_m_amu", delta_m)
    res.with_meta("Q_mev", Q_mev)
    res.with_meta("Q_j", Q_j)
    res.with_meta("Q_kj_per_mol", Q_j * N_A.value / 1000)

    if delta_m > 0:
        res.with_step("Δm > 0: масса убыла, энергия выделяется (экзоэнергетическая реакция)")
        res.with_meta("exothermic", True)
    elif delta_m < 0:
        res.with_step("Δm < 0: масса выросла, энергия поглощается (эндоэнергетическая реакция)")
        res.with_meta("exothermic", False)
        res.with_step(
            f"Для протекания такой реакции нужна энергия не менее "
            f"{abs(Q_mev):.4f} МэВ"
        )
    else:
        res.with_step("Массы совпали: энергетический выход нулевой")
        res.with_meta("exothermic", None)
    return res


def einstein_energy(mass_defect_amu: float) -> Result:
    """Энергия, соответствующая дефекту массы: E = Δm·c²."""
    energy_j = mass_defect_amu * AMU_TO_J
    energy_mev = mass_defect_amu * AMU_TO_MEV

    res = Result(
        value=energy_j,
        unit="Дж",
        label="Энергия, соответствующая дефекту массы",
        method="E = Δm·c²",
    )
    res.with_step(f"Δm = {mass_defect_amu:.8f} а.е.м.")
    res.with_step(f"E = {mass_defect_amu:.8f}·{AMU_TO_J:.6e} = {energy_j:.6e} Дж")
    res.with_step(f"В мегаэлектронвольтах: {energy_mev:.6f} МэВ")
    res.with_meta("energy_mev", energy_mev)
    res.with_source(C_LIGHT.pretty())
    return res


# --------------------------------------------------------------------------
# Цепочки распада и равновесие
# --------------------------------------------------------------------------


def decay_chain(initial_amount: float, half_lives: list[float],
                time: float, time_unit: str = "с") -> Result:
    """Последовательный распад по цепочке A → B → C → ...

    Для двух звеньев решается аналитически, для трёх и более —
    численно методом Рунге — Кутты четвёртого порядка.
    """
    if initial_amount <= 0:
        raise NuclearError("Начальное количество должно быть больше нуля")
    if not half_lives:
        raise NuclearError("Не заданы периоды полураспада")
    if any(t <= 0 for t in half_lives):
        raise NuclearError("Все периоды полураспада должны быть больше нуля")
    if time <= 0:
        raise NuclearError("Время должно быть больше нуля")

    lambdas = [LN2 / t for t in half_lives]
    n_stages = len(lambdas)

    # Численное решение системы dN_i/dt = λ_{i-1}·N_{i-1} − λ_i·N_i.
    # Шаг привязан к самому быстрому звену: у схемы Рунге — Кутты 4 порядок
    # устойчив, пока λ·dt меньше примерно 2.8. При периоде 10⁻⁶ с и времени
    # 1 с прежний фиксированный шаг давал переполнение и NaN в ответе.
    fastest = max(lambdas)
    dt_max_stable = 0.1 / fastest
    dt = min(time / 200.0, dt_max_stable)
    steps = int(math.ceil(time / dt))
    limit = 200_000
    if steps > limit:
        half_lives_passed = time * fastest / LN2
        raise NuclearError(
            f"Цепочка слишком жёсткая для численного метода: самое быстрое "
            f"звено (T½ = {min(half_lives):g}) за {time:g} проходит "
            f"{half_lives_passed:.0f} периодов полураспада. Нужен больший "
            f"интервал времени или меньше звеньев.")
    dt = time / steps
    y = [initial_amount] + [0.0] * n_stages   # последний элемент — стабильный остаток

    def derivatives(state: list[float]) -> list[float]:
        d = [0.0] * len(state)
        d[0] = -lambdas[0] * state[0]
        for i in range(1, n_stages):
            d[i] = lambdas[i - 1] * state[i - 1] - lambdas[i] * state[i]
        # Последний, стабильный продукт только накапливается
        d[n_stages] = lambdas[n_stages - 1] * state[n_stages - 1]
        return d

    for _ in range(steps):
        k1 = derivatives(y)
        y2 = [a + 0.5 * dt * b for a, b in zip(y, k1)]
        k2 = derivatives(y2)
        y3 = [a + 0.5 * dt * b for a, b in zip(y, k2)]
        k3 = derivatives(y3)
        y4 = [a + dt * b for a, b in zip(y, k3)]
        k4 = derivatives(y4)
        y = [a + dt / 6 * (b1 + 2 * b2 + 2 * b3 + b4)
             for a, b1, b2, b3, b4 in zip(y, k1, k2, k3, k4)]

    rows = []
    for i in range(n_stages):
        rows.append({
            "Звено": i + 1,
            "T½": half_lives[i],
            "λ, 1/ед. времени": round(lambdas[i], 6),
            "Количество": y[i],
            "Доля, %": round(y[i] / initial_amount * 100, 4),
        })
    rows.append({
        "Звено": "стабильный",
        "T½": "∞",
        "λ, 1/ед. времени": 0.0,
        "Количество": y[n_stages],
        "Доля, %": round(y[n_stages] / initial_amount * 100, 4),
    })

    res = table_result(rows, label="Распад по цепочке",
                       columns=["Звено", "T½", "λ, 1/ед. времени",
                                "Количество", "Доля, %"])
    res.method = "Численное интегрирование системы уравнений распада (Рунге — Кутта 4)"
    res.with_step(f"Начальное количество: {initial_amount:g}")
    res.with_step(f"Время: {time:g} {time_unit}")
    for i, t in enumerate(half_lives):
        res.with_step(
            f"Звено {i + 1}: T½ = {t:g}, λ = {lambdas[i]:.6e}, "
            f"осталось {y[i]:.6e} ({y[i] / initial_amount * 100:.4f} %)"
        )
    res.with_step(
        f"Накопилось стабильного продукта: {y[n_stages]:.6e} "
        f"({y[n_stages] / initial_amount * 100:.4f} %)"
    )
    res.with_meta("amounts", y)
    res.with_meta("lambdas", lambdas)

    # Проверка сохранения суммарного количества атомов
    total = sum(y)
    res.with_step(
        f"Проверка баланса: сумма всех количеств {total:.6e} "
        f"против начального {initial_amount:.6e}"
    )
    if abs(total - initial_amount) / initial_amount > 0.01:
        res.with_warning(
            f"Баланс количества сошёлся с погрешностью "
            f"{abs(total - initial_amount) / initial_amount * 100:.2f} %: "
            f"шаг интегрирования слишком велик"
        )
    return res


# --------------------------------------------------------------------------
# Работа с настоящими нуклидами через библиотеку radioactivedecay
# --------------------------------------------------------------------------


def _radioactive_decay():
    """Ленивый импорт библиотеки радиоактивного распада.

    Импорт отложен, чтобы остальные функции движка работали даже там,
    где библиотека не установлена.
    """
    try:
        import radioactivedecay as rd
    except ImportError as exc:  # pragma: no cover
        raise NuclearError(
            "Для расчёта распада реальных нуклидов нужна библиотека "
            "radioactivedecay. Установите её: python -m pip install "
            "radioactivedecay"
        ) from exc
    return rd


def _normalize_nuclide(text: str) -> str:
    """Привести обозначение нуклида к виду «символ-масса».

    Допускаются записи «U-238», «U238», «238U», «u-238», «Tc-99m».
    Метастабильные состояния сохраняются: «U-238m».
    """
    raw = str(text).strip()
    if not raw:
        raise NuclearError("Не указан нуклид")

    # Русское название элемента заменяем на символ: «уран-238» -> «U-238»
    from ..core import periodic
    letters = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", raw)
    if letters:
        element = periodic.find(letters)
        if element is not None:
            start = raw.lower().find(letters.lower())
            if start >= 0:
                raw = raw[:start] + element.symbol + raw[start + len(letters):]

    compact = raw.replace(" ", "").replace("–", "-").replace("—", "-")

    # 238U, 238-U -> U-238
    match = re.match(r"^(\d+)-?([A-Za-z]+)(m\d*)?$", compact)
    if match:
        mass, symbol, meta = match.groups()
        return f"{_canonical_symbol(symbol)}-{mass}{meta or ''}"

    # U-238, U238, u238 -> U-238
    match = re.match(r"^([A-Za-z]+)-?(\d+)(m\d*)?$", compact)
    if match:
        symbol, mass, meta = match.groups()
        return f"{_canonical_symbol(symbol)}-{mass}{meta or ''}"

    return compact


def _canonical_symbol(symbol: str) -> str:
    """Привести символ элемента к правильному регистру: «u» -> «U»."""
    if len(symbol) == 1:
        return symbol.upper()
    return symbol[0].upper() + symbol[1:].lower()


def nuclide_data(nuclide: str) -> Result:
    """Справочные данные изотопа: период полураспада, каналы распада, дочерние.

    Данные берутся из базы библиотеки radioactivedecay (1252 нуклида,
    включая метастабильные состояния).
    """
    rd = _radioactive_decay()
    identifier = _normalize_nuclide(nuclide)

    try:
        item = rd.Nuclide(identifier)
    except Exception as exc:
        raise DataNotFoundError(
            f"Нуклид «{nuclide}» не найден в базе. Проверьте обозначение, "
            f"например: U-238, Cs-137, Co-60."
        ) from exc

    half_life_seconds = item.half_life("s")
    modes = [str(mode) for mode in item.decay_modes()]
    branching = item.branching_fractions()
    progeny = [str(child) for child in item.progeny()]

    rows = []
    for index, mode in enumerate(modes):
        share = branching[index] if index < len(branching) else None
        rows.append({
            "Канал распада": mode,
            "Доля": f"{share * 100:.4g} %" if share is not None else "—",
            "Дочерний нуклид": progeny[index] if index < len(progeny) else "—",
        })

    res = table_result(rows, label=f"Свойства нуклида {identifier}",
                       columns=["Канал распада", "Доля", "Дочерний нуклид"])
    res.method = "База библиотеки radioactivedecay (ICRP-107, AME2020, NUBASE2020)"
    res.with_source("radioactivedecay: ICRP-107, AME2020, NUBASE2020")
    res.with_step(f"Нуклид: {identifier}")
    res.with_step(f"A = {item.A}, Z = {item.Z}, состояние: {item.state}")
    res.with_step(f"Период полураспада: {_human_half_life(half_life_seconds)}")
    res.with_step(f"Каналов распада: {len(modes)}")
    res.with_meta("half_life_s", half_life_seconds)
    res.with_meta("modes", modes)
    res.with_meta("progeny", progeny)
    res.with_meta("atomic_mass", item.atomic_mass)

    if item.state not in ("", "0", None):
        res.with_warning(
            f"Нуклид находится в возбуждённом (метастабильном) состоянии "
            f"«{item.state}» — его период полураспада отличается от основного"
        )
    if len(modes) > 1:
        res.with_assumption(
            "Нуклид распадается по нескольким каналам. Доли указаны как "
            "вероятности ветвления на один распад."
        )

    return res


def _human_half_life(seconds: float) -> str:
    """Записать период полураспада в удобных единицах."""
    if not math.isfinite(seconds):
        return "стабилен"
    if seconds <= 0:
        return "неизвестен"

    for unit, factor in (("год", TIME_UNITS["год"]), ("сут", 86400.0),
                         ("ч", 3600.0), ("мин", 60.0)):
        if seconds >= factor:
            return f"{seconds / factor:.4g} {unit} ({seconds:.4g} с)"
    return f"{seconds:.4g} с"


def decay_by_nuclides(nuclides: dict[str, float], time: float,
                      time_unit: str = "год",
                      amount_unit: str = "атомов") -> Result:
    """Распад реальных нуклидов с учётом ветвлений и дочерних цепочек.

    В отличие от decay_chain, где периоды полураспада задаются числами,
    здесь достаточно имени изотопа: библиотека знает период, каналы распада
    и все дочерние нуклиды, включая ветвления.

    Args:
        nuclides: начальное количество по нуклидам, например
            {"U-238": 1e20, "Th-232": 5e19}.
        time: время выдержки.
        time_unit: единица времени — «с», «мин», «ч», «сут», «год».
        amount_unit: «атомов» или «Бк» (начальная активность).
    """
    if not nuclides:
        raise NuclearError("Не задано ни одного нуклида")
    if time < 0:
        raise NuclearError("Время не может быть отрицательным")

    unit = _RD_TIME_UNITS.get(time_unit)
    if unit is None:
        raise NuclearError(
            f"Неизвестная единица времени «{time_unit}». "
            f"Допустимые: {', '.join(sorted(_RD_TIME_UNITS))}"
        )

    rd = _radioactive_decay()

    contents = {}
    for name, amount in nuclides.items():
        if amount < 0:
            raise NuclearError(f"Количество для {name} не может быть отрицательным")
        contents[_normalize_nuclide(name)] = amount

    inventory_units = "Bq" if amount_unit.lower() in ("бк", "bq") else "num"
    try:
        inventory = rd.Inventory(contents, units=inventory_units)
        final = inventory.decay(time, unit)
    except Exception as exc:
        raise NuclearError(f"Не удалось выполнить распад: {exc}") from exc

    # Ключи от библиотеки приходят как numpy-строки: приводим к обычным,
    # иначе они протекают в подписи таблицы и в метаданные результата
    numbers = {str(k): float(v) for k, v in final.numbers().items()}
    activities = {str(k): float(v) for k, v in final.activities().items()}
    initial_numbers = {str(k): float(v) for k, v in inventory.numbers().items()}

    # Включаем исходные нуклиды, даже если они полностью распались
    all_names = set(contents) | set(numbers)
    rows = []
    for name in sorted(all_names):
        initial = initial_numbers.get(name, 0.0)
        remaining = numbers.get(name, 0.0)
        share = remaining / initial * 100 if initial else None
        rows.append({
            "Нуклид": name,
            "Было": f"{initial:.4g}",
            "Осталось": f"{remaining:.4g}",
            "Доля": f"{share:.4g} %" if share is not None else "образовался",
            "Активность, Бк": f"{activities.get(name, 0.0):.4g}",
        })

    res = table_result(rows, label=f"Распад за {time:g} {time_unit}",
                       columns=["Нуклид", "Было", "Осталось", "Доля",
                                "Активность, Бк"])
    res.method = ("Решение системы уравнений распада по базе "
                  "radioactivedecay с учётом ветвлений")
    res.with_step(f"Начальный состав: "
                  + ", ".join(f"{k} = {v:.4g}" for k, v in contents.items()))
    res.with_step(f"Время выдержки: {time:g} {time_unit}")
    res.with_step(f"Нуклидов в конечной смеси: {len(numbers)}")
    res.with_source("radioactivedecay: ICRP-107, AME2020, NUBASE2020")
    res.with_meta("numbers", numbers)
    res.with_meta("activities", activities)

    if len(numbers) > len(contents):
        res.with_assumption(
            "В расчёт включены дочерние нуклиды, которых не было в исходном "
            "составе: они образуются по цепочке распада."
        )
    return res


# Природные радиоактивные ряды: материнский нуклид и название
NATURAL_SERIES = {
    "ряд урана (U-238)": "U-238",
    "ряд актиния (U-235)": "U-235",
    "ряд тория (Th-232)": "Th-232",
}


def natural_series(name: str | None = None) -> Result:
    """Природные радиоактивные ряды и их характеристики.

    Args:
        name: ключ из NATURAL_SERIES. Если не задан, выводятся все три ряда.
    """
    rd = _radioactive_decay()

    if name is not None and name not in NATURAL_SERIES:
        raise NuclearError(
            f"Неизвестный ряд «{name}». Допустимые: "
            f"{', '.join(NATURAL_SERIES)}"
        )
    selected = {name: NATURAL_SERIES[name]} if name else dict(NATURAL_SERIES)

    rows = []
    for series_name, parent in selected.items():
        try:
            item = rd.Nuclide(parent)
        except Exception:  # pragma: no cover
            continue
        half_life = item.half_life("y")
        rows.append({
            "Ряд": series_name,
            "Материнский нуклид": parent,
            "T½, лет": f"{half_life:.4g}",
            "Прямых дочерних": len(item.progeny()),
        })

    res = table_result(rows, label="Природные радиоактивные ряды",
                       columns=["Ряд", "Материнский нуклид", "T½, лет",
                                "Прямых дочерних"])
    res.method = "База библиотеки radioactivedecay"
    for series_name, parent in selected.items():
        try:
            half_life = rd.Nuclide(parent).half_life("y")
        except Exception:  # pragma: no cover
            continue
        res.with_step(f"{series_name}: {parent}, T½ = {half_life:.4g} лет")
    res.with_assumption(
        "Приведены только материнские нуклиды рядов. Полная цепочка "
        "включает продукты распада вплоть до стабильного изотопа свинца."
    )
    return res


def secular_equilibrium(parent_half_life: float, daughter_half_life: float,
                        parent_activity: float) -> Result:
    """Вековое равновесие: активность дочернего нуклида.

    Если период полураспада материнского нуклида много больше дочернего,
    активности выравниваются: A(дочь) ≈ A(мать).
    """
    if parent_half_life <= 0 or daughter_half_life <= 0:
        raise NuclearError("Периоды полураспада должны быть больше нуля")
    if parent_activity <= 0:
        raise NuclearError("Активность материнского нуклида должна быть больше нуля")

    ratio = parent_half_life / daughter_half_life

    if ratio < 10:
        res = Result(
            label="Вековое равновесие не устанавливается",
            method="Условие T½(мать) ≫ T½(дочь)",
        )
        res.value = None
        res.with_step(
            f"T½(мать)/T½(дочь) = {ratio:.3f}, что меньше 10. "
            f"Вековое равновесие не достигается: активности не выравниваются."
        )
        res.with_warning(
            "Для векового равновесия необходимо, чтобы период полураспада "
            "материнского нуклида превышал дочерний не менее чем на порядок"
        )
        return res

    daughter_activity = parent_activity

    res = Result(
        value=daughter_activity,
        unit="Бк",
        label="Активность дочернего нуклида в вековом равновесии",
        method="A(дочь) = A(мать) при T½(мать) ≫ T½(дочь)",
    )
    res.with_step(f"T½(мать) = {parent_half_life:g}")
    res.with_step(f"T½(дочь) = {daughter_half_life:g}")
    res.with_step(f"Отношение: {ratio:.3e} — условие выполнено")
    res.with_step(f"A(дочь) = A(мать) = {parent_activity:.6e} Бк")
    res.with_meta("ratio", ratio)
    res.with_meta("daughter_activity", daughter_activity)
    res.with_assumption(
        "Материнский нуклид распадается значительно медленнее дочернего, "
        "поэтому его количество за время наблюдения практически не меняется"
    )
    return res


# --------------------------------------------------------------------------
# Дозиметрия
# --------------------------------------------------------------------------


def absorbed_dose(energy_j: float, mass_kg: float) -> Result:
    """Поглощённая доза: D = E/m, измеряется в греях."""
    if energy_j < 0:
        raise NuclearError("Энергия не может быть отрицательной")
    if mass_kg <= 0:
        raise NuclearError("Масса должна быть больше нуля")

    dose = energy_j / mass_kg

    res = Result(
        value=dose,
        unit="Гр",
        label="Поглощённая доза",
        method="D = E/m",
    )
    res.with_step(f"D = {energy_j:g} Дж / {mass_kg:g} кг = {dose:.6f} Гр")
    res.with_step("1 Гр = 1 Дж/кг")
    res.with_meta("dose_gy", dose)
    return res


def equivalent_dose(absorbed_dose_gy: float, radiation_type: str = "gamma") -> Result:
    """Эквивалентная доза: H = D·w_R, измеряется в зивертах.

    Взвешивающие коэффициенты по НРБ-99/2009 и публикациям МКРЗ.
    """
    factors = {
        "gamma": (1.0, "фотоны всех энергий"),
        "рентген": (1.0, "рентгеновское излучение"),
        "beta": (1.0, "электроны и бета-частицы"),
        "электрон": (1.0, "электроны"),
        "нейтрон": (5.0, "нейтроны (зависит от энергии, взято среднее)"),
        "протон": (2.0, "протоны"),
        "alpha": (20.0, "альфа-частицы"),
        "альфа": (20.0, "альфа-частицы"),
        "осколок": (20.0, "тяжёлые ядра отдачи"),
    }

    key = str(radiation_type).strip().lower()
    if key not in factors:
        raise NuclearError(
            f"Неизвестный тип излучения «{radiation_type}». "
            f"Допустимые: {', '.join(sorted(set(factors)))}"
        )

    factor, description = factors[key]
    if absorbed_dose_gy < 0:
        raise NuclearError("Поглощённая доза не может быть отрицательной")

    h = absorbed_dose_gy * factor

    res = Result(
        value=h,
        unit="Зв",
        label="Эквивалентная доза",
        method="H = D·w_R",
    )
    res.with_step(f"Поглощённая доза: {absorbed_dose_gy:g} Гр")
    res.with_step(f"Тип излучения: {description}, w_R = {factor:g}")
    res.with_step(f"H = {absorbed_dose_gy:g}·{factor:g} = {h:.6f} Зв")
    res.with_step(f"В миллизивертах: {h * 1000:.4f} мЗв")
    res.with_meta("sievert", h)
    res.with_meta("millisievert", h * 1000)
    res.with_meta("weighting_factor", factor)
    res.with_step(
        "Для сравнения: естественный фон даёт около 2–3 мЗв в год, "
        "разовая доза 1 Зв вызывает лучевую болезнь"
    )
    res.with_assumption(
        "Взвешивающий коэффициент взят по типу излучения без учёта его "
        "спектра. Для нейтронов коэффициент сильно зависит от энергии."
    )
    return res


def dose_rate(activity_bq: float, gamma_constant: float,
              distance_m: float) -> Result:
    """Мощность дозы от точечного источника.

    P = A·Г/r², где Г — гамма-постоянная радионуклида.

    Args:
        activity_bq: активность, Бк.
        gamma_constant: гамма-постоянная, (Р·см²)/(ч·мКи).
        distance_m: расстояние, м.
    """
    if activity_bq <= 0:
        raise NuclearError("Активность должна быть больше нуля")
    if gamma_constant < 0:
        raise NuclearError("Гамма-постоянная не может быть отрицательной")
    if distance_m <= 0:
        raise NuclearError("Расстояние должно быть больше нуля")

    # Переводим активность в мКи, расстояние в см
    activity_mci = activity_bq / 3.7e7
    distance_cm = distance_m * 100.0
    rate_r_h = gamma_constant * activity_mci / distance_cm ** 2

    res = Result(
        value=rate_r_h,
        unit="Р/ч",
        label="Мощность экспозиционной дозы",
        method="P = A·Г/r²",
    )
    res.with_step(f"Активность: {activity_bq:.6e} Бк = {activity_mci:.6e} мКи")
    res.with_step(f"Расстояние: {distance_m:g} м = {distance_cm:g} см")
    res.with_step(f"Гамма-постоянная: {gamma_constant:g} (Р·см²)/(ч·мКи)")
    res.with_step(
        f"P = {gamma_constant:g}·{activity_mci:.6e}/{distance_cm:g}² = "
        f"{rate_r_h:.6e} Р/ч"
    )
    # 1 Р/ч приблизительно соответствует 8.7 мГр/ч в воздухе
    res.with_step(
        f"Приблизительно в единицах поглощённой дозы: "
        f"{rate_r_h * 8.7:.6e} мГр/ч в воздухе"
    )
    res.with_meta("rate_r_h", rate_r_h)
    res.with_meta("rate_mgy_h", rate_r_h * 8.7)
    res.with_assumption(
        "Источник точечный, поглощение в воздухе не учитывается, "
        "рассеяние отсутствует. Для реальных расчётов нужны поправки "
        "на барьер и геометрию."
    )
    return res
