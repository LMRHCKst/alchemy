"""Тема Qt-интерфейса: цвета, шрифты и общая таблица стилей."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# --------------------------------------------------------------------------
# Цвета — те же, что были в tkinter-версии, чтобы программа не меняла лицо
# --------------------------------------------------------------------------

COLOR_BG = "#1a1a1a"
COLOR_SIDEBAR = "#141414"
COLOR_CARD = "#242424"
COLOR_CARD_ALT = "#2b2b2b"
COLOR_FIELD = "#1f1f1f"
COLOR_ACCENT = "#4facfe"
COLOR_ACCENT_DIM = "#2c6fa8"
COLOR_OK = "#2ecc71"
COLOR_WARN = "#f39c12"
COLOR_ERROR = "#e74c3c"
COLOR_TEXT = "#e8e8e8"
COLOR_TEXT_DIM = "#9a9a9a"
COLOR_TEXT_FAINT = "#6d6d6d"
COLOR_BORDER = "#3a3a3a"

# --------------------------------------------------------------------------
# Шрифты
# --------------------------------------------------------------------------

FAMILY_UI = "Segoe UI"
FAMILY_MONO = "Consolas"


def font(size: int, bold: bool = False, mono: bool = False) -> QFont:
    """Шрифт интерфейса нужного размера."""
    result = QFont(FAMILY_MONO if mono else FAMILY_UI, size)
    if bold:
        result.setBold(True)
    return result


FONT_TITLE = 18
FONT_HEADING = 13
FONT_BODY = 10
FONT_SMALL = 9
FONT_RESULT = 20


# --------------------------------------------------------------------------
# Таблица стилей
# --------------------------------------------------------------------------

STYLESHEET = f"""
/* Фон задаётся только контейнерам. Если повесить его на QWidget, подписи
   внутри карточек получат цвет окна и проступят тёмными полосами. */
QWidget {{
    color: {COLOR_TEXT};
    font-family: "{FAMILY_UI}";
    font-size: {FONT_BODY}pt;
}}

QLabel {{
    background: transparent;
}}

QMainWindow, QDialog {{
    background-color: {COLOR_BG};
}}

QScrollArea, #Page {{
    background-color: {COLOR_BG};
}}

/* ---------- боковое меню ---------- */

#Sidebar {{
    background-color: {COLOR_SIDEBAR};
    border-right: 1px solid {COLOR_BORDER};
}}

#SidebarTitle {{
    color: {COLOR_ACCENT};
    font-size: 19pt;
    font-weight: bold;
    padding: 18px 16px 2px 16px;
}}

#SidebarSubtitle {{
    color: {COLOR_TEXT_FAINT};
    font-size: {FONT_SMALL}pt;
    padding: 0 16px 14px 16px;
}}

#SidebarGroup {{
    color: {COLOR_TEXT_FAINT};
    font-size: {FONT_SMALL}pt;
    padding: 12px 16px 4px 16px;
}}

QListWidget#SidebarList {{
    background-color: {COLOR_SIDEBAR};
    border: none;
    outline: none;
    padding: 0 8px;
}}

QListWidget#SidebarList::item {{
    padding: 5px 10px;
    border-radius: 6px;
    color: {COLOR_TEXT};
}}

QListWidget#SidebarList::item:hover {{
    background-color: #1f1f1f;
}}

QListWidget#SidebarList::item:selected {{
    background-color: {COLOR_ACCENT_DIM};
    color: #ffffff;
}}

/* ---------- меню ---------- */

QMenuBar {{
    background-color: {COLOR_SIDEBAR};
    color: {COLOR_TEXT};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 2px 6px;
}}

QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {COLOR_CARD_ALT};
}}

QMenu {{
    background-color: {COLOR_CARD};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 22px 6px 16px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {COLOR_ACCENT_DIM};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background: {COLOR_BORDER};
    margin: 4px 8px;
}}

/* ---------- карточки ---------- */

#Card {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}

#CardBody {{
    background-color: transparent;
}}

#CardTitle {{
    font-size: {FONT_HEADING}pt;
    font-weight: bold;
    color: {COLOR_TEXT};
    padding: 0;
}}

#CardDesc {{
    color: {COLOR_TEXT_FAINT};
    font-size: {FONT_SMALL}pt;
}}

/* ---------- поля ввода ---------- */

QLineEdit {{
    background-color: {COLOR_FIELD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_ACCENT_DIM};
}}

QLineEdit:focus {{
    border: 1px solid {COLOR_ACCENT};
}}

