"""Дополнительные вкладки Qt-интерфейса. Начато с режима Cantera."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..core.errors import AlchemyError
from ..core.results import Result
from ..engines import cantera_engine as CE
from .components import BaseTab, LabeledCombo, LabeledEntry


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


#: давление в 1 атмосфере, Па — столько подставляем по умолчанию
ONE_ATM = 101325.0

PRESSURE_UNITS = {
    "атм": ONE_ATM,
    "бар": 100000.0,
    "кПа": 1000.0,
    "Па": 1.0,
}


class CanteraTab(BaseTab):
    """Равновесие и горение газовых смесей на Cantera.

    Отдельный режим: работает только если установлена библиотека Cantera.
    Остальные вкладки от неё не зависят.
    """

    title = "Газы: равновесие и горение (Cantera)"
    description = ("Равновесие газовой смеси, адиабатическая температура "
                   "горения, свойства газа и кинетика в реакторе. "
                   "Работает на механизмах Cantera: gri30, h2o2 и других.")
    action_label = "Рассчитать"
    history_action = "Cantera"

    MODES = [
        "Свойства газовой смеси",
        "Равновесие состава",
        "Адиабатическая температура горения",
        "Кинетика в реакторе",
        "Что содержит механизм",
    ]

    MECHANISMS = ["gri30.yaml", "h2o2.yaml", "air.yaml",
                  "nDodecane_Reitz.yaml", "liquidvapor.yaml"]

    def build_inputs(self, parent):
        if not CE.available():
            note = QLabel(
                "Библиотека Cantera не установлена. Установите её командой\n"
                "    python -m pip install cantera\n"
                "и перезапустите программу.")
            note.setObjectName("FieldHint")
            note.setWordWrap(True)
            parent.layout().addWidget(note)
            self.action_button.setEnabled(False)
            return

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
        if not CE.available():
            return
        _clear_layout(self.area_layout)
        self.fields = {}
        mode = self.mode.get()

        mechanism = LabeledCombo(
            self.area, "Механизм", self.MECHANISMS, width=220,
            default="gri30.yaml")
        self.area_layout.addWidget(mechanism)
        self.fields["mechanism"] = mechanism

        if mode == self.MODES[4]:
            self._bind_enter()
            return

        composition = LabeledEntry(
            self.area, "Состав смеси", width=340, default="CH4:1, O2:2, N2:7.52",
            hint="вещество:количество через запятую")
        self.area_layout.addWidget(composition)
        self.fields["composition"] = composition

        temperature = LabeledEntry(
            self.area, "Температура, К", width=120, default="300")
        self.area_layout.addWidget(temperature)
        self.fields["temperature"] = temperature

        pressure = LabeledEntry(
            self.area, "Давление", width=120, default="1")
        self.area_layout.addWidget(pressure)
        self.fields["pressure"] = pressure

        pressure_unit = LabeledCombo(
            self.area, "Единица давления", list(PRESSURE_UNITS), width=120,
            default="атм")
        self.area_layout.addWidget(pressure_unit)
        self.fields["pressure_unit"] = pressure_unit

        if mode == self.MODES[2]:
            adiabatic = LabeledCombo(
                self.area, "Режим равновесия", ["энтальпия и давление",
                                                "температура и давление"],
                width=220, default="энтальпия и давление")
            self.area_layout.addWidget(adiabatic)
            self.fields["hp_mode"] = adiabatic

        if mode == self.MODES[3]:
            time_end = LabeledEntry(
                self.area, "Время расчёта, с", width=120, default="0.01")
            self.area_layout.addWidget(time_end)
            self.fields["time"] = time_end

        note = QLabel(
            "Состав пишется как «CH4:1, O2:2, N2:7.52». Названия веществ "
            "должны быть из выбранного механизма.")
        note.setObjectName("FieldHint")
        note.setWordWrap(True)
        self.area_layout.addWidget(note)

        self._bind_enter()

    # ---------------- расчёт ----------------

    def calculate(self) -> Result:
        if not CE.available():
            raise AlchemyError(
                "Библиотека Cantera не установлена: "
                "python -m pip install cantera")

        mode = self.mode.get()
        mechanism = self.fields["mechanism"].get()

        if mode == self.MODES[4]:
            return CE.mechanism_info(mechanism)

        composition = self.fields["composition"].get().strip()
        temperature = self._number("temperature")
        pressure = self._number("pressure") * PRESSURE_UNITS[
            self.fields["pressure_unit"].get()]

        if mode == self.MODES[0]:
            return CE.gas_properties(mechanism, temperature, pressure,
                                     composition)

        if mode == self.MODES[1]:
            return CE.equilibrium(mechanism, temperature, pressure, composition)

        if mode == self.MODES[2]:
            if self.fields["hp_mode"].get().startswith("энтальпия"):
                return CE.adiabatic_temperature(mechanism, temperature,
                                                pressure, composition)
            return CE.equilibrium(mechanism, temperature, pressure, composition)

        time_end = self._number("time")
        return CE.reactor_kinetics(mechanism, temperature, pressure,
                                   composition, time_end)

    def _number(self, key: str) -> float:
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            raise AlchemyError(f"Не заполнено поле: {key}")
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")
