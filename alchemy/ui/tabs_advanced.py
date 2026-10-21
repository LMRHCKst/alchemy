"""Блок «Дополнительные модули»: углублённые расчёты и справочные инструменты.

Здесь собрано то, что выходит за рамки базового курса, но нужно студентам
старших курсов, аналитикам и всем, кто работает с реальными системами:
равновесия с активностями, кривые титрования, диаграммы Пурбе, ошибки
измерений, ядерные расчёты, коллигативные свойства.
"""

from __future__ import annotations

import math
from .widgets import filedialog, messagebox

from . import widgets as ctk

from ..core import formula as F
from ..core import periodic
from . import theme
from ..core.errors import AlchemyError
from ..core.results import Result
from ..data import acids as ADB
from ..data import electrodes as EDB
from ..data import solubility as SDB
from ..data import thermo as TDB
from ..data import loader
from ..engines import acidbase as AB
from ..engines import gases as G
from ..engines import electrochemistry as EC
from ..engines import kinetics as KIN
from ..engines import nuclear as NUC
from ..engines import solutions as SOL
from ..engines import stoichiometry as ST
from ..engines import thermo as TH
from ..engines import balancer as BAL
from .components import (
    COLOR_TEXT_DIM, FONT_SMALL,
    Card, EditableTable, KeyValueGrid, LabeledCombo, LabeledEntry, BaseTab,
)


# ==========================================================================
# 1. Равновесия с активностями
# ==========================================================================


class EquilibriumTab(BaseTab):
    title = "Равновесия и активности"
    description = ("Решение уравнения электронейтральности с учётом ионной силы "
                   "и коэффициентов активности. Даёт правильный ответ для "
                   "смесей, амфолитов и концентрированных растворов, где "
                   "обычные формулы pH не работают.")
    action_label = "Решить равновесие"
    history_action = "Равновесие"

    def build_inputs(self, parent):
        ctk.CTkLabel(parent, text="Кислоты в системе (формула, концентрация):",
                     font=("Segoe UI", 12), text_color=theme.COLOR_TEXT,
                     anchor="w").pack(fill="x", pady=(4, 2))

        self.table = EditableTable(parent, columns=["Кислота", "C, моль/л"],
                                   add_label="Добавить кислоту")
        self.table.pack(fill="x")
        self.table.reset()
        self.table.add_row(["H3PO4", "0.1"])

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        for label, key, default in (
            ("Сильная кислота, моль/л", "strong_acid", "0"),
            ("Сильное основание, моль/л", "strong_base", "0"),
            ("Температура, К", "temperature", "298.15"),
        ):
            ctk.CTkLabel(row, text=label + ":", font=("Segoe UI", 12),
                         text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 4))
            entry = ctk.CTkEntry(row, width=90, font=("Consolas", 13))
            entry.pack(side="left", padx=(0, 14))
            entry.insert(0, default)
            setattr(self, key, entry)

        self.use_activity = ctk.CTkCheckBox(
            parent, text="Учитывать коэффициенты активности",
            font=("Segoe UI", 12), text_color=theme.COLOR_TEXT)
        self.use_activity.pack(anchor="w", pady=4)
        self.use_activity.select()

    def calculate(self) -> Result:
        rows = self.table.get_rows()
        systems = []

        for row in rows:
            acid_text = row[0].strip()
            raw = row[1].strip().replace(",", ".") if len(row) > 1 else ""
            if not acid_text or not raw:
                continue
            try:
                c = float(raw)
            except ValueError:
                raise AlchemyError(f"Концентрация «{raw}» не является числом")

            acid = ADB.maybe_acid(acid_text)
            if acid is None:
                raise AlchemyError(
                    f"Кислоты «{acid_text}» нет в справочнике. "
                    f"Доступно {len(ADB.all_acids())} кислот."
                )

            pka_list = AB._related_pka(acid.formula, acid.protons) or [acid.pKa]
            systems.append(AB.AcidSystem(acid.formula, c, pka_list))

        strong_acid = float(self.strong_acid.get().replace(",", ".") or 0)
        strong_base = float(self.strong_base.get().replace(",", ".") or 0)
        t_k = float(self.temperature.get().replace(",", ".") or 298.15)

        if not systems and strong_acid <= 0 and strong_base <= 0:
            raise AlchemyError("Задайте хотя бы одну кислоту или сильный электролит")

        eq = AB.solve_acid_base(
            systems, strong_acid=strong_acid, strong_base=strong_base,
            temperature_k=t_k,
            include_activity=bool(self.use_activity.get()),
        )

        res = Result(
            value=eq.ph,
            label="pH равновесной системы",
            method="Решение уравнения электронейтральности методом бисекции "
                   "с самосогласованным расчётом ионной силы",
        )
        res.with_step(f"Температура: {t_k:g} К, pKw = {ADB.pkw_at(t_k):.4f}")
        if strong_acid:
            res.with_step(f"Сильная кислота: {strong_acid:g} моль/л")
        if strong_base:
            res.with_step(f"Сильное основание: {strong_base:g} моль/л")

        for system in systems:
            res.with_step(
                f"{system.name}: C = {system.total_concentration:g} моль/л, "
                f"ступеней диссоциации {system.n_protons}"
            )

        res.with_step("")
        res.with_step(f"Ионная сила: I = {eq.ionic_strength:.6f} моль/л")
        if eq.gammas:
            res.with_step("Коэффициенты активности:")
            for ion, gamma in list(eq.gammas.items())[:10]:
                res.with_step(f"  γ({ion}) = {gamma:.6f}")
        res.with_step(f"[H⁺] = {eq.h_concentration:.6e} моль/л")
        res.with_step(f"pH = {eq.ph:.4f}")
        res.with_step(f"Итераций поиска решения: {eq.iterations}")

        if eq.fractions:
            res.with_step("")
            res.with_step("Доли форм кислот:")
            for name, value in eq.fractions.items():
                if value > 1e-8:
                    percent = value * 100
                    bar = "█" * max(0, int(percent / 5))
                    res.with_step(f"  {name:24} {percent:7.3f} % {bar}")

        res.with_meta("ionic_strength", eq.ionic_strength)
        res.with_meta("fractions", eq.fractions)
        res.with_meta("gammas", eq.gammas)
        res.with_meta("iterations", eq.iterations)
        res.with_source(ADB.source())

        if not self.use_activity.get():
            res.with_warning(
                "Расчёт без учёта активностей: для концентраций выше 0.01 моль/л "
                "результат заметно отличается от реального"
            )
        return res


# ==========================================================================
# 2. Кривые титрования
# ==========================================================================


class TitrationTab(BaseTab):
    title = "Кривые титрования"
    description = ("Кривая титрования строится из решения равновесий в каждой "
                   "точке, а не по зашитым формулам. Указываются объём "
                   "эквивалентности, скачок и подходящий индикатор.")
    action_label = "Построить кривую"
    history_action = "Титрование"

    def build_inputs(self, parent):
        self.acid = LabeledCombo(
            parent, "Титруемая кислота:",
            [a.formula for a in ADB.all_acids()],
            default="CH3COOH", width=200)
        self.acid.pack(fill="x", pady=4)

        row1 = ctk.CTkFrame(parent, fg_color="transparent")
        row1.pack(fill="x", pady=3)
        for label, key, default in (
            ("Концентрация кислоты, моль/л", "c_acid", "0.1"),
            ("Объём аликвоты, мл", "v_acid", "20"),
        ):
            ctk.CTkLabel(row1, text=label + ":", font=("Segoe UI", 12),
                         text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 4))
            entry = ctk.CTkEntry(row1, width=100, font=("Consolas", 13))
            entry.pack(side="left", padx=(0, 16))
            entry.insert(0, default)
            setattr(self, key, entry)

        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", pady=3)
        for label, key, default in (
            ("Концентрация титранта (NaOH), моль/л", "c_base", "0.1"),
            ("Точек на кривой", "points", "80"),
        ):
            ctk.CTkLabel(row2, text=label + ":", font=("Segoe UI", 12),
                         text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 4))
            entry = ctk.CTkEntry(row2, width=100, font=("Consolas", 13))
            entry.pack(side="left", padx=(0, 16))
            entry.insert(0, default)
            setattr(self, key, entry)

    def calculate(self) -> Result:
        def num(entry, name):
            raw = entry.get().strip().replace(",", ".")
            if not raw:
                raise AlchemyError(f"Не заполнено поле: {name}")
            try:
                return float(raw)
            except ValueError:
                raise AlchemyError(f"Значение «{raw}» не является числом")

        return AB.titration_curve(
            self.acid.get(), num(self.c_acid, "концентрация кислоты"),
            num(self.v_acid, "объём аликвоты"),
            num(self.c_base, "концентрация титранта"),
            points=int(num(self.points, "число точек")),
        )


# ==========================================================================
# 3. Подбор индикатора
# ==========================================================================


