"""Газовые законы: идеальный газ, Ван-дер-Ваальс, смеси, кинетическая теория.

Отличие от прежней версии: единицы давления и температуры вводятся вместе
со значением и проверяются. Раньше давление в паскалях молча подставлялось
в формулу, где ожидались атмосферы, и ответ уезжал на пять порядков.
"""

from __future__ import annotations

import math
from ..core.constants import (
    MOLAR_VOLUME_STP_L, R, R_ATM, STP_PRESSURE_PA, STP_TEMPERATURE_K,
)
from ..core.errors import InputError
from ..core.formula import molar_mass
from ..core.results import Result, series_result, table_result
from ..core.units import convert, normalize

# Универсальная газовая постоянная в разных единицах
R_VALUES = {
    "Па": (8.314462618, "м³"),      # Дж/(моль·К), объём в м³
    "кПа": (8.314462618, "л"),      # кПа·л/(моль·К)
    "атм": (0.082057366, "л"),
    "бар": (0.083144626, "л"),
    "торр": (62.363577, "л"),
    "мм рт.ст.": (62.363577, "л"),
}


class GasError(InputError):
    """Газовый расчёт невозможен."""


def r_for_pressure(pressure_unit: str) -> tuple[float, str]:
    """Газовая постоянная, согласованная с единицей давления.

    Возвращает (значение R, единица объёма). Это защищает от главной ошибки
    газовых расчётов — подстановки давления не в тех единицах.
    """
    unit = normalize(pressure_unit)
    if unit not in R_VALUES:
        raise GasError(
            f"Единица давления «{pressure_unit}» не поддерживается. "
            f"Допустимые: {', '.join(R_VALUES)}"
        )
    return R_VALUES[unit]


# --------------------------------------------------------------------------
# Идеальный газ
# --------------------------------------------------------------------------


def ideal_gas(pressure: float | None = None, volume: float | None = None,
              moles: float | None = None, temperature: float | None = None,
              pressure_unit: str = "атм", volume_unit: str = "л",
              temperature_unit: str = "К") -> Result:
    """Уравнение состояния идеального газа. Ровно одна величина неизвестна.

    Единицы обязательны: давление переводится в ту, для которой берётся
    газовая постоянная, объём — соответственно.
    """
    params = {"P": pressure, "V": volume, "n": moles, "T": temperature}
    unknown = [k for k, v in params.items() if v is None]
    if len(unknown) != 1:
        raise GasError(
            "Нужно задать ровно три величины из четырёх (P, V, n, T), "
            "четвёртая будет найдена"
        )

    name = unknown[0]

    # Приводим единицы
    if pressure is not None:
        if pressure <= 0:
            raise GasError("Давление должно быть больше нуля")
    if volume is not None and volume <= 0:
        raise GasError("Объём должен быть больше нуля")
    if moles is not None and moles <= 0:
        raise GasError("Количество вещества должно быть больше нуля")

    T_k = None
    if temperature is not None:
        T_k = convert(temperature, temperature_unit, "К")
        if T_k <= 0:
            raise GasError(
                f"Температура {temperature} {temperature_unit} соответствует "
                f"{T_k:.2f} К — это абсолютный нуль или ниже, расчёт невозможен"
            )

    R_val, vol_unit = r_for_pressure(pressure_unit)

    # Объём переводим в единицу, согласованную с R, давление — тоже.
    # Без перевода давления формула молча давала бы неверный результат:
    # 101325 «атм» вместо 101325 Па.
    V_in = None
    if volume is not None:
        V_in = convert(volume, volume_unit, vol_unit)

    P_in = pressure   # давление уже в той же единице, для которой взята R

    steps = []
    if name == "P":
        if V_in is None or moles is None or T_k is None:
            raise GasError("Недостаточно данных для расчёта давления")
        value_in = moles * R_val * T_k / V_in          # в единице R
        value = value_in
        unit = normalize(pressure_unit)
        steps.append(
            f"P = n·R·T/V = {moles:g}·{R_val:g}·{T_k:.2f}/{V_in:g} "
            f"= {value_in:.6g} {unit}"
        )
        target_unit = unit
        P_in = value_in
    elif name == "V":
        if pressure is None or moles is None or T_k is None:
            raise GasError("Недостаточно данных для расчёта объёма")
        value_in = moles * R_val * T_k / P_in
        value = convert(value_in, vol_unit, volume_unit)
        unit = normalize(volume_unit)
        steps.append(
            f"V = n·R·T/P = {moles:g}·{R_val:g}·{T_k:.2f}/{P_in:g} "
            f"= {value_in:.6g} {vol_unit} = {value:.6g} {unit}"
        )
        target_unit = unit
    elif name == "n":
        if pressure is None or V_in is None or T_k is None:
            raise GasError("Недостаточно данных для расчёта количества вещества")
        value = P_in * V_in / (R_val * T_k)
        unit = "моль"
        steps.append(f"n = P·V/(R·T) = {P_in:g}·{V_in:g}/({R_val:g}·{T_k:.2f})")
        target_unit = unit
    else:  # T
        if pressure is None or V_in is None or moles is None:
            raise GasError("Недостаточно данных для расчёта температуры")
        value = P_in * V_in / (moles * R_val)
        unit = "К"
        steps.append(f"T = P·V/(n·R) = {P_in:g}·{V_in:g}/({moles:g}·{R_val:g})")
        target_unit = unit

    res = Result(
        value=value,
        unit=target_unit,
        label=f"Уравнение состояния идеального газа: найдено {name}",
        method="PV = nRT",
    )
    for s in steps:
        res.with_step(s)
    res.with_step(
        f"Газовая постоянная принята R = {R_val:g} для давления в {pressure_unit}"
    )
    res.with_source(R_ATM.pretty())

    if name == "T":
        res.with_meta("temperature_c", value - 273.15)

    # Проверка применимости идеальной модели
    if pressure is not None and normalize(pressure_unit) == "атм" and pressure > 10:
        res.with_warning(
            f"Давление {pressure:g} атм велико: идеальный газ описывает такую "
            f"систему с заметной погрешностью, используйте уравнение "
            f"Ван-дер-Ваальса"
        )
    if T_k is not None and T_k < 50:
        res.with_warning(
            f"Температура {T_k:.1f} К очень низкая: возможна конденсация, "
            f"уравнение идеального газа неприменимо"
        )
    return res


