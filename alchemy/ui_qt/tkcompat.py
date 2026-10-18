"""Совместимый слой: tkinter-подобный API поверх Qt.

Вкладки писались под customtkinter. Вместо того чтобы переписывать три
с половиной тысячи строк, этот модуль даёт те же шесть виджетов и те же
методы (pack, configure, insert, winfo_children, destroy) на Qt.

Что это даёт: вкладки остаются единственным источником правды, а перенос
на Qt сводится к подмене backend. Когда-нибудь вкладки перепишут нативно,
и тогда этот модуль просто выбросят.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from . import theme

# --------------------------------------------------------------------------
# Разбор аргументов в стиле tkinter
# --------------------------------------------------------------------------


def _font(value) -> QFont:
    """Шрифт из кортежа вида («Segoe UI», 12) или («Consolas», 13, «bold»)."""
    if isinstance(value, QFont):
        return value
    if isinstance(value, tuple) and value:
        family = str(value[0])
        size = int(value[1]) if len(value) > 1 and isinstance(
            value[1], (int, float)) else theme.FONT_BODY
        style = value[2] if len(value) > 2 else ""
        result = QFont(family, size)
        if style and "bold" in str(style):
            result.setBold(True)
        return result
    return theme.font(theme.FONT_BODY)


def _color(value) -> str | None:
    """Цвет из строки. «transparent» и None означают «не задавать»."""
    if not value or not isinstance(value, str):
        return None
    if value.lower() in ("transparent", "none"):
        return None
    return value


def _pixels(value) -> int:
    """Размер из аргумента. Кортежи вида (0, 8) сводим к одному числу."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, (tuple, list)):
        numbers = [int(v) for v in value if isinstance(v, (int, float))]
        return max(numbers) if numbers else 0
    return 0


# --------------------------------------------------------------------------
# Раскладка: pack() поверх Qt-компоновок
# --------------------------------------------------------------------------


def _ensure_layout(parent: QWidget) -> QVBoxLayout | QHBoxLayout:
    """Компоновка контейнера: вертикальная по умолчанию."""
    layout = parent.layout()
    if layout is None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        parent.setLayout(layout)
    return layout


def pack(widget: QWidget, side: str = "top", fill: str = "none",
         expand: bool = False, anchor: str = "center",
         padx=None, pady=None, **_ignored) -> None:
    """Разместить виджет в контейнере, как это делал tkinter."""
    parent = widget.parentWidget()
    if parent is None:
        return

    horizontal = side in ("left", "right")
    layout = _ensure_layout(parent)

    if horizontal:
        # Внутри вертикальной компоновки горизонтальные элементы собираются
        # в общую строку, пока подряд идут только они
        if not isinstance(layout, QHBoxLayout):
            row = getattr(parent, "_compat_row", None)
            if row is None:
                row = QWidget(parent)
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)
                layout.addWidget(row)
                parent._compat_row = row
            layout = row.layout()
    else:
        # Вертикальный элемент закрывает начатую строку
        parent._compat_row = None

    gap = _pixels(pady) if pady is not None else _pixels(padx)

    if fill in ("x", "both"):
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        widget.setMinimumWidth(0)
        widget.setMaximumWidth(16777215)

    alignment = Qt.AlignmentFlag(0)
    if anchor in ("w", "nw", "sw"):
        alignment = Qt.AlignLeft
    elif anchor in ("e", "ne", "se"):
        alignment = Qt.AlignRight

    if horizontal:
        # В строке всегда держим распорку в конце. Без неё Qt раздаёт
        # свободное место между ячейками, и поля уезжают от подписей.
        if not (layout.count() and layout.itemAt(layout.count() - 1)
                .spacerItem() is not None):
            layout.addStretch(1)

        # И отступ, и виджет вставляются ПЕРЕД распоркой. Если добавить
        # отступ через addSpacing, он уйдёт за распорку и следующий виджет
        # окажется уже после неё — элементы разъедутся по всей строке.
        position = layout.count() - 1
        if gap:
            layout.insertSpacing(position, gap)
            position += 1
        layout.insertWidget(position, widget, 0, alignment)
    else:
        if gap:
            layout.addSpacing(gap)
        if alignment:
            layout.addWidget(widget, 0, alignment)
        else:
            layout.addWidget(widget, 1 if expand else 0)


# --------------------------------------------------------------------------
# Общая часть виджетов
# --------------------------------------------------------------------------


