"""Компоненты Qt-интерфейса: карточки, поля, панель результата, основа вкладки.

Имена и поведение намеренно повторяют tkinter-версию из alchemy/ui/components,
чтобы вкладки переносились с минимальными правками: тот же Card, LabeledEntry,
LabeledCombo, KeyValueGrid, ResultView, BaseTab с методами build_inputs,
build_extra, calculate, run.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from ..core.results import Result
from . import theme
from .theme import (
    COLOR_ERROR, COLOR_OK, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_FAINT,
    COLOR_WARN,
)


def _label(text: str, object_name: str = "", wrap: bool = False,
           size: int | None = None, bold: bool = False,
           color: str | None = None) -> QLabel:
    """Быстро создать подпись с нужным стилем."""
    widget = QLabel(text)
    if object_name:
        widget.setObjectName(object_name)
    if wrap:
        widget.setWordWrap(True)
    if size is not None or bold:
        widget.setFont(theme.font(size or theme.FONT_BODY, bold=bold))
    if color is not None:
        widget.setStyleSheet(f"color: {color};")
    return widget


# --------------------------------------------------------------------------
# Карточка
# --------------------------------------------------------------------------


class Card(QFrame):
    """Карточка с заголовком, пояснением и местом под содержимое."""

    def __init__(self, parent: QWidget | None = None, title: str = "",
                 desc: str = ""):
        super().__init__(parent)
        self.setObjectName("Card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(4)

        if title:
            outer.addWidget(_label(title, "CardTitle"))
        if desc:
            description = _label(desc, "CardDesc", wrap=True)
            outer.addWidget(description)

        #: сюда наследник складывает содержимое
        self.body = QWidget()
        self.body.setObjectName("CardBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 6 if title or desc else 0, 0, 0)
        self.body_layout.setSpacing(6)
        outer.addWidget(self.body)


class CollapsibleCard(Card):
    """Карточка, содержимое которой скрыто до нажатия."""

    def __init__(self, parent: QWidget | None = None, title: str = "Подробнее",
                 desc: str = "", expanded: bool = False):
        super().__init__(parent, title=title, desc=desc)
        self._expanded = expanded
        self.body.setVisible(expanded)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self.body.setVisible(self._expanded)


# --------------------------------------------------------------------------
# Поля ввода
# --------------------------------------------------------------------------


class LabeledEntry(QWidget):
    """Подпись, поле ввода и необязательная подсказка справа."""

    LABEL_WIDTH = 250

    def __init__(self, parent: QWidget | None = None, label: str = "",
                 width: int = 180, hint: str = "", default: str = ""):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.label = _label(label, "FieldLabel")
        self.label.setFixedWidth(self.LABEL_WIDTH)
        row.addWidget(self.label)

        self.entry = QLineEdit()
        self.entry.setFixedWidth(width)
        if default:
            self.entry.setText(default)
        row.addWidget(self.entry)

        if hint:
            self.hint = _label(hint, "FieldHint")
            row.addWidget(self.hint)
        else:
            self.hint = None

        row.addStretch(1)

    # ---------------- совместимость с tkinter-версией ----------------

    def get(self) -> str:
        return self.entry.text()

    def set(self, text: str) -> None:
        self.entry.setText(str(text))

    def clear(self) -> None:
        self.entry.clear()

    def set_enabled(self, enabled: bool) -> None:
        self.entry.setEnabled(enabled)


class LabeledCombo(QWidget):
    """Выпадающий список с подписью.

    Ширина подписи общая с LabeledEntry, поэтому поля и списки встают
    на одну вертикаль.
    """

    #: испускается при смене выбора — по нему вкладка перестраивает форму
    changed = Signal()

    LABEL_WIDTH = LabeledEntry.LABEL_WIDTH

    def __init__(self, parent: QWidget | None = None, label: str = "",
                 values: list[str] | None = None, default: str | None = None,
                 width: int = 220, label_width: int | None = None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        if label:
            self.label = _label(label, "FieldLabel")
            self.label.setFixedWidth(self.LABEL_WIDTH if label_width is None
                                     else label_width)
            row.addWidget(self.label)

        self.combo = QComboBox()
        self.combo.setFixedWidth(width)
        self.combo.addItems(values or [])
        if default:
            self.combo.setCurrentText(default)
        row.addWidget(self.combo)
        row.addStretch(1)

        self.combo.currentTextChanged.connect(lambda _: self.changed.emit())

    def get(self) -> str:
        return self.combo.currentText()

    def set(self, value: str) -> None:
        self.combo.setCurrentText(str(value))

    def set_items(self, values: list[str], keep: bool = True) -> None:
        current = self.get() if keep else None
        self.combo.clear()
        self.combo.addItems(values)
        if current:
            self.set(current)


class KeyValueGrid(QWidget):
    """Сетка «подпись — поле» в две колонки."""

    def __init__(self, parent: QWidget | None = None,
                 rows: list[tuple[str, str, str]] | None = None,
                 columns: int = 1):
        super().__init__(parent)
        from PySide6.QtWidgets import QGridLayout

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(5)
        self.fields: dict[str, QLineEdit] = {}
        self._columns = max(1, columns)

        for key, label, default in (rows or []):
            self.add_row(key, label, default)

    def add_row(self, key: str, label: str, default: str = "") -> QLineEdit:
        index = len(self.fields)
        row = index // self._columns
        col = index % self._columns
        caption = _label(label)
        edit = QLineEdit()
        edit.setFixedWidth(120)
        if default:
            edit.setText(default)
        self._grid.addWidget(caption, row, col * 2, Qt.AlignRight)
        self._grid.addWidget(edit, row, col * 2 + 1)
        self.fields[key] = edit
        return edit

    def get(self, key: str) -> str:
        return self.fields[key].text()

    def clear(self) -> None:
        for edit in self.fields.values():
            edit.clear()


class EditableTable(QWidget):
    """Таблица «вещество — значение» с добавлением и удалением строк."""

    def __init__(self, parent: QWidget | None = None,
                 columns: list[str] | None = None,
                 add_label: str = "Добавить строку"):
        super().__init__(parent)
        from PySide6.QtWidgets import QGridLayout

        self.columns = columns or ["Вещество", "Значение"]
        self._rows: list[list[QLineEdit]] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._grid = QGridLayout()
        self._grid.setSpacing(4)
        outer.addLayout(self._grid)

        for index, name in enumerate(self.columns):
            self._grid.addWidget(_label(name, "FieldHint"), 0, index)

        self._add_button = QPushButton(add_label)
        self._add_button.setFixedWidth(180)
        self._add_button.clicked.connect(lambda: self.add_row())
        outer.addWidget(self._add_button)

        self.add_row()

    def add_row(self) -> None:
        row_index = len(self._rows) + 1
        widgets: list[QLineEdit] = []
        for col in range(len(self.columns)):
            edit = QLineEdit()
            edit.setFixedWidth(140 if col == 0 else 110)
            self._grid.addWidget(edit, row_index, col)
            widgets.append(edit)

        remove = QPushButton("✕")
        remove.setFixedWidth(28)
        remove.clicked.connect(lambda: self._remove(widgets))
        self._grid.addWidget(remove, row_index, len(self.columns))
        self._rows.append(widgets)

    def _remove(self, widgets: list[QLineEdit]) -> None:
        if len(self._rows) <= 1:
            for edit in widgets:
                edit.clear()
            return
        self._rows.remove(widgets)
        for edit in widgets:
            edit.deleteLater()
        self._rebuild()

    def _rebuild(self) -> None:
        while self._grid.count() > len(self.columns):
            item = self._grid.takeAt(len(self.columns))
            widget = item.widget()
            if widget is not None and widget not in [
                    w for row in self._rows for w in row]:
                widget.deleteLater()
        # Переставляем оставшиеся строки подряд
        for index, widgets in enumerate(self._rows, start=1):
            for col, edit in enumerate(widgets):
                self._grid.addWidget(edit, index, col)

    def rows(self) -> list[list[str]]:
        return [[edit.text() for edit in widgets] for widgets in self._rows]

    def clear(self) -> None:
        for widgets in self._rows:
            for edit in widgets:
                edit.clear()


# --------------------------------------------------------------------------
# Панель результата
# --------------------------------------------------------------------------


class ResultView(QFrame):
    """Показ результата: значение, модель, предупреждения, таблица, ход расчёта."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ResultPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(6)

        self.label = _label("Результат появится здесь", "ResultLabel", wrap=True)
        outer.addWidget(self.label)

        self.value_label = _label("—", "ResultValue", wrap=True)
        outer.addWidget(self.value_label)

        self.method_label = _label("", "ResultMethod", wrap=True)
        outer.addWidget(self.method_label)

        # предупреждения
        self.warn_box = QWidget()
        self.warn_layout = QVBoxLayout(self.warn_box)
        self.warn_layout.setContentsMargins(0, 0, 0, 0)
        self.warn_layout.setSpacing(2)
        self.warn_box.setVisible(False)
        outer.addWidget(self.warn_box)

        # таблица
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setWordWrap(True)
        self.table.setVisible(False)
        outer.addWidget(self.table)

        # кнопка «ход расчёта»
        self.details_button = QPushButton("▶  Показать ход расчёта и допущения")
        self.details_button.setObjectName("Link")
        self.details_button.setVisible(False)
        self.details_button.clicked.connect(self._toggle_details)
        outer.addWidget(self.details_button)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setFont(theme.font(theme.FONT_SMALL, mono=True))
        self.details.setMinimumHeight(180)
        self.details.setVisible(False)
        outer.addWidget(self.details)

        outer.addStretch(1)

        self._details_open = False

    # ---------------- показ ----------------

    def clear(self) -> None:
        self.label.setText("Результат появится здесь")
        self.value_label.setText("—")
        self.value_label.setStyleSheet(f"color: {COLOR_TEXT_DIM};")
        self.method_label.setText("")
        self._clear_warnings()
        self.table.setVisible(False)
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.details.clear()
        self.details.setVisible(False)
        self.details_button.setVisible(False)
        self._details_open = False
        self.details_button.setText("▶  Показать ход расчёта и допущения")

    def show(self, result: Result) -> None:
        """Показать результат расчёта."""
        self.label.setText(result.label or "Результат")

        tabular = (result.kind in ("table", "series")
                   and isinstance(result.value, list))
        if tabular:
            self.value_label.setVisible(False)
        else:
            self.value_label.setVisible(True)
            if result.value is None:
                self.value_label.setText("расчёт не выполнен")
                self.value_label.setStyleSheet(f"color: {COLOR_ERROR};")
            else:
                self.value_label.setText(result.formatted())
                color = COLOR_ERROR if result.has_warnings else theme.COLOR_ACCENT
                self.value_label.setStyleSheet(f"color: {color};")

        self.method_label.setText(result.method or "")

        self._fill_warnings(result.warnings)

        if tabular:
            self._fill_table(result)
        else:
            self.table.setVisible(False)

        self.details.setPlainText(result.summary())
        has_details = bool(result.summary().strip())
        self.details_button.setVisible(has_details)
        self.details.setVisible(has_details and self._details_open)

        if result.has_warnings and has_details:
            self._show_details()

    def show_error(self, message: str) -> None:
        """Показать сообщение об ошибке."""
        self.label.setText("Ошибка расчёта")
        self.value_label.setVisible(True)
        self.value_label.setText("—")
        self.value_label.setStyleSheet(f"color: {COLOR_ERROR};")
        self.method_label.setText("")
        self._fill_warnings([message], is_error=True)
        self.table.setVisible(False)
        self.details.clear()
        self.details.setVisible(False)
        self.details_button.setVisible(False)

    # ---------------- внутреннее ----------------

    def _clear_warnings(self) -> None:
        while self.warn_layout.count():
            item = self.warn_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.warn_box.setVisible(False)

    def _fill_warnings(self, messages: list[str],
                       is_error: bool = False) -> None:
        self._clear_warnings()
        for message in messages:
            mark = "✕" if is_error else "⚠"
            row = _label(f"{mark}  {message}",
                         "ResultError" if is_error else "ResultWarning",
                         wrap=True,
                         color=COLOR_ERROR if is_error else COLOR_WARN)
            self.warn_layout.addWidget(row)
        self.warn_box.setVisible(bool(messages))

    def _fill_table(self, result: Result) -> None:
        rows = result.value
        if not rows:
            self.table.setVisible(False)
            return

        columns = result.meta.get("columns") or list(rows[0].keys())
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels([str(c) for c in columns])

        for r, row in enumerate(rows):
            for c, name in enumerate(columns):
                value = row.get(name, "")
                if isinstance(value, float):
                    text = f"{value:.4f}"
                else:
                    text = str(value)
                item = QTableWidgetItem(text)
                self.table.setItem(r, c, item)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # Ограничиваем высоту, чтобы длинная таблица не растягивала вкладку
        visible_rows = min(len(rows), 12)
        row_height = self.table.verticalHeader().defaultSectionSize()
        self.table.setMinimumHeight(visible_rows * row_height + 34)
        self.table.setVisible(True)

    def _toggle_details(self) -> None:
        self._details_open = not self._details_open
        self.details.setVisible(self._details_open)
        self.details_button.setText(
            "▼  Скрыть ход расчёта" if self._details_open
            else "▶  Показать ход расчёта и допущения")

    def _show_details(self) -> None:
        self._details_open = True
        self.details.setVisible(True)
        self.details_button.setText("▼  Скрыть ход расчёта")