class IndicatorTab(BaseTab):
    title = "Подбор индикатора"
    description = ("Систематическая погрешность титрования из-за индикатора "
                   "рассчитывается количественно: сравнивается объём титранта "
                   "при pH перехода индикатора с объёмом эквивалентности.")
    action_label = "Подобрать индикатор"
    history_action = "Подбор индикатора"

    def build_inputs(self, parent):
        self.acid = LabeledCombo(
            parent, "Кислота:", [a.formula for a in ADB.all_acids()],
            default="CH3COOH", width=200)
        self.acid.pack(fill="x", pady=4)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        for label, key, default in (
            ("C кислоты, моль/л", "c_acid", "0.1"),
            ("V аликвоты, мл", "v_acid", "20"),
            ("C титранта, моль/л", "c_base", "0.1"),
        ):
            ctk.CTkLabel(row, text=label + ":", font=("Segoe UI", 12),
                         text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 4))
            entry = ctk.CTkEntry(row, width=90, font=("Consolas", 13))
            entry.pack(side="left", padx=(0, 14))
            entry.insert(0, default)
            setattr(self, key, entry)

    def calculate(self) -> Result:
        def num(entry, name):
            raw = entry.get().strip().replace(",", ".")
            if not raw:
                raise AlchemyError(f"Не заполнено поле: {name}")
            try:
                return float(raw)
            except ValueError:
                raise AlchemyError(f"Значение «{raw}» не является числом")

        return AB.compare_indicators(self.acid.get(), num(self.c_acid, "C"),
                                     num(self.v_acid, "V"), num(self.c_base, "C"))


# ==========================================================================
# 4. Коллигативные свойства
# ==========================================================================


class ColligativeTab(BaseTab):
    title = "Коллигативные свойства"
    description = ("Понижение температуры замерзания, повышение температуры "
                   "кипения, осмотическое давление. Фактор Вант-Гоффа "
                   "учитывается — для электролитов он удваивает эффект.")
    action_label = "Рассчитать"
    history_action = "Коллигативные свойства"

    def build_inputs(self, parent):
        self.solvent = LabeledCombo(
            parent, "Растворитель:",
            [s.name for s in SDB.all_solvents()], default="Вода", width=200)
        self.solvent.pack(fill="x", pady=4)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text="Моляльность, моль/кг:", font=("Segoe UI", 12),
                     text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 4))
        self.molality = ctk.CTkEntry(row, width=100, font=("Consolas", 13))
        self.molality.pack(side="left", padx=(0, 16))
        self.molality.insert(0, "0.5")

        ctk.CTkLabel(row, text="Фактор Вант-Гоффа i:", font=("Segoe UI", 12),
                     text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 4))
        self.i_entry = ctk.CTkEntry(row, width=80, font=("Consolas", 13))
        self.i_entry.pack(side="left")
        self.i_entry.insert(0, "2.0")

        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", pady=3)
        ctk.CTkLabel(row2, text="Молярность для осмоса, моль/л:",
                     font=("Segoe UI", 12), text_color=theme.COLOR_TEXT).pack(side="left",
                                                                      padx=(0, 4))
        self.molarity = ctk.CTkEntry(row2, width=100, font=("Consolas", 13))
        self.molarity.pack(side="left", padx=(0, 16))
        self.molarity.insert(0, "0.48")

        ctk.CTkLabel(row2, text="Температура, К:", font=("Segoe UI", 12),
                     text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 4))
        self.temperature = ctk.CTkEntry(row2, width=80, font=("Consolas", 13))
        self.temperature.pack(side="left")
        self.temperature.insert(0, "298.15")

    def build_extra(self, parent):
        card = Card(parent, title="Определение молярной массы по криоскопии",
                    desc="Метод, который используют в лабораторной практике")
        card.pack(fill="x", padx=2, pady=(10, 0))

        grid = KeyValueGrid(card.body, [
            ("dt", "Понижение T замерзания, К", "0.31"),
            ("m_solute", "Масса вещества, г", "1.0"),
            ("m_solvent", "Масса растворителя, г", "100"),
            ("i", "Фактор Вант-Гоффа", "1"),
        ], columns=2)
        grid.pack(fill="x")
        self.cryo = grid

        ctk.CTkButton(card.body, text="Рассчитать молярную массу", width=220,
                      command=self.run_cryo).pack(anchor="w", pady=(8, 0))

    def run_cryo(self):
        try:
            result = SOL.molar_mass_from_freezing(
                self.solvent.get(), self.cryo.value("dt"),
                self.cryo.value("m_solute"), self.cryo.value("m_solvent"),
                float(self.cryo.get("i") or 1))
        except AlchemyError as exc:
            self.result_view.show_error(str(exc))
            return
        self.result_view.show(result)
        self.log(result)

    def calculate(self) -> Result:
        molality = float(self.molality.get().replace(",", ".") or 0)
        i = float(self.i_entry.get().replace(",", ".") or 1)
        molarity = float(self.molarity.get().replace(",", ".") or 0)
        t_k = float(self.temperature.get().replace(",", ".") or 298.15)

        return SOL.colligative_report(self.solvent.get(), molality, i,
                                      temperature_k=t_k, molarity=molarity)


# ==========================================================================
# 5. Обработка кинетических данных
# ==========================================================================


class KineticsDataTab(BaseTab):
    title = "Обработка кинетических данных"
    description = ("Определение порядка реакции и константы скорости по "
                   "экспериментальным точкам. Проверяются три модели, "
                   "выбирается лучшая по коэффициенту детерминации.")
    action_label = "Обработать данные"
    history_action = "Кинетика: обработка данных"

    def build_inputs(self, parent):
        ctk.CTkLabel(parent,
                     text="Введите опытные точки: время и концентрация.",
                     font=("Segoe UI", 12), text_color=theme.COLOR_TEXT,
                     anchor="w").pack(fill="x", pady=(4, 2))

        self.table = EditableTable(parent,
                                   columns=["Время", "Концентрация, моль/л"],
                                   add_label="Добавить точку")
        self.table.pack(fill="x")
        self.table.reset()
        for t, c in ((0, "1.000"), (5, "0.779"), (10, "0.607"),
                     (15, "0.472"), (20, "0.368"), (25, "0.287")):
            self.table.add_row([str(t), c])

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text="Начальная концентрация C₀, моль/л "
                               "(пусто — взять первую точку):",
                     font=("Segoe UI", 12), text_color=theme.COLOR_TEXT).pack(side="left")
        self.c0_entry = ctk.CTkEntry(row, width=100, font=("Consolas", 13))
        self.c0_entry.pack(side="left", padx=8)

    def build_extra(self, parent):
        card = Card(parent, title="Дополнительно: подгонка Аррениуса",
                    desc="Введите пары «температура — константа скорости»")
        card.pack(fill="x", padx=2, pady=(10, 0))

        self.arr_table = EditableTable(card.body, columns=["T, К", "k"],
                                       add_label="Добавить точку")
        self.arr_table.pack(fill="x")
        for t, k in ((290, "0.00085"), (310, "0.0052"), (330, "0.024"),
                     (350, "0.094"), (370, "0.31")):
            self.arr_table.add_row([str(t), k])

        ctk.CTkButton(card.body, text="Подогнать Аррениуса", width=220,
                      command=self.run_arrhenius).pack(anchor="w", pady=(8, 0))

    def run_arrhenius(self):
        data = []
        for row in self.arr_table.get_rows():
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                continue
            try:
                data.append((float(row[0].replace(",", ".")),
                             float(row[1].replace(",", "."))))
            except ValueError:
                self.result_view.show_error(f"Не удалось прочитать точку: {row}")
                return
        try:
            result = KIN.arrhenius_parameters(data)
        except AlchemyError as exc:
            self.result_view.show_error(str(exc))
            return
        self.result_view.show(result)
        self.log(result)

    def calculate(self) -> Result:
        times, concs = [], []
        for row in self.table.get_rows():
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                continue
            try:
                times.append(float(row[0].replace(",", ".")))
                concs.append(float(row[1].replace(",", ".")))
            except ValueError:
                raise AlchemyError(f"Не удалось прочитать точку: {row}")

        c0_raw = self.c0_entry.get().strip().replace(",", ".")
        c0 = float(c0_raw) if c0_raw else None
        return KIN.determine_order(times, concs, c0)


# ==========================================================================
# 6. Электролиз: подробный расчёт
# ==========================================================================


