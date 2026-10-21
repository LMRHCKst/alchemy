"""Смещение химического равновесия по принципу Ле Шателье.

9 и 11 класс: как изменение температуры, давления и концентрации влияет
на положение равновесия. Направление выводится из уравнения реакции:
считаются моли газов по сторонам и знак теплового эффекта.
"""

from __future__ import annotations

from ..core import formula as F
from ..core.errors import AlchemyError, InputError
from ..core.results import Result, table_result

#: вещества, которые точно газы, если состояние не указано
KNOWN_GASES = {
    "H2", "O2", "N2", "Cl2", "F2", "Br2", "I2", "O3",
    "CO", "CO2", "NO", "NO2", "N2O", "N2O3", "N2O4", "N2O5", "SO2", "SO3",
    "NH3", "HCl", "HBr", "HI", "HF", "H2S", "CH4", "C2H2", "C2H4", "C2H6",
    "PH3", "SiF4", "BF3", "SF6", "Cl2O", "HCN",
}

FACTORS = {
    "temperature": "Температура",
    "pressure": "Давление",
    "concentration": "Концентрация",
}

#: родительный падеж для строк таблицы: «повышение температуры»,
#: а не «повышение температура»
FACTORS_GENITIVE = {
    "temperature": "температуры",
    "pressure": "давления",
    "concentration": "концентрации",
}

#: как человек называет фактор. Английские ключи оставлены для кода,
#: русские — потому что интерфейс русский и в подсказке перечислены они
FACTOR_ALIASES = {
    "temperature": "temperature", "температура": "temperature",
    "температуру": "temperature", "нагрев": "temperature",
    "pressure": "pressure", "давление": "pressure",
    "давлением": "pressure",
    "concentration": "concentration", "концентрация": "concentration",
    "концентрацию": "concentration",
}

#: как человек называет изменение
CHANGE_ALIASES = {
    "increase": "increase", "повышение": "increase", "повысить": "increase",
    "увеличить": "increase", "больше": "increase", "растёт": "increase",
    "decrease": "decrease", "понижение": "decrease", "понизить": "decrease",
    "уменьшить": "decrease", "меньше": "decrease", "падает": "decrease",
}


def _gas_amount(species: str) -> int | None:
    """Молей газа в одном моле вещества: 1 для газа, 0 для конденсированного.

    None означает «не удалось определить».
    """
    body, state = F.split_state(species)

    if state == "g":
        return 1
    if state in ("s", "l"):
        return 0

    if body in KNOWN_GASES:
        return 1

    # Вещества из справочника: смотрим, есть ли полином для газа
    try:
        from ..data import polynomials as POLY

        if POLY.find(body, "g") is not None:
            return 1
        if POLY.find(body, "s") is not None or POLY.find(body, "l") is not None:
            return 0
    except Exception:
        pass

    return None


def _coefficient(term: str) -> tuple[int, str]:
    """Коэффициент и формула из записи вещества."""
    import re

    text = term.strip()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(\D.*)$", text)
    if match:
        return int(round(float(match.group(1)))), match.group(2).strip()
    return 1, text


def gas_moles(equation: str) -> tuple[int | None, int | None]:
    """Молей газа слева и справа."""
    from ..engines import balancer as BAL

    left, right = BAL.parse_equation(equation)

    def total(terms):
        result = 0
        for term in terms:
            coefficient, formula_text = _coefficient(term)
            gas = _gas_amount(formula_text)
            if gas is None:
                return None
            result += coefficient * gas
        return result

    return total(left), total(right)


