"""Главное окно приложения.

Функции разделены на два блока:

    ОСНОВНЫЕ МОДУЛИ        — то, что нужно на каждом занятии и в каждой задаче;
    ДОПОЛНИТЕЛЬНЫЕ МОДУЛИ  — углублённые расчёты, справочные инструменты,
                             работа с экспериментальными данными.

Такое деление оправдано: новичку не нужно продираться через диаграммы Пурбе
и обработку кинетических данных, а опытному пользователю не приходится
искать нужное среди базовых калькуляторов.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import customtkinter as ctk

from ..core.results import Result
from .components import (
    COLOR_ACCENT, COLOR_BG, COLOR_CARD, COLOR_ERROR, COLOR_OK,
    COLOR_TEXT, COLOR_TEXT_DIM, FONT_BODY, FONT_SMALL, FONT_TITLE,
    setup_theme,
)
from .tabs_advanced import (
    ColligativeTab, ElectrolysisTab, EquilibriumTab, GraphsTab, HandbookTab,
    HistoryTab, IndicatorTab, KineticsDataTab, NuclearTab, PracticeTab,
    TitrationTab, UncertaintyTab,
)
from .tabs_basic import (
    AcidBaseTab, BalancerTab, BufferTab, ElectrochemistryTab,
    FormulaAnalysisTab, GasTab, KineticsTab, MolarMassTab, PeriodicTableTab,
    SolutionTab, StoichiometryTab, ThermoTab,
)


APP_TITLE = "Alchemy — химический калькулятор"
APP_VERSION = "3.0"


@dataclass
class TabSpec:
    """Описание вкладки для меню."""

    title: str
    description: str
    cls: type
    group: str
    icon: str = ""


BASIC_TABS: list[TabSpec] = [
    TabSpec("Молярная масса", "Масса и состав вещества", MolarMassTab, "basic", "M"),
    TabSpec("Анализ формулы", "Простейшая и молекулярная формула", FormulaAnalysisTab,
            "basic", "F"),
    TabSpec("Уравнивание реакций", "Коэффициенты методом Гаусса", BalancerTab,
            "basic", "="),
    TabSpec("Стехиометрия", "Лимитирующий реагент и выход", StoichiometryTab,
            "basic", "S"),
    TabSpec("Растворы и концентрации", "C, w, b, X, ppm и рецепты", SolutionTab,
            "basic", "C"),
    TabSpec("Кислоты и основания", "pH с учётом активностей", AcidBaseTab,
            "basic", "pH"),
    TabSpec("Буферные растворы", "pH, ёмкость, приготовление", BufferTab,
            "basic", "B"),
    TabSpec("Газовые законы", "Идеальный и реальный газ", GasTab, "basic", "PV"),
    TabSpec("Термохимия", "ΔH, ΔS, ΔG, равновесие", ThermoTab, "basic", "H"),
    TabSpec("Химическая кинетика", "Скорость, Аррениус, порядок", KineticsTab,
            "basic", "k"),
    TabSpec("Электрохимия", "Нернст, элементы, электролиз", ElectrochemistryTab,
            "basic", "E"),
    TabSpec("Таблица Менделеева", "118 элементов со свойствами", PeriodicTableTab,
            "basic", "Z"),
]

ADVANCED_TABS: list[TabSpec] = [
    TabSpec("Равновесия и активности", "Ионная сила, коэффициенты активности",
            EquilibriumTab, "advanced", "γ"),
    TabSpec("Кривые титрования", "Из решения равновесий", TitrationTab,
            "advanced", "T"),
    TabSpec("Подбор индикатора", "Погрешность титрования", IndicatorTab,
            "advanced", "i"),
    TabSpec("Коллигативные свойства", "ΔT кип, ΔT зам, осмос", ColligativeTab,
            "advanced", "Δ"),
    TabSpec("Обработка кинетических данных", "Порядок реакции по точкам",
            KineticsDataTab, "advanced", "k(t)"),
    TabSpec("Расчёт электролиза", "Продукты, напряжение, энергия",
            ElectrolysisTab, "advanced", "I"),
    TabSpec("Ядерная химия", "Распад, активность, энергия ядра", NuclearTab,
            "advanced", "N"),
    TabSpec("Погрешности", "Неопределённости и значащие цифры", UncertaintyTab,
            "advanced", "±"),
    TabSpec("Справочник веществ", "Все базы данных с источниками", HandbookTab,
            "advanced", "DB"),
    TabSpec("Графики", "По реальным расчётам, а не по заготовкам", GraphsTab,
            "advanced", "∿"),
    TabSpec("Журнал операций", "История расчётов и экспорт", HistoryTab,
            "advanced", "J"),
    TabSpec("Проверка расчётов", "Тренажёр с проверкой ответа", PracticeTab,
            "advanced", "?"),
]


class AlchemyApp(ctk.CTk):
    """Главное окно."""

    def __init__(self):
        super().__init__()

        self.history: list[dict] = []
        self._tabs: dict[type, ctk.CTkFrame] = {}
        self._buttons: dict[type, ctk.CTkButton] = {}
        self._current: ctk.CTkFrame | None = None

        self.title(f"{APP_TITLE} {APP_VERSION}")
        self.geometry("1400x920")
        self.minsize(1100, 700)
        self.configure(fg_color=COLOR_BG)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_content()
        self._build_statusbar()

        # Стартуем с первой основной вкладки
        self.show(BASIC_TABS[0].cls)

    # ---------------- построение ----------------

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkScrollableFrame(self, width=270, corner_radius=0,
                                         fg_color="#121212")
        sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar = sidebar

        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(18, 6))

        ctk.CTkLabel(header, text="ALCHEMY", font=("Segoe UI", 24, "bold"),
                     text_color=COLOR_ACCENT, anchor="w").pack(fill="x")
        ctk.CTkLabel(header, text=f"химический калькулятор {APP_VERSION}",
                     font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
                     anchor="w").pack(fill="x")

        self._add_group(sidebar, "ОСНОВНЫЕ МОДУЛИ", BASIC_TABS)
        self._add_group(sidebar, "ДОПОЛНИТЕЛЬНЫЕ МОДУЛИ", ADVANCED_TABS)

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(16, 20))
        ctk.CTkLabel(
            footer,
            text="Все расчёты выполняются локально.\n"
                 "Справочные данные и источники\nуказаны в результатах.",
            font=("Segoe UI", 9), text_color="#6a6a6a",
            justify="left", anchor="w").pack(fill="x")

    def _add_group(self, parent, title: str, tabs: list[TabSpec]) -> None:
        ctk.CTkLabel(parent, text=title, font=("Segoe UI", 10, "bold"),
                     text_color="#6a6a6a", anchor="w").pack(
            fill="x", padx=16, pady=(14, 4))

        for spec in tabs:
            button = ctk.CTkButton(
                parent, text=f"  {spec.title}", anchor="w",
                fg_color="transparent", hover_color="#252525",
                text_color=COLOR_TEXT, font=FONT_BODY, height=34,
                command=lambda s=spec: self.show(s.cls),
            )
            button.pack(fill="x", padx=8, pady=1)
            self._buttons[spec.cls] = button

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=18, pady=(18, 0))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, height=28, fg_color="#121212", corner_radius=0)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.status_label = ctk.CTkLabel(
            bar, text="Готово", font=("Segoe UI", 10),
            text_color=COLOR_TEXT_DIM, anchor="w")
        self.status_label.pack(side="left", padx=16, pady=3)

        self.count_label = ctk.CTkLabel(
            bar, text="", font=("Segoe UI", 10),
            text_color="#5a5a5a", anchor="e")
        self.count_label.pack(side="right", padx=16, pady=3)
        self._update_count()

    def _update_count(self) -> None:
        self.count_label.configure(
            text=f"расчётов в журнале: {len(self.history)}")

    # ---------------- переключение вкладок ----------------

    def show(self, cls: type) -> None:
        """Показать вкладку, создав её при первом обращении."""
        if self._current is not None:
            self._current.grid_forget()

        frame = self._tabs.get(cls)
        if frame is None:
            try:
                frame = cls(self.content, self)
            except Exception as exc:
                self._show_fatal(cls, exc)
                return
            self._tabs[cls] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self._current = frame
        frame.grid(row=0, column=0, sticky="nsew")

        # Подсветка активной кнопки
        for tab_cls, button in self._buttons.items():
            if tab_cls is cls:
                button.configure(fg_color="#1f3a52", text_color=COLOR_ACCENT)
            else:
                button.configure(fg_color="transparent", text_color=COLOR_TEXT)

        title = getattr(frame, "title", cls.__name__)
        self.status_label.configure(text=f"{title}", text_color=COLOR_TEXT_DIM)

    def _show_fatal(self, cls: type, exc: Exception) -> None:
        """Показать сообщение, если вкладку не удалось создать."""
        from tkinter import messagebox
        messagebox.showerror(
            "Ошибка вкладки",
            f"Не удалось открыть вкладку {cls.__name__}:\n"
            f"{type(exc).__name__}: {exc}",
        )

    # ---------------- журнал ----------------

    def log_operation(self, action: str, result: Result) -> None:
        """Записать операцию в журнал."""
        entry = {
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "result": result.formatted(),
            "detail": result.summary(),
            "warnings": list(result.warnings),
        }
        self.history.insert(0, entry)
        if len(self.history) > 500:
            self.history.pop()

        self.status_label.configure(
            text=f"{action}: {result.formatted()}"[:120],
            text_color=COLOR_ERROR if result.has_warnings else COLOR_OK,
        )
        self._update_count()

    def transfer(self, target_cls: type, key: str, value) -> None:
        """Передать данные на другую вкладку (для связей между модулями)."""
        self.show(target_cls)
        frame = self._tabs.get(target_cls)
        receiver = getattr(frame, "receive_data", None)
        if receiver is not None:
            try:
                receiver(key, value)
            except Exception:
                pass


def run() -> None:
    """Запустить приложение."""
    setup_theme()
    app = AlchemyApp()
    app.mainloop()
