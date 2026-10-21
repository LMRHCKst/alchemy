"""Главное окно Qt-интерфейса.

Вкладки берутся из пакета alchemy.ui: там же лежат их компоненты и виджеты.
"""

from __future__ import annotations

import datetime
import sys
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.results import Result
from ..ui import theme
from . import prefs

from ..ui.tabs_advanced import (
    ColligativeTab, ElectrolysisTab, EquilibriumTab, GraphsTab, HandbookTab,
    HistoryTab, IndicatorTab, KineticsDataTab, NuclearTab, PracticeTab,
    TitrationTab, UncertaintyTab,
)
from ..ui.tabs_basic import (
    AcidBaseTab, BalancerTab, BufferTab, ElectrochemistryTab,
    FormulaAnalysisTab, GasTab, KineticsTab, MolarMassTab, PeriodicTableTab,
    SolutionTab, StoichiometryTab, ThermoTab,
)
from ..ui.tabs_organic import (       # noqa: E402
    CombustionTab, OrganicClassesTab, OrganicReactionsTab,
)
from ..ui.tabs_school import (
    HydrolysisTab, IonicTab, SolubilityTab, ValenceTab,
    BondingTab, ClassesTab, HardnessTab, OxidationTab, QualitativeTab,
    RedoxTab, ShiftTab,
)
from .ai_tab import AiTab
from .cantera_tab import CanteraTab


APP_TITLE = "Alchemy — химический калькулятор"

#: Подпись сборки вместо номера версии. Номер появится, когда будет что
#: нумеровать: сейчас это рабочая сборка, а не релиз.
APP_LABEL = "нестабильная сборка"

#: Значок беты — греческая буква, как в сервисах Яндекса
BETA_TEXT = "β"
BETA_TOOLTIP = "бета: нестабильная сборка"


@dataclass
class TabSpec:
    """Описание вкладки для меню."""

    title: str
    description: str
    cls: type
    group: str


BASIC_TABS: list[TabSpec] = [
    TabSpec("Молярная масса", "Масса и состав вещества", MolarMassTab, "basic"),
    TabSpec("Анализ формулы", "Простейшая и молекулярная формула",
            FormulaAnalysisTab, "basic"),
    TabSpec("Уравнивание реакций", "Коэффициенты методом Гаусса", BalancerTab,
            "basic"),
    TabSpec("Стехиометрия", "Лимитирующий реагент и выход", StoichiometryTab,
            "basic"),
    TabSpec("Растворы и концентрации", "C, w, b, X, ppm и рецепты", SolutionTab,
            "basic"),
    TabSpec("Кислоты и основания", "pH с учётом активностей", AcidBaseTab,
            "basic"),
    TabSpec("Буферные растворы", "pH, ёмкость, приготовление", BufferTab,
            "basic"),
    TabSpec("Газовые законы", "Идеальный и реальный газ", GasTab, "basic"),
    TabSpec("Термохимия", "ΔH, ΔS, ΔG, равновесие", ThermoTab, "basic"),
    TabSpec("Химическая кинетика", "Скорость, Аррениус, порядок", KineticsTab,
            "basic"),
    TabSpec("Электрохимия", "Нернст, элементы, электролиз",
            ElectrochemistryTab, "basic"),
    TabSpec("Таблица Менделеева", "118 элементов со свойствами",
            PeriodicTableTab, "basic"),
    TabSpec("Степени окисления", "СО, тип реакции, окислитель",
            OxidationTab, "basic"),
    TabSpec("Классы и названия", "Класс вещества и номенклатура",
            ClassesTab, "basic"),
    TabSpec("Валентность", "Валентность по формуле и обратно", ValenceTab, "valence"),
    TabSpec("Ионные уравнения", "Молекулярное в ионное", IonicTab, "ionic"),
    TabSpec("Гидролиз солей", "Среда, константа, степень", HydrolysisTab, "hydrolysis"),
    TabSpec("Растворимость и pH", "Осадки и влияние кислотности",
            SolubilityTab, "solubility"),
    TabSpec("Органические классы", "Класс, гомологи, изомеры", 
            OrganicClassesTab, "basic"),
    TabSpec("Формула по сгоранию", "Формула из продуктов сгорания",
            CombustionTab, "basic"),
]