class _Compat:
    """Методы, которые вкладки ждут от любого виджета."""

    def pack(self, **kwargs) -> None:
        pack(self, **kwargs)

    def pack_forget(self) -> None:
        layout = self.parentWidget().layout() if self.parentWidget() else None
        if layout is not None:
            layout.removeWidget(self)
        self.setVisible(False)

    def grid(self, row: int = 0, column: int = 0, **kwargs) -> None:
        """Единственный вызов grid в проекте — сводим к pack."""
        pack(self, side="top", fill="x")

    def winfo_children(self) -> list:
        return self.findChildren(QWidget, options=Qt.FindDirectChildrenOnly)

    def destroy(self) -> None:
        # setParent(None) убирает виджет из компоновки сразу, deleteLater
        # освобождает память в цикле событий
        self.setParent(None)
        self.deleteLater()

    def configure(self, **kwargs) -> None:
        self._apply(**kwargs)

    def config(self, **kwargs) -> None:
        self._apply(**kwargs)

    def _apply(self, **kwargs) -> None:
        """Разобрать аргументы configure и применить к Qt-виджету."""
        for key, value in kwargs.items():
            if key in ("text", "label") and hasattr(self, "setText"):
                self.setText(str(value))
            elif key == "font" and hasattr(self, "setFont"):
                self.setFont(_font(value))
            elif key in ("text_color", "fg_color", "hover_color",
                         "border_color") and hasattr(self, "setStyleSheet"):
                color = _color(value)
                if color is not None:
                    if key == "fg_color":
                        self.setStyleSheet(f"background-color: {color};")
                    elif key == "text_color":
                        self.setStyleSheet(f"color: {color};")
            elif key == "state" and hasattr(self, "setEnabled"):
                self.setEnabled(str(value) not in ("disabled", "readonly"))
            elif key == "values" and hasattr(self, "addItems"):
                self.clear()
                self.addItems([str(v) for v in value])
            elif key == "height" and hasattr(self, "setFixedHeight"):
                if isinstance(value, (int, float)):
                    self.setFixedHeight(int(value))
            elif key == "width" and hasattr(self, "setFixedWidth"):
                if isinstance(value, (int, float)):
                    self.setFixedWidth(int(value))
            elif key == "wraplength" and hasattr(self, "setWordWrap"):
                self.setWordWrap(True)


# --------------------------------------------------------------------------
# Виджеты
# --------------------------------------------------------------------------


class CTkFrame(_Compat, QFrame):
    """Контейнер. Внутри себя собирает дочерние элементы через pack()."""

    def __init__(self, master=None, fg_color=None, corner_radius=None,
                 width=None, height=None, **kwargs):
        super().__init__(master)
        self.setFrameShape(QFrame.NoFrame)
        color = _color(fg_color)
        if color is not None:
            self.setStyleSheet(
                f"background-color: {color}; border-radius: "
                f"{int(corner_radius or 0)}px;")
        if width:
            self.setMinimumWidth(int(width))

    def configure(self, **kwargs):
        self._apply(**kwargs)


class CTkLabel(_Compat, QLabel):
    """Подпись."""

    def __init__(self, master=None, text: str = "", font=None,
                 text_color=None, anchor=None, justify=None,
                 wraplength=None, width=None, **kwargs):
        super().__init__(str(text), master)
        self.setFont(_font(font) if font else theme.font(theme.FONT_BODY))
        color = _color(text_color)
        if color is not None:
            self.setStyleSheet(f"color: {color};")
        if wraplength:
            self.setWordWrap(True)
        if anchor in ("w", "nw", "sw"):
            self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        elif anchor in ("e", "ne", "se"):
            self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if width:
            self.setFixedWidth(int(width))


class CTkEntry(_Compat, QLineEdit):
    """Поле ввода с tkinter-подобными insert/get/delete."""

    def __init__(self, master=None, width=None, font=None, **kwargs):
        super().__init__(master)
        if font:
            self.setFont(_font(font))
        if width:
            self.setFixedWidth(int(width))

    def insert(self, index, text: str) -> None:
        text = str(text)
        if str(index) in ("0", "insert") or index == 0:
            self.setText(text + self.text())
        else:
            self.setText(self.text() + text)

    def delete(self, first, second=None) -> None:
        if str(second) == "end" or second is None:
            self.clear()
        else:
            text = self.text()
            start = int(first) if str(first).isdigit() else 0
            end = int(second) if str(second).isdigit() else len(text)
            self.setText(text[:start] + text[end:])

    def get(self) -> str:
        return self.text()

    def bind(self, sequence: str, handler=None) -> None:
        if sequence in ("<Return>", "<KP_Enter>") and handler is not None:
            self.returnPressed.connect(lambda: handler(None))


class CTkButton(_Compat, QPushButton):
    """Кнопка."""

    def __init__(self, master=None, text: str = "", width=None, font=None,
                 command=None, fg_color=None, text_color=None,
                 border_width=None, border_color=None, height=None, **kwargs):
        super().__init__(str(text), master)
        if font:
            self.setFont(_font(font))
        if width:
            self.setFixedWidth(int(width))
        if height:
            self.setFixedHeight(int(height))
        if command is not None:
            self.clicked.connect(lambda: command())
        color = _color(fg_color)
        text_c = _color(text_color)
        parts = []
        # Узкие кнопки (ячейки таблицы Менделеева — 38 px) при стилевом
        # отступе 16 px по краям обрезают текст до прочерка
        if width is not None and int(width) < 70:
            parts.append("padding: 0px; font-size: 9pt;")
        if color is not None:
            parts.append(f"background-color: {color};")
        if text_c is not None:
            parts.append(f"color: {text_c};")
        border = _color(border_color)
        if border is not None and border_width:
            parts.append(f"border: {int(border_width)}px solid {border};")
        if parts:
            self.setStyleSheet(" ".join(parts))

    def configure(self, **kwargs):
        if "command" in kwargs:
            try:
                self.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.clicked.connect(lambda: kwargs["command"]())
        self._apply(**{k: v for k, v in kwargs.items() if k != "command"})

    def invoke(self) -> None:
        self.click()


