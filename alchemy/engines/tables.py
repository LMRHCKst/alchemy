"""Табличные сведения школьного курса: плотности, разложение, электролиз.

Здесь собрано то, что нельзя вывести из формул: справочные таблицы,
которые в школе дают готовыми. Каждая запись хранит тир достоверности:
A — справочник или стандарт, B — учебник, C — энциклопедия,
? — не подтверждено.

Данные лежат в `alchemy/data/school_tables.json`, собранном из внешней
сверки. Функции этого модуля не считают химию заново — они находят
запись и честно говорят, если её нет или если она не подтверждена.
"""

from __future__ import annotations

import json
from functools import lru_cache

from ..core import formula as F
from ..core.errors import InputError
from ..core.results import Result, table_result

_FILE = "school_tables.json"

_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")


def ion_key(text: str) -> str:
    """Ключ иона: элемент и число, без знака заряда.

    «Ag+» и «Ag» дают один ключ, а «Fe2+» и «Fe3+» — разные: цифру
    заряда терять нельзя, иначе двухвалентное железо путается с
    трёхвалентным.
    """
    import re

    clean = _plain(text).strip().lower()
    match = re.match(r"^(.*?)(\d*)([+-])?$", clean)
    if not match:
        return clean
    return f"{match.group(1)}{match.group(2)}"


def _plain(text: str) -> str:
    """Привести формулу из таблицы к обычной записи: NaClO₃ → NaClO3."""
    return str(text).translate(_SUBSCRIPTS).translate(_SUPERSCRIPTS).strip()


@lru_cache(maxsize=1)
def _tables() -> dict:
    from ..data import loader

    return loader.load(_FILE)


def _rows(name: str) -> list[dict]:
    return list(_tables().get(name) or [])


# --------------------------------------------------------------------------
# Плотность растворов
# --------------------------------------------------------------------------

def solution_density(substance: str, mass_percent: float) -> Result:
    """Плотность раствора при 20 °C по массовой доле.

    Для серной кислоты таблица плотная (шаг 1 %, 91 точка, NBS), поэтому
    между точками линейная интерполяция даёт ошибку меньше 0.1 %. Для
    остальных веществ точек мало, и об этом сказано в результате.
    """
    key = str(substance).strip().lower()
    table = [row for row in _rows("density_h2so4")
             if key in ("h2so4", "серная", "серная кислота", "h2so4(ж)")]

    if not table:
        raise InputError(
            "Плотность есть только для серной кислоты (таблица NBS, "
            "шаг 1 %). Для остальных веществ данных не хватает.")

    if not 0 <= mass_percent <= 100:
        raise InputError("Массовая доля должна быть от 0 до 100 %")

    table.sort(key=lambda row: row["w"])
    w_min, w_max = table[0]["w"], table[-1]["w"]
    if mass_percent > w_max:
        raise InputError(
            f"Таблица заканчивается на {w_max:g} %. Олеум и 100 % "
            f"кислоту считают отдельно: плотность максимальна при 98–99 %.")

    below = max((row for row in table if row["w"] <= mass_percent),
                key=lambda row: row["w"])
    above = min((row for row in table if row["w"] >= mass_percent),
                key=lambda row: row["w"])

    if below["w"] == above["w"]:
        rho = below["rho"]
    else:
        share = (mass_percent - below["w"]) / (above["w"] - below["w"])
        rho = below["rho"] + share * (above["rho"] - below["rho"])

    res = Result(
        value=rho,
        unit="г/см³",
        label=f"Плотность раствора H₂SO₄ {mass_percent:g} % при 20 °C",
        method="Таблица NBS Circular 19, линейная интерполяция",
    )
    res.with_step(f"Ближайшие точки: {below['w']:g} % → {below['rho']:.5f}, "
                  f"{above['w']:g} % → {above['rho']:.5f}")
    res.with_step(f"Плотность при {mass_percent:g} %: {rho:.5f} г/см³")
    res.with_meta("mass_percent", mass_percent)
    res.with_source("NBS Circular 19 (1924), Table 13; тир A")
    return res