def van_der_waals_constants(name: str) -> tuple[float, float]:
    """Константы Ван-дер-Ваальса для газа, (a в л²·атм/моль², b в л/моль).

    Значения взяты из справочника и приведены для распространённых газов.
    """
    data = _VDW_TABLE.get(str(name).strip())
    if data is None:
        raise GasError(
            f"Нет констант Ван-дер-Ваальса для «{name}». "
            f"Доступны: {', '.join(sorted(_VDW_TABLE))}"
        )
    return data


# a в л²·атм/моль², b в л/моль, Tc в К, Pc в атм
_VDW_TABLE: dict[str, tuple[float, float]] = {
    "He": (0.0346, 0.0238),
    "Ne": (0.2135, 0.0171),
    "Ar": (1.355, 0.0322),
    "Kr": (2.325, 0.0396),
    "Xe": (4.250, 0.0511),
    "H2": (0.2476, 0.0266),
    "N2": (1.370, 0.0387),
    "O2": (1.382, 0.0319),
    "Cl2": (6.579, 0.0562),
    "F2": (1.171, 0.0294),
    "CO": (1.505, 0.0399),
    "CO2": (3.640, 0.0427),
    "SO2": (6.714, 0.0564),
    "NH3": (4.170, 0.0371),
    "NO": (1.358, 0.0279),
    "N2O": (3.832, 0.0443),
    "H2O": (5.536, 0.0305),
    "H2S": (4.484, 0.0434),
    "CH4": (2.253, 0.0428),
    "C2H6": (5.562, 0.0638),
    "C3H8": (9.392, 0.0905),
    "C4H10": (14.66, 0.1226),
    "C2H4": (4.612, 0.0582),
    "C2H2": (4.448, 0.0514),
    "HCl": (3.673, 0.0408),
    "HBr": (4.510, 0.0443),
    "HI": (5.500, 0.0531),
    "CCl4": (20.01, 0.1281),
}

# Критические параметры: Tc в К, Pc в атм
_CRITICAL_TABLE: dict[str, tuple[float, float]] = {
    "He": (5.19, 2.24), "Ne": (44.4, 26.2), "Ar": (150.7, 48.0),
    "Kr": (209.4, 54.3), "Xe": (289.7, 57.6),
    "H2": (33.2, 12.8), "N2": (126.2, 33.5), "O2": (154.6, 49.8),
    "Cl2": (417.0, 76.0), "CO2": (304.1, 72.8), "SO2": (430.8, 77.8),
    "NH3": (405.5, 111.3), "CH4": (190.6, 45.4), "C2H6": (305.4, 48.2),
    "C3H8": (369.8, 41.9), "H2O": (647.1, 217.7), "HCl": (324.7, 81.0),
    "C2H4": (282.4, 49.7), "NO": (180.0, 64.0), "CO": (132.9, 34.5),
}


def van_der_waals(pressure: float | None = None, volume: float | None = None,
                  moles: float | None = None, temperature: float | None = None,
                  gas: str | None = None,
                  a: float | None = None, b: float | None = None) -> Result:
    """Уравнение Ван-дер-Ваальса: (P + n²a/V²)(V − nb) = nRT.

    Единицы: P в атм, V в л, n в моль, T в К — как в справочнике констант.
    """
    if gas is not None:
        a_tab, b_tab = van_der_waals_constants(gas)
        a = a_tab if a is None else a
        b = b_tab if b is None else b
    if a is None or b is None:
        raise GasError(
            "Нужно указать газ (например «CO2») или задать константы a и b вручную"
        )

    params = {"P": pressure, "V": volume, "n": moles, "T": temperature}
    unknown = [k for k, v in params.items() if v is None]
    if len(unknown) != 1:
        raise GasError("Нужно задать ровно три величины из четырёх")

    name = unknown[0]
    R_val = R_ATM.value

    res = Result(
        label=f"Уравнение Ван-дер-Ваальса: найдено {name}",
        method="(P + n²a/V²)·(V − nb) = n·R·T",
    )
    if gas:
        res.with_step(f"Газ: {gas}, a = {a:g} л²·атм/моль², b = {b:g} л/моль")

    if name == "P":
        if volume <= 0 or moles <= 0 or temperature <= 0:
            raise GasError("V, n и T должны быть больше нуля")
        value = moles * R_val * temperature / volume - a * moles ** 2 / volume ** 2
        unit = "атм"
        res.with_step(
            f"P = {moles:g}·{R_val:g}·{temperature:g}/{volume:g} − "
            f"{a:g}·{moles:g}²/{volume:g}² = {value:.6f} атм"
        )
    elif name == "V":
        if pressure <= 0 or moles <= 0 or temperature <= 0:
            raise GasError("P, n и T должны быть больше нуля")
        value = _solve_vdw_volume(pressure, moles, temperature, a, b, R_val)
        unit = "л"
        res.with_step(f"Объём найден численно методом Ньютона: V = {value:.6f} л")
    elif name == "n":
        if pressure <= 0 or volume <= 0 or temperature <= 0:
            raise GasError("P, V и T должны быть больше нуля")
        value = _solve_vdw_moles(pressure, volume, temperature, a, b, R_val)
        unit = "моль"
        res.with_step(f"Количество вещества найдено численно: n = {value:.6f} моль")
    else:
        if pressure <= 0 or volume <= 0 or moles <= 0:
            raise GasError("P, V и n должны быть больше нуля")
        corrected_v = volume - moles * b
        if corrected_v <= 0:
            raise GasError(
                f"Объём {volume:g} л меньше поправки на собственный объём "
                f"молекул ({moles * b:.4f} л). Такое состояние невозможно."
            )
        value = (pressure + a * moles ** 2 / volume ** 2) * corrected_v / (moles * R_val)
        unit = "К"
        res.with_step(
            f"T = (P + a·n²/V²)·(V − n·b)/(n·R) = {value:.6f} К"
        )

    res.value = value
    res.unit = unit

    # Сравнение с идеальной моделью — наглядно показывает роль поправок
    if name == "P":
        ideal = moles * R_val * temperature / volume
        res.with_step(f"Идеальный газ дал бы P = {ideal:.6f} атм, "
                      f"расхождение {abs(value - ideal) / ideal * 100:.2f} %")
        res.with_meta("ideal_pressure", ideal)
    elif name == "V":
        ideal = moles * R_val * temperature / pressure
        res.with_step(f"Идеальный газ дал бы V = {ideal:.6f} л, "
                      f"расхождение {abs(value - ideal) / ideal * 100:.2f} %")
        res.with_meta("ideal_volume", ideal)

    if gas:
        res.with_meta("a", a)
        res.with_meta("b", b)
    return res


