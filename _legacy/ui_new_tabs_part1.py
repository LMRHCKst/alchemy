# -*- coding: utf-8 -*-
"""
Новые вкладки для химического калькулятора (Часть 1).
Включает: FormulaAnalysisTab, AdvancedSolutionsTab, AdvancedAcidBaseTab, ColligativeTab.
"""


class FormulaAnalysisTab(ctk.CTkFrame):
    """Вкладка анализа химических формул."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self.empirical_entries = []

        # --- Основная карточка ---
        card = CardFrame(self, title="Анализ химической формулы",
                         desc="Полный анализ элементного состава, молярной массы и эмпирической формулы")

        # Ввод формулы
        entry_frame = ctk.CTkFrame(card, fg_color="transparent")
        entry_frame.pack(fill="x", padx=20, pady=(10, 5))
        ctk.CTkLabel(entry_frame, text="Формула:", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 8))
        self.formula_entry = ctk.CTkEntry(entry_frame, width=280, font=("Consolas", 14),
                                          placeholder_text="напр. C6H12O6, CuSO4*5H2O")
        self.formula_entry.pack(side="left", padx=5)
        self.formula_entry.bind("<Return>", lambda e: self.calc_full())

        # Кнопки
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=8)
        ctk.CTkButton(btn_frame, text="Полный анализ", command=self.calc_full, width=140,
                      fg_color="#2980b9").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Эмпирическая формула", command=self.show_empirical, width=180,
                      fg_color="#8e44ad").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Очистить", command=self.clear, width=100,
                      fg_color="gray").pack(side="left", padx=5)

        # Результаты (Textbox)
        self.result_box = ctk.CTkTextbox(card, height=350, font=("Consolas", 12), wrap="word",
                                         fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.result_box.pack(fill="both", expand=True, padx=15, pady=(5, 15))

    def clear(self):
        """Очищает все поля."""
        self.formula_entry.delete(0, "end")
        self.result_box.delete("0.0", "end")
        self.result_box.insert("0.0", "Введите формулу и нажмите 'Полный анализ'.\n")
        self.empirical_entries = []

    def _format_full_analysis(self, formula_str):
        """Форматирует полный анализ формулы в текст."""
        mass = FormulaParser.calculate_mass(formula_str)
        if mass == 0.0:
            raise ValueError("Не удалось вычислить молярную массу. Проверьте формулу.")

        composition = FormulaParser.get_composition(formula_str)
        mass_pct = FormulaParser.get_mass_percentages(formula_str)

        # Заголовок
        line = "\u2550" * 42
        header = f"\n{line}\n  \u2550\u2550\u2550 Молярная масса: {mass:.4f} г/моль \u2550\u2550\u2550\n{line}\n"

        # Таблица элементов
        col_el = "Элемент"
        col_ru = "Название"
        col_cnt = "Кол-во"
        col_pct = "% по массе"
        separator = "\u2500" * 50

        table = f"\n {col_el:<8s}\u2502 {col_ru:<16s}\u2502 {col_cnt:<6s}\u2502 {col_pct}\n {separator}\n"

        for el, count in sorted(composition.items()):
            el_ru = ELEMENTS_RU.get(el, el)
            cnt_str = str(int(count)) if count == int(count) else str(count)
            pct = mass_pct.get(el, 0.0)
            table += f" {el:<8s}\u2502 {el_ru:<16s}\u2502 {cnt_str:<6s}\u2502 {pct:.2f}%\n"

        # Суммарная информация
        total_atoms = sum(composition.values())
        summary = f"\n Всего элементов: {len(composition)}\n"
        summary += f" Всего атомов: {int(total_atoms)}\n"

        return header + table + summary

    def calc_full(self):
        """Выполняет полный анализ формулы."""
        formula = self.formula_entry.get().strip()
        if not formula:
            self.result_box.delete("0.0", "end")
            self.result_box.insert("0.0", "Ошибка: введите формулу!\n")
            return

        try:
            text = self._format_full_analysis(formula)
            self.result_box.delete("0.0", "end")
            self.result_box.insert("0.0", text)
            mass = FormulaParser.calculate_mass(formula)
            HistoryManager.add(f"Анализ ({formula})", f"M = {mass:.4f} г/моль")
        except Exception as e:
            self.result_box.delete("0.0", "end")
            self.result_box.insert("0.0", f"Ошибка: {str(e)}\n")

    def show_empirical(self):
        """Показывает панель для расчёта эмпирической формулы по массовым процентам."""
        # Очищаем результат и показываем форму ввода
        self.result_box.delete("0.0", "end")
        self.result_box.insert("0.0", "=== ЭМПИРИЧЕСКАЯ ФОРМУЛА ===\n")
        self.result_box.insert("end", "Добавьте элементы и их массовые проценты.\n")
        self.result_box.insert("end", "Нажмите 'Рассчитать' для получения эмпирической формулы.\n")
        self.result_box.insert("end", "\n")

        self.empirical_entries = []

        # Добавляем минимальные 2 строки ввода
        self._add_empirical_row()
        self._add_empirical_row()

        # Кнопки управления
        emp_frame = ctk.CTkFrame(self, fg_color="transparent")
        emp_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkButton(emp_frame, text="+ Добавить элемент", command=self._add_empirical_row,
                      width=160, fg_color="#27ae60").pack(side="left", padx=5)
        ctk.CTkButton(emp_frame, text="Рассчитать эмпирическую формулу",
                      command=self.calc_empirical, width=260, fg_color="#8e44ad").pack(side="left", padx=5)
        ctk.CTkButton(emp_frame, text="Удалить последний",
                      command=self._remove_empirical_row, width=150, fg_color="#c0392b").pack(side="left", padx=5)

        self.empirical_frame = emp_frame

    def _add_empirical_row(self):
        """Добавляет строку ввода для элемента в эмпирическую формулу."""
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=30, pady=2)

        el_entry = ctk.CTkEntry(row, width=80, placeholder_text="Символ", font=("Consolas", 13))
        el_entry.pack(side="left", padx=(0, 5))

        ctk.CTkLabel(row, text="%", font=("Arial", 12)).pack(side="left", padx=(0, 5))

        pct_entry = ctk.CTkEntry(row, width=120, placeholder_text="напр. 40.00", font=("Consolas", 13))
        pct_entry.pack(side="left", padx=(0, 5))

        self.empirical_entries.append((row, el_entry, pct_entry))
        if len(self.empirical_entries) > 1:
            # Подвинем кнопки вниз
            if hasattr(self, 'empirical_frame') and self.empirical_frame.winfo_exists():
                self.empirical_frame.pack_forget()
                self.empirical_frame.pack(fill="x", padx=20, pady=5)

    def _remove_empirical_row(self):
        """Удаляет последнюю строку ввода элемента."""
        if len(self.empirical_entries) > 2:
            row, _, _ = self.empirical_entries.pop()
            row.destroy()

    def calc_empirical(self):
        """Вычисляет эмпирическую формулу по введённым массовым процентам."""
        percentages = {}
        has_error = False

        for row_idx, (row, el_entry, pct_entry) in enumerate(self.empirical_entries):
            el = el_entry.get().strip()
            pct_str = pct_entry.get().strip()

            if not el:
                continue

            try:
                pct = float(pct_str)
            except (ValueError, TypeError):
                self.result_box.delete("0.0", "end")
                self.result_box.insert("0.0", f"Ошибка: неверное значение процента в строке {row_idx + 1}.\n")
                has_error = True
                break

            if pct <= 0:
                self.result_box.delete("0.0", "end")
                self.result_box.insert("0.0", f"Ошибка: процент должен быть > 0 в строке {row_idx + 1}.\n")
                has_error = True
                break

            percentages[el] = pct

        if has_error:
            return

        if len(percentages) < 2:
            self.result_box.delete("0.0", "end")
            self.result_box.insert("0.0", "Ошибка: необходимо минимум 2 элемента.\n")
            return

        try:
            empirical = FormulaParser.empirical_formula_from_percentages(percentages)
            self.result_box.delete("0.0", "end")

            total_pct = sum(percentages.values())
            text = "=== ЭМПИРИЧЕСКАЯ ФОРМУЛА ===\n\n"
            text += f" Исходные данные:\n"
            for el, pct in percentages.items():
                el_ru = ELEMENTS_RU.get(el, el)
                text += f"   {el} ({el_ru}): {pct:.2f}%\n"
            text += f"   Сумма: {total_pct:.2f}%\n\n"
            text += f" {'=' * 30}\n"
            text += f" Эмпирическая формула: {empirical}\n"
            text += f" {'=' * 30}\n"

            self.result_box.insert("0.0", text)
            HistoryManager.add("Эмпирическая формула", empirical)
        except Exception as e:
            self.result_box.delete("0.0", "end")
            self.result_box.insert("0.0", f"Ошибка: {str(e)}\n")


class AdvancedSolutionsTab(ctk.CTkFrame):
    """Вкладка расширенных расчётов растворов (с под-вкладками)."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        tabview = ctk.CTkTabview(self, fg_color=("#2b2b2b", "#2b2b2b"))
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # === Под-вкладка 1: Молярность / Моляльность ===
        tab_mol = tabview.add("Молярность / Моляльность")
        self._build_molarity_molality(tab_mol)

        # === Под-вкладка 2: Нормальность ===
        tab_norm = tabview.add("Нормальность")
        self._build_normality(tab_norm)

        # === Под-вкладка 3: Массовая/Мольная доля ===
        tab_frac = tabview.add("Массовая/Мольная доля")
        self._build_fractions(tab_frac)

        # === Под-вкладка 4: Смешивание растворов ===
        tab_mix = tabview.add("Смешивание растворов")
        self._build_mixing(tab_mix)

        # === Под-вкладка 5: Серийное разбавление ===
        tab_serial = tabview.add("Серийное разбавление")
        self._build_serial_dilution(tab_serial)

        # === Под-вкладка 6: Конвертер концентраций ===
        tab_conv = tabview.add("Конвертер концентраций")
        self._build_converter(tab_conv)

    # ---------- Под-вкладка 1: Молярность / Моляльность ----------
    def _build_molarity_molality(self, parent):
        card = CardFrame(parent, title="Молярность / Моляльность",
                         desc="C = m / (M \u00b7 V)   |   b = m / (M \u00b7 m_растворителя)")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        labels_fields = [
            ("Масса вещества (г):", "mass", "5.0"),
            ("Молярная масса (г/моль):", "mw", "58.44"),
            ("Объём раствора (л):", "volume", "0.5"),
            ("Масса растворителя (кг):", "solvent", "0.1"),
        ]
        self.mm_entries = {}
        for i, (label, key, default) in enumerate(labels_fields):
            ctk.CTkLabel(grid, text=label, font=("Arial", 11)).grid(row=i, column=0, padx=5, pady=4, sticky="e")
            e = ctk.CTkEntry(grid, width=140)
            e.grid(row=i, column=1, padx=5, pady=4)
            e.insert(0, default)
            self.mm_entries[key] = e

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=8)
        ctk.CTkButton(btn_frame, text="Молярность C = m/(M\u00b7V)", command=self._calc_molarity,
                      width=220, fg_color="#2980b9").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Моляльность b = m/(M\u00b7m)", command=self._calc_molality,
                      width=220, fg_color="#27ae60").pack(side="left", padx=5)

        self.mm_result = ResultLabel(card, text="Результат появится здесь")
        self.mm_result.pack(pady=10)

    def _calc_molarity(self):
        try:
            mass = float(self.mm_entries["mass"].get())
            mw = float(self.mm_entries["mw"].get())
            vol = float(self.mm_entries["volume"].get())
            result = SolutionCalculator.molarity(mass, mw, vol)
            self.mm_result.configure(text=f"C = {result:.4f} моль/л", text_color="#4facfe")
            HistoryManager.add("Молярность", f"{result:.4f} М (m={mass}г, M={mw}, V={vol}л)")
        except Exception as e:
            self.mm_result.configure(text=f"Ошибка: {e}", text_color="red")

    def _calc_molality(self):
        try:
            mass = float(self.mm_entries["mass"].get())
            mw = float(self.mm_entries["mw"].get())
            solvent = float(self.mm_entries["solvent"].get())
            result = SolutionCalculator.molality(mass, mw, solvent)
            self.mm_result.configure(text=f"b = {result:.4f} моль/кг", text_color="#2ecc71")
            HistoryManager.add("Моляльность", f"{result:.4f} m (m={mass}г, M={mw}, m_solv={solvent}кг)")
        except Exception as e:
            self.mm_result.configure(text=f"Ошибка: {e}", text_color="red")

    # ---------- Под-вкладка 2: Нормальность ----------
    def _build_normality(self, parent):
        card = CardFrame(parent, title="Нормальность", desc="N = C \u00b7 n (фактор эквивалентности)")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(grid, text="Молярность C (моль/л):", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.norm_c = ctk.CTkEntry(grid, width=140)
        self.norm_c.grid(row=0, column=1, padx=5, pady=5)
        self.norm_c.insert(0, "1.0")

        ctk.CTkLabel(grid, text="Фактор эквивалентности n:", font=("Arial", 11)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.norm_n = ctk.CTkEntry(grid, width=140)
        self.norm_n.grid(row=1, column=1, padx=5, pady=5)
        self.norm_n.insert(0, "2")

        ctk.CTkButton(card, text="N = C \u00b7 n", command=self._calc_normality,
                      width=150, fg_color="#e67e22").pack(pady=10)

        self.norm_result = ResultLabel(card, text="-")
        self.norm_result.pack(pady=10)

    def _calc_normality(self):
        try:
            c = float(self.norm_c.get())
            n = float(self.norm_n.get())
            result = SolutionCalculator.normality(c, n)
            self.norm_result.configure(text=f"N = {result:.4f} моль-экв/л", text_color="#e67e22")
            HistoryManager.add("Нормальность", f"{result:.4f} Н (C={c}, n={n})")
        except Exception as e:
            self.norm_result.configure(text=f"Ошибка: {e}", text_color="red")

    # ---------- Под-вкладка 3: Массовая/Мольная доля ----------
    def _build_fractions(self, parent):
        card = CardFrame(parent, title="Массовая и мольная доля",
                         desc="w = m_в-ва / m_раствора  |  x = n_в-ва / (n_в-ва + n_растворителя)")

        # Массовая доля
        mf = ctk.CTkFrame(card, fg_color="transparent")
        mf.pack(fill="x", padx=20, pady=(10, 5))
        ctk.CTkLabel(mf, text="Массовая доля:", font=("Arial", 12, "bold"), text_color="#4facfe").pack(anchor="w")

        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=2)
        ctk.CTkLabel(row1, text="m_растворённого (г):").pack(side="left", padx=5)
        self.mf_solute = ctk.CTkEntry(row1, width=100)
        self.mf_solute.pack(side="left", padx=5)
        self.mf_solute.insert(0, "10")
        ctk.CTkLabel(row1, text="m_раствора (г):").pack(side="left", padx=(15, 5))
        self.mf_solution = ctk.CTkEntry(row1, width=100)
        self.mf_solution.pack(side="left", padx=5)
        self.mf_solution.insert(0, "100")

        ctk.CTkButton(card, text="Массовая доля", command=self._calc_mass_fraction,
                      width=140, fg_color="#2980b9").pack(anchor="w", padx=25, pady=3)

        self.mf_result = ctk.CTkLabel(card, text="w = -", font=("Consolas", 14, "bold"), text_color="#4facfe")
        self.mf_result.pack(anchor="w", padx=30, pady=3)

        # Разделитель
        ctk.CTkFrame(card, height=2, fg_color="gray40").pack(fill="x", padx=20, pady=10)

        # Мольная доля
        xf = ctk.CTkFrame(card, fg_color="transparent")
        xf.pack(fill="x", padx=20, pady=(5, 5))
        ctk.CTkLabel(xf, text="Мольная доля:", font=("Arial", 12, "bold"), text_color="#2ecc71").pack(anchor="w")

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=2)
        ctk.CTkLabel(row2, text="n_растворённого (моль):").pack(side="left", padx=5)
        self.xf_solute = ctk.CTkEntry(row2, width=100)
        self.xf_solute.pack(side="left", padx=5)
        self.xf_solute.insert(0, "0.5")
        ctk.CTkLabel(row2, text="n_растворителя (моль):").pack(side="left", padx=(15, 5))
        self.xf_solvent = ctk.CTkEntry(row2, width=100)
        self.xf_solvent.pack(side="left", padx=5)
        self.xf_solvent.insert(0, "5.0")

        ctk.CTkButton(card, text="Мольная доля", command=self._calc_mole_fraction,
                      width=140, fg_color="#27ae60").pack(anchor="w", padx=25, pady=3)

        self.xf_result = ctk.CTkLabel(card, text="x = -", font=("Consolas", 14, "bold"), text_color="#2ecc71")
        self.xf_result.pack(anchor="w", padx=30, pady=3)

    def _calc_mass_fraction(self):
        try:
            ms = float(self.mf_solute.get())
            msl = float(self.mf_solution.get())
            result = SolutionCalculator.mass_fraction(ms, msl)
            pct = result * 100
            self.mf_result.configure(text=f"w = {result:.6f}  ({pct:.2f}%)", text_color="#4facfe")
            HistoryManager.add("Массовая доля", f"{pct:.2f}%")
        except Exception as e:
            self.mf_result.configure(text=f"Ошибка: {e}", text_color="red")

    def _calc_mole_fraction(self):
        try:
            ns = float(self.xf_solute.get())
            nsv = float(self.xf_solvent.get())
            result = SolutionCalculator.mole_fraction(ns, nsv)
            self.xf_result.configure(text=f"x = {result:.6f}  ({result * 100:.2f}%)", text_color="#2ecc71")
            HistoryManager.add("Мольная доля", f"{result:.4f}")
        except Exception as e:
            self.xf_result.configure(text=f"Ошибка: {e}", text_color="red")

    # ---------- Под-вкладка 4: Смешивание растворов ----------
    def _build_mixing(self, parent):
        card = CardFrame(parent, title="Смешивание растворов",
                         desc="C_смеси = (C1\u00b7V1 + C2\u00b7V2) / (V1 + V2)")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        self.mix_entries = {}
        fields = [("C1 (моль/л):", "c1", "2.0"), ("V1 (л):", "v1", "0.5"),
                  ("C2 (моль/л):", "c2", "0.5"), ("V2 (л):", "v2", "1.0")]
        for i, (label, key, default) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            ctk.CTkLabel(grid, text=label, font=("Arial", 11)).grid(row=row, column=col, padx=5, pady=5, sticky="e")
            e = ctk.CTkEntry(grid, width=110)
            e.grid(row=row, column=col + 1, padx=5, pady=5)
            e.insert(0, default)
            self.mix_entries[key] = e

        ctk.CTkButton(card, text="Смешать", command=self._calc_mixing,
                      width=140, fg_color="#9b59b6").pack(pady=10)

        self.mix_result = ResultLabel(card, text="Результат появится здесь")
        self.mix_result.pack(pady=10)

    def _calc_mixing(self):
        try:
            c1 = float(self.mix_entries["c1"].get())
            v1 = float(self.mix_entries["v1"].get())
            c2 = float(self.mix_entries["c2"].get())
            v2 = float(self.mix_entries["v2"].get())
            res = SolutionCalculator.mixing_concentrations(c1, v1, c2, v2)
            text = (f"C_смеси = {res['концентрация_смеси']:.4f} моль/л\n"
                    f"V_общ = {res['общий_объём_л']:.4f} л\n"
                    f"n_общ = {res['общее_кол_во_моль']:.4f} моль")
            self.mix_result.configure(text=text, text_color="#4facfe")
            HistoryManager.add("Смешивание", f"C={res['концентрация_смеси']:.4f} M, V={res['общий_объём_л']:.4f} л")
        except Exception as e:
            self.mix_result.configure(text=f"Ошибка: {e}", text_color="red")

    # ---------- Под-вкладка 5: Серийное разбавление ----------
    def _build_serial_dilution(self, parent):
        card = CardFrame(parent, title="Серийное разбавление",
                         desc="C_n = C_0 \u00b7 (V_переноса / V_колбы)^n")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        self.sd_entries = {}
        fields = [("C_начальная (моль/л):", "c0", "1.0"),
                  ("V_колбы (л):", "v_flask", "0.1"),
                  ("V_переноса (л):", "v_transfer", "0.01"),
                  ("Число шагов:", "n_steps", "5")]
        for i, (label, key, default) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            ctk.CTkLabel(grid, text=label, font=("Arial", 11)).grid(row=row, column=col, padx=5, pady=5, sticky="e")
            e = ctk.CTkEntry(grid, width=110)
            e.grid(row=row, column=col + 1, padx=5, pady=5)
            e.insert(0, default)
            self.sd_entries[key] = e

        ctk.CTkButton(card, text="Рассчитать", command=self._calc_serial_dilution,
                      width=140, fg_color="#e74c3c").pack(pady=10)

        self.sd_result = ResultLabel(card, text="Результат появится здесь")
        self.sd_result.pack(pady=(10, 5))

        # Scrollable area for table
        self.sd_scroll = ctk.CTkScrollableFrame(card, height=180, fg_color="transparent")
        self.sd_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    def _calc_serial_dilution(self):
        try:
            c0 = float(self.sd_entries["c0"].get())
            v_flask = float(self.sd_entries["v_flask"].get())
            v_transfer = float(self.sd_entries["v_transfer"].get())
            n_steps = int(float(self.sd_entries["n_steps"].get()))

            results = SolutionCalculator.serial_dilution(c0, v_flask, v_transfer, n_steps)

            # Очищаем предыдущие результаты
            for w in self.sd_scroll.winfo_children():
                w.destroy()

            # Заголовок таблицы
            header = ctk.CTkFrame(self.sd_scroll, fg_color="gray30")
            header.pack(fill="x", pady=2)
            ctk.CTkLabel(header, text="Шаг", width=80, font=("Arial", 11, "bold")).pack(side="left", padx=5)
            ctk.CTkLabel(header, text="Концентрация (моль/л)", font=("Arial", 11, "bold")).pack(side="left", padx=5)

            for step, conc in results:
                row = ctk.CTkFrame(self.sd_scroll, fg_color=("#2b2b2b", "#2b2b2b"))
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(row, text=str(step), width=80, font=("Consolas", 11)).pack(side="left", padx=5)
                ctk.CTkLabel(row, text=f"{conc:.6e}", font=("Consolas", 11),
                             text_color="#4facfe").pack(side="left", padx=5)

            self.sd_result.configure(
                text=f"Итого шагов: {len(results) - 1} | Финальная C = {results[-1][1]:.4e} М",
                text_color="#e74c3c")
            HistoryManager.add("Серийное разбавление",
                               f"{n_steps} шагов: {results[0][1]:.2f}M \u2192 {results[-1][1]:.4e}M")
        except Exception as e:
            self.sd_result.configure(text=f"Ошибка: {e}", text_color="red")

    # ---------- Под-вкладка 6: Конвертер концентраций ----------
    def _build_converter(self, parent):
        card = CardFrame(parent, title="Конвертер концентраций",
                         desc="Перевод между M, m, %, ppm, N, g/L")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        # Value
        ctk.CTkLabel(grid, text="Значение:", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.conv_value = ctk.CTkEntry(grid, width=140)
        self.conv_value.grid(row=0, column=1, padx=5, pady=5)
        self.conv_value.insert(0, "1.0")

        # From type
        ctk.CTkLabel(grid, text="Из:", font=("Arial", 11)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.conv_from = ctk.CTkOptionMenu(grid, values=["M", "m", "%", "ppm", "N", "g/L"], width=140)
        self.conv_from.grid(row=1, column=1, padx=5, pady=5)

        # To type
        ctk.CTkLabel(grid, text="В:", font=("Arial", 11)).grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.conv_to = ctk.CTkOptionMenu(grid, values=["M", "m", "%", "ppm", "N", "g/L"], width=140)
        self.conv_to.grid(row=2, column=1, padx=5, pady=5)
        self.conv_to.set("g/L")

        # Optional MW
        ctk.CTkLabel(grid, text="Молярная масса (опц.):", font=("Arial", 11)).grid(row=0, column=2, padx=(20, 5), pady=5, sticky="e")
        self.conv_mw = ctk.CTkEntry(grid, width=120)
        self.conv_mw.grid(row=0, column=3, padx=5, pady=5)
        self.conv_mw.insert(0, "58.44")

        # Optional density
        ctk.CTkLabel(grid, text="Плотность г/мл (опц.):", font=("Arial", 11)).grid(row=1, column=2, padx=(20, 5), pady=5, sticky="e")
        self.conv_density = ctk.CTkEntry(grid, width=120)
        self.conv_density.grid(row=1, column=3, padx=5, pady=5)
        self.conv_density.insert(0, "1.0")

        # Optional n_factor
        ctk.CTkLabel(grid, text="n-фактор (опц.):", font=("Arial", 11)).grid(row=2, column=2, padx=(20, 5), pady=5, sticky="e")
        self.conv_nfactor = ctk.CTkEntry(grid, width=120)
        self.conv_nfactor.grid(row=2, column=3, padx=5, pady=5)
        self.conv_nfactor.insert(0, "1")

        ctk.CTkButton(card, text="Перевести", command=self._calc_convert,
                      width=140, fg_color="#16a085").pack(pady=10)

        self.conv_result = ResultLabel(card, text="Результат появится здесь")
        self.conv_result.pack(pady=10)

    def _calc_convert(self):
        try:
            value = float(self.conv_value.get())
            from_type = self.conv_from.get()
            to_type = self.conv_to.get()

            mw = None
            density = None
            n_factor = None

            mw_str = self.conv_mw.get().strip()
            if mw_str:
                mw = float(mw_str)

            dens_str = self.conv_density.get().strip()
            if dens_str:
                density = float(dens_str)

            nf_str = self.conv_nfactor.get().strip()
            if nf_str:
                n_factor = float(nf_str)

            result = SolutionCalculator.convert_concentration(value, from_type, to_type,
                                                              mw=mw, density=density, n_factor=n_factor)
            self.conv_result.configure(text=f"{value} {from_type} = {result:.6f} {to_type}",
                                       text_color="#16a085")
            HistoryManager.add("Конвертация", f"{value} {from_type} \u2192 {result:.6f} {to_type}")
        except Exception as e:
            self.conv_result.configure(text=f"Ошибка: {e}", text_color="red")


class AdvancedAcidBaseTab(ctk.CTkFrame):
    """Вкладка расширенных кислотно-основных расчётов (с под-вкладками)."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        tabview = ctk.CTkTabview(self, fg_color=("#2b2b2b", "#2b2b2b"))
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        tab1 = tabview.add("Сильная к-та / основание")
        self._build_strong(tab1)

        tab2 = tabview.add("Слабая кислота")
        self._build_weak_acid(tab2)

        tab3 = tabview.add("Слабое основание")
        self._build_weak_base(tab3)

        tab4 = tabview.add("Полипротные кислоты")
        self._build_polyprotic(tab4)

        tab5 = tabview.add("Гидролиз солей")
        self._build_salt_hydrolysis(tab5)

        tab6 = tabview.add("Буфер (Г-Х)")
        self._build_buffer(tab6)

        tab7 = tabview.add("Ka / Kb конвертер")
        self._build_ka_kb_converter(tab7)

    # ---------- Под-вкладка 1: Сильная кислота/основание ----------
    def _build_strong(self, parent):
        card = CardFrame(parent, title="Сильная кислота / основание",
                         desc="pH = -lg(C) для кислоты  |  pH = 14 + lg(C) для основания")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(grid, text="Концентрация (моль/л):", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.strong_c = ctk.CTkEntry(grid, width=140)
        self.strong_c.grid(row=0, column=1, padx=5, pady=5)
        self.strong_c.insert(0, "0.01")

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=8)
        ctk.CTkButton(btn_frame, text="pH кислоты (сильной)", command=self._calc_strong_acid,
                      width=200, fg_color="#e74c3c").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="pH основания (сильного)", command=self._calc_strong_base,
                      width=200, fg_color="#2980b9").pack(side="left", padx=5)

        self.strong_result = ResultLabel(card, text="pH = -")
        self.strong_result.pack(pady=10)

    def _ph_color(self, ph):
        """Возвращает цвет в зависимости от pH."""
        try:
            ph_val = float(ph)
            if ph_val < 3:
                return "#e74c3c"
            elif ph_val < 5.5:
                return "#e67e22"
            elif ph_val < 6.5:
                return "#f1c40f"
            elif ph_val < 7.5:
                return "#2ecc71"
            elif ph_val < 9:
                return "#1abc9c"
            else:
                return "#2980b9"
        except (ValueError, TypeError):
            return "#4facfe"

    def _calc_strong_acid(self):
        try:
            c = float(self.strong_c.get())
            ph = AcidBaseCalculator.strong_acid_ph(c)
            color = self._ph_color(ph)
            self.strong_result.configure(text=f"pH = {ph:.4f}", text_color=color)
            HistoryManager.add("pH сильной к-ты", f"pH={ph:.4f} (C={c} M)")
        except Exception as e:
            self.strong_result.configure(text=f"Ошибка: {e}", text_color="red")

    def _calc_strong_base(self):
        try:
            c = float(self.strong_c.get())
            ph = AcidBaseCalculator.strong_base_ph(c)
            color = self._ph_color(ph)
            self.strong_result.configure(text=f"pH = {ph:.4f}", text_color=color)
            HistoryManager.add("pH сильн. основания", f"pH={ph:.4f} (C={c} M)")
        except Exception as e:
            self.strong_result.configure(text=f"Ошибка: {e}", text_color="red")

    # ---------- Под-вкладка 2: Слабая кислота ----------
    def _build_weak_acid(self, parent):
        card = CardFrame(parent, title="Слабая кислота",
                         desc="[H+] = \u221a(Ka \u00b7 C), при C/Ka < 100 решается квадратное уравнение")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(grid, text="Концентрация (моль/л):", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.wa_c = ctk.CTkEntry(grid, width=180)
        self.wa_c.grid(row=0, column=1, padx=5, pady=5)
        self.wa_c.insert(0, "0.1")

        ctk.CTkLabel(grid, text="Ka:", font=("Arial", 11)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.wa_ka = ctk.CTkEntry(grid, width=180, placeholder_text="напр. 1.74e-5")
        self.wa_ka.grid(row=1, column=1, padx=5, pady=5)
        self.wa_ka.insert(0, "1.74e-5")

        # Быстрые Ka
        quick_frame = ctk.CTkFrame(card, fg_color="transparent")
        quick_frame.pack(fill="x", padx=20, pady=2)
        ctk.CTkLabel(quick_frame, text="Быстрый выбор:", font=("Arial", 10), text_color="gray60").pack(side="left", padx=5)
        for name, ka in [("CH3COOH", "1.74e-5"), ("HCOOH", "1.77e-4"), ("HCN", "6.2e-10"), ("HF", "6.6e-4")]:
            ctk.CTkButton(quick_frame, text=name, width=80, height=26, font=("Arial", 9),
                          command=lambda n=name, k=ka: self._set_wa_ka(k),
                          fg_color="#34495e").pack(side="left", padx=2)

        ctk.CTkButton(card, text="pH слабой кислоты", command=self._calc_weak_acid,
                      width=180, fg_color="#e74c3c").pack(pady=10)

        self.wa_result = ctk.CTkTextbox(card, height=100, font=("Consolas", 12), wrap="word",
                                        fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.wa_result.pack(fill="x", padx=15, pady=(5, 15))

    def _set_wa_ka(self, ka_val):
        self.wa_ka.delete(0, "end")
        self.wa_ka.insert(0, ka_val)

    def _calc_weak_acid(self):
        try:
            c = float(self.wa_c.get())
            ka = float(self.wa_ka.get())
            ph = AcidBaseCalculator.weak_acid_ph(c, ka)
            h_conc = 10 ** (-ph)
            dissoc = (h_conc / c) * 100

            color = self._ph_color(ph)
            text = f"  pH = {ph:.4f}\n  [H+] = {h_conc:.4e} моль/л\n  \u03b1 (степень дисс.) = {dissoc:.4f}%"
            self.wa_result.delete("0.0", "end")
            self.wa_result.insert("0.0", text)
            HistoryManager.add("pH слабой к-ты", f"pH={ph:.4f}, \u03b1={dissoc:.2f}%")
        except Exception as e:
            self.wa_result.delete("0.0", "end")
            self.wa_result.insert("0.0", f"Ошибка: {e}\n")

    # ---------- Под-вкладка 3: Слабое основание ----------
    def _build_weak_base(self, parent):
        card = CardFrame(parent, title="Слабое основание",
                         desc="[OH-] = \u221a(Kb \u00b7 C), pOH = -lg([OH-]), pH = 14 - pOH")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(grid, text="Концентрация (моль/л):", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.wb_c = ctk.CTkEntry(grid, width=180)
        self.wb_c.grid(row=0, column=1, padx=5, pady=5)
        self.wb_c.insert(0, "0.1")

        ctk.CTkLabel(grid, text="Kb:", font=("Arial", 11)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.wb_kb = ctk.CTkEntry(grid, width=180, placeholder_text="напр. 1.74e-5")
        self.wb_kb.grid(row=1, column=1, padx=5, pady=5)
        self.wb_kb.insert(0, "1.8e-5")

        ctk.CTkButton(card, text="pH слабого основания", command=self._calc_weak_base,
                      width=200, fg_color="#2980b9").pack(pady=10)

        self.wb_result = ctk.CTkTextbox(card, height=100, font=("Consolas", 12), wrap="word",
                                        fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.wb_result.pack(fill="x", padx=15, pady=(5, 15))

    def _calc_weak_base(self):
        try:
            c = float(self.wb_c.get())
            kb = float(self.wb_kb.get())
            ph = AcidBaseCalculator.weak_base_ph(c, kb)
            oh_conc = 10 ** (-(14 - ph))
            dissoc = (oh_conc / c) * 100

            color = self._ph_color(ph)
            text = f"  pH = {ph:.4f}\n  [OH-] = {oh_conc:.4e} моль/л\n  \u03b1 (степень дисс.) = {dissoc:.4f}%"
            self.wb_result.delete("0.0", "end")
            self.wb_result.insert("0.0", text)
            HistoryManager.add("pH слаб. основания", f"pH={ph:.4f}, \u03b1={dissoc:.2f}%")
        except Exception as e:
            self.wb_result.delete("0.0", "end")
            self.wb_result.insert("0.0", f"Ошибка: {e}\n")

    # ---------- Под-вкладка 4: Полипротные кислоты ----------
    def _build_polyprotic(self, parent):
        card = CardFrame(parent, title="Полипротные кислоты",
                         desc="Расчёт pH и доминирующего вида (диссоциация по ступеням)")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        fields = [("Концентрация (моль/л):", "c", "0.1"),
                  ("Ka1:", "ka1", "7.1e-3"),
                  ("Ka2:", "ka2", "6.3e-8"),
                  ("Ka3 (опц.):", "ka3", "4.5e-13")]
        self.poly_entries = {}
        for i, (label, key, default) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            ctk.CTkLabel(grid, text=label, font=("Arial", 11)).grid(row=row, column=col, padx=5, pady=5, sticky="e")
            e = ctk.CTkEntry(grid, width=140)
            e.grid(row=row, column=col + 1, padx=5, pady=5)
            e.insert(0, default)
            self.poly_entries[key] = e

        # Быстрый выбор
        quick_frame = ctk.CTkFrame(card, fg_color="transparent")
        quick_frame.pack(fill="x", padx=20, pady=2)
        ctk.CTkLabel(quick_frame, text="Быстрый выбор:", font=("Arial", 10), text_color="gray60").pack(side="left", padx=5)
        for name, k1, k2, k3 in [
            ("H2SO3", "1.3e-2", "6.3e-8", ""),
            ("H3PO4", "7.1e-3", "6.3e-8", "4.5e-13"),
            ("H2CO3", "4.3e-7", "4.7e-11", ""),
            ("H2S", "1.0e-7", "1.3e-13", ""),
        ]:
            ctk.CTkButton(quick_frame, text=name, width=70, height=26, font=("Arial", 9),
                          command=lambda a=k1, b=k2, c=k3: self._set_poly(a, b, c),
                          fg_color="#34495e").pack(side="left", padx=2)

        ctk.CTkButton(card, text="Рассчитать pH", command=self._calc_polyprotic,
                      width=160, fg_color="#e67e22").pack(pady=10)

        self.poly_result = ctk.CTkTextbox(card, height=100, font=("Consolas", 12), wrap="word",
                                          fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.poly_result.pack(fill="x", padx=15, pady=(5, 15))

    def _set_poly(self, ka1, ka2, ka3):
        self.poly_entries["ka1"].delete(0, "end")
        self.poly_entries["ka1"].insert(0, ka1)
        self.poly_entries["ka2"].delete(0, "end")
        self.poly_entries["ka2"].insert(0, ka2)
        self.poly_entries["ka3"].delete(0, "end")
        self.poly_entries["ka3"].insert(0, ka3)

    def _calc_polyprotic(self):
        try:
            c = float(self.poly_entries["c"].get())
            ka1 = float(self.poly_entries["ka1"].get())
            ka2 = float(self.poly_entries["ka2"].get())
            ka3_str = self.poly_entries["ka3"].get().strip()
            ka_values = [ka1, ka2]
            if ka3_str:
                ka_values.append(float(ka3_str))

            res = AcidBaseCalculator.polyprotic_acid_ph(c, ka_values)

            text = f"  pH = {res['ph']:.4f}\n"
            text += f"  Доминирующий вид: {res['доминирующий_вид']}\n"
            text += f"  Число ступеней диссоциации: {len(ka_values)}\n"
            for i, ka in enumerate(ka_values, 1):
                pka = -math.log10(ka)
                text += f"  pKa{i} = {pka:.4f}  (Ka{i} = {ka:.2e})\n"

            self.poly_result.delete("0.0", "end")
            self.poly_result.insert("0.0", text)
            HistoryManager.add("Полипротная к-та", f"pH={res['ph']:.4f}, {res['доминирующий_вид']}")
        except Exception as e:
            self.poly_result.delete("0.0", "end")
            self.poly_result.insert("0.0", f"Ошибка: {e}\n")

    # ---------- Под-вкладка 5: Гидролиз солей ----------
    def _build_salt_hydrolysis(self, parent):
        card = CardFrame(parent, title="Гидролиз солей",
                         desc="Определение типа гидролиза и среды раствора")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        # Тип катиона
        ctk.CTkLabel(grid, text="Тип катиона:", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.hydro_cation = ctk.CTkOptionMenu(grid, width=300,
                                              values=["Сильное основание (Na+, K+)",
                                                      "Слабое основание (NH4+, Al3+)",
                                                      "Другое"])
        self.hydro_cation.grid(row=0, column=1, padx=5, pady=5)

        # Тип аниона
        ctk.CTkLabel(grid, text="Тип аниона:", font=("Arial", 11)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.hydro_anion = ctk.CTkOptionMenu(grid, width=300,
                                             values=["Сильная кислота (Cl-, NO3-)",
                                                     "Слабая кислота (CH3COO-, CO3^2-)",
                                                     "Другое"])
        self.hydro_anion.grid(row=1, column=1, padx=5, pady=5)

        # Ka, Kb опционально
        opt_frame = ctk.CTkFrame(card, fg_color="transparent")
        opt_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(opt_frame, text="Ka (опц.):", font=("Arial", 11)).pack(side="left", padx=5)
        self.hydro_ka = ctk.CTkEntry(opt_frame, width=130, placeholder_text="напр. 1.74e-5")
        self.hydro_ka.pack(side="left", padx=5)
        ctk.CTkLabel(opt_frame, text="Kb (опц.):", font=("Arial", 11)).pack(side="left", padx=(20, 5))
        self.hydro_kb = ctk.CTkEntry(opt_frame, width=130, placeholder_text="напр. 1.8e-5")
        self.hydro_kb.pack(side="left", padx=5)

        ctk.CTkButton(card, text="Рассчитать", command=self._calc_salt_hydrolysis,
                      width=160, fg_color="#8e44ad").pack(pady=10)

        self.hydro_result = ctk.CTkTextbox(card, height=120, font=("Consolas", 12), wrap="word",
                                           fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.hydro_result.pack(fill="x", padx=15, pady=(5, 15))

    def _calc_salt_hydrolysis(self):
        try:
            cat_text = self.hydro_cation.get()
            an_text = self.hydro_anion.get()

            # Определяем тип катиона
            if "Сильное" in cat_text:
                cation = "сильный"
            elif "Слабое" in cat_text:
                cation = "слабый"
            else:
                cation = "другой"

            # Определяем тип аниона
            if "Сильная" in an_text:
                anion = "сильный"
            elif "Слабая" in an_text:
                anion = "слабый"
            else:
                anion = "другой"

            ka = None
            kb = None
            ka_str = self.hydro_ka.get().strip()
            if ka_str:
                ka = float(ka_str)
            kb_str = self.hydro_kb.get().strip()
            if kb_str:
                kb = float(kb_str)

            res = AcidBaseCalculator.salt_hydrolysis_ph(cation, anion, Ka=ka, Kb=kb)

            text = f"  Тип: {res['тип']}\n"
            text += f"  Гидролиз: {res['гидролиз']}\n"
            if isinstance(res.get('ph'), (int, float)):
                text += f"  pH \u2248 {res['ph']:.2f}\n"
            else:
                text += f"  pH: {res['ph']}\n"
            text += f"  Среда: {res['среда']}\n"

            if "Kb_соли" in res:
                text += f"  Kb соли: {res['Kb_соли']}\n"
            if "Ka_соли" in res:
                text += f"  Ka соли: {res['Ka_соли']}\n"

            self.hydro_result.delete("0.0", "end")
            self.hydro_result.insert("0.0", text)
            HistoryManager.add("Гидролиз соли", f"{res['тип']} | {res['среда']}")
        except Exception as e:
            self.hydro_result.delete("0.0", "end")
            self.hydro_result.insert("0.0", f"Ошибка: {e}\n")

    # ---------- Под-вкладка 6: Буфер (Гендерсон-Хассельбах) ----------
    def _build_buffer(self, parent):
        card = CardFrame(parent, title="Буфер (Гендерсон-Хассельбах)",
                         desc="pH = pKa + lg([A-]/[HA])")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        fields = [("pKa:", "pka", "4.75"),
                  ("[Кислота] HA (моль/л):", "acid", "0.1"),
                  ("[Соль] A- (моль/л):", "base", "0.1")]
        self.buf_entries = {}
        for i, (label, key, default) in enumerate(fields):
            ctk.CTkLabel(grid, text=label, font=("Arial", 11)).grid(row=i, column=0, padx=5, pady=5, sticky="e")
            e = ctk.CTkEntry(grid, width=160)
            e.grid(row=i, column=1, padx=5, pady=5)
            e.insert(0, default)
            self.buf_entries[key] = e

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(pady=8)
        ctk.CTkButton(btn_frame, text="pH буфера", command=self._calc_buffer_ph,
                      width=160, fg_color="#2980b9").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Ёмкость буфера", command=self._calc_buffer_capacity,
                      width=180, fg_color="#16a085").pack(side="left", padx=5)

        self.buf_result = ctk.CTkTextbox(card, height=120, font=("Consolas", 12), wrap="word",
                                         fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.buf_result.pack(fill="x", padx=15, pady=(5, 15))

    def _calc_buffer_ph(self):
        try:
            pka = float(self.buf_entries["pka"].get())
            acid = float(self.buf_entries["acid"].get())
            base = float(self.buf_entries["base"].get())
            ph = AcidBaseCalculator.henderson_hasselbalch(pka, acid, base)
            color = self._ph_color(ph)
            ratio = base / acid
            text = f"  pH = {ph:.4f}\n"
            text += f"  pKa = {pka}\n"
            text += f"  [A-]/[HA] = {ratio:.4f}\n"
            self.buf_result.delete("0.0", "end")
            self.buf_result.insert("0.0", text)
            HistoryManager.add("Буфер pH", f"pH={ph:.4f} (pKa={pka})")
        except Exception as e:
            self.buf_result.delete("0.0", "end")
            self.buf_result.insert("0.0", f"Ошибка: {e}\n")

    def _calc_buffer_capacity(self):
        try:
            pka = float(self.buf_entries["pka"].get())
            acid = float(self.buf_entries["acid"].get())
            base = float(self.buf_entries["base"].get())
            res = AcidBaseCalculator.buffer_capacity(pka, acid, base)

            text = f"  Буферная ёмкость \u03b2 = {res['буферная_ёмкость']:.6f}\n"
            text += f"  pH (до добавления) = {res['pH_до_добавления']:.4f}\n"
            text += f"  \u0394pH (при +0.001 моль) = {res['изменение_pH']}\n"
            self.buf_result.delete("0.0", "end")
            self.buf_result.insert("0.0", text)
            HistoryManager.add("Буферная ёмкость", f"\u03b2={res['буферная_ёмкость']:.6f}")
        except Exception as e:
            self.buf_result.delete("0.0", "end")
            self.buf_result.insert("0.0", f"Ошибка: {e}\n")

    # ---------- Под-вкладка 7: Ka / Kb конвертер ----------
    def _build_ka_kb_converter(self, parent):
        card = CardFrame(parent, title="Ka / Kb конвертер",
                         desc="Ka \u2194 pKa, Kb = Kw/Ka, pKb = 14 - pKa")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(grid, text="Ka:", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.ck_ka = ctk.CTkEntry(grid, width=200, placeholder_text="напр. 1.74e-5")
        self.ck_ka.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="pKa:", font=("Arial", 11)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.ck_pka = ctk.CTkEntry(grid, width=200, placeholder_text="напр. 4.75")
        self.ck_pka.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkButton(card, text="Рассчитать всё", command=self._calc_ka_kb,
                      width=180, fg_color="#e67e22").pack(pady=10)

        self.ck_result = ctk.CTkTextbox(card, height=140, font=("Consolas", 12), wrap="word",
                                        fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.ck_result.pack(fill="x", padx=15, pady=(5, 15))

    def _calc_ka_kb(self):
        try:
            ka_str = self.ck_ka.get().strip()
            pka_str = self.ck_pka.get().strip()

            ka = None
            pka = None

            if ka_str:
                ka = float(ka_str)
                pka = AcidBaseCalculator.pka_from_ka(ka)
            elif pka_str:
                pka = float(pka_str)
                ka = AcidBaseCalculator.ka_from_pka(pka)
            else:
                self.ck_result.delete("0.0", "end")
                self.ck_result.insert("0.0", "Ошибка: введите Ka или pKa\n")
                return

            kb = AcidBaseCalculator.kb_from_ka(ka)
            pkb = AcidBaseCalculator.pkb_from_ka(ka)

            text = f"  Ka  = {ka:.6e}\n"
            text += f"  pKa = {pka:.4f}\n"
            text += f"  {'─' * 30}\n"
            text += f"  Kb  = {kb:.6e}\n"
            text += f"  pKb = {pkb:.4f}\n"
            text += f"  {'─' * 30}\n"
            text += f"  Ka \u00b7 Kb = {ka * kb:.4e} (должно быть \u2248 1e-14)\n"

            self.ck_result.delete("0.0", "end")
            self.ck_result.insert("0.0", text)
            HistoryManager.add("Ka/Kb конвертер", f"Ka={ka:.2e}, pKa={pka:.2f}, pKb={pkb:.2f}")
        except Exception as e:
            self.ck_result.delete("0.0", "end")
            self.ck_result.insert("0.0", f"Ошибка: {e}\n")


class ColligativeTab(ctk.CTkFrame):
    """Вкладка коллигативных свойств растворов (с под-вкладками)."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        self._solvent_names = list(ColligativeCalculator.SOLVENT_CONSTANTS.keys())

        tabview = ctk.CTkTabview(self, fg_color=("#2b2b2b", "#2b2b2b"))
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        tab1 = tabview.add("Повышение Т. кип.")
        self._build_boiling(tab1)

        tab2 = tabview.add("Понижение Т. зам.")
        self._build_freezing(tab2)

        tab3 = tabview.add("Осмотическое давление")
        self._build_osmotic(tab3)

        tab4 = tabview.add("Молярная масса")
        self._build_mw_colligative(tab4)

        tab5 = tabview.add("Закон Рауля")
        self._build_raoult(tab5)

    # ---------- Под-вкладка 1: Повышение Т. кип. ----------
    def _build_boiling(self, parent):
        card = CardFrame(parent, title="Повышение температуры кипения",
                         desc="\u0394Tb = Kb \u00b7 m")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(grid, text="Растворитель:", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.bp_solvent = ctk.CTkOptionMenu(grid, values=self._solvent_names, width=200)
        self.bp_solvent.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Моляльность (моль/кг):", font=("Arial", 11)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.bp_molality = ctk.CTkEntry(grid, width=200)
        self.bp_molality.grid(row=1, column=1, padx=5, pady=5)
        self.bp_molality.insert(0, "0.5")

        ctk.CTkButton(card, text="Рассчитать", command=self._calc_boiling,
                      width=160, fg_color="#e74c3c").pack(pady=10)

        self.bp_result = ctk.CTkTextbox(card, height=100, font=("Consolas", 12), wrap="word",
                                        fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.bp_result.pack(fill="x", padx=15, pady=(5, 15))

    def _calc_boiling(self):
        try:
            solvent = self.bp_solvent.get()
            molality = float(self.bp_molality.get())
            res = ColligativeCalculator.boiling_point_new(solvent, molality)

            text = f"  Растворитель: {res['растворитель']}\n"
            text += f"  Tb чистого: {res['Tb_чистого_растворителя']} °C\n"
            text += f"  \u0394Tb = {res['повышение_Т_кипения']} °C\n"
            text += f"  Tb раствора = {res['Tb_раствора']} °C\n"

            self.bp_result.delete("0.0", "end")
            self.bp_result.insert("0.0", text)
            HistoryManager.add("Т. кипения", f"Tb={res['Tb_раствора']} °C (\u0394Tb={res['повышение_Т_кипения']} °C)")
        except Exception as e:
            self.bp_result.delete("0.0", "end")
            self.bp_result.insert("0.0", f"Ошибка: {e}\n")

    # ---------- Под-вкладка 2: Понижение Т. зам. ----------
    def _build_freezing(self, parent):
        card = CardFrame(parent, title="Понижение температуры замерзания",
                         desc="\u0394Tf = Kf \u00b7 m")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(grid, text="Растворитель:", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.fp_solvent = ctk.CTkOptionMenu(grid, values=self._solvent_names, width=200)
        self.fp_solvent.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Моляльность (моль/кг):", font=("Arial", 11)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.fp_molality = ctk.CTkEntry(grid, width=200)
        self.fp_molality.grid(row=1, column=1, padx=5, pady=5)
        self.fp_molality.insert(0, "0.5")

        ctk.CTkButton(card, text="Рассчитать", command=self._calc_freezing,
                      width=160, fg_color="#2980b9").pack(pady=10)

        self.fp_result = ctk.CTkTextbox(card, height=100, font=("Consolas", 12), wrap="word",
                                        fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.fp_result.pack(fill="x", padx=15, pady=(5, 15))

    def _calc_freezing(self):
        try:
            solvent = self.fp_solvent.get()
            molality = float(self.fp_molality.get())
            res = ColligativeCalculator.freezing_point_new(solvent, molality)

            text = f"  Растворитель: {res['растворитель']}\n"
            text += f"  Tf чистого: {res['Tf_чистого_растворителя']} °C\n"
            text += f"  \u0394Tf = {res['понижение_Т_замерзания']} °C\n"
            text += f"  Tf раствора = {res['Tf_раствора']} °C\n"

            self.fp_result.delete("0.0", "end")
            self.fp_result.insert("0.0", text)
            HistoryManager.add("Т. замерзания", f"Tf={res['Tf_раствора']} °C (\u0394Tf={res['понижение_Т_замерзания']} °C)")
        except Exception as e:
            self.fp_result.delete("0.0", "end")
            self.fp_result.insert("0.0", f"Ошибка: {e}\n")

    # ---------- Под-вкладка 3: Осмотическое давление ----------
    def _build_osmotic(self, parent):
        card = CardFrame(parent, title="Осмотическое давление",
                         desc="\u03c0 = i \u00b7 M \u00b7 R \u00b7 T")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        fields = [("Молярность M (моль/л):", "M", "0.1"),
                  ("Температура T (K):", "T", "298"),
                  ("Фактор Вант-Гоффа i:", "i", "1")]
        self.osm_entries = {}
        for i, (label, key, default) in enumerate(fields):
            ctk.CTkLabel(grid, text=label, font=("Arial", 11)).grid(row=i, column=0, padx=5, pady=5, sticky="e")
            e = ctk.CTkEntry(grid, width=160)
            e.grid(row=i, column=1, padx=5, pady=5)
            e.insert(0, default)
            self.osm_entries[key] = e

        ctk.CTkButton(card, text="\u03c0 = iMRT", command=self._calc_osmotic,
                      width=160, fg_color="#27ae60").pack(pady=10)

        self.osm_result = ResultLabel(card, text="Результат появится здесь")
        self.osm_result.pack(pady=10)

    def _calc_osmotic(self):
        try:
            m = float(self.osm_entries["M"].get())
            t = float(self.osm_entries["T"].get())
            i_factor = float(self.osm_entries["i"].get())
            result = ColligativeCalculator.osmotic_pressure_vant_hoff(m, t, i_factor)
            self.osm_result.configure(text=f"\u03c0 = {result:.4f} атм", text_color="#27ae60")
            HistoryManager.add("Осмотич. давление", f"\u03c0={result:.4f} атм (M={m}, T={t}K, i={i_factor})")
        except Exception as e:
            self.osm_result.configure(text=f"Ошибка: {e}", text_color="red")

    # ---------- Под-вкладка 4: Молярная масса ----------
    def _build_mw_colligative(self, parent):
        card = CardFrame(parent, title="Молярная масса (из коллигативных свойств)",
                         desc="M = (K \u00b7 m_в-ва) / (\u0394T \u00b7 m_растворителя)")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        fields = [("\u0394T (°C):", "dt", "0.93"),
                  ("K (константа растворителя):", "K", "1.86"),
                  ("m_в-ва (г):", "m_solute", "5.0"),
                  ("m_растворителя (кг):", "m_solvent", "0.05")]
        self.mwc_entries = {}
        for i, (label, key, default) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            ctk.CTkLabel(grid, text=label, font=("Arial", 11)).grid(row=row, column=col, padx=5, pady=5, sticky="e")
            e = ctk.CTkEntry(grid, width=120)
            e.grid(row=row, column=col + 1, padx=5, pady=5)
            e.insert(0, default)
            self.mwc_entries[key] = e

        ctk.CTkButton(card, text="M = K\u00b7m/(\u0394T\u00b7m_solv)", command=self._calc_mw_colligative,
                      width=220, fg_color="#8e44ad").pack(pady=10)

        self.mwc_result = ResultLabel(card, text="Результат появится здесь")
        self.mwc_result.pack(pady=10)

    def _calc_mw_colligative(self):
        try:
            dt = float(self.mwc_entries["dt"].get())
            k = float(self.mwc_entries["K"].get())
            m_solute = float(self.mwc_entries["m_solute"].get())
            m_solvent = float(self.mwc_entries["m_solvent"].get())
            result = ColligativeCalculator.molecular_weight_from_colligative(dt, k, m_solute, m_solvent)
            self.mwc_result.configure(text=f"M = {result:.4f} г/моль", text_color="#8e44ad")
            HistoryManager.add("Мол. масса (коллиг.)", f"M={result:.4f} г/моль")
        except Exception as e:
            self.mwc_result.configure(text=f"Ошибка: {e}", text_color="red")

    # ---------- Под-вкладка 5: Закон Рауля ----------
    def _build_raoult(self, parent):
        card = CardFrame(parent, title="Закон Рауля",
                         desc="P = x_растворителя \u00b7 P\u00b0_растворителя")
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(grid, text="P\u00b0 (давление пара чистого р-ля):", font=("Arial", 11)).grid(
            row=0, column=0, padx=5, pady=5, sticky="e")
        self.rr_p = ctk.CTkEntry(grid, width=160)
        self.rr_p.grid(row=0, column=1, padx=5, pady=5)
        self.rr_p.insert(0, "23.76")

        ctk.CTkLabel(grid, text="x_растворителя (мольная доля):", font=("Arial", 11)).grid(
            row=1, column=0, padx=5, pady=5, sticky="e")
        self.rr_x = ctk.CTkEntry(grid, width=160)
        self.rr_x.grid(row=1, column=1, padx=5, pady=5)
        self.rr_x.insert(0, "0.9")

        ctk.CTkButton(card, text="P = x \u00b7 P\u00b0", command=self._calc_raoult,
                      width=160, fg_color="#16a085").pack(pady=10)

        self.rr_result = ctk.CTkTextbox(card, height=80, font=("Consolas", 12), wrap="word",
                                        fg_color=("#1e1e1e", "#1e1e1e"), text_color="white")
        self.rr_result.pack(fill="x", padx=15, pady=(5, 15))

    def _calc_raoult(self):
        try:
            p_pure = float(self.rr_p.get())
            x = float(self.rr_x.get())
            result = ColligativeCalculator.raoults_law(p_pure, x)

            text = f"  P\u00b0 = {p_pure}\n"
            text += f"  x_растворителя = {x}\n"
            text += f"  P раствора = {result:.4f}\n"
            text += f"  \u0394P = {p_pure - result:.4f} (понижение)\n"

            self.rr_result.delete("0.0", "end")
            self.rr_result.insert("0.0", text)
            HistoryManager.add("Закон Рауля", f"P={result:.4f} (x={x}, P\u00b0={p_pure})")
        except Exception as e:
            self.rr_result.delete("0.0", "end")
            self.rr_result.insert("0.0", f"Ошибка: {e}\n")
