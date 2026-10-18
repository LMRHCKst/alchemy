"""Органическая химия: классы, изомерия, формула по продуктам сгорания.

Школьный курс 10 класса. Органика отличается от неорганики тем, что
у веществ один состав может соответствовать нескольким классам
(C2H4 — этен или циклоэтан), поэтому класс определяется по составу
с оговоркой, когда ответ неоднозначен.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from ..core import formula as F
from ..core.errors import AlchemyError, DataNotFoundError, InputError
from ..core.results import Result, table_result

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "organic.json")

#: молярные массы для расчёта по продуктам сгорания
M_CO2 = 44.009
M_H2O = 18.015
M_C = 12.011
M_H = 1.008
M_O = 15.999

#: молярный объём газа при нормальных условиях, л/моль
MOLAR_VOLUME = 22.414


@lru_cache(maxsize=1)
def _database() -> dict:
    """Загрузить справочник органики."""
    try:
        with open(DATA_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover
        raise DataNotFoundError(
            "Не найден справочник органики (alchemy/data/organic.json)") from exc


def _series() -> list[dict]:
    return _database()["series"]


def _find_series(key_or_name: str) -> dict | None:
    """Найти класс по ключу или названию."""
    text = str(key_or_name or "").strip().lower()
    if not text:
        return None
    for item in _series():
        if item["key"].lower() == text:
            return item
        if item["name"].lower() == text:
            return item
        if item["name"].lower().startswith(text):
            return item
    return None


def classes_table() -> Result:
    """Все классы органических веществ."""
    rows = []
    for item in _series():
        rows.append({
            "Класс": item["name"],
            "Общая формула": item["general"],
            "Группа": item["group"],
            "Суффикс": item["suffix"],
        })

    res = table_result(rows, label="Классы органических веществ",
                       columns=["Класс", "Общая формула", "Группа", "Суффикс"])
    res.method = "Справочник классов школьного курса"
    res.with_step(f"Классов в справочнике: {len(rows)}")
    res.with_step("Общая формула показывает, как связаны число атомов "
                  "углерода и водорода внутри гомологического ряда")
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def homologous_series(key_or_name: str) -> Result:
    """Гомологический ряд класса с молярными массами."""
    series = _find_series(key_or_name)
    if series is None:
        raise DataNotFoundError(
            f"Класс «{key_or_name}» не найден. Доступны: "
            + ", ".join(item["name"] for item in _series()))

    rows = []
    for member in series["members"]:
        mass = F.molar_mass(member["formula"])
        rows.append({
            "Формула": member["formula"],
            "Название": member["name"],
            "Тривиальное": member["trivial"] or "—",
            "Молярная масса": f"{mass:.2f}",
        })

    res = table_result(rows, label=f"Гомологический ряд: {series['name']}",
                       columns=["Формула", "Название", "Тривиальное",
                                "Молярная масса"])
    res.method = "Гомологический ряд класса; массы по стандартным атомным"
    res.with_step(f"Класс: {series['name']}")
    res.with_step(f"Общая формула: {series['general']}")
    res.with_step(f"Функциональная группа: {series['group']}")
    res.with_step(f"Суффикс в названии: {series['suffix']}")
    res.with_step("")
    res.with_step(series["note"])
    res.with_step("")
    res.with_step("Каждый следующий гомолог отличается на группу CH2, "
                  "то есть на 14.03 г/моль")

    if len(rows) > 1:
        first = F.molar_mass(series["members"][0]["formula"])
        second = F.molar_mass(series["members"][1]["formula"])
        res.with_step(f"Проверка: {first:.2f} + 14.03 = {first + 14.027:.2f}, "
                      f"а следующий гомолог {second:.2f}")

    res.with_meta("key", series["key"])
    res.with_meta("count", len(rows))
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def _member_by_formula(text: str) -> tuple[dict, dict] | None:
    """Найти вещество в справочнике по точной формуле."""
    normalized = F.normalize_input(text)
    body, _state = F.split_state(normalized)
    for series in _series():
        for member in series["members"]:
            if F.normalize_input(member["formula"]) == body:
                return series, member
    return None


def _looks_like_formula(text: str) -> bool:
    """Похоже ли на химическую формулу, а не на слово."""
    import re

    return bool(re.fullmatch(r"[A-Za-z0-9()\[\]*·.{}^+-]+", text or "")
                and any(char.isupper() for char in text or ""))


def _member_by_name(text: str) -> tuple[dict, dict] | None:
    """Найти вещество по названию, включая тривиальное."""
    lowered = str(text or "").strip().lower()
    if not lowered:
        return None
    for series in _series():
        for member in series["members"]:
            names = [member["name"].lower()]
            if member.get("trivial"):
                names.append(str(member["trivial"]).lower())
            for name in names:
                if name == lowered or name.startswith(lowered):
                    return series, member
    return None


def _hydrocarbon_class(carbons: int, hydrogens: int) -> list[tuple[str, str]]:
    """Возможные классы для углеводорода CnHm."""
    if carbons < 1:
        return []

    saturated = 2 * carbons + 2
    options = []

    if hydrogens == saturated:
        options.append(("alkanes", "предельный углеводород"))
    elif hydrogens == 2 * carbons:
        options.append(("alkenes", "одна двойная связь"))
        options.append(("cycloalkanes", "замкнутый цикл без двойных связей"))
    elif hydrogens == 2 * carbons - 2:
        options.append(("alkynes", "одна тройная связь"))
        options.append(("alkadienes", "две двойные связи"))
    elif carbons >= 6 and hydrogens == 2 * carbons - 6:
        options.append(("arenes", "ароматическое кольцо"))
    elif hydrogens < 2 * carbons - 2:
        options.append(("arenes", "несколько кратных связей или кольцо"))

    return options


def _oxygen_class(carbons: int, hydrogens: int,
                  oxygens: int) -> list[tuple[str, str]]:
    """Возможные классы для кислородсодержащего вещества."""
    options = []

    if oxygens == 1:
        if hydrogens == 2 * carbons + 2:
            options.append(("alcohols", "одна группа OH, предельный"))
        elif hydrogens == 2 * carbons:
            options.append(("aldehydes", "карбонильная группа на конце"))
            options.append(("ketones", "карбонильная группа внутри цепи"))
        elif carbons >= 6 and hydrogens == 2 * carbons - 6:
            options.append(("phenols", "OH при ароматическом кольце"))
    elif oxygens == 2:
        if hydrogens == 2 * carbons:
            options.append(("acids", "карбоксильная группа"))
            options.append(("esters", "сложноэфирная группа"))
        elif hydrogens == 2 * carbons + 2:
            options.append(("polyols", "две группы OH"))
    elif oxygens >= 3:
        if hydrogens == 2 * carbons + 2:
            options.append(("polyols", "несколько групп OH"))

    return options


def _carbohydrate_class(carbons: int, hydrogens: int,
                        oxygens: int) -> bool:
    """Похоже ли на углевод: C_n(H2O)_m."""
    if oxygens < 1:
        return False
    if hydrogens != 2 * oxygens:
        return False
    return carbons >= 5


def class_of(text: str) -> Result:
    """Определить класс органического вещества по формуле или названию.

    Название задаёт класс однозначно: «пропен» — это алкен. Формула может
    допускать два класса: C3H6 подходит и алкену, и циклоалкану, и об этом
    надо сказать честно, а не выбирать за пользователя.
    """
    raw = str(text or "").strip()
    if not raw:
        raise InputError("Введите формулу или название вещества")

    # Название — самый надёжный вход
    found_name = _member_by_name(raw)
    if found_name is not None and not _looks_like_formula(raw):
        series, member = found_name
        res = Result(
            value=series["name"],
            unit="",
            label=f"Класс вещества: {series['name']}",
            method="Поиск по названию в справочнике классов",
        )
        res.with_step(f"Вещество: {member['name']} ({member['formula']})")
        if member.get("trivial"):
            res.with_step(f"Тривиальное название: {member['trivial']}")
        res.with_step(f"Класс: {series['name']}")
        res.with_step(f"Общая формула класса: {series['general']}")
        res.with_step(f"Функциональная группа: {series['group']}")
        res.with_step("")
        res.with_step(series["note"])
        res.with_meta("class_key", series["key"])
        res.with_meta("ambiguous", [series["key"]])
        res.with_source(_database().get("_source", "Школьный курс химии"))
        return res

    # Дальше — по составу
    try:
        composition = F.parse(raw)
    except AlchemyError as exc:
        raise InputError(
            f"Не удалось разобрать «{raw}». Поддерживается формула "
            f"или известное название (метан, этанол, уксусная).") from exc

    elements = set(composition.elements)
    counts = {el: composition.counts[el] for el in composition.elements}
    carbons = int(round(counts.get("C", 0)))
    hydrogens = int(round(counts.get("H", 0)))
    oxygens = int(round(counts.get("O", 0)))
    nitrogens = int(round(counts.get("N", 0)))

    if carbons == 0 or elements - {"C", "H", "O", "N"}:
        raise AlchemyError(
            "Это не похоже на органическое вещество: в органике основа "
            "углерод, остальные элементы — H, O и N.")

    # Структурная запись снимает неоднозначность: CH3COOH — это кислота,
    # а не сложный эфир, хотя состав у них один
    body_text = F.normalize_input(raw).replace("^", "")
    hinted = None
    if "COOH" in body_text:
        hinted = ("acids", "в записи видна группа COOH")
    elif "CHO" in body_text and not body_text.endswith("CH3CHO"):
        hinted = ("aldehydes", "в записи видна группа CHO")
    elif "COO" in body_text:
        hinted = ("esters", "в записи видна сложноэфирная группа COO")
    elif "OH" in body_text and "C" in body_text:
        hinted = ("alcohols", "в записи видна группа OH")

    options: list[tuple[str, str]] = []

    if elements <= {"C", "H"}:
        options = _hydrocarbon_class(carbons, hydrogens)
    elif nitrogens and oxygens >= 2:
        options = [("aminoacids", "аминогруппа и карбоксильная группа")]
    elif nitrogens:
        options = [("amines", "аминогруппа")]
    elif _carbohydrate_class(carbons, hydrogens, oxygens):
        if carbons == 6 and hydrogens == 12:
            options = [("carbohydrates", "моносахарид")]
        elif carbons == 12:
            options = [("carbohydrates", "дисахарид")]
        else:
            options = [("carbohydrates", "полисахарид")]
    else:
        options = _oxygen_class(carbons, hydrogens, oxygens)

    # Если в формуле видна функциональная группа, она сильнее состава
    if hinted is not None and any(key == hinted[0] for key, _n in options):
        options = [item for item in options if item[0] == hinted[0]]
    elif hinted is not None and not options:
        options = [hinted]

    if not options:
        raise AlchemyError(
            f"Состав {raw} не подходит ни под один класс школьного курса. "
            f"Проверьте формулу.")

    names = [_find_series(key)["name"] for key, _note in options if _find_series(key)]

    # Если формула есть в справочнике, это самое вероятное вещество,
    # но остальные варианты по составу всё равно надо показать
    member = _member_by_formula(raw)
    if member is not None:
        series, entry = member
        if series["key"] in [key for key, _n in options]:
            options.sort(key=lambda item: item[0] != series["key"])

    res = Result(
        value=names[0] if names else "не определено",
        unit="",
        label="Класс вещества по составу",
        method="Сравнение состава с общей формулой класса",
    )
    res.with_step(f"Формула: {raw}")
    res.with_step(f"Углерода: {carbons}, водорода: {hydrogens}, "
                  f"кислорода: {oxygens}" + (f", азота: {nitrogens}"
                                             if nitrogens else ""))
    if member is not None:
        res.with_step(f"В справочнике: {member[1]['name']} — "
                      f"{member[0]['name']}")
    res.with_step("")
    res.with_step("Возможные классы по составу:")
    for key, note in options:
        series_item = _find_series(key)
        if series_item:
            res.with_step(f"  {series_item['name']} — {note}")

    if len(options) > 1:
        res.with_warning(
            "Однозначно определить класс по формуле нельзя: "
            + " или ".join(names)
            + ". Нужно знать строение. Например, C3H6 — это и пропен "
              "(двойная связь), и циклопропан (кольцо)."
        )

    res.with_meta("class_key", options[0][0])
    res.with_meta("ambiguous", [key for key, _note in options])
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def isomers(formula: str) -> Result:
    """Число структурных изомеров и типы изомерии."""
    raw = str(formula or "").strip()
    if not raw:
        raise InputError("Введите формулу вещества")

    table = _database().get("alkane_isomers", {})
    normalized = F.normalize_input(raw)
    body, _state = F.split_state(normalized)

    found = _member_by_formula(raw)
    class_note = ""
    if found is not None:
        class_note = f" ({found[0]['name']})"

    count = table.get(body)
    types = _database().get("isomerism", [])

    rows = [{"Тип изомерии": item["type"], "Пример": item["example"],
             "Суть": item["note"]} for item in types]

    res = table_result(rows, label=f"Изомерия для {body}{class_note}",
                       columns=["Тип изомерии", "Пример", "Суть"])
    res.method = "Справочник типов изомерии; число изомеров алканов из таблицы"
    res.with_step(f"Формула: {body}")

    if count is not None:
        res.with_step(f"Структурных изомеров: {count}")
        # value остаётся таблицей типов изомерии, число идёт в мету
        res.label = f"Структурных изомеров у {body}: {count}"
        if count == 1:
            res.with_step("Изомеров нет: при таком числе атомов углерода "
                          "цепь может быть только одна.")
        else:
            res.with_step("Считать изомеры нужно по правилам: сначала "
                          "прямая цепь, потом цепи с заместителями.")
    else:
        res.with_step("Число изомеров для этой формулы в таблицу не входит. "
                      "Типы изомерии перечислены ниже.")

    res.with_step("")
    res.with_step("Типы изомерии, которые нужно проверять:")
    for item in types[:4]:
        res.with_step(f"  {item['type']}: {item['example']}")

    res.with_meta("formula", body)
    res.with_meta("count", count)
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def _integers_from_moles(moles: dict[str, float]) -> tuple[dict[str, int], float]:
    """Целые отношения количеств вещества.

    Делим на меньшее и подбираем множитель, при котором все числа
    становятся целыми. Возвращает отношения и множитель.
    """
    values = {el: n for el, n in moles.items() if n > 1e-9}
    if not values:
        raise InputError("Не удалось определить состав: все количества нулевые")

    smallest = min(values.values())
    normalized = {el: n / smallest for el, n in values.items()}

    for factor in range(1, 13):
        scaled = {el: n * factor for el, n in normalized.items()}
        if all(abs(v - round(v)) < 0.08 for v in scaled.values()):
            integers = {el: int(round(v)) for el, v in scaled.items()}
            return integers, factor

    # Не подошло ни одно целое: оставляем как есть с точностью до второго знака
    integers = {el: max(1, round(v)) for el, v in normalized.items()}
    return integers, 1.0


def _formula_text(integers: dict[str, int]) -> str:
    """Собрать формулу из отношений: C, H, O по порядку."""
    order = [el for el in ("C", "H", "N", "O") if el in integers]
    parts = []
    for element in order:
        count = integers[element]
        parts.append(element if count == 1 else f"{element}{count}")
    return "".join(parts)


def combustion_formula(sample_mass: float, co2_mass: float = 0.0,
                       h2o_mass: float = 0.0, co2_volume: float = 0.0,
                       molar_mass: float = 0.0) -> Result:
    """Молекулярная формула по продуктам сгорания.

    Классическая задача 10 класса: сожгли навеску, собрали CO2 и H2O,
    нашли формулу.

    Args:
        sample_mass: масса сожжённого вещества, г.
        co2_mass: масса образовавшегося CO2, г.
        h2o_mass: масса образовавшейся воды, г.
        co2_volume: объём CO2 при н.у., л (если масса не задана).
        molar_mass: молярная масса вещества, г/моль (необязательно).
    """
    if sample_mass <= 0:
        raise InputError("Масса навески должна быть больше нуля")
    if co2_mass <= 0 and co2_volume <= 0:
        raise InputError("Укажите массу или объём углекислого газа")
    if h2o_mass < 0:
        raise InputError("Масса воды не может быть отрицательной")

    # Углерод: сколько его в CO2
    if co2_mass > 0:
        n_carbon = co2_mass / M_CO2
    else:
        n_carbon = co2_volume / MOLAR_VOLUME

    # Водород: в воде два атома H на молекулу
    n_hydrogen = 2 * h2o_mass / M_H2O if h2o_mass > 0 else 0.0

    mass_carbon = n_carbon * M_C
    mass_hydrogen = n_hydrogen * M_H

    # Школьные задачи дают округлённые массы (44, 18, 12, 1), поэтому
    # сумма может превысить навеску на доли процента. Допускаем это,
    # но только в пределах округления.
    excess = mass_carbon + mass_hydrogen - sample_mass
    tolerance = max(0.01, sample_mass * 0.01)

    if excess > tolerance:
        raise InputError(
            f"Углерод и водород вместе весят "
            f"{mass_carbon + mass_hydrogen:.3f} г, а навеска "
            f"{sample_mass:.3f} г. Данные противоречат друг другу.")

    mass_oxygen = sample_mass - mass_carbon - mass_hydrogen
    if mass_oxygen < 0:
        # Избыток в пределах округления: кислорода в веществе нет
        mass_oxygen = 0.0
    n_oxygen = mass_oxygen / M_O if mass_oxygen > 1e-6 else 0.0

    moles = {"C": n_carbon, "H": n_hydrogen}
    if n_oxygen > 0:
        moles["O"] = n_oxygen

    integers, factor = _integers_from_moles(moles)
    empirical = _formula_text(integers)

    res = Result(
        value=empirical,
        unit="",
        label="Формула по продуктам сгорания",
        method="По массе CO2 и H2O; кислород — по разности масс",
    )
    res.with_step(f"Навеска: {sample_mass:g} г")
    if co2_mass > 0:
        res.with_step(f"CO2: {co2_mass:g} г")
    else:
        res.with_step(f"CO2: {co2_volume:g} л при н.у.")
    if h2o_mass > 0:
        res.with_step(f"H2O: {h2o_mass:g} г")
    res.with_step("")

    if co2_mass > 0:
        res.with_step(f"n(C) = {co2_mass:g} / {M_CO2} = {n_carbon:.6f} моль")
    else:
        res.with_step(f"n(C) = {co2_volume:g} / {MOLAR_VOLUME} = "
                      f"{n_carbon:.6f} моль")
    res.with_step(f"m(C) = {n_carbon:.6f} × {M_C} = {mass_carbon:.4f} г")
    res.with_step("")
    res.with_step(f"n(H) = 2 × {h2o_mass:g} / {M_H2O} = {n_hydrogen:.6f} моль")
    res.with_step(f"m(H) = {n_hydrogen:.6f} × {M_H} = {mass_hydrogen:.4f} г")
    res.with_step("")
    res.with_step(f"m(O) = {sample_mass:g} − {mass_carbon:.4f} − "
                  f"{mass_hydrogen:.4f} = {mass_oxygen:.4f} г")
    res.with_step(f"n(O) = {mass_oxygen:.4f} / {M_O} = {n_oxygen:.6f} моль")
    res.with_step("")
    ratio = " : ".join(f"{moles[el]:.4f}" for el in moles)
    res.with_step(f"Отношение {':'.join(moles)} = {ratio}")
    res.with_step(f"Делим на меньшее и подбираем множитель: {factor:g}")
    res.with_step(f"Целые отношения: " +
                  " : ".join(str(integers[el]) for el in integers))
    res.with_step(f"Простейшая формула: {empirical}")

    molecular = empirical
    if molar_mass > 0:
        molecular = F.molecular_formula_from_empirical(empirical, molar_mass)
        res.with_step("")
        res.with_step(f"При молярной массе {molar_mass:g} г/моль "
                      f"молекулярная формула: {molecular}")
        mass_empirical = F.molar_mass(empirical)
        factor = round(molar_mass / mass_empirical)
        res.with_step(f"Множитель: {molar_mass:g} / {mass_empirical:.2f} = {factor}")
        res.value = molecular
        res.label = "Молекулярная формула по продуктам сгорания"

    res.with_meta("empirical", empirical)
    res.with_meta("molecular", molecular)
    res.with_meta("carbons", n_carbon)
    res.with_meta("hydrogens", n_hydrogen)
    res.with_meta("oxygens", n_oxygen)

    res.with_assumption(
        "Сгорание полное: весь углерод перешёл в CO2, весь водород в H2O. "
        "Кислород считается по разности масс, поэтому другие элементы "
        "(азот, галогены) дадут ошибку."
    )
    res.with_source("Расчёт по продуктам сгорания: школьный курс химии")
    return res


def reactions_of(key_or_name: str) -> Result:
    """Реакции класса органических веществ."""
    series = _find_series(key_or_name)
    if series is None:
        raise DataNotFoundError(
            f"Класс «{key_or_name}» не найден. Доступны: "
            + ", ".join(item["name"] for item in _series()))

    rows = []
    for reaction in series["reactions"]:
        rows.append({
            "Тип": reaction["type"],
            "Уравнение": reaction["equation"],
            "Примечание": reaction["note"],
        })

    res = table_result(rows, label=f"Реакции: {series['name']}",
                       columns=["Тип", "Уравнение", "Примечание"])
    res.method = "Справочник реакций школьного курса"
    res.with_step(f"Класс: {series['name']}")
    res.with_step(f"Реакций в справочнике: {len(rows)}")
    res.with_step("")
    for reaction in series["reactions"]:
        res.with_step(f"  {reaction['type']}: {reaction['equation']}")
        if reaction["note"]:
            res.with_step(f"    {reaction['note']}")

    res.with_meta("key", series["key"])
    res.with_meta("count", len(rows))
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def qualitative_tests(key_or_name: str = "") -> Result:
    """Качественные пробы в органике."""
    text = str(key_or_name or "").strip()
    tests = _database()["qualitative"]

    if text:
        series = _find_series(text)
        if series is None:
            raise DataNotFoundError(f"Класс «{text}» не найден")
        tests = [item for item in tests if item["class"] == series["key"]]
        if not tests:
            raise DataNotFoundError(
                f"Для класса «{series['name']}» качественных проб "
                f"в справочнике нет")

    rows = []
    for item in tests:
        series = _find_series(item["class"])
        rows.append({
            "Класс": series["name"] if series else item["class"],
            "Проба": item["test"],
            "Признак": item["effect"],
            "Пояснение": item["note"],
        })

    res = table_result(rows, label="Качественные пробы в органике",
                       columns=["Класс", "Проба", "Признак", "Пояснение"])
    res.method = "Справочник качественных реакций"
    res.with_step(f"Проб в справочнике: {len(rows)}")
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def polymers_table() -> Result:
    """Полимеры и их мономеры."""
    rows = []
    for item in _database()["polymers"]:
        rows.append({
            "Мономер": f"{item['monomer']} ({item['monomer_name']})",
            "Полимер": f"{item['polymer']} — {item['polymer_name']}",
            "Тип": item["type"],
            "Применение": item["use"],
        })

    res = table_result(rows, label="Полимеры и мономеры",
                       columns=["Мономер", "Полимер", "Тип", "Применение"])
    res.method = "Справочник полимеров школьного курса"
    res.with_step(f"Полимеров в справочнике: {len(rows)}")
    res.with_step("Реакция полимеризации идёт без выделения побочных "
                  "продуктов, поликонденсации — с выделением воды")
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def genetic_link(first: str, second: str) -> Result:
    """Возможный переход между классами органики."""
    first_class = class_of(first)
    second_class = class_of(second)

    key_first = first_class.meta["class_key"]
    key_second = second_class.meta["class_key"]

    transitions = {
        ("alkanes", "alkenes"): "дегидрирование: алкан → алкен + H2",
        ("alkanes", "alkynes"): "двойное дегидрирование через алкен",
        ("alkenes", "alkanes"): "гидрирование: алкен + H2 → алкан",
        ("alkenes", "alcohols"): "гидратация: алкен + H2O → спирт",
        ("alkenes", "alkynes"): "дегидрирование: алкен → алкин + H2",
        ("alkynes", "alkenes"): "гидрирование: алкин + H2 → алкен",
        ("alkynes", "arenes"): "тримеризация: 3C2H2 → C6H6",
        ("alcohols", "aldehydes"): "окисление: спирт + CuO → альдегид",
        ("alcohols", "alkenes"): "дегидратация: спирт → алкен + H2O",
        ("alcohols", "acids"): "окисление через альдегид",
        ("aldehydes", "acids"): "окисление: альдегид + O2 → кислота",
        ("aldehydes", "alcohols"): "восстановление: альдегид + H2 → спирт",
        ("acids", "esters"): "этерификация: кислота + спирт → эфир + H2O",
        ("esters", "acids"): "гидрология: эфир + H2O → кислота + спирт",
        ("esters", "fats"): "жиры — сложные эфиры глицерина",
        ("carbohydrates", "alcohols"): "брожение глюкозы даёт этанол",
        ("amines", "aminoacids"): "через замещение водорода на карбоксил",
        ("aminoacids", "proteins"): "поликонденсация: пептидная связь",
        ("alkenes", "alkadienes"): "через дегидрирование",
        ("alkadienes", "arenes"): "дегидроциклизация",
    }

    step = transitions.get((key_first, key_second))

    res = Result(
        value="возможен" if step else "прямую не рассматривают",
        unit="",
        label=f"Генетическая связь: {first} → {second}",
        method="Правила переходов между классами органики",
    )
    res.with_step(f"{first}: {first_class.value}")
    res.with_step(f"{second}: {second_class.value}")
    res.with_step("")
    if step:
        res.with_step(f"Переход: {step}")
    else:
        res.with_step(
            "Прямого перехода между этими классами в школьном курсе нет. "
            "Он может идти через промежуточные вещества.")

    if "гидрология" in str(step):
        res.with_step("Имеется в виду гидролиз.")

    res.with_meta("first_class", key_first)
    res.with_meta("second_class", key_second)
    res.with_meta("possible", bool(step))
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def nomenclature_help() -> Result:
    """Корни и суффиксы названий органики."""
    data = _database()["nomenclature"]

    rows = []
    for number, root in data["roots"].items():
        rows.append({"Углерода": number, "Корень": root})

    res = table_result(rows, label="Названия по числу атомов углерода",
                       columns=["Углерода", "Корень"])
    res.method = "Номенклатура IUPAC: корни названий"
    res.with_step("Корень зависит от числа атомов углерода в цепи: "
                  "мет, эт, проп, бут, пент…")
    res.with_step("")
    res.with_step("Суффиксы по классам:")
    for key, suffix in data["suffixes"].items():
        series = _find_series(key)
        name = series["name"] if series else key
        res.with_step(f"  {name}: {suffix}")
    res.with_step("")
    res.with_step(data["rule"])
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res
