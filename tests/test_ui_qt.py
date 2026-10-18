# -*- coding: utf-8 -*-
"""Тесты Qt-интерфейса.

Окна не открываются: используется offscreen-платформа Qt, поэтому тесты
идут в обычном прогоне и не мешают работе за компьютером.
"""

from __future__ import annotations

import os
import unittest

# Платформу нужно выбрать до создания QApplication
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:      # pragma: no cover
    QApplication = None


HAS_QT = QApplication is not None

_app = None


def setUpModule():
    """Один QApplication на весь модуль."""
    global _app
    if HAS_QT and _app is None:
        _app = QApplication.instance() or QApplication([])


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestTheme(unittest.TestCase):
    """Оформление."""

    def test_colors_defined(self):
        from alchemy.ui_qt import theme

        for name in ("COLOR_BG", "COLOR_CARD", "COLOR_ACCENT", "COLOR_TEXT"):
            value = getattr(theme, name)
            self.assertTrue(value.startswith("#"))
            self.assertEqual(len(value), 7)

    def test_stylesheet_has_no_widget_background(self):
        """Фон на QWidget дал бы тёмные полосы внутри карточек."""
        from alchemy.ui_qt import theme

        head = theme.STYLESHEET.split("/* ------")[0]
        self.assertNotIn("QWidget {\n    background-color", head)

    def test_font_helper(self):
        from alchemy.ui_qt import theme

        self.assertTrue(theme.font(10).family())
        self.assertTrue(theme.font(12, bold=True).bold())


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestAppShell(unittest.TestCase):
    """Главное окно."""

    def setUp(self):
        from alchemy.ui_qt import theme
        from alchemy.ui_qt.app import AlchemyApp

        theme.apply_theme(_app)
        self.window = AlchemyApp()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def test_title(self):
        self.assertIn("Alchemy", self.window.windowTitle())

    def test_tabs_registered(self):
        self.assertGreaterEqual(len(self.window._items), 3)

    def test_open_every_tab(self):
        from alchemy.ui_qt.app import ADVANCED_TABS, BASIC_TABS

        for spec in BASIC_TABS + ADVANCED_TABS:
            self.window.open_tab(spec.cls)
            self.assertIn(spec.cls, self.window._tabs)

    def test_open_same_tab_twice_reuses_widget(self):
        from alchemy.ui_qt.app import BASIC_TABS

        spec = BASIC_TABS[0]
        self.window.open_tab(spec.cls)
        first = self.window._tabs[spec.cls]
        self.window.open_tab(spec.cls)
        self.assertIs(self.window._tabs[spec.cls], first)

    def test_history_grows(self):
        from alchemy.ui_qt.app import BASIC_TABS

        self.window.open_tab(BASIC_TABS[0].cls)
        tab = self.window._tabs[BASIC_TABS[0].cls]
        before = len(self.window.history)
        tab.run()
        self.assertEqual(len(self.window.history), before + 1)


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestMolarMassTab(unittest.TestCase):
    """Молярная масса в Qt-версии."""

    def setUp(self):
        from alchemy.ui_qt.tabs_basic import MolarMassTab

        self.tab = MolarMassTab()

    def tearDown(self):
        self.tab.deleteLater()

    def test_molar_mass_matches_engine(self):
        from alchemy.core import formula as F

        result = self.tab.calculate()
        self.assertAlmostEqual(result.numeric(), F.molar_mass("CuSO4*5H2O"),
                               places=4)

    def test_charge_notation_understood(self):
        self.tab.formula.set("MnO4-")
        result = self.tab.calculate()
        self.assertAlmostEqual(result.numeric(), 118.936, delta=0.01)

    def test_empty_formula_raises(self):
        from alchemy.core.errors import AlchemyError

        self.tab.formula.set("")
        with self.assertRaises(AlchemyError):
            self.tab.calculate()

    def test_run_fills_result(self):
        self.tab.run()
        self.assertIn("г/моль", self.tab.result_view.value_label.text())

    def test_error_shown_not_raised(self):
        self.tab.formula.set("Xx2O3")
        self.tab.run()
        self.assertIn("Ошибка", self.tab.result_view.label.text())

    def test_sample_mass_conversion(self):
        self.tab.formula.set("H2O")
        self.tab.sample_mass.set("18.015")
        result = self.tab.calculate()
        self.assertIn("моль", result.summary())


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestThermoTab(unittest.TestCase):
    """Термохимия в Qt-версии."""

    def setUp(self):
        from alchemy.ui_qt.tabs_basic import ThermoTab

        self.tab = ThermoTab()

    def tearDown(self):
        self.tab.deleteLater()

    def test_enthalpy(self):
        result = self.tab.calculate()
        self.assertAlmostEqual(result.numeric(), 178.3, delta=1.0)

    def test_mode_switch_adds_temperature_field(self):
        self.tab.mode.set("При заданной температуре (закон Кирхгофа)")
        self.assertIn("temperature", self.tab.fields)

    def test_kirchhoff_mode(self):
        self.tab.mode.set("При заданной температуре (закон Кирхгофа)")
        self.tab.fields["temperature"].set("1000")
        result = self.tab.calculate()
        self.assertIsNotNone(result.numeric())

    def test_bad_temperature(self):
        from alchemy.core.errors import AlchemyError

        self.tab.mode.set("При заданной температуре (закон Кирхгофа)")
        self.tab.fields["temperature"].set("abc")
        with self.assertRaises(AlchemyError):
            self.tab.calculate()


@unittest.skipUnless(HAS_QT, "PySide6 не установлена")
class TestResultView(unittest.TestCase):
    """Панель результата."""

    def setUp(self):
        from alchemy.ui_qt.components import ResultView

        self.view = ResultView()

    def tearDown(self):
        self.view.deleteLater()

    def test_clear_restores_placeholder(self):
        self.view.clear()
        self.assertIn("Результат появится", self.view.label.text())

    def test_show_error(self):
        self.view.show_error("что-то пошло не так")
        self.assertIn("Ошибка", self.view.label.text())
        self.assertTrue(self.view.warn_box.isVisibleTo(self.view))

    def test_table_hides_value_label(self):
        from alchemy.core.results import table_result

        result = table_result([{"А": "1", "Б": "2"}], label="Таблица")
        self.view.show(result)
        self.assertFalse(self.view.value_label.isVisibleTo(self.view))
        self.assertTrue(self.view.table.isVisibleTo(self.view))

    def test_scalar_shows_value(self):
        from alchemy.core.results import Result

        self.view.show(Result(value=42.0, unit="г", label="Масса"))
        self.assertTrue(self.view.value_label.isVisibleTo(self.view))
        self.assertIn("42", self.view.value_label.text())


if __name__ == "__main__":
    unittest.main()
