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

#: исходные (тёмные) значения: к ним возвращаемся при переключении темы
_DARK_VALUES = {
    "COLOR_BG": COLOR_BG,
    "COLOR_SIDEBAR": COLOR_SIDEBAR,
    "COLOR_CARD": COLOR_CARD,
    "COLOR_CARD_ALT": COLOR_CARD_ALT,
    "COLOR_FIELD": COLOR_FIELD,
    "COLOR_ACCENT": COLOR_ACCENT,
    "COLOR_ACCENT_DIM": COLOR_ACCENT_DIM,
    "COLOR_OK": COLOR_OK,
    "COLOR_WARN": COLOR_WARN,
    "COLOR_ERROR": COLOR_ERROR,
    "COLOR_TEXT": COLOR_TEXT,
    "COLOR_TEXT_DIM": COLOR_TEXT_DIM,
    "COLOR_TEXT_FAINT": COLOR_TEXT_FAINT,
    "COLOR_BORDER": COLOR_BORDER,
}


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

/* Значок бета — по образцу яндексовых пометок: маленькая скруглённая
   плашка фирменного красного, строчными буквами, рядом с названием. */
/* Пометка беты — тихая: без заливки, тонкая рамка и приглушённая буква.
   Она не должна спорить с названием, только сообщать статус. */
#BetaBadge {{
    background-color: transparent;
    color: #9a9a9a;
    border: 1px solid #4a4a4a;
    border-radius: 6px;
    font-size: 10pt;
    padding: 0px 6px 1px 6px;
    min-width: 19px;
    min-height: 19px;
}}

#SidebarSearch {{
    background-color: {COLOR_FIELD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    margin: 0 12px 8px 12px;
    color: {COLOR_TEXT};
}}

#SidebarSubtitle {{
    color: {COLOR_TEXT_FAINT};
    font-size: {FONT_SMALL}pt;
    padding: 10px 16px 14px 16px;
    border-top: 1px solid {COLOR_BORDER};
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
    padding: 0 8px 10px 8px;
}}

QListWidget#SidebarList::item {{
    padding: 6px 10px;
    margin: 1px 0px;
    border-radius: 6px;
}}

QListWidget#SidebarList::item:hover {{
    background-color: #1f1f1f;
}}

QListWidget#SidebarList::item:selected {{
    background-color: {COLOR_ACCENT_DIM};
    color: #ffffff;
    border-left: 3px solid {COLOR_ACCENT};
    padding-left: 7px;
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

#ResultValue[muted="true"] {{
    color: {COLOR_TEXT_DIM};
}}

#ResultValue[error="true"] {{
    color: {COLOR_ERROR};
}}

#ResultValue[warn="true"] {{
    color: {COLOR_WARN};
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


# Соответствие тёмных цветов светлым. Стили собраны из констант выше,
# поэтому светлая тема делается заменой: так один и тот же код рисует
# две разные картинки, и не надо держать две копии стилей.
LIGHT_MAP = {
    "#1a1a1a": "#f2f4f7",   # фон окна
    "#141414": "#ffffff",   # сайдбар
    "#242424": "#ffffff",   # карточки
    "#2b2b2b": "#e9edf3",   # поля и кнопки
    "#1f1f1f": "#e3e8f0",   # наведение
    "#1d1d1d": "#e6eaf1",
    "#333333": "#c9d0da",
    "#3d3d3d": "#bcc4cf",
    "#4a4a4a": "#b3bbc7",
    "#4d4d4d": "#aab3c0",
    "#e8e8e8": "#111827",   # основной текст: почти чёрный
    "#9a9a9a": "#4b5563",   # вторичный текст: заметнее
    "#6d6d6d": "#4b5563",   # приглушённый
    "#3a3a3a": "#cfd6e0",   # границы
    "#4facfe": "#1a5fb4",   # акцент
    "#7fc3ff": "#0f4c9c",
    "#2c6fa8": "#d6e4f7",   # фон выделения в полях
    "#2563a8": "#1a5fb4",
    "#2ecc71": "#15803d",
    "#f39c12": "#a16207",
    "#e74c3c": "#b91c1c",
}

#: Что дописать в светлой теме сверх замены цветов. Список выделения
#: в меню и текст на акцентных кнопках заменой не лечатся: там фон и
#: цвет текста подбираются парой, иначе получается белое на светлом.
LIGHT_OVERRIDES = """
QListWidget#SidebarList::item:selected {
    background-color: #d6e4f7;
    color: #0b2e59;
    border-left: 3px solid #1a5fb4;
    padding-left: 7px;
}

QListWidget#SidebarList::item:selected:hover {
    background-color: #c8dcf5;
}

QPushButton#Primary, QPushButton:checked {
    color: #ffffff;
}

QMenu::item:selected {
    background-color: #d6e4f7;
    color: #0b2e59;
}

QTabBar::tab:selected {
    color: #0b2e59;
}

#ResultValue {
    color: #0f4c9c;
}

#ResultWarning {
    color: #92400e;
}

#ResultError {
    color: #b91c1c;
}
"""


def stylesheet(light: bool = False) -> str:
    """Таблица стилей для нужной темы."""
    if not light:
        return STYLESHEET
    text = STYLESHEET
    for dark, bright in LIGHT_MAP.items():
        text = text.replace(dark, bright)
    return text + LIGHT_OVERRIDES


def _use_colors(light: bool) -> None:
    """Подменить константы темы.

    Часть интерфейса задаёт цвет при создании виджета и запоминает его.
    Чтобы такие виджеты получали правильный цвет, константы модуля
    переключаются вместе со стилями: код читает их в момент создания.
    """
    global COLOR_BG, COLOR_SIDEBAR, COLOR_CARD, COLOR_CARD_ALT, COLOR_FIELD
    global COLOR_ACCENT, COLOR_ACCENT_DIM, COLOR_OK, COLOR_WARN, COLOR_ERROR
    global COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_FAINT, COLOR_BORDER

    for name, dark in _DARK_VALUES.items():
        value = LIGHT_MAP.get(dark, dark) if light else dark
        globals()[name] = value


def apply_theme(app: QApplication, light: bool = False) -> None:
    """Применить тему к приложению."""
    _use_colors(light)
    app.setStyle("Fusion")

    def color(name: str) -> str:
        return LIGHT_MAP.get(name, name) if light else name

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(color(COLOR_BG)))
    palette.setColor(QPalette.WindowText, QColor(color(COLOR_TEXT)))
    palette.setColor(QPalette.Base, QColor(color(COLOR_FIELD)))
    palette.setColor(QPalette.AlternateBase, QColor(color(COLOR_CARD)))
    palette.setColor(QPalette.Text, QColor(color(COLOR_TEXT)))
    palette.setColor(QPalette.Button, QColor(color(COLOR_CARD_ALT)))
    palette.setColor(QPalette.ButtonText, QColor(color(COLOR_TEXT)))
    palette.setColor(QPalette.Highlight, QColor(color(COLOR_ACCENT)))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    # неактивные элементы: в светлой теме стандартный серый слишком бледный
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(color(COLOR_TEXT_FAINT)))

    palette.setColor(QPalette.ToolTipBase, QColor(color(COLOR_CARD_ALT)))
    palette.setColor(QPalette.ToolTipText, QColor(color(COLOR_TEXT)))
    app.setPalette(palette)

    app.setStyleSheet(stylesheet(light))
