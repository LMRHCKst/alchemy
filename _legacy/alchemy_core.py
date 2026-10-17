import math
import re
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

import sys
import os

# Фикс путей для работы внутри папки с EXE
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS # Для OneFile
    current_dir = os.path.dirname(sys.executable) # Для OneDir (наш случай)
    sys.path.append(current_dir)
    # Принудительно задаем путь к базе данных Mendeleev
    os.environ['MENDELEEV_DATA_DIR'] = os.path.join(current_dir, 'mendeleev')


# Подключение профессиональных библиотек
HAS_MENDELEEV = False
HAS_CHEMPY = False
try:
    from mendeleev import element

    HAS_MENDELEEV = True
except ImportError:
    pass
try:
    from chempy import balance_stoichiometry, Substance
    from chempy.util import periodic

    HAS_CHEMPY = True
except ImportError:
    pass

# Глобальные Константы
CONSTANTS = {
    'R': 8.314,  # Дж/(моль·К)
    'R_atm': 0.08206,  # Л·атм/(моль·К)
    'F': 96485,  # Кл/моль
    'NA': 6.022e23,  # 1/моль
    'c': 2.998e8,  # м/с
    'h': 6.626e-34  # Дж·с
}

# Кэш для UI (чтобы таблица рисовалась быстро)
LAYOUT_CACHE = {
    'H': [1, 1, 1, 'nonmetal'], 'He': [2, 18, 1, 'noble'],
    'Li': [3, 1, 2, 'alkali'], 'Be': [4, 2, 2, 'alkaline'],
    'B': [5, 13, 2, 'metalloid'], 'C': [6, 14, 2, 'nonmetal'], 'N': [7, 15, 2, 'nonmetal'], 'O': [8, 16, 2, 'nonmetal'],
    'F': [9, 17, 2, 'halogen'], 'Ne': [10, 18, 2, 'noble'],
    'Na': [11, 1, 3, 'alkali'], 'Mg': [12, 2, 3, 'alkaline'],
    'Al': [13, 13, 3, 'post-transition'], 'Si': [14, 14, 3, 'metalloid'], 'P': [15, 15, 3, 'nonmetal'],
    'S': [16, 16, 3, 'nonmetal'], 'Cl': [17, 17, 3, 'halogen'], 'Ar': [18, 18, 3, 'noble'],
    'K': [19, 1, 4, 'alkali'], 'Ca': [20, 2, 4, 'alkaline'],
    'Sc': [21, 3, 4, 'transition'], 'Ti': [22, 4, 4, 'transition'], 'V': [23, 5, 4, 'transition'],
    'Cr': [24, 6, 4, 'transition'], 'Mn': [25, 7, 4, 'transition'], 'Fe': [26, 8, 4, 'transition'],
    'Co': [27, 9, 4, 'transition'], 'Ni': [28, 10, 4, 'transition'], 'Cu': [29, 11, 4, 'transition'],
    'Zn': [30, 12, 4, 'transition'],
    'Ga': [31, 13, 4, 'post-transition'], 'Ge': [32, 14, 4, 'metalloid'], 'As': [33, 15, 4, 'metalloid'],
    'Se': [34, 16, 4, 'nonmetal'], 'Br': [35, 17, 4, 'halogen'], 'Kr': [36, 18, 4, 'noble'],
    'Rb': [37, 1, 5, 'alkali'], 'Sr': [38, 2, 5, 'alkaline'],
    'Y': [39, 3, 5, 'transition'], 'Zr': [40, 4, 5, 'transition'], 'Nb': [41, 5, 5, 'transition'],
    'Mo': [42, 6, 5, 'transition'], 'Tc': [43, 7, 5, 'transition'], 'Ru': [44, 8, 5, 'transition'],
    'Rh': [45, 9, 5, 'transition'], 'Pd': [46, 10, 5, 'transition'], 'Ag': [47, 11, 5, 'transition'],
    'Cd': [48, 12, 5, 'transition'],
    'In': [49, 13, 5, 'post-transition'], 'Sn': [50, 14, 5, 'post-transition'], 'Sb': [51, 15, 5, 'metalloid'],
    'Te': [52, 16, 5, 'metalloid'], 'I': [53, 17, 5, 'halogen'], 'Xe': [54, 18, 5, 'noble'],
    'Cs': [55, 1, 6, 'alkali'], 'Ba': [56, 2, 6, 'alkaline'],
    'La': [57, 3, 6, 'lanthanide'], 'Ce': [58, 3, 6, 'lanthanide'], 'Pr': [59, 3, 6, 'lanthanide'],
    'Nd': [60, 3, 6, 'lanthanide'], 'Pm': [61, 3, 6, 'lanthanide'], 'Sm': [62, 3, 6, 'lanthanide'],
    'Eu': [63, 3, 6, 'lanthanide'], 'Gd': [64, 3, 6, 'lanthanide'], 'Tb': [65, 3, 6, 'lanthanide'],
    'Dy': [66, 3, 6, 'lanthanide'], 'Ho': [67, 3, 6, 'lanthanide'], 'Er': [68, 3, 6, 'lanthanide'],
    'Tm': [69, 3, 6, 'lanthanide'], 'Yb': [70, 3, 6, 'lanthanide'], 'Lu': [71, 3, 6, 'lanthanide'],
    'Hf': [72, 4, 6, 'transition'], 'Ta': [73, 5, 6, 'transition'], 'W': [74, 6, 6, 'transition'],
    'Re': [75, 7, 6, 'transition'], 'Os': [76, 8, 6, 'transition'], 'Ir': [77, 9, 6, 'transition'],
    'Pt': [78, 10, 6, 'transition'], 'Au': [79, 11, 6, 'transition'], 'Hg': [80, 12, 6, 'transition'],
    'Tl': [81, 13, 6, 'post-transition'], 'Pb': [82, 14, 6, 'post-transition'], 'Bi': [83, 15, 6, 'post-transition'],
    'Po': [84, 16, 6, 'metalloid'], 'At': [85, 17, 6, 'halogen'], 'Rn': [86, 18, 6, 'noble'],
    'Fr': [87, 1, 7, 'alkali'], 'Ra': [88, 2, 7, 'alkaline'],
    'Ac': [89, 3, 7, 'actinide'], 'Th': [90, 3, 7, 'actinide'], 'Pa': [91, 3, 7, 'actinide'],
    'U': [92, 3, 7, 'actinide'], 'Np': [93, 3, 7, 'actinide'], 'Pu': [94, 3, 7, 'actinide'],
    'Am': [95, 3, 7, 'actinide'], 'Cm': [96, 3, 7, 'actinide'], 'Bk': [97, 3, 7, 'actinide'],
    'Cf': [98, 3, 7, 'actinide'], 'Es': [99, 3, 7, 'actinide'], 'Fm': [100, 3, 7, 'actinide'],
    'Md': [101, 3, 7, 'actinide'], 'No': [102, 3, 7, 'actinide'], 'Lr': [103, 3, 7, 'actinide'],
    'Rf': [104, 4, 7, 'transition'], 'Db': [105, 5, 7, 'transition'], 'Sg': [106, 6, 7, 'transition'],
    'Bh': [107, 7, 7, 'transition'], 'Hs': [108, 8, 7, 'transition'], 'Mt': [109, 9, 7, 'transition'],
    'Ds': [110, 10, 7, 'transition'], 'Rg': [111, 11, 7, 'transition'], 'Cn': [112, 12, 7, 'transition'],
    'Nh': [113, 13, 7, 'post-transition'], 'Fl': [114, 14, 7, 'post-transition'], 'Mc': [115, 15, 7, 'post-transition'],
    'Lv': [116, 16, 7, 'post-transition'], 'Ts': [117, 17, 7, 'halogen'], 'Og': [118, 18, 7, 'noble']
}

ELEMENTS_RU = {
    'H': 'Водород', 'He': 'Гелий', 'Li': 'Литий', 'Be': 'Бериллий', 'B': 'Бор', 'C': 'Углерод', 'N': 'Азот',
    'O': 'Кислород', 'F': 'Фтор', 'Ne': 'Неон', 'Na': 'Натрий', 'Mg': 'Магний', 'Al': 'Алюминий', 'Si': 'Кремний',
    'P': 'Фосфор', 'S': 'Сера', 'Cl': 'Хлор', 'Ar': 'Аргон', 'K': 'Калий', 'Ca': 'Кальций', 'Sc': 'Скандий',
    'Ti': 'Титан', 'V': 'Ванадий', 'Cr': 'Хром', 'Mn': 'Марганец', 'Fe': 'Железо', 'Co': 'Кобальт', 'Ni': 'Никель',
    'Cu': 'Медь', 'Zn': 'Цинк', 'Ga': 'Галлий', 'Ge': 'Германий', 'As': 'Мышьяк', 'Se': 'Селен', 'Br': 'Бром',
    'Kr': 'Криптон', 'Rb': 'Рубидий', 'Sr': 'Стронций', 'Y': 'Иттрий', 'Zr': 'Цирконий', 'Nb': 'Ниобий',
    'Mo': 'Молибден', 'Tc': 'Технеций', 'Ru': 'Рутений', 'Rh': 'Родий', 'Pd': 'Палладий', 'Ag': 'Серебро',
    'Cd': 'Кадмий',
    'In': 'Индий', 'Sn': 'Олово', 'Sb': 'Сурьма', 'Te': 'Теллур', 'I': 'Йод', 'Xe': 'Ксенон', 'Cs': 'Цезий',
    'Ba': 'Барий', 'La': 'Лантан', 'Ce': 'Церий', 'Pr': 'Празеодим', 'Nd': 'Неодим', 'Pm': 'Прометий',
    'Sm': 'Самарий', 'Eu': 'Европий', 'Gd': 'Гадолиний', 'Tb': 'Тербий', 'Dy': 'Диспрозий', 'Ho': 'Гольмий',
    'Er': 'Эрбий', 'Tm': 'Тулий', 'Yb': 'Иттербий', 'Lu': 'Лютеций', 'Hf': 'Гафний', 'Ta': 'Тантал', 'W': 'Вольфрам',
    'Re': 'Рений', 'Os': 'Осмий', 'Ir': 'Иридий', 'Pt': 'Платина', 'Au': 'Золото', 'Hg': 'Ртуть', 'Tl': 'Таллий',
    'Pb': 'Свинец', 'Bi': 'Висмут', 'Po': 'Полоний', 'At': 'Астат', 'Rn': 'Радон', 'Fr': 'Франций', 'Ra': 'Радий',
    'Ac': 'Актиний', 'Th': 'Торий', 'Pa': 'Протактиний', 'U': 'Уран', 'Np': 'Нептуний', 'Pu': 'Плутоний',
    'Am': 'Америций', 'Cm': 'Кюрий', 'Bk': 'Берклий', 'Cf': 'Калифорний', 'Es': 'Эйнштейний', 'Fm': 'Фермий',
    'Md': 'Менделевий', 'No': 'Нобелий', 'Lr': 'Лоуренсий', 'Rf': 'Резерфордий', 'Db': 'Дубний', 'Sg': 'Сиборгий',
    'Bh': 'Борий', 'Hs': 'Хассий', 'Mt': 'Мейтнерий', 'Ds': 'Дармштадтий', 'Rg': 'Рентгений', 'Cn': 'Коперниций',
    'Nh': 'Нихоний', 'Fl': 'Флеровий', 'Mc': 'Московий', 'Lv': 'Ливерморий', 'Ts': 'Теннессин', 'Og': 'Оганесон'
}

# Встроенная база атомных весов (IUPAC 2023, г/моль)
ATOMIC_WEIGHTS = {
    'H': 1.008, 'He': 4.003, 'Li': 6.941, 'Be': 9.012, 'B': 10.81,
    'C': 12.011, 'N': 14.007, 'O': 15.999, 'F': 18.998, 'Ne': 20.180,
    'Na': 22.990, 'Mg': 24.305, 'Al': 26.982, 'Si': 28.086, 'P': 30.974,
    'S': 32.065, 'Cl': 35.453, 'Ar': 39.948, 'K': 39.098, 'Ca': 40.078,
    'Sc': 44.956, 'Ti': 47.867, 'V': 50.942, 'Cr': 51.996, 'Mn': 54.938,
    'Fe': 55.845, 'Co': 58.933, 'Ni': 58.693, 'Cu': 63.546, 'Zn': 65.38,
    'Ga': 69.723, 'Ge': 72.630, 'As': 74.922, 'Se': 78.971, 'Br': 79.904,
    'Kr': 83.798, 'Rb': 85.468, 'Sr': 87.62, 'Y': 88.906, 'Zr': 91.224,
    'Nb': 92.906, 'Mo': 95.95, 'Tc': 98.0, 'Ru': 101.07, 'Rh': 102.91,
    'Pd': 106.42, 'Ag': 107.87, 'Cd': 112.41, 'In': 114.82, 'Sn': 118.71,
    'Sb': 121.76, 'Te': 127.60, 'I': 126.90, 'Xe': 131.29, 'Cs': 132.91,
    'Ba': 137.33, 'La': 138.91, 'Ce': 140.12, 'Pr': 140.91, 'Nd': 144.24,
    'Pm': 145.0, 'Sm': 150.36, 'Eu': 151.96, 'Gd': 157.25, 'Tb': 158.93,
    'Dy': 162.50, 'Ho': 164.93, 'Er': 167.26, 'Tm': 168.93, 'Yb': 173.05,
    'Lu': 174.97, 'Hf': 178.49, 'Ta': 180.95, 'W': 183.84, 'Re': 186.21,
    'Os': 190.23, 'Ir': 192.22, 'Pt': 195.08, 'Au': 196.97, 'Hg': 200.59,
    'Tl': 204.38, 'Pb': 207.2, 'Bi': 208.98, 'Po': 209.0, 'At': 210.0,
    'Rn': 222.0, 'Fr': 223.0, 'Ra': 226.0, 'Ac': 227.0, 'Th': 232.04,
    'Pa': 231.04, 'U': 238.03, 'Np': 237.0, 'Pu': 244.0, 'Am': 243.0,
    'Cm': 247.0, 'Bk': 247.0, 'Cf': 251.0, 'Es': 252.0, 'Fm': 257.0,
    'Md': 258.0, 'No': 259.0, 'Lr': 262.0, 'Rf': 267.0, 'Db': 270.0,
    'Sg': 271.0, 'Bh': 270.0, 'Hs': 277.0, 'Mt': 278.0, 'Ds': 281.0,
    'Rg': 282.0, 'Cn': 285.0, 'Nh': 286.0, 'Fl': 289.0, 'Mc': 290.0,
    'Lv': 293.0, 'Ts': 294.0, 'Og': 294.0
}

