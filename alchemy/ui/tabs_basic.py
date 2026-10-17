"""Блок «Основные модули»: расчёты, которые нужны каждый день.

Здесь собраны вкладки для базовых задач: молярная масса, стехиометрия,
растворы, кислотно-основные расчёты, газы, термохимия, кинетика,
электрохимия. Каждая вкладка вызывает движок и показывает результат
вместе с ходом расчёта.
"""

from __future__ import annotations

import customtkinter as ctk

from ..core import formula as F
from ..core import periodic
from ..core.errors import AlchemyError
from ..core.results import Result
from ..data import acids as ADB
from ..engines import acidbase as AB
from ..engines import balancer as BAL
from ..engines import electrochemistry as EC
from ..engines import gases as G
from ..engines import kinetics as KIN
from ..engines import solutions as SOL
from ..engines import stoichiometry as ST
from ..engines import thermo as TH
from .components import (
    Card, EditableTable, KeyValueGrid, LabeledCombo, LabeledEntry, BaseTab,
)


# ==========================================================================
# 1. Молярная масса
# ==========================================================================


class MolarMassTab(BaseTab):
    title = "Молярная масса"
    description = ("Расчёт молярной массы и состава вещества. Понимает гидраты "
                   "(CuSO4*5H2O, CuSO4·5H2O), ионы (MnO4-, SO4^2-, SO4{2-}), "
                   "комплексы ([Cu(NH3)4]SO4) и состояния (Fe2O3(тв)).")
    action_label = "Рассчитать"
    history_action = "Молярная масса"

    def build_inputs(self, parent):
        self.formula = LabeledEntry(parent, "Формула", width=280,
                                    hint="например CuSO4*5H2O или MnO4-")
        self.formula.pack(fill="x", pady=4)
        self.formula.entry.insert(0, "CuSO4*5H2O")

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text="Масса навески, г:", font=("Segoe UI", 12),
                     text_color="#e8e8e8").pack(side="left", padx=(0, 8))
        self.sample_mass = ctk.CTkEntry(row, width=120, font=("Consolas", 13))
        self.sample_mass.pack(side="left")
        ctk.CTkLabel(row, text="(необязательно — для пересчёта в моли)",
                     font=("Segoe UI", 10),
                     text_color="#9a9a9a").pack(side="left", padx=8)

        self.build_extra_hint(parent)

    def build_extra_hint(self, parent):
        pass

    def calculate(self) -> Result:
        text = self.formula.get()
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
        res.with_step(f"Заряд: {comp.charge:+d}" if comp.charge else "Заряд: 0 (нейтральная частица)")
        if comp.state:
            res.with_step(f"Агрегатное состояние: {comp.state}")
        res.with_step("")
        res.with_step("Вклад элементов:")
        for el in comp.elements:
            element = periodic.by_symbol(el)
            count = comp.counts[el]
            contribution = element.atomic_mass * count
            percent = comp.mass_percentages[el]
            res.with_step(
                f"  {el}: {count:g} × {element.atomic_mass:.4f} = "
                f"{contribution:.4f} г/моль ({percent:.3f} %)"
            )
        res.with_step("")
        res.with_step(f"Итого: {comp.molar_mass:.4f} г/моль")
        res.with_step(
            f"Неопределённость: ±{comp.mass_uncertainty:.4f} г/моль "
            f"({comp.mass_uncertainty / comp.molar_mass * 100:.4f} %)"
        )

        if comp.mass_uncertainty > 0:
            res.uncertainty = comp.mass_uncertainty

        # Предупреждения о качестве данных
        special = [el for el in comp.elements
                   if not periodic.by_symbol(el).has_standard_mass]
        if special:
            names = ", ".join(f"{el} ({periodic.by_symbol(el).name_ru})"
                              for el in special)
            res.with_warning(
                f"Для элементов {names} стандартной атомной массы нет: "
                f"использована масса наиболее долгоживущего изотопа. "
                f"Молярная масса такого вещества зависит от изотопного состава."
            )

        if "*" in text or "·" in text:
            parts = comp.parts
            res.with_step("")
            res.with_step("Состав гидрата:")
            for part, mult in parts:
                try:
                    M_part = F.molar_mass(part) * mult
                    res.with_step(f"  {mult:g} × {part}: {M_part:.4f} г/моль")
                except AlchemyError:
                    pass
            free = [p for p, m in parts if "H2O" not in p]
            if free:
                try:
                    mass_anhydrous = F.molar_mass(free[0])
                    water_pct = (1 - mass_anhydrous / comp.molar_mass) * 100
                    res.with_step(
                        f"  Массовая доля воды в гидрате: {water_pct:.2f} %"
                    )
                    res.with_meta("water_percent", water_pct)
                    res.with_meta("anhydrous_mass", mass_anhydrous)
                except AlchemyError:
                    pass

        # Пересчёт навески
        mass = self.sample_mass.get().strip()
        if mass:
            try:
                m = float(mass.replace(",", "."))
                n = m / comp.molar_mass
                res.with_step("")
                res.with_step(
                    f"Навеска {m:g} г содержит {n:.6f} моль вещества"
                )
                res.with_step(
                    f"Число формульных единиц: {n * 6.02214076e23:.4e}"
                )
                res.with_meta("moles", n)
            except ValueError:
                res.with_warning(f"Масса навески «{mass}» не распознана как число")

        res.with_meta("composition", comp.as_dict())
        res.with_source("Атомные массы: IUPAC/CIAAW")
        return res


# ==========================================================================
# 2. Анализ формулы
# ==========================================================================


