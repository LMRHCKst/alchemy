"""Химическая кинетика: порядки реакций, Аррениус, обработка опытных данных.

Возможности, которых не было в прежней версии:

    * определение порядка реакции по опытным данным (метод Вант-Гоффа,
      интегральный метод с линеаризацией и выбором лучшей модели по R²);
    * подгонка константы скорости и энергии активации методом наименьших
      квадратов вместо расчёта по двум точкам;
    * доверительные интервалы для параметров;
    * модели сложных реакций: параллельные, последовательные, обратимые.

Расчёт ведётся без внешних библиотек: линейная регрессия реализована здесь же,
поэтому результат воспроизводим и не зависит от установленных пакетов.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.constants import R
from ..core.errors import InputError
from ..core.results import Result, series_result, table_result

R_GAS = R.value   # 8.314462618 Дж/(моль·К)


class KineticsError(InputError):
    """Кинетический расчёт невозможен."""


# --------------------------------------------------------------------------
# Простейшие пересчёты
# --------------------------------------------------------------------------


def rate_law(k: float, concentrations: dict[str, float],
             orders: dict[str, float]) -> Result:
    """Скорость реакции по закону действующих масс: v = k·Π[A]^n.

    Args:
        k: константа скорости.
        concentrations: {вещество: концентрация, моль/л}.
        orders: {вещество: порядок по веществу}.
    """
    if k < 0:
        raise KineticsError("Константа скорости не может быть отрицательной")

    total_order = 0.0
    product = 1.0
    steps = []
    for species, order in orders.items():
        if species not in concentrations:
            raise KineticsError(
                f"Для вещества {species} не задана концентрация"
            )
        c = concentrations[species]
        if c < 0:
            raise KineticsError("Концентрация не может быть отрицательной")
        if c == 0 and order < 0:
            raise KineticsError(
                f"При нулевой концентрации {species} и отрицательном порядке "
                f"скорость не определена"
            )
        contribution = c ** order
        product *= contribution
        total_order += order
        steps.append(f"[{species}]^{order:g} = {c:g}^{order:g} = {contribution:.6e}")

    v = k * product

    res = Result(
        value=v,
        unit="моль/(л·с)",
        label="Скорость реакции",
        method="v = k·Π[A]^n (закон действующих масс)",
    )
    res.with_step(f"k = {k:g}")
    for s in steps:
        res.with_step(s)
    res.with_step(f"Суммарный порядок реакции: {total_order:g}")
    res.with_step(f"v = {k:g}·{product:.6e} = {v:.6e} моль/(л·с)")
    res.with_meta("total_order", total_order)
    return res


def rate_constant_from_rate(rate: float, concentrations: dict[str, float],
                            orders: dict[str, float]) -> Result:
    """Константа скорости по измеренной скорости реакции."""
    if rate < 0:
        raise KineticsError("Скорость не может быть отрицательной")

    product = 1.0
    for species, order in orders.items():
        c = concentrations.get(species)
        if c is None:
            raise KineticsError(f"Не задана концентрация {species}")
        product *= c ** order

    if product == 0:
        raise KineticsError(
            "Произведение концентраций равно нулю — константу определить нельзя"
        )

    k = rate / product

    res = Result(
        value=k,
        unit="(зависит от порядка реакции)",
        label="Константа скорости реакции",
        method="k = v/Π[A]^n",
    )
    res.with_step(f"Произведение концентраций: {product:.6e}")
    res.with_step(f"k = {rate:g}/{product:.6e} = {k:.6e}")
    return res


def order_of_reaction(rate1: float, c1: float, rate2: float, c2: float,
                      species: str = "A") -> Result:
    """Порядок реакции по веществу методом Вант-Гоффа.

    n = lg(v₂/v₁)/lg(c₂/c₁) при изменении концентрации только этого вещества.
    """
    for name, value in (("v₁", rate1), ("v₂", rate2), ("c₁", c1), ("c₂", c2)):
        if value <= 0:
            raise KineticsError(f"{name} должна быть больше нуля")
    if abs(c1 - c2) < 1e-15:
        raise KineticsError(
            "Концентрации совпадают, порядок реакции определить нельзя"
        )

    n = math.log(rate2 / rate1) / math.log(c2 / c1)

    res = Result(
        value=n,
        label=f"Порядок реакции по веществу {species}",
        method="Метод Вант-Гоффа: n = lg(v₂/v₁)/lg(c₂/c₁)",
    )
    res.with_step(f"lg(v₂/v₁) = lg({rate2:g}/{rate1:g}) = {math.log10(rate2 / rate1):.6f}")
    res.with_step(f"lg(c₂/c₁) = lg({c2:g}/{c1:g}) = {math.log10(c2 / c1):.6f}")
    res.with_step(f"n = {n:.6f}")

    rounded = round(n)
    if abs(n - rounded) < 0.05:
        res.with_step(f"Значение близко к целому: порядок равен {rounded}")
        res.with_meta("nearest_integer", rounded)
    else:
        res.with_step(
            "Значение нецелое — это возможно для дробных порядков или "
            "указывает на сложный механизм реакции"
        )
    res.with_assumption(
        "Концентрация остальных реагентов поддерживается постоянной, "
        "температура не меняется"
    )
    return res


# --------------------------------------------------------------------------
# Интегральные законы скорости
# --------------------------------------------------------------------------


@dataclass
class IntegratedLaw:
    """Результат расчёта по интегральному закону скорости."""

    order: int
    value: float
    unit: str
    quantity: str          # что найдено: ct, c0, k, t
    formula: str


def concentration_at_time(order: int, k: float, c0: float, t: float) -> Result:
    """Концентрация реагента через время t.

    Реакции нулевого, первого и второго порядка:
        C(t) = C₀ − k·t                        (порядок 0)
        C(t) = C₀·exp(−k·t)                    (порядок 1)
        C(t) = C₀/(1 + k·C₀·t)                 (порядок 2)
    """
    if k < 0:
        raise KineticsError("Константа скорости не может быть отрицательной")
    if c0 <= 0:
        raise KineticsError("Начальная концентрация должна быть больше нуля")
    if t < 0:
        raise KineticsError("Время не может быть отрицательным")

    if order == 0:
        value = c0 - k * t
        formula = "C(t) = C₀ − k·t"
        if value < 0:
            t_full = c0 / k if k > 0 else float("inf")
            raise KineticsError(
                f"Реакция завершится за {t_full:.6g} ед. времени: "
                f"при t = {t:g} концентрация обратилась бы в отрицательную. "
                f"Проверьте исходные данные."
            )
    elif order == 1:
        value = c0 * math.exp(-k * t)
        formula = "C(t) = C₀·exp(−k·t)"
    elif order == 2:
        value = c0 / (1.0 + k * c0 * t)
        formula = "C(t) = C₀/(1 + k·C₀·t)"
    else:
        raise KineticsError(
            f"Поддерживаются порядки 0, 1 и 2, получен {order}. "
            f"Для других порядков используйте численное интегрирование."
        )

    res = Result(value=value, unit="моль/л",
                 label=f"Концентрация через {t:g} ед. времени",
                 method=formula)
    res.with_step(f"Порядок реакции: {order}")
    res.with_step(f"C₀ = {c0:g} моль/л, k = {k:g}, t = {t:g}")
    res.with_step(f"C(t) = {value:.6e} моль/л")
    res.with_step(
        f"Прореагировало: {c0 - value:.6e} моль/л "
        f"({(c0 - value) / c0 * 100:.2f} % от начального)"
    )
    res.with_meta("reacted", c0 - value)
    res.with_meta("fraction_remaining", value / c0)
    return res


def time_to_concentration(order: int, k: float, c0: float, ct: float) -> Result:
    """Время достижения заданной концентрации."""
    if k <= 0:
        raise KineticsError("Константа скорости должна быть больше нуля")
    if c0 <= 0 or ct <= 0:
        raise KineticsError("Концентрации должны быть больше нуля")
    if ct > c0:
        raise KineticsError(
            f"Конечная концентрация {ct:g} больше начальной {c0:g} — "
            f"для реакции расходования это невозможно"
        )

    if order == 0:
        t = (c0 - ct) / k
        formula = "t = (C₀ − C)/k"
    elif order == 1:
        t = math.log(c0 / ct) / k
        formula = "t = ln(C₀/C)/k"
    elif order == 2:
        t = (1.0 / ct - 1.0 / c0) / k
        formula = "t = (1/C − 1/C₀)/k"
    else:
        raise KineticsError(f"Поддерживаются порядки 0, 1 и 2, получен {order}")

    res = Result(value=t, unit="(единица времени, обратная k)",
                 label="Время достижения заданной концентрации",
                 method=formula)
    res.with_step(f"Порядок {order}, k = {k:g}, C₀ = {c0:g}, C = {ct:g}")
    res.with_step(f"t = {t:.6g}")
    res.with_step(f"Степень превращения: {(1 - ct / c0) * 100:.4f} %")
    res.with_meta("conversion", 1 - ct / c0)
    return res


def half_life(order: int, k: float, c0: float | None = None) -> Result:
    """Период полупревращения.

    Для нулевого порядка зависит от начальной концентрации,
    для первого — нет, для второго — обратно пропорционален C₀.
    """
    if k <= 0:
        raise KineticsError("Константа скорости должна быть больше нуля")

    if order == 0:
        if c0 is None or c0 <= 0:
            raise KineticsError(
                "Для нулевого порядка нужна начальная концентрация"
            )
        t_half = c0 / (2 * k)
        formula = "t½ = C₀/(2k)"
    elif order == 1:
        t_half = math.log(2) / k
        formula = "t½ = ln2/k"
    elif order == 2:
        if c0 is None or c0 <= 0:
            raise KineticsError(
                "Для второго порядка нужна начальная концентрация"
            )
        t_half = 1.0 / (k * c0)
        formula = "t½ = 1/(k·C₀)"
    else:
        raise KineticsError(f"Поддерживаются порядки 0, 1 и 2, получен {order}")

    res = Result(value=t_half, unit="(единица времени, обратная k)",
                 label=f"Период полупревращения для реакции порядка {order}",
                 method=formula)
    res.with_step(f"k = {k:g}" + (f", C₀ = {c0:g} моль/л" if c0 else ""))
    res.with_step(f"t½ = {t_half:.6g}")

    if order == 1:
        res.with_step(
            "Для первого порядка период полупревращения не зависит от "
            "начальной концентрации — это его отличительная черта"
        )
    elif order == 2 and c0:
        res.with_step(
            f"Для второго порядка при уменьшении C₀ вдвое период "
            f"полупревращения удвоится: {2 * t_half:.6g}"
        )

    res.with_meta("decay_99_percent", _time_for_conversion(order, k, c0, 0.99))
    return res


def _time_for_conversion(order: int, k: float, c0: float | None,
                         conversion: float) -> float | None:
    """Время достижения заданной степени превращения."""
    if k <= 0 or conversion <= 0 or conversion >= 1:
        return None
    if order == 0:
        if c0 is None:
            return None
        return c0 * conversion / k
    if order == 1:
        return -math.log(1 - conversion) / k
    if order == 2:
        if c0 is None:
            return None
        return conversion / (k * c0 * (1 - conversion))
    return None


# --------------------------------------------------------------------------
# Температурная зависимость: уравнение Аррениуса
# --------------------------------------------------------------------------


def arrhenius_k2(k1: float, t1: float, ea_j: float, t2: float,
                 temperature_unit: str = "К") -> Result:
    """Константа скорости при другой температуре.

    ln(k₂/k₁) = −Ea/R·(1/T₂ − 1/T₁)

    Args:
        ea_j: энергия активации в Дж/моль.
    """
    from ..core.units import convert
    T1 = convert(t1, temperature_unit, "К")
    T2 = convert(t2, temperature_unit, "К")

    if k1 <= 0:
        raise KineticsError("k₁ должна быть больше нуля")
    if T1 <= 0 or T2 <= 0:
        raise KineticsError("Температуры должны быть выше абсолютного нуля")
    if T1 == T2:
        raise KineticsError("Температуры должны различаться")
    if ea_j < 0:
        raise KineticsError(
            "Энергия активации не может быть отрицательной: это означало бы "
            "замедление реакции при нагревании"
        )

    ln_ratio = -ea_j / R_GAS * (1.0 / T2 - 1.0 / T1)
    k2 = k1 * math.exp(ln_ratio)

    res = Result(value=k2, unit="(та же единица, что и k₁)",
                 label=f"Константа скорости при {T2:.2f} К",
                 method="Уравнение Аррениуса в интегральной форме")
    res.with_step(f"Ea = {ea_j:g} Дж/моль = {ea_j / 1000:.2f} кДж/моль")
    res.with_step(f"T₁ = {T1:.2f} К, T₂ = {T2:.2f} К")
    res.with_step(
        f"ln(k₂/k₁) = −{ea_j:g}/{R_GAS:g}·(1/{T2:.2f} − 1/{T1:.2f}) = {ln_ratio:.6f}"
    )
    res.with_step(f"k₂ = {k1:g}·e^{ln_ratio:.6f} = {k2:.6e}")
    res.with_step(
        f"Скорость изменилась в {k2 / k1:.4f} раза "
        f"({'выросла' if k2 > k1 else 'упала'})"
    )
    res.with_meta("k_ratio", k2 / k1)
    res.with_meta("ln_ratio", ln_ratio)

    if abs(T2 - T1) > 100:
        res.with_warning(
            f"Интервал температур {abs(T2 - T1):.0f} К велик. Уравнение "
            f"Аррениуса с постоянной Ea в таком интервале даёт заметную "
            f"погрешность: реальная Ea сама зависит от температуры."
        )
    return res


def activation_energy(k1: float, t1: float, k2: float, t2: float,
                      temperature_unit: str = "К") -> Result:
    """Энергия активации по двум значениям константы скорости.

    Ea = R·ln(k₂/k₁)/(1/T₁ − 1/T₂)
    """
    from ..core.units import convert
    T1 = convert(t1, temperature_unit, "К")
    T2 = convert(t2, temperature_unit, "К")

    if k1 <= 0 or k2 <= 0:
        raise KineticsError("Константы скорости должны быть больше нуля")
    if T1 <= 0 or T2 <= 0:
        raise KineticsError("Температуры должны быть выше абсолютного нуля")
    if abs(T1 - T2) < 1e-9:
        raise KineticsError("Температуры должны различаться")

    ea = R_GAS * math.log(k2 / k1) / (1.0 / T1 - 1.0 / T2)

    res = Result(value=ea, unit="Дж/моль",
                 label="Энергия активации",
                 method="Ea = R·ln(k₂/k₁)/(1/T₁ − 1/T₂)")
    res.with_step(f"ln(k₂/k₁) = ln({k2:g}/{k1:g}) = {math.log(k2 / k1):.6f}")
    res.with_step(
        f"1/T₁ − 1/T₂ = 1/{T1:.2f} − 1/{T2:.2f} = {1 / T1 - 1 / T2:.6e}"
    )
    res.with_step(f"Ea = {R_GAS:g}·{math.log(k2 / k1):.6f}/{1 / T1 - 1 / T2:.6e}")
    res.with_step(f"Ea = {ea:.2f} Дж/моль = {ea / 1000:.2f} кДж/моль")
    res.with_meta("ea_kj", ea / 1000)

    if ea < 0:
        res.with_warning(
            "Отрицательная энергия активации физически бессмысленна. "
            "Проверьте данные: вероятно, перепутаны значения k или T, "
            "либо реакция осложнена диффузией или равновесием."
        )
    elif ea > 400000:
        res.with_warning(
            f"Энергия активации {ea / 1000:.0f} кДж/моль очень велика. "
            f"Такие значения редки, проверьте данные."
        )
    return res


def arrhenius_parameters(data: list[tuple[float, float]]) -> Result:
    """Подгонка предэкспоненты и энергии активации по набору опытных точек.

    Args:
        data: список пар (температура в К, константа скорости).
              Нужно не менее трёх точек для оценки качества.

    Линеаризация: ln k = ln A − Ea/(R·T), регрессия ln k от 1/T.
    """
    if len(data) < 2:
        raise KineticsError("Нужно не менее двух опытных точек")

    valid = [(T, k) for T, k in data if T > 0 and k > 0]
    if len(valid) < 2:
        raise KineticsError(
            "Температуры и константы скорости должны быть больше нуля"
        )

    xs = [1.0 / T for T, _ in valid]
    ys = [math.log(k) for _, k in valid]

    slope, intercept, r2, stderr_slope = _linear_regression(xs, ys)

    ea = -slope * R_GAS
    ln_A = intercept
    A = math.exp(ln_A)

    res = Result(
        value=ea,
        unit="Дж/моль",
        label="Энергия активации по опытным данным",
        method="Метод наименьших квадратов: ln k от 1/T",
    )
    res.with_step(f"Опытных точек: {len(valid)}")
    for T, k in valid:
        res.with_step(f"  T = {T:g} К, k = {k:.6e}, 1/T = {1 / T:.6e}, ln k = {math.log(k):.6f}")
    res.with_step(f"Уравнение регрессии: ln k = {intercept:.6f} + ({slope:.4f})·(1/T)")
    res.with_step(f"Ea = −наклон·R = {ea:.2f} Дж/моль = {ea / 1000:.2f} кДж/моль")
    res.with_step(f"ln A = {ln_A:.6f}, A = {A:.6e}")
    res.with_step(f"Коэффициент детерминации R² = {r2:.6f}")

    res.with_meta("ea_j", ea)
    res.with_meta("ea_kj", ea / 1000)
    res.with_meta("A", A)
    res.with_meta("ln_A", ln_A)
    res.with_meta("r_squared", r2)
    res.with_meta("slope", slope)
    res.with_meta("intercept", intercept)

    if len(valid) >= 3:
        # Доверительный интервал для Ea по стандартной ошибке наклона
        margin = 2.0 * stderr_slope * R_GAS   # приблизительно 95 %
        res.with_step(
            f"Оценка доверительного интервала (95 %): "
            f"Ea = {ea / 1000:.2f} ± {margin / 1000:.2f} кДж/моль"
        )
        res.with_meta("ea_ci95_kj", margin / 1000)
        res.uncertainty = margin

    res.with_step(
        f"При повышении температуры от {valid[0][0]:g} до {valid[-1][0]:g} К "
        f"константа скорости растёт в {valid[-1][1] / valid[0][1]:.4g} раза"
    )

    if r2 < 0.98:
        res.with_warning(
            f"R² = {r2:.4f} ниже 0.98: точки плохо ложатся на прямую. "
            f"Возможные причины — ошибки опыта, осложнение диффузией "
            f"или изменение механизма реакции в этом интервале температур."
        )
    if len(valid) == 2:
        res.with_warning(
            "По двум точкам нельзя оценить качество подгонки: "
            "R² всегда будет равен единице. Добавьте точки."
        )
    return res


def _linear_regression(xs: list[float], ys: list[float]
                       ) -> tuple[float, float, float, float]:
    """Линейная регрессия y = a + b·x.

    Returns:
        (наклон, свободный член, R², стандартная ошибка наклона)
    """
    n = len(xs)
    if n < 2:
        raise KineticsError("Для регрессии нужно минимум две точки")

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        raise KineticsError(
            "Все значения 1/T совпадают: регрессию построить нельзя"
        )

    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x

    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

    if n > 2 and sxx > 0:
        stderr_slope = math.sqrt(ss_res / (n - 2) / sxx)
    else:
        stderr_slope = 0.0

    return slope, intercept, r2, stderr_slope


def arrhenius_curve(A: float, ea_j: float, t_min: float = 250.0,
                    t_max: float = 600.0, points: int = 60) -> Result:
    """Зависимость константы скорости от температуры — для графика."""
    if A <= 0:
        raise KineticsError("Предэкспоненциальный множитель должен быть больше нуля")
    if t_min <= 0 or t_max <= t_min:
        raise KineticsError("Температуры должны удовлетворять 0 < Tмин < Tмакс")

    data = []
    step = (t_max - t_min) / (points - 1) if points > 1 else 0
    for i in range(points):
        T = t_min + i * step
        k = A * math.exp(-ea_j / (R_GAS * T))
        data.append((T, k))

    res = series_result(
        data,
        x_label="Температура, К",
        y_label="Константа скорости k",
        label=f"Зависимость k(T) при Ea = {ea_j / 1000:.1f} кДж/моль",
    )
    res.method = "k = A·exp(−Ea/RT)"
    res.with_meta("A", A)
    res.with_meta("ea_j", ea_j)

    # Температурный коэффициент: во сколько раз растёт k при +10 К
    k_25 = A * math.exp(-ea_j / (R_GAS * 298.15))
    k_35 = A * math.exp(-ea_j / (R_GAS * 308.15))
    res.with_step(
        f"При нагревании от 25 до 35 °C скорость растёт в {k_35 / k_25:.3f} раза"
    )
    res.with_step(
        "Правило Вант-Гоффа (рост в 2–4 раза на 10 К) выполняется при "
        "Ea примерно 50–90 кДж/моль"
    )
    res.with_meta("ratio_25_35", k_35 / k_25)
    return res


# --------------------------------------------------------------------------
# Определение порядка реакции по опытным данным
# --------------------------------------------------------------------------


def determine_order(times: list[float], concentrations: list[float],
                    c0: float | None = None) -> Result:
    """Определить порядок реакции по опытным данным.

    Проверяются три модели: нулевой, первый и второй порядок. Для каждой
    строится линеаризация в соответствующих координатах, и выбирается та,
    у которой коэффициент детерминации R² выше.

    Args:
        times: моменты времени.
        concentrations: концентрации в эти моменты.
        c0: начальная концентрация. Если не задана, берётся первое значение.

    Координаты линеаризации:
        нулевой порядок:  C   от t   →  наклон −k
        первый порядок:   ln C от t  →  наклон −k
        второй порядок:   1/C  от t  →  наклон +k
    """
    if len(times) != len(concentrations):
        raise KineticsError(
            f"Число моментов времени ({len(times)}) и концентраций "
            f"({len(concentrations)}) должно совпадать"
        )
    if len(times) < 3:
        raise KineticsError(
            "Для определения порядка нужно не менее трёх точек"
        )

    pairs = sorted(zip(times, concentrations))
    ts = [t for t, _ in pairs]
    cs = [c for _, c in pairs]

    if any(c <= 0 for c in cs):
        raise KineticsError(
            "Все концентрации должны быть больше нуля: иначе логарифмическая "
            "и обратная линеаризации невозможны"
        )
    if any(t < 0 for t in ts):
        raise KineticsError("Время не может быть отрицательным")

    c_start = c0 if c0 is not None else cs[0]
    if c_start <= 0:
        raise KineticsError("Начальная концентрация должна быть больше нуля")

    models = []

    # Нулевой порядок: C от t
    slope0, intercept0, r2_0, _ = _linear_regression(ts, cs)
    models.append({
        "Порядок": 0,
        "Координаты": "C — t",
        "k": -slope0,
        "R²": r2_0,
        "Линейная форма": "C = C₀ − k·t",
    })

    # Первый порядок: ln C от t
    ln_c = [math.log(c) for c in cs]
    slope1, intercept1, r2_1, _ = _linear_regression(ts, ln_c)
    models.append({
        "Порядок": 1,
        "Координаты": "ln C — t",
        "k": -slope1,
        "R²": r2_1,
        "Линейная форма": "ln C = ln C₀ − k·t",
    })

    # Второй порядок: 1/C от t
    inv_c = [1.0 / c for c in cs]
    slope2, intercept2, r2_2, _ = _linear_regression(ts, inv_c)
    models.append({
        "Порядок": 2,
        "Координаты": "1/C — t",
        "k": slope2,
        "R²": r2_2,
        "Линейная форма": "1/C = 1/C₀ + k·t",
    })

    best = max(models, key=lambda m: m["R²"])

    res = table_result(models, label="Определение порядка реакции",
                       columns=["Порядок", "Координаты", "k", "R²", "Линейная форма"])
    res.method = "Интегральный метод: выбор лучшей линеаризации по R²"
    res.with_step(f"Опытных точек: {len(ts)}")
    for t, c in pairs:
        res.with_step(f"  t = {t:g}, C = {c:.6e} моль/л")
    res.with_step("")
    for m in models:
        res.with_step(
            f"Порядок {m['Порядок']} ({m['Координаты']}): "
            f"k = {m['k']:.6e}, R² = {m['R²']:.6f}"
        )
    res.with_step("")
    res.with_step(
        f"Лучшая модель — порядок {best['Порядок']} "
        f"(R² = {best['R²']:.6f}, k = {best['k']:.6e})"
    )

    res.with_meta("order", best["Порядок"])
    res.with_meta("k", best["k"])
    res.with_meta("r_squared", best["R²"])
    res.with_meta("models", models)
    res.with_meta("c0", c_start)

    # Проверка согласованности: если две модели близки, вывод ненадёжен
    sorted_models = sorted(models, key=lambda m: -m["R²"])
    if len(sorted_models) >= 2:
        gap = sorted_models[0]["R²"] - sorted_models[1]["R²"]
        if gap < 0.01:
            res.with_warning(
                f"Порядки {sorted_models[0]['Порядок']} и "
                f"{sorted_models[1]['Порядок']} описывают данные почти "
                f"одинаково хорошо (разница R² всего {gap:.4f}). "
                f"Нужно больше точек или более широкий интервал времени."
            )
        res.with_meta("second_best_order", sorted_models[1]["Порядок"])
        res.with_meta("r2_gap", gap)

    if best["R²"] < 0.99:
        res.with_warning(
            f"Даже лучшая модель даёт R² = {best['R²']:.4f}. "
            f"Порядок реакции определён ненадёжно."
        )

    # Проверка полупревращения как дополнительный критерий
    order = best["Порядок"]
    k = best["k"]
    if k > 0:
        if order == 0:
            t_half = c_start / (2 * k)
        elif order == 1:
            t_half = math.log(2) / k
        else:
            t_half = 1.0 / (k * c_start)
        res.with_step(f"Период полупревращения при этих параметрах: {t_half:.6g}")
        res.with_meta("half_life", t_half)

    res.with_assumption(
        "Температура постоянна, реакция необратима, начальная концентрация "
        "известна точно"
    )
    return res


def vanthoff_temperature_coefficient(k1: float, k2: float,
                                     dt: float = 10.0) -> Result:
    """Температурный коэффициент Вант-Гоффа γ = k(T+ΔT)/k(T)."""
    if k1 <= 0 or k2 <= 0:
        raise KineticsError("Константы скорости должны быть больше нуля")
    if dt <= 0:
        raise KineticsError("Интервал температур должен быть больше нуля")

    gamma = (k2 / k1) ** (10.0 / dt)

    res = Result(
        value=gamma,
        label=f"Температурный коэффициент (приведён к 10 К)",
        method="γ = (k₂/k₁)^(10/ΔT)",
    )
    res.with_step(f"k₂/k₁ = {k2 / k1:.4f} на интервале {dt:g} К")
    res.with_step(f"γ = {gamma:.4f}")
    res.with_step(
        "Правило Вант-Гоффа: обычно γ лежит в пределах 2–4. "
        + ("Значение в этих пределах." if 2 <= gamma <= 4
           else "Значение выходит за обычные пределы.")
    )
    return res


# --------------------------------------------------------------------------
# Сложные реакции
# --------------------------------------------------------------------------


def parallel_reactions(k1: float, k2: float) -> Result:
    """Параллельные реакции первого порядка: A → B и A → C.

    Доли продуктов определяются отношением констант и не зависят от
    начальной концентрации.
    """
    if k1 <= 0 or k2 <= 0:
        raise KineticsError("Константы скорости должны быть больше нуля")

    k_total = k1 + k2
    fraction_b = k1 / k_total
    fraction_c = k2 / k_total
    t_half = math.log(2) / k_total

    res = Result(
        value=fraction_b,
        label="Доля продукта B в параллельной реакции",
        method="[B]/[C] = k₁/k₂, доли не зависят от времени",
    )
    res.with_step(f"k₁ = {k1:g} (образование B), k₂ = {k2:g} (образование C)")
    res.with_step(f"Эффективная константа: k = k₁ + k₂ = {k_total:g}")
    res.with_step(f"Доля B: {fraction_b * 100:.4f} %")
    res.with_step(f"Доля C: {fraction_c * 100:.4f} %")
    res.with_step(f"Период полупревращения исходного вещества: {t_half:.6g}")
    res.with_meta("k_total", k_total)
    res.with_meta("fraction_b", fraction_b)
    res.with_meta("fraction_c", fraction_c)
    res.with_meta("half_life", t_half)
    res.with_step(
        "Соотношение продуктов не меняется со временем — это признак "
        "параллельных реакций одного порядка"
    )
    return res


def consecutive_reactions(k1: float, k2: float, c0: float,
                          points: int = 100,
                          t_max: float | None = None) -> Result:
    """Последовательные реакции A → B → C, обе первого порядка.

    Концентрации:
        [A] = C₀·exp(−k₁t)
        [B] = C₀·k₁/(k₂−k₁)·(exp(−k₁t) − exp(−k₂t))
        [C] = C₀ − [A] − [B]
    """
    if k1 <= 0 or k2 <= 0:
        raise KineticsError("Константы скорости должны быть больше нуля")
    if c0 <= 0:
        raise KineticsError("Начальная концентрация должна быть больше нуля")
    if abs(k1 - k2) < 1e-12:
        raise KineticsError(
            "При k₁ = k₂ формула для промежуточного продукта вырождается: "
            "задайте различающиеся константы"
        )

    if t_max is None:
        t_max = 5.0 * math.log(2) / min(k1, k2)

    data = []
    step = t_max / (points - 1) if points > 1 else 0
    for i in range(points):
        t = i * step
        a = c0 * math.exp(-k1 * t)
        b = c0 * k1 / (k2 - k1) * (math.exp(-k1 * t) - math.exp(-k2 * t))
        c = c0 - a - b
        data.append({"Время": t, "A": a, "B": b, "C": c})

    # Время максимума промежуточного продукта
    t_max_b = math.log(k2 / k1) / (k2 - k1) if k1 != k2 else 0.0
    b_max = (c0 * k1 / (k2 - k1)
             * (math.exp(-k1 * t_max_b) - math.exp(-k2 * t_max_b)))

    res = table_result(data[:20],
                       label="Последовательные реакции A → B → C",
                       columns=["Время", "A", "B", "C"])
    res.method = "Аналитическое решение для двух последовательных реакций первого порядка"
    res.with_step(f"k₁ = {k1:g} (A → B), k₂ = {k2:g} (B → C)")
    res.with_step(f"Начальная концентрация A: {c0:g} моль/л")
    res.with_step(
        f"Максимум промежуточного продукта B достигается при t = {t_max_b:.6g}, "
        f"[B]макс = {b_max:.6e} моль/л"
    )
    res.with_step(
        f"Это {(b_max / c0) * 100:.2f} % от начальной концентрации A"
    )
    if k2 > k1:
        res.with_step(
            "k₂ > k₁: промежуточный продукт быстро расходуется, "
            "его стационарная концентрация мала"
        )
    else:
        res.with_step(
            "k₁ > k₂: промежуточный продукт накапливается — "
            "он более устойчив, чем исходное вещество"
        )

    res.with_meta("t_max_b", t_max_b)
    res.with_meta("b_max", b_max)
    res.with_meta("series", data)
    res.with_meta("k1", k1)
    res.with_meta("k2", k2)
    return res


def reversible_first_order(k_forward: float, k_reverse: float,
                           c0: float, points: int = 100,
                           t_max: float | None = None) -> Result:
    """Обратимая реакция первого порядка A ⇌ B.

    Равновесные концентрации: [A]∞ = C₀·k₋/(k₊+k₋), [B]∞ = C₀·k₊/(k₊+k₋).
    Эффективная константа: k(набл) = k₊ + k₋.
    """
    if k_forward <= 0 or k_reverse <= 0:
        raise KineticsError("Константы скорости должны быть больше нуля")
    if c0 <= 0:
        raise KineticsError("Начальная концентрация должна быть больше нуля")

    k_obs = k_forward + k_reverse
    a_inf = c0 * k_reverse / k_obs
    b_inf = c0 * k_forward / k_obs
    K_eq = k_forward / k_reverse

    if t_max is None:
        t_max = 5.0 * math.log(2) / k_obs

    data = []
    step = t_max / (points - 1) if points > 1 else 0
    for i in range(points):
        t = i * step
        a = a_inf + (c0 - a_inf) * math.exp(-k_obs * t)
        b = c0 - a
        data.append({"Время": t, "A": a, "B": b})

    res = table_result(data[:20],
                       label="Обратимая реакция первого порядка A ⇌ B",
                       columns=["Время", "A", "B"])
    res.method = "Аналитическое решение для обратимой реакции первого порядка"
    res.with_step(f"k₊ = {k_forward:g}, k₋ = {k_reverse:g}")
    res.with_step(f"Константа равновесия K = k₊/k₋ = {K_eq:.6f}")
    res.with_step(f"Наблюдаемая константа: k = k₊ + k₋ = {k_obs:g}")
    res.with_step(f"Равновесные концентрации: [A] = {a_inf:.6e}, [B] = {b_inf:.6e} моль/л")
    res.with_step(
        f"В равновесии {b_inf / c0 * 100:.2f} % вещества превратилось в B"
    )
    res.with_step(
        f"Время достижения половины пути до равновесия: "
        f"{math.log(2) / k_obs:.6g}"
    )
    res.with_meta("k_observed", k_obs)
    res.with_meta("K", K_eq)
    res.with_meta("a_inf", a_inf)
    res.with_meta("b_inf", b_inf)
    res.with_meta("series", data)
    res.with_assumption(
        "Реакция первого порядка в обоих направлениях, объём постоянен"
    )
    return res


def catalyst_effect(ea_uncatalyzed: float, ea_catalyzed: float,
                    temperature_k: float = 298.15) -> Result:
    """Во сколько раз катализатор ускоряет реакцию.

    Отношение констант k(кат)/k(без кат) = exp((Ea₁ − Ea₂)/(R·T))
    при условии, что предэкспоненциальные множители одинаковы.
    """
    if temperature_k <= 0:
        raise KineticsError("Температура должна быть выше абсолютного нуля")
    if ea_catalyzed > ea_uncatalyzed:
        raise KineticsError(
            "Энергия активации с катализатором выше, чем без него: "
            "это не катализ, проверьте данные"
        )

    ratio = math.exp((ea_uncatalyzed - ea_catalyzed) / (R_GAS * temperature_k))

    res = Result(
        value=ratio,
        label="Ускорение реакции катализатором",
        method="k(кат)/k(без кат) = exp((Ea₁ − Ea₂)/(RT)) при равных A",
    )
    res.with_step(
        f"Снижение энергии активации: {ea_uncatalyzed / 1000:.2f} → "
        f"{ea_catalyzed / 1000:.2f} кДж/моль "
        f"(на {(ea_uncatalyzed - ea_catalyzed) / 1000:.2f} кДж/моль)"
    )
    res.with_step(f"Температура: {temperature_k:.2f} К")
    res.with_step(f"Скорость возрастает в {ratio:.4e} раза")
    res.with_meta("ratio", ratio)

    res.with_assumption(
        "Предэкспоненциальные множители для катализируемой и некатализируемой "
        "реакций приняты одинаковыми. В действительности катализатор меняет "
        "и энтропию активации, поэтому оценка даёт верхнюю границу ускорения."
    )
    return res


def reaction_curve(order: int, k: float, c0: float, t_max: float | None = None,
                   points: int = 100) -> Result:
    """Кривая расходования реагента во времени — для графика."""
    if k <= 0 or c0 <= 0:
        raise KineticsError("Константа скорости и концентрация должны быть больше нуля")

    if t_max is None:
        if order == 0:
            t_max = 1.5 * c0 / k
        elif order == 1:
            t_max = 5.0 * math.log(2) / k
        else:
            t_max = 5.0 / (k * c0)

    data = []
    step = t_max / (points - 1) if points > 1 else 0
    for i in range(points):
        t = i * step
        if order == 0:
            c = max(0.0, c0 - k * t)
        elif order == 1:
            c = c0 * math.exp(-k * t)
        elif order == 2:
            c = c0 / (1.0 + k * c0 * t)
        else:
            raise KineticsError(f"Поддерживаются порядки 0, 1 и 2, получен {order}")

        # Линеаризованная координата для проверки порядка
        if order == 0:
            y = c
        elif order == 1:
            y = math.log(c) if c > 0 else float("-inf")
        else:
            y = 1.0 / c if c > 0 else float("inf")
        data.append((t, c))

    res = series_result(
        data,
        x_label="Время",
        y_label="Концентрация, моль/л",
        label=f"Кинетическая кривая, порядок {order}",
    )
    res.method = f"Интегральный закон скорости порядка {order}"
    res.with_meta("order", order)
    res.with_meta("k", k)
    res.with_meta("c0", c0)
    return res