def _get_atomic_weight(element_symbol):
    """Получить атомную массу элемента. Приоритет: mendeleev > chempy > встроенная база."""
    if HAS_MENDELEEV:
        try:
            return element(element_symbol).atomic_weight
        except Exception:
            pass
    if HAS_CHEMPY:
        try:
            from chempy.util import periodic
            return periodic.table[element_symbol].mass
        except Exception:
            pass
    if element_symbol in ATOMIC_WEIGHTS:
        return ATOMIC_WEIGHTS[element_symbol]
    raise ValueError(f"Неизвестный элемент: {element_symbol}")

CATEGORIES_RU = {
    'alkali': 'Щелочной металл', 'alkaline': 'Щелочноземельный', 'transition': 'Переходный металл',
    'post-transition': 'Пост-переходный', 'metalloid': 'Полуметалл', 'nonmetal': 'Неметалл',
    'halogen': 'Галоген', 'noble': 'Благородный газ', 'lanthanide': 'Лантаноид', 'actinide': 'Актиноид'
}

CATEGORY_COLORS = {
    'alkali': '#e74c3c', 'alkaline': '#e67e22', 'transition': '#f1c40f',
    'post-transition': '#2ecc71', 'metalloid': '#1abc9c', 'nonmetal': '#3498db',
    'halogen': '#9b59b6', 'noble': '#8e44ad', 'lanthanide': '#ffb3e6', 'actinide': '#ffccf2'
}


# Менеджеры (Library, History, Context)
class LibraryManager:
    FILE_NAME = "alchemy_library.json"
    _data = {}

    @classmethod
    def load(cls):
        if not os.path.exists(cls.FILE_NAME):
            cls._create_default()
        try:
            with open(cls.FILE_NAME, "r", encoding="utf-8") as f:
                cls._data = json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки библиотеки: {e}")
            cls._create_default()
            with open(cls.FILE_NAME, "r", encoding="utf-8") as f:
                cls._data = json.load(f)

    @classmethod
    def get_data(cls):
        if not cls._data:
            cls.load()
        return cls._data

    @classmethod
    def add_entry(cls, category, entry):
        if category not in cls._data:
            cls._data[category] = []
        cls._data[category].append(entry)
        with open(cls.FILE_NAME, "w", encoding="utf-8") as f:
            json.dump(cls._data, f, indent=4, ensure_ascii=False)

    @classmethod
    def _create_default(cls):
        default = {
            "Растворители": [
                {"Название": "Вода", "Формула": "H2O", "T.кип": "100"},
                {"Название": "Этанол", "Формула": "C2H5OH", "T.кип": "78.4"},
                {"Название": "Ацетон", "Формула": "C3H6O", "T.кип": "56.0"}
            ],
            "Кислоты": [
                {"Название": "Соляная", "Формула": "HCl", "pKa": "-6.3"},
                {"Название": "Уксусная", "Формула": "CH3COOH", "pKa": "4.75"}
            ],
            "Щелочи": [
                {"Название": "Гидроксид натрия", "Формула": "NaOH", "pKb": "0.2"},
                {"Название": "Гидроксид калия", "Формула": "KOH", "pKb": "0.5"}
            ]
        }
        with open(cls.FILE_NAME, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4, ensure_ascii=False)


