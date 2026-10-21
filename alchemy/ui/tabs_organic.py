"""Вкладки органической химии: классы, сгорание, реакции.

Школьный курс 10 класса. Органика не входила в программу до этого,
поэтому вынесена отдельным модулем.
"""

from __future__ import annotations

from . import widgets as ctk
from .components import BaseTab, LabeledCombo, LabeledEntry
from . import theme
from ..core.errors import AlchemyError
from ..core.results import Result
from ..engines import organic as ORG


def _field(area, fields, key, label, default="", width=220):
    """Поле ввода с подписью."""
    widget = LabeledEntry(area, label, width=width, default=default)
    widget.pack(fill="x", pady=3)
    fields[key] = widget
    return widget


# ==========================================================================
# 1. Классы органики
# ==========================================================================


class OrganicClassesTab(BaseTab):
    """Класс вещества, гомологический ряд, изомерия, номенклатура."""

    title = "Органические классы"
    description = ("Класс органического вещества по формуле или названию, "
                   "гомологический ряд, число структурных изомеров, "
                   "правила названий.")
    action_label = "Определить"
    history_action = "Органика: классы"

    MODES = ["Класс по формуле", "Гомологический ряд", "Изомерия",
             "Номенклатура", "Все классы"]

    def build_inputs(self, parent):
        self.mode = LabeledCombo(parent, "Задача:", self.MODES, width=320)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}
        mode = self.mode.get()

        if mode == self.MODES[0]:
            _field(self.area, self.fields, "substance",
                   "Формула или название", "C2H5OH", width=240)
            hint = ("Понимает и формулу (C2H5OH, CH3COOH), и название "
                    "(этанол, уксусная). Если состав допускает два класса, "
                    "скажет об этом честно.")
        elif mode == self.MODES[1]:
            classes = [item["name"] for item in ORG._series()]
            combo = LabeledCombo(self.area, "Класс", classes, width=280)
            combo.pack(fill="x", pady=3)
            self.fields["series"] = combo
            hint = ("Показывает гомологов с молярными массами "
                    "и проверяет разницу в 14 г/моль.")
        elif mode == self.MODES[2]:
            _field(self.area, self.fields, "substance", "Формула",
                   "C5H12", width=200)
            hint = ("Для алканов число изомеров берётся из таблицы, "
                    "для остальных перечисляются типы изомерии.")
        else:
            hint = ("Корни названий по числу атомов углерода "
                    "и суффиксы по классам.")

        ctk.CTkLabel(self.area, text=hint, font=("Segoe UI", 10),
                     text_color=theme.COLOR_TEXT_DIM, anchor="w",
                     wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        mode = self.mode.get()
        if mode == self.MODES[0]:
            return ORG.class_of(self.fields["substance"].get())
        if mode == self.MODES[1]:
            return ORG.homologous_series(self.fields["series"].get())
        if mode == self.MODES[2]:
            return ORG.isomers(self.fields["substance"].get())
        if mode == self.MODES[3]:
            return ORG.nomenclature_help()
        return ORG.classes_table()


# ==========================================================================
# 2. Формула по продуктам сгорания
# ==========================================================================


class CombustionTab(BaseTab):
    """Молекулярная формула по продуктам сгорания."""

    title = "Формула по сгоранию"
    description = ("Классическая задача 10 класса: сожгли навеску, собрали "
                   "углекислый газ и воду — нашли формулу. Кислород "
                   "считается по разности масс.")
    action_label = "Найти формулу"
    history_action = "Формула по сгоранию"

    def build_inputs(self, parent):
        _field(parent, self.fields, "sample", "Масса навески, г", "4.6",
               width=140)
        _field(parent, self.fields, "co2", "Масса CO2, г", "8.8", width=140)
        _field(parent, self.fields, "co2_volume",
               "или объём CO2 при н.у., л", "", width=140)
        _field(parent, self.fields, "h2o", "Масса H2O, г", "5.4", width=140)
        _field(parent, self.fields, "molar", "Молярная масса, г/моль",
               "", width=140)

        ctk.CTkLabel(
            parent,
            text="Масса CO2 и объём CO2 — взаимозаменяемы, заполните что-то "
                 "одно. Молярную массу указывайте, если нужна молекулярная "
                 "формула, а не простейшая.",
            font=("Segoe UI", 10), text_color=theme.COLOR_TEXT_DIM, anchor="w",
            wraplength=760).pack(fill="x", pady=(6, 0))

    def _number(self, key: str, required: bool = False) -> float:
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            if required:
                raise AlchemyError(f"Не заполнено поле: {key}")
            return 0.0
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def calculate(self) -> Result:
        return ORG.combustion_formula(
            self._number("sample", required=True),
            co2_mass=self._number("co2"),
            h2o_mass=self._number("h2o"),
            co2_volume=self._number("co2_volume"),
            molar_mass=self._number("molar"),
        )


# ==========================================================================
# 3. Реакции органики
# ==========================================================================


class OrganicReactionsTab(BaseTab):
    """Реакции классов, качественные пробы, полимеры, переходы."""

    title = "Реакции органики"
    description = ("Реакции по классам органических веществ, качественные "
                   "пробы, полимеры и переходы между классами.")
    action_label = "Показать"
    history_action = "Органика: реакции"

    MODES = ["Реакции класса", "Качественные пробы", "Полимеры",
             "Генетическая связь"]

    def build_inputs(self, parent):
        self.mode = LabeledCombo(parent, "Задача:", self.MODES, width=320)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}
        mode = self.mode.get()
        classes = [item["name"] for item in ORG._series()]

        if mode in (self.MODES[0], self.MODES[1]):
            combo = LabeledCombo(self.area, "Класс", classes, width=280,
                                 default="Алкены")
            combo.pack(fill="x", pady=3)
            self.fields["series"] = combo
            hint = ("Качественные пробы есть не для всех классов: "
                    "для алканов и аренов их нет." if mode == self.MODES[1]
                    else "Уравнения записаны в той же форме, что понимает "
                         "парсер программы.")
        elif mode == self.MODES[3]:
            _field(self.area, self.fields, "first", "Откуда", "C2H5OH",
                   width=180)
            _field(self.area, self.fields, "second", "Куда", "CH3CHO",
                   width=180)
            hint = ("Показывает, возможен ли переход между классами "
                    "в школьном курсе.")
        else:
            hint = ""

        if hint:
            ctk.CTkLabel(self.area, text=hint, font=("Segoe UI", 10),
                         text_color=theme.COLOR_TEXT_DIM, anchor="w",
                         wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        mode = self.mode.get()
        if mode == self.MODES[0]:
            return ORG.reactions_of(self.fields["series"].get())
        if mode == self.MODES[1]:
            return ORG.qualitative_tests(self.fields["series"].get())
        if mode == self.MODES[2]:
            return ORG.polymers_table()
        return ORG.genetic_link(self.fields["first"].get(),
                                self.fields["second"].get())