class CTkTextbox(_Compat, QTextEdit):
    """Многострочное поле."""

    def __init__(self, master=None, height=None, font=None, fg_color=None,
                 wrap="word", **kwargs):
        super().__init__(master)
        if font:
            self.setFont(_font(font))
        if height:
            self.setFixedHeight(int(height))
        color = _color(fg_color)
        if color is not None:
            self.setStyleSheet(f"background-color: {color};")
        self.setLineWrapMode(
            QTextEdit.WidgetWidth if wrap != "none" else QTextEdit.NoWrap)

    def insert(self, index, text: str) -> None:
        if str(index) in ("1.0", "0.0", "end-1c"):
            self.setPlainText(str(text))
        else:
            self.append(str(text))

    def get(self, first=None, second=None) -> str:
        return self.toPlainText()

    def delete(self, first, second=None) -> None:
        self.clear()


class CTkCheckBox(_Compat, QCheckBox):
    """Флажок."""

    def __init__(self, master=None, text: str = "", command=None,
                 font=None, **kwargs):
        super().__init__(str(text), master)
        if font:
            self.setFont(_font(font))
        if command is not None:
            self.stateChanged.connect(lambda _: command())

    def get(self) -> int:
        return 1 if self.isChecked() else 0

    def select(self) -> None:
        self.setChecked(True)

    def deselect(self) -> None:
        self.setChecked(False)

    def toggle(self) -> None:
        self.setChecked(not self.isChecked())


class CTkComboBox(_Compat, QComboBox):
    """Выпадающий список."""

    def __init__(self, master=None, values=None, width=None, command=None,
                 font=None, **kwargs):
        super().__init__(master)
        if values:
            self.addItems([str(v) for v in values])
        if width:
            self.setFixedWidth(int(width))
        if font:
            self.setFont(_font(font))
        if command is not None:
            self.currentTextChanged.connect(lambda _: command())

    def get(self) -> str:
        return self.currentText()

    def set(self, value) -> None:
        self.setCurrentText(str(value))

    def configure(self, **kwargs):
        if "command" in kwargs:
            try:
                self.currentTextChanged.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.currentTextChanged.connect(lambda _: kwargs["command"]())
        self._apply(**kwargs)


class CTkScrollableFrame(_Compat, QFrame):
    """Прокручиваемый контейнер. В проекте почти не используется."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)


# --------------------------------------------------------------------------
# Заглушки для tkinter-функций
# --------------------------------------------------------------------------


def set_appearance_mode(mode: str) -> None:
    """Тёмная тема задаётся в theme.apply_theme."""


def set_default_color_theme(name: str) -> None:
    """Цветовая схема задаётся в theme.apply_theme."""


def set_widget_scaling(value: float) -> None:
    """Масштабирование берёт на себя Qt."""


class _FileDialog:
    """Замена tkinter.filedialog."""

    @staticmethod
    def asksaveasfilename(**kwargs) -> str:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            None, kwargs.get("title", "Сохранить"),
            kwargs.get("initialfile", ""), "Все файлы (*)")
        return path

    @staticmethod
    def askopenfilename(**kwargs) -> str:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            None, kwargs.get("title", "Открыть"), "",
            "Все файлы (*)")
        return path


class _MessageBox:
    """Замена tkinter.messagebox."""

    @staticmethod
    def showinfo(title: str = "", message: str = "", **kwargs) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(None, title, message)

    @staticmethod
    def showwarning(title: str = "", message: str = "", **kwargs) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(None, title, message)

    @staticmethod
    def showerror(title: str = "", message: str = "", **kwargs) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(None, title, message)

    @staticmethod
    def askyesno(title: str = "", message: str = "", **kwargs) -> bool:
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(None, title, message)
        return answer == QMessageBox.Yes


filedialog = _FileDialog()
messagebox = _MessageBox()


class FigureCanvasTkAgg:
    """Замена matplotlib-бэкенда: рисуем фигуру в Qt-контейнере."""

    #: без минимальной высоты холст схлопывается в ноль
    MIN_HEIGHT = 320

    def __init__(self, figure=None, master=None):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

        self.figure = figure
        # Родителя задаём сразу: pack() без родителя ничего не делает,
        # и график молча не появлялся
        self.canvas = FigureCanvasQTAgg(figure)
        self._master = master
        if master is not None:
            self.canvas.setParent(master)
        self.canvas.setMinimumHeight(self.MIN_HEIGHT)

    def get_tk_widget(self):
        """Возвращает виджет, который можно упаковать через pack()."""
        canvas = self.canvas
        if not hasattr(canvas, "pack"):
            # Вкладки зовут .pack() у результата — подмешиваем метод
            canvas.pack = lambda **kwargs: pack(canvas, **kwargs)
        return canvas

    def draw(self) -> None:
        self.canvas.draw()

    def draw_idle(self) -> None:
        self.canvas.draw_idle()
