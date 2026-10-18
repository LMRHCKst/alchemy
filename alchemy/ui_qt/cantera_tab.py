"""Вкладка Cantera: отдельный режим для газовых смесей."""

from __future__ import annotations

from ..core.errors import AlchemyError
from ..core.results import Result
from ..engines import cantera_engine as CE
from ..ui.components import BaseTab, LabeledCombo, LabeledEntry
from ..ui.widgets import CTkLabel

#: давление в 1 атмосфере, Па
ONE_ATM = 101325.0

PRESSURE_UNITS = {
    "атм": ONE_ATM,
    "бар": 100000.0,
    "кПа": 1000.0,
    "Па": 1.0,
}


class CanteraTab(BaseTab):
    """Равновесие и горение газовых смесей на Cantera."""

    title = "Газы: равновесие и горение (Cantera)"
    description = ("Равновесие газовой смеси, адиабатическая температура "
                   "горения, свойства газа и кинетика в реакторе. Работает "
                   "на механизмах Cantera: gri30, h2o2 и других.")
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
            CTkLabel(
                parent,
                text="Библиотека Cantera не установлена.\n"
                     "Установите её:  python -m pip install cantera\n"
                     "и перезапустите программу.",
                font=("Segoe UI", 10), text_color="#9a9a9a",
                anchor="w").pack(fill="x")
            return

        self.mode = LabeledCombo(parent, "Задача:", self.MODES, width=340)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda: self._rebuild())

        from ..ui.widgets import CTkFrame

        self.area = CTkFrame(parent, fg_color=None)
        self.area.pack(fill="x", pady=6)

        self._rebuild()

    def _rebuild(self):
        if not CE.available():
            return
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}

        mode = self.mode.get()

        mechanism = LabeledCombo(self.area, "Механизм", self.MECHANISMS,
                                 width=220, default="gri30.yaml")
        mechanism.pack(fill="x", pady=3)
        self.fields["mechanism"] = mechanism

        if mode != self.MODES[4]:
            composition = LabeledEntry(
                self.area, "Состав смеси", width=340,
                default="CH4:1, O2:2, N2:7.52",
                hint="вещество:количество через запятую")
            composition.pack(fill="x", pady=3)
            self.fields["composition"] = composition

            temperature = LabeledEntry(self.area, "Температура, К", width=120,
                                       default="300")
            temperature.pack(fill="x", pady=3)
            self.fields["temperature"] = temperature

            pressure = LabeledEntry(self.area, "Давление", width=120,
                                    default="1")
            pressure.pack(fill="x", pady=3)
            self.fields["pressure"] = pressure

            unit = LabeledCombo(self.area, "Единица давления",
                                list(PRESSURE_UNITS), width=120, default="атм")
            unit.pack(fill="x", pady=3)
            self.fields["pressure_unit"] = unit

        if mode == self.MODES[2]:
            hp_mode = LabeledCombo(
                self.area, "Режим равновесия",
                ["энтальпия и давление", "температура и давление"],
                width=240, default="энтальпия и давление")
            hp_mode.pack(fill="x", pady=3)
            self.fields["hp_mode"] = hp_mode

        if mode == self.MODES[3]:
            time_end = LabeledEntry(self.area, "Время расчёта, с", width=120,
                                    default="0.01")
            time_end.pack(fill="x", pady=3)
            self.fields["time"] = time_end

        CTkLabel(
            self.area,
            text="Состав пишется как «CH4:1, O2:2, N2:7.52». Названия веществ "
                 "должны быть из выбранного механизма.",
            font=("Segoe UI", 9), text_color="#9a9a9a",
            anchor="w", wraplength=760).pack(fill="x", pady=(6, 0))

        self.bind_enter()

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
        pressure = (self._number("pressure")
                    * PRESSURE_UNITS[self.fields["pressure_unit"].get()])

        if mode == self.MODES[0]:
            return CE.gas_properties(mechanism, temperature, pressure,
                                     composition)

        if mode == self.MODES[1]:
            return CE.equilibrium(mechanism, temperature, pressure,
                                  composition)

        if mode == self.MODES[2]:
            if self.fields["hp_mode"].get().startswith("энтальпия"):
                return CE.adiabatic_temperature(mechanism, temperature,
                                                pressure, composition)
            return CE.equilibrium(mechanism, temperature, pressure,
                                  composition)

        return CE.reactor_kinetics(mechanism, temperature, pressure,
                                   composition, self._number("time"))

    def _number(self, key: str) -> float:
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            raise AlchemyError(f"Не заполнено поле: {key}")
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")
