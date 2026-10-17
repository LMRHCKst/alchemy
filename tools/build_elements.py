# -*- coding: utf-8 -*-
"""Генератор справочника элементов из библиотеки mendeleev.

Скрипт запускается разработчиком один раз. Результат — JSON в
alchemy/data/elements.json. Само приложение этот скрипт не использует и в
mendeleev не нуждается: работает на собственном снимке данных.

Запуск:
    python tools/build_elements.py
"""

import json
import os
import sys

try:
    from mendeleev import element
    from mendeleev.fetch import fetch_table
except ImportError:
    print("Требуется mendeleev: pip install mendeleev")
    sys.exit(1)

# Категории в терминах mendeleev (серии элементов) -> русские подписи
CATEGORY_RU = {
    "alkali metals": "Щелочной металл",
    "alkaline earth metals": "Щёлочноземельный металл",
    "transition metals": "Переходный металл",
    "poor metals": "Постпереходный металл",
    "metalloids": "Полуметалл",
    "nonmetals": "Неметалл",
    "halogens": "Галоген",
    "noble gases": "Благородный газ",
    "lanthanides": "Лантаноид",
    "actinides": "Актиноид",
    "unknown, probably transition metal": "Переходный металл (предположительно)",
    "unknown, probably post-transition metal": "Постпереходный (предположительно)",
    "unknown, probably metalloid": "Полуметалл (предположительно)",
    "unknown, predicted to be noble gas": "Благородный газ (предсказан)",
    "unknown, probably other nonmetal": "Неметалл (предположительно)",
}

# Нормализация: единственное число, как в русской традиции для подписи
CATEGORY_RU = {k: v for k, v in CATEGORY_RU.items()}

# Цвета категорий для таблицы
CATEGORY_COLOR = {
    "Щелочной металл": "#e74c3c",
    "Щёлочноземельный металл": "#e67e22",
    "Переходный металл": "#f1c40f",
    "Постпереходный металл": "#2ecc71",
    "Полуметалл": "#1abc9c",
    "Неметалл": "#3498db",
    "Галоген": "#9b59b6",
    "Благородный газ": "#8e44ad",
    "Лантаноид": "#ff9ff3",
    "Актиноид": "#feca57",
}

# Позиция в короткопериодном/длиннопериодном варианте таблицы.
# Лантаноиды и актиноиды выносятся в отдельные строки.
# Элементы, для которых IUPAC не приводит стандартную атомную массу
# (нет устойчивых изотопов либо нет земной изотопной распространённости).
# Для них в таблице стоит масса наиболее долгоживущего изотопа — это надо
# показывать пользователю явно, иначе расчёт молярной массы выглядит точнее,
# чем он есть.
NO_STANDARD_MASS = frozenset(
    # Tc и Pm — нет устойчивых изотопов;
    # Po..Ac — радиоактивные без устойчивых изотопов;
    # Np и тяжелее — только искусственные, масса наиболее долгоживущего изотопа.
    # Th, Pa и U стандартную атомную массу имеют, они сюда не входят.
    {43, 61} | set(range(84, 90)) | set(range(93, 119))
)