def _solve_vdw_volume(P: float, n: float, T: float, a: float, b: float,
                      R_val: float) -> float:
    """Решить кубическое уравнение Ван-дер-Ваальса относительно объёма.

    Метод Ньютона с начальным приближением из идеального газа. Решение
    ограничивается снизу поправкой n·b, иначе корень уходит в нефизическую
    область.
    """
    v_min = n * b * 1.0001
    v = max(n * R_val * T / P, v_min * 1.5)

    for _ in range(200):
        if v <= v_min:
            v = v_min * 1.01
        term = P + a * n ** 2 / v ** 2
        f = term * (v - n * b) - n * R_val * T
        df = term - 2 * a * n ** 2 / v ** 3 * (v - n * b)
        if abs(df) < 1e-15:
            break
        delta = f / df
        v -= delta
        if abs(delta) < 1e-12:
            break

    if v <= n * b:
        raise GasError(
            "Решение уравнения Ван-дер-Ваальса не найдено: при заданных "
            "давлении и температуре газ не существует в виде одной фазы "
            "(возможна конденсация)"
        )
    return v


def _solve_vdw_moles(P: float, V: float, T: float, a: float, b: float,
                     R_val: float) -> float:
    """Решить уравнение Ван-дер-Ваальса относительно количества вещества."""
    n = P * V / (R_val * T)   # начальное приближение
    for _ in range(200):
        if n <= 0:
            n = 1e-6
        term = P + a * n ** 2 / V ** 2
        f = term * (V - n * b) - n * R_val * T
        df = (2 * a * n / V ** 2) * (V - n * b) - term * b - R_val * T
        if abs(df) < 1e-15:
            break
        delta = f / df
        n -= delta
        if abs(delta) < 1e-12:
            break
    if n <= 0:
        raise GasError("Решение дало отрицательное количество вещества")
    return n


# --------------------------------------------------------------------------
# Объединённый газовый закон
# --------------------------------------------------------------------------


def combined_gas_law(p1: float | None = None, v1: float | None = None,
                     t1: float | None = None,
                     p2: float | None = None, v2: float | None = None,
                     t2: float | None = None,
                     temperature_unit: str = "К") -> Result:
    """Объединённый газовый закон P₁V₁/T₁ = P₂V₂/T₂.

    Все давления должны быть в одинаковых единицах, температуры
    переводятся в кельвины автоматически.
    """
    T1 = convert(t1, temperature_unit, "К") if t1 is not None else None
    T2 = convert(t2, temperature_unit, "К") if t2 is not None else None

    params = {"P₁": p1, "V₁": v1, "T₁": T1, "P₂": p2, "V₂": v2, "T₂": T2}
    unknown = [k for k, v in params.items() if v is None]
    if len(unknown) != 1:
        raise GasError("Нужно задать ровно пять величин из шести")

    for k, v in params.items():
        if v is not None and v <= 0:
            raise GasError(f"{k} должна быть больше нуля")

    name = unknown[0]

    if name == "P₁":
        value = p2 * v2 * T1 / (v1 * T2)
    elif name == "V₁":
        value = p2 * v2 * T1 / (p1 * T2)
    elif name == "T₁":
        value = p1 * v1 * T2 / (p2 * v2)
    elif name == "P₂":
        value = p1 * v1 * T2 / (v2 * T1)
    elif name == "V₂":
        value = p1 * v1 * T2 / (p2 * T1)
    else:
        value = p2 * v2 * T1 / (p1 * v1)

    unit = "К" if name.startswith("T") else ("л" if name.startswith("V") else "атм")

    res = Result(
        value=value,
        unit=unit,
        label=f"Объединённый газовый закон: найдено {name}",
        method="P₁V₁/T₁ = P₂V₂/T₂",
    )
    for k, v in params.items():
        marker = " ← найдено" if k == name else ""
        if v is not None:
            res.with_step(f"{k} = {v:g}{marker}")

    if name == "T₁" and T1 is not None:
        res.with_meta("temperature_c", value - 273.15)
    if name == "T₂":
        res.with_meta("temperature_c", value - 273.15)

    res.with_assumption(
        "Количество газа не меняется, газ считается идеальным. "
        "Температуры переведены в кельвины."
    )
    return res


