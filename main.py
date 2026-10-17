"""Точка входа приложения Alchemy.

Запуск:
    python main.py

Программа не устанавливает пакеты самостоятельно: зависимости указываются
явно, а справочные данные лежат в alchemy/data, поэтому интернет не нужен.
"""

from __future__ import annotations

import os
import sys

# Корень проекта в путь поиска модулей — чтобы запуск работал
# из любой рабочей папки
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_dependencies() -> list[str]:
    """Проверить наличие необходимых пакетов."""
    import importlib.util

    required = {
        "customtkinter": "customtkinter",
        "matplotlib": "matplotlib",
    }
    missing = []
    for module, label in required.items():
        if importlib.util.find_spec(module) is None:
            missing.append(label)
    return missing


def check_data() -> list[str]:
    """Проверить наличие справочных файлов."""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "alchemy", "data")
    expected = ["elements.json", "thermo.json", "electrodes.json",
                "acids.json", "solubility.json", "solvents.json"]
    return [name for name in expected
            if not os.path.exists(os.path.join(data_dir, name))]


def main() -> int:
    missing = check_dependencies()
    if missing:
        print("Не хватает библиотек: " + ", ".join(missing))
        print()
        print("Установите их командой:")
        print(f"    {sys.executable} -m pip install customtkinter matplotlib")
        return 1

    missing_data = check_data()
    if missing_data:
        print("Не найдены файлы справочников: " + ", ".join(missing_data))
        print("Проверьте целостность папки alchemy/data")
        return 1

    from alchemy.ui.app import run
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