# Неопределённости стандартных атомных масс по CIAAW (IUPAC).
# В mendeleev эти поля для многих элементов пусты, поэтому таблица задана
# явно — иначе погрешность молярной массы молча занижается до нуля.
CIAAW_UNCERTAINTY = {
    "H": 0.0002, "He": 0.0002, "Li": 0.06, "Be": 0.0003, "B": 0.007,
    "C": 0.002, "N": 0.0002, "O": 0.0003, "F": 0.0005, "Ne": 0.0006,
    "Na": 0.0002, "Mg": 0.0002, "Al": 0.0005, "Si": 0.001, "P": 0.0005,
    "S": 0.002, "Cl": 0.001, "Ar": 0.0005, "K": 0.0002, "Ca": 0.0004,
    "Sc": 0.0001, "Ti": 0.0001, "V": 0.0001, "Cr": 0.0001, "Mn": 0.0001,
    "Fe": 0.0001, "Co": 0.0001, "Ni": 0.0001, "Cu": 0.0001, "Zn": 0.0001,
    "Ga": 0.0001, "Ge": 0.0001, "As": 0.0001, "Se": 0.0001, "Br": 0.0003,
    "Kr": 0.0003, "Rb": 0.0001, "Sr": 0.0001, "Y": 0.0001, "Zr": 0.0001,
    "Nb": 0.0001, "Mo": 0.0001, "Ru": 0.0001, "Rh": 0.0001, "Pd": 0.0001,
    "Ag": 0.0001, "Cd": 0.0001, "In": 0.0001, "Sn": 0.0001, "Sb": 0.0001,
    "Te": 0.0001, "I": 0.0001, "Xe": 0.0001, "Cs": 0.0001, "Ba": 0.0001,
    "La": 0.0001, "Ce": 0.0001, "Pr": 0.0001, "Nd": 0.0001, "Sm": 0.0001,
    "Eu": 0.0001, "Gd": 0.0001, "Tb": 0.0001, "Dy": 0.0001, "Ho": 0.0001,
    "Er": 0.0001, "Tm": 0.0001, "Yb": 0.0001, "Lu": 0.0001, "Hf": 0.0001,
    "Ta": 0.0001, "W": 0.0001, "Re": 0.0001, "Os": 0.0001, "Ir": 0.0001,
    "Pt": 0.0001, "Au": 0.0001, "Hg": 0.0001, "Tl": 0.0002, "Pb": 0.0001,
    "Bi": 0.0001,
    # Th, Pa, U имеют стандартную атомную массу, хотя и радиоактивны
    "Th": 0.0004, "Pa": 0.0001, "U": 0.00003,
}