class ElectrolysisTab(BaseTab):
    title = "Расчёт электролиза"
    description = ("Полный расчёт процесса электролиза: продукты на электродах, "
                   "напряжение разложения, масса и объём продуктов, время "
                   "процесса и расход электроэнергии.")
    action_label = "Рассчитать электролиз"
    history_action = "Электролиз"

    def build_inputs(self, parent):
        ctk.CTkLabel(parent,
                     text="Возможные полуреакции (по одной в строке):",
                     font=("Segoe UI", 12), text_color=theme.COLOR_TEXT,
                     anchor="w").pack(fill="x", pady=(4, 2))

        self.text = ctk.CTkTextbox(parent, height=110, font=("Consolas", 12),
                                   fg_color=theme.COLOR_CARD_ALT, wrap="none")
        self.text.pack(fill="x")
        self.text.insert("1.0", "Cu2+/Cu\nH+/H2\nO2/H2O")

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        for label, key, default in (
            ("Сила тока, А", "current", "5"),
            ("Время, мин", "time_min", "30"),
            ("Выход по току, %", "efficiency", "95"),
            ("Температура, К", "temperature", "298.15"),
        ):
            ctk.CTkLabel(row, text=label + ":", font=("Segoe UI", 12),
                         text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 4))
            entry = ctk.CTkEntry(row, width=80, font=("Consolas", 13))
            entry.pack(side="left", padx=(0, 12))
            entry.insert(0, default)
            setattr(self, key, entry)

        ctk.CTkLabel(parent,
                     text="Доступные обозначения полуреакций: " +
                          ", ".join(e.id for e in EDB.all_electrodes()[:14]) + "...",
                     font=("Segoe UI", 10), text_color=theme.COLOR_TEXT_DIM,
                     justify="left", anchor="w", wraplength=760).pack(fill="x")

    def calculate(self) -> Result:
        raw = self.text.get("1.0", "end").strip()
        identifiers = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(identifiers) < 2:
            raise AlchemyError("Укажите не менее двух полуреакций")

        for ident in identifiers:
            if EDB.maybe(ident) is None:
                raise AlchemyError(
                    f"Полуреакция «{ident}» не найдена. "
                    f"Используйте обозначения вида Cu2+/Cu, H+/H2"
                )

        def num(entry, name):
            raw_value = entry.get().strip().replace(",", ".")
            if not raw_value:
                raise AlchemyError(f"Не заполнено поле: {name}")
            try:
                return float(raw_value)
            except ValueError:
                raise AlchemyError(f"Значение «{raw_value}» не является числом")

        current = num(self.current, "сила тока")
        time_s = num(self.time_min, "время") * 60.0
        efficiency = num(self.efficiency, "выход по току")
        t_k = num(self.temperature, "температура")

        products = EC.electrolysis_products(identifiers, t_k)
        cathode = EDB.find(products.meta["cathode"])
        anode = EDB.find(products.meta["anode"])

        res = Result(
            value=products.numeric(),
            unit="В",
            label="Минимальное напряжение разложения",
            method="Разность потенциалов наиболее выгодных полуреакций "
                   "с поправкой Нернста",
        )
        for step in products.steps:
            res.with_step(step)
        res.with_step("")
        res.with_step(f"Режим: I = {current:g} А, t = {time_s / 60:.2f} мин, "
                      f"выход по току {efficiency:g} %")

        charge = current * time_s
        res.with_step(f"Заряд: Q = {charge:.2f} Кл = {charge / 3600:.4f} А·ч")
        res.with_step(f"Количество электронов: {charge / 96485.33212:.6f} моль")

        # Масса продукта на катоде
        rows = []
        for name, electrode in (("Катод", cathode), ("Анод", anode)):
            formula_text = _formula_from_half_reaction(electrode.half_reaction)
            if formula_text is None:
                continue
            try:
                M = F.molar_mass(formula_text)
            except AlchemyError:
                continue
            mass = charge * M / (electrode.n * 96485.33212) * efficiency / 100.0
            rows.append({
                "Электрод": name,
                "Полуреакция": electrode.id,
                "Вещество": formula_text,
                "Молярная масса": round(M, 4),
                "Число электронов": electrode.n,
                "Масса, г": round(mass, 6),
            })
            res.with_step(
                f"{name}: {electrode.id} → {formula_text}, "
                f"M = {M:.4f} г/моль, n = {electrode.n}"
            )
            res.with_step(
                f"  m = Q·M/(n·F)·η = {charge:.2f}·{M:.4f}/"
                f"({electrode.n}·96485.33212)·{efficiency / 100:g} = {mass:.6f} г"
            )

        res.with_meta("products_table", rows)
        res.with_meta("charge_c", charge)
        res.with_meta("cathode", cathode.id)
        res.with_meta("anode", anode.id)
        res.with_source(EDB.source())

        # Расход энергии
        voltage = products.numeric()
        practical_voltage = voltage + 0.5   # перенапряжение
        energy = practical_voltage * charge / 1000.0
        res.with_step("")
        res.with_step(
            f"Расход электроэнергии при практическом напряжении "
            f"{practical_voltage:.2f} В (с учётом перенапряжения около 0.5 В): "
            f"{energy:.4f} кДж = {energy / 3600:.6f} кВт·ч"
        )
        res.with_meta("energy_kj", energy)
        res.with_meta("practical_voltage", practical_voltage)

        if rows:
            res.with_meta("masses", {r["Электрод"]: r["Масса, г"] for r in rows})

        res.with_assumption(
            "Перенапряжение принято 0.5 В — это ориентировочная величина. "
            "Реальное значение зависит от материала электрода, плотности тока "
            "и температуры."
        )
        return res