class FormulaAnalysisTab(BaseTab):
    title = "Анализ формулы"
    description = ("Определение простейшей и молекулярной формулы по составу, "
                   "степень ненесыщенности, эквивалентная масса, "
                   "массовые доли элементов.")
    action_label = "Анализировать"
    history_action = "Анализ формулы"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Что известно:",
            ["Массовые доли элементов, %", "Массы элементов, г",
             "Формула — определить состав"],
            width=280,
        )
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda _: self._switch_mode())

        self.mode_hint = ctk.CTkLabel(
            parent, text="", font=("Segoe UI", 10), text_color="#9a9a9a",
            anchor="w", justify="left", wraplength=760)
        self.mode_hint.pack(fill="x", pady=(2, 6))

        self.table = EditableTable(parent, columns=["Элемент", "Значение"],
                                   add_label="Добавить элемент")
        self.table.pack(fill="x", pady=4)

        self.molar_mass_row = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(self.molar_mass_row, text="Молярная масса, г/моль:",
                     font=("Segoe UI", 12), text_color="#e8e8e8").pack(side="left",
                                                                      padx=(0, 8))
        self.molar_mass_entry = ctk.CTkEntry(self.molar_mass_row, width=140,
                                             font=("Consolas", 13))
        self.molar_mass_entry.pack(side="left")
        ctk.CTkLabel(self.molar_mass_row,
                     text="(необязательно — для молекулярной формулы)",
                     font=("Segoe UI", 10), text_color="#9a9a9a").pack(side="left",
                                                                       padx=8)

        self._switch_mode()

    def _switch_mode(self):
        mode = self.mode.get()
        if "доли" in mode:
            self.mode_hint.configure(
                text="Введите элементы и их массовые доли в процентах. "
                     "Сумма не обязана быть ровно 100 — программа нормирует.")
            self.table.columns = ["Элемент", "Массовая доля, %"]
            self.table.reset()
            self.table.add_row(["C", "40.0"])
            self.table.add_row(["H", "6.7"])
            self.table.add_row(["O", "53.3"])
        elif "Массы" in mode:
            self.mode_hint.configure(
                text="Введите элементы и их массы в граммах (из данных анализа).")
            self.table.columns = ["Элемент", "Масса, г"]
            self.table.reset()
            self.table.add_row(["Fe", "69.94"])
            self.table.add_row(["O", "30.06"])
        else:
            self.mode_hint.configure(
                text="Введите формулу — программа покажет состав, массовые доли "
                     "и дополнительную информацию.")
            self.table.columns = ["Формула", "—"]
            self.table.reset()
            self.table.add_row(["CH3COOH", ""])

        # Обновляем заголовки
        for widget in self.table.header.winfo_children():
            widget.destroy()
        for col in self.table.columns:
            ctk.CTkLabel(self.table.header, text=col, font=("Segoe UI", 10),
                         text_color="#9a9a9a", width=150,
                         anchor="w").pack(side="left", padx=4)
        self.molar_mass_row.pack_forget()
        if "Формула" not in self.mode.get():
            self.molar_mass_row.pack(fill="x", pady=4)

    def calculate(self) -> Result:
        mode = self.mode.get()
        rows = self.table.get_rows()

        if not rows:
            raise AlchemyError("Заполните таблицу")

        if "Формула" in mode:
            text = rows[0][0]
            if not text:
                raise AlchemyError("Введите формулу")
            return self._analyze_formula(text)

        values: dict[str, float] = {}
        for row in rows:
            element = row[0].strip()
            if not element:
                continue
            raw = row[1].strip().replace(",", ".")
            if not raw:
                continue
            try:
                values[element] = float(raw)
            except ValueError:
                raise AlchemyError(
                    f"Значение «{row[1]}» для элемента {element} не является числом"
                )

        if len(values) < 2:
            raise AlchemyError("Нужно указать не менее двух элементов")

        if "доли" in mode:
            empirical = F.empirical_formula(percentages=values)
            basis = "массовым долям"
        else:
            empirical = F.empirical_formula(masses=values)
            basis = "массам элементов"

        res = Result(
            value=empirical,
            label=f"Простейшая формула по {basis}",
            method="Деление на атомные массы, нормировка и подбор целых отношений",
        )
        res.with_step("Исходные данные:")
        total = sum(values.values())
        for element, value in values.items():
            try:
                el = periodic.by_symbol(element)
                share = value / total * 100 if "доли" in mode else None
                text = f"  {element} ({el.name_ru}): {value:g}"
                if share is not None:
                    text += f" % (доля {share:.4f} от суммы)"
                res.with_step(text)
            except AlchemyError:
                res.with_step(f"  {element}: {value:g}")

        res.with_step("")
        res.with_step("Пересчёт в моли:")
        moles = {}
        for element, value in values.items():
            el = periodic.by_symbol(element)
            moles[element] = value / el.atomic_mass
            res.with_step(
                f"  n({element}) = {value:g}/{el.atomic_mass:.4f} = "
                f"{moles[element]:.6f} моль"
            )

        min_moles = min(moles.values())
        res.with_step("")
        res.with_step(f"Минимальное количество: {min_moles:.6f} моль")
        res.with_step("Отношения:")
        for element, n in moles.items():
            res.with_step(f"  {element}: {n / min_moles:.4f}")

        res.with_step("")
        res.with_step(f"Простейшая формула: {empirical}")

        # Молекулярная формула
        mm_raw = self.molar_mass_entry.get().strip().replace(",", ".")
        if mm_raw:
            try:
                mm = float(mm_raw)
            except ValueError:
                res.with_warning(f"Молярная масса «{mm_raw}» не распознана")
                mm = None
            if mm:
                try:
                    molecular = F.molecular_formula_from_empirical(empirical, mm)
                    res.with_step(f"Молекулярная формула при M = {mm:g}: {molecular}")
                    res.with_meta("molecular_formula", molecular)
                    res.value = molecular
                    res.label = "Молекулярная формула"
                except AlchemyError as exc:
                    res.with_warning(str(exc))

        # Проверка массы формульной единицы
        mass_of_empirical = F.molar_mass(empirical)
        res.with_step("")
        res.with_step(f"Молярная масса простейшей формулы: {mass_of_empirical:.4f} г/моль")
        res.with_meta("empirical_formula", empirical)
        res.with_meta("empirical_mass", mass_of_empirical)
        return res

    def _analyze_formula(self, text: str) -> Result:
        comp = F.parse(text)

        res = Result(
            value=comp.molar_mass,
            unit="г/моль",
            label=f"Состав {comp.display}",
            method="Расчёт по стандартным атомным массам",
        )
        res.with_step(f"Формула: {comp.display}")
        res.with_step(f"Всего атомов в формульной единице: {comp.total_atoms:g}")
        res.with_step(f"Элементов: {len(comp.elements)}")
        res.with_step("")
        res.with_step("Массовые доли:")
        for element in comp.elements:
            el = periodic.by_symbol(element)
            res.with_step(
                f"  {element} ({el.name_ru}): {comp.counts[element]:g} атомов, "
                f"{comp.mass_percentages[element]:.4f} %"
            )
        res.with_step("")
        res.with_step(f"Молярная масса: {comp.molar_mass:.4f} г/моль")

        du = F.degrees_of_unsaturation(text)
        if du is not None:
            res.with_step("")
            res.with_step(
                f"Число ненасыщенности (индекс дефицита водорода): {du}"
            )
            res.with_step(
                "Каждая единица соответствует либо двойной связи, либо циклу"
            )
            res.with_meta("degrees_of_unsaturation", du)

        try:
            eq2 = F.equivalent_mass(text, 2)
            res.with_step(f"Эквивалентная масса (для двухвалентного обмена): {eq2:.4f} г/моль")
        except AlchemyError:
            pass

        res.with_meta("composition", comp.as_dict())
        return res


# ==========================================================================
# 3. Стехиометрия
# ==========================================================================


class StoichiometryTab(BaseTab):
    title = "Стехиометрия"
    description = ("Расчёт по уравнению реакции: лимитирующий реагент, "
                   "теоретический выход, избыток. Уравнение уравнивается "
                   "автоматически — коэффициенты вводить не нужно.")
    action_label = "Рассчитать"
    history_action = "Стехиометрия"

    def build_inputs(self, parent):
        self.equation = LabeledEntry(
            parent, "Уравнение реакции", width=520,
            hint="например Fe2O3 + CO = Fe + CO2")
        self.equation.pack(fill="x", pady=4)
        self.equation.entry.insert(0, "Fe2O3 + CO = Fe + CO2")

        ctk.CTkLabel(parent, text="Что дано по каждому реагенту:",
                     font=("Segoe UI", 12, "bold"), text_color="#e8e8e8",
                     anchor="w").pack(fill="x", pady=(10, 2))

        self.amount_kind = LabeledCombo(
            parent, "Способ задания:",
            ["Массы, г", "Количества, моль",
             "Объёмы растворов (C·V, моль)", "Объёмы газов при н.у., л"],
            width=260,
        )
        self.amount_kind.pack(fill="x", pady=4)

        self.table = EditableTable(
            parent, columns=["Вещество", "Количество"],
            add_label="Добавить реагент")
        self.table.pack(fill="x", pady=4)
        self.table.reset()
        self.table.add_row(["Fe2O3", "16.0"])
        self.table.add_row(["CO", "10.0"])

        self.extra_hint = ctk.CTkLabel(
            parent, text="", font=("Segoe UI", 10), text_color="#9a9a9a",
            anchor="w", justify="left", wraplength=760)
        self.extra_hint.pack(fill="x", pady=(4, 0))

    def calculate(self) -> Result:
        equation = self.equation.get()
        if not equation:
            raise AlchemyError("Введите уравнение реакции")

        rows = self.table.get_rows()
        if not rows:
            raise AlchemyError("Укажите хотя бы один реагент с количеством")

        kind_map = {
            "Массы, г": "mass",
            "Количества, моль": "moles",
            "Объёмы растворов (C·V, моль)": "solution",
            "Объёмы газов при н.у., л": "volume_l",
        }
        kind = kind_map.get(self.amount_kind.get(), "moles")

        given = []
        for row in rows:
            species = row[0].strip()
            raw = row[1].strip().replace(",", ".") if len(row) > 1 else ""
            if not species and not raw:
                continue
            if not species:
                raise AlchemyError("В одной из строк не указано вещество")
            if not raw:
                raise AlchemyError(f"Не указано количество для {species}")
            try:
                amount = float(raw)
            except ValueError:
                raise AlchemyError(f"Количество «{raw}» для {species} не является числом")
            given.append({"species": species, "amount": amount, "kind": kind})

        if not given:
            raise AlchemyError("Не указано ни одного количества")

        return ST.complex_problem(equation, given)


# ==========================================================================
# 4. Уравнивание реакций
# ==========================================================================


class BalancerTab(BaseTab):
    title = "Уравнивание реакций"
    description = ("Расстановка коэффициентов методом Гаусса в точной "
                   "арифметике. Работает с окислительно-восстановительными "
                   "реакциями и ионными уравнениями с сохранением заряда. "
                   "Заряд понимает и в обычной записи (MnO4-), и с крышкой "
                   "(MnO4^-), и в скобках (MnO4{-}).")
    action_label = "Уравнять"
    history_action = "Уравнивание реакции"

    def build_inputs(self, parent):
        self.equation = LabeledEntry(
            parent, "Реакция", width=560,
            hint="реагенты = продукты")
        self.equation.pack(fill="x", pady=4)
        self.equation.entry.insert(0, "KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O")

        ctk.CTkLabel(
            parent,
            text="Поддерживаются записи: H2 + O2 = H2O,  KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O,\n"
                 "MnO4- + Fe2+ + H+ = Mn2+ + Fe3+ + H2O,  CuSO4*5H2O = CuSO4 + H2O\n"
                 "Заряд можно писать как MnO4-, MnO4^- или MnO4{-} — все три формы равнозначны",
            font=("Segoe UI", 10), text_color="#9a9a9a",
            justify="left", anchor="w").pack(fill="x", pady=(6, 0))

    def build_extra(self, parent):
        card = Card(parent, title="Уравнять несколько реакций сразу",
                    desc="По одной реакции в строке")
        card.pack(fill="x", padx=2, pady=(10, 0))

        self.many_text = ctk.CTkTextbox(card.body, height=110,
                                        font=("Consolas", 12),
                                        fg_color="#2b2b2b", wrap="none")
        self.many_text.pack(fill="x", pady=(0, 8))
        self.many_text.insert("1.0", "N2 + H2 = NH3\nFe + O2 = Fe2O3\n"
                                     "Cr2O7^2- + H^+ + e^- = Cr^3+ + H2O")

        ctk.CTkButton(card.body, text="Уравнять список", width=180,
                      command=self.run_many).pack(anchor="w")

    def calculate(self) -> Result:
        text = self.equation.get()
        if not text:
            raise AlchemyError("Введите уравнение реакции")
        return BAL.balance(text)

    def run_many(self):
        raw = self.many_text.get("1.0", "end").strip()
        if not raw:
            self.result_view.show_error("Введите хотя бы одну реакцию")
            return
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        try:
            result = BAL.balance_many(lines)
        except AlchemyError as exc:
            self.result_view.show_error(str(exc))
            return
        self.result_view.show(result)
        self.log(result)


