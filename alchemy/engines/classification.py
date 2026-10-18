"""Классификация неорганических веществ и их названия.

8 и 9 класс: оксиды, основания, кислоты, соли; основные, кислотные
и амфотерные оксиды; щёлочи и нерастворимые основания; генетическая связь.

Кислотный остаток ищется по составу, а не по строке: так разбираются
формулы со скобками вроде Fe2(SO4)3 и Al2(SO4)3.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from ..core import formula as F
from ..core import periodic
from ..core.errors import AlchemyError, DataNotFoundError, InputError
from ..core.results import Result, table_result

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "nomenclature.json")

#: классы веществ
CLASSES = {
    "simple_metal": "Простое вещество, металл",
    "simple_nonmetal": "Простое вещество, неметалл",
    "basic_oxide": "Основный оксид",
    "acidic_oxide": "Кислотный оксид",
    "amphoteric_oxide": "Амфотерный оксид",
    "non_salt_oxide": "Несолеобразующий оксид",
    "base": "Основание (щёлочь)",
    "insoluble_base": "Основание (нерастворимое)",
    "amphoteric_hydroxide": "Амфотерный гидроксид",
    "acid": "Кислота",
    "salt": "Соль",
    "unknown": "Не удалось отнести к классу",
}

#: родительный падеж для неметаллов: оксид углерода(IV)
NONMETAL_GENITIVE = {
    "C": "углерода", "S": "серы", "N": "азота", "P": "фосфора",
    "Si": "кремния", "Cl": "хлора", "Br": "брома", "I": "иода",
    "O": "кислорода", "H": "водорода", "B": "бора",
    "As": "мышьяка", "Se": "селена", "Te": "теллура", "F": "фтора",
}

#: категории, которые считаются металлами
METAL_CATEGORIES = ("Переходный металл", "Постпереходный металл",
                    "Щелочной металл", "Щёлочноземельный металл",
                    "Лантаноид", "Актиноид")


@lru_cache(maxsize=1)
def _database() -> dict:
    """Загрузить справочник номенклатуры."""
    try:
        with open(DATA_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover
        raise DataNotFoundError(
            "Не найден справочник номенклатуры "
            "(alchemy/data/nomenclature.json)") from exc


def is_metal(symbol: str) -> bool:
    """Металл ли элемент. Категории берём из справочника как есть."""
    try:
        category = periodic.by_symbol(symbol).category or ""
    except Exception:
        return False
    return category in METAL_CATEGORIES


def _roman(number: int) -> str:
    """Римская цифра для валентности."""
    values = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII"}
    return values.get(int(number), str(number))


def _cation_name(symbol: str, charge: int, genitive: bool) -> str | None:
    """Название катиона с валентностью там, где она переменная."""
    database = _database()

    variable = database.get("variable_cations", {}).get(symbol)
    if variable:
        forms = variable.get(str(charge))
        if forms:
            base = forms[1] if genitive else forms[0]
            # Железо, медь и олово бывают в разной валентности, поэтому
            # цифра обязательна: сульфат железа(III), а не просто железа
            return f"{base}({_roman(charge)})" if charge else base

    entry = database["cations"].get(symbol)
    if entry:
        # У металлов с постоянной валентностью цифру не пишем
        return entry["genitive"] if genitive else entry["name"]

    if symbol == "NH4":
        return "аммония" if genitive else "аммоний"

    if symbol in NONMETAL_GENITIVE:
        base = NONMETAL_GENITIVE[symbol] if genitive else \
            NONMETAL_GENITIVE[symbol].rstrip("ая")
        return f"{base}({_roman(charge)})" if charge else base

    try:
        element = periodic.by_symbol(symbol)
    except Exception:
        return None

    base = element.name_ru.lower()
    if genitive:
        base = base + "а" if not base.endswith(("а", "я", "ь")) else base
    return f"{base}({_roman(charge)})" if charge else base


def find_anion(composition) -> tuple[str, int, str, int] | None:
    """Найти кислотный остаток по составу.

    Возвращает (формула остатка, число остатков, элемент-катион, число
    катионов) или None.
    """
    database = _database()
    counts = {el: composition.counts[el] for el in composition.elements}

    best = None
    for anion in sorted(database["anions"], key=len, reverse=True):
        try:
            anion_comp = F.parse(anion)
        except AlchemyError:
            continue

        if any(el not in counts for el in anion_comp.elements):
            continue

        ratios = []
        for element in anion_comp.elements:
            ratios.append(counts[element] / anion_comp.counts[element])
        if not ratios:
            continue
        if max(ratios) - min(ratios) > 1e-9:
            continue

        unit_count = ratios[0]
        if abs(unit_count - round(unit_count)) > 1e-9 or unit_count < 1:
            continue
        unit_count = int(round(unit_count))

        remaining = {}
        for element, total in counts.items():
            left = total - anion_comp.counts.get(element, 0) * unit_count
            if left > 1e-9:
                remaining[element] = left

        if len(remaining) == 1:
            cation_symbol = next(iter(remaining))
            cation_count = remaining[cation_symbol]
            if abs(cation_count - round(cation_count)) > 1e-9:
                continue
            cation_count = int(round(cation_count))

            # Остаток не должен совпадать со всей формулой
            if not cation_count:
                continue

            candidate = (anion, unit_count, cation_symbol, cation_count)
            if best is None or len(anion) > len(best[0]):
                best = candidate

    return best


def _oxide_class(composition, body: str) -> tuple[str, str]:
    """Класс оксида и основание для него."""
    database = _database()
    counts = {el: composition.counts[el] for el in composition.elements}
    other = next(el for el in composition.elements if el != "O")

    if body in database["amphoteric_oxides"]:
        return "amphoteric_oxide", "оксид амфотерного металла"
    if body in database["non_salt_oxides"]:
        return "non_salt_oxide", "оксид, не образующий солей"
    if body in database["acidic_oxides_of_metals"]:
        return "acidic_oxide", "оксид металла в высшей степени окисления"

    if is_metal(other):
        return "basic_oxide", f"оксид металла ({periodic.by_symbol(other).name_ru})"

    return "acidic_oxide", f"оксид неметалла ({periodic.by_symbol(other).name_ru})"


def classify(text: str) -> Result:
    """Определить класс вещества по формуле."""
    raw = str(text or "").strip()
    if not raw:
        raise InputError("Введите формулу вещества")

    composition = F.parse(raw)
    normalized = F.normalize_input(raw)
    body, _state = F.split_state(normalized)
    database = _database()

    elements = list(composition.elements)
    counts = {el: composition.counts[el] for el in elements}

    kind = "unknown"
    reason = ""

    if len(elements) == 1:
        symbol = elements[0]
        if is_metal(symbol):
            kind = "simple_metal"
            reason = f"{periodic.by_symbol(symbol).name_ru} — металл"
        else:
            kind = "simple_nonmetal"
            reason = f"{periodic.by_symbol(symbol).name_ru} — неметалл"

    elif body in database["acids"]:
        kind = "acid"
        reason = "кислота из списка известных"

    elif "OH" in body:
        metal = next((el for el in elements if el not in ("O", "H")), None)
        if metal is None:
            kind = "unknown"
            reason = "гидроксид без металла"
        elif body in database["amphoteric_hydroxides"]:
            kind = "amphoteric_hydroxide"
            reason = "гидроксид амфотерного металла"
        elif body in database["soluble_hydroxides"]:
            kind = "base"
            reason = "растворимое основание, щёлочь"
        else:
            kind = "insoluble_base"
            reason = "нерастворимое основание"

    elif "O" in elements and len(elements) == 2:
        kind, reason = _oxide_class(composition, body)

    elif "H" in elements and len(elements) == 2 and "O" not in elements:
        kind = "acid"
        reason = "бескислородная кислота"

    else:
        anion = find_anion(composition)
        if anion is not None:
            kind = "salt"
            reason = (f"катион {anion[2]} и остаток {anion[0]} "
                      f"(×{anion[1]})")

    name = CLASSES.get(kind, CLASSES["unknown"])
    res = Result(
        value=name,
        unit="",
        label=f"Класс вещества {composition.display}",
        method="Определение по составу: элементы, гидроксильная группа, "
               "кислотный остаток",
    )
    res.with_step(f"Формула: {composition.display}")
    res.with_step(f"Элементы: {', '.join(elements)}")
    if reason:
        res.with_step(f"Основание для класса: {reason}")
    res.with_step(f"Класс: {name}")

    if kind.endswith("oxide"):
        res.with_step("")
        res.with_step("Оксиды делятся на солеобразующие (основные, кислотные, "
                      "амфотерные) и несолеобразующие.")
    elif kind in ("base", "insoluble_base", "amphoteric_hydroxide"):
        res.with_step("")
        res.with_step("Основания — гидроксиды металлов. Растворимые называют "
                      "щелочами.")
    elif kind == "salt":
        anion = find_anion(composition)
        if anion:
            res.with_step("")
            res.with_step(f"Кислотный остаток: {anion[0]}, количество "
                          f"{anion[1]}. Катион: {anion[2]}, количество "
                          f"{anion[3]}")

    res.with_meta("class_key", kind)
    res.with_meta("class_name", name)
    res.with_source(database.get("_source", "Школьный курс химии"))
    return res


def name_of(text: str) -> Result:
    """Систематическое название вещества по формуле."""
    raw = str(text or "").strip()
    if not raw:
        raise InputError("Введите формулу вещества")

    composition = F.parse(raw)
    normalized = F.normalize_input(raw)
    body, _state = F.split_state(normalized)
    database = _database()

    elements = list(composition.elements)
    counts = {el: composition.counts[el] for el in elements}
    name = ""

    if len(elements) == 1:
        name = periodic.by_symbol(elements[0]).name_ru

    elif body in database["acids"]:
        name = f"{database['acids'][body]} кислота"

    elif "OH" in body:
        metal = next((el for el in elements if el not in ("O", "H")), None)
        if metal is not None:
            charge = _cation_charge_from_hydroxide(composition, metal)
            cation = _cation_name(metal, charge, genitive=True)
            if cation:
                name = f"гидроксид {cation}"

    elif "O" in elements and len(elements) == 2:
        other = next(el for el in elements if el != "O")
        charge = _oxide_valence(other, counts.get("O", 1), counts.get(other, 1))
        cation = _cation_name(other, charge, genitive=True)
        if cation:
            name = f"оксид {cation}"

    elif "NH4" in body:
        # Аммоний: убираем NH4 и ищем остаток в остатке формулы
        import re as _re

        rest = _re.sub(r"\(?NH4\)?(\d+)?", "", body, count=1)
        try:
            rest_comp = F.parse(rest) if rest else None
        except AlchemyError:
            rest_comp = None
        if rest_comp is not None:
            anion_name = None
            for candidate in sorted(database["anions"], key=len, reverse=True):
                try:
                    cand_comp = F.parse(candidate)
                except AlchemyError:
                    continue
                if not set(cand_comp.elements) <= set(rest_comp.elements):
                    continue
                # Сверяем не только элементы, но и их соотношение:
                # иначе C2O4 подходит под CO3
                ratios = [rest_comp.counts[el] / cand_comp.counts[el]
                          for el in cand_comp.elements]
                if ratios and max(ratios) - min(ratios) < 1e-9:
                    anion_name = database["anions"][candidate]["name"]
                    break
            if anion_name:
                name = f"{anion_name} аммония"

    else:
        anion = find_anion(composition)
        if anion is not None:
            anion_name = database["anions"][anion[0]]["name"]
            cation = _cation_name(anion[2], _cation_charge(anion), genitive=True)
            if cation:
                name = f"{anion_name} {cation}"

    if not name:
        raise AlchemyError(
            f"Не удалось построить название для {raw}. Программа знает "
            f"простые вещества, оксиды, гидроксиды, кислоты и соли "
            f"с известным кислотным остатком.")

    res = Result(
        value=name,
        unit="",
        label=f"Название {composition.display}",
        method="Систематическая номенклатура: анион, затем катион "
               "в родительном падеже",
    )
    res.with_step(f"Формула: {composition.display}")
    res.with_step(f"Название: {name}")
    res.with_step("")
    res.with_step("Порядок в названии соли: сначала анион, потом катион "
                  "в родительном падеже.")

    if _has_variable_valence(name):
        res.with_step("Римская цифра в скобках — степень окисления металла, "
                      "если она переменная.")

    res.with_meta("name", name)
    res.with_source(database.get("_source", "Школьный курс химии"))
    return res


def _has_variable_valence(name: str) -> bool:
    """Есть ли в названии римская цифра валентности."""
    return "(" in name and ")" in name


def _cation_charge(anion: tuple[str, int, str, int]) -> int:
    """Заряд катиона из условия электронейтральности."""
    database = _database()
    anion_formula, anion_count, _symbol, cation_count = anion
    anion_charge = database["anions"][anion_formula]["charge"]
    total_negative = abs(anion_charge) * anion_count
    return max(1, round(total_negative / cation_count))


def _cation_charge_from_hydroxide(composition, metal: str) -> int:
    """Заряд металла в гидроксиде."""
    counts = {el: composition.counts[el] for el in composition.elements}
    metal_count = counts.get(metal, 1)
    hydroxide_count = counts.get("O", 1)
    return max(1, round(hydroxide_count / metal_count))


def _oxide_valence(element: str, oxygen_count: float | int,
                   element_count: float | int) -> int:
    """Валентность элемента в оксиде по балансу кислорода."""
    if not element_count:
        return 0
    return max(1, round(2 * oxygen_count / element_count))


def genetic_link(first: str, second: str) -> Result:
    """Возможен ли переход между двумя веществами и через какие шаги."""
    first_class = classify(first)
    second_class = classify(second)

    kind_first = first_class.meta["class_key"]
    kind_second = second_class.meta["class_key"]

    transitions = {
        ("simple_metal", "basic_oxide"):
            "металл + кислород → основный оксид",
        ("basic_oxide", "base"):
            "основный оксид + вода → щёлочь",
        ("base", "salt"):
            "щёлочь + кислота или кислотный оксид → соль",
        ("simple_nonmetal", "acidic_oxide"):
            "неметалл + кислород → кислотный оксид",
        ("acidic_oxide", "acid"):
            "кислотный оксид + вода → кислота",
        ("acid", "salt"):
            "кислота + основание или металл → соль",
        ("salt", "base"):
            "соль + щёлочь → новое основание и новая соль",
        ("salt", "acid"):
            "соль + кислота → новая соль и новая кислота",
        ("basic_oxide", "acidic_oxide"):
            "основный оксид + кислотный оксид → соль",
        ("acidic_oxide", "salt"):
            "кислотный оксид + щёлочь → соль и вода",
        ("base", "basic_oxide"):
            "щелочь при нагревании разлагается на оксид и воду",
        ("acid", "acidic_oxide"):
            "неустойчивая кислота разлагается на оксид и воду",
    }

    step = transitions.get((kind_first, kind_second))

    res = Result(
        value="возможен" if step else "напрямую не показан",
        unit="",
        label=f"Генетическая связь: {first} → {second}",
        method="Правила переходов между классами неорганических веществ",
    )
    res.with_step(f"{first}: {first_class.value}")
    res.with_step(f"{second}: {second_class.value}")
    res.with_step("")
    if step:
        res.with_step(f"Переход возможен: {step}")
    else:
        res.with_step(
            "Прямого перехода между этими классами в школьном курсе нет. "
            "Он может идти через промежуточное вещество, например через соль.")
    res.with_meta("first_class", kind_first)
    res.with_meta("second_class", kind_second)
    res.with_meta("possible", bool(step))
    res.with_source("Генетическая связь классов: школьный курс химии")
    return res


def classes_table() -> Result:
    """Справочная таблица классов неорганических веществ."""
    rows = [
        {"Класс": "Основный оксид", "Состав": "металл + кислород",
         "Пример": "CaO, Na2O, FeO"},
        {"Класс": "Кислотный оксид", "Состав": "неметалл + кислород",
         "Пример": "CO2, SO3, P2O5"},
        {"Класс": "Амфотерный оксид", "Состав": "металл + кислород",
         "Пример": "Al2O3, ZnO, Cr2O3"},
        {"Класс": "Основание (щёлочь)", "Состав": "металл + OH",
         "Пример": "NaOH, KOH, Ca(OH)2"},
        {"Класс": "Нерастворимое основание", "Состав": "металл + OH",
         "Пример": "Cu(OH)2, Fe(OH)3"},
        {"Класс": "Кислота", "Состав": "водород + кислотный остаток",
         "Пример": "HCl, H2SO4, H3PO4"},
        {"Класс": "Соль", "Состав": "металл + кислотный остаток",
         "Пример": "NaCl, CuSO4, CaCO3"},
    ]
    res = table_result(rows, label="Классы неорганических веществ",
                       columns=["Класс", "Состав", "Пример"])
    res.method = "Справочная таблица школьного курса"
    res.with_step("Амфотерные оксиды и гидроксиды реагируют и с кислотами, "
                  "и со щелочами")
    res.with_step("Несолеобразующие оксиды (CO, NO, N2O) солей не дают")
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res
