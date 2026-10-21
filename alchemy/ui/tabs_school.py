"""Вкладки школьной программы: 8, 9 и 11 класс.

Степени окисления, электронный баланс, строение вещества, смещение
равновесия, жёсткость воды, качественные реакции, классы веществ.
Органическая химия сюда не входит.
"""

from __future__ import annotations

from . import widgets as ctk

from ..core.errors import AlchemyError
from ..core.results import Result
from ..engines import bonding as B
from ..engines import classification as CL
from ..engines import equilibrium as EQ
from ..engines import hardness as H
from ..engines import oxidation as OX
from ..engines import qualitative as Q
from ..engines import hydrolysis as HD
from ..engines import ioniceq as IE
from ..engines import redox as RX
from ..engines import solubility as SLB
from ..engines import valence as VL
from .components import BaseTab, Card, LabeledCombo, LabeledEntry


def _field(area, fields, key, label, default="", width=220):
    """Поле ввода с подписью, сложенное в словарь fields."""
    widget = LabeledEntry(area, label, width=width, default=default)
    widget.pack(fill="x", pady=3)
    fields[key] = widget
    return widget


# ==========================================================================
# 1. Степени окисления
# ==========================================================================


class OxidationTab(BaseTab):
    """Степени окисления, тип реакции, окислитель и восстановитель."""

    title = "Степени окисления"
    description = ("Степени окисления элементов в формуле, тип химической "
                   "реакции по числу и составу веществ, кто окислитель "
                   "и кто восстановитель.")
    action_label = "Определить"
    history_action = "Степени окисления"

    MODES = ["Степени окисления", "Тип реакции",
             "Окислитель и восстановитель"]

    def build_inputs(self, parent):
        self.mode = LabeledCombo(parent, "Задача:", self.MODES, width=300)
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
            _field(self.area, self.fields, "substance", "Формула вещества",
                   "K2Cr2O7", width=260)
            hint = ("Постоянные степени окисления берутся из правил, "
                    "неизвестная вычисляется по балансу зарядов.")
        elif mode == self.MODES[1]:
            _field(self.area, self.fields, "equation", "Уравнение реакции",
                   "Zn + CuSO4 = ZnSO4 + Cu", width=460)
            hint = ("Четыре типа: соединение, разложение, замещение, обмен.")
        else:
            _field(self.area, self.fields, "equation", "Уравнение реакции",
                   "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O", width=460)
            hint = ("Показывает, какой элемент отдаёт электроны, "
                    "а какой принимает.")

        ctk.CTkLabel(self.area, text=hint, font=("Segoe UI", 10),
                     text_color="#9a9a9a", anchor="w",
                     wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        mode = self.mode.get()
        if mode == self.MODES[0]:
            return OX.oxidation_states(self.fields["substance"].get())
        if mode == self.MODES[1]:
            return OX.reaction_type(self.fields["equation"].get())
        return OX.oxidizer_reducer(self.fields["equation"].get())


# ==========================================================================
# 2. Электронный баланс
# ==========================================================================


class RedoxTab(BaseTab):
    """Уравнивание ОВР методом электронного баланса."""

    title = "Электронный баланс"
    description = ("Уравнивание окислительно-восстановительных реакций "
                   "методом электронного баланса: полуреакции, число "
                   "электронов, множители.")
    action_label = "Уравнять"
    history_action = "Электронный баланс"

    MODES = ["Электронный баланс", "Таблица полуреакций"]

    def build_inputs(self, parent):
        self.mode = LabeledCombo(parent, "Задача:", self.MODES, width=300)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}

        if self.mode.get() == self.MODES[0]:
            _field(self.area, self.fields, "equation", "Уравнение реакции",
                   "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O", width=460)
            ctk.CTkLabel(
                self.area,
                text="Коэффициенты проверяются точным решением системы "
                     "уравнений, поэтому ошибки в подборе исключены.",
                font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w",
                wraplength=760).pack(fill="x", pady=(6, 0))

        self.bind_enter()

    def calculate(self) -> Result:
        if self.mode.get() == self.MODES[1]:
            return RX.half_reactions_table()
        return RX.electron_balance(self.fields["equation"].get())


# ==========================================================================
# 3. Строение вещества
# ==========================================================================