# ==========================================================================
# 5. Растворы и концентрации
# ==========================================================================


class SolutionTab(BaseTab):
    title = "Растворы и концентрации"
    description = ("Пересчёт между способами выражения концентрации, "
                   "приготовление раствора, разбавление, смешивание. "
                   "Плотность берётся из справочника, а не подставляется "
                   "приближённо.")
    action_label = "Рассчитать"
    history_action = "Растворы"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["Пересчёт концентраций", "Приготовление раствора",
             "Разбавление (C₁V₁ = C₂V₂)", "Смешивание двух растворов",
             "Серийное разбавление", "Концентрация по плотности"],
            width=300,
        )
        self.mode.pack(fill="x", pady=4)

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)

        self.mode.combo.configure(command=lambda _: self._rebuild())
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()

        mode = self.mode.get()
        self.fields: dict[str, ctk.CTkEntry] = {}

        def field(key, label, default="", width=130):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color="#e8e8e8", width=280,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry
            return entry

        if mode == "Пересчёт концентраций":
            field("formula", "Формула вещества", "NaOH")
            self.kind = LabeledCombo(self.area, "Задано:",
                                     ["Массовая доля, %", "Молярность, моль/л",
                                      "Моляльность, моль/кг",
                                      "Массовая концентрация, г/л"],
                                     default="Массовая доля, %", width=240)
            self.kind.pack(fill="x", pady=3)
            field("value", "Значение", "20")
            field("temperature", "Температура, °C", "20")
        elif mode == "Приготовление раствора":
            field("formula", "Формула вещества", "NaCl")
            field("molarity", "Требуемая молярность, моль/л", "0.1")
            field("volume", "Объём колбы, мл", "500")
            field("purity", "Содержание основного вещества, %", "100")
            field("hydrate", "Кристаллизационная вода (число H2O)", "0")
        elif mode == "Разбавление (C₁V₁ = C₂V₂)":
            field("c1", "Исходная концентрация C₁, моль/л", "1.0")
            field("v1", "Объём порции V₁, мл (пусто = найти)", "")
            field("c2", "Конечная концентрация C₂, моль/л", "0.1")
            field("v2", "Конечный объём V₂, мл", "100")
        elif mode == "Смешивание двух растворов":
            field("c1", "Концентрация первого, моль/л", "1.0")
            field("v1", "Объём первого, мл", "100")
            field("c2", "Концентрация второго, моль/л", "0.5")
            field("v2", "Объём второго, мл", "200")
        elif mode == "Серийное разбавление":
            field("c0", "Начальная концентрация, моль/л", "1.0")
            field("transfer", "Объём переноса, мл", "1")
            field("flask", "Объём колбы, мл", "10")
            field("steps", "Число шагов", "3")
        else:
            field("formula", "Формула вещества", "H2SO4")
            field("density", "Измеренная плотность, г/мл", "1.8361")
            field("temperature", "Температура, °C", "20")

    def _num(self, key, required=True):
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            if required:
                raise AlchemyError(f"Не заполнено поле: {key}")
            return None
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def _text(self, key):
        return self.fields[key].get().strip()

    def calculate(self) -> Result:
        mode = self.mode.get()

        if mode == "Пересчёт концентраций":
            return self._convert()
        if mode == "Приготовление раствора":
            return self._recipe()
        if mode == "Разбавление (C₁V₁ = C₂V₂)":
            return self._dilution()
        if mode == "Смешивание двух растворов":
            return self._mixing()
        if mode == "Серийное разбавление":
            return self._serial()
        return self._from_density()

    def _convert(self):
        formula_text = self._text("formula")
        value = self._num("value")
        kind = self.kind.get()
        temperature = self._num("temperature", required=False) or 20.0

        if kind == "Массовая доля, %":
            solution = SOL.from_mass_fraction(
                formula_text, value, solution_mass=100.0,
                temperature_c=temperature)
        elif kind == "Молярность, моль/л":
            solution = SOL.from_molarity(
                formula_text, value, 1.0, temperature_c=temperature)
        elif kind == "Моляльность, моль/кг":
            solution = SOL.from_molality(
                formula_text, value, 1000.0, temperature_c=temperature)
        else:
            solution = SOL.from_mass_concentration(
                formula_text, value, 1.0, temperature_c=temperature)

        res = SOL.describe(solution, label=f"Раствор {formula_text}")
        res.with_step("")
        res.with_step("Пересчёт выполнен строго через массу раствора, "
                      "без приближённых формул вида «молярность = моляльность × плотность»")
        return res

    def _recipe(self):
        formula_text = self._text("formula")
        molarity = self._num("molarity")
        volume = self._num("volume")
        purity = self._num("purity", required=False) or 100.0
        hydrate = self._num("hydrate", required=False) or 0
        return SOL.recipe(formula_text, molarity, volume, purity=purity,
                          hydrate_water=int(hydrate))

    def _dilution(self):
        c1 = self._num("c1", required=False)
        v1 = self._num("v1", required=False)
        c2 = self._num("c2", required=False)
        v2 = self._num("v2", required=False)
        # Объёмы вводились в мл
        v1_l = v1 / 1000.0 if v1 is not None else None
        v2_l = v2 / 1000.0 if v2 is not None else None
        return SOL.dilution(c_initial=c1, v_initial=v1_l,
                            c_final=c2, v_final=v2_l)

    def _mixing(self):
        c1 = self._num("c1")
        v1 = self._num("v1") / 1000.0
        c2 = self._num("c2")
        v2 = self._num("v2") / 1000.0
        return SOL.mixing([
            {"concentration": c1, "volume_l": v1},
            {"concentration": c2, "volume_l": v2},
        ])

    def _serial(self):
        c0 = self._num("c0")
        transfer = self._num("transfer")
        flask = self._num("flask")
        steps = int(self._num("steps"))
        return SOL.serial_dilution(c0, transfer, flask, steps)

    def _from_density(self):
        formula_text = self._text("formula")
        density = self._num("density")
        temperature = self._num("temperature", required=False) or 20.0
        return SOL.concentration_from_density(formula_text, density, temperature)


# ==========================================================================
# 6. Кислоты и основания
# ==========================================================================


