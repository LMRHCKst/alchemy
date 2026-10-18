"""Компоненты вкладок: карточки, поля, таблицы, панель результата.

Набор и методы те же, что ждут вкладки: pack(), .entry.insert(),
.combo.configure(), get_rows() и прочие. Внутри — Qt.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from ..core.errors import AlchemyError, InputError
from ..core.results import Result
from ..core.units import UnitError, parse_quantity
from . import theme
from .widgets import CTkEntry, CTkFrame, CTkLabel, CTkComboBox, _font, _color, pack

# Константы, которые вкладки импортируют напрямую
COLOR_TEXT_DIM = theme.COLOR_TEXT_DIM
COLOR_TEXT = theme.COLOR_TEXT
COLOR_ACCENT = theme.COLOR_ACCENT
COLOR_WARN = theme.COLOR_WARN
COLOR_ERROR = theme.COLOR_ERROR
FONT_SMALL = theme.FONT_SMALL
FONT_BODY = theme.FONT_BODY


def _field_text(field) -> str:
    """Текст из поля ввода любого вида."""
    if field is None:
        return ""
    getter = getattr(field, "get", None)
    if getter is None:
        return ""
    try:
        return str(getter()).strip()
    except Exception:
        return ""


def _pack_widget(widget, **kwargs) -> None:
    pack(widget, **kwargs)


# --------------------------------------------------------------------------
# Карточка
# --------------------------------------------------------------------------


class Card(QFrame):
    """Карточка с заголовком и пояснением. Содержимое кладут в .body."""

    def __init__(self, master=None, title: str = "", desc: str = "", **kwargs):
        super().__init__(master)
        self.setObjectName("Card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(4)

        if title:
            heading = QLabel(title)
            heading.setObjectName("CardTitle")
            outer.addWidget(heading)
        if desc:
            description = QLabel(desc)
            description.setObjectName("CardDesc")
            description.setWordWrap(True)
            outer.addWidget(description)

        self.body = CTkFrame(self, fg_color=None)
        self.body.setObjectName("CardBody")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 6 if title or desc else 0, 0, 0)
        body_layout.setSpacing(6)
        outer.addWidget(self.body)

    def pack(self, **kwargs) -> None:
        _pack_widget(self, **kwargs)


class CollapsibleCard(Card):
    """Карточка, содержимое которой скрыто до нажатия."""

    def __init__(self, master=None, title: str = "Подробнее", desc: str = "",
                 expanded: bool = False, **kwargs):
        super().__init__(master, title=title, desc=desc)
        self._expanded = expanded
        self.body.setVisible(expanded)


# --------------------------------------------------------------------------
# Поля ввода
# --------------------------------------------------------------------------


class LabeledEntry(QWidget):
    """Подпись, поле ввода и необязательная подсказка."""

    #: ширина колонки подписи. Совпадает с той, что используют вкладки
    #: в своих помощниках полей, иначе списки и поля встают на разные
    #: вертикали и колонка выглядит рваной.
    LABEL_WIDTH = 340

    def __init__(self, master=None, label: str = "", width: int = 180,
                 hint: str = "", default: str = "", **kwargs):
        super().__init__(master)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        self.label.setFixedWidth(self.LABEL_WIDTH)
        row.addWidget(self.label)

        self.entry = CTkEntry(self, width=width, font=("Consolas", 12))
        if default:
            self.entry.setText(default)
        row.addWidget(self.entry)

        if hint:
            self.hint = QLabel(hint)
            self.hint.setObjectName("FieldHint")
            row.addWidget(self.hint)
        else:
            self.hint = None

        row.addStretch(1)

    def pack(self, **kwargs) -> None:
        _pack_widget(self, **kwargs)

    def get(self) -> str:
        return self.entry.text()

    def set(self, text: str) -> None:
        self.entry.setText(str(text))

    def clear(self) -> None:
        self.entry.clear()

    def winfo_children(self) -> list:
        return self.findChildren(QWidget, options=Qt.FindDirectChildrenOnly)


class LabeledCombo(QWidget):
    """Выпадающий список с подписью."""

    changed = Signal()

    LABEL_WIDTH = LabeledEntry.LABEL_WIDTH

    def __init__(self, master=None, label: str = "", values=None,
                 default: str | None = None, width: int = 220,
                 label_width: int | None = None, **kwargs):
        super().__init__(master)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        if label:
            self.label = QLabel(label)
            self.label.setObjectName("FieldLabel")
            self.label.setFixedWidth(self.LABEL_WIDTH if label_width is None
                                     else label_width)
            row.addWidget(self.label)

        self.combo = CTkComboBox(self, values=values, width=width)
        if default:
            self.combo.setCurrentText(default)
        row.addWidget(self.combo)
        row.addStretch(1)

        self.combo.currentTextChanged.connect(lambda _: self.changed.emit())

    def pack(self, **kwargs) -> None:
        _pack_widget(self, **kwargs)

    def get(self) -> str:
        return self.combo.currentText()

    def set(self, value: str) -> None:
        self.combo.setCurrentText(str(value))

    def winfo_children(self) -> list:
        return self.findChildren(QWidget, options=Qt.FindDirectChildrenOnly)


class KeyValueGrid(QWidget):
    """Таблица «поле — значение» для компактного ввода многих величин."""

    def __init__(self, master=None, fields=None, columns: int = 2, **kwargs):
        super().__init__(master)
        from PySide6.QtWidgets import QGridLayout

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(4)
        self.entries: dict[str, CTkEntry] = {}
        self._row = 0
        self._col = 0
        self._columns = max(1, columns)

        for key, label, default in (fields or []):
            self.add_field(key, label, default)

    def add_field(self, key: str, label: str, default: str = "",
                  width: int = 120) -> CTkEntry:
        caption = QLabel(label)
        caption.setObjectName("FieldLabel")
        entry = CTkEntry(self, width=width, font=("Consolas", 12))
        if default:
            entry.setText(str(default))
        self._grid.addWidget(caption, self._row, self._col * 2)
        self._grid.addWidget(entry, self._row, self._col * 2 + 1)
        self.entries[key] = entry

        self._col += 1
        if self._col >= self._columns:
            self._col = 0
            self._row += 1
        return entry

    def pack(self, **kwargs) -> None:
        _pack_widget(self, **kwargs)

    def get(self, key: str) -> str:
        return self.entries[key].text().strip()

    def value(self, key: str, required: bool = True,
              label: str = "") -> float | None:
        raw = self.get(key)
        if not raw:
            if required:
                raise InputError(f"Не заполнено поле «{label or key}»")
            return None
        try:
            number, _unit = parse_quantity(raw)
        except UnitError:
            raise InputError(
                f"Не удалось прочитать число в поле «{label or key}»: «{raw}»")
        return number

    def set(self, key: str, value) -> None:
        self.entries[key].clear()
        if value is not None:
            self.entries[key].setText(str(value))

    def clear(self) -> None:
        for entry in self.entries.values():
            entry.clear()


class EditableTable(QWidget):
    """Таблица «вещество — значение» с добавлением и удалением строк."""

    def __init__(self, master=None, columns=None, add_label: str = "Добавить",
                 **kwargs):
        super().__init__(master)
        self.columns = list(columns or ["Вещество", "Значение"])
        self._rows: list[list[CTkEntry]] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self.header = CTkFrame(self, fg_color=None)
        outer.addWidget(self.header)

        self.rows_area = CTkFrame(self, fg_color=None)
        outer.addWidget(self.rows_area)

        self._add_button = QPushButton(add_label)
        self._add_button.setFixedWidth(190)
        self._add_button.clicked.connect(lambda: self.add_row())
        outer.addWidget(self._add_button)

        self._rebuild_header()
        self.add_row()

    def _rebuild_header(self) -> None:
        for child in self.header.winfo_children():
            child.destroy()
        row_layout = self.header.layout()
        if row_layout is None:
            row_layout = QHBoxLayout(self.header)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
        for name in self.columns:
            caption = CTkLabel(self.header, text=name, font=("Segoe UI", 9),
                               text_color=theme.COLOR_TEXT_DIM, width=150,
                               anchor="w")
            row_layout.addWidget(caption)

    def add_row(self, values=None) -> None:
        """Добавить строку. Значения можно задать сразу списком."""
        entries: list[CTkEntry] = []
        row = QWidget(self.rows_area)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for index in range(len(self.columns)):
            entry = CTkEntry(row, width=150 if index == 0 else 110,
                             font=("Consolas", 12))
            if values and index < len(values) and values[index]:
                entry.setText(str(values[index]))
            layout.addWidget(entry)
            entries.append(entry)

        remove = QPushButton("✕")
        remove.setFixedWidth(28)
        remove.clicked.connect(lambda: self._remove(entries))
        layout.addWidget(remove)
        layout.addStretch(1)

        area_layout = self.rows_area.layout()
        if area_layout is None:
            area_layout = QVBoxLayout(self.rows_area)
            area_layout.setContentsMargins(0, 0, 0, 0)
            area_layout.setSpacing(2)
        area_layout.addWidget(row)

        entries[0]._row_widget = row
        self._rows.append(entries)

    def _remove(self, entries: list[CTkEntry]) -> None:
        if len(self._rows) <= 1:
            for entry in entries:
                entry.clear()
            return
        self._rows.remove(entries)
        row = getattr(entries[0], "_row_widget", None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()

    def reset(self) -> None:
        """Убрать все строки и оставить одну пустую."""
        for entries in self._rows:
            row = getattr(entries[0], "_row_widget", None)
            if row is not None:
                row.setParent(None)
                row.deleteLater()
        self._rows.clear()
        self._rebuild_header()
        self.add_row()

    def get_rows(self) -> list[list[str]]:
        """Непустые строки таблицы."""
        result = []
        for entries in self._rows:
            values = [entry.text() for entry in entries]
            if any(value.strip() for value in values):
                result.append(values)
        return result

    def clear(self) -> None:
        for entries in self._rows:
            for entry in entries:
                entry.clear()

    def pack(self, **kwargs) -> None:
        _pack_widget(self, **kwargs)


# --------------------------------------------------------------------------
# Чтение чисел
# --------------------------------------------------------------------------


def _read_number(raw: str, name: str = "", unit: str | None = None) -> float:
    """Число из строки с понятным сообщением об ошибке."""
    text = str(raw).strip().replace(",", ".")
    if not text:
        raise InputError(f"Не заполнено поле: {name}")

    if unit:
        try:
            quantity = parse_quantity(f"{text} {unit}")
            return quantity.value
        except UnitError:
            raise InputError(f"Не удалось прочитать число: «{raw}»")

    try:
        return float(text)
    except ValueError:
        try:
            quantity = parse_quantity(text)
            return quantity.value
        except UnitError:
            raise InputError(f"Не удалось прочитать число: «{raw}»")


# --------------------------------------------------------------------------
# Панель результата
# --------------------------------------------------------------------------


class ResultView(QFrame):
    """Показ результата: значение, модель, предупреждения, таблица, расчёт."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master)
        self.setObjectName("ResultPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(6)

        self.label = QLabel("Результат появится здесь")
        self.label.setObjectName("ResultLabel")
        self.label.setWordWrap(True)
        outer.addWidget(self.label)

        self.value_label = QLabel("—")
        self.value_label.setObjectName("ResultValue")
        self.value_label.setWordWrap(True)
        outer.addWidget(self.value_label)

        self.method_label = QLabel("")
        self.method_label.setObjectName("ResultMethod")
        self.method_label.setWordWrap(True)
        outer.addWidget(self.method_label)

        self.warn_box = QWidget()
        self.warn_layout = QVBoxLayout(self.warn_box)
        self.warn_layout.setContentsMargins(0, 0, 0, 0)
        self.warn_layout.setSpacing(2)
        self.warn_box.setVisible(False)
        outer.addWidget(self.warn_box)

        from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setVisible(False)
        outer.addWidget(self.table)

        self.details_button = QPushButton("▶  Показать ход расчёта и допущения")
        self.details_button.setObjectName("Link")
        self.details_button.setVisible(False)
        self.details_button.clicked.connect(self._toggle_details)
        outer.addWidget(self.details_button)

        # LaTeX появляется только там, где есть формула или уравнение
        self.latex_button = QPushButton("Копировать LaTeX")
        self.latex_button.setObjectName("Link")
        self.latex_button.setVisible(False)
        self.latex_button.clicked.connect(self._copy_latex)
        outer.addWidget(self.latex_button)

        self._latex_text = ""
        self.last_result: Result | None = None

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setFont(_font(("Consolas", 9)))
        self.details.setMinimumHeight(160)
        self.details.setVisible(False)
        outer.addWidget(self.details)

        self._details_open = False

    def pack(self, **kwargs) -> None:
        _pack_widget(self, **kwargs)

    # ---------------- показ ----------------

    def clear(self) -> None:
        self.label.setText("Результат появится здесь")
        self.value_label.setText("—")
        self.value_label.setStyleSheet(f"color: {theme.COLOR_TEXT_DIM};")
        self.method_label.setText("")
        self._clear_warnings()
        self.table.setVisible(False)
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.details.clear()
        self.details.setVisible(False)
        self.details_button.setVisible(False)
        self.set_latex("")
        self.latex_button.setText("Копировать LaTeX")
        self.last_result = None
        self._details_open = False

    def show(self, result: Result) -> None:
        self.last_result = result
        self.latex_button.setText("Копировать LaTeX")
        self.label.setText(result.label or "Результат")

        # Словарь — это несколько величин сразу (например пересчёт
        # концентраций). Показывать его строкой нечитаемо, поэтому таблицей.
        mapping = isinstance(result.value, dict)
        tabular = mapping or (result.kind in ("table", "series")
                              and isinstance(result.value, list))
        if tabular:
            self.value_label.setVisible(False)
        else:
            self.value_label.setVisible(True)
            if result.value is None:
                self.value_label.setText("расчёт не выполнен")
                self.value_label.setStyleSheet(f"color: {theme.COLOR_ERROR};")
            else:
                self.value_label.setText(result.formatted())
                color = (theme.COLOR_ERROR if result.has_warnings
                         else theme.COLOR_ACCENT)
                self.value_label.setStyleSheet(f"color: {color};")

        self.method_label.setText(result.method or "")
        self._fill_warnings(result.warnings)
        if mapping:
            self._fill_rows(
                [{"Величина": key, "Значение": value}
                 for key, value in result.value.items()],
                ["Величина", "Значение"])
        elif tabular:
            self._fill_table(result)
        else:
            self.table.setVisible(False)

        summary = result.summary()
        has_details = bool(summary.strip())
        self.details.setPlainText(summary)
        self.details_button.setVisible(has_details)
        self.details.setVisible(has_details and self._details_open)

    def show_error(self, message: str) -> None:
        self.label.setText("Ошибка расчёта")
        self.value_label.setVisible(True)
        self.value_label.setText("—")
        self.value_label.setStyleSheet(f"color: {theme.COLOR_ERROR};")
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
                widget.setParent(None)
                widget.deleteLater()
        self.warn_box.setVisible(False)

    def _fill_warnings(self, messages, is_error: bool = False) -> None:
        self._clear_warnings()
        for message in messages:
            mark = "✕" if is_error else "⚠"
            row = QLabel(f"{mark}  {message}")
            row.setWordWrap(True)
            row.setStyleSheet(
                f"color: {theme.COLOR_ERROR if is_error else theme.COLOR_WARN};")
            self.warn_layout.addWidget(row)
        self.warn_box.setVisible(bool(messages))

    def _fill_table(self, result: Result) -> None:
        rows = result.value
        if not rows:
            self.table.setVisible(False)
            return

        # Серии приходят точками (x, y), таблицы — словарями
        if isinstance(rows[0], dict):
            columns = result.meta.get("columns") or list(rows[0].keys())
            values = [[row.get(name, "") for name in columns] for row in rows]
        else:
            columns = [result.meta.get("x_label", "X"),
                       result.meta.get("y_label", "Y")]
            values = [list(row) for row in rows]

        self._fill_rows(values, columns)

    def _fill_rows(self, rows, columns) -> None:
        """Заполнить таблицу готовыми строками и колонками."""
        from PySide6.QtWidgets import QHeaderView, QTableWidgetItem

        if not rows:
            self.table.setVisible(False)
            return

        dicts = isinstance(rows[0], dict)
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels([str(c) for c in columns])

        for r, row in enumerate(rows):
            values = ([row.get(name, "") for name in columns] if dicts
                      else list(row))
            for c, value in enumerate(values):
                if isinstance(value, float):
                    text = f"{value:.6g}"
                else:
                    text = str(value)
                self.table.setItem(r, c, QTableWidgetItem(text))

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        visible_rows = min(len(rows), 12)
        row_height = self.table.verticalHeader().defaultSectionSize()
        self.table.setMinimumHeight(visible_rows * row_height + 34)
        self.table.setVisible(True)

    def set_latex(self, text: str) -> None:
        """Задать LaTeX-запись результата и показать кнопку копирования."""
        self._latex_text = str(text or "").strip()
        self.latex_button.setVisible(bool(self._latex_text))
        if self._latex_text:
            self.latex_button.setToolTip(self._latex_text[:300])

    def _copy_latex(self) -> None:
        from PySide6.QtWidgets import QApplication

        if not self._latex_text:
            return
        QApplication.clipboard().setText(self._latex_text)
        self.latex_button.setText("LaTeX скопирован ✓")

    def _toggle_details(self) -> None:
        self._details_open = not self._details_open
        self.details.setVisible(self._details_open)
        self.details_button.setText(
            "▼  Скрыть ход расчёта" if self._details_open
            else "▶  Показать ход расчёта и допущения")


# --------------------------------------------------------------------------
# Основа расчётной вкладки
# --------------------------------------------------------------------------


class BaseTab(QWidget):
    """Расчётная вкладка. Наследник описывает поля и считает результат."""

    title = "Вкладка"
    description = ""
    action_label = "Рассчитать"
    history_action = ""

    def __init__(self, master=None, controller=None, **kwargs):
        super().__init__(master)
        self.controller = controller
        self.fields: dict = {}

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

        heading = QLabel(self.title)
        heading.setObjectName("PageTitle")
        self.content_layout.addWidget(heading)

        if self.description:
            description = QLabel(self.description)
            description.setObjectName("PageDesc")
            description.setWordWrap(True)
            self.content_layout.addWidget(description)

        self.inputs_card = Card(title="Исходные данные")
        self.content_layout.addWidget(self.inputs_card)
        self.build_inputs(self.inputs_card.body)

        buttons = QWidget()
        button_row = QHBoxLayout(buttons)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self.action_button = QPushButton(self.action_label)
        self.action_button.setObjectName("Primary")
        self.action_button.setFixedWidth(190)
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

        self.extra_area = QWidget()
        extra_layout = QVBoxLayout(self.extra_area)
        extra_layout.setContentsMargins(0, 0, 0, 0)
        extra_layout.setSpacing(10)
        self.build_extra(self.extra_area)
        if extra_layout.count():
            self.content_layout.addWidget(self.extra_area)

        self.result_view = ResultView()
        self.content_layout.addWidget(self.result_view)
        self.content_layout.addStretch(1)

        self.bind_enter()
        self.on_ready()

    # ---------------- для наследников ----------------

    def on_ready(self) -> None:
        """Вызывается после сборки вкладки."""

    def build_inputs(self, parent) -> None:
        """Создать поля ввода."""

    def build_extra(self, parent) -> None:
        """Создать дополнительные блоки."""

    def calculate(self) -> Result:
        raise NotImplementedError

    def reset(self) -> None:
        self.clear_widgets(self.inputs_card.body)
        self.result_view.clear()

    # ---------------- общее ----------------

    def clear_widgets(self, parent) -> None:
        """Очистить все поля ввода внутри контейнера."""
        if isinstance(parent, QLineEdit):
            parent.clear()
            return
        if hasattr(parent, "clear") and isinstance(
                parent, (LabeledEntry, KeyValueGrid, EditableTable)):
            parent.clear()
            return
        for child in parent.findChildren(QWidget, options=Qt.FindChildrenRecursively):
            if isinstance(child, QLineEdit):
                child.clear()

    def run(self) -> None:
        """Выполнить расчёт и показать результат."""
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

        # LaTeX-запись: формула или уравнение, которое ввёл пользователь
        try:
            from ..core import report as report_module

            self.result_view.set_latex(
                report_module.latex_of(result, source=self.latex_source()))
        except Exception:
            self.result_view.set_latex("")

        self.log(result)

    def log(self, result: Result) -> None:
        """Записать расчёт в журнал операций."""
        if self.controller is None:
            return
        logger = getattr(self.controller, "log_operation", None)
        if logger is None:
            return
        try:
            logger(self.history_action or self.title, result)
        except Exception:
            pass

    def latex_source(self) -> str:
        """Уравнение или формула, которую ввёл пользователь.

        Нужна для LaTeX и для отчёта. Вкладки хранят её по-разному:
        в fields, в отдельном атрибуте или в первой строке таблицы.
        """
        keys = ("equation", "formula", "reaction", "substance")

        # 1. Словарь полей текущего режима
        for key in keys:
            field = self.fields.get(key)
            value = _field_text(field)
            if value:
                return value

        # 2. Отдельные атрибуты вкладки
        for name in keys:
            value = _field_text(getattr(self, name, None))
            if value:
                return value

        # 3. Первая строка редактируемой таблицы (анализ формулы)
        table = getattr(self, "table", None)
        rows = getattr(table, "rows", None)
        if callable(rows):
            try:
                for row in rows():
                    for cell in row:
                        text = str(cell or "").strip()
                        if text:
                            return text
            except Exception:
                pass

        return ""

    def bind_enter(self) -> None:
        """Расчёт по Enter в любом поле ввода."""
        for edit in self.findChildren(QLineEdit):
            if not getattr(edit, "_enter_bound", False):
                edit.returnPressed.connect(self.run)
                edit._enter_bound = True

    def bind_all_entry(self, widget, handler) -> None:
        """Совместимость: подписка на Enter у всех полей."""
        for edit in widget.findChildren(QLineEdit):
            edit.returnPressed.connect(lambda: handler(None))

    # ---------------- вспомогательные конструкторы ----------------

    def info_block(self, parent, text: str, title: str = "") -> None:
        """Блок пояснений под полями."""
        heading = title or "Как это считается"
        card = Card(master=parent, title=heading, desc=text)
        card.pack(fill="x", pady=(6, 0))

    def row(self, parent, *widgets):
        """Разместить виджеты в одну строку."""
        frame = CTkFrame(parent, fg_color=None)
        for widget in widgets:
            pack(widget, side="left", padx=(0, 12))
        frame.pack(fill="x", pady=3)
        return frame
