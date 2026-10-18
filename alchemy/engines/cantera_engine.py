"""Расчёты на Cantera: газовые смеси, равновесие, горение, кинетика.

Этот движок — отдельный режим, а не часть основной расчётной цепочки.
Cantera решает задачи, которых в основном наборе нет: равновесие газовой
смеси при заданных T и P, адиабатическая температура горения, свойства
газа при высокой температуре, кинетика в реакторе идеального смешения.

Библиотека необязательная: если Cantera не установлена, остальная программа
работает как обычно, а этот модуль сообщает об этом понятным сообщением.

Механизмы берутся из комплекта Cantera: gri30 (природный газ, 53 вида,
325 реакций), h2o2 (водород), air, KOH и другие.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import DataNotFoundError, InputError
from ..core.constants import R as R_GAS
from ..core.results import Result, series_result, table_result

# Механизмы, которые имеет смысл показывать пользователю: остальные в
# комплекте — учебные примеры для конкретных задач (плазма, топливные
# элементы), они путают выбор.
USEFUL_MECHANISMS = {
    "gri30.yaml": "Природный газ: 53 вида, 325 реакций",
    "h2o2.yaml": "Водород и кислород",
    "air.yaml": "Воздух",
    "nDodecane_Reitz.yaml": "Додекан (дизельное топливо)",
    "liquidvapor.yaml": "Вода и пар",
    "graphite.yaml": "Углерод",
}

#: давление в 1 атмосфере, Па
ONE_ATM = 101325.0


class CanteraError(InputError):
    """Расчёт на Cantera невозможен."""


def _cantera():
    """Ленивый импорт Cantera с понятным сообщением об отсутствии."""
    try:
        import cantera as ct
    except ImportError as exc:  # pragma: no cover
        raise CanteraError(
            "Для этого режима нужна библиотека Cantera. Установите её:\n"
            "    python -m pip install cantera"
        ) from exc
    return ct


def available() -> bool:
    """Установлена ли Cantera."""
    try:
        import cantera  # noqa: F401
    except ImportError:
        return False
    return True


def version() -> str:
    """Версия Cantera или пустая строка."""
    try:
        import cantera
    except ImportError:
        return ""
    return cantera.__version__


def list_mechanisms() -> list[dict]:
    """Доступные механизмы с кратким описанием."""
    _cantera()
    rows = []
    for name, description in USEFUL_MECHANISMS.items():
        rows.append({"Механизм": name, "Что описывает": description})
    return rows


def _make_gas(mechanism: str, temperature: float, pressure: float,
              composition: str):
    """Создать газовую смесь с проверкой входных данных."""
    ct = _cantera()
    if not mechanism:
        raise CanteraError("Не выбран механизм")
    if temperature <= 0:
        raise InputError("Температура должна быть больше нуля")
    if pressure <= 0:
        raise InputError("Давление должно быть больше нуля")
    text = str(composition or "").strip()
    if not text:
        raise InputError(
            "Не задан состав смеси. Пишите в виде «CH4:1, O2:2, N2:7.52» — "
            "вещество и количество через двоеточие"
        )

    # Атмосферы и бар приводим к паскалям — Cantera работает в СИ
    try:
        gas = ct.Solution(mechanism)
    except Exception as exc:
        raise DataNotFoundError(
            f"Механизм «{mechanism}» не найден среди данных Cantera"
        ) from exc

    try:
        gas.TPX = temperature, pressure, text
    except Exception as exc:
        raise InputError(
            f"Не удалось разобрать состав «{text}». Проверьте названия "
            f"веществ: они должны быть из выбранного механизма. "
            f"Ошибка Cantera: {exc}"
        ) from exc

    return gas


def _row(name: str, value, unit: str) -> dict:
    if isinstance(value, float):
        if abs(value) >= 1e4 or (value != 0 and abs(value) < 1e-3):
            text = f"{value:.4e}"
        else:
            text = f"{value:.4f}"
    else:
        text = str(value)
    return {"Величина": name, "Значение": text, "Единица": unit}


def gas_properties(mechanism: str, temperature: float, pressure: float,
                   composition: str) -> Result:
    """Свойства газовой смеси при заданных температуре и давлении.

    Args:
        mechanism: имя механизма, например «gri30.yaml».
        temperature: температура, К.
        pressure: давление, Па.
        composition: состав, например «CH4:1, O2:2, N2:7.52».
    """
    gas = _make_gas(mechanism, temperature, pressure, composition)

    mean_molar_mass = gas.mean_molecular_weight / 1000.0      # кг/моль
    rows = [
        _row("Температура", temperature, "К"),
        _row("Давление", pressure, "Па"),
        _row("Средняя молярная масса", mean_molar_mass * 1000, "г/моль"),
        _row("Плотность", gas.density, "кг/м³"),
        _row("Удельный объём", 1.0 / gas.density if gas.density else 0.0, "м³/кг"),
        _row("Теплоёмкость cp", gas.cp_mass, "Дж/(кг·К)"),
        _row("Теплоёмкость cv", gas.cv_mass, "Дж/(кг·К)"),
        _row("Показатель адиабаты", gas.cp_mass / gas.cv_mass, ""),
        _row("Удельная энтальпия", gas.enthalpy_mass / 1000, "кДж/кг"),
        _row("Удельная энтропия", gas.entropy_mass / 1000, "кДж/(кг·К)"),
        _row("Вязкость", gas.viscosity, "Па·с"),
        _row("Теплопроводность", gas.thermal_conductivity, "Вт/(м·К)"),
        _row("Число Прандтля", gas.viscosity * gas.cp_mass
             / gas.thermal_conductivity, ""),
    ]

    res = table_result(rows, label="Свойства газовой смеси",
                       columns=["Величина", "Значение", "Единица"])
    res.method = f"Cantera {version()}, механизм {mechanism}"
    res.with_step(f"Механизм: {mechanism} "
                  f"({gas.n_species} видов, {gas.n_reactions} реакций)")
    res.with_step(f"Состав: {composition}")
    res.with_step(f"T = {temperature:g} К, P = {pressure:g} Па")
    res.with_source("Cantera: механизмы и данные из комплекта библиотеки")

    # Мольная теплоёмкость полезна для сверки с ручным расчётом
    cp_molar = gas.cp_mass * mean_molar_mass
    res.with_step(f"Мольная теплоёмкость cp = {cp_molar:.2f} Дж/(моль·К)")
    res.with_meta("mean_molar_mass", mean_molar_mass)
    res.with_meta("cp_molar", cp_molar)
    res.with_assumption(
        "Свойства рассчитаны по уравнению состояния идеального газа с "
        "поправками механизма. Для плотных газов при высоком давлении "
        "результат приближённый."
    )
    return res


def equilibrium(mechanism: str, temperature: float, pressure: float,
                composition: str, mode: str = "TP") -> Result:
    """Равновесный состав газовой смеси.

    Args:
        mode: «TP» — заданы температура и давление (изотермическое
            равновесие); «HP» — заданы энтальпия и давление (адиабатическое
            горение, температура подбирается).
    """
    ct = _cantera()
    gas = _make_gas(mechanism, temperature, pressure, composition)

    initial_temperature = float(gas.T)

    try:
        if mode == "HP":
            gas.equilibrate("HP")
        else:
            gas.equilibrate("TP")
    except Exception as exc:
        raise CanteraError(f"Не удалось найти равновесие: {exc}") from exc

    rows = []
    for name, fraction in zip(gas.species_names, gas.X):
        if fraction < 1e-6:
            continue
        rows.append({
            "Вещество": name,
            "Мольная доля, %": f"{fraction * 100:.4f}",
            "Масса, %": f"{(fraction * gas.molecular_weights[gas.species_index(name)] / gas.mean_molecular_weight) * 100:.4f}",
        })

    rows.sort(key=lambda row: -float(row["Мольная доля, %"]))

    label = ("Равновесие при постоянных энтальпии и давлении"
             if mode == "HP"
             else "Равновесие при постоянных температуре и давлении")
    res = table_result(rows, label=label,
                       columns=["Вещество", "Мольная доля, %", "Масса, %"])
    res.method = f"Минимизация энергии Гиббса, Cantera {version()}"
    res.with_step(f"Механизм: {mechanism}")
    res.with_step(f"Исходный состав: {composition}")
    res.with_step(f"Исходная температура: {initial_temperature:.1f} К")
    res.with_step(f"Температура после равновесия: {gas.T:.1f} К")
    res.with_step(f"Давление: {gas.P:g} Па")
    res.with_step(f"Веществ в равновесной смеси: {len(rows)}")
    res.with_source("Cantera: минимизация энергии Гиббса по механизму")
    res.with_meta("equilibrium_temperature", float(gas.T))
    res.with_meta("equilibrium_pressure", float(gas.P))

    if mode == "HP" and abs(gas.T - initial_temperature) > 1:
        res.with_step(
            f"Температура изменилась на {gas.T - initial_temperature:+.1f} К "
            f"за счёт выделившегося тепла"
        )

    res.with_assumption(
        "Равновесие считается по газовой фазе. Твёрдые продукты "
        "(сажа, зола) не учитываются: механизм описывает только газы."
    )
    return res


def adiabatic_temperature(mechanism: str, temperature: float, pressure: float,
                          composition: str) -> Result:
    """Адиабатическая температура горения смеси.

    Смесь сжигается при постоянных энтальпии и давлении; температура
    подбирается так, чтобы энтальпия сохранилась.
    """
    gas = _make_gas(mechanism, temperature, pressure, composition)
    initial = float(gas.T)

    try:
        gas.equilibrate("HP")
    except Exception as exc:
        raise CanteraError(f"Не удалось найти адиабатическую температуру: {exc}") from exc

    rise = gas.T - initial
    res = Result(
        value=float(gas.T),
        unit="К",
        label="Адиабатическая температура горения",
        method=f"Постоянные энтальпия и давление, Cantera {version()}",
    )
    res.with_step(f"Механизм: {mechanism}")
    res.with_step(f"Состав: {composition}")
    res.with_step(f"Начальная температура: {initial:.1f} К")
    res.with_step(f"Давление: {pressure:g} Па")
    res.with_step(f"Температура после сгорания: {gas.T:.1f} К")
    res.with_step(f"Подъём температуры: {rise:+.1f} К")
    res.with_source("Cantera: адиабатическое равновесие")

    res.with_assumption(
        "Горение полное, до равновесия. Теплопотери отсутствуют, "
        "поэтому реальная температура всегда ниже."
    )
    if rise < 1:
        res.with_warning(
            "Температура почти не изменилась: смесь либо негорючая, либо "
            "уже при начальной температуре находится в равновесии"
        )
    return res


def reactor_kinetics(mechanism: str, temperature: float, pressure: float,
                     composition: str, time_end: float,
                     points: int = 60) -> Result:
    """Изменение состава и температуры во времени в реакторе.

    Реактор идеального смешения при постоянном объёме: смесь
    воспламеняется, температура растёт, исходные вещества расходуются.
    """
    _cantera()
    ct = _cantera()
    if time_end <= 0:
        raise InputError("Время расчёта должно быть больше нуля")
    points = max(2, min(500, int(points)))

    gas = _make_gas(mechanism, temperature, pressure, composition)

    # Исходные мольные доли: по ним потом видно, что именно выгорело
    initial_fractions = list(gas.X)

    reactor = ct.IdealGasReactor(gas, clone=False)
    network = ct.ReactorNet([reactor])

    times: list[float] = []
    temperatures: list[float] = []
    shares: list[float] = []

    try:
        for step in range(points + 1):
            target = time_end * step / points
            if step > 0:
                network.advance(target)
            # Время ведёт сеть реакторов, у самого реактора такого поля нет
            times.append(float(network.time))
            temperatures.append(float(reactor.T))
            shares.append(0.0)
    except Exception as exc:
        raise CanteraError(
            f"Реактор не сошёлся: {exc}. Попробуйте другое время или состав"
        ) from exc

    # Основное вещество — то, чья доля упала сильнее всего.
    # Азот и прочие разбавители почти не меняются, поэтому в выбор не попадают.
    final_fractions = list(reactor.phase.X)
    changes = [initial_fractions[i] - final_fractions[i]
               for i in range(len(initial_fractions))]
    main_index = max(range(len(changes)), key=lambda i: changes[i])
    main_name = gas.species_names[main_index]

    if changes[main_index] <= 1e-9:
        # Ничего не выгорело — тогда просто самое заметное по доле
        main_index = max(range(len(initial_fractions)),
                         key=lambda i: initial_fractions[i])
        main_name = gas.species_names[main_index]

    res = series_result(
        list(zip(times, temperatures)),
        x_label="Время, с",
        y_label="Температура, К",
        label="Температура в реакторе во времени",
    )
    res.method = f"Реактор идеального смешения, Cantera {version()}"
    res.with_step(f"Механизм: {mechanism}")
    res.with_step(f"Состав: {composition}")
    res.with_step(f"Начальная температура: {temperature:.1f} К")
    res.with_step(f"Выгорает: {main_name} "
                  f"({initial_fractions[main_index]*100:.2f} % -> "
                  f"{final_fractions[main_index]*100:.2f} %)")
    res.with_step(f"Конечная температура: {temperatures[-1]:.1f} К")
    res.with_step(f"Шагов расчёта: {len(times)}")
    res.with_source("Cantera: кинетика по механизму")
    res.with_meta("series_temperature", list(zip(times, temperatures)))
    res.with_meta("series_share", list(zip(times, shares)))
    res.with_meta("main_share_initial", initial_fractions[main_index])
    res.with_meta("main_share_final", final_fractions[main_index])
    res.with_meta("main_species", main_name)
    res.with_assumption(
        "Реактор идеального смешения, постоянный объём, теплопотери "
        "отсутствуют. Реальная кинетика зависит от геометрии и смешения."
    )
    return res


def mechanism_info(mechanism: str) -> Result:
    """Что содержит механизм: виды и число реакций."""
    ct = _cantera()
    try:
        gas = ct.Solution(mechanism)
    except Exception as exc:
        raise DataNotFoundError(f"Механизм «{mechanism}» не найден") from exc

    rows = [{"Вещество": name} for name in gas.species_names]
    res = table_result(rows, label=f"Вещества механизма {mechanism}",
                       columns=["Вещество"])
    res.method = f"Cantera {version()}"
    res.with_step(f"Видов: {gas.n_species}")
    res.with_step(f"Реакций: {gas.n_reactions}")
    res.with_step(f"Фаз: {gas.n_phases}")
    res.with_source("Cantera: комплект механизмов")
    return res
