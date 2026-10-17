import math


class AdvancedGasTab(ctk.CTkFrame):
    """Расширенная вкладка газовых законов с под-вкладками."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")

        tabview = ctk.CTkTabview(self)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Под-вкладка 1: Идеальный газ PV=nRT ---
        tab_ideal = tabview.add("Идеальный газ PV=nRT")
        c1 = CardFrame(tab_ideal, title="Идеальный газ PV=nRT",
                       desc="Оставьте ровно ОДНО поле пустым. R = 0.08206 Л·атм/(моль·К)")
        grid1 = ctk.CTkFrame(c1, fg_color="transparent")
        grid1.pack(pady=10, padx=15)

        self.ideal_entries = {}
        ideal_labels = [("P", "P (атм)"), ("V", "V (Л)"), ("n", "n (моль)"), ("T", "T (K)")]
        for i, (key, label) in enumerate(ideal_labels):
            row, col = i // 2, (i % 2) * 2
            ctk.CTkLabel(grid1, text=label, font=("Arial", 11)).grid(row=row * 2, column=col, padx=5, pady=(5, 0), sticky="w")
            e = ctk.CTkEntry(grid1, width=100, placeholder_text=key)
            e.grid(row=row * 2 + 1, column=col, padx=5, pady=(0, 10))
            self.ideal_entries[key] = e

        ctk.CTkButton(c1, text="Рассчитать", command=self.calc_ideal, width=140).pack(pady=10)
        self.ideal_res = ResultLabel(c1, text="...")
        self.ideal_res.pack(pady=10)

        # --- Под-вкладка 2: Ван-дер-Ваальс ---
        tab_vdw = tabview.add("Ван-дер-Ваальс")
        c2 = CardFrame(tab_vdw, title="Уравнение Ван-дер-Ваальса",
                       desc="(P + an²/V²)(V - nb) = nRT. Оставьте P или V пустым.")

        gas_names = list(GasCalculator.VDW_CONSTANTS.keys()) if GasCalculator.VDW_CONSTANTS else []
        gas_names.append("Вручную")

        sel_frame = ctk.CTkFrame(c2, fg_color="transparent")
        sel_frame.pack(fill="x", padx=15, pady=(5, 0))
        ctk.CTkLabel(sel_frame, text="Газ:").pack(side="left", padx=5)
        self.vdw_gas_var = ctk.StringVar(value=gas_names[0] if gas_names else "Вручную")
        self.vdw_gas_menu = ctk.CTkOptionMenu(sel_frame, values=gas_names, variable=self.vdw_gas_var,
                                              command=self._on_vdw_gas_change, width=200)
        self.vdw_gas_menu.pack(side="left", padx=5)

        # Ручной ввод a и b
        self.vdw_ab_frame = ctk.CTkFrame(c2, fg_color="transparent")
        self.vdw_ab_frame.pack(fill="x", padx=15)
        ctk.CTkLabel(self.vdw_ab_frame, text="a:").pack(side="left", padx=2)
        self.vdw_a_entry = ctk.CTkEntry(self.vdw_ab_frame, width=90, placeholder_text="L²·atm/mol²")
        self.vdw_a_entry.pack(side="left", padx=2)
        ctk.CTkLabel(self.vdw_ab_frame, text="b:").pack(side="left", padx=(10, 2))
        self.vdw_b_entry = ctk.CTkEntry(self.vdw_ab_frame, width=90, placeholder_text="L/mol")
        self.vdw_b_entry.pack(side="left", padx=2)

        grid2 = ctk.CTkFrame(c2, fg_color="transparent")
        grid2.pack(pady=10, padx=15)

        self.vdw_entries = {}
        vdw_labels = [("P", "P (атм)"), ("V", "V (Л)"), ("n", "n (моль)"), ("T", "T (K)")]
        for i, (key, label) in enumerate(vdw_labels):
            row, col = i // 2, (i % 2) * 2
            ctk.CTkLabel(grid2, text=label, font=("Arial", 11)).grid(row=row * 2, column=col, padx=5, pady=(5, 0), sticky="w")
            e = ctk.CTkEntry(grid2, width=100, placeholder_text=key)
            e.grid(row=row * 2 + 1, column=col, padx=5, pady=(0, 10))
            self.vdw_entries[key] = e

        ctk.CTkButton(c2, text="Рассчитать", command=self.calc_vdw, width=140).pack(pady=10)
        self.vdw_res = ResultLabel(c2, text="...")
        self.vdw_res.pack(pady=10)

        self._on_vdw_gas_change(self.vdw_gas_var.get())

        # --- Под-вкладка 3: Объединённый газовый закон ---
        tab_combined = tabview.add("Объединённый закон")
        c3 = CardFrame(tab_combined, title="Объединённый газовый закон",
                       desc="P1V1/T1 = P2V2/T2. Оставьте ОДНО поле пустым.")
        grid3 = ctk.CTkFrame(c3, fg_color="transparent")
        grid3.pack(pady=10, padx=15)

        self.combined_entries = {}
        comb_labels = [("P1", "P1 (атм)"), ("V1", "V1 (Л)"), ("T1", "T1 (K)"),
                       ("P2", "P2 (атм)"), ("V2", "V2 (Л)"), ("T2", "T2 (K)")]
        for i, (key, label) in enumerate(comb_labels):
            row, col = i // 3, (i % 3) * 2
            ctk.CTkLabel(grid3, text=label, font=("Arial", 11)).grid(row=row * 2, column=col, padx=5, pady=(5, 0), sticky="w")
            e = ctk.CTkEntry(grid3, width=90, placeholder_text=key)
            e.grid(row=row * 2 + 1, column=col, padx=5, pady=(0, 10))
            self.combined_entries[key] = e

        ctk.CTkButton(c3, text="Рассчитать", command=self.calc_combined, width=140).pack(pady=10)
        self.combined_res = ResultLabel(c3, text="...")
        self.combined_res.pack(pady=10)

        # --- Под-вкладка 4: Закон Дальтона ---
        tab_dalton = tabview.add("Закон Дальтона")
        c4 = CardFrame(tab_dalton, title="Закон Дальтона",
                       desc="P_i = x_i * P_total. Добавьте газы и введите данные.")

        ctk.CTkLabel(c4, text="P_total (атм):").pack(anchor="w", padx=20, pady=(5, 0))
        self.dalton_total = ctk.CTkEntry(c4, width=150, placeholder_text="Общее давление")
        self.dalton_total.pack(anchor="w", padx=20, pady=3)

        self.dalton_rows_frame = ctk.CTkFrame(c4, fg_color="transparent")
        self.dalton_rows_frame.pack(fill="x", padx=10, pady=5)

        self.dalton_rows = []
        self._add_dalton_row("Газ 1")
        self._add_dalton_row("Газ 2")

        btn_dalton_frame = ctk.CTkFrame(c4, fg_color="transparent")
        btn_dalton_frame.pack(pady=5)
        ctk.CTkButton(btn_dalton_frame, text="Добавить газ", command=self._add_dalton_row, width=130,
                      fg_color="#2980b9").pack(side="left", padx=5)
        ctk.CTkButton(btn_dalton_frame, text="Рассчитать парциальные давления", command=self.calc_dalton, width=260).pack(
            side="left", padx=5)

        self.dalton_res = ctk.CTkTextbox(c4, height=150, font=("Consolas", 12), wrap="word")
        self.dalton_res.pack(fill="x", padx=15, pady=10)
        self.dalton_res.insert("0.0", "Результаты появятся здесь...")

        # --- Под-вкладка 5: Свойства газа ---
        tab_props = tabview.add("Свойства газа")
        c5 = CardFrame(tab_props, title="Свойства газа")

        # Плотность газа
        ctk.CTkLabel(c5, text="--- Плотность газа d = PM/(RT) ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 5))
        f_den = ctk.CTkFrame(c5, fg_color="transparent")
        f_den.pack(fill="x", padx=20)
        ctk.CTkLabel(f_den, text="P (атм):").pack(side="left", padx=3)
        self.den_p = ctk.CTkEntry(f_den, width=80)
        self.den_p.pack(side="left", padx=3)
        ctk.CTkLabel(f_den, text="T (K):").pack(side="left", padx=3)
        self.den_t = ctk.CTkEntry(f_den, width=80)
        self.den_t.pack(side="left", padx=3)
        ctk.CTkLabel(f_den, text="M (г/моль):").pack(side="left", padx=3)
        self.den_mw = ctk.CTkEntry(f_den, width=80)
        self.den_mw.pack(side="left", padx=3)
        ctk.CTkButton(f_den, text="d", command=self.calc_density, width=50).pack(side="left", padx=3)
        self.den_res = ResultLabel(c5, text="...")
        self.den_res.pack(pady=5)

        # Скорость молекул
        ctk.CTkLabel(c5, text="--- Скорость молекул v_rms ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 5))
        f_spd = ctk.CTkFrame(c5, fg_color="transparent")
        f_spd.pack(fill="x", padx=20)
        ctk.CTkLabel(f_spd, text="T (K):").pack(side="left", padx=3)
        self.spd_t = ctk.CTkEntry(f_spd, width=80)
        self.spd_t.pack(side="left", padx=3)
        ctk.CTkLabel(f_spd, text="M (кг/моль):").pack(side="left", padx=3)
        self.spd_mw = ctk.CTkEntry(f_spd, width=100)
        self.spd_mw.pack(side="left", padx=3)
        ctk.CTkButton(f_spd, text="v_rms", command=self.calc_rms_speed, width=60).pack(side="left", padx=3)
        self.spd_res = ResultLabel(c5, text="...")
        self.spd_res.pack(pady=5)

        # Закон Грэма
        ctk.CTkLabel(c5, text="--- Закон Грэма ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 5))
        f_gr = ctk.CTkFrame(c5, fg_color="transparent")
        f_gr.pack(fill="x", padx=20)
        ctk.CTkLabel(f_gr, text="r1:").pack(side="left", padx=3)
        self.gr_r1 = ctk.CTkEntry(f_gr, width=80)
        self.gr_r1.pack(side="left", padx=3)
        ctk.CTkLabel(f_gr, text="MW1 (г/моль):").pack(side="left", padx=3)
        self.gr_mw1 = ctk.CTkEntry(f_gr, width=80)
        self.gr_mw1.pack(side="left", padx=3)
        ctk.CTkLabel(f_gr, text="MW2 (г/моль):").pack(side="left", padx=3)
        self.gr_mw2 = ctk.CTkEntry(f_gr, width=80)
        self.gr_mw2.pack(side="left", padx=3)
        ctk.CTkButton(f_gr, text="r2", command=self.calc_grahams, width=50).pack(side="left", padx=3)
        self.gr_res = ResultLabel(c5, text="...")
        self.gr_res.pack(pady=10)

    # ---- Вспомогательные методы ----

    def _on_vdw_gas_change(self, choice):
        if choice == "Вручную":
            self.vdw_ab_frame.pack(fill="x", padx=15)
            self.vdw_a_entry.delete(0, "end")
            self.vdw_b_entry.delete(0, "end")
        else:
            self.vdw_ab_frame.pack_forget()
            if GasCalculator.VDW_CONSTANTS and choice in GasCalculator.VDW_CONSTANTS:
                a_val, b_val = GasCalculator.VDW_CONSTANTS[choice]
                self.vdw_a_entry.delete(0, "end")
                self.vdw_a_entry.insert(0, str(a_val))
                self.vdw_b_entry.delete(0, "end")
                self.vdw_b_entry.insert(0, str(b_val))

    def _add_dalton_row(self, name="Газ"):
        row_frame = ctk.CTkFrame(self.dalton_rows_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        name_e = ctk.CTkEntry(row_frame, width=100, placeholder_text="Название")
        name_e.pack(side="left", padx=3)
        xf_e = ctk.CTkEntry(row_frame, width=80, placeholder_text="x_i")
        xf_e.pack(side="left", padx=3)
        del_btn = ctk.CTkButton(row_frame, text="✕", width=30, fg_color="gray",
                                command=lambda: self._remove_dalton_row(row_frame))
        del_btn.pack(side="left", padx=3)
        self.dalton_rows.append((row_frame, name_e, xf_e))

    def _remove_dalton_row(self, frame):
        for i, (f, n, x) in enumerate(self.dalton_rows):
            if f is frame:
                self.dalton_rows.pop(i)
                frame.destroy()
                break

    # ---- Расчёты ----

    def calc_ideal(self):
        try:
            vals = {}
            for k, e in self.ideal_entries.items():
                txt = e.get().strip()
                vals[k] = float(txt) if txt else None

            none_count = sum(1 for v in vals.values() if v is None)
            if none_count != 1:
                self.ideal_res.configure(text="Оставьте ровно 1 поле пустым", text_color="orange")
                return

            result = GasCalculator.ideal_gas(
                P=vals.get('P'), V=vals.get('V'), n=vals.get('n'), T=vals.get('T')
            )
            # result is a dict with key=param_name, value=solved_value
            if isinstance(result, dict):
                param = list(result.keys())[0]
                val = result[param]
                units = {"P": "атм", "V": "Л", "n": "моль", "T": "K"}
                unit = units.get(param, "")
                self.ideal_res.configure(text=f"{param} = {val:.6g} {unit}", text_color="#4facfe")
                HistoryManager.add("Идеальный газ", f"{param} = {val:.6g} {unit}")
            else:
                self.ideal_res.configure(text=f"Результат: {result}", text_color="#4facfe")
                HistoryManager.add("Идеальный газ", str(result))
        except Exception as e:
            self.ideal_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_vdw(self):
        try:
            vals = {}
            for k, e in self.vdw_entries.items():
                txt = e.get().strip()
                vals[k] = float(txt) if txt else None

            none_count = sum(1 for v in vals.values() if v is None)
            if none_count != 1:
                self.vdw_res.configure(text="Оставьте P или V пустым", text_color="orange")
                return

            if vals.get('P') is None and vals.get('V') is not None and vals['V'] <= 0:
                raise ValueError("V должно быть > 0")
            if vals.get('V') is None and vals.get('P') is not None and vals['P'] <= 0:
                raise ValueError("P должно быть > 0")

            a = float(self.vdw_a_entry.get()) if self.vdw_a_entry.get().strip() else 0
            b = float(self.vdw_b_entry.get()) if self.vdw_b_entry.get().strip() else 0

            result = GasCalculator.van_der_waals(
                P=vals.get('P'), V=vals.get('V'), n=vals.get('n'), T=vals.get('T'),
                a=a, b=b
            )

            if isinstance(result, dict):
                param = list(result.keys())[0]
                val = result[param]
                units = {"P": "атм", "V": "Л"}
                unit = units.get(param, "")
                self.vdw_res.configure(text=f"{param} = {val:.6g} {unit}", text_color="#4facfe")
                HistoryManager.add("Ван-дер-Ваальс", f"{param} = {val:.6g} {unit}")
            else:
                self.vdw_res.configure(text=f"Результат: {result}", text_color="#4facfe")
                HistoryManager.add("Ван-дер-Ваальс", str(result))
        except Exception as e:
            self.vdw_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_combined(self):
        try:
            vals = {}
            for k, e in self.combined_entries.items():
                txt = e.get().strip()
                vals[k] = float(txt) if txt else None

            none_count = sum(1 for v in vals.values() if v is None)
            if none_count != 1:
                self.combined_res.configure(text="Оставьте ровно 1 поле пустым", text_color="orange")
                return

            result = GasCalculator.combined_gas_law(
                P1=vals.get('P1'), V1=vals.get('V1'), T1=vals.get('T1'),
                P2=vals.get('P2'), V2=vals.get('V2'), T2=vals.get('T2')
            )

            if isinstance(result, dict):
                param = list(result.keys())[0]
                val = result[param]
                units = {"P2": "атм", "V2": "Л", "T2": "K", "P1": "атм", "V1": "Л", "T1": "K"}
                unit = units.get(param, "")
                self.combined_res.configure(text=f"{param} = {val:.6g} {unit}", text_color="#4facfe")
                HistoryManager.add("Объём. газ. закон", f"{param} = {val:.6g} {unit}")
            else:
                self.combined_res.configure(text=f"Результат: {result}", text_color="#4facfe")
        except Exception as e:
            self.combined_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_dalton(self):
        try:
            p_total = float(self.dalton_total.get().strip())
            if p_total <= 0:
                raise ValueError("P_total должно быть > 0")

            mole_fractions = []
            gas_names_list = []
            for _, name_e, xf_e in self.dalton_rows:
                name = name_e.get().strip() or "?"
                xf = float(xf_e.get().strip())
                gas_names_list.append(name)
                mole_fractions.append(xf)

            result = GasCalculator.dalton_partial_pressure(p_total, mole_fractions)

            self.dalton_res.delete("0.0", "end")
            lines = [f"P_total = {p_total} атм\n{'─' * 40}\n"]
            if isinstance(result, list):
                for i, (name, p_partial) in enumerate(zip(gas_names_list, result)):
                    lines.append(f"{name}: P_i = {p_partial:.6g} атм (x_i = {mole_fractions[i]:.4f})\n")
            elif isinstance(result, dict):
                for i, name in enumerate(gas_names_list):
                    p_partial = result.get(name, result.get(i, 0))
                    lines.append(f"{name}: P_i = {p_partial:.6g} атм (x_i = {mole_fractions[i]:.4f})\n")
            else:
                lines.append(str(result))

            self.dalton_res.insert("0.0", "".join(lines))
            HistoryManager.add("Дальтон", f"P_total={p_total}, {len(gas_names_list)} газов")
        except Exception as e:
            self.dalton_res.delete("0.0", "end")
            self.dalton_res.insert("0.0", f"Ошибка: {e}")

    def calc_density(self):
        try:
            P = float(self.den_p.get())
            T = float(self.den_t.get())
            mw = float(self.den_mw.get())
            d = GasCalculator.gas_density(P, T, mw)
            self.den_res.configure(text=f"d = {d:.6g} г/Л", text_color="#4facfe")
            HistoryManager.add("Плотность газа", f"d = {d:.6g} г/Л")
        except Exception as e:
            self.den_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_rms_speed(self):
        try:
            T = float(self.spd_t.get())
            mw_kg = float(self.spd_mw.get())
            v = GasCalculator.rms_speed(T, mw_kg)
            self.spd_res.configure(text=f"v_rms = {v:.2f} м/с", text_color="#4facfe")
            HistoryManager.add("Скорость молекул", f"v_rms = {v:.2f} м/с")
        except Exception as e:
            self.spd_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_grahams(self):
        try:
            r1 = float(self.gr_r1.get())
            mw1 = float(self.gr_mw1.get())
            mw2 = float(self.gr_mw2.get())
            r2 = GasCalculator.grahams_law(r1, mw1, mw2)
            self.gr_res.configure(text=f"r2 = {r2:.6g}", text_color="#4facfe")
            HistoryManager.add("Закон Грэма", f"r2 = {r2:.6g}")
        except Exception as e:
            self.gr_res.configure(text=f"Ошибка: {e}", text_color="red")


class AdvancedThermoTab(ctk.CTkFrame):
    """Расширенная вкладка термодинамики с под-вкладками."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")

        tabview = ctk.CTkTabview(self)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Под-вкладка 1: Энергия Гиббса ---
        tab_gibbs = tabview.add("Энергия Гиббса")
        c1 = CardFrame(tab_gibbs, title="Энергия Гиббса",
                       desc="ΔG = ΔH - TΔS. Введите параметры реакции.")

        g1 = ctk.CTkFrame(c1, fg_color="transparent")
        g1.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(g1, text="ΔH (кДж/моль):").pack(side="left", padx=3)
        self.gibbs_dh = ctk.CTkEntry(g1, width=100)
        self.gibbs_dh.pack(side="left", padx=3)
        ctk.CTkLabel(g1, text="ΔS (Дж/(моль·К)):").pack(side="left", padx=3)
        self.gibbs_ds = ctk.CTkEntry(g1, width=100)
        self.gibbs_ds.pack(side="left", padx=3)
        ctk.CTkLabel(g1, text="T (K):").pack(side="left", padx=3)
        self.gibbs_t = ctk.CTkEntry(g1, width=80)
        self.gibbs_t.pack(side="left", padx=3)
        self.gibbs_t.insert(0, "298")

        ctk.CTkButton(c1, text="ΔG = ΔH - TΔS", command=self.calc_gibbs, width=180).pack(pady=10)
        self.gibbs_res = ResultLabel(c1, text="...")
        self.gibbs_res.pack(pady=3)
        self.gibbs_info = ctk.CTkLabel(c1, text="", font=("Arial", 12), text_color="gray70", wraplength=450, justify="left")
        self.gibbs_info.pack(pady=5)

        # --- Под-вкладка 2: K равновесия ---
        tab_keq = tabview.add("K равновесия")
        c2 = CardFrame(tab_keq, title="Константа равновесия", desc="Связь ΔG и K")

        # K из ΔG
        ctk.CTkLabel(c2, text="K из ΔG:", font=("Arial", 12, "bold")).pack(anchor="w", padx=20, pady=(10, 3))
        f_k1 = ctk.CTkFrame(c2, fg_color="transparent")
        f_k1.pack(fill="x", padx=20)
        ctk.CTkLabel(f_k1, text="ΔG (кДж/моль):").pack(side="left", padx=3)
        self.keq_dg = ctk.CTkEntry(f_k1, width=100)
        self.keq_dg.pack(side="left", padx=3)
        ctk.CTkLabel(f_k1, text="T (K):").pack(side="left", padx=3)
        self.keq_t1 = ctk.CTkEntry(f_k1, width=80)
        self.keq_t1.pack(side="left", padx=3)
        self.keq_t1.insert(0, "298")
        ctk.CTkButton(f_k1, text="K из ΔG", command=self.calc_keq_from_dg, width=100).pack(side="left", padx=5)
        self.keq_from_dg_res = ResultLabel(c2, text="...")
        self.keq_from_dg_res.pack(pady=5)

        # ΔG из K
        ctk.CTkLabel(c2, text="ΔG из K:", font=("Arial", 12, "bold")).pack(anchor="w", padx=20, pady=(10, 3))
        f_k2 = ctk.CTkFrame(c2, fg_color="transparent")
        f_k2.pack(fill="x", padx=20)
        ctk.CTkLabel(f_k2, text="K:").pack(side="left", padx=3)
        self.keq_k = ctk.CTkEntry(f_k2, width=100)
        self.keq_k.pack(side="left", padx=3)
        ctk.CTkLabel(f_k2, text="T (K):").pack(side="left", padx=3)
        self.keq_t2 = ctk.CTkEntry(f_k2, width=80)
        self.keq_t2.pack(side="left", padx=3)
        self.keq_t2.insert(0, "298")
        ctk.CTkButton(f_k2, text="ΔG из K", command=self.calc_dg_from_keq, width=100).pack(side="left", padx=5)
        self.dg_from_keq_res = ResultLabel(c2, text="...")
        self.dg_from_keq_res.pack(pady=10)

        # --- Под-вкладка 3: Закон Гесса ---
        tab_hess = tabview.add("Закон Гесса")
        c3 = CardFrame(tab_hess, title="Закон Гесса",
                       desc="Σ ΔH_реакции = Σ(ΔH_стадий × знак). +1 = продукты, -1 = реагенты.")

        self.hess_scroll = ctk.CTkScrollableFrame(c3, height=180, fg_color="transparent")
        self.hess_scroll.pack(fill="x", padx=10, pady=5)

        self.hess_rows = []
        for _ in range(3):
            self._add_hess_row()

        btn_hess = ctk.CTkFrame(c3, fg_color="transparent")
        btn_hess.pack(pady=5)
        ctk.CTkButton(btn_hess, text="Добавить стадию", command=self._add_hess_row, width=140,
                      fg_color="#2980b9").pack(side="left", padx=5)
        ctk.CTkButton(btn_hess, text="Рассчитать ΔH", command=self.calc_hess, width=160).pack(side="left", padx=5)
        self.hess_res = ResultLabel(c3, text="...")
        self.hess_res.pack(pady=10)

        # --- Под-вкладка 4: Калориметрия ---
        tab_cal = tabview.add("Калориметрия")
        c4 = CardFrame(tab_cal, title="Калориметрия", desc="q = mcΔT")

        f_cal = ctk.CTkFrame(c4, fg_color="transparent")
        f_cal.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(f_cal, text="m (г):").pack(side="left", padx=3)
        self.cal_mass = ctk.CTkEntry(f_cal, width=80)
        self.cal_mass.pack(side="left", padx=3)
        ctk.CTkLabel(f_cal, text="c (Дж/(г·К)):").pack(side="left", padx=3)
        self.cal_sh = ctk.CTkEntry(f_cal, width=100)
        self.cal_sh.pack(side="left", padx=3)
        ctk.CTkLabel(f_cal, text="ΔT (K):").pack(side="left", padx=3)
        self.cal_dt = ctk.CTkEntry(f_cal, width=80)
        self.cal_dt.pack(side="left", padx=3)

        ctk.CTkButton(c4, text="q = mcΔT", command=self.calc_calorimetry, width=140).pack(pady=10)
        self.cal_res = ResultLabel(c4, text="...")
        self.cal_res.pack(pady=10)

        # --- Под-вкладка 5: Вант-Гофф ---
        tab_vh = tabview.add("Вант-Гофф")
        c5 = CardFrame(tab_vh, title="Уравнение Вант-Гоффа",
                       desc="ln(K2/K1) = -ΔH/R × (1/T2 - 1/T1)")

        f_vh = ctk.CTkFrame(c5, fg_color="transparent")
        f_vh.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(f_vh, text="K1:").pack(side="left", padx=3)
        self.vh_k1 = ctk.CTkEntry(f_vh, width=80)
        self.vh_k1.pack(side="left", padx=3)
        ctk.CTkLabel(f_vh, text="T1 (K):").pack(side="left", padx=3)
        self.vh_t1 = ctk.CTkEntry(f_vh, width=80)
        self.vh_t1.pack(side="left", padx=3)
        ctk.CTkLabel(f_vh, text="T2 (K):").pack(side="left", padx=3)
        self.vh_t2 = ctk.CTkEntry(f_vh, width=80)
        self.vh_t2.pack(side="left", padx=3)
        ctk.CTkLabel(f_vh, text="ΔH (кДж/моль):").pack(side="left", padx=3)
        self.vh_dh = ctk.CTkEntry(f_vh, width=100)
        self.vh_dh.pack(side="left", padx=3)

        ctk.CTkButton(c5, text="Рассчитать K2", command=self.calc_vant_hoff, width=160).pack(pady=10)
        self.vh_res = ResultLabel(c5, text="...")
        self.vh_res.pack(pady=10)

        # --- Под-вкладка 6: Энергия связей ---
        tab_bond = tabview.add("Энергия связей")
        c6 = CardFrame(tab_bond, title="Энергия связей",
                       desc="ΔH = Σ(broken) - Σ(formed)")

        f_bond = ctk.CTkFrame(c6, fg_color="transparent")
        f_bond.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(f_bond, text="Σ broken (кДж/моль):").pack(side="left", padx=3)
        self.bond_broken = ctk.CTkEntry(f_bond, width=120)
        self.bond_broken.pack(side="left", padx=3)
        ctk.CTkLabel(f_bond, text="Σ formed (кДж/моль):").pack(side="left", padx=3)
        self.bond_formed = ctk.CTkEntry(f_bond, width=120)
        self.bond_formed.pack(side="left", padx=3)

        ctk.CTkButton(c6, text="ΔH = Σ(broken) - Σ(formed)", command=self.calc_bond_energy, width=260).pack(pady=10)
        self.bond_res = ResultLabel(c6, text="...")
        self.bond_res.pack(pady=10)

    # ---- Вспомогательные ----

    def _add_hess_row(self):
        row = ctk.CTkFrame(self.hess_scroll, fg_color="transparent")
        row.pack(fill="x", pady=2)
        sign_var = ctk.StringVar(value="+1")
        sign_menu = ctk.CTkOptionMenu(row, values=["+1", "-1"], variable=sign_var, width=60)
        sign_menu.pack(side="left", padx=3)
        entry = ctk.CTkEntry(row, width=150, placeholder_text="ΔH (кДж/моль)")
        entry.pack(side="left", padx=3)
        del_btn = ctk.CTkButton(row, text="Удалить", width=70, fg_color="gray",
                                command=lambda: self._remove_hess_row(row))
        del_btn.pack(side="left", padx=3)
        self.hess_rows.append((entry, sign_var))

    def _remove_hess_row(self, frame):
        for i, (e, s) in enumerate(self.hess_rows):
            e_widget = e.master
            if e_widget is frame:
                self.hess_rows.pop(i)
                frame.destroy()
                break

    # ---- Расчёты ----

    def calc_gibbs(self):
        try:
            dH = float(self.gibbs_dh.get())
            dS = float(self.gibbs_ds.get())
            T = float(self.gibbs_t.get())

            dG = ThermoCalculator.gibbs_energy(dH, dS, T)

            self.gibbs_res.configure(text=f"ΔG = {dG:.4f} кДж/моль", text_color="#4facfe")
            HistoryManager.add("Энергия Гиббса", f"ΔG = {dG:.4f} кДж/моль")

            # Самопроизвольность
            if dG < 0:
                spont_text = "✓ Реакция самопроизвольна (ΔG < 0)"
                color = "#2ecc71"
            elif dG > 0:
                spont_text = "✗ Реакция несамопроизвольна (ΔG > 0)"
                color = "#e74c3c"
            else:
                spont_text = "≈ Реакция в равновесии (ΔG = 0)"
                color = "#f39c12"

            info = spont_text

            # Равновесная температура (если dS != 0)
            if dS != 0:
                t_eq = dH / (dS / 1000.0)  # dH в кДж, dS в Дж -> dS/1000 в кДж
                if t_eq > 0:
                    info += f"\nT_равн = {t_eq:.2f} K ({t_eq - 273.15:.2f} °C)"

            self.gibbs_info.configure(text=info, text_color=color)
        except Exception as e:
            self.gibbs_res.configure(text=f"Ошибка: {e}", text_color="red")
            self.gibbs_info.configure(text="")

    def calc_keq_from_dg(self):
        try:
            dG = float(self.keq_dg.get())
            T = float(self.keq_t1.get())
            K = ThermoCalculator.equilibrium_constant(dG, T)
            if isinstance(K, (int, float)):
                self.keq_from_dg_res.configure(text=f"K = {K:.6g}", text_color="#4facfe")
            else:
                self.keq_from_dg_res.configure(text=f"K = {K}", text_color="#4facfe")
            HistoryManager.add("K из ΔG", f"K = {K:.6g}")
        except Exception as e:
            self.keq_from_dg_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_dg_from_keq(self):
        try:
            K = float(self.keq_k.get())
            T = float(self.keq_t2.get())
            # dG = -RT ln(K), результат в кДж: dG = -R*T*ln(K)/1000
            R = 8.314
            dG = -R * T * math.log(K) / 1000.0
            self.dg_from_keq_res.configure(text=f"ΔG = {dG:.4f} кДж/моль", text_color="#4facfe")
            HistoryManager.add("ΔG из K", f"ΔG = {dG:.4f} кДж/моль")
        except Exception as e:
            self.dg_from_keq_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_hess(self):
        try:
            terms = []
            for entry, sign_var in self.hess_rows:
                val_str = entry.get().strip()
                if not val_str:
                    continue
                val = float(val_str)
                sign = float(sign_var.get())
                terms.append({"value": val, "sign": sign})

            if not terms:
                self.hess_res.configure(text="Добавьте хотя бы одну стадию", text_color="orange")
                return

            result = ThermoCalculator.hess_law(terms)
            if isinstance(result, dict):
                dH = result.get("delta_H", result.get("result", result))
            else:
                dH = result

            self.hess_res.configure(text=f"ΔH_реакции = {dH:.4f} кДж/моль", text_color="#4facfe")
            HistoryManager.add("Закон Гесса", f"ΔH = {dH:.4f} кДж/моль ({len(terms)} стадий)")
        except Exception as e:
            self.hess_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_calorimetry(self):
        try:
            mass = float(self.cal_mass.get())
            sh = float(self.cal_sh.get())
            dt = float(self.cal_dt.get())
            q = ThermoCalculator.calorimetry(mass, sh, dt)
            if isinstance(q, dict):
                q_val = q.get("q", q.get("heat", q))
            else:
                q_val = q
            self.cal_res.configure(text=f"q = {q_val:.4f} Дж ({q_val / 1000:.4f} кДж)", text_color="#4facfe")
            HistoryManager.add("Калориметрия", f"q = {q_val:.4f} Дж")
        except Exception as e:
            self.cal_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_vant_hoff(self):
        try:
            K1 = float(self.vh_k1.get())
            T1 = float(self.vh_t1.get())
            T2 = float(self.vh_t2.get())
            dH = float(self.vh_dh.get())
            K2 = ThermoCalculator.van_t_hoff(K1, T1, T2, dH)
            if isinstance(K2, dict):
                K2 = K2.get("K2", K2.get("result", K2))
            self.vh_res.configure(text=f"K2 = {K2:.6g}", text_color="#4facfe")
            HistoryManager.add("Вант-Гофф", f"K2 = {K2:.6g}")
        except Exception as e:
            self.vh_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_bond_energy(self):
        try:
            broken = float(self.bond_broken.get())
            formed = float(self.bond_formed.get())
            dH = ThermoCalculator.bond_energy(broken, formed)
            if isinstance(dH, dict):
                dH = dH.get("delta_H", dH.get("result", dH))
            self.bond_res.configure(text=f"ΔH = {dH:.4f} кДж/моль", text_color="#4facfe")
            HistoryManager.add("Энергия связей", f"ΔH = {dH:.4f} кДж/моль")
        except Exception as e:
            self.bond_res.configure(text=f"Ошибка: {e}", text_color="red")