def _formula_from_half_reaction(half_reaction: str) -> str | None:
    """Извлечь формулу продукта из записи полуреакции.

    Для «Cu2+ + 2e- -> Cu» это Cu, для «2H+ + 2e- -> H2» это H2.
    """
    if "->" not in half_reaction:
        return None
    _, _, right = half_reaction.partition("->")
    # Берём первый продукт
    for chunk in right.split("+"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Убираем коэффициент
        i = 0
        while i < len(chunk) and (chunk[i].isdigit() or chunk[i] == "."):
            i += 1
        body = chunk[i:].strip()
        if body and body[0].isupper():
            try:
                F.parse(body)
                return body
            except AlchemyError:
                continue
    return None


# ==========================================================================
# 7. Ядерная химия
# ==========================================================================


class NuclearTab(BaseTab):
    title = "Ядерная химия"
    description = ("Радиоактивный распад, активность, энергия связи ядра, "
                   "энергетический выход ядерных реакций, цепочки распада, "
                   "дозовые величины.")
    action_label = "Рассчитать"
    history_action = "Ядерная химия"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["Распад за время t",
             "Время до заданного количества",
             "Постоянная распада по периоду полураспада",
             "Активность образца",
             "Масса по активности",
             "Перевод единиц активности",
             "Энергия связи ядра",
             "Энергия ядерной реакции",
             "Цепочка распада",
             "Распад реального нуклида",
             "Свойства нуклида",
             "Природные ряды",
             "Вековое равновесие",
             "Дозиметрия"],
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
        time_units = ["с", "мин", "ч", "сут", "год", "тыс. лет", "млн лет"]

        def field(key, label, default="", width=150):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color=theme.COLOR_TEXT, width=330,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        if mode == "Распад за время t":
            field("n0", "Начальное количество", "100")
            field("half_life", "Период полураспада", "10")
            self.t_unit = LabeledCombo(self.area, "Единица времени:",
                                       time_units, default="сут", width=120)
            self.t_unit.pack(fill="x", pady=2)
            field("time", "Прошло времени", "30")
        elif mode == "Время до заданного количества":
            field("n0", "Начальное количество", "100")
            field("target", "Целевое количество", "5")
            field("half_life", "Период полураспада", "10")
            self.t_unit = LabeledCombo(self.area, "Единица времени:",
                                       time_units, default="сут", width=120)
            self.t_unit.pack(fill="x", pady=2)
        elif mode == "Постоянная распада по периоду полураспада":
            field("half_life", "Период полураспада", "1600")
            self.t_unit = LabeledCombo(self.area, "Единица времени:",
                                       time_units, default="год", width=120)
            self.t_unit.pack(fill="x", pady=2)
        elif mode == "Активность образца":
            field("moles", "Количество вещества, моль", "0.0044248")
            field("half_life", "Период полураспада, с", "5.05e10")
            field("name", "Название нуклида (для подписи)", "Ra-226")
        elif mode == "Масса по активности":
            field("activity", "Активность, Бк", "1000000")
            field("half_life", "Период полураспада, с", "5.05e10")
            field("molar_mass", "Молярная масса, г/моль", "226")
        elif mode == "Перевод единиц активности":
            field("value", "Значение", "1")
            self.from_unit = LabeledCombo(self.area, "Из единицы:",
                                          list(NUC.ACTIVITY_UNITS),
                                          default="Ки", width=140)
            self.from_unit.pack(fill="x", pady=2)
            self.to_unit = LabeledCombo(self.area, "В единицу:",
                                        list(NUC.ACTIVITY_UNITS),
                                        default="Бк", width=140)
            self.to_unit.pack(fill="x", pady=2)
        elif mode == "Энергия связи ядра":
            field("nuclide", "Нуклид", "Fe-56", width=140)
        elif mode == "Энергия ядерной реакции":
            field("reactants", "Реагенты (через запятую)", "U-235, n", width=280)
            field("products", "Продукты (через запятую)",
                  "Ba-141, Kr-92, n, n, n", width=280)
        elif mode == "Цепочка распада":
            field("n0", "Начальное количество", "100")
            field("half_lives", "Периоды полураспада (через запятую)",
                  "10, 5, 2", width=240)
            field("time", "Время", "20")
        elif mode == "Распад реального нуклида":
            field("nuclide", "Нуклид (например Co-60)", "Co-60")
            field("amount", "Начальное количество", "1e20")
            self.amount_unit = LabeledCombo(
                self.area, "Что задано:",
                ["атомов", "Бк"], default="атомов", width=140)
            self.amount_unit.pack(fill="x", pady=2)
            self.decay_unit = LabeledCombo(
                self.area, "Единица времени:",
                ["с", "мин", "ч", "сут", "год"], default="год", width=140)
            self.decay_unit.pack(fill="x", pady=2)
            field("time", "Время выдержки", "5.271")
        elif mode == "Свойства нуклида":
            field("nuclide", "Нуклид (например Co-60)", "Co-60")
        elif mode == "Природные ряды":
            self.series = LabeledCombo(
                self.area, "Ряд:",
                ["все три"] + list(NUC.NATURAL_SERIES), default="все три",
                width=260)
            self.series.pack(fill="x", pady=2)
        elif mode == "Вековое равновесие":
            field("parent", "Период полураспада материнского", "1600")
            field("daughter", "Период полураспада дочернего", "3.82")
            field("activity", "Активность материнского, Бк", "3.7e10")
        else:
            field("dose", "Поглощённая доза, Гр", "0.001")
            self.radiation = LabeledCombo(
                self.area, "Тип излучения:",
                ["gamma", "beta", "alpha", "нейтрон", "протон"],
                default="gamma", width=140)
            self.radiation.pack(fill="x", pady=2)
            field("mass", "Масса облучаемого объекта, кг", "70")

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

        if mode == "Распад за время t":
            return NUC.decayed_amount(self._num("n0"), self._num("half_life"),
                                      self._num("time"), self.t_unit.get())
        if mode == "Время до заданного количества":
            return NUC.time_to_decay(self._num("n0"), self._num("target"),
                                     self._num("half_life"), self.t_unit.get())
        if mode == "Постоянная распада по периоду полураспада":
            return NUC.half_life_to_lambda(self._num("half_life"),
                                           self.t_unit.get())
        if mode == "Активность образца":
            return NUC.activity(self._num("moles"), self._num("half_life"),
                                self._text("name"))
        if mode == "Масса по активности":
            return NUC.mass_from_activity(self._num("activity"),
                                          self._num("half_life"),
                                          self._num("molar_mass"))
        if mode == "Перевод единиц активности":
            return NUC.convert_activity(self._num("value"),
                                        self.from_unit.get(),
                                        self.to_unit.get())
        if mode == "Энергия связи ядра":
            return NUC.nuclear_binding_energy(self._text("nuclide"))
        if mode == "Энергия ядерной реакции":
            reactants = [x.strip() for x in self._text("reactants").split(",")
                         if x.strip()]
            products = [x.strip() for x in self._text("products").split(",")
                        if x.strip()]
            if not reactants or not products:
                raise AlchemyError("Укажите реагенты и продукты")
            return NUC.reaction_energy(reactants, products)
        if mode == "Цепочка распада":
            raw = self._text("half_lives")
            try:
                half_lives = [float(x.strip().replace(",", "."))
                              for x in raw.split(",") if x.strip()]
            except ValueError:
                raise AlchemyError(f"Не удалось прочитать периоды: «{raw}»")
            return NUC.decay_chain(self._num("n0"), half_lives, self._num("time"))
        if mode == "Распад реального нуклида":
            amount = self._num("amount")
            if amount <= 0:
                raise AlchemyError("Начальное количество должно быть больше нуля")
            return NUC.decay_by_nuclides(
                {self._text("nuclide"): amount},
                self._num("time"),
                self.decay_unit.get(),
                self.amount_unit.get(),
            )
        if mode == "Свойства нуклида":
            return NUC.nuclide_data(self._text("nuclide"))
        if mode == "Природные ряды":
            chosen = self.series.get()
            return NUC.natural_series(None if chosen == "все три" else chosen)
        if mode == "Вековое равновесие":
            return NUC.secular_equilibrium(self._num("parent"),
                                           self._num("daughter"),
                                           self._num("activity"))
        dose = self._num("dose")
        mass = self._num("mass")
        # Поглощённая доза на массу, затем эквивалентная
        absorbed = NUC.absorbed_dose(dose * mass, mass)
        equivalent = NUC.equivalent_dose(absorbed.numeric(), self.radiation.get())
        equivalent.with_step("")
        equivalent.with_step(f"Пересчёт: {dose:g} Гр на объект массой {mass:g} кг")
        return equivalent


# ==========================================================================
# 8. Анализ погрешностей
# ==========================================================================


class UncertaintyTab(BaseTab):
    title = "Погрешности и значимые цифры"
    description = ("Распространение неопределённости по формулам, округление "
                   "до разумного числа значащих цифр, проверка результатов "
                   "расчёта на грубые ошибки.")
    action_label = "Рассчитать"
    history_action = "Погрешности"

    def build_inputs(self, parent):
        self.mode = LabeledCombo(
            parent, "Задача:",
            ["Значащие цифры в записи числа",
             "Округлить с учётом погрешности",
             "Молярная масса с неопределённостью",
             "Концентрация раствора с неопределённостью",
             "Проверка расчёта: сходимость и грубые ошибки"],
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

        def field(key, label, default="", width=160):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color=theme.COLOR_TEXT, width=340,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        if mode == "Значащие цифры в записи числа":
            field("numbers", "Числа через запятую", "0.00450, 1500, 1500., 1.500e3",
                  width=320)
        elif mode == "Округлить с учётом погрешности":
            field("value", "Значение", "9.8123")
            field("uncertainty", "Погрешность", "0.0234")
            field("unit", "Единица", "м/с²")
        elif mode == "Молярная масса с неопределённостью":
            field("formula", "Формула", "H2SO4")
        elif mode == "Концентрация раствора с неопределённостью":
            field("mass", "Масса навески, г", "1.2345")
            field("mass_unc", "Погрешность массы, г", "0.0002")
            field("volume", "Объём колбы, мл", "100.0")
            field("volume_unc", "Погрешность объёма, мл", "0.1")
            field("molar_mass", "Молярная масса, г/моль", "58.443")
            field("mm_unc", "Погрешность молярной массы", "0.001")
        else:
            field("equations", "Уравнения реакций (по одному в строке)",
                  "Fe2O3 + CO = Fe + CO2\nFe2O3 + 3CO = 2Fe + 3CO2", width=420)

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
        from ..core.results import Measurement, count_significant, format_measurement
        mode = self.mode.get()

        if mode == "Значащие цифры в записи числа":
            raw = self.fields["numbers"].get()
            items = [x.strip() for x in raw.split(",") if x.strip()]
            if not items:
                raise AlchemyError("Введите хотя бы одно число")

            rows = []
            for item in items:
                count = count_significant(item)
                rows.append({
                    "Запись": item,
                    "Значащих цифр": count,
                    "Пояснение": _explain_significant(item, count),
                })

            res = Result(
                value=rows,
                kind="table",
                label="Число значащих цифр",
                method="Правила значащих цифр: ведущие нули не значащие, "
                       "хвостовые нули без точки не значащие",
            )
            res.meta["columns"] = ["Запись", "Значащих цифр", "Пояснение"]
            for row in rows:
                res.with_step(f"{row['Запись']}: {row['Значащих цифр']} — {row['Пояснение']}")
            return res

        if mode == "Округлить с учётом погрешности":
            value = self._num("value")
            unc = self._num("uncertainty")
            unit = self.fields["unit"].get().strip()
            text = format_measurement(value, unc, unit)

            res = Result(
                value=value,
                unit=unit,
                label="Значение, округлённое с учётом погрешности",
                method="Погрешность записывается одной-двумя значащими цифрами, "
                       "значение округляется до того же разряда",
            )
            res.with_step(f"Введено: {value} ± {unc} {unit}")
            res.with_step(f"Правильная запись: {text}")
            res.with_step(
                "Правило: если старшая цифра погрешности 1 или 2, "
                "оставляют две значащие цифры, иначе одну"
            )
            res.with_step(
                f"Относительная погрешность: {abs(unc / value) * 100:.4f} %"
            )
            res.with_meta("formatted", text)
            res.uncertainty = unc
            res.value = value
            return res

        if mode == "Молярная масса с неопределённостью":
            text = self.fields["formula"].get().strip()
            comp = F.parse(text)
            measurement = comp.molar_mass_measurement

            res = Result(
                value=measurement.value,
                unit="г/моль",
                label=f"Молярная масса {comp.display}",
                method="Суммирование атомных масс с распространением "
                       "неопределённостей по закону Гаусса",
            )
            res.uncertainty = measurement.uncertainty
            res.with_step(
                f"σ = √(Σ(nᵢ·σᵢ)²) = {measurement.uncertainty:.6f} г/моль"
            )
            res.with_step(
                f"Результат: {format_measurement(measurement.value, measurement.uncertainty, 'г/моль')}"
            )
            res.with_step(
                f"Относительная неопределённость: "
                f"{measurement.uncertainty / measurement.value * 100:.5f} %"
            )

            res.with_step("")
            res.with_step("Вклад элементов:")
            for el in comp.elements:
                element = periodic.by_symbol(el)
                n = comp.counts[el]
                contribution = (n * (element.mass_uncertainty or 0)) ** 2
                res.with_step(
                    f"  {el}: n = {n:g}, σ(атома) = {element.mass_uncertainty or 0}, "
                    f"вклад в дисперсию {contribution:.3e}"
                )

            res.with_source("Атомные массы и неопределённости: IUPAC/CIAAW")
            return res

        if mode == "Концентрация раствора с неопределённостью":
            m = self._num("mass")
            dm = self._num("mass_unc")
            v = self._num("volume")
            dv = self._num("volume_unc")
            M = self._num("molar_mass")
            dM = self._num("mm_unc")

            # C = m/(M·V) в моль/л, V в мл -> V/1000 л
            C = m / (M * v / 1000.0)

            # Относительные неопределённости складываются квадратично
            rel_m = dm / m
            rel_M = dM / M
            rel_v = dv / v
            rel_C = math.sqrt(rel_m ** 2 + rel_M ** 2 + rel_v ** 2)
            dC = C * rel_C

            res = Result(
                value=C,
                unit="моль/л",
                label="Концентрация раствора",
                method="C = m/(M·V), неопределённость по закону распространения "
                       "погрешностей",
            )
            res.uncertainty = dC
            res.with_step(f"C = {m:g}/({M:g}·{v:g}/1000) = {C:.8f} моль/л")
            res.with_step("")
            res.with_step("Относительные неопределённости входных величин:")
            res.with_step(f"  масса:        {rel_m * 100:.5f} %")
            res.with_step(f"  молярная масса: {rel_M * 100:.5f} %")
            res.with_step(f"  объём:        {rel_v * 100:.5f} %")
            res.with_step(
                f"Итоговая: √(Σ) = {rel_C * 100:.5f} %"
            )
            res.with_step(
                f"Результат: {format_measurement(C, dC, 'моль/л')}"
            )

            # Вклад каждой величины
            res.with_step("")
            res.with_step("Вклад в общую дисперсию:")
            shares = {
                "масса": rel_m ** 2 / rel_C ** 2 * 100,
                "молярная масса": rel_M ** 2 / rel_C ** 2 * 100,
                "объём": rel_v ** 2 / rel_C ** 2 * 100,
            }
            for name, share in sorted(shares.items(), key=lambda x: -x[1]):
                res.with_step(f"  {name}: {share:.2f} %")
            biggest = max(shares, key=shares.get)
            res.with_step(
                f"Наибольший вклад даёт {biggest} — именно эту величину "
                f"стоит измерять точнее"
            )
            res.with_meta("relative_uncertainty", rel_C)
            res.with_meta("contributions", shares)
            return res

        # Проверка расчёта
        text = self.fields["equations"].get("1.0", "end") if hasattr(
            self.fields["equations"], "get") else ""
        if isinstance(self.fields["equations"], ctk.CTkEntry):
            text = self.fields["equations"].get()

        equations = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
        if not equations:
            raise AlchemyError("Введите хотя бы одно уравнение")

        rows = []
        for eq in equations:
            try:
                balanced = BAL.balance(eq)
                check = balanced.meta["elements"]
                max_dev = max(
                    abs(v["left"] - v["right"]) for v in check.values()
                )
                rows.append({
                    "Уравнение": eq,
                    "Уравнено": balanced.value,
                    "Макс. отклонение": max_dev,
                    "Статус": "верно" if max_dev < 1e-9 else "ОШИБКА",
                })
            except AlchemyError as exc:
                rows.append({
                    "Уравнение": eq,
                    "Уравнено": "—",
                    "Макс. отклонение": None,
                    "Статус": f"ошибка: {exc}",
                })

        res = Result(
            value=rows,
            kind="table",
            label="Проверка уравнений на баланс",
            method="Независимая проверка баланса массы и заряда по каждому элементу",
        )
        res.meta["columns"] = ["Уравнение", "Уравнено", "Макс. отклонение", "Статус"]
        for row in rows:
            res.with_step(
                f"{row['Уравнение']}: {row['Статус']} "
                f"(отклонение {row['Макс. отклонение']})"
            )
        return res


def _explain_significant(text: str, count: int) -> str:
    """Пояснить, почему у числа столько значащих цифр."""
    s = str(text).strip()
    if "e" in s.lower():
        return "экспоненциальная запись: все цифры мантиссы значащие"
    if "." not in s:
        stripped = s.lstrip("+-").lstrip("0")
        trailing = len(stripped) - len(stripped.rstrip("0"))
        if trailing:
            return "хвостовые нули без десятичной точки не считаются значащими"
        return "все цифры значащие"
    mantissa = s.lstrip("+-")
    leading = len(mantissa.split(".")[0].lstrip("0"))
    if leading == 0:
        return "ведущие нули после запятой не значащие"
    return "все цифры, начиная с первой ненулевой, значащие"


# ==========================================================================
# 9. Справочник веществ
# ==========================================================================


class HandbookTab(BaseTab):
    title = "Справочник веществ"
    description = ("Термохимические данные, малорастворимые соединения, "
                   "растворители, кислоты, электродные потенциалы, "
                   "физические константы — с указанием источников.")
    action_label = "Найти"
    history_action = "Справочник"

    def build_inputs(self, parent):
        self.section = LabeledCombo(
            parent, "Раздел:",
            ["Термохимия: вещества", "Термохимия: ионы",
             "Малорастворимые соединения", "Растворители",
             "Кислоты и основания", "Индикаторы",
             "Электродные потенциалы", "Физические константы",
             "Статистика справочников"],
            width=280)
        self.section.pack(fill="x", pady=4)
        self.section.combo.configure(command=lambda _: self.run())

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Поиск:", font=("Segoe UI", 12),
                     text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 8))
        self.query = ctk.CTkEntry(row, width=260, font=("Consolas", 13))
        self.query.pack(side="left")
        ctk.CTkLabel(row, text="(пусто — показать всё)", font=("Segoe UI", 10),
                     text_color=theme.COLOR_TEXT_DIM).pack(side="left", padx=8)

    def calculate(self) -> Result:
        section = self.section.get()
        query = self.query.get().strip()

        if section == "Термохимия: вещества":
            return self._thermo_substances(query)
        if section == "Термохимия: ионы":
            return self._thermo_ions(query)
        if section == "Малорастворимые соединения":
            return self._solids(query)
        if section == "Растворители":
            return self._solvents(query)
        if section == "Кислоты и основания":
            return self._acids(query)
        if section == "Индикаторы":
            return self._indicators()
        if section == "Электродные потенциалы":
            return self._electrodes(query)
        if section == "Физические константы":
            return self._constants()
        return self._stats()

    def _thermo_substances(self, query):
        from ..core.constants import ALL_CONSTANTS
        items = TDB.all_substances()
        if query:
            items = TDB.search(query, limit=200)
        rows = []
        for s in items[:200]:
            rows.append({
                "Вещество": s.name,
                "Формула": s.key,
                "Состояние": s.state_ru,
                "ΔH°f, кДж/моль": s.dHf,
                "ΔG°f, кДж/моль": s.dGf,
                "S°, Дж/(моль·К)": s.S,
                "Cp, Дж/(моль·К)": s.Cp,
                "M, г/моль": s.M,
            })
        res = Result(value=rows, kind="table",
                     label=f"Термохимические данные ({len(rows)} записей)",
                     method="Стандартные величины при 298.15 К")
        res.meta["columns"] = ["Вещество", "Формула", "Состояние",
                               "ΔH°f, кДж/моль", "ΔG°f, кДж/моль",
                               "S°, Дж/(моль·К)", "Cp, Дж/(моль·К)", "M, г/моль"]
        res.with_source(TDB.source())
        return res

    def _thermo_ions(self, query):
        items = TDB.all_ions()
        if query:
            q = query.lower()
            items = [i for i in items if q in i.key.lower() or q in i.name.lower()]
        rows = [{
            "Ион": i.key,
            "Название": i.name,
            "ΔH°f, кДж/моль": i.dHf,
            "ΔG°f, кДж/моль": i.dGf,
            "S°, Дж/(моль·К)": i.S,
        } for i in items]
        res = Result(value=rows, kind="table",
                     label=f"Термохимия ионов ({len(rows)} записей)",
                     method="Шкала с ΔH°f(H⁺, aq) = 0")
        res.meta["columns"] = ["Ион", "Название", "ΔH°f, кДж/моль",
                               "ΔG°f, кДж/моль", "S°, Дж/(моль·К)"]
        res.with_source(TDB.source())
        res.with_step(
            "Абсолютные значения для ионов условны: они отсчитываются от "
            "иона водорода. Корректны только разности, то есть тепловые "
            "эффекты реакций."
        )
        return res

    def _solids(self, query):
        items = SDB.all_solids()
        if query:
            items = SDB.search(query, limit=100)
        rows = []
        for s in items:
            rows.append({
                "Формула": s.formula,
                "Название": s.name,
                "Ks": f"{s.Ksp:.2e}",
                "pKs": round(s.pKsp, 2),
                "Растворимость, моль/л": f"{s.solubility_pure_water():.3e}",
                "Растворимость, г/л": (f"{s.solubility_g_per_l():.3e}"
                                       if s.solubility_g_per_l() else "—"),
            })
        res = Result(value=rows, kind="table",
                     label=f"Малорастворимые соединения ({len(rows)})",
                     method="Термодинамические произведения растворимости при 298 К")
        res.meta["columns"] = ["Формула", "Название", "Ks", "pKs",
                               "Растворимость, моль/л", "Растворимость, г/л"]
        res.with_source(SDB.solubility_source())
        res.with_assumption(
            "Растворимость рассчитана для чистой воды без учёта ионной силы "
            "и гидролиза. В реальных условиях она может отличаться в разы."
        )
        return res

    def _solvents(self, query):
        items = SDB.all_solvents()
        if query:
            q = query.lower()
            items = [s for s in items if q in s.name.lower() or q in s.formula.lower()]
        rows = [{
            "Растворитель": s.name,
            "Формула": s.formula,
            "M, г/моль": s.M,
            "ρ, г/см³": s.density,
            "T кип, °C": (round(s.Tb_C, 1) if s.Tb_C is not None else None),
            "T плав, °C": (round(s.Tf_C, 1) if s.Tf_C is not None else None),
            "Kb": s.Kb,
            "Kf": s.Kf,
            "ε": s.eps,
        } for s in items]
        res = Result(value=rows, kind="table",
                     label=f"Растворители ({len(rows)})",
                     method="Физические свойства при нормальных условиях")
        res.meta["columns"] = ["Растворитель", "Формула", "M, г/моль",
                               "ρ, г/см³", "T кип, °C", "T плав, °C",
                               "Kb", "Kf", "ε"]
        res.with_source(SDB.solvents_source())
        return res

    def _acids(self, query):
        rows = []
        for a in ADB.all_acids():
            if query and query.lower() not in a.formula.lower() \
                    and query.lower() not in a.name.lower():
                continue
            rows.append({
                "Формула": a.formula,
                "Название": a.name,
                "pKa": a.pKa,
                "Ka": f"{a.Ka:.3e}",
                "Тип": "сильная" if a.is_strong else "слабая",
                "Ступеней": a.protons,
                "Есть T-зависимость": "да" if a.has_temperature_data else "нет",
            })
        for b in ADB.all_bases():
            if query and query.lower() not in b.formula.lower() \
                    and query.lower() not in b.name.lower():
                continue
            rows.append({
                "Формула": b.formula,
                "Название": b.name,
                "pKa": b.pKa_conj,
                "Ka": f"{10 ** (-b.pKa_conj):.3e}",
                "Тип": "сильное" if b.is_strong else "слабое",
                "Ступеней": "—",
                "Есть T-зависимость": "—",
            })
        res = Result(value=rows, kind="table",
                     label=f"Кислоты и основания ({len(rows)})",
                     method="Для оснований приведён pKa сопряжённой кислоты")
        res.meta["columns"] = ["Формула", "Название", "pKa", "Ka", "Тип",
                               "Ступеней", "Есть T-зависимость"]
        res.with_source(ADB.source())
        res.with_step(
            "pKw зависит от температуры: при 25 °C это 14.00, при 100 °C — 12.27. "
            "Программа учитывает эту зависимость во всех расчётах pH."
        )
        return res

    def _indicators(self):
        rows = [{
            "Индикатор": i.name,
            "pKa": i.pKa,
            "Интервал перехода": f"{i.transition_low:g}–{i.transition_high:g}",
            "Цвет в кислой среде": i.color_acid,
            "Цвет в щелочной среде": i.color_base,
        } for i in ADB.all_indicators()]
        res = Result(value=rows, kind="table",
                     label=f"Кислотно-основные индикаторы ({len(rows)})",
                     method="Справочные данные")
        res.meta["columns"] = ["Индикатор", "pKa", "Интервал перехода",
                               "Цвет в кислой среде", "Цвет в щелочной среде"]
        res.with_source(ADB.source())
        return res

    def _electrodes(self, query):
        items = EDB.search(query) if query else EDB.all_electrodes()
        rows = [{
            "Обозначение": e.id,
            "Полуреакция": e.half_reaction,
            "E°, В": round(e.E0, 4),
            "n": e.n,
            "Среда": {"acid": "кислая", "base": "щелочная",
                      "any": "любая"}.get(e.medium, e.medium),
        } for e in items]
        res = Result(value=rows, kind="table",
                     label=f"Стандартные электродные потенциалы ({len(rows)})",
                     method="Относительно стандартного водородного электрода, 298.15 К")
        res.meta["columns"] = ["Обозначение", "Полуреакция", "E°, В", "n", "Среда"]
        res.with_source(EDB.source())
        res.with_step(
            "Чем больше E°, тем сильнее окислитель в левой части записи. "
            "Реакция идёт в сторону образования более слабого окислителя."
        )
        return res

    def _constants(self):
        from ..core.constants import ALL_CONSTANTS
        rows = [{
            "Обозначение": c.symbol,
            "Название": c.name,
            "Значение": c.value,
            "Единица": c.unit,
            "Неопределённость": (c.uncertainty if c.uncertainty else "точно"),
            "Источник": c.source,
        } for c in ALL_CONSTANTS]
        res = Result(value=rows, kind="table",
                     label=f"Физические константы ({len(rows)})",
                     method="CODATA-2018, SI-2019, IUPAC")
        res.meta["columns"] = ["Обозначение", "Название", "Значение",
                               "Единица", "Неопределённость", "Источник"]
        res.with_step(
            "Значения с пометкой «точно» зафиксированы определением "
            "Международной системы единиц с 2019 года"
        )
        return res

    def _stats(self):
        stats = loader.stats()
        rows = [{"Раздел": k, "Записей": v} for k, v in stats.items()]
        res = Result(value=rows, kind="table",
                     label="Состав справочной базы",
                     method="Подсчёт записей по файлам данных")
        res.meta["columns"] = ["Раздел", "Записей"]
        res.with_step(f"Всего разделов: {len(rows)}")
        res.with_step(f"Всего записей: {sum(stats.values())}")
        res.with_step("")
        res.with_step("Источники данных:")
        for f in loader.available_files():
            res.with_step(f"  {f}: {loader.source_of(f)[:110]}...")
        res.with_source(
            "Справочники собраны из: IUPAC, CIAAW, CRC Handbook, "
            "NIST-JANAF, справочник Глушко, справочник Никольского, "
            "Лурье «Справочник по аналитической химии»"
        )
        return res