def boyle(p1: float, v1: float,
          p2: float | None = None, v2: float | None = None) -> Result:
    """Изотермический процесс: P₁V₁ = P₂V₂ (закон Бойля — Мариотта)."""
    if p2 is None and v2 is None:
        raise GasError("Нужно задать либо P₂, либо V₂")
    if p2 is not None and v2 is not None:
        raise GasError("Задайте только одну неизвестную величину")

    if v2 is None:
        value = p1 * v1 / p2
        name, unit = "V₂", "л"
    else:
        value = p1 * v1 / v2
        name, unit = "P₂", "атм"

    res = Result(value=value, unit=unit,
                 label=f"Закон Бойля — Мариотта: найдено {name}",
                 method="P₁V₁ = P₂V₂ при T = const")
    res.with_step(f"{p1:g}·{v1:g} = {p1 * v1:.6g}")
    res.with_step(f"{name} = {value:.6g} {unit}")
    res.with_assumption("Процесс изотермический, газ идеальный")
    return res


def charles(v1: float, t1: float, t2: float | None = None,
            v2: float | None = None,
            temperature_unit: str = "К") -> Result:
    """Изобарный процесс: V₁/T₁ = V₂/T₂ (закон Шарля)."""
    T1 = convert(t1, temperature_unit, "К")
    if T1 <= 0:
        raise GasError("Температура должна быть выше абсолютного нуля")

    if (t2 is None) == (v2 is None):
        raise GasError("Задайте ровно одну неизвестную величину")

    if v2 is None:
        T2 = convert(t2, temperature_unit, "К")
        if T2 <= 0:
            raise GasError("Температура должна быть выше абсолютного нуля")
        value = v1 * T2 / T1
        name, unit = "V₂", "л"
    else:
        value = T1 * v2 / v1
        name, unit = "T₂", "К"
        T2 = value

    res = Result(value=value, unit=unit,
                 label=f"Закон Шарля: найдено {name}",
                 method="V₁/T₁ = V₂/T₂ при P = const")
    res.with_step(f"V₁/T₁ = {v1:g}/{T1:.2f} = {v1 / T1:.6e}")
    res.with_step(f"{name} = {value:.6g} {unit}")
    res.with_assumption("Процесс изобарный, газ идеальный")
    return res


def gay_lussac(p1: float, t1: float, t2: float | None = None,
               p2: float | None = None,
               temperature_unit: str = "К") -> Result:
    """Изохорный процесс: P₁/T₁ = P₂/T₂."""
    T1 = convert(t1, temperature_unit, "К")
    if T1 <= 0:
        raise GasError("Температура должна быть выше абсолютного нуля")

    if (t2 is None) == (p2 is None):
        raise GasError("Задайте ровно одну неизвестную величину")

    if p2 is None:
        T2 = convert(t2, temperature_unit, "К")
        value = p1 * T2 / T1
        name, unit = "P₂", "атм"
    else:
        value = T1 * p2 / p1
        name, unit = "T₂", "К"

    res = Result(value=value, unit=unit,
                 label=f"Изохорный процесс: найдено {name}",
                 method="P₁/T₁ = P₂/T₂ при V = const")
    res.with_step(f"P₁/T₁ = {p1:g}/{T1:.2f} = {p1 / T1:.6e}")
    res.with_step(f"{name} = {value:.6g} {unit}")
    res.with_assumption("Процесс изохорный, газ идеальный")
    return res


# --------------------------------------------------------------------------
# Смеси газов
# --------------------------------------------------------------------------


def dalton_law(partial_pressures: dict[str, float] | None = None,
               total_pressure: float | None = None,
               mole_fractions: dict[str, float] | None = None,
               total_moles: float | None = None) -> Result:
    """Закон Дальтона для смеси газов.

    Два режима:
        1) заданы парциальные давления — находится общее;
        2) заданы мольные доли и общее давление — находятся парциальные.
    """
    if partial_pressures:
        total = sum(partial_pressures.values())
        rows = []
        for gas, p in partial_pressures.items():
            rows.append({
                "Газ": gas,
                "Парциальное давление": round(p, 6),
                "Мольная доля": round(p / total, 6) if total else 0,
            })
        res = table_result(rows, label="Парциальные давления компонентов смеси",
                           columns=["Газ", "Парциальное давление", "Мольная доля"])
        res.value = total
        res.kind = "table"
        res.unit = "атм"
        res.method = "Закон Дальтона: P(общ) = Σ Pᵢ"
        res.with_step(f"Общее давление: {total:.6f} атм")
        res.with_meta("total_pressure", total)
        res.with_meta("partial_pressures", partial_pressures)
        return res

    if mole_fractions is not None and total_pressure is not None:
        sum_x = sum(mole_fractions.values())
        if abs(sum_x - 1.0) > 0.01:
            raise GasError(
                f"Сумма мольных долей должна быть равна единице, "
                f"получено {sum_x:.4f}. Проверьте состав смеси."
            )
        rows = []
        for gas, x in mole_fractions.items():
            rows.append({
                "Газ": gas,
                "Мольная доля": round(x, 6),
                "Парциальное давление": round(x * total_pressure, 6),
            })
        res = table_result(rows, label="Парциальные давления по мольным долям",
                           columns=["Газ", "Мольная доля", "Парциальное давление"])
        res.value = total_pressure
        res.kind = "table"
        res.unit = "атм"
        res.method = "Pᵢ = xᵢ·P(общ)"
        res.with_meta("partial_pressures",
                      {g: x * total_pressure for g, x in mole_fractions.items()})
        return res

    raise GasError(
        "Задайте либо парциальные давления, либо мольные доли вместе "
        "с общим давлением"
    )


