"""Загрузка JSON-справочников из папки data.

Все справочники читаются один раз и кэшируются. Файлы лежат рядом с кодом,
поэтому программа работает офлайн и не зависит от версий внешних библиотек.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from ..core.errors import DataNotFoundError

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


@lru_cache(maxsize=32)
def load(filename: str) -> dict:
    """Прочитать справочник по имени файла. Результат кэшируется."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        raise DataNotFoundError(
            f"Не найден файл справочника: {path}"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_meta(filename: str) -> dict[str, Any]:
    """Метаданные справочника: источник, единицы, примечания."""
    data = load(filename)
    return {k: v for k, v in data.items() if k.startswith("_")}


def source_of(filename: str) -> str:
    """Строка с источником данных для отображения в результате."""
    data = load(filename)
    return data.get("_source", "источник не указан")


def available_files() -> list[str]:
    """Список доступных справочников."""
    return sorted(
        f for f in os.listdir(DATA_DIR)
        if f.endswith(".json") and f != "names_ru.json"
    )


def exists() -> bool:
    """Проверить, что базовая папка данных на месте."""
    return os.path.isdir(DATA_DIR)


def stats() -> dict[str, int]:
    """Сколько записей в каждом справочнике — для окна «О справочниках»."""
    result: dict[str, int] = {}

    thermo = load("thermo.json")
    result["Вещества (термодинамика)"] = len(thermo.get("substances", {}))
    result["Ионы (термодинамика)"] = len(thermo.get("ions", {}))
    result["Фазовые переходы"] = len(thermo.get("phase_transitions", {}))

    electrodes = load("electrodes.json")
    result["Электродные потенциалы"] = len(electrodes.get("electrodes", []))

    acids = load("acids.json")
    result["Кислоты"] = len(acids.get("acids", []))
    result["Основания"] = len(acids.get("bases", []))
    result["Индикаторы"] = len(acids.get("ph_indicators", []))

    solubility = load("solubility.json")
    result["Малорастворимые соединения"] = len(solubility.get("solids", []))

    solvents = load("solvents.json")
    result["Растворители"] = len(solvents.get("solvents", []))
    result["Таблицы плотности растворов"] = len(solvents.get("solution_density", {})) - 1

    result["Элементы"] = len(load("elements.json").get("elements", {}))

    # Полиномы Cp(T) — отдельная база, шире компактного справочника
    try:
        from . import polynomials as POLY
        result["Вещества с Cp(T)"] = POLY.count()
    except Exception:
        # Файл полиномов необязателен: программа работает и без него
        pass

    return result