class HistoryManager:
    _log = []

    @classmethod
    def add(cls, action: str, result: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {"time": timestamp, "action": action, "result": result}
        cls._log.insert(0, entry)
        if len(cls._log) > 100:
            cls._log.pop()
        ContextManager.set(result, action)

    @classmethod
    def get_log(cls):
        return cls._log

    @classmethod
    def set_log(cls, l):
        cls._log = l

    @classmethod
    def clear(cls):
        cls._log = []


class ContextManager:
    _current_val = "-"
    _desc = ""
    _listeners = []

    @classmethod
    def set(cls, val, desc=""):
        cls._current_val = str(val)
        cls._desc = desc
        for cb in cls._listeners:
            cb(cls._current_val, cls._desc)

    @classmethod
    def get(cls):
        return cls._current_val

    @classmethod
    def register_listener(cls, callback):
        cls._listeners.append(callback)


# ПАРСЕРЫ И КАЛЬКУЛЯТОРЫ (На базе ChemPy и Mendeleev)
class FormulaParser:
    @staticmethod
    def calculate_mass(formula_str: str) -> float:
        """
        Использует ChemPy для точного расчета молярной массы.
        Если ChemPy нет, пытается использовать ручной парсер (legacy).
        """
        if not formula_str or not formula_str.strip():
            return 0.0

        formula_str = formula_str.strip()

        # 1. Попытка через ChemPy (самый надежный способ)
        if HAS_CHEMPY:
            try:
                # ChemPy может иметь проблемы с "CuSO4*5H2O", превратим его в композицию
                if '*' in formula_str:
                    parts = formula_str.split('*')
                    main_sub = Substance.from_formula(parts[0].strip())
                    # Обработка гидрата (например 5H2O)
                    hydrate_part = parts[1].strip()
                    # Извлекаем множитель
                    match = re.match(r'^(\d+)?(.*)$', hydrate_part)
                    factor = 1
                    sub_str = hydrate_part
                    if match:
                        f_str, sub_str = match.groups()
                        if f_str:
                            factor = int(f_str)
                        else:
                            sub_str = hydrate_part

                    hydrate_sub = Substance.from_formula(sub_str.strip())
                    total_mass = main_sub.mass + (hydrate_sub.mass * factor)
                    return total_mass
                else:
                    s = Substance.from_formula(formula_str)
                    return s.mass
            except Exception as e:
                print(f"ChemPy error: {e}")
                pass  # Если ChemPy не справился, идем дальше

        # 2. Fallback (для простых случаев или если библиотеки нет)
        if HAS_MENDELEEV:
            try:
                comp = FormulaParser._parse_molecule_legacy(formula_str)
                total = 0.0
                for el, count in comp.items():
                    total += element(el).atomic_weight * count
                return total
            except Exception as e:
                print(f"Mendeleev fallback error: {e}")
                pass

        # 3. Встроенная база атомных весов (последний resort)
        return FormulaParser._calculate_mass_builtin(formula_str)

    @staticmethod
    def _calculate_mass_builtin(formula_str: str) -> float:
        """Расчёт молярной массы с использованием встроенной базы атомных весов.

        Работает без внешних библиотек (mendeleev/chempy).
        """
        try:
            comp = FormulaParser._parse_molecule_legacy(formula_str)
            if not comp:
                return 0.0
            total = 0.0
            for el, count in comp.items():
                aw = _get_atomic_weight(el)
                total += aw * count
            return total
        except Exception:
            return 0.0

    @staticmethod
    def _parse_molecule_legacy(f: str) -> Dict[str, float]:
        """Старый ручной парсер на случай отсутствия ChemPy"""
        try:
            f = f.replace(" ", "")
            # Обработка гидратов (простая)
            if '*' in f:
                parts = f.split('*')
                main = FormulaParser._parse_molecule_legacy(parts[0])
                match = re.match(r'^(\d+)(.*)$', parts[1])
                mult = int(match.group(1)) if match and match.group(1) else 1
                sub = parts[1][len(str(mult)):] if match else parts[1]
                hydrate = FormulaParser._parse_molecule_legacy(sub)
                for k, v in hydrate.items():
                    main[k] = main.get(k, 0) + v * mult
                return main

            # Обработка скобок
            while '(' in f:
                m = re.search(r'\(([A-Za-z0-9]+)\)(\d*)', f)
                if m:
                    cont, mult_str = m.group(1), m.group(2)
                    mult = int(mult_str) if mult_str else 1
                    inner = FormulaParser._parse_molecule_legacy(cont)
                    expanded_parts = []
                    for k, v in inner.items():
                        expanded_parts.append(f"{k}{int(v * mult) if v * mult == int(v * mult) else v * mult}")
                    expanded = ''.join(expanded_parts)
                    f = f.replace(m.group(0), expanded, 1)
                else:
                    break

            comp = {}
            for el, cnt in re.findall(r'([A-Z][a-z]?)(\d*\.?\d*)', f):
                count = float(cnt) if cnt else 1.0
                comp[el] = comp.get(el, 0) + count
            return comp
        except Exception as e:
            print(f"Legacy parser error: {e}")
            return {}

    # ============ НОВЫЕ СТАТИЧЕСКИЕ МЕТОДЫ ============

    @staticmethod
    def get_composition(formula_str: str) -> Dict[str, float]:
        """Возвращает словарь количеств элементов в формуле.

        Пример: 'H2O' -> {'H': 2.0, 'O': 1.0}

        Args:
            formula_str: Химическая формула

        Returns:
            Словарь {элемент: количество}
        """
        if not formula_str or not formula_str.strip():
            raise ValueError("Формула не может быть пустой")
        comp = FormulaParser._parse_molecule_legacy(formula_str.strip())
        if not comp:
            raise ValueError(f"Не удалось разобрать формулу: {formula_str}")
        return comp

    @staticmethod
    def get_mass_percentages(formula_str: str) -> Dict[str, float]:
        """Вычисляет массовые проценты каждого элемента в формуле.

        Пример: 'H2O' -> {'H': 11.19, 'O': 88.81}

        Args:
            formula_str: Химическая формула

        Returns:
            Словарь {элемент: массовый_процент}
        """
        comp = FormulaParser.get_composition(formula_str)
        molar_mass = FormulaParser.calculate_mass(formula_str)
        if molar_mass <= 0:
            raise ValueError(f"Не удалось вычислить молярную массу для: {formula_str}")

        percentages = {}
        total = 0.0
        for el, count in comp.items():
            aw = _get_atomic_weight(el)
            mass_contribution = aw * count
            percentages[el] = mass_contribution
            total += mass_contribution

        for el in percentages:
            percentages[el] = round(percentages[el] / total * 100, 2)

        return percentages

    @staticmethod
    def empirical_formula_from_percentages(percentages: Dict[str, float]) -> str:
        """Определяет простейшую (эмпирическую) формулу по массовым процентам.

        Пример: {'H': 11.19, 'O': 88.81} -> 'H2O'

        Args:
            percentages: Словарь {элемент: массовый_процент}

        Returns:
            Строка эмпирической формулы
        """
        if not percentages:
            raise ValueError("Словарь процентов не может быть пустым")

        total_pct = sum(percentages.values())
        if total_pct <= 0:
            raise ValueError("Сумма массовых процентов должна быть больше нуля")

        # Получаем атомные массы
        atomic_weights = {}
        for el in percentages:
            atomic_weights[el] = _get_atomic_weight(el)

        # Считаем мольные количества
        moles = {}
        for el, pct in percentages.items():
            moles[el] = pct / atomic_weights[el]

        # Находим минимальное значение
        min_moles = min(moles.values())
        if min_moles <= 0:
            raise ValueError("Ошибка: мольное количество не может быть <= 0")

        # Вычисляем отношения
        ratios = {}
        for el, mol in moles.items():
            ratio = mol / min_moles
            # Округляем до ближайшего целого с небольшой допуск
            rounded = round(ratio)
            # Если близко к целому, берём целое; иначе умножаем всё на 2 и пробуем
            if abs(ratio - rounded) < 0.15:
                ratios[el] = rounded
            else:
                ratios[el] = round(ratio * 2)
                # Проверяем, не нужно ли умножить всё на 2
                for el2 in ratios:
                    if ratios[el2] != round(ratio * 2) if el2 == el else ratios[el2]:
                        break

        # Если после округления все нули или есть нули, пробуем масштабирование
        max_ratio = max(ratios.values())
        if max_ratio == 0:
            raise ValueError("Не удалось вычислить эмпирическую формулу")

        # Нормализуем до целых чисел
        def _to_ints(ratios_dict):
            # Пробуем множители 1..10
            for mult in range(1, 11):
                int_dict = {}
                all_ints = True
                for el, r in ratios_dict.items():
                    val = r * mult
                    rounded_val = round(val)
                    if abs(val - rounded_val) < 0.1 and rounded_val > 0:
                        int_dict[el] = rounded_val
                    else:
                        all_ints = False
                        break
                if all_ints:
                    return int_dict
            # Fallback: просто округляем
            return {el: max(1, round(r)) for el, r in ratios_dict.items()}

        # Пересчитаем отношения более точно
        raw_ratios = {el: mol / min_moles for el, mol in moles.items()}
        int_ratios = _to_ints(raw_ratios)

        # Формируем строку формулы
        parts = []
        for el in sorted(int_ratios.keys()):
            count = int_ratios[el]
            if count == 1:
                parts.append(el)
            else:
                parts.append(f"{el}{count}")
        return "".join(parts)

    @staticmethod
    def get_formula_info(formula_str: str) -> Dict[str, Any]:
        """Возвращает полную информацию о формуле.

        Включает: молярную массу, элементный состав, массовые проценты,
        а также анализ степеней окисления (если доступен mendeleev).

        Args:
            formula_str: Химическая формула

        Returns:
            Словарь с полной информацией о формуле
        """
        if not formula_str or not formula_str.strip():
            raise ValueError("Формула не может быть пустой")

        formula_str = formula_str.strip()
        molar_mass = FormulaParser.calculate_mass(formula_str)
        composition = FormulaParser.get_composition(formula_str)
        mass_pct = FormulaParser.get_mass_percentages(formula_str)

        info = {
            "formula": formula_str,
            "molar_mass_g_mol": round(molar_mass, 4),
            "composition": composition,
            "mass_percentages": mass_pct,
            "element_count": len(composition),
            "total_atoms": sum(composition.values()),
        }

        # Анализ степеней окисления (если доступен mendeleev)
        if HAS_MENDELEEV:
            try:
                oxidation_states = {}
                for el in composition:
                    el_obj = element(el)
                    if hasattr(el_obj, 'oxcationStates') and el_obj.oxcationStates:
                        oxidation_states[el] = {
                            "name_ru": ELEMENTS_RU.get(el, el),
                            "possible_oxidation_states": el_obj.oxcationStates,
                        }
                    elif hasattr(el_obj, 'oxidation_states') and el_obj.oxidation_states:
                        oxidation_states[el] = {
                            "name_ru": ELEMENTS_RU.get(el, el),
                            "possible_oxidation_states": el_obj.oxidation_states,
                        }
                if oxidation_states:
                    info["oxidation_states"] = oxidation_states
            except Exception:
                pass

        return info


class SolutionCalculator:
    """Калькулятор расчётов растворов."""

    @staticmethod
    def molarity(mass, mw, volume_l):
        """Вычисляет молярность раствора. C = m / (M * V)

        Args:
            mass: Масса вещества (г)
            mw: Молярная масса (г/моль)
            volume_l: Объём раствора (л)

        Returns:
            Молярность (моль/л)
        """
        if mw <= 0:
            raise ValueError("Молярная масса должна быть больше нуля")
        if volume_l <= 0:
            raise ValueError("Объём должен быть больше нуля")
        return round(mass / (mw * volume_l), 6)

    @staticmethod
    def molality(mass, mw, mass_solvent_kg):
        """Вычисляет моляльность раствора. b = m / (M * m_solvent)

        Args:
            mass: Масса вещества (г)
            mw: Молярная масса (г/моль)
            mass_solvent_kg: Масса растворителя (кг)

        Returns:
            Моляльность (моль/кг)
        """
        if mw <= 0:
            raise ValueError("Молярная масса должна быть больше нуля")
        if mass_solvent_kg <= 0:
            raise ValueError("Масса растворителя должна быть больше нуля")
        return round(mass / (mw * mass_solvent_kg), 6)

    @staticmethod
    def normality(molarity, n_factor):
        """Вычисляет нормальность раствора. N = C * n

        Args:
            molarity: Молярность (моль/л)
            n_factor: Фактор эквивалентности

        Returns:
            Нормальность (моль-экв/л)
        """
        if n_factor <= 0:
            raise ValueError("Фактор эквивалентности должен быть больше нуля")
        return round(molarity * n_factor, 6)

    @staticmethod
    def mass_fraction(mass_solute, mass_solution):
        """Вычисляет массовую долю вещества. w = m_solute / m_solution

        Args:
            mass_solute: Масса растворённого вещества (г)
            mass_solution: Общая масса раствора (г)

        Returns:
            Массовая доля (от 0 до 1)
        """
        if mass_solution <= 0:
            raise ValueError("Общая масса раствора должна быть больше нуля")
        if mass_solute < 0:
            raise ValueError("Масса растворённого вещества не может быть отрицательной")
        if mass_solute > mass_solution:
            raise ValueError("Масса растворённого вещества не может превышать массу раствора")
        return round(mass_solute / mass_solution, 6)

    @staticmethod
    def mole_fraction(moles_solute, moles_solvent):
        """Вычисляет мольную долю растворённого вещества. x = n_solute / (n_solute + n_solvent)

        Args:
            moles_solute: Количество вещества растворённого (моль)
            moles_solvent: Количество вещества растворителя (моль)

        Returns:
            Мольная доля растворённого вещества (от 0 до 1)
        """
        total = moles_solute + moles_solvent
        if total <= 0:
            raise ValueError("Сумма количеств веществ должна быть больше нуля")
        return round(moles_solute / total, 6)

    @staticmethod
    def dilution_c1v1_c2v2(c1=None, v1=None, c2=None, v2=None):
        """Решает уравнение разбавления C1*V1 = C2*V2 для одной неизвестной.

        Args:
            c1: Начальная концентрация (моль/л)
            v1: Начальный объём (л)
            c2: Конечная концентрация (моль/л)
            v2: Конечный объём (л)

        Returns:
            Кортеж (имя_параметра, значение)
        """
        params = {'c1': c1, 'v1': v1, 'c2': c2, 'v2': v2}
        none_params = [k for k, v in params.items() if v is None]

        if len(none_params) != 1:
            raise ValueError("Должна быть указана ровно одна неизвестная величина (None)")

        unknown = none_params[0]

        if unknown == 'c1':
            if v1 is None or c2 is None or v2 is None or v1 <= 0 or v2 <= 0:
                raise ValueError("Недостаточно данных или деление на ноль")
            result = (c2 * v2) / v1
        elif unknown == 'v1':
            if c1 is None or c2 is None or v2 is None or c1 <= 0:
                raise ValueError("Недостаточно данных или деление на ноль")
            result = (c2 * v2) / c1
        elif unknown == 'c2':
            if c1 is None or v1 is None or v2 is None or v2 <= 0:
                raise ValueError("Недостаточно данных или деление на ноль")
            result = (c1 * v1) / v2
        elif unknown == 'v2':
            if c1 is None or v1 is None or c2 is None or c2 <= 0:
                raise ValueError("Недостаточно данных или деление на ноль")
            result = (c1 * v1) / c2
        else:
            raise ValueError(f"Неизвестный параметр: {unknown}")

        return (unknown, round(result, 6))

    @staticmethod
    def mixing_concentrations(c1, v1, c2, v2):
        """Вычисляет концентрацию после смешивания двух растворов.
        C_mix = (C1*V1 + C2*V2) / (V1 + V2)

        Args:
            c1: Концентрация первого раствора (моль/л)
            v1: Объём первого раствора (л)
            c2: Концентрация второго раствора (моль/л)
            v2: Объём второго раствора (л)

        Returns:
            Словарь с результатами смешивания
        """
        v_total = v1 + v2
        if v_total <= 0:
            raise ValueError("Суммарный объём должен быть больше нуля")
        c_mix = (c1 * v1 + c2 * v2) / v_total
        return {
            "концентрация_смеси": round(c_mix, 6),
            "единица": "моль/л",
            "общий_объём_л": round(v_total, 6),
            "моль_из_раствора_1": round(c1 * v1, 6),
            "моль_из_раствора_2": round(c2 * v2, 6),
            "общее_кол_во_моль": round(c1 * v1 + c2 * v2, 6),
        }

    @staticmethod
    def serial_dilution(c_initial, v_initial, v_transfer, n_steps):
        """Вычисляет концентрации при серийном разбавлении.

        Args:
            c_initial: Начальная концентрация (моль/л)
            v_initial: Объём колбы на каждом шаге (л)
            v_transfer: Объём переноса (л)
            n_steps: Количество шагов разбавления

        Returns:
            Список кортежей (номер_шага, концентрация)
        """
        if v_initial <= 0:
            raise ValueError("Объём колбы должен быть больше нуля")
        if v_transfer <= 0:
            raise ValueError("Объём переноса должен быть больше нуля")
        if v_transfer > v_initial:
            raise ValueError("Объём переноса не может превышать объём колбы")
        if n_steps < 1:
            raise ValueError("Количество шагов должно быть не менее 1")
        if n_steps != int(n_steps):
            raise ValueError("Количество шагов должно быть целым числом")

        dilution_factor = v_transfer / v_initial
        results = [(0, round(c_initial, 6))]
        current_c = c_initial
        for i in range(1, n_steps + 1):
            current_c = current_c * dilution_factor
            results.append((i, round(current_c, 6)))
        return results

    @staticmethod
    def titration_endpoint(va, ca, vb, cb):
        """Вычисляет параметры титрования (сильная кислота + сильное основание).

        Args:
            va: Объём кислоты (л)
            ca: Концентрация кислоты (моль/л)
            vb: Объём добавленного основания (л)
            cb: Концентрация основания (моль/л)

        Returns:
            Словарь с параметрами титрования
        """
        if va <= 0 or ca <= 0 or cb <= 0:
            raise ValueError("Объёмы и концентрации должны быть больше нуля")
        if vb < 0:
            raise ValueError("Объём основания не может быть отрицательным")

        # Объём в точке эквивалентности
        ve = (ca * va) / cb

        # pH до точки эквивалентности (избыток кислоты)
        total_volume_before = va + min(vb, ve * 0.999)
        excess_acid_before = ca * va - cb * min(vb, ve * 0.999)
        if total_volume_before > 0 and excess_acid_before > 0:
            h_conc_before = excess_acid_before / total_volume_before
            ph_before = round(-math.log10(h_conc_before), 4)
        else:
            ph_before = 7.0

        # pH в точке эквивалентности
        ph_at_eq = 7.0  # Для сильных кислот и оснований

        # pH после точки эквивалентности (избыток основания)
        total_volume_after = va + max(vb, ve * 1.001)
        excess_base_after = cb * max(vb, ve * 1.001) - ca * va
        if total_volume_after > 0 and excess_base_after > 0:
            oh_conc_after = excess_base_after / total_volume_after
            poh_after = -math.log10(oh_conc_after)
            ph_after = round(14.0 - poh_after, 4)
        else:
            ph_after = 7.0

        # Определяем стадию титрования
        if vb < ve * 0.999:
            stage = "До точки эквивалентности (избыток кислоты)"
        elif abs(vb - ve) < ve * 0.001:
            stage = "В точке эквивалентности"
        else:
            stage = "После точки эквивалентности (избыток основания)"

        # Текущий pH при заданном vb
        total_volume = va + vb
        if total_volume > 0:
            excess = ca * va - cb * vb
            if abs(excess) < 1e-12:
                current_ph = 7.0
            elif excess > 0:
                current_ph = round(-math.log10(excess / total_volume), 4)
            else:
                oh_conc = abs(excess) / total_volume
                current_ph = round(14.0 - (-math.log10(oh_conc)), 4)
        else:
            current_ph = 7.0

        return {
            "объём_эквивалентности_ve": round(ve, 6),
            "единица_ve": "л",
            "ph_до_экв": ph_before,
            "ph_в_точке_экв": ph_at_eq,
            "ph_после_экв": ph_after,
            "текущий_ph": current_ph,
            "стадия": stage,
        }

    @staticmethod
    def mass_from_molarity(molarity, volume_ml, mw):
        """Вычисляет массу вещества по молярности. m = C * V * M

        Args:
            molarity: Молярность (моль/л)
            volume_ml: Объём (мл)
            mw: Молярная масса (г/моль)

        Returns:
            Масса вещества (г)
        """
        if mw <= 0:
            raise ValueError("Молярная масса должна быть больше нуля")
        if volume_ml < 0:
            raise ValueError("Объём не может быть отрицательным")
        volume_l = volume_ml / 1000.0
        return round(molarity * volume_l * mw, 6)

    @staticmethod
    def volume_from_molarity(mass, molarity, mw):
        """Вычисляет объём раствора по массе и молярности. V = m / (C * M)

        Args:
            mass: Масса вещества (г)
            molarity: Молярность (моль/л)
            mw: Молярная масса (г/моль)

        Returns:
            Объём раствора (мл)
        """
        if molarity <= 0:
            raise ValueError("Молярность должна быть больше нуля")
        if mw <= 0:
            raise ValueError("Молярная масса должна быть больше нуля")
        if mass < 0:
            raise ValueError("Масса не может быть отрицательной")
        volume_l = mass / (molarity * mw)
        return round(volume_l * 1000.0, 6)

    @staticmethod
    def convert_concentration(value, from_type, to_type, mw=None, density=None, n_factor=None):
        """Конвертирует между типами концентрации: M, m, %, ppm, N, g/L.

        Args:
            value: Значение концентрации
            from_type: Исходный тип ("M", "m", "%", "ppm", "N", "g/L")
            to_type: Целевой тип ("M", "m", "%", "ppm", "N", "g/L")
            mw: Молярная масса (г/моль), требуется для некоторых преобразований
            density: Плотность раствора (г/мл), требуется для некоторых преобразований
            n_factor: Фактор эквивалентности, требуется для N

        Returns:
            Сконвертированное значение концентрации
        """
        valid_types = {"M", "m", "%", "ppm", "N", "g/L"}
        if from_type not in valid_types or to_type not in valid_types:
            raise ValueError(f"Неподдерживаемый тип концентрации. Допустимые: {valid_types}")

        if from_type == to_type:
            return value

        # Сначала переводим всё в молярность (M), потом в целевой тип
        # Шаг 1: from_type -> M
        molarity = None
        if from_type == "M":
            molarity = value
        elif from_type == "N":
            if n_factor is None or n_factor <= 0:
                raise ValueError("Для конвертации из нормальности требуется factor эквивалентности (n_factor)")
            molarity = value / n_factor
        elif from_type == "g/L":
            if mw is None or mw <= 0:
                raise ValueError("Для конвертации из g/L требуется молярная масса (mw)")
            molarity = value / mw
        elif from_type == "%":
            # Массовый процент -> молярность: C = (w/100 * density*1000) / mw
            if density is None or mw is None or mw <= 0 or density <= 0:
                raise ValueError("Для конвертации из % требуются плотность (density, г/мл) и молярная масса (mw)")
            # w = value%, density в г/мл, 1 мл = density г раствора
            # масса вещества на 1 л = w/100 * density * 1000 (г/л)
            mass_per_l = (value / 100.0) * density * 1000.0
            molarity = mass_per_l / mw
        elif from_type == "ppm":
            # ppm = мг/л -> г/л -> моль/л
            if mw is None or mw <= 0:
                raise ValueError("Для конвертации из ppm требуется молярная масса (mw)")
            mass_per_l = value / 1000.0  # мг/л -> г/л
            molarity = mass_per_l / mw
        elif from_type == "m":
            # Моляльность -> молярность требует плотности
            if density is None or mw is None or mw <= 0 or density <= 0:
                raise ValueError("Для конвертации из моляльности требуются плотность (density, г/мл) и молярная масса (mw)")
            # m моль/кг растворителя, density г/мл -> в 1 л раствора density*1000 г
            # Масса растворителя в 1 л: приблизительно density*1000 * (1 - w), но для разбавленных:
            # C ≈ m * density (приближение для разбавленных растворов)
            molarity = value * density

        if molarity is None:
            raise ValueError(f"Не удалось конвертировать из {from_type}")

        # Шаг 2: M -> to_type
        if to_type == "M":
            return round(molarity, 6)
        elif to_type == "N":
            if n_factor is None or n_factor <= 0:
                raise ValueError("Для конвертации в нормальность требуется factor эквивалентности (n_factor)")
            return round(molarity * n_factor, 6)
        elif to_type == "g/L":
            if mw is None or mw <= 0:
                raise ValueError("Для конвертации в g/L требуется молярная масса (mw)")
            return round(molarity * mw, 6)
        elif to_type == "%":
            if density is None or mw is None or mw <= 0 or density <= 0:
                raise ValueError("Для конвертации в % требуются плотность (density) и молярная масса (mw)")
            mass_per_l = molarity * mw
            total_mass_per_l = density * 1000.0
            return round(mass_per_l / total_mass_per_l * 100.0, 6)
        elif to_type == "ppm":
            if mw is None or mw <= 0:
                raise ValueError("Для конвертации в ppm требуется молярная масса (mw)")
            mass_per_l = molarity * mw
            return round(mass_per_l * 1000.0, 6)
        elif to_type == "m":
            if density is None or mw is None or mw <= 0 or density <= 0:
                raise ValueError("Для конвертации в моляльность требуются плотность (density) и молярная масса (mw)")
            return round(molarity / density, 6)

        raise ValueError(f"Неподдерживаемый целевой тип: {to_type}")


class GasCalculator:
    """Калькулятор законов идеальных и реальных газов."""

    R = 0.08206   # Л·атм/(моль·К)
    R_SI = 8.314  # Дж/(моль·К)

    # Константы Ван-дер-Ваальса для распространённых газов (a в Л²·атм/моль², b в Л/моль)
    VDW_CONSTANTS = {
        "He": (0.0346, 0.0238),
        "H2": (0.2476, 0.0266),
        "N2": (1.370, 0.0387),
        "O2": (1.382, 0.0319),
        "CO2": (3.640, 0.0427),
        "NH3": (4.170, 0.0371),
        "CH4": (2.253, 0.0428),
        "H2O": (5.536, 0.0305),
        "Cl2": (6.579, 0.0562),
        "SO2": (6.714, 0.0564),
    }

    @staticmethod
    def ideal_gas(P=None, V=None, n=None, T=None):
        """Решает уравнение PV = nRT для одной неизвестной величины.

        Args:
            P: Давление (атм)
            V: Объём (л)
            n: Количество вещества (моль)
            T: Температура (К)

        Returns:
            Кортеж (имя_параметра, значение, единица)
        """
        params = {'P': P, 'V': V, 'n': n, 'T': T}
        none_params = [k for k, v in params.items() if v is None]

        if len(none_params) != 1:
            raise ValueError("Должна быть указана ровно одна неизвестная величина (None)")

        unknown = none_params[0]

        if unknown == 'P':
            if V <= 0 or n <= 0 or T <= 0:
                raise ValueError("V, n и T должны быть больше нуля")
            result = n * GasCalculator.R * T / V
            return ('P', round(result, 6), 'атм')
        elif unknown == 'V':
            if P <= 0 or n <= 0 or T <= 0:
                raise ValueError("P, n и T должны быть больше нуля")
            result = n * GasCalculator.R * T / P
            return ('V', round(result, 6), 'л')
        elif unknown == 'n':
            if P <= 0 or V <= 0 or T <= 0:
                raise ValueError("P, V и T должны быть больше нуля")
            result = P * V / (GasCalculator.R * T)
            return ('n', round(result, 6), 'моль')
        elif unknown == 'T':
            if P <= 0 or V <= 0 or n <= 0:
                raise ValueError("P, V и n должны быть больше нуля")
            result = P * V / (n * GasCalculator.R)
            return ('T', round(result, 4), 'К')

    @staticmethod
    def van_der_waals(P=None, V=None, n=None, T=None, a=0, b=0):
        """Решает уравнение Ван-дер-Ваальса (P + n²a/V²)(V - nb) = nRT.

        Поддерживается решение для P или V (для n и T используются формулы
        идентичные идеальному газу).

        Args:
            P: Давление (атм)
            V: Объём (л)
            n: Количество вещества (моль)
            T: Температура (К)
            a: Параметр a (Л²·атм/моль²)
            b: Параметр b (Л/моль)

        Returns:
            Кортеж (имя_параметра, значение, единица)
        """
        params = {'P': P, 'V': V, 'n': n, 'T': T}
        none_params = [k for k, v in params.items() if v is None]

        if len(none_params) != 1:
            raise ValueError("Должна быть указана ровно одна неизвестная величина (None)")

        unknown = none_params[0]

        if unknown == 'P':
            if V <= 0 or n <= 0 or T <= 0:
                raise ValueError("V, n и T должны быть больше нуля")
            result = n * GasCalculator.R * T / V - a * n * n / (V * V)
            return ('P', round(result, 6), 'атм')
        elif unknown == 'V':
            # Численное решение кубического уравнения методом Ньютона
            if P <= 0 or n <= 0 or T <= 0:
                raise ValueError("P, n и T должны быть больше нуля")
            # (P + n²a/V²)(V - nb) = nRT
            # Начальное приближение из идеального газа
            v_ideal = n * GasCalculator.R * T / P
            v = v_ideal
            for _ in range(100):
                # f(V) = (P + n²a/V²)(V - nb) - nRT
                term_a = P + a * n * n / (v * v)
                f_val = term_a * (v - n * b) - n * GasCalculator.R * T
                # Производная f'(V)
                df_val = term_a + (v - n * b) * (-2 * a * n * n / (v * v * v))
                if abs(df_val) < 1e-15:
                    break
                delta = f_val / df_val
                v = v - delta
                if abs(delta) < 1e-10:
                    break
            if v <= 0:
                raise ValueError("Не удалось найти решение: отрицательный объём")
            return ('V', round(v, 6), 'л')
        elif unknown == 'n':
            if P <= 0 or V <= 0 or T <= 0:
                raise ValueError("P, V и T должны быть больше нуля")
            # Приближённое решение: используем итерацию
            n_ideal = P * V / (GasCalculator.R * T)
            n_val = n_ideal
            for _ in range(100):
                f_val = (P + a * n_val * n_val / (V * V)) * (V - n_val * b) - n_val * GasCalculator.R * T
                df_val = (2 * a * n_val / (V * V)) * (V - n_val * b) + (P + a * n_val * n_val / (V * V)) * (-b) - GasCalculator.R * T
                if abs(df_val) < 1e-15:
                    break
                delta = f_val / df_val
                n_val = n_val - delta
                if abs(delta) < 1e-10:
                    break
            return ('n', round(n_val, 6), 'моль')
        elif unknown == 'T':
            if P <= 0 or V <= 0 or n <= 0:
                raise ValueError("P, V и n должны быть больше нуля")
            term = P + a * n * n / (V * V)
            vol_corrected = V - n * b
            if vol_corrected <= 0:
                raise ValueError("Объём после поправки на b ≤ 0, проверьте параметры")
            result = term * vol_corrected / (n * GasCalculator.R)
            return ('T', round(result, 4), 'К')

    @staticmethod
    def combined_gas_law(P1=None, V1=None, T1=None, P2=None, V2=None, T2=None):
        """Решает объединённый газовый закон P1*V1/T1 = P2*V2/T2.

        Args:
            P1, V1, T1: Начальные состояние
            P2, V2, T2: Конечное состояние

        Returns:
            Кортеж (имя_параметра, значение, единица)
        """
        params = {'P1': P1, 'V1': V1, 'T1': T1, 'P2': P2, 'V2': V2, 'T2': T2}
        none_params = [k for k, v in params.items() if v is None]

        if len(none_params) != 1:
            raise ValueError("Должна быть указана ровно одна неизвестная величина (None)")

        unknown = none_params[0]

        if unknown == 'P1':
            if V1 <= 0 or T1 <= 0 or P2 <= 0 or V2 <= 0 or T2 <= 0:
                raise ValueError("Все остальные параметры должны быть > 0")
            result = P2 * V2 * T1 / (V1 * T2)
            return ('P1', round(result, 6), 'атм')
        elif unknown == 'V1':
            if P1 <= 0 or T1 <= 0 or P2 <= 0 or V2 <= 0 or T2 <= 0:
                raise ValueError("Все остальные параметры должны быть > 0")
            result = P2 * V2 * T1 / (P1 * T2)
            return ('V1', round(result, 6), 'л')
        elif unknown == 'T1':
            if P1 <= 0 or V1 <= 0 or P2 <= 0 or V2 <= 0 or T2 <= 0:
                raise ValueError("Все остальные параметры должны быть > 0")
            result = P1 * V1 * T2 / (P2 * V2)
            return ('T1', round(result, 4), 'К')
        elif unknown == 'P2':
            if P1 <= 0 or V1 <= 0 or T1 <= 0 or V2 <= 0 or T2 <= 0:
                raise ValueError("Все остальные параметры должны быть > 0")
            result = P1 * V1 * T2 / (V2 * T1)
            return ('P2', round(result, 6), 'атм')
        elif unknown == 'V2':
            if P1 <= 0 or V1 <= 0 or T1 <= 0 or P2 <= 0 or T2 <= 0:
                raise ValueError("Все остальные параметры должны быть > 0")
            result = P1 * V1 * T2 / (P2 * T1)
            return ('V2', round(result, 6), 'л')
        elif unknown == 'T2':
            if P1 <= 0 or V1 <= 0 or T1 <= 0 or P2 <= 0 or V2 <= 0:
                raise ValueError("Все остальные параметры должны быть > 0")
            result = P2 * V2 * T1 / (P1 * V1)
            return ('T2', round(result, 4), 'К')

    @staticmethod
    def dalton_partial_pressure(p_total, mole_fractions):
        """Вычисляет парциальные давления по закону Дальтона. Pi = xi * P_total.

        Args:
            p_total: Общее давление (атм)
            mole_fractions: Словарь {название_газа: мольная_доля}

        Returns:
            Словарь {название_газа: парциальное_давление}
        """
        if p_total <= 0:
            raise ValueError("Общее давление должно быть больше нуля")
        total_frac = sum(mole_fractions.values())
        if abs(total_frac - 1.0) > 0.05:
            raise ValueError(f"Сумма мольных долей должна быть ≈ 1.0, получено {total_frac:.4f}")

        result = {}
        for gas_name, x in mole_fractions.items():
            result[gas_name] = round(x * p_total, 6)
        return result

    @staticmethod
    def gas_density(P, T, mw):
        """Вычисляет плотность газа. d = P*M / (R*T)

        Args:
            P: Давление (атм)
            T: Температура (К)
            mw: Молярная масса (г/моль)

        Returns:
            Плотность газа (г/л)
        """
        if P <= 0 or T <= 0 or mw <= 0:
            raise ValueError("P, T и молярная масса должны быть больше нуля")
        return round(P * mw / (GasCalculator.R * T), 6)

    @staticmethod
    def molar_mass_from_density(d, P, T):
        """Вычисляет молярную массу газа по плотности. M = d*R*T / P

        Args:
            d: Плотность газа (г/л)
            P: Давление (атм)
            T: Температура (К)

        Returns:
            Молярная масса (г/моль)
        """
        if d <= 0 or P <= 0 or T <= 0:
            raise ValueError("Плотность, давление и температура должны быть больше нуля")
        return round(d * GasCalculator.R * T / P, 4)

    @staticmethod
    def rms_speed(T, mw_kg):
        """Вычисляет среднеквадратичную скорость молекул газа. v_rms = sqrt(3RT/M)

        Args:
            T: Температура (К)
            mw_kg: Молярная масса (кг/моль)

        Returns:
            Среднеквадратичная скорость (м/с)
        """
        if T <= 0 or mw_kg <= 0:
            raise ValueError("Температура и молярная масса должны быть больше нуля")
        return round(math.sqrt(3 * GasCalculator.R_SI * T / mw_kg), 4)

    @staticmethod
    def grahams_law(r1, mw1, mw2):
        """Решает закон Грэма: r1/r2 = sqrt(M2/M1). Вычисляет r2.

        Args:
            r1: Скорость диффузии/эффузии первого газа
            mw1: Молярная масса первого газа (г/моль)
            mw2: Молярная масса второго газа (г/моль)

        Returns:
            Скорость диффузии/эффузии второго газа
        """
        if mw1 <= 0 or mw2 <= 0:
            raise ValueError("Молярные массы должны быть больше нуля")
        if r1 < 0:
            raise ValueError("Скорость не может быть отрицательной")
        return round(r1 * math.sqrt(mw2 / mw1), 6)


class ThermoCalculator:
    """Калькулятор термодинамических расчётов."""

    R = 8.314  # Дж/(моль·К)

    @staticmethod
    def gibbs_energy(dH, dS, T):
        """Вычисляет энергию Гиббса. ΔG = ΔH - T·ΔS

        Args:
            dH: Изменение энтальпии (кДж/моль)
            dS: Изменение энтропии (Дж/(моль·К))
            T: Температура (К)

        Returns:
            Словарь с ΔG, спонтанностью и равновесной температурой
        """
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")

        dg = dH - T * dS / 1000.0  # dS в Дж, переводим в кДж

        if dg < 0:
            spontaneity = "Спонтанный (самопроизвольный)"
        elif dg > 0:
            spontaneity = "Неспонтанный"
        else:
            spontaneity = "Равновесие"

        # Температура равновесия (если dH и dS одного знака)
        equilibrium_temp = None
        if dS != 0 and (dH > 0) == (dS > 0):
            equilibrium_temp = round(dH * 1000.0 / dS, 2)
            if equilibrium_temp < 0:
                equilibrium_temp = None

        return {
            "delta_G_kJ_mol": round(dg, 4),
            "спонтанность": spontaneity,
            "температура_равновесия_K": equilibrium_temp,
        }

    @staticmethod
    def equilibrium_constant(dG, T):
        """Вычисляет константу равновесия. ΔG = -RT·ln(K) → K = exp(-ΔG/(RT))

        Args:
            dG: Энергия Гиббса (кДж/моль)
            T: Температура (К)

        Returns:
            Константа равновесия K
        """
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        dG_J = dG * 1000.0  # кДж -> Дж
        K = math.exp(-dG_J / (ThermoCalculator.R * T))
        return round(K, 6)

    @staticmethod
    def gibbs_from_emf(E, n, T=298):
        """Вычисляет энергию Гиббса из ЭДС. ΔG = -nFE

        Args:
            E: ЭДС (В)
            n: Количество электронов
            T: Температура (К)

        Returns:
            Энергия Гиббса (кДж/моль)
        """
        if n <= 0:
            raise ValueError("Количество электронов должно быть больше нуля")
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        F = CONSTANTS['F']
        dG_J = -n * F * E
        return round(dG_J / 1000.0, 4)

    @staticmethod
    def emf_from_gibbs(dG, n):
        """Вычисляет ЭДС из энергии Гиббса. E = -ΔG / (nF)

        Args:
            dG: Энергия Гиббса (кДж/моль)
            n: Количество электронов

        Returns:
            ЭДС (В)
        """
        if n <= 0:
            raise ValueError("Количество электронов должно быть больше нуля")
        F = CONSTANTS['F']
        dG_J = dG * 1000.0  # кДж -> Дж
        return round(-dG_J / (n * F), 6)

    @staticmethod
    def hess_law(terms):
        """Применяет закон Гесса. Σ(ΔH_i · sign_i)

        Args:
            terms: Список кортежей (ΔH, знак), где знак = +1 или -1

        Returns:
            Общее изменение энтальпии (кДж/моль)
        """
        if not terms:
            raise ValueError("Список членов не может быть пустым")
        total = 0.0
        for i, (dH, sign) in enumerate(terms):
            if sign not in (1, -1):
                raise ValueError(f"Знак члена {i} должен быть +1 или -1, получено {sign}")
            total += dH * sign
        return round(total, 4)

    @staticmethod
    def calorimetry(mass_g, specific_heat, delta_T):
        """Вычисляет теплоту по формуле q = mcΔT

        Args:
            mass_g: Масса (г)
            specific_heat: Удельная теплоёмкость (Дж/(г·К))
            delta_T: Изменение температуры (К или °C)

        Returns:
            Теплота (Дж)
        """
        if mass_g < 0:
            raise ValueError("Масса не может быть отрицательной")
        if specific_heat < 0:
            raise ValueError("Удельная теплоёмкость не может быть отрицательной")
        return round(mass_g * specific_heat * delta_T, 4)

    @staticmethod
    def van_t_hoff(K1, T1, T2, dH):
        """Уравнение Вант-Гоффа. ln(K2/K1) = -ΔH/R * (1/T2 - 1/T1)

        Args:
            K1: Константа равновесия при T1
            T1: Температура 1 (К)
            T2: Температура 2 (К)
            dH: Изменение энтальпии (Дж/моль)

        Returns:
            Словарь {K2: константа_равновесия, ln_K2_K1: логарифм_отношения}
        """
        if K1 <= 0:
            raise ValueError("K1 должно быть больше нуля")
        if T1 <= 0 or T2 <= 0 or T1 == T2:
            raise ValueError("Температуры должны быть > 0 и различаться")
        ln_ratio = -dH / ThermoCalculator.R * (1.0 / T2 - 1.0 / T1)
        K2 = K1 * math.exp(ln_ratio)
        return {
            "K2": round(K2, 6),
            "ln_K2_K1": round(ln_ratio, 6),
        }

    @staticmethod
    def entropy_change(dH, dG, T):
        """Вычисляет изменение энтропии. ΔS = (ΔH - ΔG) / T

        Args:
            dH: Изменение энтальпии (кДж/моль)
            dG: Изменение энергии Гиббса (кДж/моль)
            T: Температура (К)

        Returns:
            Изменение энтропии (Дж/(моль·К))
        """
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        dS_kJ = (dH - dG) / T  # кДж/(моль·К)
        return round(dS_kJ * 1000.0, 4)  # Дж/(моль·К)

    @staticmethod
    def bond_energy(dH_bonds_broken, dH_bonds_formed):
        """Вычисляет энтальпию реакции по энергиям связей. ΔH = Σ(разорванные) - Σ(образованные)

        Args:
            dH_bonds_broken: Сумма энергий разорванных связей (кДж/моль)
            dH_bonds_formed: Сумма энергий образованных связей (кДж/моль)

        Returns:
            Изменение энтальпии (кДж/моль)
        """
        return round(dH_bonds_broken - dH_bonds_formed, 4)


class KineticsCalculator:
    """Калькулятор химической кинетики."""

    R = 8.314  # Дж/(моль·К)

    @staticmethod
    def arrhenius(k1, T1, Ea, T2):
        """Уравнение Аррениуса: k2 = k1 * exp(Ea/R * (1/T1 - 1/T2))

        Args:
            k1: Константа скорости при T1
            T1: Температура 1 (К)
            Ea: Энергия активации (Дж/моль)
            T2: Температура 2 (К)

        Returns:
            Константа скорости k2
        """
        if k1 <= 0:
            raise ValueError("k1 должно быть больше нуля")
        if T1 <= 0 or T2 <= 0:
            raise ValueError("Температуры должны быть больше нуля")
        if T1 == T2:
            raise ValueError("Температуры не должны быть равны")
        k2 = k1 * math.exp(Ea / KineticsCalculator.R * (1.0 / T1 - 1.0 / T2))
        return round(k2, 6)

    @staticmethod
    def activation_energy(k1, T1, k2, T2):
        """Вычисляет энергию активации. Ea = R * ln(k2/k1) / (1/T1 - 1/T2)

        Args:
            k1: Константа скорости при T1
            T1: Температура 1 (К)
            k2: Константа скорости при T2
            T2: Температура 2 (К)

        Returns:
            Энергия активации (Дж/моль)
        """
        if k1 <= 0 or k2 <= 0:
            raise ValueError("Константы скорости должны быть больше нуля")
        if T1 <= 0 or T2 <= 0 or T1 == T2:
            raise ValueError("Температуры должны быть > 0 и различаться")
        Ea = KineticsCalculator.R * math.log(k2 / k1) / (1.0 / T1 - 1.0 / T2)
        return round(Ea, 4)

    @staticmethod
    def half_life_zero_order(k, c0):
        """Период полураспада для реакции нулевого порядка. t1/2 = C0 / (2k)

        Args:
            k: Константа скорости
            c0: Начальная концентрация

        Returns:
            Период полураспада
        """
        if k <= 0:
            raise ValueError("Константа скорости должна быть больше нуля")
        if c0 <= 0:
            raise ValueError("Начальная концентрация должна быть больше нуля")
        return round(c0 / (2 * k), 6)

    @staticmethod
    def half_life_first_order(k):
        """Период полураспада для реакции первого порядка. t1/2 = ln(2) / k

        Args:
            k: Константа скорости

        Returns:
            Период полураспада
        """
        if k <= 0:
            raise ValueError("Константа скорости должна быть больше нуля")
        return round(math.log(2) / k, 6)

    @staticmethod
    def half_life_second_order(k, c0):
        """Период полураспада для реакции второго порядка. t1/2 = 1 / (k * C0)

        Args:
            k: Константа скорости
            c0: Начальная концентрация

        Returns:
            Период полураспада
        """
        if k <= 0:
            raise ValueError("Константа скорости должна быть больше нуля")
        if c0 <= 0:
            raise ValueError("Начальная концентрация должна быть больше нуля")
        return round(1.0 / (k * c0), 6)

    @staticmethod
    def integrated_rate_zero(k, t, c0=None, ct=None):
        """Интегрированный закон скорости нулевого порядка: C0 - Ct = k·t

        Args:
            k: Константа скорости
            t: Время
            c0: Начальная концентрация (если ct задан)
            ct: Конечная концентрация (если c0 задан)

        Returns:
            Словарь {имя_параметра: значение}
        """
        if k <= 0:
            raise ValueError("Константа скорости должна быть больше нуля")
        if t < 0:
            raise ValueError("Время не может быть отрицательным")

        if c0 is not None and ct is not None:
            return {"c0": round(c0, 6), "ct": round(ct, 6), "проверка_kt": round(k * t, 6)}
        elif c0 is not None:
            ct_val = c0 - k * t
            if ct_val < 0:
                raise ValueError("Концентрация не может быть отрицательной. Реакция завершилась.")
            return {"ct": round(ct_val, 6)}
        elif ct is not None:
            if ct < 0:
                raise ValueError("Конечная концентрация не может быть отрицательной")
            c0_val = ct + k * t
            return {"c0": round(c0_val, 6)}
        else:
            raise ValueError("Необходимо указать либо c0, либо ct")

    @staticmethod
    def integrated_rate_first(k, t, c0=None, ct=None):
        """Интегрированный закон скорости первого порядка: ln(C0/Ct) = k·t или Ct = C0·exp(-k·t)

        Args:
            k: Константа скорости
            t: Время
            c0: Начальная концентрация (если ct задан)
            ct: Конечная концентрация (если c0 задан)

        Returns:
            Словарь {имя_параметра: значение}
        """
        if k <= 0:
            raise ValueError("Константа скорости должна быть больше нуля")
        if t < 0:
            raise ValueError("Время не может быть отрицательным")

        if c0 is not None and ct is not None:
            return {"c0": round(c0, 6), "ct": round(ct, 6), "проверка_kt": round(k * t, 6)}
        elif c0 is not None:
            ct_val = c0 * math.exp(-k * t)
            return {"ct": round(ct_val, 6)}
        elif ct is not None:
            if ct <= 0:
                raise ValueError("Конечная концентрация должна быть больше нуля")
            c0_val = ct / math.exp(-k * t)
            return {"c0": round(c0_val, 6)}
        else:
            raise ValueError("Необходимо указать либо c0, либо ct")

    @staticmethod
    def integrated_rate_second(k, t, c0=None, ct=None):
        """Интегрированный закон скорости второго порядка: 1/Ct - 1/C0 = k·t

        Args:
            k: Константа скорости
            t: Время
            c0: Начальная концентрация (если ct задан)
            ct: Конечная концентрация (если c0 задан)

        Returns:
            Словарь {имя_параметра: значение}
        """
        if k <= 0:
            raise ValueError("Константа скорости должна быть больше нуля")
        if t < 0:
            raise ValueError("Время не может быть отрицательным")

        if c0 is not None and ct is not None:
            return {"c0": round(c0, 6), "ct": round(ct, 6), "проверка_kt": round(k * t, 6)}
        elif c0 is not None:
            inv_ct = 1.0 / c0 + k * t
            if inv_ct <= 0:
                raise ValueError("Невозможно вычислить концентрацию")
            ct_val = 1.0 / inv_ct
            return {"ct": round(ct_val, 6)}
        elif ct is not None:
            if ct <= 0:
                raise ValueError("Конечная концентрация должна быть больше нуля")
            c0_val = 1.0 / (1.0 / ct - k * t)
            if c0_val <= 0:
                raise ValueError("Невозможно вычислить начальную концентрацию")
            return {"c0": round(c0_val, 6)}
        else:
            raise ValueError("Необходимо указать либо c0, либо ct")

    @staticmethod
    def reaction_time(order, k, c0, target_fraction):
        """Вычисляет время для достижения заданной доли от начальной концентрации.

        Args:
            order: Порядок реакции (0, 1 или 2)
            k: Константа скорости
            c0: Начальная концентрация
            target_fraction: Целевая доля (напр. 0.5 для t1/2, 0.1 для 90% протекания)

        Returns:
            Время
        """
        if order not in (0, 1, 2):
            raise ValueError("Порядок реакции должен быть 0, 1 или 2")
        if k <= 0:
            raise ValueError("Константа скорости должна быть больше нуля")
        if c0 <= 0:
            raise ValueError("Начальная концентрация должна быть больше нуля")
        if target_fraction <= 0 or target_fraction >= 1:
            raise ValueError("Целевая доля должна быть в интервале (0, 1)")

        ct = c0 * target_fraction

        if order == 0:
            t = (c0 - ct) / k
        elif order == 1:
            if ct <= 0:
                raise ValueError("Для первого порядка конечная концентрация должна быть > 0")
            t = math.log(c0 / ct) / k
        elif order == 2:
            if ct <= 0:
                raise ValueError("Для второго порядка конечная концентрация должна быть > 0")
            t = (1.0 / ct - 1.0 / c0) / k

        return round(t, 6)


class ElectrochemistryCalculator:
    """Калькулятор электрохимических расчётов."""

    F = 96485  # Кл/моль (постоянная Фарадея)
    R = 8.314  # Дж/(моль·К)

    @staticmethod
    def nernst_equation(E0, T, n, Q):
        """Уравнение Нернста. E = E0 - (RT/(nF)) * ln(Q)

        Args:
            E0: Стандартный электродный потенциал (В)
            T: Температура (К)
            n: Количество электронов
            Q: Реакционная частность

        Returns:
            Потенциал (В)
        """
        if n <= 0:
            raise ValueError("Количество электронов должно быть больше нуля")
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        if Q <= 0:
            raise ValueError("Реакционная частность Q должна быть больше нуля")
        E = E0 - (ElectrochemistryCalculator.R * T / (n * ElectrochemistryCalculator.F)) * math.log(Q)
        return round(E, 6)

    @staticmethod
    def cell_emf(cathode_E0, anode_E0, T, n, Q=1.0):
        """Вычисляет ЭДС гальванического элемента. E = E_катод - E_анод - (RT/nF)*ln(Q)

        Args:
            cathode_E0: Стандартный потенциал катода (В)
            anode_E0: Стандартный потенциал анода (В)
            T: Температура (К)
            n: Количество электронов
            Q: Реакционная частность

        Returns:
            Словарь с ЭДС и параметрами
        """
        if n <= 0:
            raise ValueError("Количество электронов должно быть больше нуля")
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        if Q <= 0:
            raise ValueError("Реакционная частность Q должна быть больше нуля")
        E0_cell = cathode_E0 - anode_E0
        nernst_term = (ElectrochemistryCalculator.R * T / (n * ElectrochemistryCalculator.F)) * math.log(Q)
        E_cell = E0_cell - nernst_term
        return {
            "E_элемента": round(E_cell, 6),
            "E0_стандартный": round(E0_cell, 6),
            "унернста": round(nernst_term, 6),
            "единица": "В",
        }

    @staticmethod
    def faraday_law_mass(I, t, n, mw):
        """Закон Фарадея: масса вещества на электроде. m = (I * t * M) / (n * F)

        Args:
            I: Сила тока (А)
            t: Время (с)
            n: Количество электронов
            mw: Молярная масса (г/моль)

        Returns:
            Масса вещества (г)
        """
        if I <= 0:
            raise ValueError("Сила тока должна быть больше нуля")
        if t < 0:
            raise ValueError("Время не может быть отрицательным")
        if n <= 0:
            raise ValueError("Количество электронов должно быть больше нуля")
        if mw <= 0:
            raise ValueError("Молярная масса должна быть больше нуля")
        mass = (I * t * mw) / (n * ElectrochemistryCalculator.F)
        return round(mass, 6)

    @staticmethod
    def faraday_law_volume(I, t, n, T=298, P=1.0):
        """Закон Фарадея: объём газа. V = (I * t * R * T) / (n * F * P)

        Args:
            I: Сила тока (А)
            t: Время (с)
            n: Количество электронов
            T: Температура (К)
            P: Давление (атм)

        Returns:
            Объём газа (л)
        """
        if I <= 0:
            raise ValueError("Сила тока должна быть больше нуля")
        if t < 0:
            raise ValueError("Время не может быть отрицательным")
        if n <= 0:
            raise ValueError("Количество электронов должно быть больше нуля")
        if P <= 0 or T <= 0:
            raise ValueError("Давление и температура должны быть больше нуля")
        R_atm = 0.08206
        volume = (I * t * R_atm * T) / (n * ElectrochemistryCalculator.F * P)
        return round(volume, 6)

    @staticmethod
    def gibbs_from_emf(E, n, T=298):
        """Энергия Гиббса из ЭДС. ΔG = -nFE

        Args:
            E: ЭДС (В)
            n: Количество электронов
            T: Температура (К)

        Returns:
            Энергия Гиббса (кДж/моль)
        """
        if n <= 0:
            raise ValueError("Количество электронов должно быть больше нуля")
        dG_J = -n * ElectrochemistryCalculator.F * E
        return round(dG_J / 1000.0, 4)

    @staticmethod
    def equilibrium_constant_from_emf(E, n, T=298):
        """Константа равновесия из ЭДС. K = exp(nFE/(RT))

        Args:
            E: Стандартная ЭДС (В)
            n: Количество электронов
            T: Температура (К)

        Returns:
            Константа равновесия K
        """
        if n <= 0:
            raise ValueError("Количество электронов должно быть больше нуля")
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        K = math.exp(n * ElectrochemistryCalculator.F * E / (ElectrochemistryCalculator.R * T))
        return round(K, 6)

    @staticmethod
    def electrochemical_efficiency(actual_mass, theoretical_mass):
        """Вычисляет выход по току. η = (m_факт / m_теор) * 100%

        Args:
            actual_mass: Фактическая масса (г)
            theoretical_mass: Теоретическая масса (г)

        Returns:
            Выход по току (%)
        """
        if theoretical_mass <= 0:
            raise ValueError("Теоретическая масса должна быть больше нуля")
        if actual_mass < 0:
            raise ValueError("Фактическая масса не может быть отрицательной")
        efficiency = (actual_mass / theoretical_mass) * 100.0
        return round(efficiency, 4)


class AcidBaseCalculator:
    """Калькулятор кислотно-основных расчётов."""

    # Константы диссоциации для распространённых кислот
    KA_VALUES = {
        "HCl": 1e7,
        "HBr": 1e9,
        "HI": 1e10,
        "HNO3": 24,
        "H2SO4": 1e3,
        "HClO4": 1e10,
        "HF": 6.6e-4,
        "CH3COOH": 1.74e-5,
        "HCOOH": 1.77e-4,
        "HCN": 6.2e-10,
        "H2S": 1.0e-7,
        "H2SO3": 1.3e-2,
        "H3PO4": 7.1e-3,
        "H2PO4-": 6.3e-8,
        "HPO4^2-": 4.5e-13,
        "H2CO3": 4.3e-7,
        "HCO3-": 4.7e-11,
        "C6H5COOH": 6.3e-5,
        "HNO2": 7.2e-4,
    }

    @staticmethod
    def strong_acid_ph(concentration):
        """Вычисляет pH сильной кислоты. pH = -log10(C)

        Args:
            concentration: Концентрация (моль/л)

        Returns:
            pH
        """
        if concentration <= 0:
            raise ValueError("Концентрация должна быть больше нуля")
        if concentration > 1:
            raise ValueError("Для концентраций > 1 М требуется учёт активности")
        return round(-math.log10(concentration), 4)

    @staticmethod
    def strong_base_ph(concentration):
        """Вычисляет pH сильного основания. pOH = -log10(C), pH = 14 - pOH

        Args:
            concentration: Концентрация (моль/л)

        Returns:
            pH
        """
        if concentration <= 0:
            raise ValueError("Концентрация должна быть больше нуля")
        if concentration > 1:
            raise ValueError("Для концентраций > 1 М требуется учёт активности")
        poh = -math.log10(concentration)
        return round(14.0 - poh, 4)

    @staticmethod
    def weak_acid_ph(concentration, Ka):
        """Вычисляет pH слабой кислоты. [H+] = sqrt(Ka * C), pH = -log10([H+])

        Args:
            concentration: Концентрация (моль/л)
            Ka: Константа диссоциации

        Returns:
            pH
        """
        if concentration <= 0:
            raise ValueError("Концентрация должна быть больше нуля")
        if Ka <= 0:
            raise ValueError("Ka должно быть больше нуля")
        # Проверка применимости приближения: C/Ka > 100
        if concentration / Ka < 100:
            # Более точное решение квадратного уравнения: [H+]² + Ka[H+] - Ka*C = 0
            h_conc = (-Ka + math.sqrt(Ka * Ka + 4 * Ka * concentration)) / 2.0
        else:
            h_conc = math.sqrt(Ka * concentration)
        if h_conc <= 0:
            raise ValueError("Не удалось вычислить концентрацию H+")
        return round(-math.log10(h_conc), 4)

    @staticmethod
    def weak_base_ph(concentration, Kb):
        """Вычисляет pH слабого основания. [OH-] = sqrt(Kb * C), pOH = -log([OH-]), pH = 14 - pOH

        Args:
            concentration: Концентрация (моль/л)
            Kb: Константа диссоциации основания

        Returns:
            pH
        """
        if concentration <= 0:
            raise ValueError("Концентрация должна быть больше нуля")
        if Kb <= 0:
            raise ValueError("Kb должно быть больше нуля")
        # Проверка применимости приближения
        if concentration / Kb < 100:
            oh_conc = (-Kb + math.sqrt(Kb * Kb + 4 * Kb * concentration)) / 2.0
        else:
            oh_conc = math.sqrt(Kb * concentration)
        if oh_conc <= 0:
            raise ValueError("Не удалось вычислить концентрацию OH-")
        poh = -math.log10(oh_conc)
        return round(14.0 - poh, 4)

    @staticmethod
    def polyprotic_acid_ph(concentration, Ka_values):
        """Вычисляет pH полипротонной кислоты. Обычно доминирует первая ступень.

        Args:
            concentration: Концентрация (моль/л)
            Ka_values: Список констант диссоциации [Ka1, Ka2, ...]

        Returns:
            Словарь {ph, доминирующий_вид}
        """
        if concentration <= 0:
            raise ValueError("Концентрация должна быть больше нуля")
        if not Ka_values:
            raise ValueError("Список Ka не может быть пустым")
        if not all(k > 0 for k in Ka_values):
            raise ValueError("Все значения Ka должны быть больше нуля")

        Ka1 = Ka_values[0]

        # Для первой ступени диссоциации используем формулу слабой кислоты
        if concentration / Ka1 < 100:
            h_conc = (-Ka1 + math.sqrt(Ka1 * Ka1 + 4 * Ka1 * concentration)) / 2.0
        else:
            h_conc = math.sqrt(Ka1 * concentration)

        ph = round(-math.log10(h_conc), 4)

        # Определяем доминирующий вид на основе pH
        dominant = None
        pka_values = [-math.log10(ka) for ka in Ka_values]

        if len(Ka_values) >= 3:
            pKa1, pKa2, pKa3 = pka_values[0], pka_values[1], pka_values[2]
            if ph < pKa1 - 1:
                dominant = "H3A (ненонизированная кислота)"
            elif pKa1 - 1 <= ph < (pKa1 + pKa2) / 2:
                dominant = "H2A- (после первой диссоциации)"
            elif (pKa1 + pKa2) / 2 <= ph < (pKa2 + pKa3) / 2:
                dominant = "HA2- (после второй диссоциации)"
            else:
                dominant = "A3- (после третьей диссоциации)"
        elif len(Ka_values) >= 2:
            pKa1, pKa2 = pka_values[0], pka_values[1]
            if ph < pKa1 - 1:
                dominant = "H2A (ненонизированная кислота)"
            elif pKa1 - 1 <= ph < (pKa1 + pKa2) / 2:
                dominant = "HA- (после первой диссоциации)"
            else:
                dominant = "A2- (после полной диссоциации)"
        else:
            dominant = "HA (мононротонная кислота)"

        return {
            "ph": ph,
            "доминирующий_вид": dominant,
            "Ka_значения": Ka_values,
        }

    @staticmethod
    def salt_hydrolysis_ph(cation, anion, Ka=None, Kb=None):
        """Определяет тип гидролиза соли и вычисляет pH.

        Args:
            cation: Катион (название или 'сильный'/'слабый')
            anion: Анион (название или 'сильный'/'слабый')
            Ka: Ka сопряжённой кислоты (для аниона слабой кислоты)
            Kb: Kb сопряжённого основания (для катиона слабого основания)

        Returns:
            Словарь с результатами анализа гидролиза
        """
        # Определяем силу катиона и аниона
        strong_cations = {"Na", "K", "Ca", "Mg", "Ba", "Li", "Rb", "Cs", "Sr", "сильный", "strong"}
        strong_anions = {"Cl", "Br", "I", "NO3", "ClO4", "SO4", "сильный", "strong"}

        cation_is_strong = cation in strong_cations
        anion_is_strong = anion in strong_anions

        if cation_is_strong and anion_is_strong:
            return {
                "тип": "Нейтральная соль",
                "гидролиз": "Не гидролизуется",
                "ph": 7.0,
                "среда": "Нейтральная",
            }
        elif cation_is_strong and not anion_is_strong:
            # Соль слабой кислоты + сильного основания
            if Ka is None or Ka <= 0:
                return {
                    "тип": "Соль слабой кислоты + сильного основания",
                    "гидролиз": "По аниону",
                    "ph": "7 < pH < 14 (требуется Ka)",
                    "среда": "Щелочная",
                }
            # pH = 7 + 0.5*pKa + 0.5*log(C) — приближённо для разбавленных
            Kb_salt = 1e-14 / Ka
            # Для точного расчёта нужна концентрация; возвращаем диапазон
            return {
                "тип": "Соль слабой кислоты + сильного основания",
                "гидролиз": "По аниону",
                "Kb_соли": f"{Kb_salt:.4e}",
                "среда": "Щелочная (pH > 7)",
            }
        elif not cation_is_strong and anion_is_strong:
            # Соль сильной кислоты + слабого основания
            if Kb is None or Kb <= 0:
                return {
                    "тип": "Соль сильной кислоты + слабого основания",
                    "гидролиз": "По катиону",
                    "ph": "0 < pH < 7 (требуется Kb)",
                    "среда": "Кислая",
                }
            Ka_salt = 1e-14 / Kb
            return {
                "тип": "Соль сильной кислоты + слабого основания",
                "гидролиз": "По катиону",
                "Ka_соли": f"{Ka_salt:.4e}",
                "среда": "Кислая (pH < 7)",
            }
        else:
            # Соль слабой кислоты + слабого основания
            return {
                "тип": "Соль слабой кислоты + слабого основания",
                "гидролиз": "По катиону и аниону",
                "ph": "Зависит от соотношения Ka и Kb",
                "среда": "Определяется сравнением Ka и Kb",
            }

    @staticmethod
    def henderson_hasselbalch(pKa, acid_conc, base_conc):
        """Уравнение Гендерсона-Хассельбальха. pH = pKa + log10([A-]/[HA])

        Args:
            pKa: Величина pKa
            acid_conc: Концентрация кислоты [HA]
            base_conc: Концентрация сопряжённого основания [A-]

        Returns:
            pH
        """
        if acid_conc <= 0:
            raise ValueError("Концентрация кислоты должна быть больше нуля")
        if base_conc <= 0:
            raise ValueError("Концентрация основания должна быть больше нуля")
        ratio = base_conc / acid_conc
        ph = pKa + math.log10(ratio)
        return round(ph, 4)

    @staticmethod
    def buffer_capacity(pKa, acid_conc, base_conc, added_moles=0.001, volume=1.0):
        """Вычисляет буферную ёмкость. β ≈ 2.303 * C_total * Ka * [H+] / (Ka + [H+])²

        Args:
            pKa: Величина pKa
            acid_conc: Концентрация кислоты (моль/л)
            base_conc: Концентрация сопряжённого основания (моль/л)
            added_moles: Добавленное количество сильной кислоты/основания (моль)
            volume: Объём буфера (л)

        Returns:
            Словарь с результатами
        """
        if acid_conc <= 0 or base_conc <= 0:
            raise ValueError("Концентрации должны быть больше нуля")
        if volume <= 0:
            raise ValueError("Объём должен быть больше нуля")

        Ka = 10.0 ** (-pKa)
        c_total = acid_conc + base_conc

        # [H+] из уравнения Гендерсона-Хассельбальха
        h_conc = Ka * acid_conc / base_conc

        if h_conc <= 0:
            raise ValueError("Не удалось вычислить [H+]")

        # Буферная ёмкость
        beta = 2.303 * c_total * Ka * h_conc / ((Ka + h_conc) ** 2)

        # Изменение pH при добавлении
        ph_before = AcidBaseCalculator.henderson_hasselbalch(pKa, acid_conc, base_conc)
        new_acid = acid_conc + added_moles / volume
        new_base = base_conc - added_moles / volume
        if new_acid > 0 and new_base > 0:
            ph_after = AcidBaseCalculator.henderson_hasselbalch(pKa, new_acid, new_base)
            delta_ph = abs(ph_after - ph_before)
        else:
            delta_ph = float('inf')

        return {
            "буферная_ёмкость": round(beta, 6),
            "pH_до_добавления": ph_before,
            "изменение_pH": round(delta_ph, 4) if delta_ph != float('inf') else "Буфер исчерпан",
        }

    @staticmethod
    def ka_from_pka(pKa):
        """Конвертирует pKa в Ka. Ka = 10^(-pKa)

        Args:
            pKa: Величина pKa

        Returns:
            Ka
        """
        return round(10.0 ** (-pKa), 10)

    @staticmethod
    def pka_from_ka(Ka):
        """Конвертирует Ka в pKa. pKa = -log10(Ka)

        Args:
            Ka: Константа диссоциации

        Returns:
            pKa
        """
        if Ka <= 0:
            raise ValueError("Ka должно быть больше нуля")
        return round(-math.log10(Ka), 4)

    @staticmethod
    def kb_from_ka(Ka):
        """Вычисляет Kb из Ka. Kw = Ka * Kb → Kb = 1e-14 / Ka

        Args:
            Ka: Константа диссоциации кислоты

        Returns:
            Kb сопряжённого основания
        """
        if Ka <= 0:
            raise ValueError("Ka должно быть больше нуля")
        return round(1e-14 / Ka, 10)

    @staticmethod
    def pkb_from_ka(Ka):
        """Вычисляет pKb из Ka. pKb = 14 - pKa

        Args:
            Ka: Константа диссоциации кислоты

        Returns:
            pKb
        """
        if Ka <= 0:
            raise ValueError("Ka должно быть больше нуля")
        pKa = -math.log10(Ka)
        return round(14.0 - pKa, 4)


class ColligativeCalculator:
    """Калькулятор коллигативных свойств растворов."""

    R = 0.08206  # Л·атм/(моль·К)
    Kb_WATER = 0.512   # °C·кг/моль
    Kf_WATER = 1.86    # °C·кг/моль
    Kb_ETHANOL = 1.22
    Kf_ETHANOL = 1.99
    Kb_BENZENE = 2.53
    Kf_BENZENE = 5.12

    SOLVENT_CONSTANTS = {
        "Вода": {"Kb": 0.512, "Kf": 1.86, "Tb": 100.0, "Tf": 0.0},
        "Этанол": {"Kb": 1.22, "Kf": 1.99, "Tb": 78.37, "Tf": -114.1},
        "Бензол": {"Kb": 2.53, "Kf": 5.12, "Tb": 80.1, "Tf": 5.5},
        "Ацетон": {"Kb": 1.71, "Kf": None, "Tb": 56.0, "Tf": -94.7},
        "CCl4": {"Kb": 5.03, "Kf": 29.8, "Tb": 76.7, "Tf": -23.0},
    }

    @staticmethod
    def boiling_point_elevation(molality, Kb):
        """Вычисляет повышение температуры кипения. ΔTb = Kb * m

        Args:
            molality: Моляльность (моль/кг)
            Kb: Эбуллиоскопическая константа (°C·кг/моль)

        Returns:
            Повышение температуры кипения (°C)
        """
        if molality < 0:
            raise ValueError("Моляльность не может быть отрицательной")
        if Kb < 0:
            raise ValueError("Kb не может быть отрицательным")
        return round(Kb * molality, 4)

    @staticmethod
    def freezing_point_depression(molality, Kf):
        """Вычисляет понижение температуры замерзания. ΔTf = Kf * m

        Args:
            molality: Моляльность (моль/кг)
            Kf: Криоскопическая константа (°C·кг/моль)

        Returns:
            Понижение температуры замерзания (°C)
        """
        if molality < 0:
            raise ValueError("Моляльность не может быть отрицательной")
        if Kf is None:
            raise ValueError("Криоскопическая константа не определена для данного растворителя")
        if Kf < 0:
            raise ValueError("Kf не может быть отрицательным")
        return round(Kf * molality, 4)

    @staticmethod
    def osmotic_pressure(molarity, T, R=0.08206):
        """Вычисляет осмотическое давление. π = MRT

        Args:
            molarity: Молярность (моль/л)
            T: Температура (К)
            R: Газовая постоянная (Л·атм/(моль·К))

        Returns:
            Осмотическое давление (атм)
        """
        if molarity < 0:
            raise ValueError("Молярность не может быть отрицательной")
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        return round(molarity * R * T, 6)

    @staticmethod
    def osmotic_pressure_vant_hoff(molarity, T, i, R=0.08206):
        """Вычисляет осмотическое давление с учётом фактора Вант-Гоффа. π = iMRT

        Args:
            molarity: Молярность (моль/л)
            T: Температура (К)
            i: Фактор Вант-Гоффа
            R: Газовая постоянная (Л·атм/(моль·К))

        Returns:
            Осмотическое давление (атм)
        """
        if molarity < 0:
            raise ValueError("Молярность не может быть отрицательной")
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        if i < 0:
            raise ValueError("Фактор Вант-Гоффа не может быть отрицательным")
        return round(i * molarity * R * T, 6)

    @staticmethod
    def van_t_hoff_factor(n_solute, n_particles):
        """Вычисляет фактор Вант-Гоффа. i = n_particles / n_solute

        Args:
            n_solute: Количество формульных единиц растворённого вещества
            n_particles: Общее количество частиц в растворе

        Returns:
            Фактор Вант-Гоффа
        """
        if n_solute <= 0:
            raise ValueError("Количество формульных единиц должно быть больше нуля")
        if n_particles < 0:
            raise ValueError("Количество частиц не может быть отрицательным")
        return round(n_particles / n_solute, 4)

    @staticmethod
    def boiling_point_new(solvent_name, molality):
        """Вычисляет новую температуру кипения раствора. Tb_new = Tb + Kb * m

        Args:
            solvent_name: Название растворителя (из SOLVENT_CONSTANTS)
            molality: Моляльность (моль/кг)

        Returns:
            Словарь с новой температурой кипения
        """
        if solvent_name not in ColligativeCalculator.SOLVENT_CONSTANTS:
            available = ", ".join(ColligativeCalculator.SOLVENT_CONSTANTS.keys())
            raise ValueError(f"Неизвестный растворитель: {solvent_name}. Доступные: {available}")
        if molality < 0:
            raise ValueError("Моляльность не может быть отрицательной")

        props = ColligativeCalculator.SOLVENT_CONSTANTS[solvent_name]
        Kb = props["Kb"]
        Tb = props["Tb"]
        delta_Tb = Kb * molality
        return {
            "растворитель": solvent_name,
            "Tb_чистого_растворителя": Tb,
            "повышение_Т_кипения": round(delta_Tb, 4),
            "Tb_раствора": round(Tb + delta_Tb, 4),
            "единица": "°C",
        }

    @staticmethod
    def freezing_point_new(solvent_name, molality):
        """Вычисляет новую температуру замерзания раствора. Tf_new = Tf - Kf * m

        Args:
            solvent_name: Название растворителя (из SOLVENT_CONSTANTS)
            molality: Моляльность (моль/кг)

        Returns:
            Словарь с новой температурой замерзания
        """
        if solvent_name not in ColligativeCalculator.SOLVENT_CONSTANTS:
            available = ", ".join(ColligativeCalculator.SOLVENT_CONSTANTS.keys())
            raise ValueError(f"Неизвестный растворитель: {solvent_name}. Доступные: {available}")
        if molality < 0:
            raise ValueError("Моляльность не может быть отрицательной")

        props = ColligativeCalculator.SOLVENT_CONSTANTS[solvent_name]
        Kf = props["Kf"]
        Tf = props["Tf"]
        if Kf is None:
            raise ValueError(f"Криоскопическая константа не определена для {solvent_name}")
        delta_Tf = Kf * molality
        return {
            "растворитель": solvent_name,
            "Tf_чистого_растворителя": Tf,
            "понижение_Т_замерзания": round(delta_Tf, 4),
            "Tf_раствора": round(Tf - delta_Tf, 4),
            "единица": "°C",
        }

    @staticmethod
    def molecular_weight_from_colligative(delta_T, K_solvent, mass_solute, mass_solvent):
        """Вычисляет молярную массу по коллигативному свойству.
        M = (K * mass_solute) / (delta_T * mass_solvent_kg)

        Args:
            delta_T: Изменение температуры (°C)
            K_solvent: Криоскопическая или эбуллиоскопическая константа (°C·кг/моль)
            mass_solute: Масса растворённого вещества (г)
            mass_solvent: Масса растворителя (кг)

        Returns:
            Молярная масса (г/моль)
        """
        if delta_T <= 0:
            raise ValueError("Изменение температуры должно быть больше нуля")
        if K_solvent <= 0:
            raise ValueError("Константа растворителя должна быть больше нуля")
        if mass_solute <= 0:
            raise ValueError("Масса растворённого вещества должна быть больше нуля")
        if mass_solvent <= 0:
            raise ValueError("Масса растворителя должна быть больше нуля")
        mw = (K_solvent * mass_solute) / (delta_T * mass_solvent)
        return round(mw, 4)

    @staticmethod
    def raoults_law(p_solvent, x_solvent):
        """Закон Рауля. P = x_растворителя * P°_растворителя

        Args:
            p_solvent: Давление пара чистого растворителя (атм или мм рт. ст.)
            x_solvent: Мольная доля растворителя

        Returns:
            Давление пара раствора
        """
        if p_solvent < 0:
            raise ValueError("Давление не может быть отрицательным")
        if x_solvent < 0 or x_solvent > 1:
            raise ValueError("Мольная доля должна быть в интервале [0, 1]")
        return round(p_solvent * x_solvent, 6)

    @staticmethod
    def ideal_mole_fraction(solvent_moles, solute_moles):
        """Вычисляет мольную долю растворителя. x = n_растворителя / (n_растворителя + n_растворённого)

        Args:
            solvent_moles: Количество растворителя (моль)
            solute_moles: Количество растворённого вещества (моль)

        Returns:
            Мольная доля растворителя
        """
        if solvent_moles < 0:
            raise ValueError("Количество растворителя не может быть отрицательным")
        if solute_moles < 0:
            raise ValueError("Количество растворённого вещества не может быть отрицательным")
        total = solvent_moles + solute_moles
        if total <= 0:
            raise ValueError("Суммарное количество моль должно быть больше нуля")
        return round(solvent_moles / total, 6)


class StoichiometryCalculator:
    """Калькулятор стехиометрических расчётов."""

    @staticmethod
    def limiting_reagent(masses, molar_masses, coefficients):
        """Определяет лимитирующий реагент.

        Args:
            masses: Словарь {реагент: масса_г}
            molar_masses: Словарь {реагент: молярная_масса}
            coefficients: Словарь {реагент: коэффициент}

        Returns:
            Кортеж (лимитирующий_реагент, словарь_моль_доступно, словарь_моль_потребно)
        """
        if not masses:
            raise ValueError("Словарь масс не может быть пустым")

        moles_available = {}
        moles_needed = {}
        ratios = {}

        for reactant, mass in masses.items():
            if reactant not in molar_masses:
                raise ValueError(f"Молярная масса не указана для: {reactant}")
            if reactant not in coefficients:
                raise ValueError(f"Коэффициент не указан для: {reactant}")
            if molar_masses[reactant] <= 0:
                raise ValueError(f"Молярная масса {reactant} должна быть > 0")
            if mass < 0:
                raise ValueError(f"Масса {reactant} не может быть отрицательной")

            moles = mass / molar_masses[reactant]
            moles_available[reactant] = moles

            # Определяем минимальный коэффициент
            moles_needed[reactant] = moles / coefficients[reactant]

        limiting = min(moles_needed, key=moles_needed.get)
        return (limiting, moles_available, moles_needed)

    @staticmethod
    def theoretical_yield(limiting_mass, limiting_mw, limiting_coeff, product_mw, product_coeff):
        """Вычисляет теоретический выход продукта.
        m_product = (m_limiting / MW_limiting) * (coeff_product / coeff_limiting) * MW_product

        Args:
            limiting_mass: Масса лимитирующего реагента (г)
            limiting_mw: Молярная масса лимитирующего реагента (г/моль)
            limiting_coeff: Коэффициент лимитирующего реагента
            product_mw: Молярная масса продукта (г/моль)
            product_coeff: Коэффициент продукта

        Returns:
            Теоретическая масса продукта (г)
        """
        if limiting_mw <= 0 or product_mw <= 0:
            raise ValueError("Молярные массы должны быть больше нуля")
        if limiting_coeff <= 0 or product_coeff <= 0:
            raise ValueError("Коэффициенты должны быть больше нуля")
        if limiting_mass < 0:
            raise ValueError("Масса не может быть отрицательной")
        moles_limiting = limiting_mass / limiting_mw
        moles_product = moles_limiting * (product_coeff / limiting_coeff)
        mass_product = moles_product * product_mw
        return round(mass_product, 6)

    @staticmethod
    def percent_yield(actual, theoretical):
        """Вычисляет процент выхода. % = (m_факт / m_теор) * 100

        Args:
            actual: Фактический выход (г)
            theoretical: Теоретический выход (г)

        Returns:
            Процент выхода (%)
        """
        if theoretical <= 0:
            raise ValueError("Теоретический выход должен быть больше нуля")
        if actual < 0:
            raise ValueError("Фактический выход не может быть отрицательным")
        return round((actual / theoretical) * 100.0, 4)

    @staticmethod
    def actual_yield(percent, theoretical):
        """Вычисляет фактический выход. m_факт = (% * m_теор) / 100

        Args:
            percent: Процент выхода (%)
            theoretical: Теоретический выход (г)

        Returns:
            Фактический выход (г)
        """
        if theoretical <= 0:
            raise ValueError("Теоретический выход должен быть больше нуля")
        if percent < 0:
            raise ValueError("Процент выхода не может быть отрицательным")
        return round((percent / 100.0) * theoretical, 6)

    @staticmethod
    def moles_from_mass(mass, mw):
        """Вычисляет количество вещества. n = m / M

        Args:
            mass: Масса (г)
            mw: Молярная масса (г/моль)

        Returns:
            Количество вещества (моль)
        """
        if mw <= 0:
            raise ValueError("Молярная масса должна быть больше нуля")
        if mass < 0:
            raise ValueError("Масса не может быть отрицательной")
        return round(mass / mw, 6)

    @staticmethod
    def mass_from_moles(moles, mw):
        """Вычисляет массу вещества. m = n * M

        Args:
            moles: Количество вещества (моль)
            mw: Молярная масса (г/моль)

        Returns:
            Масса (г)
        """
        if mw <= 0:
            raise ValueError("Молярная масса должна быть больше нуля")
        if moles < 0:
            raise ValueError("Количество моль не может быть отрицательным")
        return round(moles * mw, 6)

    @staticmethod
    def volume_of_gas_at_stp(moles):
        """Вычисляет объём газа при н.у. V = n * 22.414 л

        Args:
            moles: Количество вещества (моль)

        Returns:
            Объём газа (л)
        """
        if moles < 0:
            raise ValueError("Количество моль не может быть отрицательным")
        return round(moles * 22.414, 6)

    @staticmethod
    def moles_from_gas_volume(volume, T=273.15, P=1.0, R=0.08206):
        """Вычисляет количество газа из объёма. n = PV/(RT)

        Args:
            volume: Объём газа (л)
            T: Температура (К)
            P: Давление (атм)
            R: Газовая постоянная

        Returns:
            Количество вещества (моль)
        """
        if volume < 0:
            raise ValueError("Объём не может быть отрицательным")
        if T <= 0:
            raise ValueError("Температура должна быть больше нуля")
        if P <= 0:
            raise ValueError("Давление должно быть больше нуля")
        return round(P * volume / (R * T), 6)

    @staticmethod
    def particles_count(moles):
        """Вычисляет число частиц. N = n * N_A

        Args:
            moles: Количество вещества (моль)

        Returns:
            Число частиц
        """
        if moles < 0:
            raise ValueError("Количество моль не может быть отрицательным")
        return round(moles * CONSTANTS['NA'], 4)

    @staticmethod
    def comprehensive_reaction_analysis(reactants, products, given_masses, molar_masses, coefficients=None):
        """Полный анализ реакции: лимитирующий реагент, теоретический выход, избыток.

        Args:
            reactants: Список формул реагентов
            products: Список формул продуктов
            given_masses: Словарь {формула: масса_г}
            molar_masses: Словарь {формула: молярная_масса}
            coefficients: Словарь {формула: коэффициент} (если None, предполагаются все = 1)

        Returns:
            Словарь с полным анализом реакции
        """
        if not reactants or not products:
            raise ValueError("Списки реагентов и продуктов не могут быть пустыми")
        if not given_masses:
            raise ValueError("Даны массы не могут быть пустыми")

        if coefficients is None:
            coefficients = {r: 1 for r in reactants + products}

        # Формируем словари для расчётов
        reactant_masses = {r: given_masses.get(r, 0) for r in reactants if r in given_masses}
        reactant_mw = {r: molar_masses[r] for r in reactant_masses if r in molar_masses}
        reactant_coeffs = {r: coefficients.get(r, 1) for r in reactant_masses}

        # Определяем лимитирующий реагент
        limiting, moles_available, moles_needed = StoichiometryCalculator.limiting_reagent(
            reactant_masses, reactant_mw, reactant_coeffs
        )

        limiting_moles = moles_available[limiting]
        limiting_coeff = reactant_coeffs[limiting]

        # Теоретический выход для каждого продукта
        product_yields = {}
        for prod in products:
            if prod in molar_masses and prod in coefficients:
                product_mass = StoichiometryCalculator.theoretical_yield(
                    given_masses[limiting],
                    molar_masses[limiting],
                    limiting_coeff,
                    molar_masses[prod],
                    coefficients[prod]
                )
                product_yields[prod] = round(product_mass, 6)

        # Расчёт избытка реагентов
        excess = {}
        for reactant in reactant_masses:
            if reactant != limiting:
                # Сколько моль данного реагента нужно
                needed_moles = limiting_moles / limiting_coeff * reactant_coeffs[reactant]
                excess_moles = moles_available[reactant] - needed_moles
                excess_mass = excess_moles * molar_masses[reactant]
                excess[reactant] = {
                    "избыток_моль": round(max(0, excess_moles), 6),
                    "избыток_масса_г": round(max(0, excess_mass), 6),
                    "потреблено_моль": round(needed_moles, 6),
                }

        return {
            "лимитирующий_реагент": limiting,
            "моли_лимитирующего": round(limiting_moles, 6),
            "теоретический_выход_г": product_yields,
            "избыток_реагентов": excess,
            "все_моли_доступно": {k: round(v, 6) for k, v in moles_available.items()},
        }


class EquationBalancer:
    @staticmethod
    def balance(reactants_str: str, products_str: str) -> str:
        """
        Балансировка реакции используя ChemPy.
        """
        if not HAS_CHEMPY:
            return "Требуется библиотека ChemPy (pip install chempy)"
        try:
            # Очистка ввода
            reac = [x.strip() for x in reactants_str.split('+') if x.strip()]
            prod = [x.strip() for x in products_str.split('+') if x.strip()]

            if not reac or not prod:
                return "Введите реагенты и продукты"

            # Балансировка
            reac_dict, prod_dict = balance_stoichiometry(set(reac), set(prod))

            # Формирование красивого вывода
            def fmt(d):
                parts = []
                for k, v in sorted(d.items()):
                    # v может быть float, если простые числа, приведем к int если это целое
                    coeff = ""
                    if v != 1:
                        coeff = str(int(v)) if float(v).is_integer() else f"{v:.2f}"
                    parts.append(f"{coeff}{k}" if coeff else k)
                return " + ".join(parts)

            return f"{fmt(reac_dict)} → {fmt(prod_dict)}"

        except Exception as e:
            return f"Ошибка балансировки: {str(e)}"


class UnitConverter:
    # База данных коэффициентов (относительно базовой единицы)
    UNITS = {
        "Температура": ["C", "K", "F"],
        "Давление": {
            "Pa": 1.0, "kPa": 1000.0, "MPa": 1000000.0, "bar": 100000.0,
            "atm": 101325.0, "mmHg": 133.322, "psi": 6894.76
        },
        "Объем": {
            "L": 1.0, "mL": 0.001, "m3": 1000.0, "cm3": 0.001, "gal(US)": 3.78541
        },
        "Энергия": {
            "J": 1.0, "kJ": 1000.0, "cal": 4.184, "kcal": 4184.0, "eV": 1.602e-19
        },
        "Масса": {
            "g": 1.0, "kg": 1000.0, "mg": 0.001, "mcg": 1e-6,
            "lb": 453.592, "oz": 28.3495, "ton": 1e6
        },
        "Длина": {
            "m": 1.0, "cm": 0.01, "mm": 0.001, "km": 1000.0,
            "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.34
        },
        "Время": {
            "s": 1.0, "min": 60.0, "h": 3600.0, "d": 86400.0
        },
        "Концентрация": {
            "M": 1.0, "mM": 0.001, "µM": 1e-6, "nM": 1e-9,
            "ppm": 1e-3, "ppb": 1e-6, "g/L": None
        },
        "Давление_расш": {
            "Pa": 1.0, "kPa": 1000.0, "MPa": 1000000.0, "bar": 100000.0,
            "atm": 101325.0, "mmHg": 133.322, "psi": 6894.76,
            "Torr": 133.322, "mmH2O": 9.80665
        }
    }

    @staticmethod
    def convert(val: float, category: str, u_from: str, u_to: str) -> Optional[float]:
        try:
            if category == "Температура":
                k = val
                if u_from == "C":
                    k = val + 273.15
                elif u_from == "F":
                    k = (val - 32) * 5 / 9 + 273.15

                if u_to == "K":
                    return k
                if u_to == "C":
                    return k - 273.15
                if u_to == "F":
                    return (k - 273.15) * 9 / 5 + 32
                return None

            if category in UnitConverter.UNITS:
                table = UnitConverter.UNITS[category]
                if u_from in table and u_to in table:
                    from_factor = table[u_from]
                    to_factor = table[u_to]
                    # Если один из факторов None (например, g/L в концентрации)
                    if from_factor is None or to_factor is None:
                        return None
                    base_val = val * from_factor
                    return base_val / to_factor

            return None
        except Exception as e:
            print(f"Conversion error: {e}")
            return None


# ЗАГЛУШКА ИИ АССИСТЕНТА
class AIAssistantStub:
    @staticmethod
    def ask(query: str) -> str:
        return f"Я пока не подключен к мозгу, но я слышу вас: '{query}'. \n(ИИ Ассистент находится в разработке)"