def dalton_from_masses(masses: dict[str, float],
                       total_pressure: float | None = None,
                       volume_l: float | None = None,
                       temperature_k: float | None = None) -> Result:
    """Парциальные давления по массам компонентов.

    Мольные доли считаются по массам и молярным массам, что избавляет
    от ручного пересчёта.
    """
    if not masses:
        raise GasError("Не задан состав смеси")

    moles = {}
    for gas, m in masses.items():
        if m < 0:
            raise GasError(f"Масса {gas} не может быть отрицательной")
        try:
            M = molar_mass(gas)
        except Exception as exc:
            raise GasError(f"Не удалось определить молярную массу {gas}: {exc}") from exc
        moles[gas] = m / M

    total_moles = sum(moles.values())
    if total_moles <= 0:
        raise GasError("Суммарное количество вещества равно нулю")

    fractions = {g: n / total_moles for g, n in moles.items()}

    average_M = sum(masses.values()) / total_moles

    res = Result(
        value=average_M,
        unit="г/моль",
        label="Средняя молярная масса газовой смеси",
        method="M(ср) = Σm / Σn",
    )
    for gas, n in moles.items():
        res.with_step(
            f"{gas}: m = {masses[gas]:g} г, M = {molar_mass(gas):.4f} г/моль, "
            f"n = {n:.6f} моль, x = {fractions[gas]:.6f}"
        )
    res.with_step(f"Суммарно {total_moles:.6f} моль, средняя M = {average_M:.4f} г/моль")
    res.with_meta("moles", moles)
    res.with_meta("mole_fractions", fractions)

    if total_pressure is not None:
        partials = {g: x * total_pressure for g, x in fractions.items()}
        res.with_meta("partial_pressures", partials)
        for gas, p in partials.items():
            res.with_step(f"P({gas}) = {fractions[gas]:.6f}·{total_pressure:g} = {p:.6f} атм")

    if volume_l is not None and temperature_k is not None:
        if volume_l <= 0 or temperature_k <= 0:
            raise GasError("Объём и температура должны быть больше нуля")
        p_total = total_moles * R_ATM.value * temperature_k / volume_l
        res.with_step(
            f"Из уравнения состояния: P(общ) = {total_moles:.6f}·{R_ATM.value:g}·"
            f"{temperature_k:g}/{volume_l:g} = {p_total:.6f} атм"
        )
        res.with_meta("computed_total_pressure", p_total)

    res.with_assumption(
        "Газы не взаимодействуют химически, смесь идеальная. "
        "Для реальных смесей при высоком давлении нужны коэффициенты фугитивности."
    )
    return res


# --------------------------------------------------------------------------
# Плотность и молярная масса газа
# --------------------------------------------------------------------------


def gas_density(pressure: float, temperature_k: float, gas: str | None = None,
                molar_mass_value: float | None = None,
                real: bool = False) -> Result:
    """Плотность газа. d = P·M/(R·T).

    Args:
        pressure: давление, атм.
        temperature_k: температура, К.
        gas: формула газа, чтобы взять молярную массу из справочника.
        molar_mass_value: молярная масса, если газ не указан формулой.
        real: учитывать ли поправки Ван-дер-Ваальса.
    """
    if pressure <= 0 or temperature_k <= 0:
        raise GasError("Давление и температура должны быть больше нуля")

    if molar_mass_value is None:
        if gas is None:
            raise GasError("Укажите газ или его молярную массу")
        molar_mass_value = molar_mass(gas)

    R_val = R_ATM.value
    density = pressure * molar_mass_value / (R_val * temperature_k)

    res = Result(
        value=density,
        unit="г/л",
        label=f"Плотность газа{' ' + gas if gas else ''}",
        method="d = P·M/(R·T)",
    )
    res.with_step(f"M = {molar_mass_value:.4f} г/моль")
    res.with_step(
        f"d = {pressure:g}·{molar_mass_value:.4f}/({R_val:g}·{temperature_k:g}) "
        f"= {density:.6f} г/л"
    )

    if real and gas is not None:
        try:
            a, b = van_der_waals_constants(gas)
        except GasError:
            res.with_warning(
                f"Константы Ван-дер-Ваальса для {gas} неизвестны, "
                f"поправка не применена"
            )
        else:
            # Из уравнения Ван-дер-Ваальса: V/n находится численно, d = M/V·n
            try:
                v_molar = _solve_vdw_volume(pressure, 1.0, temperature_k, a, b, R_val)
                density_real = molar_mass_value / v_molar
                res.with_step(
                    f"С поправками Ван-дер-Ваальса: V(моль) = {v_molar:.6f} л, "
                    f"d = {density_real:.6f} г/л"
                )
                res.with_meta("density_ideal", density)
                res.with_meta("density_real", density_real)
                res.with_meta("z_factor", pressure * v_molar / (R_val * temperature_k))
                res.value = density_real
            except GasError as exc:
                res.with_warning(f"Поправка Ван-дер-Ваальса не применена: {exc}")

    res.with_meta("density_gl", res.numeric())
    res.with_meta("density_gl_stp", molar_mass_value / MOLAR_VOLUME_STP_L)
    res.with_step(
        f"При нормальных условиях (273.15 К, 101.325 кПа) плотность была бы "
        f"{molar_mass_value / MOLAR_VOLUME_STP_L:.6f} г/л"
    )
    return res