# ==========================================================================
# 10. Графики
# ==========================================================================


class GraphsTab(BaseTab):
    title = "Графики"
    description = ("Построение графиков по реальным расчётам: кривые "
                   "титрования, зависимости ΔG(T), кинетические кривые, "
                   "распределение Максвелла, диаграммы Пурбе, кривые распада.")
    action_label = "Построить"
    history_action = "Графики"

    def build_inputs(self, parent):
        self.plot_type = LabeledCombo(
            parent, "Что построить:",
            ["Кривая титрования кислоты",
             "Зависимость ΔG от температуры",
             "Кинетическая кривая",
             "Распределение Максвелла",
             "Диаграмма Пурбе",
             "Кривая радиоактивного распада",
             "Зависимость k(T) по Аррениусу",
             "Последовательные реакции A → B → C"],
            width=320)
        self.plot_type.pack(fill="x", pady=4)
        self.plot_type.combo.configure(command=lambda _: self._rebuild())

        self.area = ctk.CTkFrame(parent, fg_color="transparent")
        self.area.pack(fill="x", pady=6)
        self._rebuild()

    def _rebuild(self):
        for widget in self.area.winfo_children():
            widget.destroy()
        self.fields = {}
        mode = self.plot_type.get()

        def field(key, label, default="", width=140):
            frame = ctk.CTkFrame(self.area, fg_color="transparent")
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=label, font=("Segoe UI", 12),
                         text_color=theme.COLOR_TEXT, width=320,
                         anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=width, font=("Consolas", 13))
            entry.pack(side="left")
            if default:
                entry.insert(0, default)
            self.fields[key] = entry

        if mode == "Кривая титрования кислоты":
            self.combo = LabeledCombo(self.area, "Кислота:",
                                      [a.formula for a in ADB.all_acids()],
                                      default="CH3COOH", width=200)
            self.combo.pack(fill="x", pady=2)
            field("c_acid", "C кислоты, моль/л", "0.1")
            field("v_acid", "V аликвоты, мл", "20")
            field("c_base", "C титранта, моль/л", "0.1")
        elif mode == "Зависимость ΔG от температуры":
            field("equation", "Уравнение реакции",
                  "CaCO3(тв) = CaO(тв) + CO2", width=400)
            field("t_min", "T от, К", "300")
            field("t_max", "T до, К", "1400")
        elif mode == "Кинетическая кривая":
            self.combo = LabeledCombo(self.area, "Порядок реакции:",
                                      ["0", "1", "2"], default="1", width=100)
            self.combo.pack(fill="x", pady=2)
            field("k", "Константа скорости", "0.1")
            field("c0", "Начальная концентрация, моль/л", "1.0")
        elif mode == "Распределение Максвелла":
            field("gas", "Газ", "N2")
            field("temperature", "Температура, К", "298.15")
        elif mode == "Диаграмма Пурбе":
            self.combo = LabeledCombo(self.area, "Элемент:",
                                      list(EC.POURBAIX_SYSTEMS),
                                      default="Fe", width=140)
            self.combo.pack(fill="x", pady=2)
            field("ph_min", "pH от", "0")
            field("ph_max", "pH до", "14")
        elif mode == "Кривая радиоактивного распада":
            field("n0", "Начальное количество", "100")
            field("half_life", "Период полураспада, с", "10")
            field("periods", "Число периодов на графике", "6")
        elif mode == "Зависимость k(T) по Аррениусу":
            field("A", "Предэкспонента A", "1e10")
            field("ea", "Энергия активации, кДж/моль", "75")
            field("t_min", "T от, К", "250")
            field("t_max", "T до, К", "600")
        else:
            field("k1", "k₁ (A → B)", "0.1")
            field("k2", "k₂ (B → C)", "0.05")
            field("c0", "Начальная концентрация A, моль/л", "1.0")

    def build_extra(self, parent):
        self.plot_frame = Card(parent, title="График")
        self.plot_frame.pack(fill="both", expand=True, padx=2, pady=(10, 0))
        # Пока график не построен, в области карточки висит пустота.
        # Подсказка объясняет, что здесь появится.
        self.plot_hint = ctk.CTkLabel(
            self.plot_frame.body,
            text="Здесь появится график.\n"
                 "Выберите, что построить, и нажмите «Построить».",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM, justify="center")
        self.plot_hint.pack(expand=True, pady=60)

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
        mode = self.plot_type.get()

        if mode == "Кривая титрования кислоты":
            return AB.titration_curve(self.combo.get(), self._num("c_acid"),
                                      self._num("v_acid"), self._num("c_base"))
        if mode == "Зависимость ΔG от температуры":
            return TH.gibbs_vs_temperature(
                self.fields["equation"].get().strip(),
                self._num("t_min"), self._num("t_max"))
        if mode == "Кинетическая кривая":
            return KIN.reaction_curve(int(self.combo.get()), self._num("k"),
                                      self._num("c0"))
        if mode == "Распределение Максвелла":
            return G.maxwell_boltzmann(self._num("temperature"),
                                       self.fields["gas"].get().strip())
        if mode == "Диаграмма Пурбе":
            return EC.pourbaix_diagram(self.combo.get(), self._num("ph_min"),
                                       self._num("ph_max"))
        if mode == "Кривая радиоактивного распада":
            return NUC.decay_curve(self._num("n0"), self._num("half_life"),
                                   n_half_lives=self._num("periods"))
        if mode == "Зависимость k(T) по Аррениусу":
            return KIN.arrhenius_curve(self._num("A"), self._num("ea") * 1000.0,
                                       self._num("t_min"), self._num("t_max"))
        return KIN.consecutive_reactions(self._num("k1"), self._num("k2"),
                                         self._num("c0"))

    def run(self) -> None:
        """Построить расчёт и, если получен набор точек, нарисовать график."""
        super().run()
        try:
            result = self.calculate()
        except Exception:
            return
        if result.kind == "series":
            self._draw_series(result)

    def _draw_series(self, result: Result) -> None:
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from .widgets import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            return

        for widget in self.plot_frame.body.winfo_children():
            widget.destroy()

        figure = Figure(figsize=(7, 4.2), facecolor="#242424", dpi=100)
        axes = figure.add_subplot(111)
        axes.set_facecolor("#242424")

        data = result.value
        if result.meta.get("lines"):
            # Диаграмма Пурбе: несколько линий
            for label, points in result.meta["lines"].items():
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                style = "--" if "водород" in label or "кислород" in label else "-"
                axes.plot(xs, ys, style, linewidth=1.6, label=label)
            axes.legend(facecolor="#242424", edgecolor="#3a3a3a",
                        labelcolor=theme.COLOR_TEXT, fontsize=8)
        elif result.meta.get("series"):
            # Последовательные реакции: три кривые
            series = result.meta["series"]
            for key in ("A", "B", "C"):
                xs = [p["Время"] for p in series]
                ys = [p[key] for p in series]
                axes.plot(xs, ys, linewidth=1.8, label=key)
            axes.legend(facecolor="#242424", edgecolor="#3a3a3a",
                        labelcolor=theme.COLOR_TEXT)
        else:
            xs = [p[0] for p in data]
            ys = [p[1] for p in data]
            axes.plot(xs, ys, color=theme.COLOR_ACCENT, linewidth=2)

        axes.set_xlabel(result.meta.get("x_label", "x"), color=theme.COLOR_TEXT,
                        fontsize=10)
        axes.set_ylabel(result.meta.get("y_label", "y"), color=theme.COLOR_TEXT,
                        fontsize=10)
        axes.set_title(result.label, color=theme.COLOR_TEXT, fontsize=11)
        axes.tick_params(colors=theme.COLOR_TEXT_DIM, labelsize=9)
        for spine in axes.spines.values():
            spine.set_color("#3a3a3a")
        axes.grid(True, alpha=0.2, color="#666666")

        figure.tight_layout()

        canvas = FigureCanvasTkAgg(figure, self.plot_frame.body)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