def concentration_from_density(substance: str, mass_percent: float,
                               molar_mass: float | None = None) -> Result:
    """Перевести массовую долю в молярность через плотность."""
    density = solution_density(substance, mass_percent).numeric()

    if molar_mass is None:
        from ..core.formula import molar_mass as molar_mass_of

        molar_mass = molar_mass_of(substance)

    # 1 л раствора весит 1000·ρ г; в нём w % вещества
    grams = density * 1000.0 * mass_percent / 100.0
    molarity = grams / molar_mass

    res = Result(
        value=molarity,
        unit="моль/л",
        label=f"Молярность раствора {substance} {mass_percent:g} %",
        method="C = 10·ρ·w / M",
    )
    res.with_step(f"Плотность: {density:.5f} г/см³")
    res.with_step(f"В 1 л раствора: {grams:.1f} г вещества")
    res.with_step(f"M = {molar_mass:.3f} г/моль -> C = {molarity:.4f} моль/л")
    res.with_source("Плотность: NBS Circular 19")
    return res


# --------------------------------------------------------------------------
# Электролиз
# --------------------------------------------------------------------------

def electrolysis(electrolyte: str, state: str = "раствор") -> Result:
    """Продукты электролиза раствора или расплава."""
    want = _plain(electrolyte).lower()
    want_state = "расплав" if str(state).lower().startswith("распл") else "раствор"

    hits = []
    for row in _rows("electrolysis"):
        name = _plain(row["Электролит"])
        if name.rstrip("*").lower() == want or name.lower().startswith(want):
            hits.append(row)

    if not hits:
        raise InputError(
            f"В таблице электролиза нет «{electrolyte}». "
            f"Известны: {', '.join(sorted({_plain(r['Электролит']) for r in _rows('electrolysis')})[:15])}…")

    row = next((r for r in hits if r["Состояние"] == want_state), hits[0])

    res = Result(
        value=f"катод: {row['Катод']}; анод: {row['Анод']}",
        unit="",
        label=f"Электролиз {row['Электролит']}, {row['Состояние']}",
        method="Таблица продуктов электролиза школьного курса",
    )
    res.with_step(f"Катод: {row['Катод']}")
    res.with_step(f"Анод: {row['Анод']}")
    res.with_step(f"Суммарно: {row['Суммарно']}")
    if "не подтверждено" in row["Суммарно"] or "?" in row["Суммарно"]:
        res.with_warning(
            "Продукты этого электролиза в таблице помечены как "
            "неподтверждённые: на экзамене возможен другой ответ.")
    res.with_meta("cathode", row["Катод"])
    res.with_meta("anode", row["Анод"])
    res.with_source("Таблица школьного курса, тир C")
    return res


# --------------------------------------------------------------------------
# Термическое разложение
# --------------------------------------------------------------------------

def decomposition(substance: str) -> Result:
    """Что получится при прокаливании."""
    want = _plain(substance).lower()
    hits = [row for row in _rows("decomposition")
            if _plain(row["Вещество"]).lower() == want]

    if not hits:
        raise InputError(
            f"В таблице разложения нет «{substance}». Известны: "
            f"{', '.join(_plain(r['Вещество']) for r in _rows('decomposition')[:12])}…")

    rows = [{"Условие": row["Условие"], "Продукты": row["Продукты"],
             "Тир": row["Тир"]} for row in hits]

    res = table_result(
        rows,
        label=f"Термическое разложение {substance}",
        columns=["Условие", "Продукты", "Тир"],
    )
    res.method = "Таблица термического разложения школьного курса"
    for row in hits:
        if row["Тир"] in ("C", "?"):
            res.with_warning(
                f"Продукты помечены тиром {row['Тир']}: это общее правило "
                f"без справочного подтверждения, возможны варианты.")
            break
    res.with_source("Таблица школьного курса, тир C")
    return res


# --------------------------------------------------------------------------
# Качественные реакции
# --------------------------------------------------------------------------