ADVANCED_TABS: list[TabSpec] = [
    TabSpec("Равновесия и активности", "Ионная сила, коэффициенты активности",
            EquilibriumTab, "advanced"),
    TabSpec("Кривые титрования", "Из решения равновесий", TitrationTab,
            "advanced"),
    TabSpec("Подбор индикатора", "Погрешность титрования", IndicatorTab,
            "advanced"),
    TabSpec("Коллигативные свойства", "ΔT кип, ΔT зам, осмос", ColligativeTab,
            "advanced"),
    TabSpec("Обработка кинетических данных", "Порядок реакции по точкам",
            KineticsDataTab, "advanced"),
    TabSpec("Расчёт электролиза", "Продукты, напряжение, энергия",
            ElectrolysisTab, "advanced"),
    TabSpec("Ядерная химия", "Распад, активность, энергия ядра", NuclearTab,
            "advanced"),
    TabSpec("Газы: равновесие и горение", "Равновесие и горение на Cantera",
            CanteraTab, "advanced"),
    TabSpec("Погрешности", "Неопределённости и значащие цифры",
            UncertaintyTab, "advanced"),
    TabSpec("Справочник веществ", "Все базы данных с источниками",
            HandbookTab, "advanced"),
    TabSpec("Графики", "Кривые по реальным расчётам", GraphsTab, "advanced"),
    TabSpec("Журнал операций", "История расчётов и протокол", HistoryTab,
            "advanced"),
    TabSpec("Проверка расчётов", "Тренажёр с проверкой ответа", PracticeTab,
            "advanced"),
    TabSpec("Электронный баланс", "ОВР методом электронного баланса",
            RedoxTab, "advanced"),
    TabSpec("Строение вещества", "Тип связи и кристаллическая решётка",
            BondingTab, "advanced"),
    TabSpec("Смещение равновесия", "Принцип Ле Шателье", ShiftTab,
            "advanced"),
    TabSpec("Жёсткость воды", "Градусы жёсткости и умягчение",
            HardnessTab, "advanced"),
    TabSpec("Определитель ионов", "Качественные реакции", QualitativeTab,
            "advanced"),
    TabSpec("Реакции органики", "Реакции классов, пробы, полимеры",
            OrganicReactionsTab, "advanced"),
]

#: отдельный блок в меню: не модуль расчёта, а разговор с моделью
CHAT_TABS: list[TabSpec] = [
    TabSpec("ИИ-расчётчик", "Вопрос словами, считает движок", AiTab, "chat"),
]