def layout_position(z: int) -> tuple:
    """Вернуть (строка, столбец) для таблицы 18 столбцов."""
    if z == 1:
        return (1, 1)
    if z == 2:
        return (1, 18)
    if 3 <= z <= 4:
        return (2, z - 2)
    if 5 <= z <= 10:
        return (2, z + 8)
    if 11 <= z <= 12:
        return (3, z - 10)
    if 13 <= z <= 18:
        return (3, z)
    if 19 <= z <= 36:
        return (4, z - 18)
    if 37 <= z <= 54:
        return (5, z - 36)
    if 55 <= z <= 56:
        return (6, z - 54)
    # Лантаноиды 57-71 — отдельная строка 9
    if 57 <= z <= 71:
        return (9, z - 57 + 3)
    if 72 <= z <= 86:
        return (6, z - 68)
    if 87 <= z <= 88:
        return (7, z - 86)
    # Актиноиды 89-103 — отдельная строка 10
    if 89 <= z <= 103:
        return (10, z - 89 + 3)
    if 104 <= z <= 118:
        return (7, z - 100)
    return (0, 0)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(os.path.dirname(here), "alchemy", "data")
    os.makedirs(out_dir, exist_ok=True)

    # Точный словарь русских названий — приоритетный источник
    names_ru_path = os.path.join(out_dir, "names_ru.json")
    try:
        with open(names_ru_path, encoding="utf-8") as f:
            names_ru = json.load(f)
    except Exception:
        names_ru = {}

    # Таблица с русскими названиями из mendeleev — резервный источник
    try:
        ru_table = fetch_table("elements", cache=True)
    except Exception:
        ru_table = None

    elements = {}
    for z in range(1, 119):
        try:
            e = element(z)
        except Exception as exc:
            print(f"  пропуск Z={z}: {exc}")
            continue

        row, col = layout_position(z)
        cat_en = (e.series or "").lower() if getattr(e, "series", None) else ""
        cat_ru = CATEGORY_RU.get(cat_en, cat_en or "—")

        # Русское название элемента: словарь -> mendeleev -> английское
        name_ru = names_ru.get(e.symbol)
        if not name_ru and ru_table is not None:
            try:
                row_ru = ru_table[ru_table["atomic_number"] == z]
                if len(row_ru):
                    for column in ("name_ru", "russian_name"):
                        if column in row_ru.columns:
                            val = row_ru.iloc[0][column]
                            if isinstance(val, str) and val:
                                name_ru = val
                                break
            except Exception:
                pass

        ionization = []
        try:
            for ie in e.ionization_energies or []:
                ionization.append(round(float(ie.energy), 6))
        except Exception:
            pass

        ox_states = []
        try:
            ox_states = sorted({int(s.oxidation_state) for s in (e.oxidation_states or [])})
        except Exception:
            pass

        isotopes = []
        try:
            for iso in e.isotopes or []:
                isotopes.append({
                    "mass_number": int(iso.mass_number),
                    "abundance": (round(float(iso.abundance), 8)
                                  if iso.abundance is not None else None),
                    "mass": (round(float(iso.mass), 8) if iso.mass is not None else None),
                    "half_life": (float(iso.half_life) if iso.half_life is not None else None),
                    "half_life_unit": getattr(iso, "half_life_unit", None),
                    "is_radioactive": bool(getattr(iso, "is_radioactive", False)),
                })
        except Exception:
            pass
        # Стабильные изотопы — вперёд, по массовому числу
        isotopes.sort(key=lambda i: (i["abundance"] is None, i["mass_number"]))

        def num(attr, digits=6):
            v = getattr(e, attr, None)
            if v is None:
                return None
            try:
                return round(float(v), digits)
            except (TypeError, ValueError):
                return None

        # Неопределённость массы имеет смысл только при наличии стандартной
        # атомной массы. Иначе поле остаётся пустым, и приложение честно
        # показывает, что точность здесь другая.
        if z in NO_STANDARD_MASS:
            mass_uncertainty = None
        else:
            mass_uncertainty = num("atomic_weight_uncertainty", 8)
            if mass_uncertainty is None:
                # Данные CIAAW имеют приоритет как более полные
                mass_uncertainty = CIAAW_UNCERTAINTY.get(e.symbol)

        elements[str(z)] = {
            "z": z,
            "symbol": e.symbol,
            "name_ru": name_ru or e.name,
            "name_en": e.name,
            "mass": round(float(e.atomic_weight), 8) if e.atomic_weight else None,
            "mass_uncertainty": mass_uncertainty,
            "is_radioactive": bool(getattr(e, "is_radioactive", False)),
            "category": cat_ru,
            "category_color": CATEGORY_COLOR.get(cat_ru, "#95a5a6"),
            "group": int(e.group_id) if getattr(e, "group_id", None) else None,
            "period": int(e.period) if getattr(e, "period", None) else None,
            "block": getattr(e, "block", None),
            "row": row,
            "col": col,
            "electron_config": getattr(e, "econf", None),
            "electronegativity": num("en_pauling", 4),
            "density": num("density", 6),
            "melting_point": num("melting_point", 4),
            "boiling_point": num("boiling_point", 4),
            "fusion_heat": num("fusion_heat", 6),
            "evaporation_heat": num("evaporation_heat", 6),
            "specific_heat": num("specific_heat_capacity", 6),
            "molar_heat_capacity": num("molar_heat_capacity", 6),
            "thermal_conductivity": num("thermal_conductivity", 6),
            "heat_of_formation": num("heat_of_formation", 6),
            "atomic_radius": num("atomic_radius", 4),
            "covalent_radius": num("covalent_radius_cordero", 4),
            "vdw_radius": num("vdw_radius", 4),
            "electron_affinity": num("electron_affinity", 6),
            "ionization_energies": ionization,
            "oxidation_states": ox_states,
            "isotopes": isotopes,
        }

    path = os.path.join(out_dir, "elements.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "source": "mendeleev 1.1.0 (данные IUPAC/CIAAW)",
            "generated_by": "tools/build_elements.py",
            "category_colors": CATEGORY_COLOR,
            "elements": elements,
        }, f, ensure_ascii=False, indent=1)

    size_kb = os.path.getsize(path) / 1024
    print(f"Готово: {path}")
    print(f"Элементов: {len(elements)}, размер: {size_kb:.0f} КБ")

    missing_mass = [v["symbol"] for v in elements.values() if v["mass"] is None]
    if missing_mass:
        print(f"Без атомной массы: {missing_mass}")


if __name__ == "__main__":
    main()