class AdvancedKineticsTab(ctk.CTkFrame):
    """Расширенная вкладка химической кинетики с под-вкладками."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")

        tabview = ctk.CTkTabview(self)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Под-вкладка 1: Аррениус ---
        tab_arr = tabview.add("Аррениус")
        c1 = CardFrame(tab_arr, title="Уравнение Аррениуса",
                       desc="k = A·exp(-Ea/(RT))")

        # k2 из k1, T1, Ea, T2
        ctk.CTkLabel(c1, text="Расчёт k2:", font=("Arial", 12, "bold")).pack(anchor="w", padx=20, pady=(10, 3))
        f_a1 = ctk.CTkFrame(c1, fg_color="transparent")
        f_a1.pack(fill="x", padx=20)
        ctk.CTkLabel(f_a1, text="k1:").pack(side="left", padx=2)
        self.arr_k1 = ctk.CTkEntry(f_a1, width=80)
        self.arr_k1.pack(side="left", padx=2)
        ctk.CTkLabel(f_a1, text="T1 (K):").pack(side="left", padx=2)
        self.arr_t1 = ctk.CTkEntry(f_a1, width=70)
        self.arr_t1.pack(side="left", padx=2)
        ctk.CTkLabel(f_a1, text="Ea (Дж/моль):").pack(side="left", padx=2)
        self.arr_ea = ctk.CTkEntry(f_a1, width=100)
        self.arr_ea.pack(side="left", padx=2)
        ctk.CTkLabel(f_a1, text="T2 (K):").pack(side="left", padx=2)
        self.arr_t2 = ctk.CTkEntry(f_a1, width=70)
        self.arr_t2.pack(side="left", padx=2)
        ctk.CTkButton(f_a1, text="k2", command=self.calc_arrhenius_k2, width=50).pack(side="left", padx=3)
        self.arr_k2_res = ResultLabel(c1, text="...")
        self.arr_k2_res.pack(pady=5)

        # Ea из k1, T1, k2, T2
        ctk.CTkLabel(c1, text="Расчёт Ea:", font=("Arial", 12, "bold")).pack(anchor="w", padx=20, pady=(10, 3))
        f_a2 = ctk.CTkFrame(c1, fg_color="transparent")
        f_a2.pack(fill="x", padx=20)
        ctk.CTkLabel(f_a2, text="k1:").pack(side="left", padx=2)
        self.arr_k1b = ctk.CTkEntry(f_a2, width=80)
        self.arr_k1b.pack(side="left", padx=2)
        ctk.CTkLabel(f_a2, text="T1 (K):").pack(side="left", padx=2)
        self.arr_t1b = ctk.CTkEntry(f_a2, width=70)
        self.arr_t1b.pack(side="left", padx=2)
        ctk.CTkLabel(f_a2, text="k2:").pack(side="left", padx=2)
        self.arr_k2b = ctk.CTkEntry(f_a2, width=80)
        self.arr_k2b.pack(side="left", padx=2)
        ctk.CTkLabel(f_a2, text="T2 (K):").pack(side="left", padx=2)
        self.arr_t2b = ctk.CTkEntry(f_a2, width=70)
        self.arr_t2b.pack(side="left", padx=2)
        ctk.CTkButton(f_a2, text="Ea", command=self.calc_activation_energy, width=50).pack(side="left", padx=3)
        self.arr_ea_res = ResultLabel(c1, text="...")
        self.arr_ea_res.pack(pady=10)

        # --- Под-вкладка 2: Период полураспада ---
        tab_half = tabview.add("Период полураспада")
        c2 = CardFrame(tab_half, title="Период полураспада", desc="t₁/₂ для различных порядков реакции")

        f_h = ctk.CTkFrame(c2, fg_color="transparent")
        f_h.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(f_h, text="Порядок:").pack(side="left", padx=3)
        self.half_order = ctk.CTkOptionMenu(f_h, values=["0", "1", "2"], width=60)
        self.half_order.pack(side="left", padx=3)
        ctk.CTkLabel(f_h, text="k:").pack(side="left", padx=3)
        self.half_k = ctk.CTkEntry(f_h, width=100)
        self.half_k.pack(side="left", padx=3)
        ctk.CTkLabel(f_h, text="C0 (для порядка 2):").pack(side="left", padx=3)
        self.half_c0 = ctk.CTkEntry(f_h, width=100, placeholder_text="только для 2-го")
        self.half_c0.pack(side="left", padx=3)

        ctk.CTkButton(c2, text="t₁/₂", command=self.calc_half_life, width=100).pack(pady=10)
        self.half_res = ResultLabel(c2, text="...")
        self.half_res.pack(pady=10)

        # --- Под-вкладка 3: Интегрированные уравнения ---
        tab_int = tabview.add("Интегр. уравнения")
        c3 = CardFrame(tab_int, title="Интегрированные уравнения скорости",
                       desc="Решение для Ct по заданным k, t, C0")

        f_i = ctk.CTkFrame(c3, fg_color="transparent")
        f_i.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(f_i, text="Порядок:").pack(side="left", padx=3)
        self.int_order = ctk.CTkOptionMenu(f_i, values=["0", "1", "2"], width=60)
        self.int_order.pack(side="left", padx=3)
        ctk.CTkLabel(f_i, text="k:").pack(side="left", padx=3)
        self.int_k = ctk.CTkEntry(f_i, width=80)
        self.int_k.pack(side="left", padx=3)
        ctk.CTkLabel(f_i, text="t:").pack(side="left", padx=3)
        self.int_t = ctk.CTkEntry(f_i, width=80)
        self.int_t.pack(side="left", padx=3)
        ctk.CTkLabel(f_i, text="C0:").pack(side="left", padx=3)
        self.int_c0 = ctk.CTkEntry(f_i, width=80)
        self.int_c0.pack(side="left", padx=3)

        ctk.CTkButton(c3, text="Рассчитать Ct", command=self.calc_integrated, width=140).pack(pady=10)
        self.int_res = ResultLabel(c3, text="...")
        self.int_res.pack(pady=10)

        # --- Под-вкладка 4: Время реакции ---
        tab_time = tabview.add("Время реакции")
        c4 = CardFrame(tab_time, title="Время реакции",
                       desc="Время достижения заданной доли превращения")

        f_t = ctk.CTkFrame(c4, fg_color="transparent")
        f_t.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(f_t, text="Порядок:").pack(side="left", padx=3)
        self.time_order = ctk.CTkOptionMenu(f_t, values=["0", "1", "2"], width=60)
        self.time_order.pack(side="left", padx=3)
        ctk.CTkLabel(f_t, text="k:").pack(side="left", padx=3)
        self.time_k = ctk.CTkEntry(f_t, width=80)
        self.time_k.pack(side="left", padx=3)
        ctk.CTkLabel(f_t, text="C0:").pack(side="left", padx=3)
        self.time_c0 = ctk.CTkEntry(f_t, width=80)
        self.time_c0.pack(side="left", padx=3)
        ctk.CTkLabel(f_t, text="Доля:").pack(side="left", padx=3)
        self.time_frac = ctk.CTkEntry(f_t, width=80)
        self.time_frac.pack(side="left", padx=3)
        self.time_frac.insert(0, "0.5")

        ctk.CTkButton(c4, text="Время до цели", command=self.calc_reaction_time, width=160).pack(pady=10)
        self.time_res = ResultLabel(c4, text="...")
        self.time_res.pack(pady=10)

    # ---- Расчёты ----

    def calc_arrhenius_k2(self):
        try:
            k1 = float(self.arr_k1.get())
            T1 = float(self.arr_t1.get())
            Ea = float(self.arr_ea.get())
            T2 = float(self.arr_t2.get())
            k2 = KineticsCalculator.arrhenius(k1, T1, Ea, T2)
            if isinstance(k2, dict):
                k2 = k2.get("k2", k2.get("result", k2))
            self.arr_k2_res.configure(text=f"k2 = {k2:.6g}", text_color="#4facfe")
            HistoryManager.add("Аррениус (k2)", f"k2 = {k2:.6g}")
        except Exception as e:
            self.arr_k2_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_activation_energy(self):
        try:
            k1 = float(self.arr_k1b.get())
            T1 = float(self.arr_t1b.get())
            k2 = float(self.arr_k2b.get())
            T2 = float(self.arr_t2b.get())
            Ea = KineticsCalculator.activation_energy(k1, T1, k2, T2)
            if isinstance(Ea, dict):
                Ea = Ea.get("Ea", Ea.get("result", Ea))
            self.arr_ea_res.configure(text=f"Ea = {Ea:.4f} Дж/моль ({Ea / 1000:.4f} кДж/моль)", text_color="#4facfe")
            HistoryManager.add("Аррениус (Ea)", f"Ea = {Ea:.4f} Дж/моль")
        except Exception as e:
            self.arr_ea_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_half_life(self):
        try:
            order = int(self.half_order.get())
            k = float(self.half_k.get())
            c0_str = self.half_c0.get().strip()

            if order == 0:
                if not c0_str:
                    raise ValueError("Для порядка 0 введите C0")
                c0 = float(c0_str)
                t_half = KineticsCalculator.half_life_zero_order(k, c0)
            elif order == 1:
                t_half = KineticsCalculator.half_life_first_order(k)
            elif order == 2:
                if not c0_str:
                    raise ValueError("Для порядка 2 введите C0")
                c0 = float(c0_str)
                t_half = KineticsCalculator.half_life_second_order(k, c0)
            else:
                raise ValueError("Порядок должен быть 0, 1 или 2")

            if isinstance(t_half, dict):
                t_half = t_half.get("t_half", t_half.get("result", t_half))

            self.half_res.configure(text=f"t₁/₂ = {t_half:.6g}", text_color="#4facfe")
            HistoryManager.add(f"Полураспад (порядок {order})", f"t₁/₂ = {t_half:.6g}")
        except Exception as e:
            self.half_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_integrated(self):
        try:
            order = int(self.int_order.get())
            k = float(self.int_k.get())
            t = float(self.int_t.get())
            c0 = float(self.int_c0.get())

            if order == 0:
                ct = KineticsCalculator.integrated_rate_zero(k, t, c0=c0)
            elif order == 1:
                ct = KineticsCalculator.integrated_rate_first(k, t, c0=c0)
            elif order == 2:
                ct = KineticsCalculator.integrated_rate_second(k, t, c0=c0)
            else:
                raise ValueError("Порядок должен быть 0, 1 или 2")

            if isinstance(ct, dict):
                ct = ct.get("Ct", ct.get("result", ct))

            self.int_res.configure(text=f"Ct = {ct:.6g}", text_color="#4facfe")
            HistoryManager.add(f"Интегр. ур-е (порядок {order})", f"Ct = {ct:.6g}")
        except Exception as e:
            self.int_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_reaction_time(self):
        try:
            order = int(self.time_order.get())
            k = float(self.time_k.get())
            c0 = float(self.time_c0.get())
            frac = float(self.time_frac.get())

            t = KineticsCalculator.reaction_time(order, k, c0, frac)

            if isinstance(t, dict):
                t = t.get("time", t.get("result", t))

            self.time_res.configure(text=f"t = {t:.6g}", text_color="#4facfe")
            HistoryManager.add(f"Время реакции (порядок {order})", f"t = {t:.6g} (доля {frac})")
        except Exception as e:
            self.time_res.configure(text=f"Ошибка: {e}", text_color="red")


class AdvancedStoichiometryTab(ctk.CTkFrame):
    """Расширенная вкладка стехиометрии с под-вкладками."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")

        tabview = ctk.CTkTabview(self)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Под-вкладка 1: Лимитирующий реагент ---
        tab_limit = tabview.add("Лимитир. реагент")
        c1 = CardFrame(tab_limit, title="Лимитирующий реагент",
                       desc="Определение лимитирующего реагента и расчёт")

        self.reagent_scroll = ctk.CTkScrollableFrame(c1, height=200, fg_color="transparent")
        self.reagent_scroll.pack(fill="x", padx=10, pady=5)

        self.reagent_rows = []
        self._add_reagent_row("Реагент 1")
        self._add_reagent_row("Реагент 2")

        btn_r = ctk.CTkFrame(c1, fg_color="transparent")
        btn_r.pack(pady=5)
        ctk.CTkButton(btn_r, text="Добавить реагент", command=self._add_reagent_row, width=140,
                      fg_color="#2980b9").pack(side="left", padx=5)
        ctk.CTkButton(btn_r, text="Рассчитать", command=self.calc_limiting, width=120).pack(side="left", padx=5)

        self.limit_res = ctk.CTkTextbox(c1, height=180, font=("Consolas", 11), wrap="word")
        self.limit_res.pack(fill="x", padx=15, pady=10)
        self.limit_res.insert("0.0", "Результаты появятся здесь...")

        # --- Под-вкладка 2: Выход продукта ---
        tab_yield = tabview.add("Выход продукта")
        c2 = CardFrame(tab_yield, title="Выход продукта")

        # Теоретический выход
        ctk.CTkLabel(c2, text="--- Теоретический выход ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 3))
        f_ty = ctk.CTkFrame(c2, fg_color="transparent")
        f_ty.pack(fill="x", padx=20)
        ctk.CTkLabel(f_ty, text="m_лим. (г):").pack(side="left", padx=2)
        self.yield_m_lim = ctk.CTkEntry(f_ty, width=70)
        self.yield_m_lim.pack(side="left", padx=2)
        ctk.CTkLabel(f_ty, text="MW_лим.:").pack(side="left", padx=2)
        self.yield_mw_lim = ctk.CTkEntry(f_ty, width=70)
        self.yield_mw_lim.pack(side="left", padx=2)
        ctk.CTkLabel(f_ty, text="коэфф_лим.:").pack(side="left", padx=2)
        self.yield_coeff_lim = ctk.CTkEntry(f_ty, width=60)
        self.yield_coeff_lim.pack(side="left", padx=2)
        ctk.CTkLabel(f_ty, text="MW_прод.:").pack(side="left", padx=2)
        self.yield_mw_prod = ctk.CTkEntry(f_ty, width=70)
        self.yield_mw_prod.pack(side="left", padx=2)
        ctk.CTkLabel(f_ty, text="коэфф_прод.:").pack(side="left", padx=2)
        self.yield_coeff_prod = ctk.CTkEntry(f_ty, width=60)
        self.yield_coeff_prod.pack(side="left", padx=2)
        ctk.CTkButton(f_ty, text="Теор. выход", command=self.calc_theoretical_yield, width=100).pack(side="left", padx=3)
        self.theor_res = ResultLabel(c2, text="...")
        self.theor_res.pack(pady=5)

        # Процентный выход
        ctk.CTkLabel(c2, text="--- Процентный выход ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 3))
        f_py = ctk.CTkFrame(c2, fg_color="transparent")
        f_py.pack(fill="x", padx=20)
        ctk.CTkLabel(f_py, text="Факт. выход (г):").pack(side="left", padx=2)
        self.pct_actual = ctk.CTkEntry(f_py, width=90)
        self.pct_actual.pack(side="left", padx=2)
        ctk.CTkLabel(f_py, text="Теор. выход (г):").pack(side="left", padx=2)
        self.pct_theor = ctk.CTkEntry(f_py, width=90)
        self.pct_theor.pack(side="left", padx=2)
        ctk.CTkButton(f_py, text="% выход", command=self.calc_percent_yield, width=90).pack(side="left", padx=3)
        self.pct_res = ResultLabel(c2, text="...")
        self.pct_res.pack(pady=5)

        # Фактический выход из %
        ctk.CTkLabel(c2, text="--- Фактический выход из % ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 3))
        f_ay = ctk.CTkFrame(c2, fg_color="transparent")
        f_ay.pack(fill="x", padx=20)
        ctk.CTkLabel(f_ay, text="% выход:").pack(side="left", padx=2)
        self.act_pct = ctk.CTkEntry(f_ay, width=80)
        self.act_pct.pack(side="left", padx=2)
        ctk.CTkLabel(f_ay, text="Теор. выход (г):").pack(side="left", padx=2)
        self.act_theor = ctk.CTkEntry(f_ay, width=90)
        self.act_theor.pack(side="left", padx=2)
        ctk.CTkButton(f_ay, text="Факт. выход", command=self.calc_actual_yield, width=100).pack(side="left", padx=3)
        self.act_res = ResultLabel(c2, text="...")
        self.act_res.pack(pady=10)

        # --- Под-вкладка 3: Пересчёты ---
        tab_conv = tabview.add("Пересчёты")
        c3 = CardFrame(tab_conv, title="Пересчёты", desc="Преобразования между массой, молями, объёмом, частицами")

        # Масса → Моли
        ctk.CTkLabel(c3, text="--- Масса → Моли ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 3))
        f1 = ctk.CTkFrame(c3, fg_color="transparent")
        f1.pack(fill="x", padx=20)
        ctk.CTkLabel(f1, text="m (г):").pack(side="left", padx=2)
        self.conv_mass = ctk.CTkEntry(f1, width=80)
        self.conv_mass.pack(side="left", padx=2)
        ctk.CTkLabel(f1, text="MW (г/моль):").pack(side="left", padx=2)
        self.conv_mw1 = ctk.CTkEntry(f1, width=80)
        self.conv_mw1.pack(side="left", padx=2)
        ctk.CTkButton(f1, text="→ Моли", command=self.conv_mass_to_moles, width=80).pack(side="left", padx=3)
        self.conv_mol_res = ResultLabel(c3, text="...")
        self.conv_mol_res.pack(pady=5)

        # Моли → Масса
        ctk.CTkLabel(c3, text="--- Моли → Масса ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 3))
        f2 = ctk.CTkFrame(c3, fg_color="transparent")
        f2.pack(fill="x", padx=20)
        ctk.CTkLabel(f2, text="n (моль):").pack(side="left", padx=2)
        self.conv_mol = ctk.CTkEntry(f2, width=80)
        self.conv_mol.pack(side="left", padx=2)
        ctk.CTkLabel(f2, text="MW (г/моль):").pack(side="left", padx=2)
        self.conv_mw2 = ctk.CTkEntry(f2, width=80)
        self.conv_mw2.pack(side="left", padx=2)
        ctk.CTkButton(f2, text="→ Масса", command=self.conv_moles_to_mass, width=80).pack(side="left", padx=3)
        self.conv_mass_res = ResultLabel(c3, text="...")
        self.conv_mass_res.pack(pady=5)

        # Моли → Объём газа (н.у.)
        ctk.CTkLabel(c3, text="--- Моли → Объём газа (н.у.) ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 3))
        f3 = ctk.CTkFrame(c3, fg_color="transparent")
        f3.pack(fill="x", padx=20)
        ctk.CTkLabel(f3, text="n (моль):").pack(side="left", padx=2)
        self.conv_mol_vol = ctk.CTkEntry(f3, width=100)
        self.conv_mol_vol.pack(side="left", padx=2)
        ctk.CTkButton(f3, text="→ Объём", command=self.conv_moles_to_volume, width=80).pack(side="left", padx=3)
        self.conv_vol_res = ResultLabel(c3, text="...")
        self.conv_vol_res.pack(pady=5)

        # Объём газа → Моли
        ctk.CTkLabel(c3, text="--- Объём газа → Моли ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 3))
        f4 = ctk.CTkFrame(c3, fg_color="transparent")
        f4.pack(fill="x", padx=20)
        ctk.CTkLabel(f4, text="V (Л):").pack(side="left", padx=2)
        self.conv_vol = ctk.CTkEntry(f4, width=80)
        self.conv_vol.pack(side="left", padx=2)
        ctk.CTkLabel(f4, text="T (K):").pack(side="left", padx=2)
        self.conv_t = ctk.CTkEntry(f4, width=70)
        self.conv_t.pack(side="left", padx=2)
        ctk.CTkLabel(f4, text="P (атм):").pack(side="left", padx=2)
        self.conv_p = ctk.CTkEntry(f4, width=70)
        self.conv_p.pack(side="left", padx=2)
        ctk.CTkButton(f4, text="→ Моли", command=self.conv_volume_to_moles, width=80).pack(side="left", padx=3)
        self.conv_volmol_res = ResultLabel(c3, text="...")
        self.conv_volmol_res.pack(pady=5)

        # Моли → Частицы
        ctk.CTkLabel(c3, text="--- Моли → Частицы ---", font=("Arial", 12, "bold"),
                     text_color="gray80").pack(anchor="w", padx=20, pady=(10, 3))
        f5 = ctk.CTkFrame(c3, fg_color="transparent")
        f5.pack(fill="x", padx=20)
        ctk.CTkLabel(f5, text="n (моль):").pack(side="left", padx=2)
        self.conv_mol_part = ctk.CTkEntry(f5, width=100)
        self.conv_mol_part.pack(side="left", padx=2)
        ctk.CTkButton(f5, text="→ Частицы", command=self.conv_moles_to_particles, width=100).pack(side="left", padx=3)
        self.conv_part_res = ResultLabel(c3, text="...")
        self.conv_part_res.pack(pady=10)

    # ---- Вспомогательные ----

    def _add_reagent_row(self, default_name="Реагент"):
        row = ctk.CTkFrame(self.reagent_scroll, fg_color="transparent")
        row.pack(fill="x", pady=2)
        name_e = ctk.CTkEntry(row, width=90, placeholder_text="Название")
        name_e.pack(side="left", padx=2)
        name_e.insert(0, default_name)
        mass_e = ctk.CTkEntry(row, width=70, placeholder_text="m (г)")
        mass_e.pack(side="left", padx=2)
        mw_e = ctk.CTkEntry(row, width=70, placeholder_text="MW")
        mw_e.pack(side="left", padx=2)
        coeff_e = ctk.CTkEntry(row, width=50, placeholder_text="коэфф.")
        coeff_e.pack(side="left", padx=2)
        coeff_e.insert(0, "1")
        del_btn = ctk.CTkButton(row, text="✕", width=30, fg_color="gray",
                                command=lambda: self._remove_reagent_row(row))
        del_btn.pack(side="left", padx=3)
        self.reagent_rows.append((row, name_e, mass_e, mw_e, coeff_e))

    def _remove_reagent_row(self, frame):
        for i, (f, n, m, mw, c) in enumerate(self.reagent_rows):
            if f is frame:
                self.reagent_rows.pop(i)
                frame.destroy()
                break

    # ---- Расчёты ----

    def calc_limiting(self):
        try:
            masses = []
            molar_masses = []
            coefficients = []
            names = []

            for _, name_e, mass_e, mw_e, coeff_e in self.reagent_rows:
                name = name_e.get().strip() or "?"
                masses.append(float(mass_e.get()))
                molar_masses.append(float(mw_e.get()))
                coefficients.append(float(coeff_e.get()))
                names.append(name)

            result = StoichiometryCalculator.limiting_reagent(masses, molar_masses, coefficients)

            self.limit_res.delete("0.0", "end")
            lines = []

            if isinstance(result, dict):
                limiting_idx = result.get("limiting_index", result.get("limiting_reagent", None))
                if limiting_idx is not None and isinstance(limiting_idx, int) and limiting_idx < len(names):
                    lines.append(f"Лимитирующий реагент: {names[limiting_idx]}\n")
                    lines.append(f"{'─' * 40}\n")
                for i, name in enumerate(names):
                    avail_mol = masses[i] / molar_masses[i]
                    needed_str = ""
                    if isinstance(result, dict) and "needed_moles" in result:
                        needed = result["needed_moles"]
                        if i < len(needed):
                            needed_str = f" | Нужно: {needed[i]:.6g} моль"
                    lines.append(f"{name}: {masses[i]} г → {avail_mol:.6g} моль{needed_str}\n")
                if "excess" in result:
                    lines.append(f"\nИзбыток: {result['excess']}\n")
            else:
                lines.append(str(result))

            self.limit_res.insert("0.0", "".join(lines))
            HistoryManager.add("Лимит. реагент", f"{len(names)} реагентов рассчитано")
        except Exception as e:
            self.limit_res.delete("0.0", "end")
            self.limit_res.insert("0.0", f"Ошибка: {e}")

    def calc_theoretical_yield(self):
        try:
            m_lim = float(self.yield_m_lim.get())
            mw_lim = float(self.yield_mw_lim.get())
            coeff_lim = float(self.yield_coeff_lim.get())
            mw_prod = float(self.yield_mw_prod.get())
            coeff_prod = float(self.yield_coeff_prod.get())

            result = StoichiometryCalculator.theoretical_yield(m_lim, mw_lim, coeff_lim, mw_prod, coeff_prod)

            if isinstance(result, dict):
                mass_prod = result.get("mass", result.get("theoretical_yield", result))
            else:
                mass_prod = result

            self.theor_res.configure(text=f"Теор. выход = {mass_prod:.6g} г", text_color="#4facfe")
            HistoryManager.add("Теор. выход", f"{mass_prod:.6g} г")
        except Exception as e:
            self.theor_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_percent_yield(self):
        try:
            actual = float(self.pct_actual.get())
            theoretical = float(self.pct_theor.get())
            pct = StoichiometryCalculator.percent_yield(actual, theoretical)
            if isinstance(pct, dict):
                pct = pct.get("percent", pct.get("result", pct))
            self.pct_res.configure(text=f"Выход = {pct:.4f}%", text_color="#4facfe")
            HistoryManager.add("% выход", f"{pct:.4f}%")
        except Exception as e:
            self.pct_res.configure(text=f"Ошибка: {e}", text_color="red")

    def calc_actual_yield(self):
        try:
            pct = float(self.act_pct.get())
            theoretical = float(self.act_theor.get())
            actual = StoichiometryCalculator.actual_yield(pct, theoretical)
            if isinstance(actual, dict):
                actual = actual.get("mass", actual.get("result", actual))
            self.act_res.configure(text=f"Факт. выход = {actual:.6g} г", text_color="#4facfe")
            HistoryManager.add("Факт. выход", f"{actual:.6g} г")
        except Exception as e:
            self.act_res.configure(text=f"Ошибка: {e}", text_color="red")

    def conv_mass_to_moles(self):
        try:
            mass = float(self.conv_mass.get())
            mw = float(self.conv_mw1.get())
            n = StoichiometryCalculator.moles_from_mass(mass, mw)
            if isinstance(n, dict):
                n = n.get("moles", n.get("result", n))
            self.conv_mol_res.configure(text=f"n = {n:.6g} моль", text_color="#4facfe")
            HistoryManager.add("Масса→Моли", f"{n:.6g} моль")
        except Exception as e:
            self.conv_mol_res.configure(text=f"Ошибка: {e}", text_color="red")

    def conv_moles_to_mass(self):
        try:
            moles = float(self.conv_mol.get())
            mw = float(self.conv_mw2.get())
            m = StoichiometryCalculator.mass_from_moles(moles, mw)
            if isinstance(m, dict):
                m = m.get("mass", m.get("result", m))
            self.conv_mass_res.configure(text=f"m = {m:.6g} г", text_color="#4facfe")
            HistoryManager.add("Моли→Масса", f"{m:.6g} г")
        except Exception as e:
            self.conv_mass_res.configure(text=f"Ошибка: {e}", text_color="red")

    def conv_moles_to_volume(self):
        try:
            moles = float(self.conv_mol_vol.get())
            v = StoichiometryCalculator.volume_of_gas_at_stp(moles)
            if isinstance(v, dict):
                v = v.get("volume", v.get("result", v))
            self.conv_vol_res.configure(text=f"V = {v:.6g} Л (н.у.)", text_color="#4facfe")
            HistoryManager.add("Моли→Объём", f"{v:.6g} Л")
        except Exception as e:
            self.conv_vol_res.configure(text=f"Ошибка: {e}", text_color="red")

    def conv_volume_to_moles(self):
        try:
            vol = float(self.conv_vol.get())
            T = float(self.conv_t.get())
            P = float(self.conv_p.get())
            n = StoichiometryCalculator.moles_from_gas_volume(vol, T, P)
            if isinstance(n, dict):
                n = n.get("moles", n.get("result", n))
            self.conv_volmol_res.configure(text=f"n = {n:.6g} моль", text_color="#4facfe")
            HistoryManager.add("Объём→Моли", f"{n:.6g} моль")
        except Exception as e:
            self.conv_volmol_res.configure(text=f"Ошибка: {e}", text_color="red")

    def conv_moles_to_particles(self):
        try:
            moles = float(self.conv_mol_part.get())
            count = StoichiometryCalculator.particles_count(moles)
            if isinstance(count, dict):
                count = count.get("count", count.get("result", count))
            # Форматируем в научной нотации
            self.conv_part_res.configure(text=f"N = {count:.4e}", text_color="#4facfe")
            HistoryManager.add("Моли→Частицы", f"N = {count:.4e}")
        except Exception as e:
            self.conv_part_res.configure(text=f"Ошибка: {e}", text_color="red")