# --------------------------------------------------------------------------
# Основа расчётной вкладки
# --------------------------------------------------------------------------


class BaseTab(QWidget):
    """Расчётная вкладка: заголовок, поля, кнопки, панель результата.

    Наследник описывает поля в build_inputs и реализует calculate.
    """

    title = "Вкладка"
    description = ""
    action_label = "Рассчитать"
    history_action = ""

    def __init__(self, parent: QWidget | None = None, controller=None):
        super().__init__(parent)
        self.controller = controller
        self.fields: dict[str, QWidget] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll)

        content = QWidget()
        content.setObjectName("Page")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(20, 16, 20, 16)
        self.content_layout.setSpacing(10)
        self.scroll.setWidget(content)

        # заголовок
        self.content_layout.addWidget(_label(self.title, "PageTitle"))
        if self.description:
            description = _label(self.description, "PageDesc", wrap=True)
            self.content_layout.addWidget(description)

        # поля ввода
        self.inputs_card = Card(title="Исходные данные")
        self.content_layout.addWidget(self.inputs_card)
        self.build_inputs(self.inputs_card.body)

        # кнопки
        buttons = QWidget()
        button_row = QHBoxLayout(buttons)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self.action_button = QPushButton(self.action_label)
        self.action_button.setObjectName("Primary")
        self.action_button.setFixedWidth(180)
        self.action_button.setMinimumHeight(34)
        self.action_button.clicked.connect(self.run)
        button_row.addWidget(self.action_button)

        self.clear_button = QPushButton("Очистить")
        self.clear_button.setFixedWidth(110)
        self.clear_button.setMinimumHeight(34)
        self.clear_button.clicked.connect(self.reset)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)
        self.content_layout.addWidget(buttons)

        # дополнительные блоки
        self.extra_area = QWidget()
        self.extra_layout = QVBoxLayout(self.extra_area)
        self.extra_layout.setContentsMargins(0, 0, 0, 0)
        self.extra_layout.setSpacing(10)
        self.build_extra(self.extra_area)
        if self.extra_layout.count():
            self.content_layout.addWidget(self.extra_area)

        # Панель занимает столько, сколько в ней содержимого: растянутая
        # рамка на весь экран читается как пустой ящик
        self.result_view = ResultView()
        self.content_layout.addWidget(self.result_view)
        self.content_layout.addStretch(1)

        self._bind_enter()
        self.on_ready()

    # ---------------- для наследников ----------------

    def on_ready(self) -> None:
        """Вызывается после сборки вкладки."""

    def build_inputs(self, parent: QWidget) -> None:
        """Создать поля ввода."""

    def build_extra(self, parent: QWidget) -> None:
        """Создать дополнительные блоки."""

    def calculate(self) -> Result:
        raise NotImplementedError

    def reset(self) -> None:
        """Очистить поля и результат."""
        self._clear_fields(self.inputs_card.body)
        self.result_view.clear()

    # ---------------- общее ----------------

    def _clear_fields(self, widget: QWidget) -> None:
        if isinstance(widget, QLineEdit):
            widget.clear()
        elif isinstance(widget, LabeledEntry):
            widget.clear()
        elif isinstance(widget, KeyValueGrid):
            widget.clear()
        elif isinstance(widget, EditableTable):
            widget.clear()
        for child in widget.findChildren(QWidget):
            if isinstance(child, QLineEdit):
                child.clear()

    def run(self) -> None:
        """Выполнить расчёт и показать результат."""
        from ..core.errors import AlchemyError

        try:
            result = self.calculate()
        except AlchemyError as exc:
            self.result_view.show_error(str(exc))
            return
        except ZeroDivisionError:
            self.result_view.show_error(
                "Деление на ноль: проверьте исходные данные")
            return
        except Exception as exc:
            self.result_view.show_error(
                f"Непредвиденная ошибка ({type(exc).__name__}): {exc}")
            return

        self.result_view.show(result)
        self._log(result)

    def _log(self, result: Result) -> None:
        if self.controller is None:
            return
        logger = getattr(self.controller, "log_operation", None)
        if logger is None:
            return
        try:
            logger(self.history_action or self.title, result)
        except Exception:
            pass

    def _bind_enter(self) -> None:
        """Enter в любом поле запускает расчёт."""
        for edit in self.findChildren(QLineEdit):
            edit.returnPressed.connect(self.run)

    # ---------------- вспомогательные конструкторы ----------------

    def info_block(self, parent, text: str, title: str = "") -> None:
        """Блок пояснений под полями: свёрнут, пока не нажали."""
        heading = title or "Как это считается"
        card = CollapsibleCard(title=heading)

        toggle = QPushButton("▶  " + heading)
        toggle.setObjectName("Link")
        card.body_layout.addWidget(toggle)

        body = _label(text, "CardDesc", wrap=True)
        card.body_layout.addWidget(body)
        card.body.setVisible(False)

        def switch() -> None:
            visible = not card.body.isVisible()
            card.body.setVisible(visible)
            toggle.setText(("▼  " if visible else "▶  ") + heading)

        toggle.clicked.connect(switch)

        layout = parent.layout()
        if layout is None:
            layout = QVBoxLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)

    def row(self, parent, *widgets) -> QWidget:
        """Разместить виджеты в одну строку."""
        frame = QWidget()
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        for widget in widgets:
            row.addWidget(widget)
        row.addStretch(1)
        return frame