QLineEdit:disabled {{
    color: {COLOR_TEXT_FAINT};
}}

QComboBox {{
    background-color: {COLOR_FIELD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    color: {COLOR_TEXT};
}}

QComboBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_ACCENT_DIM};
    color: {COLOR_TEXT};
    outline: none;
}}

/* ---------- кнопки ---------- */

QPushButton {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    color: {COLOR_TEXT};
}}

QPushButton:hover {{
    background-color: #333333;
}}

QPushButton:pressed {{
    background-color: #1d1d1d;
}}

QPushButton#Primary {{
    background-color: #2563a8;
    border: 1px solid {COLOR_ACCENT};
    color: #ffffff;
    font-weight: bold;
}}

QPushButton#Primary:hover {{
    background-color: {COLOR_ACCENT_DIM};
}}

QPushButton#Link {{
    background-color: transparent;
    border: none;
    color: {COLOR_ACCENT};
    text-align: left;
    padding: 3px 0;
}}

QPushButton#Link:hover {{
    color: #7fc3ff;
}}

/* ---------- прокрутка ---------- */

QScrollArea {{
    border: none;
    background-color: {COLOR_BG};
}}

QScrollBar:vertical {{
    background: {COLOR_BG};
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: #3d3d3d;
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: #4d4d4d;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {COLOR_BG};
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: #3d3d3d;
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ---------- таблицы ---------- */

QTableWidget {{
    background-color: {COLOR_CARD};
    alternate-background-color: #282828;
    gridline-color: {COLOR_BORDER};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_ACCENT_DIM};
}}

QTableWidget::item {{
    padding: 4px 6px;
}}

QHeaderView::section {{
    background-color: #303030;
    color: {COLOR_TEXT};
    border: none;
    border-right: 1px solid {COLOR_BORDER};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 5px 6px;
    font-weight: bold;
}}

/* ---------- текстовое поле хода расчёта ---------- */

QTextEdit {{
    background-color: {COLOR_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    color: {COLOR_TEXT};
    padding: 8px;
    selection-background-color: {COLOR_ACCENT_DIM};
}}

/* ---------- панель результата ---------- */

#ResultPanel {{
    background-color: {COLOR_CARD_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}

#ResultLabel {{
    font-size: {FONT_HEADING}pt;
    font-weight: bold;
    color: {COLOR_TEXT};
}}

#ResultValue {{
    font-family: "{FAMILY_MONO}";
    font-size: {FONT_RESULT}pt;
    font-weight: bold;
    color: {COLOR_ACCENT};
}}

#ResultMethod {{
    color: {COLOR_TEXT_DIM};
    font-size: {FONT_SMALL}pt;
}}

#ResultWarning {{
    color: {COLOR_WARN};
    font-size: {FONT_SMALL}pt;
}}

#ResultError {{
    color: {COLOR_ERROR};
    font-size: {FONT_SMALL}pt;
}}

/* ---------- прочее ---------- */

#PageTitle {{
    font-size: {FONT_TITLE}pt;
    font-weight: bold;
    color: {COLOR_TEXT};
}}

#PageDesc {{
    color: {COLOR_TEXT_DIM};
    font-size: {FONT_SMALL}pt;
}}

#FieldLabel {{
    color: {COLOR_TEXT};
}}

#FieldHint {{
    color: {COLOR_TEXT_FAINT};
    font-size: {FONT_SMALL}pt;
}}

#StatusBar {{
    background-color: {COLOR_SIDEBAR};
    color: {COLOR_TEXT_FAINT};
    font-size: {FONT_SMALL}pt;
    border-top: 1px solid {COLOR_BORDER};
}}

QCheckBox {{
    color: {COLOR_TEXT};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    background-color: {COLOR_FIELD};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
}}

QToolTip {{
    background-color: {COLOR_CARD_ALT};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    padding: 4px 6px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Применить тему к приложению."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLOR_BG))
    palette.setColor(QPalette.WindowText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.Base, QColor(COLOR_FIELD))
    palette.setColor(QPalette.AlternateBase, QColor(COLOR_CARD))
    palette.setColor(QPalette.Text, QColor(COLOR_TEXT))
    palette.setColor(QPalette.Button, QColor(COLOR_CARD_ALT))
    palette.setColor(QPalette.ButtonText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.Highlight, QColor(COLOR_ACCENT_DIM))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor(COLOR_CARD_ALT))
    palette.setColor(QPalette.ToolTipText, QColor(COLOR_TEXT))
    app.setPalette(palette)

    app.setStyleSheet(STYLESHEET)