class AcidBaseTab(BaseTab):
    title = "Кислоты и основания"
    description = ("pH растворов кислот, оснований и их смесей. Учитываются "
                   "активности ионов, температура и все ступени диссоциации. "
                   "Расчёт идёт из решения уравнения электронейтральности.")
    action_label = "Рассчитать"
    history_action = "pH"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["pH кислоты или основания", "pH соли (гидролиз)",
             "pH смеси кислоты и основания", "Подбор индикатора"],
            width=300,
        )
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda _: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}
        mode = self.mode.get()

        def field(key, label, default="", width=150):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color="#e8e8e8", width=300,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        if mode == "pH кислоты или основания":
            self.substance = LabeledCombo(
                self.area, "Вещество из справочника:",
                [a.formula for a in ADB.all_acids()] + ["— основания —"] +
                [b.formula for b in ADB.all_bases()],
                default="CH3COOH", width=220)
            self.substance.pack(fill="x", pady=3)
            field("concentration", "Концентрация, моль/л", "0.1")
            field("temperature", "Температура, °C", "25")
        elif mode == "pH соли (гидролиз)":
            self.substance = LabeledCombo(
                self.area, "Соль из справочника:",
                [a.formula for a in ADB.all_acids()] + ["— основания —"] +
                [b.formula for b in ADB.all_bases()],
                default="CH3COONa", width=220)
            self.substance.pack(fill="x", pady=3)
            field("concentration", "Концентрация соли, моль/л", "0.1")
            field("temperature", "Температура, °C", "25")
        elif mode == "pH смеси кислоты и основания":
            field("acid", "Кислота (формула)", "CH3COOH")
            field("acid_c", "Концентрация кислоты, моль/л", "0.1")
            field("acid_v", "Объём кислоты, мл", "20")
            field("base", "Основание (формула)", "NaOH")
            field("base_c", "Концентрация основания, моль/л", "0.1")
            field("base_v", "Объём основания, мл", "10")
        else:
            field("acid", "Кислота (формула)", "CH3COOH")
            field("acid_c", "Концентрация кислоты, моль/л", "0.1")
            field("acid_v", "Объём кислоты, мл", "20")
            field("base_c", "Концентрация титранта (NaOH), моль/л", "0.1")

    def _num(self, key, required=True):
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            if required:
                raise AlchemyError(f"Не заполнено поле: {key}")
            return None
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def _text(self, key):
        return self.fields[key].get().strip()

    def calculate(self) -> Result:
        mode = self.mode.get()

        if mode == "pH кислоты или основания":
            return self._ph_substance()
        if mode == "pH соли (гидролиз)":
            return self._salt_hydrolysis()
        if mode == "pH смеси кислоты и основания":
            return self._mixture()
        return self._indicator()

    def _ph_substance(self):
        query = self.substance.get()
        c = self._num("concentration")
        t_c = self._num("temperature", required=False) or 25.0
        t_k = t_c + 273.15

        if ADB.maybe_acid(query) is not None:
            return AB.ph_of_acid(query, c, t_k)
        if ADB.maybe_base(query) is not None:
            return AB.ph_of_base(query, c, t_k)

        # Вещество не в справочнике — пробуем как формулу соли
        raise AlchemyError(
            f"«{query}» нет в справочнике кислот и оснований. "
            f"Для солей выберите задачу «pH соли (гидролиз)»."
        )

    def _salt_hydrolysis(self):
        query = self.substance.get()
        c = self._num("concentration")

        # Соль слабой кислоты или слабого основания: строим равновесие
        from ..core.formula import parse

        ion = ADB.maybe_acid(query)
        if ion is not None:
            # Это кислота в составе соли (например CH3COONa содержит CH3COOH)
            acid = ion
            if acid.is_strong:
                res = Result(value=7.0, label="pH раствора соли сильной кислоты",
                             method="Сильная кислота в составе соли не гидролизуется")
                res.with_step(
                    f"Соль образована сильной кислотой {acid.formula} "
                    f"и сильным основанием — среда нейтральная"
                )
                return res
            # Соль слабой кислоты и сильного основания: гидролиз по аниону
            kb = 1e-14 / acid.Ka
            pkb = -__import__("math").log10(kb)
            # pH = 7 + 0.5·pKa + 0.5·lg C
            import math
            pka = acid.pKa
            ph = 7.0 + 0.5 * pka + 0.5 * math.log10(c)

            res = Result(
                value=ph,
                label=f"pH раствора соли {query}",
                method="Гидролиз по аниону: pH = 7 + ½·pKa + ½·lg C",
            )
            res.with_step(f"Соль образована слабой кислотой {acid.name} "
                          f"и сильным основанием")
            res.with_step(f"pKa({acid.formula}) = {pka:.4f}, "
                          f"pKb сопряжённого основания = {pkb:.4f}")
            res.with_step(f"Концентрация соли: {c:g} моль/л")
            res.with_step(
                f"pH = 7 + 0.5·{pka:.4f} + 0.5·lg({c:g}) = {ph:.4f}"
            )
            res.with_step(f"Гидролиз идёт по аниону: {acid.formula}⁻ + H₂O ⇌ "
                          f"{acid.formula}H + OH⁻")
            res.with_source(ADB.source())
            res.with_assumption(
                "Соль полностью диссоциирована, гидролиз неглубокий. "
                "Для концентрированных растворов нужен расчёт равновесий."
            )
            return res

        base = ADB.maybe_base(query)
        if base is not None:
            import math
            if base.is_strong and base.OH:
                raise AlchemyError(
                    f"{base.formula} — сильное основание, это не соль. "
                    f"Выберите задачу «pH кислоты или основания»."
                )
            # Гидролиз по катиону
            pka_conj = base.pKa_conj
            ph = 7.0 - 0.5 * (14.0 - pka_conj) - 0.5 * math.log10(c)

            res = Result(
                value=ph,
                label=f"pH раствора соли {query}",
                method="Гидролиз по катиону",
            )
            res.with_step(f"Соль образована слабым основанием {base.name}")
            res.with_step(f"pKa сопряжённой кислоты = {pka_conj:.4f}")
            res.with_step(f"pH = {ph:.4f} (среда кислая)")
            res.with_source(ADB.source())
            return res

        raise AlchemyError(
            f"«{query}» не найдено. Выберите кислоту или основание "
            f"из списка — по ним определяется тип гидролиза."
        )

    def _mixture(self):
        acid_query = self._text("acid")
        base_query = self._text("base")
        c_acid = self._num("acid_c")
        v_acid = self._num("acid_v") / 1000.0
        c_base = self._num("base_c")
        v_base = self._num("base_v") / 1000.0

        acid = ADB.find_acid(acid_query)
        base = ADB.find_base(base_query)

        v_total = v_acid + v_base
        if v_total <= 0:
            raise AlchemyError("Суммарный объём должен быть больше нуля")

        c_acid_now = c_acid * v_acid / v_total
        c_base_now = c_base * v_base / v_total

        n_acid = c_acid * v_acid
        n_base = c_base * v_base * max(1, base.OH) if base.is_strong else c_base * v_base

        # Для кислоты с несколькими ступенями берём все pKa
        pka_list = None
        if acid.protons > 1:
            pka_list = AB._related_pka(acid.formula, acid.protons)
        if pka_list is None:
            pka_list = [acid.pKa]

        systems = []
        strong_acid = 0.0
        strong_base = 0.0

        if acid.is_strong:
            strong_acid = c_acid_now
        else:
            systems.append(AB.AcidSystem(acid.formula, c_acid_now, pka_list))

        if base.is_strong:
            strong_base = c_base_now * max(1, base.OH)
        else:
            # Слабое основание эквивалентно добавлению кислоты-сопряжённой
            kb = 10.0 ** (-base.pKb)
            pka_conj = 14.0 - __import__("math").log10(kb) if kb > 0 else 14.0
            systems.append(AB.AcidSystem(base.formula, c_base_now, [pka_conj]))

        eq = AB.solve_acid_base(systems, strong_acid=strong_acid,
                                strong_base=strong_base)

        res = Result(
            value=eq.ph,
            label="pH смеси кислоты и основания",
            method="Решение уравнения электронейтральности с учётом активностей",
        )
        res.with_step(
            f"Кислота: {acid.name}, C = {c_acid:g} моль/л, V = {v_acid * 1000:g} мл "
            f"→ n = {n_acid:.6f} моль"
        )
        res.with_step(
            f"Основание: {base.name}, C = {c_base:g} моль/л, V = {v_base * 1000:g} мл "
            f"→ n = {c_base * v_base:.6f} моль"
        )
        res.with_step(f"После смешивания объём {v_total * 1000:.2f} мл")
        res.with_step(f"Концентрация кислоты: {c_acid_now:.6f} моль/л")
        res.with_step(f"Концентрация основания: {c_base_now:.6f} моль/л")
        res.with_step(f"Ионная сила: {eq.ionic_strength:.6f} моль/л")
        res.with_step(f"[H⁺] = {eq.h_concentration:.6e} моль/л")
        res.with_step(f"pH = {eq.ph:.4f}")

        if eq.fractions:
            res.with_step("")
            res.with_step("Доли форм:")
            for name, value in eq.fractions.items():
                if value > 1e-6:
                    res.with_step(f"  {name}: {value * 100:.3f} %")

        res.with_meta("ionic_strength", eq.ionic_strength)
        res.with_meta("fractions", eq.fractions)
        res.with_meta("ph", eq.ph)
        res.with_source(ADB.source())
        return res

    def _indicator(self):
        acid_query = self._text("acid")
        c_acid = self._num("acid_c")
        v_acid = self._num("acid_v")
        c_base = self._num("base_c")
        return AB.compare_indicators(acid_query, c_acid, v_acid, c_base)


# ==========================================================================
# 7. Буферные растворы
# ==========================================================================


class BufferTab(BaseTab):
    title = "Буферные растворы"
    description = ("pH буферного раствора, буферная ёмкость и расчёт "
                   "приготовления. Уравнение Гендерсона — Хассельбальха "
                   "записано через активности.")
    action_label = "Рассчитать"
    history_action = "Буферный раствор"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["pH буфера по составу", "Буферная ёмкость",
             "Сколько взять для заданного pH"],
            width=280)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda _: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}

        def field(key, label, default="", width=150):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color="#e8e8e8", width=320,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        acids = [a.formula for a in ADB.all_acids() if not a.is_strong][:40]
        self.acid = LabeledCombo(self.area, "Кислота (сопряжённая пара):",
                                 acids, default="CH3COOH", width=220)
        self.acid.pack(fill="x", pady=3)

        mode = self.mode.get()
        if mode == "pH буфера по составу":
            field("c_acid", "Концентрация кислоты, моль/л", "0.1")
            field("c_salt", "Концентрация соли, моль/л", "0.1")
            field("temperature", "Температура, °C", "25")
        elif mode == "Буферная ёмкость":
            field("c_acid", "Концентрация кислоты, моль/л", "0.1")
            field("c_salt", "Концентрация соли, моль/л", "0.1")
            field("temperature", "Температура, °C", "25")
        else:
            field("target_ph", "Требуемый pH", "5.0")
            field("volume", "Объём буфера, л", "1.0")
            field("total_c", "Суммарная концентрация, моль/л", "0.2")

    def _num(self, key, required=True):
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            if required:
                raise AlchemyError(f"Не заполнено поле: {key}")
            return None
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def calculate(self) -> Result:
        mode = self.mode.get()
        acid = self.acid.get()

        if mode == "pH буфера по составу":
            c_acid = self._num("c_acid")
            c_salt = self._num("c_salt")
            t_c = self._num("temperature", required=False) or 25.0
            return AB.buffer_ph(acid, c_acid, c_salt, t_c + 273.15)
        if mode == "Буферная ёмкость":
            c_acid = self._num("c_acid")
            c_salt = self._num("c_salt")
            t_c = self._num("temperature", required=False) or 25.0
            return AB.buffer_capacity(acid, c_acid, c_salt, t_c + 273.15)
        return AB.buffer_preparation(acid, self._num("target_ph"),
                                     self._num("volume"), self._num("total_c"))


