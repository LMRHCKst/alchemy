"""Главное окно Qt-интерфейса.

Вкладки берутся из пакета alchemy.ui: там же лежат их компоненты и виджеты.
"""

from __future__ import annotations

import datetime
import sys
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.results import Result
from ..ui import theme

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

        edit_menu = bar.addMenu("Правка")
        action = edit_menu.addAction("Копировать LaTeX")
        action.triggered.connect(self.copy_latex)

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

        self.nav = QListWidget()
        self.nav.setObjectName("SidebarList")
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.currentItemChanged.connect(self._on_nav_changed)
        column.addWidget(self.nav, 1)

        # ИИ-чат стоит первым: это вход, а не ещё один модуль
        self._add_group("ИИ-ЧАТ", CHAT_TABS)
        self._add_group("ОСНОВНЫЕ МОДУЛИ", BASIC_TABS)
        self._add_group("ДОПОЛНИТЕЛЬНЫЕ МОДУЛИ", ADVANCED_TABS)

        footer = QLabel(f"Модулей: "
                        f"{len(BASIC_TABS) + len(ADVANCED_TABS)}, "
                        f"плюс ИИ-чат.\n"
                        f"Расчёты локальные, источники указаны.")
        footer.setObjectName("SidebarSubtitle")
        footer.setWordWrap(True)
        column.addWidget(footer)

        return sidebar

    def _add_group(self, title: str, specs: list[TabSpec]) -> None:
        header = QListWidgetItem(title.upper())
        header.setFlags(Qt.NoItemFlags)
        header.setData(Qt.UserRole, None)
        header.setForeground(QColor(theme.COLOR_TEXT_FAINT))
        header.setFont(theme.font(theme.FONT_SMALL - 1, bold=True))
        header.setSizeHint(QSize(0, 30))
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