class AlchemyApp(QMainWindow):
    """Главное окно на Qt."""

    def __init__(self):
        super().__init__()

        self.history: list[dict] = []
        self._tabs: dict[type, QWidget] = {}
        self._items: dict[type, QListWidgetItem] = {}

        self.setWindowTitle(f"{APP_TITLE} ({BETA_TEXT})")

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack, 1)
        right_layout.addWidget(self._build_statusbar())

        layout.addWidget(right, 1)
        self.setCentralWidget(central)

        self._build_menu()

        self.resize(1400, 920)
        self.setMinimumSize(1100, 700)

        self.open_tab(BASIC_TABS[0].cls)

    # ---------------- меню и экспорт ----------------


    # ---------------- поиск, история, тема ----------------

    def _filter_modules(self, text: str) -> None:
        """Оставить в меню только модули, подходящие под запрос.

        Ищем и по названию, и по описанию: «гидролиз» найдётся и по
        заголовку, и по подсказке. Заголовки разделов прячутся, если в
        разделе не осталось ни одного модуля.
        """
        query = text.strip().lower()
        visible_by_group: dict[str, int] = {}
        current_group = ""

        for index in range(self.nav.count()):
            item = self.nav.item(index)
            cls = item.data(Qt.UserRole)
            if cls is None:
                title = item.text()
                if title:
                    current_group = title
                continue
            spec_title = item.text().lower()
            tooltip = (item.toolTip() or "").lower()
            matches = (not query or query in spec_title or query in tooltip)
            item.setHidden(not matches)
            if matches:
                visible_by_group[current_group] =                     visible_by_group.get(current_group, 0) + 1

        # заголовки и отступы показываем только у непустых разделов
        current_group = ""
        for index in range(self.nav.count()):
            item = self.nav.item(index)
            if item.data(Qt.UserRole) is not None:
                continue
            title = item.text()
            if title:
                current_group = title
                item.setHidden(bool(query) and not visible_by_group.get(title))
            else:
                # пустой пункт — отступ или линия: прячем вместе с разделом
                item.setHidden(bool(query) and not visible_by_group.get(current_group))

    def _focus_search(self) -> None:
        """Ctrl+F: перейти к поиску."""
        self.search.setFocus()
        self.search.selectAll()

    def _remember_tab(self, cls: type) -> None:
        """Запомнить переход для истории навигации."""
        if not hasattr(self, "_nav_history"):
            self._nav_history: list[type] = []
            self._nav_position = -1
        if self._nav_position >= 0 and \
                self._nav_position < len(self._nav_history) and \
                self._nav_history[self._nav_position] is cls:
            return
        del self._nav_history[self._nav_position + 1:]
        self._nav_history.append(cls)
        self._nav_position = len(self._nav_history) - 1

    def _go_back(self) -> None:
        """Назад по истории переходов."""
        if getattr(self, "_nav_position", -1) <= 0:
            return
        self._nav_position -= 1
        self._select_tab(self._nav_history[self._nav_position])

    def _go_forward(self) -> None:
        """Вперёд по истории переходов."""
        history = getattr(self, "_nav_history", [])
        if getattr(self, "_nav_position", -1) + 1 >= len(history):
            return
        self._nav_position += 1
        self._select_tab(history[self._nav_position])

    def _select_tab(self, cls: type) -> None:
        """Открыть вкладку, не добавляя её в историю."""
        item = self._items.get(cls)
        if item is None:
            return
        self.nav.blockSignals(True)
        self.nav.setCurrentItem(item)
        self.nav.blockSignals(False)
        self.open_tab(cls)
        self._remember_tab(cls)


    def _rebuild_open_tabs(self) -> None:
        """Пересобрать открытые вкладки после смены темы.

        Часть надписей задаёт цвет при создании. Чтобы светлая тема
        применилась целиком и сразу, вкладки пересоздаются: это дешевле,
        чем обходить все виджеты и уговаривать их перекраситься.
        """
        current = self.current_tab()
        cls = type(current) if current is not None else None

        for widget in list(self._tabs.values()):
            self.stack.removeWidget(widget)
            widget.deleteLater()
        self._tabs.clear()

        if cls is not None:
            self.open_tab(cls)

    def _toggle_theme(self, light: bool) -> None:
        """Переключить тему и запомнить выбор."""
        from . import prefs

        prefs.set_light(light)
        theme.apply_theme(QApplication.instance(), light=light)
        self._rebuild_open_tabs()
        self.status_label.setText(
            "Светлая тема" if light else "Тёмная тема")

    def build_latex_document(self) -> str:
        """Собрать LaTeX-документ из текущего расчёта."""
        tab = self.current_tab()
        view = getattr(tab, "result_view", None)
        result = getattr(view, "last_result", None) if view is not None else None
        if result is None:
            self._warn("Сначала выполните расчёт.")
            return

        math = getattr(view, "_latex_text", "") or ""
        title = getattr(tab, "title", "Расчёт")

        lines = [
            r"\documentclass[12pt]{article}",
            r"\usepackage[T2A]{fontenc}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage[russian]{babel}",
            r"\usepackage{amsmath}",
            r"\begin{document}",
            "",
            rf"\section*{{{title}}}",
            "",
        ]
        if math:
            lines.append(r"\begin{equation*}")
            lines.append(math)
            lines.append(r"\end{equation*}")
            lines.append("")

        value = getattr(result, "value", None)
        if value is not None and not isinstance(value, (dict, list)):
            unit = getattr(result, "unit", "") or ""
            lines.append(rf"\noindent\textbf{{Результат:}} {value} {unit}".strip())
            lines.append("")

        method = getattr(result, "method", "") or ""
        if method:
            lines.append(rf"\noindent\textit{{{method}}}")
            lines.append("")

        steps = getattr(result, "steps", []) or []
        if steps:
            lines.append(r"\subsection*{Ход расчёта}")
            lines.append(r"\begin{enumerate}")
            for step in steps:
                safe = str(step).replace("_", r"\_").replace("%", r"\%")
                lines.append(rf"  \item {safe}")
            lines.append(r"\end{enumerate}")
            lines.append("")

        warnings = getattr(result, "warnings", []) or []
        if warnings:
            lines.append(r"\subsection*{Предупреждения}")
            lines.append(r"\begin{itemize}")
            for warning in warnings:
                safe = str(warning).replace("_", r"\_").replace("%", r"\%")
                lines.append(rf"  \item {safe}")
            lines.append(r"\end{itemize}")
            lines.append("")

        lines.append(r"\end{document}")
        return "\n".join(lines)

    def export_latex(self) -> None:
        """Сохранить текущий расчёт в файл LaTeX."""
        from PySide6.QtWidgets import QFileDialog

        text = self.build_latex_document()
        if not text:
            return

        tab = self.current_tab()
        title = getattr(tab, "title", "Расчёт")
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в LaTeX", f"{title}.tex", "LaTeX (*.tex)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as exc:
            self._warn(f"Не удалось сохранить: {exc}")
            return
        self.status_label.setText(f"Сохранено: {path}")

    def _build_menu(self) -> None:
        """Меню: выгрузка отчёта в DOCX и копирование LaTeX."""
        bar = self.menuBar()

        file_menu = bar.addMenu("Файл")

        action = file_menu.addAction("Экспорт журнала в DOCX…")
        action.triggered.connect(self.export_journal_docx)

        action = file_menu.addAction("Экспорт текущего расчёта в DOCX…")
        action.triggered.connect(self.export_result_docx)

        file_menu.addSeparator()
        action = file_menu.addAction("Выход")
        action.triggered.connect(self.close)

        action = file_menu.addAction("Экспорт расчёта в LaTeX…")
        action.triggered.connect(self.export_latex)

        edit_menu = bar.addMenu("Правка")
        action = edit_menu.addAction("Копировать LaTeX")
        action.triggered.connect(self.copy_latex)

        action = edit_menu.addAction("Поиск по модулям")
        action.setShortcut(QKeySequence("Ctrl+F"))
        action.triggered.connect(self._focus_search)

        action = edit_menu.addAction("Назад")
        action.setShortcut(QKeySequence("Alt+Left"))
        action.triggered.connect(self._go_back)

        action = edit_menu.addAction("Вперёд")
        action.setShortcut(QKeySequence("Alt+Right"))
        action.triggered.connect(self._go_forward)

        view_menu = bar.addMenu("Вид")
        self._light_action = view_menu.addAction("Светлая тема")
        self._light_action.setCheckable(True)
        self._light_action.setChecked(prefs.is_light())
        self._light_action.toggled.connect(self._toggle_theme)

        help_menu = bar.addMenu("Справка")
        action = help_menu.addAction("О программе")
        action.triggered.connect(self._about)

    def current_tab(self):
        """Вкладка, которая сейчас открыта."""
        return self.stack.currentWidget()

    def _ask_path(self, title: str) -> str:
        from PySide6.QtWidgets import QFileDialog

        from ..core import report as report_module

        path, _ = QFileDialog.getSaveFileName(
            self, title, report_module.suggested_name(), "Документ Word (*.docx)")
        return path

    def export_journal_docx(self) -> None:
        """Сохранить журнал операций в DOCX."""
        from ..core import report as report_module

        if not report_module.available():
            self._warn(
                "Для выгрузки в DOCX нужен пакет python-docx.\n"
                "Установите его:  python -m pip install python-docx")
            return

        path = self._ask_path("Экспорт журнала в DOCX")
        if not path:
            return

        try:
            report_module.export_journal(path, self.history)
        except Exception as exc:
            self._warn(f"Не удалось сохранить: {exc}")
            return

        self.status_label.setText(f"Журнал сохранён: {path}")

    def export_result_docx(self) -> None:
        """Сохранить текущий расчёт в DOCX."""
        from ..core import report as report_module

        if not report_module.available():
            self._warn(
                "Для выгрузки в DOCX нужен пакет python-docx.\n"
                "Установите его:  python -m pip install python-docx")
            return

        tab = self.current_tab()
        view = getattr(tab, "result_view", None)
        result = getattr(view, "last_result", None)
        if result is None:
            self._warn("Сначала выполните расчёт на открытой вкладке.")
            return

        path = self._ask_path("Экспорт расчёта в DOCX")
        if not path:
            return

        source = ""
        if hasattr(tab, "latex_source"):
            try:
                source = tab.latex_source()
            except Exception:
                source = ""

        try:
            report_module.export_result(path, result, source=source)
        except Exception as exc:
            self._warn(f"Не удалось сохранить: {exc}")
            return

        self.status_label.setText(f"Расчёт сохранён: {path}")

    def copy_latex(self) -> None:
        """Скопировать LaTeX текущего результата."""
        from PySide6.QtWidgets import QApplication

        tab = self.current_tab()
        view = getattr(tab, "result_view", None)
        text = getattr(view, "_latex_text", "") if view is not None else ""

        if not text:
            self._warn("У этого расчёта нет формулы или уравнения для LaTeX.")
            return

        QApplication.clipboard().setText(text)
        self.status_label.setText(f"LaTeX скопирован: {text[:60]}")

    def _warn(self, message: str) -> None:
        self.status_label.setText(message.split("\n")[0][:120])
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, "Alchemy", message)

    @staticmethod
    def _qt_version() -> str:
        from PySide6 import QtCore

        return QtCore.qVersion()

    def _about(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        modules = len(BASIC_TABS) + len(ADVANCED_TABS) + len(CHAT_TABS)
        QMessageBox.about(
            self, "О программе",
            f"{APP_TITLE}\n"
            f"Значок «{BETA_TEXT}» значит: {APP_LABEL}.\n"
            f"Модули есть, числа сходятся, но часть поведения ещё меняется.\n\n"
            f"Проект stffbn4k.\n"
            f"Диси (DeepSeek AI), инженер-расчётчик.\n\n"
            f"Модулей: {modules}. Расчёты идут локально,\n"
            f"справочники лежат в комплекте.\n"
            f"ИИ-чат — единственное, что ходит в сеть.\n\n"
            f"Если ответ расходится с бумагой, это моя ошибка,\n"
            f"а не твоя. Пиши.\n\n"
            f"Интерфейс: Qt {self._qt_version()}")

    # ---------------- построение ----------------

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(300)

        column = QVBoxLayout(sidebar)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        # Заголовок и значок беты в одну строку. Значок сделан по образцу
        # яндексовых пометок: маленькая скруглённая плашка фирменного
        # красного, строчными буквами, рядом с названием.
        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(16, 18, 16, 0)
        title_layout.setSpacing(8)

        title = QLabel("ALCHEMY")
        title.setObjectName("SidebarTitle")
        title_layout.addWidget(title)

        badge = QLabel(BETA_TEXT)
        badge.setObjectName("BetaBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setToolTip(BETA_TOOLTIP)
        title_layout.addWidget(badge, 0, Qt.AlignVCenter)

        title_layout.addStretch(1)
        column.addWidget(title_row)

        subtitle = QLabel("химический калькулятор")
        subtitle.setObjectName("SidebarSubtitle")
        column.addWidget(subtitle)

        self.search = QLineEdit()
        self.search.setObjectName("SidebarSearch")
        self.search.setPlaceholderText("Поиск по модулям (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_modules)
        column.addWidget(self.search)

        for number in range(1, 10):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{number}"), self)
            shortcut.activated.connect(
                lambda position=number - 1: self._open_by_number(position))

        self.nav = QListWidget()
        self.nav.setObjectName("SidebarList")
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.currentItemChanged.connect(self._on_nav_changed)
        column.addWidget(self.nav, 1)

        # ИИ-чат стоит первым: это вход, а не ещё один модуль
        self._add_group("ИИ-ЧАТ", CHAT_TABS, first=True)
        self._add_group("ОСНОВНЫЕ МОДУЛИ", BASIC_TABS)
        self._add_group("ДОПОЛНИТЕЛЬНЫЕ МОДУЛИ", ADVANCED_TABS)

        footer = QLabel(f"Модулей: "
                        f"{len(BASIC_TABS) + len(ADVANCED_TABS)}, "
                        f"плюс ИИ-чат.\n"
                        f"Расчёты локальные, источники указаны.")
        footer.setObjectName("SidebarSubtitle")
        footer.setWordWrap(True)
        column.addSpacing(6)
        column.addWidget(footer)

        return sidebar

    def _add_group(self, title: str, specs: list[TabSpec],
                   *, first: bool = False) -> None:
        """Добавить раздел меню.

        Разделы должны читаться как разделы, а не как ещё одна строка
        списка: перед каждым, кроме первого, идёт отступ, а заголовок
        набран мельче, с разрядкой и отделён линией.
        """
        if not first:
            line = QListWidgetItem("")
            line.setFlags(Qt.NoItemFlags)
            line.setData(Qt.UserRole, None)
            line.setSizeHint(QSize(0, 1))
            line.setBackground(QColor(theme.COLOR_BORDER))
            self.nav.addItem(line)

            gap = QListWidgetItem("")
            gap.setFlags(Qt.ItemIsEnabled)
            gap.setData(Qt.UserRole, None)
            gap.setSizeHint(QSize(0, 10))
            self.nav.addItem(gap)

        header = QListWidgetItem(title.upper())
        header.setFlags(Qt.ItemIsEnabled)
        header.setData(Qt.UserRole, None)
        header.setForeground(QColor(theme.COLOR_TEXT_FAINT))
        header_font = theme.font(theme.FONT_SMALL - 2, bold=True)
        header_font.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        header.setFont(header_font)
        header.setSizeHint(QSize(0, 28))
        header.setBackground(QColor(theme.COLOR_SIDEBAR))
        self.nav.addItem(header)

        for spec in specs:
            item = QListWidgetItem(spec.title)
            item.setData(Qt.UserRole, spec.cls)
            item.setToolTip(spec.description)
            self.nav.addItem(item)
            self._items[spec.cls] = item

    def _build_statusbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(28)

        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 16, 0)

        self.status_label = QLabel("Готово")
        self.status_label.setObjectName("StatusBar")
        row.addWidget(self.status_label)
        row.addStretch(1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("StatusBar")
        row.addWidget(self.count_label)

        self._update_count()
        return bar

    def _update_count(self) -> None:
        self.count_label.setText(f"расчётов в журнале: {len(self.history)}")

    # ---------------- переключение ----------------

    def _on_nav_changed(self, current: QListWidgetItem, _previous) -> None:
        if current is None:
            return
        cls = current.data(Qt.UserRole)
        if cls is not None:
            self.open_tab(cls)
            self._remember_tab(cls)

    def _open_by_number(self, position: int) -> None:
        """Ctrl+1…9 — первые девять модулей списка."""
        modules = [item for item in self._items.values()]
        ordered: list = []
        for index in range(self.nav.count()):
            item = self.nav.item(index)
            cls = item.data(Qt.UserRole)
            if cls is not None and not item.isHidden():
                ordered.append(cls)
        if 0 <= position < len(ordered):
            self._select_tab(ordered[position])
            self._remember_tab(ordered[position])

    def open_tab(self, cls: type) -> None:
        """Открыть вкладку, создав её при первом обращении."""
        widget = self._tabs.get(cls)
        if widget is None:
            try:
                widget = cls(controller=self)
            except Exception as exc:
                self.status_label.setText(
                    f"Не удалось открыть вкладку {cls.__name__}: "
                    f"{type(exc).__name__}: {exc}")
                return
            self._tabs[cls] = widget
            self.stack.addWidget(widget)

        self.stack.setCurrentWidget(widget)

        item = self._items.get(cls)
        if item is not None and self.nav.currentItem() is not item:
            self.nav.blockSignals(True)
            self.nav.setCurrentItem(item)
            self.nav.blockSignals(False)

        self.status_label.setText(getattr(widget, "title", cls.__name__))

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

        self.status_label.setText(f"{action}: {result.formatted()}"[:120])
        self._update_count()

    def transfer(self, target_cls: type, key: str, value) -> None:
        """Передать данные на другую вкладку."""
        self.open_tab(target_cls)
        widget = self._tabs.get(target_cls)
        receiver = getattr(widget, "receive_data", None)
        if receiver is not None:
            try:
                receiver(key, value)
            except Exception:
                pass


def run(argv: list[str] | None = None) -> int:
    """Запустить приложение. Возвращает код выхода."""
    app = QApplication(argv if argv is not None else sys.argv)
    theme.apply_theme(app)

    window = AlchemyApp()
    window.show()
    return app.exec()
