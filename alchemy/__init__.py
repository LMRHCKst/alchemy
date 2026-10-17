"""Alchemy — химический калькулятор.

Слоистая архитектура:

    alchemy/core      — фундамент: константы, единицы, формулы, результат
    alchemy/data      — справочные базы данных в JSON
    alchemy/engines   — расчётные движки (без единого импорта tkinter)
    alchemy/ui        — интерфейс

Движки не зависят от интерфейса: их можно использовать отдельно, в скриптах
и в тестах. Это то, чего не хватало прежней версии, где расчёты были
размазаны по вкладкам.

Быстрый старт:

    from alchemy.engines import thermo
    print(thermo.reaction_enthalpy("H2 + O2 = H2O(ж)").numeric())

Запуск приложения:

    python main.py
"""

__version__ = "3.0"
__all__ = ["core", "data", "engines", "ui"]
