"""Жёсткость воды и способы её устранения.

9 класс: жёсткость воды, ионы кальция и магния, способы умягчения.
Жёсткость выражается в градусах жёсткости: 1 °Ж = 1 мг-экв/л, то есть
20.04 мг Ca²⁺ или 12.15 мг Mg²⁺ на литр.
"""

from __future__ import annotations

from ..core import formula as F
from ..core.errors import InputError
from ..core.results import Result, table_result

#: молярные массы эквивалента, г/моль
EQUIVALENT_MASS = {
    "Ca": 40.078 / 2,
    "Mg": 24.305 / 2,
    "HCO3": 61.016,
    "Ca(OH)2": 74.093 / 2,
    "Na2CO3": 105.99 / 2,
    "Na2EDTA": 372.24 / 2,
}

#: границы жёсткости по ГОСТ 31865-2012, °Ж
HARDNESS_SCALE = [
    (0.0, 1.5, "очень мягкая"),
    (1.5, 4.0, "мягкая"),
    (4.0, 8.0, "средняя"),
    (8.0, 12.0, "жёсткая"),
    (12.0, 1e9, "очень жёсткая"),
]


def _classify(degrees: float) -> str:
    """Название жёсткости по градусам."""
    for low, high, name in HARDNESS_SCALE:
        if low <= degrees < high:
            return name
    return HARDNESS_SCALE[-1][2]


def _positive(raw: str, name: str, allow_zero: bool = True) -> float:
    """Прочитать неотрицательное число."""
    text = str(raw).strip().replace(",", ".")
    if not text:
        raise InputError(f"Не заполнено поле: {name}")
    try:
        value = float(text)
    except ValueError:
        raise InputError(f"Значение «{raw}» в поле «{name}» не число")
    if value < 0 or (value == 0 and not allow_zero):
        raise InputError(f"Поле «{name}» не может быть "
                         f"{'отрицательным' if value < 0 else 'нулём'}")
    return value


def water_hardness(calcium: float, magnesium: float,
                   hydrocarbonate: float = 0.0,
                   volume: float = 1.0) -> Result:
    """Жёсткость воды и реагенты для умягчения.

    Args:
        calcium: массовая концентрация Ca²⁺, мг/л.
        magnesium: массовая концентрация Mg²⁺, мг/л.
        hydrocarbonate: концентрация HCO3⁻, мг/л (для карбонатной жёсткости).
        volume: объём воды, м³.
    """
    if volume <= 0:
        raise InputError("Объём воды должен быть больше нуля")
    if calcium < 0 or magnesium < 0:
        raise InputError("Концентрации ионов не могут быть отрицательными")
    if hydrocarbonate < 0:
        raise InputError("Концентрация гидрокарбоната не может быть "
                         "отрицательной")

    ca_eq = calcium / EQUIVALENT_MASS["Ca"]
    mg_eq = magnesium / EQUIVALENT_MASS["Mg"]
    total = ca_eq + mg_eq

    hco3_eq = hydrocarbonate / EQUIVALENT_MASS["HCO3"] if hydrocarbonate else 0.0
    carbonate = min(total, hco3_eq)
    non_carbonate = max(0.0, total - carbonate)

    liters = volume * 1000.0

    rows = [
        {"Показатель": "Жёсткость по кальцию", "Значение": f"{ca_eq:.3f}",
         "Единица": "°Ж", "Доля": f"{ca_eq / total * 100:.1f} %" if total else "—"},
        {"Показатель": "Жёсткость по магнию", "Значение": f"{mg_eq:.3f}",
         "Единица": "°Ж", "Доля": f"{mg_eq / total * 100:.1f} %" if total else "—"},
        {"Показатель": "Общая жёсткость", "Значение": f"{total:.3f}",
         "Единица": "°Ж", "Доля": _classify(total)},
        {"Показатель": "Карбонатная (временная)", "Значение": f"{carbonate:.3f}",
         "Единица": "°Ж", "Доля": "устраняется кипячением"},
        {"Показатель": "Некарбонатная (постоянная)",
         "Значение": f"{non_carbonate:.3f}", "Единица": "°Ж",
         "Доля": "кипячением не устраняется"},
    ]

    res = table_result(rows, label="Жёсткость воды",
                       columns=["Показатель", "Значение", "Единица", "Доля"])
    res.method = ("Пересчёт массовых концентраций в мг-экв/л; "
                  "1 °Ж = 1 мг-экв/л")
    res.with_step(f"Кальций: {calcium:g} мг/л")
    res.with_step(f"Магний: {magnesium:g} мг/л")
    if hydrocarbonate:
        res.with_step(f"Гидрокарбонат: {hydrocarbonate:g} мг/л")
    res.with_step(f"Объём воды: {volume:g} м³")
    res.with_step("")
    res.with_step("Пересчёт:")
    res.with_step(f"  Ca: {calcium:g} / {EQUIVALENT_MASS['Ca']:.2f} = "
                  f"{ca_eq:.4f} мг-экв/л")
    res.with_step(f"  Mg: {magnesium:g} / {EQUIVALENT_MASS['Mg']:.2f} = "
                  f"{mg_eq:.4f} мг-экв/л")
    res.with_step(f"  Всего: {total:.4f} °Ж — {_classify(total)}")

    # Реагенты для умягчения
    lime_needed = carbonate * EQUIVALENT_MASS["Ca(OH)2"] * liters / 1000.0
    soda_needed = non_carbonate * EQUIVALENT_MASS["Na2CO3"] * liters / 1000.0
    trilone_needed = total * EQUIVALENT_MASS["Na2EDTA"] * liters / 1000.0

    res.with_step("")
    res.with_step(f"На {volume:g} м³ воды потребуется:")
    res.with_step(
        f"  известь Ca(OH)2 для карбонатной жёсткости: "
        f"{lime_needed:.1f} г ({lime_needed / 1000:.3f} кг)")
    res.with_step(
        f"  сода Na2CO3 для некарбонатной жёсткости: "
        f"{soda_needed:.1f} г ({soda_needed / 1000:.3f} кг)")
    res.with_step(
        f"  трилон Б для титрования пробы: "
        f"{trilone_needed:.2f} г ({trilone_needed / 1000:.4f} кг)")

    res.with_step("")
    res.with_step("Способы устранения:")
    res.with_step("  кипячение — только карбонатная жёсткость, "
                  "гидрокарбонаты разлагаются")
    res.with_step("  известкование — Ca(OH)2 осаждает гидрокарбонаты")
    res.with_step("  содование — Na2CO3 осаждает сульфаты и хлориды")
    res.with_step("  ионообмен — катионит заменяет Ca²⁺ и Mg²⁺ на Na⁺")
    res.with_step("  трилон Б — связывает ионы в комплекс, "
                  "применяется для определения жёсткости")

    res.with_meta("total_degrees", total)
    res.with_meta("carbonate", carbonate)
    res.with_meta("non_carbonate", non_carbonate)
    res.with_meta("classification", _classify(total))
    res.with_meta("lime_g", lime_needed)
    res.with_meta("soda_g", soda_needed)
    res.with_meta("trilone_g", trilone_needed)

    res.with_assumption(
        "Расчёт по ГОСТ 31865-2012. В жёсткость включены только кальций "
        "и магний: стронций и барий в школьном курсе не учитывают."
    )
    res.with_source("Жёсткость воды: ГОСТ 31865-2012, школьный курс химии")
    return res