def qualitative_reaction(ion: str, reagent: str = "") -> Result:
    """Признак качественной реакции на ион.

    Если реагент не задан — перечисляются все известные реакции на ион.
    """
    want_ion = _plain(ion).lower()
    want_reagent = _plain(reagent).lower()

    hits = []
    for row in _rows("qualitative"):
        name = _plain(row["Ион"]).lower()
        if name != want_ion and ion_key(name) != ion_key(want_ion):
            continue
        if want_reagent and want_reagent not in _plain(row["Реагент"]).lower():
            continue
        hits.append(row)

    if not hits:
        raise InputError(
            f"Нет качественной реакции на «{ion}»"
            + (f" с «{reagent}»" if reagent else "")
            + ". Известные ионы: "
            + ", ".join(sorted({_plain(r['Ион']) for r in _rows('qualitative')})))

    rows = [{"Реагент": row["Реагент"], "Признак": row["Признак"],
             "Осадок": row["Осадок"]} for row in hits]

    res = table_result(
        rows,
        label=f"Качественные реакции на {ion}",
        columns=["Реагент", "Признак", "Осадок"],
    )
    res.method = "Таблица качественных реакций школьного курса"
    res.with_source("Таблица школьного курса, тир C")
    return res


def flame_color(element: str) -> Result:
    """Окраска пламени для элемента."""
    colors = {
        "li": ("карминово-красный", "литий"),
        "na": ("жёлтый", "натрий"),
        "k": ("фиолетовый", "калий"),
        "ca": ("кирпично-красный", "кальций"),
        "sr": ("малиновый", "стронций"),
        "ba": ("жёлто-зелёный", "барий"),
        "cu": ("зелёный", "медь"),
    }
    key = _plain(element).strip("+").lower()
    key = key.rstrip("0123456789")
    if key not in colors:
        raise InputError(
            f"Окраска пламени известна для: {', '.join(colors)}")
    color, name = colors[key]
    res = Result(
        value=color,
        unit="",
        label=f"Окраска пламени: {name}",
        method="Таблица окрасок пламени школьного курса",
    )
    res.with_source("Таблица школьного курса, тир C")
    return res


def indicator_table() -> Result:
    """Индикаторы: интервалы перехода и цвета."""
    rows = [
        {"Индикатор": "Метиловый оранжевый", "Интервал pH": "3.1–4.4",
         "Кислая среда": "красный", "Щелочная среда": "жёлтый"},
        {"Индикатор": "Метиловый красный", "Интервал pH": "4.2–6.2",
         "Кислая среда": "красный", "Щелочная среда": "жёлтый"},
        {"Индикатор": "Лакмус", "Интервал pH": "5.0–8.0",
         "Кислая среда": "красный", "Щелочная среда": "синий"},
        {"Индикатор": "Фенолфталеин", "Интервал pH": "8.2–10.0",
         "Кислая среда": "бесцветный", "Щелочная среда": "малиновый"},
    ]
    res = table_result(rows, label="Кислотно-основные индикаторы",
                       columns=["Индикатор", "Интервал pH", "Кислая среда",
                                "Щелочная среда"])
    res.method = "Таблица индикаторов школьного курса"
    res.with_source("Таблица школьного курса, тир C")
    return res


# --------------------------------------------------------------------------
# Амфотерность и комплексы
# --------------------------------------------------------------------------

def amphoteric(formula: str) -> Result:
    """В какой гидроксокомплекс переходит амфотерный гидроксид."""
    want = _plain(formula).lower()
    for row in _rows("amphoteric"):
        if _plain(row["Гидроксид"]).lower() == want:
            res = Result(
                value=row["Комплекс"],
                unit="",
                label=f"Амфотерный гидроксид {formula} в избытке щёлочи",
                method="Таблица амфотерных гидроксокомплексов",
            )
            res.with_step(f"Условие: {row['Условие']}")
            res.with_step(f"Комплекс: {row['Комплекс']} — {row['Название']}")
            res.with_step("Растворение: "
                          f"{row['Гидроксид']} + избыток OH⁻ → {row['Комплекс']}")
            res.with_source("Таблица школьного курса, тир C")
            return res

    raise InputError(
        f"«{formula}» нет среди амфотерных гидроксидов. Известны: "
        + ", ".join(_plain(r["Гидроксид"]) for r in _rows("amphoteric")))