def molar_mass_from_density(density_gl: float, pressure: float,
                            temperature_k: float) -> Result:
    """Молярная масса газа по плотности. M = d·R·T/P."""
    if density_gl <= 0 or pressure <= 0 or temperature_k <= 0:
        raise GasError("Все величины должны быть больше нуля")

    M = density_gl * R_ATM.value * temperature_k / pressure

    res = Result(
        value=M,
        unit="г/моль",
        label="Молярная масса газа по плотности",
        method="M = d·R·T/P",
    )
    res.with_step(
        f"M = {density_gl:g}·{R_ATM.value:g}·{temperature_k:g}/{pressure:g} "
        f"= {M:.4f} г/моль"
    )
    res.with_assumption(
        "Газ идеальный. Для реальных газов при высоком давлении результат "
        "занижен, нужна поправка на сжимаемость."
    )
    return res


def relative_density(gas: str, reference: str = "воздух") -> Result:
    """Относительная плотность газа по другому газу или по воздуху."""
    M_gas = molar_mass(gas)
    if reference.lower() in ("воздух", "air"):
        M_ref = 28.96
        ref_name = "воздух (средняя M = 28.96 г/моль)"
    else:
        M_ref = molar_mass(reference)
        ref_name = reference

    value = M_gas / M_ref

    res = Result(
        value=value,
        label=f"Относительная плотность {gas} по {ref_name}",
        method="D = M(газ)/M(эталон)",
    )
    res.with_step(f"M({gas}) = {M_gas:.4f} г/моль")
    res.with_step(f"M(эталон) = {M_ref:.4f} г/моль")
    res.with_step(f"D = {value:.6f}")
    return res


# --------------------------------------------------------------------------
# Молекулярно-кинетическая теория
# --------------------------------------------------------------------------


def molecular_speeds(temperature_k: float, gas: str) -> Result:
    """Характеристические скорости молекул газа.

    v(ср.кв) = √(3RT/M), v(ср) = √(8RT/πM), v(наив) = √(2RT/M).
    """
    if temperature_k <= 0:
        raise GasError("Температура должна быть больше нуля")

    M_kg = molar_mass(gas) / 1000.0
    R_val = R.value

    v_rms = math.sqrt(3 * R_val * temperature_k / M_kg)
    v_mean = math.sqrt(8 * R_val * temperature_k / (math.pi * M_kg))
    v_probable = math.sqrt(2 * R_val * temperature_k / M_kg)

    res = Result(
        value=v_rms,
        unit="м/с",
        label=f"Среднеквадратичная скорость молекул {gas}",
        method="v = √(3RT/M)",
    )
    res.with_step(f"M({gas}) = {M_kg * 1000:.4f} г/моль = {M_kg:.6f} кг/моль")
    res.with_step(f"v(ср.кв) = √(3·{R_val:g}·{temperature_k:g}/{M_kg:.6f}) = {v_rms:.2f} м/с")
    res.with_step(f"v(средняя) = √(8RT/πM) = {v_mean:.2f} м/с")
    res.with_step(f"v(наиболее вероятная) = √(2RT/M) = {v_probable:.2f} м/с")
    res.with_meta("v_rms", v_rms)
    res.with_meta("v_mean", v_mean)
    res.with_meta("v_most_probable", v_probable)

    # Средняя кинетическая энергия одной молекулы
    from ..core.constants import K_B
    e_kin = 1.5 * K_B.value * temperature_k
    res.with_step(
        f"Средняя кинетическая энергия молекулы: <E> = 3/2·k·T = "
        f"{e_kin:.6e} Дж"
    )
    res.with_meta("mean_kinetic_energy_j", e_kin)
    return res


def grahams_law(gas1: str, gas2: str, rate1: float | None = None,
                rate2: float | None = None) -> Result:
    """Закон Грэма: скорости эффузии обратно пропорциональны √M.

    Задаётся одна из скоростей, находится вторая. Если не задана ни одна,
    вычисляется отношение скоростей.
    """
    M1 = molar_mass(gas1)
    M2 = molar_mass(gas2)
    ratio = math.sqrt(M2 / M1)

    if rate1 is None and rate2 is None:
        res = Result(
            value=ratio,
            label=f"Отношение скоростей эффузии {gas1} : {gas2}",
            method="v₁/v₂ = √(M₂/M₁)",
        )
        res.with_step(f"M({gas1}) = {M1:.4f}, M({gas2}) = {M2:.4f} г/моль")
        res.with_step(f"v({gas1})/v({gas2}) = √({M2:.4f}/{M1:.4f}) = {ratio:.6f}")
        res.with_step(
            f"{gas1} эффундирует в {ratio:.3f} раза "
            f"{'быстрее' if ratio > 1 else 'медленнее'}, чем {gas2}"
        )
        return res

    if rate1 is not None:
        value = rate1 / ratio
        name = f"скорость {gas2}"
    else:
        value = rate2 * ratio
        name = f"скорость {gas1}"

    res = Result(value=value, unit="(та же единица, что и известная скорость)",
                 label=f"Найдена {name} по закону Грэма",
                 method="v₁/v₂ = √(M₂/M₁)")
    res.with_step(f"Отношение скоростей: {ratio:.6f}")
    res.with_step(f"{name} = {value:.6f}")
    return res


def effusion_time(gas: str, reference_gas: str, reference_time: float) -> Result:
    """Время эффузии газа по известному времени для другого газа."""
    if reference_time <= 0:
        raise GasError("Время должно быть больше нуля")

    M = molar_mass(gas)
    M_ref = molar_mass(reference_gas)
    factor = math.sqrt(M / M_ref)
    time = reference_time * factor

    res = Result(
        value=time,
        unit="(та же единица, что и известное время)",
        label=f"Время эффузии {gas}",
        method="t/t₀ = √(M/M₀)",
    )
    res.with_step(f"M({gas}) = {M:.4f}, M({reference_gas}) = {M_ref:.4f} г/моль")
    res.with_step(f"t = {reference_time:g}·√({M:.4f}/{M_ref:.4f}) = {time:.6f}")
    return res


