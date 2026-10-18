"""Основные вкладки Qt-интерфейса. Пока портированы две: молярная масса
и термохимия — на них проверяется весь слой компонентов."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..core import formula as F
from ..core import periodic
from ..core.errors import AlchemyError
from ..core.results import Result
from ..engines import thermo as TH
from . import theme
from .components import BaseTab, LabeledCombo, LabeledEntry


def _clear_layout(layout) -> None:
    """Убрать все виджеты из компоновки."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


class MolarMassTab(BaseTab):
    """Молярная масса и состав вещества."""

    title = "Молярная масса"
    description = ("Масса и состав вещества. Понимает гидраты (CuSO4*5H2O), "
                   "ионы (MnO4-, SO4^-2, SO4{2-}), комплексы и состояния.")
    action_label = "Рассчитать"
    history_action = "Молярная масса"

    def build_inputs(self, parent):
        self.formula = LabeledEntry(
            parent, "Формула", width=280,
            hint="например CuSO4*5H2O или MnO4-", default="CuSO4*5H2O")
        parent.layout().addWidget(self.formula)

        self.sample_mass = LabeledEntry(
            parent, "Масса навески, г", width=120,
            hint="необязательно, для пересчёта в моли")
        parent.layout().addWidget(self.sample_mass)

        note = QLabel(
            "Заряд можно писать как MnO4-, MnO4^- или MnO4{-} — "
            "все три формы равнозначны.")
        note.setObjectName("FieldHint")
        note.setWordWrap(True)
        parent.layout().addWidget(note)

    def calculate(self) -> Result:
        text = self.formula.get().strip()
        if not text:
            raise AlchemyError("Введите формулу")

        comp = F.parse(text)

        res = Result(
            value=comp.molar_mass,
            unit="г/моль",
            label=f"Молярная масса {comp.display}",
            method="Сумма атомных масс по стандартным значениям IUPAC",
        )
        res.with_step(f"Разобрана формула: {comp.display}")
        res.with_step(f"Заряд: {comp.charge:+d}" if comp.charge
                      else "Заряд: 0 (нейтральная частица)")
        if comp.state:
            res.with_step(f"Агрегатное состояние: {comp.state}")

        res.with_step("")
        res.with_step("Вклад элементов:")
        for element_symbol in comp.elements:
            element = periodic.by_symbol(element_symbol)
            count = comp.counts[element_symbol]
            contribution = element.atomic_mass * count
            percent = comp.mass_percentages[element_symbol]
            res.with_step(
                f"  {element_symbol}: {count:g} x {element.atomic_mass:.4f} = "
                f"{contribution:.4f} г/моль ({percent:.3f} %)")

        res.with_step("")
        res.with_step(f"Итого: {comp.molar_mass:.4f} г/моль")
        res.with_step(
            f"Неопределённость: ±{comp.mass_uncertainty:.4f} г/моль "
            f"({comp.mass_uncertainty / comp.molar_mass * 100:.4f} %)")

        if comp.mass_uncertainty > 0:
            res.uncertainty = comp.mass_uncertainty

        # Элементы без стандартной атомной массы
        special = [el for el in comp.elements
                   if not periodic.by_symbol(el).has_standard_mass]
        if special:
            names = ", ".join(f"{el} ({periodic.by_symbol(el).name_ru})"
                              for el in special)
            res.with_warning(
                f"Для элементов {names} стандартной атомной массы нет: "
                f"использована масса наиболее долгоживущего изотопа.")

        # Гидрат
        if "*" in text or "·" in text:
            res.with_step("")
            res.with_step("Состав гидрата:")
            for part, mult in comp.parts:
                try:
                    part_mass = F.molar_mass(part) * mult
                    res.with_step(f"  {mult:g} x {part}: {part_mass:.4f} г/моль")
                except AlchemyError:
                    pass

        mass_text = self.sample_mass.get().strip().replace(",", ".")
        if mass_text:
            try:
                mass = float(mass_text)
            except ValueError:
                res.with_warning(
                    f"Масса навески «{mass_text}» не число — пересчёт в моли "
                    f"не выполнен")
            else:
                moles = mass / comp.molar_mass
                res.with_step("")
                res.with_step(f"Навеска {mass:g} г содержит {moles:.6f} моль")
                res.with_step(
                    f"Число формульных единиц: {moles * 6.02214076e23:.4e}")

        res.with_source("Атомные массы: IUPAC, CIAAW")
        return res


class ThermoTab(BaseTab):
    """Термохимия: тепловой эффект, Гиббс, равновесие, Кирхгоф."""

    title = "Термохимия"
    description = ("Тепловой эффект реакции по справочным данным, энергия "
                   "Гиббса, константа равновесия и температурная зависимость.")
    action_label = "Рассчитать"
    history_action = "Термохимия"

    MODES = [
        "Тепловой эффект реакции",
        "При заданной температуре (закон Кирхгофа)",
        "Константа равновесия реакции",
        "Температура равновесия",
    ]

    def build_inputs(self, parent):
        self.mode = LabeledCombo(parent, "Задача:", self.MODES, width=340)
        parent.layout().addWidget(self.mode)
        self.mode.changed.connect(self._rebuild)

        self.area = QWidget()
        self.area_layout = QVBoxLayout(self.area)
        self.area_layout.setContentsMargins(0, 4, 0, 0)
        self.area_layout.setSpacing(6)
        parent.layout().addWidget(self.area)

        self._rebuild()

    def _rebuild(self):
        _clear_layout(self.area_layout)
        self.fields = {}

        equation = LabeledEntry(
            self.area, "Уравнение реакции", width=430,
            default="CaCO3(тв) = CaO(тв) + CO2")
        self.area_layout.addWidget(equation)
        self.fields["equation"] = equation

        if self.mode.get() in (self.MODES[1], self.MODES[2]):
            temperature = LabeledEntry(
                self.area, "Температура, К", width=120, default="800")
            self.area_layout.addWidget(temperature)
            self.fields["temperature"] = temperature

        note = QLabel(
            "Состояния указывайте явно: H2O(ж), H2O(г), CaCO3(тв). "
            "Данные берутся из справочника, вводить числа не нужно.")
        note.setObjectName("FieldHint")
        note.setWordWrap(True)
        self.area_layout.addWidget(note)

        # новые поля должны ловить Enter
        self._bind_enter()

    def calculate(self) -> Result:
        equation = self.fields["equation"].get().strip()
        if not equation:
            raise AlchemyError("Введите уравнение реакции")

        mode = self.mode.get()

        if mode == self.MODES[1]:
            temperature = self._number("temperature")
            if temperature <= 0:
                raise AlchemyError("Температура должна быть больше нуля")
            return TH.kirchhoff(equation, temperature)

        if mode == self.MODES[2]:
            temperature = self._number("temperature")
            if temperature <= 0:
                raise AlchemyError("Температура должна быть больше нуля")
            enthalpy = TH.reaction_enthalpy(equation).numeric()
            entropy = TH.reaction_entropy(equation).numeric()
            return TH.equilibrium_constant(enthalpy, entropy, temperature)

        if mode == self.MODES[3]:
            return TH.equilibrium_temperature(equation)

        return TH.reaction_enthalpy(equation)

    def _number(self, key: str) -> float:
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            raise AlchemyError(f"Не заполнено поле: {key}")
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")
