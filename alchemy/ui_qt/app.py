"""Главное окно Qt-интерфейса.

Структура та же, что в tkinter-версии: слева меню из двух блоков,
справа — выбранная вкладка, снизу — строка состояния.

Пока переведены не все вкладки: Qt-версия собирается постепенно, и
неперенесённые вкладки в меню не показываются, чтобы не путать.
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
from . import theme
from .tabs_advanced import CanteraTab
from .tabs_basic import MolarMassTab, ThermoTab


APP_TITLE = "Alchemy — химический калькулятор"
APP_VERSION = "3.0"


@dataclass
class TabSpec:
    """Описание вкладки для меню."""

    title: str
    description: str
    cls: type
    group: str


BASIC_TABS: list[TabSpec] = [
    TabSpec("Молярная масса", "Масса и состав вещества", MolarMassTab, "basic"),
    TabSpec("Термохимия", "ΔH, ΔS, ΔG, равновесие", ThermoTab, "basic"),
]

ADVANCED_TABS: list[TabSpec] = [
    TabSpec("Газы: равновесие и горение", "Равновесие и горение на Cantera",
            CanteraTab, "advanced"),
]


class AlchemyApp(QMainWindow):
    """Главное окно на Qt."""

    def __init__(self):
        super().__init__()

        self.history: list[dict] = []
        self._tabs: dict[type, QWidget] = {}
        self._items: dict[type, QListWidgetItem] = {}

        self.setWindowTitle(f"{APP_TITLE} {APP_VERSION}")

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

        self.resize(1400, 920)
        self.setMinimumSize(1100, 700)

        self.open_tab(BASIC_TABS[0].cls)

    # ---------------- построение ----------------

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(280)

        column = QVBoxLayout(sidebar)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        title = QLabel("ALCHEMY")
        title.setObjectName("SidebarTitle")
        column.addWidget(title)

        subtitle = QLabel(f"химический калькулятор {APP_VERSION}")
        subtitle.setObjectName("SidebarSubtitle")
        column.addWidget(subtitle)

        self.nav = QListWidget()
        self.nav.setObjectName("SidebarList")
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.currentItemChanged.connect(self._on_nav_changed)
        column.addWidget(self.nav, 1)

        self._add_group("ОСНОВНЫЕ МОДУЛИ", BASIC_TABS)
        self._add_group("ДОПОЛНИТЕЛЬНЫЕ МОДУЛИ", ADVANCED_TABS)

        footer = QLabel("Все расчёты выполняются локально.\n"
                        "Источники данных указаны в результатах.")
        footer.setObjectName("SidebarSubtitle")
        footer.setWordWrap(True)
        column.addWidget(footer)

        return sidebar

    def _add_group(self, title: str, specs: list[TabSpec]) -> None:
        header = QListWidgetItem(title.upper())
        header.setFlags(Qt.NoItemFlags)
        header.setData(Qt.UserRole, None)
        # Заголовок группы не должен выглядеть как активный пункт меню
        header.setForeground(QColor(theme.COLOR_TEXT_FAINT))
        header_font = theme.font(theme.FONT_SMALL - 1, bold=True)
        header.setFont(header_font)
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

    def _on_nav_changed(self, current: QListWidgetItem,
                        _previous: QListWidgetItem) -> None:
        if current is None:
            return
        cls = current.data(Qt.UserRole)
        if cls is not None:
            self.open_tab(cls)

    def open_tab(self, cls: type) -> None:
        """Открыть вкладку, создав её при первом обращении.

        Имя отличается от show(), потому что show() у окна Qt — это показ
        самого окна на экране.
        """
        widget = self._tabs.get(cls)
        if widget is None:
            try:
                widget = cls(controller=self)
            except Exception as exc:   # вкладка не должна ронять окно
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

        self.status_label.setText(
            f"{action}: {result.formatted()}"[:120])
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