# ==========================================================================
# 11. Журнал операций
# ==========================================================================


class HistoryTab(BaseTab):
    title = "Журнал операций"
    description = ("Все выполненные расчёты с результатами. Журнал можно "
                   "сохранить в файл и загрузить обратно, а также выгрузить "
                   "в виде текстового протокола.")
    action_label = "Обновить"
    history_action = ""

    def build_inputs(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkButton(row, text="Обновить", width=120,
                      command=self.run).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Сохранить журнал", width=160,
                      command=self.export).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Загрузить журнал", width=160,
                      command=self.import_log).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Очистить", width=110, fg_color="transparent",
                      border_width=1, border_color="#3a3a3a",
                      text_color="#e74c3c",
                      command=self.clear).pack(side="left")

        self.filter_entry = LabeledEntry(parent, "Фильтр по названию операции",
                                         width=240)
        self.filter_entry.pack(fill="x", pady=4)

    def build_extra(self, parent):
        self.detail_card = Card(parent, title="Подробности выбранной записи")
        self.detail_card.pack(fill="x", padx=2, pady=(10, 0))
        self.detail_text = ctk.CTkTextbox(self.detail_card.body, height=180,
                                          font=("Consolas", 11),
                                          fg_color=theme.COLOR_CARD_ALT, wrap="word")
        # Пустое поле выглядит как провал: подсказываем, что делать
        self.detail_text.insert(
            "1.0", "Выберите запись в таблице ниже — здесь появится "
                  "её результат и ход расчёта.")
        self.detail_text.pack(fill="both", expand=True)

    def _get_log(self):
        if self.controller is None:
            return []
        return getattr(self.controller, "history", [])

    def calculate(self) -> Result:
        log = self._get_log()
        query = self.filter_entry.get().lower()

        rows = []
        for item in log:
            action = item.get("action", "")
            if query and query not in action.lower():
                continue
            rows.append({
                "Время": item.get("time", ""),
                "Операция": action,
                "Результат": item.get("result", ""),
            })

        res = Result(value=rows, kind="table",
                     label=f"Журнал операций ({len(rows)} записей)",
                     method="Записи добавляются автоматически при каждом расчёте")
        res.meta["columns"] = ["Время", "Операция", "Результат"]

        if not rows:
            res.with_warning("Журнал пуст. Выполните любой расчёт — запись появится здесь.")
        else:
            res.with_step(f"Показано записей: {len(rows)}")
            res.with_step(f"Всего в журнале: {len(log)}")
            res.with_step("")
            res.with_step("Последние операции:")
            for row in rows[:15]:
                res.with_step(
                    f"  {row['Время']}  {row['Операция']}: {row['Результат']}"
                )
        return res

    def export(self):
        log = self._get_log()
        if not log:
            messagebox.showinfo("Журнал", "Журнал пуст — нечего сохранять")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовый протокол", "*.txt"),
                       ("JSON", "*.json"), ("Все файлы", "*.*")],
            initialfile="alchemy_journal.txt")
        if not path:
            return

        try:
            if path.lower().endswith(".json"):
                import json
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(log, handle, ensure_ascii=False, indent=2)
            else:
                lines = ["Протокол расчётов Alchemy", "=" * 60, ""]
                for item in reversed(log):
                    lines.append(f"[{item.get('time', '')}] {item.get('action', '')}")
                    result_text = str(item.get("result", ""))
                    for line in result_text.splitlines():
                        lines.append(f"    {line}")
                    lines.append("")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("\n".join(lines))
            messagebox.showinfo("Журнал", f"Сохранено: {path}")
        except OSError as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {exc}")

    def import_log(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            import json
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, list):
                raise ValueError("в файле ожидается список записей")
            if self.controller is not None:
                self.controller.history = data
            self.run()
            messagebox.showinfo("Журнал", f"Загружено записей: {len(data)}")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить: {exc}")

    def clear(self):
        if not messagebox.askyesno("Очистка журнала",
                                   "Удалить все записи журнала?"):
            return
        if self.controller is not None:
            self.controller.history = []
        self.run()


