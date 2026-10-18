"""Точка входа приложения Alchemy.

Запуск:
    python main.py

Интерфейс на Qt. Прежний на tkinter удалён: он тянул за собой слой
совместимости, а расчёты в обоих и так совпадали.

Программа не устанавливает пакеты самостоятельно: зависимости указываются
явно, а справочные данные лежат в alchemy/data, поэтому интернет не нужен.
"""

from __future__ import annotations

import os
import sys

# Корень проекта в путь поиска модулей — чтобы запуск работал
# из любой рабочей папки
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_dependencies(qt: bool = False) -> list[str]:
    """Проверить наличие необходимых пакетов."""
    import importlib.util

    required = {
        "matplotlib": "matplotlib",
        "PySide6": "PySide6",
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


def install_hint(missing: list[str], qt: bool) -> str:
    """Подсказка по установке недостающих пакетов."""
    packages = {
        "PySide6": "PySide6-Essentials",
        "matplotlib": "matplotlib",
    }
    names = " ".join(packages.get(item, item) for item in missing)
    return f"    {sys.executable} -m pip install {names}"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    use_qt = True

    missing = check_dependencies(qt=use_qt)
    if missing:
        print("Не хватает библиотек: " + ", ".join(missing))
        print()
        print("Установите их командой:")
        print(install_hint(missing, use_qt))
        return 1

    missing_data = check_data()
    if missing_data:
        print("Не найдены файлы справочников: " + ", ".join(missing_data))
        print("Проверьте целостность папки alchemy/data")
        return 1

    from alchemy.ui_qt.app import run as qt_run
    return qt_run([sys.argv[0], *args])


if __name__ == "__main__":
    sys.exit(main())