def maxwell_boltzmann(temperature_k: float, gas: str,
                      points: int = 200) -> Result:
    """Распределение Максвелла по скоростям — для построения графика.

    f(v) = 4π·(M/(2πRT))^{3/2}·v²·exp(−Mv²/(2RT))
    """
    if temperature_k <= 0:
        raise GasError("Температура должна быть больше нуля")

    M_kg = molar_mass(gas) / 1000.0
    R_val = R.value

    v_rms = math.sqrt(3 * R_val * temperature_k / M_kg)
    v_max = v_rms * 3.0

    coeff = 4 * math.pi * (M_kg / (2 * math.pi * R_val * temperature_k)) ** 1.5

    data = []
    for i in range(points):
        v = v_max * i / (points - 1)
        f = coeff * v ** 2 * math.exp(-M_kg * v ** 2 / (2 * R_val * temperature_k))
        data.append((v, f))

    res = series_result(
        data,
        x_label="Скорость, м/с",
        y_label="Плотность вероятности",
        label=f"Распределение Максвелла для {gas} при {temperature_k:g} К",
    )
    res.method = "f(v) = 4π(M/2πRT)^{3/2}·v²·exp(−Mv²/2RT)"
    res.with_meta("v_rms", v_rms)
    return res


# --------------------------------------------------------------------------
# Реальные газы: сжимаемость и критические явления
# --------------------------------------------------------------------------


def compressibility_factor(pressure: float, temperature_k: float,
                           gas: str) -> Result:
    """Коэффициент сжимаемости Z = PV/(nRT).

    Z = 1 для идеального газа. Отклонение показывает, насколько реальный
    газ отличается от идеального.
    """
    if pressure <= 0 or temperature_k <= 0:
        raise GasError("Давление и температура должны быть больше нуля")

    a, b = van_der_waals_constants(gas)
    R_val = R_ATM.value
    v_molar = _solve_vdw_volume(pressure, 1.0, temperature_k, a, b, R_val)
    Z = pressure * v_molar / (R_val * temperature_k)

    res = Result(
        value=Z,
        label=f"Коэффициент сжимаемости {gas}",
        method="Z = P·V(моль)/(R·T) по уравнению Ван-дер-Ваальса",
    )
    res.with_step(f"Молярный объём реального газа: {v_molar:.6f} л")
    res.with_step(f"Идеальный газ дал бы: {R_val * temperature_k / pressure:.6f} л")
    res.with_step(f"Z = {Z:.6f}")

    interpretation = ("силы притяжения преобладают, газ сжимается сильнее идеального"
                       if Z < 1 else
                       "силы отталкивания преобладают, газ сжимается хуже идеального")
    res.with_step(f"Z {'<' if Z < 1 else '>'} 1: {interpretation}")
    res.with_meta("molar_volume", v_molar)

    critical = _CRITICAL_TABLE.get(gas)
    if critical:
        Tc, Pc = critical
        res.with_step(f"Критические параметры {gas}: Tк = {Tc:g} К, Pк = {Pc:g} атм")
        res.with_step(f"Приведённые параметры: T/Tк = {temperature_k / Tc:.3f}, "
                      f"P/Pк = {pressure / Pc:.3f}")
        if temperature_k < Tc:
            res.with_warning(
                f"Температура ниже критической ({Tc:g} К): при достаточном "
                f"давлении возможна конденсация, уравнение состояния "
                f"одной фазы не описывает систему"
            )
            res.with_meta("below_critical", True)
    return res


def critical_parameters(gas: str) -> Result:
    """Критические параметры газа и оценка по Ван-дер-Ваальсу."""
    critical = _CRITICAL_TABLE.get(gas)
    if critical is None:
        raise GasError(
            f"Нет критических параметров для «{gas}». "
            f"Доступны: {', '.join(sorted(_CRITICAL_TABLE))}"
        )

    Tc, Pc = critical
    a, b = van_der_waals_constants(gas)
    R_val = R_ATM.value

    Tc_calc = 8 * a / (27 * R_val * b)
    Pc_calc = a / (27 * b ** 2)
    Vc_calc = 3 * b
    Zc_calc = Pc_calc * Vc_calc / (R_val * Tc_calc)

    res = Result(
        value=Tc,
        unit="К",
        label=f"Критическая температура {gas}",
        method="Справочные данные (CRC Handbook)",
    )
    res.with_step(f"Tк = {Tc:g} К = {Tc - 273.15:.1f} °C")
    res.with_step(f"Pк = {Pc:g} атм = {Pc * 101.325:.1f} кПа")
    res.with_step("")
    res.with_step("Оценка по Ван-дер-Ваальсу из констант a и b:")
    res.with_step(f"  Tк = 8a/(27Rb) = {Tc_calc:.2f} К "
                  f"(справочное {Tc:g} К, расхождение {abs(Tc_calc - Tc) / Tc * 100:.1f} %)")
    res.with_step(f"  Pк = a/(27b²) = {Pc_calc:.2f} атм "
                  f"(справочное {Pc:g} атм, расхождение {abs(Pc_calc - Pc) / Pc * 100:.1f} %)")
    res.with_step(f"  Vк = 3b = {Vc_calc:.5f} л/моль")
    res.with_step(f"  Zк = {Zc_calc:.4f} (у идеального газа было бы 1)")
    res.with_meta("Tc", Tc)
    res.with_meta("Pc", Pc)
    res.with_meta("Tc_calculated", Tc_calc)
    res.with_meta("Pc_calculated", Pc_calc)
    res.with_meta("Zc", Zc_calc)
    res.with_assumption(
        "Уравнение Ван-дер-Ваальса даёт Zк = 0.375 для всех веществ, тогда как "
        "реальные значения лежат в пределах 0.23–0.31. Расхождение — "
        "принципиальное ограничение модели."
    )
    return res


