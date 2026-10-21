# -*- coding: utf-8 -*-
"""Тесты Qt-интерфейса.

Окна не открываются: используется offscreen-платформа Qt, поэтому тесты
идут в обычном прогоне и не мешают работе за компьютером.

Вкладки общие с tkinter-версией: их запускает слой совместимости, поэтому
здесь проверяется и он тоже.
"""

from __future__ import annotations

import os
import re
import unittest

# Платформу нужно выбрать до создания QApplication
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from alchemy.ui import theme
    from alchemy.ui_qt.app import ADVANCED_TABS, BASIC_TABS, CHAT_TABS, AlchemyApp
    HAS_QT = True
except ImportError:      # pragma: no cover
    QApplication = None
    HAS_QT = False

_app = None


def setUpModule():
    """Один QApplication на весь модуль."""
    global _app
    if HAS_QT and _app is None:
        _app = QApplication.instance() or QApplication([])
        theme.apply_theme(_app)


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestTheme(unittest.TestCase):
    """Оформление."""

    def test_colors_defined(self):
        for name in ("COLOR_BG", "COLOR_CARD", "COLOR_ACCENT", "COLOR_TEXT"):
            value = getattr(theme, name)
            self.assertTrue(value.startswith("#"))
            self.assertEqual(len(value), 7)

    def test_stylesheet_has_no_widget_background(self):
        """Фон на QWidget дал бы тёмные полосы внутри карточек."""
        head = theme.STYLESHEET.split("/* ------")[0]
        self.assertNotIn("QWidget {\n    background-color", head)

    def test_menu_styled(self):
        self.assertIn("QMenuBar", theme.STYLESHEET)
        self.assertIn("QMenu::item", theme.STYLESHEET)


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestAppShell(unittest.TestCase):
    """Главное окно."""

    def setUp(self):
        self.window = AlchemyApp()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def test_title(self):
        self.assertIn("Alchemy", self.window.windowTitle())

    def test_all_modules_registered(self):
        """16 основных, 19 дополнительных и отдельный блок ИИ-чата."""
        self.assertEqual(len(self.window._items),
                         len(BASIC_TABS) + len(ADVANCED_TABS) + len(CHAT_TABS))
        self.assertEqual(len(BASIC_TABS), 16)
        self.assertEqual(len(ADVANCED_TABS), 19)
        self.assertEqual(len(CHAT_TABS), 1)
        self.assertEqual(len(BASIC_TABS) + len(ADVANCED_TABS), 35)

    def test_open_every_tab(self):
        for spec in BASIC_TABS + ADVANCED_TABS + CHAT_TABS:
            self.window.open_tab(spec.cls)
            self.assertIn(spec.cls, self.window._tabs)

    def test_every_tab_calculates(self):
        """Каждая вкладка открывается и считает без падения."""
        failures = []
        for spec in BASIC_TABS + ADVANCED_TABS + CHAT_TABS:
            self.window.open_tab(spec.cls)
            tab = self.window._tabs.get(spec.cls)
            if tab is None:
                failures.append((spec.title, "не открылась"))
                continue
            try:
                tab.run()
            except Exception as exc:
                failures.append((spec.title, f"{type(exc).__name__}: {exc}"))
        self.assertEqual(failures, [])

    def test_open_same_tab_twice_reuses_widget(self):
        spec = BASIC_TABS[0]
        self.window.open_tab(spec.cls)
        first = self.window._tabs[spec.cls]
        self.window.open_tab(spec.cls)
        self.assertIs(self.window._tabs[spec.cls], first)

    def test_history_grows(self):
        self.window.open_tab(BASIC_TABS[0].cls)
        tab = self.window._tabs[BASIC_TABS[0].cls]
        before = len(self.window.history)
        tab.run()
        self.assertEqual(len(self.window.history), before + 1)

    def test_menu_actions_exist(self):
        menus = [action.text() for action in self.window.menuBar().actions()]
        self.assertIn("Файл", menus)
        self.assertIn("Правка", menus)


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestResultsInTabs(unittest.TestCase):
    """Расчёты через вкладки дают те же числа, что движки."""

    def setUp(self):
        self.window = AlchemyApp()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def test_molar_mass_matches_engine(self):
        from alchemy.core import formula as F

        self.window.open_tab(BASIC_TABS[0].cls)
        tab = self.window._tabs[BASIC_TABS[0].cls]
        tab.run()
        result = tab.result_view.last_result
        self.assertAlmostEqual(result.numeric(),
                               F.molar_mass("CuSO4*5H2O"), places=4)

    def test_result_is_shown_not_raw_dict(self):
        """Словарь показывается таблицей, а не строкой во весь экран."""
        from alchemy.core.results import Result

        self.window.open_tab(BASIC_TABS[0].cls)
        view = self.window._tabs[BASIC_TABS[0].cls].result_view
        view.show(Result(value={"масса": 1.0, "объём": 2.0}, label="Словарь"))
        self.assertTrue(view.table.isVisibleTo(view))
        self.assertFalse(view.value_label.isVisibleTo(view))

    def test_latex_appears_for_formula_tab(self):
        self.window.open_tab(BASIC_TABS[0].cls)
        tab = self.window._tabs[BASIC_TABS[0].cls]
        tab.run()
        self.assertIn("mathrm", tab.result_view._latex_text)

    def test_latex_source_from_field(self):
        self.window.open_tab(BASIC_TABS[0].cls)
        tab = self.window._tabs[BASIC_TABS[0].cls]
        self.assertEqual(tab.latex_source(), "CuSO4*5H2O")


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestCompatLayer(unittest.TestCase):
    """Слой совместимости tkinter → Qt."""

    def test_no_tkinter_left(self):
        """tkinter в проекте больше нет."""
        import pathlib
        import sys

        self.assertNotIn("customtkinter", sys.modules)

        root = pathlib.Path(__file__).resolve().parent.parent / "alchemy"
        offenders = []
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"^\s*(import|from)\s+(custom)?tkinter\b", text,
                         re.MULTILINE):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_entry_insert_and_get(self):
        from alchemy.ui.widgets import CTkEntry

        entry = CTkEntry()
        entry.insert(0, "abc")
        self.assertEqual(entry.get(), "abc")
        entry.insert("end", "d")
        self.assertEqual(entry.get(), "abcd")
        entry.delete(0, "end")
        self.assertEqual(entry.get(), "")

    def test_key_value_grid_value(self):
        from alchemy.ui.components import KeyValueGrid

        grid = KeyValueGrid(fields=[("dt", "Понижение", "0.31")])
        self.assertAlmostEqual(grid.value("dt"), 0.31)

    def test_key_value_grid_empty_optional(self):
        from alchemy.ui.components import KeyValueGrid

        grid = KeyValueGrid(fields=[("x", "Икс", "")])
        self.assertIsNone(grid.value("x", required=False))

    def test_key_value_grid_bad_number(self):
        from alchemy.core.errors import InputError
        from alchemy.ui.components import KeyValueGrid

        grid = KeyValueGrid(fields=[("x", "Икс", "abc")])
        with self.assertRaises(InputError):
            grid.value("x")

    def test_checkbox_get_returns_int(self):
        from alchemy.ui.widgets import CTkCheckBox

        box = CTkCheckBox()
        self.assertEqual(box.get(), 0)
        box.select()
        self.assertEqual(box.get(), 1)


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestResultView(unittest.TestCase):
    """Панель результата."""

    def setUp(self):
        from alchemy.ui.components import ResultView

        self.view = ResultView()

    def tearDown(self):
        self.view.deleteLater()

    def test_clear_restores_placeholder(self):
        self.view.clear()
        self.assertIn("Результат появится", self.view.label.text())

    def test_show_error(self):
        self.view.show_error("что-то пошло не так")
        self.assertIn("Ошибка", self.view.label.text())

    def test_scalar_shows_value(self):
        from alchemy.core.results import Result

        self.view.show(Result(value=42.0, unit="г", label="Масса"))
        self.assertTrue(self.view.value_label.isVisibleTo(self.view))
        self.assertIn("42", self.view.value_label.text())

    def test_table_hides_value_label(self):
        from alchemy.core.results import table_result

        result = table_result([{"А": "1", "Б": "2"}], label="Таблица")
        self.view.show(result)
        self.assertFalse(self.view.value_label.isVisibleTo(self.view))
        self.assertTrue(self.view.table.isVisibleTo(self.view))

    def test_series_rendered_as_table(self):
        from alchemy.core.results import series_result

        result = series_result([(0.0, 1.0), (1.0, 2.0)],
                               x_label="t", y_label="pH", label="Серия")
        self.view.show(result)
        self.assertEqual(self.view.table.rowCount(), 2)
        self.assertEqual(self.view.table.columnCount(), 2)

    def test_latex_button_hidden_by_default(self):
        self.assertFalse(self.view.latex_button.isVisibleTo(self.view))

    def test_latex_button_shown_when_set(self):
        self.view.set_latex(r"\mathrm{H_{2}O}")
        self.assertTrue(self.view.latex_button.isVisibleTo(self.view))

    def test_clear_resets_latex(self):
        self.view.set_latex(r"\mathrm{H_{2}O}")
        self.view.clear()
        self.assertEqual(self.view._latex_text, "")


if __name__ == "__main__":
    unittest.main()
