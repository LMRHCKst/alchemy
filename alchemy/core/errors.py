"""Типы ошибок и предупреждений расчётных движков.

Разделение важное: часть проблем должна останавливать расчёт (нельзя посчитать
pH раствора с отрицательной концентрацией), а часть — только предупреждать
(расчёт возможен, но модель работает за границей применимости).
"""

from __future__ import annotations


class AlchemyError(Exception):
    """Базовая ошибка программы."""


class InputError(AlchemyError, ValueError):
    """Некорректный ввод: нечисловое значение, пустое поле, битый формат."""


class DomainError(AlchemyError, ValueError):
    """Величина физически бессмысленна: отрицательная масса, объём = 0."""


class OutOfRangeError(DomainError):
    """Величина вышла за область определения модели.

    Пример: концентрация 5 моль/л для формулы pH = -lg C. Формально число
    посчитать можно, но ответ будет неверным.
    """


class ConvergenceError(AlchemyError):
    """Итерационный процесс не сошёлся."""


class DataNotFoundError(AlchemyError, KeyError):
    """Величины нет в справочной базе."""


class ModelError(AlchemyError):
    """Модель неприменима к данной системе."""


class Warning_(AlchemyError):
    """Предупреждение о качестве расчёта. Не прерывает вычисление."""

    def __init__(self, message: str, kind: str = "general"):
        super().__init__(message)
        self.message = message
        self.kind = kind

    def __str__(self) -> str:
        return self.message