def mean_free_path(pressure: float, temperature_k: float, gas: str,
                   diameter_nm: float = 0.36) -> Result:
    """Средняя длина свободного пробега: λ = kT/(√2·π·d²·P)."""
    if pressure <= 0 or temperature_k <= 0:
        raise GasError("Давление и температура должны быть больше нуля")
    if diameter_nm <= 0:
        raise GasError("Диаметр молекулы должен быть больше нуля")

    from ..core.constants import K_B
    d = diameter_nm * 1e-9
    P_pa = pressure * 101325.0
    lam = K_B.value * temperature_k / (math.sqrt(2) * math.pi * d ** 2 * P_pa)

    res = Result(
        value=lam,
        unit="м",
        label=f"Средняя длина свободного пробега {gas}",
        method="λ = k·T/(√2·π·d²·P)",
    )
    res.with_step(f"Диаметр молекулы: {diameter_nm:g} нм")
    res.with_step(f"Давление: {pressure:g} атм = {P_pa:.4g} Па")
    res.with_step(f"λ = {lam:.6e} м = {lam * 1e9:.2f} нм")
    res.with_meta("mean_free_path_nm", lam * 1e9)
    res.with_assumption(
        "Молекулы считаются твёрдыми сферами заданного диаметра. "
        "Для реальных газов диаметр зависит от температуры."
    )
    return res


def gas_stoichiometry(equation: str, given_gas: str, given_volume_l: float,
                      temperature_k: float = 273.15,
                      pressure: float = 1.0,
                      target_gas: str | None = None) -> Result:
    """Объём газа, получающегося или расходуемого в реакции.

    Объёмы газов при одинаковых условиях относятся как их мольные количества,
    поэтому для газовой реакции достаточно стехиометрии.
    """
    from .balancer import balance

    if given_volume_l <= 0:
        raise GasError("Объём должен быть больше нуля")
    if temperature_k <= 0 or pressure <= 0:
        raise GasError("Температура и давление должны быть больше нуля")

    bal = balance(equation)
    coeffs: dict[str, int] = bal.meta["coefficients"]

    def canonical(text: str) -> str:
        from ..core.formula import split_state
        body, _ = split_state(text)
        return body.replace(" ", "")

    given_key = None
    for text in coeffs:
        if canonical(text) == canonical(given_gas):
            given_key = text
            break
    if given_key is None:
        raise GasError(f"Вещества «{given_gas}» нет в уравнении {bal.value}")

    n_given = pressure * given_volume_l / (R_ATM.value * temperature_k)

    res = Result(
        label="Стехиометрия газовой реакции",
        method="По коэффициентам уравнения и уравнению состояния",
    )
    res.with_step(f"Уравнение: {bal.value}")
    res.with_step(
        f"Дано {given_volume_l:g} л {given_key} при {temperature_k:g} К и "
        f"{pressure:g} атм: n = {n_given:.6f} моль"
    )

    if target_gas is None:
        rows = []
        for text, c in coeffs.items():
            n = n_given * c / coeffs[given_key]
            v = n * R_ATM.value * temperature_k / pressure
            rows.append({
                "Вещество": text,
                "Коэффициент": c,
                "Количество, моль": round(n, 6),
                "Объём, л": round(v, 6) if _is_gas(text) else "—",
            })
        table = table_result(rows, label="Расчёт по уравнению реакции",
                             columns=["Вещество", "Коэффициент",
                                      "Количество, моль", "Объём, л"])
        table.method = res.method
        table.steps = res.steps
        table.meta["equation"] = bal.value
        table.meta["moles_given"] = n_given
        return table

    target_key = None
    for text in coeffs:
        if canonical(text) == canonical(target_gas):
            target_key = text
            break
    if target_key is None:
        raise GasError(f"Вещества «{target_gas}» нет в уравнении {bal.value}")

    n_target = n_given * coeffs[target_key] / coeffs[given_key]
    v_target = n_target * R_ATM.value * temperature_k / pressure

    res.value = v_target
    res.unit = "л"
    res.label = f"Объём {target_key} по реакции"
    res.with_step(
        f"n({target_key}) = {n_given:.6f}·{coeffs[target_key]}/{coeffs[given_key]} "
        f"= {n_target:.6f} моль"
    )
    res.with_step(f"V({target_key}) = {v_target:.6f} л")
    res.with_meta("moles", n_target)
    res.with_meta("equation", bal.value)

    res.with_assumption(
        "Вещества взяты в стехиометрическом соотношении, реакция идёт до конца, "
        "газы идеальные"
    )
    return res


def _is_gas(species: str) -> bool:
    """Считать ли вещество газом по записи состояния."""
    from ..core.formula import split_state
    _, state = split_state(species)
    if state is not None:
        return state == "g"
    # Состояние не указано: для простых газов считаем газом
    body = species.split("(")[0].replace(" ", "")
    return body in ("H2", "O2", "N2", "Cl2", "F2", "CO", "CO2", "SO2",
                    "NH3", "NO", "NO2", "CH4", "C2H6", "C3H8", "H2S",
                    "HCl", "HBr", "HI", "He", "Ne", "Ar", "Kr", "Xe")