def hardness_from_salts(salt_name: str, concentration: float) -> Result:
    """Жёсткость, которую даёт одна соль, мг/л."""
    salts = {
        "Ca(HCO3)2": ("Ca", 162.11),
        "Mg(HCO3)2": ("Mg", 146.34),
        "CaSO4": ("Ca", 136.14),
        "MgSO4": ("Mg", 120.37),
        "CaCl2": ("Ca", 110.98),
        "MgCl2": ("Mg", 95.21),
    }

    if salt_name not in salts:
        raise InputError(
            f"Неизвестная соль «{salt_name}». Известные: "
            + ", ".join(sorted(salts)))

    ion, molar_mass = salts[salt_name]
    if concentration < 0:
        raise InputError("Концентрация не может быть отрицательной")

    # концентрация в мг/л, молярная масса в г/моль:
    # ммоль/л = (мг/л) / (г/моль)
    millimoles = concentration / molar_mass
    # один ммоль двухзарядного иона даёт два мг-экв
    charge = 2 if ion in ("Ca", "Mg") else 1
    degrees = millimoles * charge

    res = Result(
        value=degrees,
        unit="°Ж",
        label=f"Жёсткость от {salt_name}",
        method="Пересчёт концентрации соли в мг-экв/л",
    )
    res.with_step(f"Соль: {salt_name}, молярная масса {molar_mass:.2f} г/моль")
    res.with_step(f"Концентрация: {concentration:g} мг/л")
    res.with_step(f"Количество вещества: {millimoles:.4f} ммоль/л")
    res.with_step(f"Даёт ионов {ion}²⁺ и жёсткость {degrees:.3f} °Ж")
    res.with_step(f"Это {_classify(degrees)} вода")
    res.with_meta("classification", _classify(degrees))
    res.with_meta("ion", ion)
    res.with_source("Жёсткость воды: школьный курс химии")
    return res


def hardness_scale_table() -> Result:
    """Таблица классов жёсткости."""
    rows = [
        {"Класс": name,
         "От": f"{low:g}",
         "До": (f"{high:g}" if high < 1e8 else "и выше")}
        for low, high, name in HARDNESS_SCALE
    ]
    res = table_result(rows, label="Классы жёсткости воды",
                       columns=["Класс", "От", "До"])
    res.method = "ГОСТ 31865-2012"
    res.with_step("Единица измерения — градус жёсткости, °Ж")
    res.with_step("1 °Ж = 1 мг-экв/л = 20.04 мг Ca²⁺/л = 12.15 мг Mg²⁺/л")
    res.with_source("ГОСТ 31865-2012")
    return res