# ==========================================================================
# 12. Проверка знаний
# ==========================================================================


class PracticeTab(BaseTab):
    title = "Проверка расчётов"
    description = ("Инструмент самопроверки: программа предлагает задачу, "
                   "вы решаете её сами, а затем вводите ответ — он "
                   "проверяется с указанием расхождения.")
    action_label = "Проверить ответ"
    history_action = "Самопроверка"

    def build_inputs(self, parent):
        self.topic = LabeledCombo(
            parent, "Тема:",
            ["Молярная масса", "Массовая доля элемента",
             "pH сильной кислоты", "pH слабого основания",
             "Разведение раствора", "Выход продукта"],
            width=260)
        self.topic.pack(fill="x", pady=4)
        self.topic.combo.configure(command=lambda _: self.new_task())

        ctk.CTkButton(parent, text="Новая задача", width=160,
                      command=self.new_task).pack(anchor="w", pady=(6, 8))

        self.task_text = ctk.CTkTextbox(parent, height=110,
                                        font=("Segoe UI", 12),
                                        fg_color=theme.COLOR_CARD_ALT, wrap="word")
        self.task_text.pack(fill="x")
        self.task_text.configure(state="disabled")

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=8)
        ctk.CTkLabel(row, text="Ваш ответ:", font=("Segoe UI", 12),
                     text_color=theme.COLOR_TEXT).pack(side="left", padx=(0, 8))
        self.answer = ctk.CTkEntry(row, width=180, font=("Consolas", 13))
        self.answer.pack(side="left")
        self.unit_label = ctk.CTkLabel(row, text="", font=("Segoe UI", 11),
                                       text_color=theme.COLOR_TEXT_DIM)
        self.unit_label.pack(side="left", padx=8)

        self._task = None

    def build_extra(self, parent):
        """Первая задача выдаётся после того, как панель результата создана."""

    def on_ready(self) -> None:
        """Вызывается после полной сборки вкладки."""
        self.new_task()

    def new_task(self):
        import random
        topic = self.topic.get()
        random.seed()

        if topic == "Молярная масса":
            options = ["H2SO4", "KMnO4", "Ca3(PO4)2", "CuSO4*5H2O",
                       "C6H12O6", "Fe2O3", "K2Cr2O7", "Al2(SO4)3"]
            formula_text = random.choice(options)
            answer = F.molar_mass(formula_text)
            self._task = {
                "text": f"Вычислите молярную массу вещества {formula_text}.",
                "answer": answer, "unit": "г/моль",
                "solution": f"M({formula_text}) = {answer:.4f} г/моль",
                "tolerance": 0.01,
            }
        elif topic == "Массовая доля элемента":
            options = [("H2O", "H"), ("Fe2O3", "Fe"), ("H2SO4", "S"),
                       ("CuSO4", "Cu"), ("CaCO3", "Ca"), ("KMnO4", "Mn")]
            formula_text, element = random.choice(options)
            comp = F.parse(formula_text)
            answer = comp.mass_percentages[element]
            self._task = {
                "text": f"Какова массовая доля {element} в {formula_text}? "
                        f"Ответ дайте в процентах.",
                "answer": answer, "unit": "%",
                "solution": f"w({element}) = {answer:.4f} %",
                "tolerance": 0.05,
            }
        elif topic == "pH сильной кислоты":
            c = random.choice([0.01, 0.05, 0.1, 0.2, 0.5])
            answer = -math.log10(c)
            self._task = {
                "text": f"Вычислите pH раствора соляной кислоты с концентрацией "
                        f"{c} моль/л (без учёта активности).",
                "answer": answer, "unit": "",
                "solution": f"pH = −lg({c}) = {answer:.4f}",
                "tolerance": 0.02,
            }
        elif topic == "pH слабого основания":
            base_options = [("NH3", 4.75), ("CH3NH2", 3.36), ("C2H5NH2", 3.25)]
            name, pkb = random.choice(base_options)
            c = random.choice([0.01, 0.05, 0.1, 0.2])
            kb = 10 ** (-pkb)
            oh = (-kb + math.sqrt(kb ** 2 + 4 * kb * c)) / 2
            poh = -math.log10(oh)
            answer = 14.0 - poh
            self._task = {
                "text": f"Вычислите pH раствора {name} с концентрацией "
                        f"{c} моль/л. pKb = {pkb}.",
                "answer": answer, "unit": "",
                "solution": (
                    f"Kb = 10^(−{pkb}) = {kb:.4e}; "
                    f"[OH⁻] = {oh:.4e} моль/л; pOH = {poh:.4f}; pH = {answer:.4f}"
                ),
                "tolerance": 0.05,
            }
        elif topic == "Разведение раствора":
            c1 = random.choice([0.5, 1.0, 2.0, 4.0])
            v2 = random.choice([100, 250, 500, 1000])
            c2 = c1 / random.choice([2, 5, 10])
            answer = c1 * (v2 / 1000.0) / c2 * 1000.0
            self._task = {
                "text": f"Какой объём (в мл) раствора с концентрацией {c1} моль/л "
                        f"нужен, чтобы приготовить {v2} мл раствора "
                        f"с концентрацией {c2:g} моль/л?",
                "answer": answer, "unit": "мл",
                "solution": (
                    f"V₁ = C₂V₂/C₁ = {c2:g}·{v2}/{c1} = {answer:.2f} мл"
                ),
                "tolerance": 0.5,
            }
        else:
            m1 = random.choice([10.0, 20.0, 50.0, 100.0])
            yield_pct = random.choice([75.0, 80.0, 85.0, 90.0, 95.0])
            answer = m1 * yield_pct / 100.0
            self._task = {
                "text": f"Теоретический выход продукта равен {m1} г. "
                        f"Каков практический выход (в граммах) при выходе "
                        f"{yield_pct} %?",
                "answer": answer, "unit": "г",
                "solution": f"m = {m1}·{yield_pct}/100 = {answer:.3f} г",
                "tolerance": 0.01,
            }

        self.task_text.configure(state="normal")
        self.task_text.delete("1.0", "end")
        self.task_text.insert("1.0", self._task["text"])
        self.task_text.configure(state="disabled")
        self.unit_label.configure(text=self._task["unit"])
        self.answer.delete(0, "end")
        self.result_view.clear()

    def calculate(self) -> Result:
        if self._task is None:
            raise AlchemyError("Сначала получите задачу")

        raw = self.answer.get().strip().replace(",", ".")
        if not raw:
            raise AlchemyError("Введите ответ")

        try:
            given = float(raw)
        except ValueError:
            raise AlchemyError(f"«{raw}» не является числом")

        expected = self._task["answer"]
        tolerance = self._task["tolerance"]
        delta = abs(given - expected)
        relative = delta / abs(expected) * 100 if expected else 0.0

        correct = delta <= tolerance

        res = Result(
            value=given,
            unit=self._task["unit"],
            label="Ответ верный" if correct else "Ответ неверный",
            method="Сравнение с эталонным значением, рассчитанным движком",
        )
        res.with_step(f"Ваш ответ: {given:g} {self._task['unit']}")
        res.with_step(f"Правильный ответ: {expected:.6g} {self._task['unit']}")
        res.with_step(f"Расхождение: {delta:.6g} ({relative:.4f} %)")
        res.with_step("")
        res.with_step("Решение:")
        res.with_step(f"  {self._task['solution']}")

        res.with_meta("correct", correct)
        res.with_meta("expected", expected)
        res.with_meta("given", given)

        if not correct:
            if relative > 20:
                res.with_warning(
                    f"Расхождение {relative:.1f} % слишком велико — "
                    f"проверьте ход решения, а не только арифметику"
                )
            else:
                res.with_warning(
                    f"Расхождение {relative:.2f} % — вероятно, округление "
                    f"или арифметическая ошибка"
                )
        return res