def complex_info(query: str) -> Result:
    """Сведения о комплексном соединении из школьного списка."""
    want = _plain(query).lower()
    for row in _rows("complexes"):
        if _plain(row["Формула"]).lower() == want:
            res = Result(
                value=row["Название"],
                unit="",
                label=f"Комплекс {row['Формула']}",
                method="Таблица комплексных соединений школьного курса",
            )
            res.with_step(f"Заряд комплекса: {row['Заряд']}")
            res.with_step(f"Координационное число: {row['КЧ']}")
            res.with_step(f"Растворимость: {row['Растворимость']}")
            res.with_meta("charge", row["Заряд"])
            res.with_meta("coordination", row["КЧ"])
            res.with_source("Таблица школьного курса, тир C")
            return res

    raise InputError(
        f"Комплекса «{query}» нет в таблице школьного курса. Известны: "
        + ", ".join(_plain(r["Формула"]) for r in _rows("complexes")[:8]) + "…")


def polymer_info(query: str) -> Result:
    """Мономер, звено и тип полимера."""
    want = _plain(query).lower()
    for row in _rows("polymers"):
        if _plain(row["Полимер"]).lower() == want:
            res = Result(
                value=row["Мономер"],
                unit="",
                label=f"Полимер {row['Полимер']}",
                method="Таблица полимеров школьного курса",
            )
            res.with_step(f"Мономер: {row['Мономер']}")
            res.with_step(f"Элементарное звено: {row['Элементарное звено']}")
            res.with_step(f"Тип реакции: {row['Тип']}")
            res.with_source("Таблица школьного курса, тир C")
            return res

    raise InputError(
        f"Полимера «{query}» нет в таблице. Известны: "
        + ", ".join(_plain(r["Полимер"]) for r in _rows("polymers")))


# --------------------------------------------------------------------------
# Ван-дер-Ваальс
# --------------------------------------------------------------------------

def vdw_constants(query: str) -> Result:
    """Константы a и b уравнения Ван-дер-Ваальса."""
    want = _plain(query).lower().strip()
    aliases = {
        "вода": "water", "water": "water", "h2o": "water",
        "co2": "carbon dioxide", "углекислый газ": "carbon dioxide",
        "o2": "oxygen", "кислород": "oxygen",
        "n2": "nitrogen", "азот": "nitrogen",
        "nh3": "ammonia", "аммиак": "ammonia",
        "h2": "hydrogen", "водород": "hydrogen",
        "ch4": "methane", "метан": "methane",
    }
    target = aliases.get(want, want)

    for row in _rows("vdw"):
        name = row["name"].lower()
        # в таблице есть уточнения в скобках: «Water (molecule)»
        if name == target or name.split(" (")[0] == target:
            res = Result(
                value=row["a"],
                unit="л²·бар/моль²",
                label=f"Константа a для {row['name']}",
                method="Таблица констант Ван-дер-Ваальса",
            )
            res.with_step(f"a = {row['a']} л²·бар/моль²")
            res.with_step(f"b = {row['b']} л/моль")
            res.with_meta("b", row["b"])
            res.with_source("CRC Handbook, 53rd ed. (1972); тир B/C")
            return res

    known = ", ".join(row["name"] for row in _rows("vdw")[:12])
    raise InputError(f"Нет констант для «{query}». Известны: {known}…")


def solvent_constants(name: str) -> Result:
    """Криоскопическая и эбулиоскопическая константы растворителя."""
    want = _plain(name).lower()
    for row in _rows("solvents"):
        if want in _plain(row["name"]).lower():
            res = Result(
                value=row["kf"],
                unit="°C·кг/моль",
                label=f"Константы растворителя: {row['name']}",
                method="Таблица криоскопических и эбулиоскопических констант",
            )
            res.with_step(f"Kf (замерзание) = {row['kf']} °C·кг/моль")
            res.with_step(f"Kb (кипение) = {row['kb']} °C·кг/моль")
            res.with_step(f"T кип = {row['t_boil']} °C, T пл = {row['t_freeze']} °C")
            res.with_meta("kb", row["kb"])
            res.with_meta("kf", row["kf"])
            res.with_source(f"{row['source']}; тир {row['tier']}")
            return res

    known = ", ".join(row["name"] for row in _rows("solvents"))
    raise InputError(f"Нет данных для «{name}». Известны: {known}")