class BondingTab(BaseTab):
    """Тип химической связи и кристаллическая решётка."""

    title = "Строение вещества"
    description = ("Тип химической связи по разнице электроотрицательностей "
                   "и тип кристаллической решётки по составу вещества.")
    action_label = "Определить"
    history_action = "Строение вещества"

    MODES = ["Тип химической связи", "Кристаллическая решётка",
             "Виды связи (таблица)", "Типы решёток (таблица)"]

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

        if self.mode.get() in (self.MODES[0], self.MODES[1]):
            _field(self.area, self.fields, "substance", "Формула вещества",
                   "H2O", width=220)
            ctk.CTkLabel(
                self.area,
                text="Шкала разницы электроотрицательностей: до 0.4 — "
                     "ковалентная неполярная, 0.4–1.7 — полярная, "
                     "больше 1.7 — ионная.",
                font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w",
                wraplength=760).pack(fill="x", pady=(6, 0))

        self.bind_enter()

    def calculate(self) -> Result:
        mode = self.mode.get()
        if mode == self.MODES[0]:
            return B.bond_analysis(self.fields["substance"].get())
        if mode == self.MODES[1]:
            return B.crystal_lattice(self.fields["substance"].get())
        if mode == self.MODES[2]:
            return B.bond_overview()
        return B.lattice_overview()


# ==========================================================================
# 4. Смещение равновесия
# ==========================================================================


class ShiftTab(BaseTab):
    """Смещение химического равновесия по Ле Шателье."""

    title = "Смещение равновесия"
    description = ("Как температура, давление и концентрация влияют "
                   "на положение равновесия. Направление выводится "
                   "из уравнения реакции.")
    action_label = "Показать"
    history_action = "Смещение равновесия"

    def build_inputs(self, parent):
        self.equation = LabeledEntry(
            parent, "Уравнение реакции", width=460,
            default="N2 + 3H2 = 2NH3")
        self.equation.pack(fill="x", pady=4)

        ctk.CTkLabel(
            parent,
            text="Агрегатные состояния влияют на правило давления. "
                 "Указывайте их явно: CO2(г), CaO(тв).",
            font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w",
            wraplength=760).pack(fill="x", pady=(6, 0))

    def calculate(self) -> Result:
        return EQ.equilibrium_shift(self.equation.get())


# ==========================================================================
# 5. Жёсткость воды
# ==========================================================================


