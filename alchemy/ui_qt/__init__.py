"""Qt-интерфейс химического калькулятора.

Собирается параллельно с tkinter-версией: вкладки переносятся постепенно,
поэтому оба интерфейса работают на одних и тех же движках.
"""

from __future__ import annotations

__all__ = ["run"]


def run(argv: list[str] | None = None) -> int:
    """Запустить Qt-интерфейс."""
    from .app import run as _run

    return _run(argv)