# ==========================================================================
# 8. Газовые законы
# ==========================================================================


class GasTab(BaseTab):
    title = "Газовые законы"
    description = ("Уравнение состояния идеального газа, Ван-дер-Ваальса, "
                   "газовые смеси, плотность газа, молекулярно-кинетическая "
                   "теория. Единицы проверяются, а не подставляются вслепую.")
    action_label = "Рассчитать"
    history_action = "Газы"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["Идеальный газ (PV = nRT)", "Реальный газ (Ван-дер-Ваальс)",
             "Объединённый газовый закон", "Смесь газов (закон Дальтона)",
             "Плотность газа и молярная масса",
             "Скорости молекул (МКТ)", "Закон Грэма",
             "Сжимаемость и критические параметры",
             "Стехиометрия газовой реакции"],
            width=320)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda _: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}
        mode = self.mode.get()

        def field(key, label, default="", width=140):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color="#e8e8e8", width=300,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        pressure_units = ["атм", "кПа", "Па", "бар", "мм рт.ст.", "торр"]
        volume_units = ["л", "мл", "м³", "см³"]

        if mode == "Идеальный газ (PV = nRT)":
            field("pressure", "Давление (пусто = найти)", "1.0")
            field("volume", "Объём, л (пусто = найти)", "")
            field("moles", "Количество, моль", "1.0")
            field("temperature", "Температура, °C", "0")
            self.p_unit = LabeledCombo(self.area, "Единица давления:",
                                       pressure_units, default="атм", width=120)
            self.p_unit.pack(fill="x", pady=2)
        elif mode == "Реальный газ (Ван-дер-Ваальс)":
            field("pressure", "Давление, атм (пусто = найти)", "1.0")
            field("volume", "Объём, л", "1.0")
            field("moles", "Количество, моль", "1.0")
            field("temperature", "Температура, К", "300")
            from ..engines.gases import _VDW_TABLE
            self.gas_name = LabeledCombo(self.area, "Газ:", sorted(_VDW_TABLE),
                                         default="CO2", width=140)
            self.gas_name.pack(fill="x", pady=2)
        elif mode == "Объединённый газовый закон":
            field("p1", "P₁, атм", "1.0")
            field("v1", "V₁, л", "10.0")
            field("t1", "T₁, К", "300")
            field("p2", "P₂, атм", "2.0")
            field("v2", "V₂, л (пусто = найти)", "")
            field("t2", "T₂, К", "300")
        elif mode == "Смесь газов (закон Дальтона)":
            ctk.CTkLabel(self.area, text="Состав смеси (газ и масса в граммах):",
                         font=("Segoe UI", 12), text_color="#e8e8e8",
                         anchor="w").pack(fill="x", pady=(4, 2))
            self.table = EditableTable(self.area, columns=["Газ", "Масса, г"],
                                       add_label="Добавить газ")
            self.table.pack(fill="x")
            self.table.reset()
            self.table.add_row(["N2", "79.0"])
            self.table.add_row(["O2", "21.0"])
            field("pressure", "Общее давление, атм (необязательно)", "")
            field("volume", "Объём, л (необязательно)", "")
            field("temperature", "Температура, К (необязательно)", "")
        elif mode == "Плотность газа и молярная масса":
            field("gas", "Газ (формула)", "CO2")
            field("pressure", "Давление, атм", "1.0")
            field("temperature", "Температура, К", "273.15")
        elif mode == "Скорости молекул (МКТ)":
            field("gas", "Газ (формула)", "N2")
            field("temperature", "Температура, К", "298.15")
        elif mode == "Закон Грэма":
            field("gas1", "Первый газ", "H2")
            field("gas2", "Второй газ", "O2")
            field("rate1", "Скорость первого (необязательно)", "")
        elif mode == "Сжимаемость и критические параметры":
            from ..engines.gases import _CRITICAL_TABLE
            self.gas_name = LabeledCombo(self.area, "Газ:",
                                         sorted(_CRITICAL_TABLE),
                                         default="CO2", width=140)
            self.gas_name.pack(fill="x", pady=2)
            field("pressure", "Давление, атм", "30")
            field("temperature", "Температура, К", "300")
        else:
            field("equation", "Уравнение реакции", "N2 + H2 = NH3(г)", width=340)
            field("gas", "Дан газ (формула)", "N2")
            field("volume", "Его объём, л", "10")
            field("target", "Найти газ (необязательно)", "NH3")

    def _num(self, key, required=True):
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            if required:
                raise AlchemyError(f"Не заполнено поле: {key}")
            return None
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def _text(self, key):
        return self.fields[key].get().strip()

    def calculate(self) -> Result:
        mode = self.mode.get()

        if mode == "Идеальный газ (PV = nRT)":
            return G.ideal_gas(
                pressure=self._num("pressure", required=False),
                volume=self._num("volume", required=False),
                moles=self._num("moles", required=False),
                temperature=self._num("temperature", required=False),
                pressure_unit=self.p_unit.get(),
                temperature_unit="°C",
            )
        if mode == "Реальный газ (Ван-дер-Ваальс)":
            return G.van_der_waals(
                pressure=self._num("pressure", required=False),
                volume=self._num("volume", required=False),
                moles=self._num("moles", required=False),
                temperature=self._num("temperature", required=False),
                gas=self.gas_name.get(),
            )
        if mode == "Объединённый газовый закон":
            return G.combined_gas_law(
                p1=self._num("p1", required=False),
                v1=self._num("v1", required=False),
                t1=self._num("t1", required=False),
                p2=self._num("p2", required=False),
                v2=self._num("v2", required=False),
                t2=self._num("t2", required=False),
            )
        if mode == "Смесь газов (закон Дальтона)":
            rows = self.table.get_rows()
            masses = {}
            for row in rows:
                gas = row[0].strip()
                raw = row[1].strip().replace(",", ".") if len(row) > 1 else ""
                if not gas or not raw:
                    continue
                try:
                    masses[gas] = float(raw)
                except ValueError:
                    raise AlchemyError(f"Масса «{raw}» для {gas} не является числом")
            if not masses:
                raise AlchemyError("Заполните состав смеси")

            pressure = self._num("pressure", required=False)
            if pressure is not None:
                return G.dalton_from_masses(masses, total_pressure=pressure)
            volume = self._num("volume", required=False)
            temperature = self._num("temperature", required=False)
            if volume is not None and temperature is not None:
                return G.dalton_from_masses(masses, volume_l=volume,
                                            temperature_k=temperature)
            return G.dalton_from_masses(masses)
        if mode == "Плотность газа и молярная масса":
            return G.gas_density(self._num("pressure"), self._num("temperature"),
                                 self._text("gas"))
        if mode == "Скорости молекул (МКТ)":
            return G.molecular_speeds(self._num("temperature"), self._text("gas"))
        if mode == "Закон Грэма":
            rate1 = self._num("rate1", required=False)
            return G.grahams_law(self._text("gas1"), self._text("gas2"),
                                 rate1=rate1)
        if mode == "Сжимаемость и критические параметры":
            return G.compressibility_factor(self._num("pressure"),
                                            self._num("temperature"),
                                            self.gas_name.get())
        return G.gas_stoichiometry(
            self._text("equation"), self._text("gas"), self._num("volume"),
            target_gas=self._text("target") or None)


# ==========================================================================
# 9. Термохимия
# ==========================================================================