class HardnessTab(BaseTab):
    """Жёсткость воды и способы её устранения."""

    title = "Жёсткость воды"
    description = ("Жёсткость по кальцию и магнию, карбонатная "
                   "и некарбонатная, класс жёсткости и масса реагентов "
                   "для умягчения.")
    action_label = "Рассчитать"
    history_action = "Жёсткость воды"

    MODES = ["Жёсткость воды", "Жёсткость от соли", "Классы жёсткости"]

    def build_inputs(self, parent):
        self.mode = LabeledCombo(parent, "Задача:", self.MODES, width=300)
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
            _field(self.area, self.fields, "calcium", "Кальций Ca²⁺, мг/л",
                   "80", width=140)
            _field(self.area, self.fields, "magnesium", "Магний Mg²⁺, мг/л",
                   "24", width=140)
            _field(self.area, self.fields, "hydrocarbonate",
                   "Гидрокарбонат HCO3⁻, мг/л", "122", width=140)
            _field(self.area, self.fields, "volume", "Объём воды, м³", "1",
                   width=140)
        elif mode == self.MODES[1]:
            salts = LabeledCombo(self.area, "Соль",
                                 ["Ca(HCO3)2", "Mg(HCO3)2", "CaSO4", "MgSO4",
                                  "CaCl2", "MgCl2"], width=200,
                                 default="Ca(HCO3)2")
            salts.pack(fill="x", pady=3)
            self.fields["salt"] = salts
            _field(self.area, self.fields, "concentration",
                   "Концентрация соли, мг/л", "162", width=140)

        ctk.CTkLabel(self.area,
                     text="1 °Ж = 1 мг-экв/л = 20.04 мг Ca²⁺/л "
                          "= 12.15 мг Mg²⁺/л",
                     font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w",
                     wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def _number(self, key: str) -> float:
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            raise AlchemyError(f"Не заполнено поле: {key}")
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def calculate(self) -> Result:
        mode = self.mode.get()
        if mode == self.MODES[2]:
            return H.hardness_scale_table()
        if mode == self.MODES[1]:
            return H.hardness_from_salts(self.fields["salt"].get(),
                                         self._number("concentration"))
        return H.water_hardness(
            self._number("calcium"), self._number("magnesium"),
            self._number("hydrocarbonate"), self._number("volume"))


# ==========================================================================
# 6. Определитель ионов
# ==========================================================================


class QualitativeTab(BaseTab):
    """Качественные реакции на ионы."""

    title = "Определитель ионов"
    description = ("Качественные реакции на катионы и анионы: реагент, "
                   "признак, продукт. Поиск по реагенту, по внешнему "
                   "признаку и по иону.")
    action_label = "Показать"
    history_action = "Определитель ионов"

    MODES = ["Все реакции", "Реакции на ион", "По реагенту", "По признаку",
             "Как распознать ион", "Сравнить два иона"]

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

        if mode in (self.MODES[1], self.MODES[4]):
            _field(self.area, self.fields, "ion", "Ион", "SO4^2-", width=200)
        elif mode == self.MODES[2]:
            _field(self.area, self.fields, "reagent", "Реагент", "AgNO3",
                   width=200)
        elif mode == self.MODES[3]:
            _field(self.area, self.fields, "effect", "Что видно",
                   "бурый осадок", width=300)
        elif mode == self.MODES[5]:
            _field(self.area, self.fields, "first", "Первый ион", "Cl-",
                   width=200)
            _field(self.area, self.fields, "second", "Второй ион", "I-",
                   width=200)

        if mode != self.MODES[0]:
            ctk.CTkLabel(
                self.area,
                text="Ион можно писать как SO4^2-, SO4-2 или по названию "
                     "соли. Реагент — как AgNO3.",
                font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w",
                wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        mode = self.mode.get()
        if mode == self.MODES[0]:
            return Q.ions_list()
        if mode == self.MODES[1]:
            return Q.ion_reactions(self.fields["ion"].get())
        if mode == self.MODES[2]:
            return Q.by_reagent(self.fields["reagent"].get())
        if mode == self.MODES[3]:
            return Q.by_effect(self.fields["effect"].get())
        if mode == self.MODES[4]:
            return Q.identify_ion(self.fields["ion"].get())
        return Q.compare_ions(self.fields["first"].get(),
                              self.fields["second"].get())


# ==========================================================================
# 7. Классы веществ и номенклатура
# ==========================================================================


class ClassesTab(BaseTab):
    """Классы неорганических веществ и названия."""

    title = "Классы и названия"
    description = ("К какому классу относится вещество, как оно называется "
                   "по систематической номенклатуре и возможен ли переход "
                   "между классами.")
    action_label = "Определить"
    history_action = "Классы веществ"

    MODES = ["Класс вещества", "Название вещества", "Генетическая связь",
             "Таблица классов"]

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

        if mode in (self.MODES[0], self.MODES[1]):
            _field(self.area, self.fields, "substance", "Формула вещества",
                   "CuSO4", width=220)
        elif mode == self.MODES[2]:
            _field(self.area, self.fields, "first", "Откуда", "CaO", width=180)
            _field(self.area, self.fields, "second", "Куда", "Ca(OH)2",
                   width=180)

        if mode != self.MODES[3]:
            ctk.CTkLabel(
                self.area,
                text="Поддерживаются оксиды, основания, кислоты и соли "
                     "с известным кислотным остатком.",
                font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w",
                wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        mode = self.mode.get()
        if mode == self.MODES[0]:
            return CL.classify(self.fields["substance"].get())
        if mode == self.MODES[1]:
            return CL.name_of(self.fields["substance"].get())
        if mode == self.MODES[2]:
            return CL.genetic_link(self.fields["first"].get(),
                                   self.fields["second"].get())
        return CL.classes_table()


# ==========================================================================
# 8. Валентность
# ==========================================================================


class ValenceTab(BaseTab):
    """Валентность по формуле и формула по валентностям."""

    title = "Валентность"
    description = ("Валентности элементов по формуле бинарного соединения "
                   "и обратная задача: собрать формулу из валентностей.")
    action_label = "Определить"
    history_action = "Валентность"

    MODES = ["Валентность по формуле", "Формула по валентностям"]

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
            _field(self.area, self.fields, "formula", "Формула",
                   "Fe2O3", width=220)
            hint = ("Считается для двух элементов: произведение числа "
                    "атомов на валентность одинаково у обоих.")
        else:
            row = ctk.CTkFrame(self.area, fg_color="transparent")
            row.pack(fill="x", pady=3)
            _field(row, self.fields, "first", "Элемент", "Al", width=120)
            _field(row, self.fields, "valency_first", "Валентность", "3",
                   width=110)
            _field(row, self.fields, "second", "Элемент", "O", width=120)
            _field(row, self.fields, "valency_second", "Валентность", "2",
                   width=110)
            hint = ("Индексы обратны валентностям: Al(III) и O(II) дают "
                    "Al2O3.")

        ctk.CTkLabel(self.area, text=hint, font=("Segoe UI", 10),
                     text_color="#9a9a9a", anchor="w",
                     wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        if self.mode.get() == self.MODES[0]:
            return VL.valences(self.fields["formula"].get())
        return VL.formula_from_valence(
            self.fields["first"].get().strip(),
            int(self.fields["valency_first"].get() or 0),
            self.fields["second"].get().strip(),
            int(self.fields["valency_second"].get() or 0))


# ==========================================================================
# 9. Ионные уравнения
# ==========================================================================


class IonicTab(BaseTab):
    """Молекулярное уравнение превращается в ионное и сокращённое."""

    title = "Ионные уравнения"
    description = ("Из молекулярного уравнения — полное и сокращённое "
                   "ионное. Сильные электролиты записываются ионами, "
                   "слабые и нерастворимые — молекулами.")
    action_label = "Превратить"
    history_action = "Ионные уравнения"

    def build_inputs(self, parent):
        _field(parent, self.fields, "equation", "Молекулярное уравнение",
               "NaOH + HCl = NaCl + H2O", width=520)
        ctk.CTkLabel(
            parent,
            text="Подходят реакции обмена: нейтрализация, осаждение, "
                 "вытеснение слабой кислоты.",
            font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w",
            wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        return IE.ionic_equation(self.fields["equation"].get())


# ==========================================================================
# 10. Гидролиз солей
# ==========================================================================


class HydrolysisTab(BaseTab):
    """Тип гидролиза, среда, константа и степень."""

    title = "Гидролиз солей"
    description = ("Гидролизуется ли соль, по какому иону, какая среда, "
                   "константа и степень гидролиза, pH раствора.")
    action_label = "Рассчитать"
    history_action = "Гидролиз соли"

    def build_inputs(self, parent):
        _field(parent, self.fields, "salt", "Формула соли",
               "Na2CO3", width=240)
        _field(parent, self.fields, "concentration", "Концентрация, моль/л",
               "0.1", width=160)
        ctk.CTkLabel(
            parent,
            text="Если константы слабого электролита нет в справочнике, "
                 "тип гидролиза и среда определяются, а степень и pH — нет.",
            font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w",
            wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        return HD.hydrolysis(self.fields["salt"].get(),
                             float(self.fields["concentration"].get()
                                   .replace(",", ".") or 0.1))


# ==========================================================================
# 11. Растворимость и pH
# ==========================================================================


class SolubilityTab(BaseTab):
    """Растворимость осадков, влияние pH и условия растворения."""

    title = "Растворимость и pH"
    description = ("Растворимость осадка в воде, при заданном pH и обратная "
                   "задача: до какого pH подкислить, чтобы он растворился.")
    action_label = "Рассчитать"
    history_action = "Растворимость"

    MODES = ["В воде", "При заданном pH", "До какого pH растворится"]

    def build_inputs(self, parent):
        self.mode = LabeledCombo(parent, "Задача:", self.MODES, width=340)
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

        _field(self.area, self.fields, "salt", "Формула осадка",
               "CaCO3", width=240)

        if mode == self.MODES[1]:
            _field(self.area, self.fields, "ph", "pH раствора", "5", width=140)
            hint = ("Ионы водорода связывают анион слабой кислоты, "
                    "равновесие сдвигается, растворимость растёт.")
        elif mode == self.MODES[2]:
            _field(self.area, self.fields, "target",
                   "Нужная растворимость, моль/л", "0.01", width=200)
            hint = ("Обратный расчёт: какая доля аниона должна остаться "
                    "непротонированной.")
        else:
            hint = ("Обычная растворимость из произведения растворимости.")

        ctk.CTkLabel(self.area, text=hint, font=("Segoe UI", 10),
                     text_color="#9a9a9a", anchor="w",
                     wraplength=760).pack(fill="x", pady=(6, 0))
        self.bind_enter()

    def calculate(self) -> Result:
        mode = self.mode.get()
        salt = self.fields["salt"].get()
        if mode == self.MODES[1]:
            return SLB.solubility_at_ph(
                salt, float(self.fields["ph"].get().replace(",", ".") or 7))
        if mode == self.MODES[2]:
            return SLB.ph_for_dissolution(
                salt,
                float(self.fields["target"].get().replace(",", ".") or 0.01))
        return SLB.solubility_pure_water(salt)

