"""Подмена backend: вкладки думают, что работают на tkinter, а рисует Qt.

Модуль ставится в sys.modules до первого импорта вкладок, поэтому
`import customtkinter as ctk` и `from .components import ...` внутри
alchemy/ui/tabs_*.py получают Qt-реализации.

Порядок важен: install() вызывается до импорта вкладок.
"""

from __future__ import annotations

import sys
import types

_installed = False


def install() -> None:
    """Подменить tkinter-модули на Qt-реализации."""
    global _installed
    if _installed:
        return

    from . import components_tk, tkcompat

    # 1. customtkinter → Qt-виджеты
    sys.modules["customtkinter"] = tkcompat

    # 2. Компоненты вкладок → Qt-версия с прежним API
    sys.modules["alchemy.ui.components"] = components_tk

    # 3. Диалоги tkinter → диалоги Qt
    filedialog = types.ModuleType("tkinter.filedialog")
    filedialog.asksaveasfilename = tkcompat.filedialog.asksaveasfilename
    filedialog.askopenfilename = tkcompat.filedialog.askopenfilename
    sys.modules["tkinter.filedialog"] = filedialog

    messagebox = types.ModuleType("tkinter.messagebox")
    messagebox.showinfo = tkcompat.messagebox.showinfo
    messagebox.showwarning = tkcompat.messagebox.showwarning
    messagebox.showerror = tkcompat.messagebox.showerror
    messagebox.askyesno = tkcompat.messagebox.askyesno
    sys.modules["tkinter.messagebox"] = messagebox

    try:
        import tkinter

        tkinter.filedialog = filedialog
        tkinter.messagebox = messagebox
    except ImportError:      # pragma: no cover
        pass

    # 4. Бэкенд matplotlib для встраивания графиков
    #    Вкладка «Графики» зовёт matplotlib.use("TkAgg") и импортирует
    #    FigureCanvasTkAgg. Модуль-заглушка отдаёт Qt-реализацию и
    #    подставляет остальные имена, которые matplotlib ищет при смене
    #    бэкенда (FigureCanvas, FigureManager, show).
    backend = types.ModuleType("matplotlib.backends.backend_tkagg")
    backend.FigureCanvasTkAgg = tkcompat.FigureCanvasTkAgg

    def _resolve(name: str):
        if name == "FigureCanvas":
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

            return FigureCanvasQTAgg
        if name == "FigureManager":
            class _QtFigureManager:
                """Заглушка менеджера: окна рисует сам Qt."""

                def __init__(self, canvas=None, num=None):
                    self.canvas = canvas
                    self.num = num

                @staticmethod
                def destroy():
                    """Окно закрывает контейнер Qt."""

            return _QtFigureManager
        if name == "show":
            return lambda *args, **kwargs: None
        if name in ("new_figure_manager", "new_figure_manager_given_figure"):
            from matplotlib.backends.backend_qtagg import (
                FigureCanvasQTAgg, new_figure_manager_given_figure,
            )

            return new_figure_manager_given_figure
        raise AttributeError(name)

    backend.__getattr__ = _resolve
    sys.modules["matplotlib.backends.backend_tkagg"] = backend

    _installed = True