class ThermoTab(BaseTab):
    title = "Термохимия"
    description = ("Тепловой эффект реакции по справочным данным, энергия "
                   "Гиббса, константа равновесия, закон Кирхгофа для "
                   "температурной зависимости.")
    action_label = "Рассчитать"
    history_action = "Термохимия"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["Тепловой эффект реакции (ΔH°, ΔS°, ΔG°)",
             "При заданной температуре (закон Кирхгофа)",
             "Константа равновесия реакции",
             "Температура равновесия",
             "Энергия Гиббса из ЭДС",
             "Калориметрия",
             "Закон Гесса (ручной ввод)",
             "Энергии связей (оценка)",
             "Сравнить несколько реакций"],
            width=340)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda _: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}
        mode = self.mode.get()

        def field(key, label, default="", width=150):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color="#e8e8e8", width=340,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        if mode in ("Тепловой эффект реакции (ΔH°, ΔS°, ΔG°)",
                    "При заданной температуре (закон Кирхгофа)",
                    "Константа равновесия реакции",
                    "Температура равновесия"):
            field("equation", "Уравнение реакции", "CaCO3(тв) = CaO(тв) + CO2",
                  width=440)
            if "Кирхгофа" in mode or "Константа" in mode:
                field("temperature", "Температура, К", "800")
            ctk.CTkLabel(
                self.area,
                text="Состояния указывайте явно: H2O(ж), H2O(г), CaCO3(тв). "
                     "Данные берутся из справочника, вводить числа не нужно.",
                font=("Segoe UI", 10), text_color="#9a9a9a",
                justify="left", anchor="w").pack(fill="x", pady=(6, 0))
        elif mode == "Энергия Гиббса из ЭДС":
            field("emf", "ЭДС, В", "1.10")
            field("n", "Число электронов", "2")
        elif mode == "Калориметрия":
            field("mass", "Масса, г", "100")
            field("heat", "Удельная теплоёмкость, Дж/(г·К)", "4.18")
            field("dt", "Изменение температуры, К", "10")
            field("calorimeter", "Теплоёмкость калориметра, Дж/К", "0")
        elif mode == "Закон Гесса (ручной ввод)":
            ctk.CTkLabel(self.area,
                         text="Стадии: энтальпия (кДж/моль) и множитель "
                              "(отрицательный, если стадию нужно обратить)",
                         font=("Segoe UI", 12), text_color="#e8e8e8",
                         anchor="w").pack(fill="x", pady=(4, 2))
            self.table = EditableTable(self.area,
                                       columns=["ΔH, кДж/моль", "Множитель"],
                                       add_label="Добавить стадию")
            self.table.pack(fill="x")
            self.table.reset()
            self.table.add_row(["-393.51", "1"])
            self.table.add_row(["-285.83", "1"])
            self.table.add_row(["-393.51", "-1"])
        elif mode == "Энергии связей (оценка)":
            field("broken", "Разорванные связи, кДж/моль (через запятую)",
                  "436, 249", width=280)
            field("formed", "Образованные связи, кДж/моль (через запятую)",
                  "926", width=280)
        else:
            ctk.CTkLabel(self.area, text="По одной реакции в строке:",
                         font=("Segoe UI", 12), text_color="#e8e8e8",
                         anchor="w").pack(fill="x", pady=(4, 2))
            self.many_text = ctk.CTkTextbox(self.area, height=100,
                                            font=("Consolas", 12),
                                            fg_color="#2b2b2b", wrap="none")
            self.many_text.pack(fill="x")
            self.many_text.insert(
                "1.0",
                "CaCO3(тв) = CaO(тв) + CO2\n"
                "N2 + H2 = NH3(г)\n"
                "H2 + O2 = H2O(ж)")
            field("temperature", "Температура, К", "298.15")

    def _num(self, key, required=True):
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            if required:
                raise AlchemyError(f"Не заполнено поле: {key}")
            return None
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def calculate(self) -> Result:
        mode = self.mode.get()

        if mode == "Тепловой эффект реакции (ΔH°, ΔS°, ΔG°)":
            return self._full_thermo()
        if mode == "При заданной температуре (закон Кирхгофа)":
            return TH.kirchhoff(self.fields["equation"].get().strip(),
                                self._num("temperature"))
        if mode == "Константа равновесия реакции":
            return TH.equilibrium_constant_from_reaction(
                self.fields["equation"].get().strip(), self._num("temperature"))
        if mode == "Температура равновесия":
            return TH.equilibrium_temperature(self.fields["equation"].get().strip())
        if mode == "Энергия Гиббса из ЭДС":
            return TH.dG_from_emf(self._num("emf"), int(self._num("n")))
        if mode == "Калориметрия":
            return TH.calorimetry(self._num("mass"), self._num("heat"),
                                  self._num("dt"),
                                  self._num("calorimeter", required=False) or 0.0)
        if mode == "Закон Гесса (ручной ввод)":
            rows = self.table.get_rows()
            terms = []
            for row in rows:
                dh_raw = row[0].strip().replace(",", ".") if len(row) > 0 else ""
                f_raw = row[1].strip().replace(",", ".") if len(row) > 1 else "1"
                if not dh_raw:
                    continue
                try:
                    terms.append((float(dh_raw), float(f_raw or 1)))
                except ValueError:
                    raise AlchemyError(f"Не удалось прочитать строку: {row}")
            return TH.hess_law(terms)
        if mode == "Энергии связей (оценка)":
            broken = self._parse_list("broken")
            formed = self._parse_list("formed")
            return TH.bond_energy_estimate(broken, formed)

        raw = self.many_text.get("1.0", "end").strip()
        equations = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not equations:
            raise AlchemyError("Введите хотя бы одну реакцию")
        return TH.compare_reactions(equations, self._num("temperature"))

    def _parse_list(self, key) -> list[float]:
        raw = self.fields[key].get().strip()
        if not raw:
            return []
        result = []
        for chunk in raw.replace(";", ",").split(","):
            chunk = chunk.strip().replace(",", ".")
            if not chunk:
                continue
            try:
                result.append(float(chunk))
            except ValueError:
                raise AlchemyError(f"Не удалось прочитать число «{chunk}»")
        return result

    def _full_thermo(self) -> Result:
        equation = self.fields["equation"].get().strip()
        if not equation:
            raise AlchemyError("Введите уравнение реакции")

        dH = TH.reaction_enthalpy(equation)
        dS = TH.reaction_entropy(equation)
        dG = TH.reaction_gibbs(equation)

        res = Result(
            value=dH.numeric(),
            unit="кДж/моль",
            label="Тепловой эффект реакции ΔH°₂₉₈",
            method="Закон Гесса по стандартным энтальпиям образования",
        )
        for step in dH.steps:
            res.with_step(step)
        res.with_step("")
        res.with_step(f"ΔS° = {dS.numeric():+.4f} Дж/(моль·К)")
        res.with_step(f"ΔG°₂₉₈ = {dG.numeric():+.4f} кДж/моль")
        res.with_step("")
        res.with_step(f"Направление: {dG.meta.get('spontaneity', '—')}")
        res.with_meta("dH", dH.numeric())
        res.with_meta("dS", dS.numeric())
        res.with_meta("dG", dG.numeric())
        res.with_meta("thermal_effect", dH.meta.get("thermal_effect"))

        if dH.has_warnings:
            for w in dH.warnings:
                res.with_warning(w)
        for src in dH.sources:
            res.with_source(src)

        # Дополнительно: температура равновесия, если существует
        try:
            t_eq = TH.equilibrium_temperature(equation)
            if t_eq.value is not None:
                res.with_step(
                    f"Температура равновесия: {t_eq.value:.2f} К "
                    f"({t_eq.value - 273.15:.2f} °C)"
                )
                res.with_meta("T_equilibrium", t_eq.value)
        except AlchemyError:
            pass

        return res


# ==========================================================================
# 10. Химическая кинетика
# ==========================================================================