def equilibrium_shift(equation: str) -> Result:
    """Собрать все правила смещения равновесия для реакции."""
    text = str(equation or "").strip()
    if not text:
        raise InputError("Введите уравнение реакции")

    from ..engines import thermo as TH

    left_gas, right_gas = gas_moles(text)

    # Тепловой эффект: если данных нет, направление по температуре
    # определить нельзя, и это надо честно сказать
    enthalpy = None
    enthalpy_error = ""
    try:
        enthalpy = TH.reaction_enthalpy(text).numeric()
    except AlchemyError as exc:
        enthalpy_error = str(exc)

    rows = []

    # Температура
    if enthalpy is not None:
        if enthalpy > 0:
            hot = "вправо (в сторону продуктов)"
            cold = "влево (в сторону исходных веществ)"
            heat_note = f"реакция эндотермическая, ΔH = {enthalpy:+.1f} кДж/моль"
        else:
            hot = "влево (в сторону исходных веществ)"
            cold = "вправо (в сторону продуктов)"
            heat_note = f"реакция экзотермическая, ΔH = {enthalpy:+.1f} кДж/моль"
        rows.append({"Фактор": "Повышение температуры",
                     "Смещение": hot, "Причина": heat_note})
        rows.append({"Фактор": "Понижение температуры",
                     "Смещение": cold, "Причина": heat_note})
    else:
        heat_note = "тепловой эффект неизвестен"

    # Давление
    if left_gas is not None and right_gas is not None:
        if left_gas == right_gas:
            pressure_note = (f"молей газа одинаково ({left_gas} и {right_gas}), "
                             f"давление не смещает равновесие")
            rows.append({"Фактор": "Давление",
                         "Смещение": "не смещается",
                         "Причина": pressure_note})
        else:
            if left_gas > right_gas:
                increase = "вправо (в сторону продуктов)"
                decrease = "влево (в сторону исходных веществ)"
            else:
                increase = "влево (в сторону исходных веществ)"
                decrease = "вправо (в сторону продуктов)"
            pressure_note = (f"молей газа слева {left_gas}, справа {right_gas}")
            rows.append({"Фактор": "Повышение давления",
                         "Смещение": increase, "Причина": pressure_note})
            rows.append({"Фактор": "Понижение давления",
                         "Смещение": decrease, "Причина": pressure_note})
    else:
        pressure_note = "не удалось определить число молей газа"

    # Концентрация
    rows.append({"Фактор": "Больше исходных веществ",
                 "Смещение": "вправо (в сторону продуктов)",
                 "Причина": "принцип Ле Шателье"})
    rows.append({"Фактор": "Больше продуктов",
                 "Смещение": "влево (в сторону исходных веществ)",
                 "Причина": "принцип Ле Шателье"})

    res = table_result(rows, label="Смещение равновесия",
                       columns=["Фактор", "Смещение", "Причина"])
    res.method = "Принцип Ле Шателье; тепловой эффект по справочным данным"
    res.with_step(f"Уравнение: {text}")
    res.with_step("")
    res.with_step(f"Молей газа: слева {left_gas}, справа {right_gas}")
    res.with_step(f"Тепловой эффект: {heat_note}")

    if enthalpy is None and enthalpy_error:
        res.with_warning(
            "Направление по температуре не определено: "
            + enthalpy_error.split(".")[0])

    if left_gas is None or right_gas is None:
        res.with_warning(
            "Давление: не удалось определить агрегатное состояние всех "
            "веществ. Укажите его явно: CO2(г), CaO(тв).")

    res.with_step("")
    res.with_step("Принцип Ле Шателье: внешнее воздействие смещает "
                  "равновесие так, чтобы ослабить это воздействие.")
    res.with_step("Катализатор на смещение равновесия не влияет: он "
                  "ускоряет и прямую, и обратную реакцию.")

    res.with_meta("left_gas", left_gas)
    res.with_meta("right_gas", right_gas)
    res.with_meta("enthalpy", enthalpy)
    res.with_assumption(
        "Правила смещения применимы к обратимым реакциям в равновесии. "
        "Катализатор на положение равновесия не влияет."
    )
    res.with_source("Принцип Ле Шателье; тепловые эффекты из справочника")
    return res


def shift_single(equation: str, factor: str,
                 change: str = "increase") -> Result:
    """Смещение равновесия по одному фактору."""
    full = equilibrium_shift(equation)

    factor_key = FACTOR_ALIASES.get(factor.strip().lower())
    if factor_key is None:
        raise InputError(
            f"Неизвестный фактор «{factor}». Допустимо: температура, "
            f"давление, концентрация")

    change = CHANGE_ALIASES.get(str(change).strip().lower(), change)
    if change not in ("increase", "decrease"):
        raise InputError(
            f"Неизвестное изменение «{change}». Допустимо: повышение "
            f"или понижение")

    if factor_key == "concentration":
        wanted = ("Больше исходных" if change == "increase"
                  else "Больше продуктов")
    else:
        keyword = "Повышение" if change == "increase" else "Понижение"
        wanted = f"{keyword} {FACTORS_GENITIVE[factor_key]}"

    row = next((item for item in full.value
                if str(item["Фактор"]).lower().startswith(wanted.lower())),
               None)

    if row is None:
        raise AlchemyError(
            f"Для фактора «{factor}» правило неприменимо: не хватает "
            f"данных о реакции (тепловой эффект или агрегатные состояния).")

    res = Result(
        value=row["Смещение"],
        unit="",
        label=f"Смещение равновесия: {row['Фактор'].lower()}",
        method="Принцип Ле Шателье",
    )
    res.with_step(f"Уравнение: {equation}")
    res.with_step(f"Воздействие: {row['Фактор']}")
    res.with_step(f"Причина: {row['Причина']}")
    res.with_step(f"Равновесие смещается: {row['Смещение']}")
    res.with_meta("factor", factor_key)
    res.with_meta("shift", row["Смещение"])
    res.with_source("Принцип Ле Шателье")
    return res