class KineticsTab(BaseTab):
    title = "Химическая кинетика"
    description = ("Скорость реакции, константа скорости, уравнение Аррениуса, "
                   "период полупревращения, определение порядка реакции по "
                   "опытным данным.")
    action_label = "Рассчитать"
    history_action = "Кинетика"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["Скорость реакции по закону действующих масс",
             "Концентрация через время t",
             "Время достижения концентрации",
             "Период полупревращения",
             "Константа скорости при другой температуре (Аррениус)",
             "Энергия активации по двум точкам",
             "Подгонка параметров Аррениуса по данным",
             "Определение порядка реакции по опытным данным",
             "Параллельные реакции",
             "Последовательные реакции",
             "Обратимая реакция",
             "Влияние катализатора"],
            width=380)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda _: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}
        mode = self.mode.get()

        def field(key, label, default="", width=150):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color="#e8e8e8", width=360,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        if mode == "Скорость реакции по закону действующих масс":
            field("k", "Константа скорости k", "0.01")
            field("orders", "Порядки (вещество=порядок, через запятую)",
                  "A=1, B=1", width=220)
            field("concentrations", "Концентрации (вещество=значение)",
                  "A=1.0, B=2.0", width=220)
        elif mode == "Концентрация через время t":
            self.order = LabeledCombo(self.area, "Порядок реакции:",
                                      ["0", "1", "2"], default="1", width=100)
            self.order.pack(fill="x", pady=2)
            field("k", "Константа скорости k", "0.1")
            field("c0", "Начальная концентрация, моль/л", "1.0")
            field("t", "Время", "10")
        elif mode == "Время достижения концентрации":
            self.order = LabeledCombo(self.area, "Порядок реакции:",
                                      ["0", "1", "2"], default="1", width=100)
            self.order.pack(fill="x", pady=2)
            field("k", "Константа скорости k", "0.1")
            field("c0", "Начальная концентрация, моль/л", "1.0")
            field("ct", "Конечная концентрация, моль/л", "0.5")
        elif mode == "Период полупревращения":
            self.order = LabeledCombo(self.area, "Порядок реакции:",
                                      ["0", "1", "2"], default="1", width=100)
            self.order.pack(fill="x", pady=2)
            field("k", "Константа скорости k", "0.1")
            field("c0", "Начальная концентрация (для порядков 0 и 2)", "1.0")
        elif mode == "Константа скорости при другой температуре (Аррениус)":
            field("k1", "k₁", "1.0")
            field("t1", "T₁, К", "300")
            field("ea", "Энергия активации, кДж/моль", "75")
            field("t2", "T₂, К", "350")
        elif mode == "Энергия активации по двум точкам":
            field("k1", "k₁", "0.001")
            field("t1", "T₁, К", "300")
            field("k2", "k₂", "0.01")
            field("t2", "T₂, К", "320")
        elif mode == "Подгонка параметров Аррениуса по данным":
            ctk.CTkLabel(self.area, text="Опытные точки (T, К и k):",
                         font=("Segoe UI", 12), text_color="#e8e8e8",
                         anchor="w").pack(fill="x", pady=(4, 2))
            self.table = EditableTable(self.area, columns=["T, К", "k"],
                                       add_label="Добавить точку")
            self.table.pack(fill="x")
            self.table.reset()
            for t, k in ((290, "0.00085"), (310, "0.0052"), (330, "0.024"),
                         (350, "0.094"), (370, "0.31")):
                self.table.add_row([str(t), k])
        elif mode == "Определение порядка реакции по опытным данным":
            ctk.CTkLabel(self.area, text="Опытные данные (время и концентрация):",
                         font=("Segoe UI", 12), text_color="#e8e8e8",
                         anchor="w").pack(fill="x", pady=(4, 2))
            self.table = EditableTable(self.area,
                                       columns=["Время", "Концентрация, моль/л"],
                                       add_label="Добавить точку")
            self.table.pack(fill="x")
            self.table.reset()
            for t, c in ((0, "1.000"), (5, "0.779"), (10, "0.607"),
                         (15, "0.472"), (20, "0.368"), (25, "0.287")):
                self.table.add_row([str(t), c])
        elif mode == "Параллельные реакции":
            field("k1", "k₁ (образование B)", "0.1")
            field("k2", "k₂ (образование C)", "0.3")
        elif mode == "Последовательные реакции":
            field("k1", "k₁ (A → B)", "0.1")
            field("k2", "k₂ (B → C)", "0.05")
            field("c0", "Начальная концентрация A, моль/л", "1.0")
        elif mode == "Обратимая реакция":
            field("kf", "k прямая", "0.3")
            field("kr", "k обратная", "0.1")
            field("c0", "Начальная концентрация A, моль/л", "1.0")
        else:
            field("ea1", "Энергия активации без катализатора, кДж/моль", "80")
            field("ea2", "Энергия активации с катализатором, кДж/моль", "60")
            field("temperature", "Температура, К", "298.15")

    def _num(self, key, required=True):
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            if required:
                raise AlchemyError(f"Не заполнено поле: {key}")
            return None
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def _pairs(self, key, name) -> dict[str, float]:
        raw = self.fields[key].get().strip()
        result = {}
        for chunk in raw.replace(";", ",").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "=" not in chunk:
                raise AlchemyError(
                    f"В поле «{name}» ожидается запись вида «A=1.0»: получено «{chunk}»"
                )
            k, _, v = chunk.partition("=")
            try:
                result[k.strip()] = float(v.strip().replace(",", "."))
            except ValueError:
                raise AlchemyError(f"Не удалось прочитать число в «{chunk}»")
        if not result:
            raise AlchemyError(f"Поле «{name}» пустое")
        return result

    def calculate(self) -> Result:
        mode = self.mode.get()

        if mode == "Скорость реакции по закону действующих масс":
            return KIN.rate_law(self._num("k"), self._pairs("concentrations", "концентрации"),
                                self._pairs("orders", "порядки"))
        if mode == "Концентрация через время t":
            return KIN.concentration_at_time(int(self.order.get()), self._num("k"),
                                             self._num("c0"), self._num("t"))
        if mode == "Время достижения концентрации":
            return KIN.time_to_concentration(int(self.order.get()), self._num("k"),
                                             self._num("c0"), self._num("ct"))
        if mode == "Период полупревращения":
            order = int(self.order.get())
            c0 = self._num("c0", required=(order != 1))
            return KIN.half_life(order, self._num("k"), c0)
        if mode == "Константа скорости при другой температуре (Аррениус)":
            return KIN.arrhenius_k2(self._num("k1"), self._num("t1"),
                                    self._num("ea") * 1000.0, self._num("t2"))
        if mode == "Энергия активации по двум точкам":
            return KIN.activation_energy(self._num("k1"), self._num("t1"),
                                         self._num("k2"), self._num("t2"))
        if mode == "Подгонка параметров Аррениуса по данным":
            data = []
            for row in self.table.get_rows():
                if len(row) < 2 or not row[0].strip() or not row[1].strip():
                    continue
                try:
                    data.append((float(row[0].replace(",", ".")),
                                 float(row[1].replace(",", "."))))
                except ValueError:
                    raise AlchemyError(f"Не удалось прочитать точку: {row}")
            return KIN.arrhenius_parameters(data)
        if mode == "Определение порядка реакции по опытным данным":
            times, concs = [], []
            for row in self.table.get_rows():
                if len(row) < 2 or not row[0].strip() or not row[1].strip():
                    continue
                try:
                    times.append(float(row[0].replace(",", ".")))
                    concs.append(float(row[1].replace(",", ".")))
                except ValueError:
                    raise AlchemyError(f"Не удалось прочитать точку: {row}")
            return KIN.determine_order(times, concs)
        if mode == "Параллельные реакции":
            return KIN.parallel_reactions(self._num("k1"), self._num("k2"))
        if mode == "Последовательные реакции":
            return KIN.consecutive_reactions(self._num("k1"), self._num("k2"),
                                             self._num("c0"))
        if mode == "Обратимая реакция":
            return KIN.reversible_first_order(self._num("kf"), self._num("kr"),
                                              self._num("c0"))
        return KIN.catalyst_effect(self._num("ea1") * 1000.0,
                                   self._num("ea2") * 1000.0,
                                   self._num("temperature"))


# ==========================================================================
# 11. Электрохимия
# ==========================================================================


class ElectrochemistryTab(BaseTab):
    title = "Электрохимия"
    description = ("Уравнение Нернста, гальванические элементы, электролиз "
                   "и законы Фарадея. Потенциалы берутся из справочника, "
                   "активности учитываются.")
    action_label = "Рассчитать"
    history_action = "Электрохимия"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["Потенциал электрода (уравнение Нернста)",
             "Гальванический элемент (ЭДС)",
             "Концентрационный элемент",
             "Подобрать окислитель",
             "Электролиз: масса вещества (закон Фарадея)",
             "Электролиз: объём газа",
             "Время электролиза",
             "Выход по току",
             "Продукты электролиза",
             "Коррозионная устойчивость",
             "Диаграмма Пурбе"],
            width=360)
        self.mode.pack(fill="x", pady=4)
        self.mode.combo.configure(command=lambda _: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}
        mode = self.mode.get()
        all_ids = [e.id for e in EC.EDB.all_electrodes()]

        def field(key, label, default="", width=150):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color="#e8e8e8", width=340,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        def combo(key, label, values, default):
            widget = LabeledCombo(self.area, label, values,
                                  default=default, width=220)
            widget.pack(fill="x", pady=2)
            self.combos[key] = widget

        self.combos = {}

        if mode == "Потенциал электрода (уравнение Нернста)":
            combo("electrode", "Полуреакция:", all_ids, "Cu2+/Cu")
            field("activity", "Активность окисленной формы, моль/л", "0.01")
            field("temperature", "Температура, К", "298.15")
        elif mode == "Гальванический элемент (ЭДС)":
            combo("cathode", "Первая полуреакция:", all_ids, "Cu2+/Cu")
            combo("anode", "Вторая полуреакция:", all_ids, "Zn2+/Zn")
            field("c_cathode", "Активность первой, моль/л", "1.0")
            field("c_anode", "Активность второй, моль/л", "1.0")
            field("temperature", "Температура, К", "298.15")
        elif mode == "Концентрационный элемент":
            combo("electrode", "Полуреакция:", all_ids, "Cu2+/Cu")
            field("c1", "Разбавленный раствор, моль/л", "0.001")
            field("c2", "Концентрированный раствор, моль/л", "1.0")
        elif mode == "Подобрать окислитель":
            combo("reductant", "Окисляемое вещество:", all_ids, "Zn2+/Zn")
            field("min_emf", "Минимальная ЭДС, В", "0.5")
        elif mode in ("Электролиз: масса вещества (закон Фарадея)",
                      "Электролиз: объём газа"):
            field("current", "Сила тока, А", "1.0")
            field("time", "Время, с", "3600")
            field("n", "Число электронов", "2")
            if "масса" in mode:
                field("molar_mass", "Молярная масса, г/моль", "63.546")
            else:
                field("temperature", "Температура, К", "298.15")
                field("pressure", "Давление, атм", "1.0")
            field("efficiency", "Выход по току, %", "100")
        elif mode == "Время электролиза":
            field("current", "Сила тока, А", "1.0")
            field("n", "Число электронов", "2")
            field("moles", "Количество вещества, моль", "1.0")
        elif mode == "Выход по току":
            field("actual", "Фактически получено, г", "0.95")
            field("theoretical", "Теоретически, г", "1.1855")
        elif mode == "Продукты электролиза":
            ctk.CTkLabel(self.area,
                         text="Перечислите возможные полуреакции через запятую:",
                         font=("Segoe UI", 12), text_color="#e8e8e8",
                         anchor="w").pack(fill="x", pady=(4, 2))
            field("list", "Полуреакции", "Cu2+/Cu, H+/H2, O2/H2O", width=380)
        elif mode == "Коррозионная устойчивость":
            combo("metal", "Металл:", all_ids, "Fe2+/Fe")
            field("ph", "pH среды", "7.0")
        else:
            combo("element", "Элемент:",
                  list(EC.POURBAIX_SYSTEMS), "Fe")
            field("ph_min", "pH от", "0")
            field("ph_max", "pH до", "14")

    def _num(self, key, required=True):
        raw = self.fields[key].get().strip().replace(",", ".")
        if not raw:
            if required:
                raise AlchemyError(f"Не заполнено поле: {key}")
            return None
        try:
            return float(raw)
        except ValueError:
            raise AlchemyError(f"Значение «{raw}» не является числом")

    def calculate(self) -> Result:
        mode = self.mode.get()

        if mode == "Потенциал электрода (уравнение Нернста)":
            return EC.electrode_potential_electrode(
                self.combos["electrode"].get(), self._num("activity"),
                self._num("temperature"))
        if mode == "Гальванический элемент (ЭДС)":
            return EC.galvanic_cell(
                self.combos["cathode"].get(), self.combos["anode"].get(),
                self._num("c_cathode"), self._num("c_anode"),
                self._num("temperature"))
        if mode == "Концентрационный элемент":
            return EC.concentration_cell(self.combos["electrode"].get(),
                                         self._num("c1"), self._num("c2"))
        if mode == "Подобрать окислитель":
            return EC.find_possible_oxidants(self.combos["reductant"].get(),
                                             self._num("min_emf"))
        if mode == "Электролиз: масса вещества (закон Фарадея)":
            return EC.faraday_mass(self._num("current"), self._num("time"),
                                   int(self._num("n")), self._num("molar_mass"),
                                   self._num("efficiency"))
        if mode == "Электролиз: объём газа":
            return EC.faraday_volume(self._num("current"), self._num("time"),
                                     int(self._num("n")),
                                     self._num("temperature"),
                                     self._num("pressure"),
                                     self._num("efficiency"))
        if mode == "Время электролиза":
            return EC.electrolysis_time(self._num("current"), int(self._num("n")),
                                        moles=self._num("moles"))
        if mode == "Выход по току":
            return EC.current_efficiency(self._num("actual"),
                                         self._num("theoretical"))
        if mode == "Продукты электролиза":
            raw = self.fields["list"].get().strip()
            items = [x.strip() for x in raw.split(",") if x.strip()]
            return EC.electrolysis_products(items)
        if mode == "Коррозионная устойчивость":
            return EC.corrosion_prediction(self.combos["metal"].get(),
                                           self._num("ph"))
        return EC.pourbaix_diagram(self.combos["element"].get(),
                                   self._num("ph_min"), self._num("ph_max"))


# ==========================================================================
# 12. Периодическая таблица
# ==========================================================================


class PeriodicTableTab(BaseTab):
    title = "Периодическая таблица"
    description = ("Все 118 элементов со свойствами, изотопами и электронными "
                   "конфигурациями. Данные из справочника, а не из внешней "
                   "библиотеки — программа работает офлайн.")
    action_label = "Показать элемент"
    history_action = "Периодическая таблица"

    def build_inputs(self, parent):
        self.selector = LabeledCombo(
            parent, "Элемент:",
            [f"{e.z}. {e.symbol} — {e.name_ru}" for e in periodic.all_elements()],
            default="26. Fe — Железо", width=320)
        self.selector.pack(fill="x", pady=4)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text="Атомный номер или символ:", font=("Segoe UI", 12),
                     text_color="#e8e8e8").pack(side="left", padx=(0, 8))
        self.query = ctk.CTkEntry(row, width=140, font=("Consolas", 13))
        self.query.pack(side="left")
        self.query.insert(0, "Fe")

    def build_extra(self, parent):
        card = Card(parent, title="Таблица целиком",
                    desc="Раскладка элементов по группам и периодам")
        card.pack(fill="x", padx=2, pady=(10, 0))

        grid = periodic.grid_layout()
        colors = {e.category: e.category_color for e in periodic.all_elements()}

        holder = ctk.CTkFrame(card.body, fg_color="transparent")
        holder.pack(fill="x")

        for row in grid:
            line = ctk.CTkFrame(holder, fg_color="transparent")
            line.pack(fill="x")
            for element in row:
                if element is None:
                    ctk.CTkLabel(line, text="", width=38, height=30).pack(
                        side="left", padx=1, pady=1)
                else:
                    ctk.CTkButton(
                        line, text=element.symbol, width=38, height=30,
                        fg_color=element.category_color, hover_color="#ffffff",
                        text_color="#111111", font=("Segoe UI", 10, "bold"),
                        command=lambda el=element: self._show_element(el),
                    ).pack(side="left", padx=1, pady=1)

        legend = ctk.CTkFrame(card.body, fg_color="transparent")
        legend.pack(fill="x", pady=(8, 0))
        for category, color in sorted(colors.items()):
            item = ctk.CTkFrame(legend, fg_color="transparent")
            item.pack(side="left", padx=(0, 10))
            ctk.CTkLabel(item, text="■", font=("Segoe UI", 12),
                         text_color=color).pack(side="left")
            ctk.CTkLabel(item, text=f" {category}", font=("Segoe UI", 9),
                         text_color="#9a9a9a").pack(side="left")

    def _show_element(self, element):
        self.selector.set(f"{element.z}. {element.symbol} — {element.name_ru}")
        self.query.delete(0, "end")
        self.query.insert(0, element.symbol)
        self.run()

    def calculate(self) -> Result:
        query = self.query.get().strip()
        element = None

        if query:
            if query.isdigit():
                element = periodic.by_number(int(query))
            else:
                element = periodic.find(query)

        if element is None:
            selection = self.selector.get()
            try:
                z = int(selection.split(".")[0])
                element = periodic.by_number(z)
            except (ValueError, IndexError):
                raise AlchemyError(f"Элемент «{query}» не найден")

        rows = element.pretty_row()
        res = Result(
            value=f"{element.symbol} ({element.name_ru})",
            label=f"Элемент {element.z}: {element.name_ru}",
            method="Справочные данные: mendeleev 1.1.0 (IUPAC, CIAAW)",
        )
        res.kind = "table"

        table_rows = [{"Свойство": k, "Значение": v} for k, v in rows.items()]

        # Изотопы
        isotopes = element.isotopes
        if isotopes:
            res.with_step(f"Всего изотопов в справочнике: {len(isotopes)}")
            stable = element.stable_isotopes
            natural = element.natural_isotopes
            res.with_step(f"Стабильных: {len(stable)}, "
                          f"в природной смеси: {len(natural)}")
            for iso in natural[:12]:
                abundance = f"{iso.abundance * 100:.4f} %" if iso.abundance else "—"
                res.with_step(
                    f"  {element.symbol}-{iso.mass_number}: "
                    f"распространённость {abundance}, "
                    f"масса {iso.mass:.6f} а.е.м."
                )

        # Проверка: средняя масса по изотопам против табличной
        avg = periodic.average_mass_from_isotopes(element.symbol)
        if avg is not None:
            res.with_step("")
            res.with_step(
                f"Проверка: средняя масса по изотопам {avg:.4f} а.е.м. "
                f"против табличной {element.atomic_mass:.4f} а.е.м. "
                f"(расхождение {abs(avg - element.atomic_mass):.4f})"
            )

        if not element.has_standard_mass:
            res.with_warning(
                f"Для {element.name_ru} стандартной атомной массы нет: "
                f"приведена масса наиболее долгоживущего изотопа "
                f"({element.atomic_mass} а.е.м.)"
            )

        res.value = table_rows
        res.meta["columns"] = ["Свойство", "Значение"]
        res.meta["element"] = element.symbol
        return res
