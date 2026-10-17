import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import math
import json
import numpy as np
from datetime import datetime

# Импорт логики
from alchemy_core import (
    CONSTANTS, LAYOUT_CACHE, ELEMENTS_RU, CATEGORIES_RU, CATEGORY_COLORS,
    HAS_MENDELEEV, HAS_CHEMPY, LibraryManager, HistoryManager, ContextManager,
    FormulaParser, EquationBalancer, UnitConverter, AIAssistantStub,
    SolutionCalculator, GasCalculator, ThermoCalculator, KineticsCalculator,
    ElectrochemistryCalculator, AcidBaseCalculator, ColligativeCalculator,
    StoichiometryCalculator
)

try:
    from mendeleev import element

    HAS_MENDELEEV = True
except ImportError:
    HAS_MENDELEEV = False

COLOR_CARD_BG = ("#2b2b2b", "#2b2b2b")

# Проверка библиотек (Графика)
HAS_MATPLOTLIB = False
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    HAS_MATPLOTLIB = True
except ImportError:
    pass


# UI Компоненты
class CardFrame(ctk.CTkFrame):
    def __init__(self, master, title=None, desc=None, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD_BG, corner_radius=10, **kwargs)
        self.pack(fill="x", padx=10, pady=10)
        if title:
            h = ctk.CTkFrame(self, fg_color="transparent")
            h.pack(fill="x", padx=15, pady=(10, 5))
            ctk.CTkLabel(h, text=title, font=("Roboto Medium", 14), text_color="gray90").pack(anchor="w")
            if desc:
                ctk.CTkLabel(h, text=desc, font=("Arial", 11), text_color="gray60", wraplength=500,
                             justify="left").pack(anchor="w")
        ctk.CTkFrame(self, height=2, fg_color="gray30").pack(fill="x", padx=10, pady=(0, 10))


class ResultLabel(ctk.CTkLabel):
    def __init__(self, master, text="...", **kwargs):
        super().__init__(master, text=text, font=("Consolas", 18, "bold"), text_color="#4facfe", **kwargs)


# ВКЛАДКИ
class AddSubstanceDialog(ctk.CTkToplevel):
    def __init__(self, master, category, callback):
        super().__init__(master)
        self.title("Добавить запись")
        self.geometry("350x280")
        self.category = category
        self.callback = callback

        ctk.CTkLabel(self, text=f"Категория: '{category}'", font=("Roboto Medium", 14)).pack(pady=10)

        self.e1 = ctk.CTkEntry(self, placeholder_text="Название")
        self.e1.pack(pady=5, padx=20, fill="x")

        self.e2 = ctk.CTkEntry(self, placeholder_text="Формула/Значение")
        self.e2.pack(pady=5, padx=20, fill="x")

        self.e3 = ctk.CTkEntry(self, placeholder_text="Дополнительная информация")
        self.e3.pack(pady=5, padx=20, fill="x")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)
        ctk.CTkButton(btn_frame, text="Сохранить", command=self.save, width=100).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Отмена", command=self.destroy, width=100, fg_color="gray").pack(side="left",
                                                                                                       padx=5)

    def save(self):
        if not self.e1.get().strip():
            messagebox.showwarning("Внимание", "Введите название!")
            return
        entry = {
            "Название": self.e1.get().strip(),
            "Значение": self.e2.get().strip() if self.e2.get() else "-",
            "Инфо": self.e3.get().strip() if self.e3.get() else "-"
        }
        self.callback(self.category, entry)
        self.destroy()


class HandbookTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        # Панель управления
        ctrl = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG)
        ctrl.pack(fill="x", padx=10, pady=10)

        self.data = LibraryManager.get_data()
        self.cats = list(self.data.keys()) or ["Растворители", "Кислоты", "Щелочи"]
        self.cat_var = ctk.StringVar(value=self.cats[0] if self.cats else "")

        self.om = ctk.CTkOptionMenu(ctrl, values=self.cats, variable=self.cat_var, command=self.refresh)
        self.om.pack(side="left", padx=10)

        ctk.CTkButton(ctrl, text="➕ Добавить", width=100, command=self.open_add_dialog).pack(side="left", padx=5)

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", lambda *args: self.refresh())
        ctk.CTkEntry(ctrl, textvariable=self.search_var, placeholder_text="Поиск...").pack(side="left", fill="x",
                                                                                           expand=True, padx=10)

        # Область прокрутки для данных
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.refresh()

    def refresh(self, *args):
        for w in self.scroll.winfo_children():
            w.destroy()

        self.data = LibraryManager.get_data()
        cat = self.cat_var.get()
        if cat not in self.data:
            return

        items = self.data[cat]
        query = self.search_var.get().lower()

        if not items:
            ctk.CTkLabel(self.scroll, text="Нет записей", text_color="gray").pack(pady=20)
            return

        # Заголовки таблицы
        headers = list(items[0].keys())
        h_frame = ctk.CTkFrame(self.scroll, fg_color="gray25")
        h_frame.pack(fill="x", padx=5, pady=2)
        for h in headers:
            ctk.CTkLabel(h_frame, text=h, width=150, anchor="w", font=("Arial", 11, "bold")).pack(side="left", padx=5)

        # Данные
        for item in items:
            if query and not any(query in str(v).lower() for v in item.values()):
                continue

            row = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD_BG)
            row.pack(fill="x", padx=5, pady=2)

            for k in headers:
                val = str(item.get(k, "-"))
                ctk.CTkLabel(row, text=val, width=150, anchor="w").pack(side="left", padx=5)

            ctk.CTkButton(row, text="Коп.", width=45, font=("Arial", 10),
                          command=lambda t=str(item): self.master.clipboard_append(t)).pack(side="right", padx=5)

    def open_add_dialog(self):
        AddSubstanceDialog(self, self.cat_var.get(), lambda c, e: [LibraryManager.add_entry(c, e), self.refresh()])


class HistoryTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        c = CardFrame(self, title="Журнал операций", desc="Последние 100 действий")
        b = ctk.CTkFrame(c, fg_color="transparent")
        b.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(b, text="💾 Сохранить", width=90, command=self.export_log, fg_color="#27ae60").pack(side="left",
                                                                                                         padx=2)
        ctk.CTkButton(b, text="📂 Открыть", width=90, command=self.import_log, fg_color="#2980b9").pack(side="left",
                                                                                                       padx=2)
        ctk.CTkButton(b, text="🔄 Обновить", width=90, command=self.refresh).pack(side="left", padx=2)
        ctk.CTkButton(b, text="🗑 Очистить", width=90, fg_color="#c0392b",
                      command=lambda: [HistoryManager.clear(), self.refresh()]).pack(side="right", padx=2)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)
        self.refresh()

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        log = HistoryManager.get_log()
        if not log:
            ctk.CTkLabel(self.scroll, text="Журнал пуст", text_color="gray", font=("Arial", 14)).pack(pady=30)
            return

        for item in log:
            r = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD_BG)
            r.pack(fill="x", pady=2, padx=5)

            ctk.CTkLabel(r, text=item['time'], width=70, text_color="gray", font=("Consolas", 11)).pack(side="left",
                                                                                                        padx=5)

            m = ctk.CTkFrame(r, fg_color="transparent")
            m.pack(side="left", fill="x", expand=True, padx=5)

            ctk.CTkLabel(m, text=item['action'], font=("Arial", 12, "bold"), anchor="w", text_color="white").pack(
                fill="x", anchor="w")
            ctk.CTkLabel(m, text=item['result'], text_color="#4facfe", anchor="w", font=("Consolas", 12)).pack(fill="x",
                                                                                                               anchor="w")

            ctk.CTkButton(r, text="📋", width=35, font=("Arial", 10),
                          command=lambda t=f"{item['action']}: {item['result']}": self.master.clipboard_append(t)).pack(
                side="right", padx=5)

    def export_log(self):
        f = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if f:
            try:
                with open(f, 'w', encoding='utf-8') as file:
                    json.dump(HistoryManager.get_log(), file, indent=2, ensure_ascii=False)
                messagebox.showinfo("Успех", f"Журнал сохранен в {f}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")

    def import_log(self):
        f = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if f:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    HistoryManager.set_log(json.load(file))
                self.refresh()
                messagebox.showinfo("Успех", "Журнал загружен")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить: {e}")


class MolarMassTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        c = CardFrame(self, title="Молярная масса", desc="Введите формулу (напр. CuSO4*5H2O или C6H12O6)")
        self.entry = ctk.CTkEntry(c, width=250, font=("Consolas", 14))
        self.entry.pack(pady=10, padx=20)
        self.entry.bind("<Return>", lambda e: self.calc())

        btn_frame = ctk.CTkFrame(c, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Рассчитать", command=self.calc, width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Очистить", command=self.clear, width=100, fg_color="gray").pack(side="left",
                                                                                                       padx=5)

        self.res = ResultLabel(c, text="0.0000 г/моль")
        self.res.pack(pady=10)

        self.act_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.act_frame.pack(pady=10, padx=20, fill="x")

        self.last_mass = 0.0
        self.last_formula = ""

    def clear(self):
        self.entry.delete(0, "end")
        self.res.configure(text="0.0000 г/моль")
        for w in self.act_frame.winfo_children():
            w.destroy()

    def calc(self):
        f = self.entry.get().strip()
        if not f:
            return

        self.last_formula = f
        m = FormulaParser.calculate_mass(f)
        if m == 0.0:
            self.res.configure(text="Ошибка: не удалось распознать формулу")
            return

        self.last_mass = m
        self.res.configure(text=f"{m:.4f} г/моль")
        HistoryManager.add(f"MM ({f})", f"{m:.4f} г/моль")

        # Очистка и создание кнопок действий
        for w in self.act_frame.winfo_children():
            w.destroy()

        ctk.CTkLabel(self.act_frame, text="Действия:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 5))

        btn_frame = ctk.CTkFrame(self.act_frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(btn_frame, text="🧪 Рецепт раствора", width=130, fg_color="#27ae60",
                      command=lambda: self.controller.transfer(SolutionRecipeTab, "mw", self.last_mass)).pack(
            side="left", padx=3)
        ctk.CTkButton(btn_frame, text="⚖️ Стехиометрия", width=130, fg_color="#8e44ad",
                      command=lambda: self.controller.transfer(StoichiometryTab, "mw", self.last_mass)).pack(
            side="left", padx=3)
        ctk.CTkButton(btn_frame, text="💧 Концентрация", width=130, fg_color="#2980b9",
                      command=lambda: self.controller.transfer(ConcentrationTab, "mw", self.last_mass)).pack(
            side="left", padx=3)
        ctk.CTkButton(btn_frame, text="📋 В буфер", width=100, fg_color="#e67e22",
                      command=lambda: ContextManager.set(f"{self.last_mass:.4f}", f"MM({self.last_formula})")).pack(
            side="left", padx=3)


class SolutionRecipeTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        c = CardFrame(self, title="Рецепт раствора", desc="Рассчитайте массу вещества для приготовления раствора")
        f = ctk.CTkFrame(c, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(f, text="Объем (мл):").pack(side="left", padx=5)
        self.ev = ctk.CTkEntry(f, width=80)
        self.ev.pack(side="left", padx=5)
        self.ev.insert(0, "100")

        ctk.CTkLabel(f, text="Концентрация (М):").pack(side="left", padx=10)
        self.ec = ctk.CTkEntry(f, width=80)
        self.ec.pack(side="left", padx=5)
        self.ec.insert(0, "1.0")

        ctk.CTkLabel(f, text="Молярная масса:").pack(side="left", padx=10)
        self.em = ctk.CTkEntry(f, width=90)
        self.em.pack(side="left", padx=5)

        btn = ctk.CTkButton(c, text="Рассчитать рецепт", command=self.gen, width=150)
        btn.pack(pady=10)

        self.out = ctk.CTkLabel(CardFrame(self, title="Инструкция приготовления"),
                                text="Введите параметры и нажмите 'Рассчитать'",
                                justify="left", wraplength=450)
        self.out.pack(pady=10, padx=20)

    def receive_data(self, key, val):
        if key == "mw":
            self.em.delete(0, "end")
            self.em.insert(0, f"{float(val):.4f}")
            self.gen()  # Автоматический расчет при получении MW

    def gen(self):
        try:
            v = float(self.ev.get())
            c = float(self.ec.get())
            m = float(self.em.get())

            if v <= 0 or c <= 0 or m <= 0:
                raise ValueError("Все значения должны быть положительными")

            grams = c * (v / 1000) * m
            self.out.configure(text=f"1. Взвесьте точно {grams:.4f} г вещества.\n"
                                    f"2. Перенесите в мерную колбу на {v} мл.\n"
                                    f"3. Добавьте растворитель (воду) до метки.\n"
                                    f"4. Тщательно перемешайте до полного растворения.")
            HistoryManager.add("Рецепт раствора", f"{grams:.4f}г для {v}мл {c}M")
        except Exception as e:
            self.out.configure(text=f"Ошибка: {str(e)}\nПроверьте правильность ввода чисел.")


class ConcentrationTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Молярность (C = n/V)")
        f = ctk.CTkFrame(c, fg_color="transparent")
        f.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(f, text="Масса (г):").pack(side="left", padx=5)
        self.m = ctk.CTkEntry(f, width=80)
        self.m.pack(side="left", padx=5)

        ctk.CTkLabel(f, text="Молярная масса:").pack(side="left", padx=10)
        self.mw = ctk.CTkEntry(f, width=80)
        self.mw.pack(side="left", padx=5)

        ctk.CTkLabel(f, text="Объем (л):").pack(side="left", padx=10)
        self.v = ctk.CTkEntry(f, width=80)
        self.v.pack(side="left", padx=5)

        ctk.CTkButton(c, text="Рассчитать", command=self.calc, width=120).pack(pady=10)
        self.res = ResultLabel(c, text="-")
        self.res.pack(pady=5)

    def receive_data(self, k, v):
        if k == "mw":
            self.mw.delete(0, "end")
            self.mw.insert(0, str(v))

    def calc(self):
        try:
            mass = float(self.m.get())
            mw = float(self.mw.get())
            vol = float(self.v.get())

            if mw <= 0 or vol <= 0:
                raise ValueError("MW и объем должны быть > 0")

            molarity = (mass / mw) / vol
            self.res.configure(text=f"{molarity:.4f} M")
            HistoryManager.add("Молярность", f"{molarity:.4f} M")
        except Exception as e:
            self.res.configure(text="Ошибка ввода")


class DilutionTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Разбавление (C₁V₁ = C₂V₂)", desc="Оставьте одно поле пустым для расчета")
        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(pady=10, padx=20)

        self.entries = {}
        labels = ["C₁ (исходная)", "V₁ (объем 1)", "C₂ (целевая)", "V₂ (объем 2)"]
        keys = ["c1", "v1", "c2", "v2"]

        for i, (txt, key) in enumerate(zip(labels, keys)):
            row = i // 2
            col = (i % 2) * 2

            ctk.CTkLabel(grid, text=txt, font=("Arial", 11)).grid(row=row * 2, column=col, padx=5, pady=(5, 0),
                                                                  sticky="w")
            e = ctk.CTkEntry(grid, width=100)
            e.grid(row=row * 2 + 1, column=col, padx=5, pady=(0, 10))
            self.entries[key] = e

        ctk.CTkButton(c, text="Рассчитать", command=self.calc, width=150).pack(pady=10)
        self.res = ResultLabel(c, text="Результат появится здесь")
        self.res.pack(pady=10)

    def calc(self):
        try:
            vals = {}
            for k, e in self.entries.items():
                txt = e.get().strip()
                vals[k] = float(txt) if txt else None

            none_count = sum(1 for v in vals.values() if v is None)
            if none_count != 1:
                self.res.configure(text="Оставьте ровно 1 поле пустым", text_color="orange")
                return

            if vals['c1'] is None:
                res = (vals['c2'] * vals['v2']) / vals['v1']
                tgt = "C₁"
            elif vals['v1'] is None:
                res = (vals['c2'] * vals['v2']) / vals['c1']
                tgt = "V₁"
            elif vals['c2'] is None:
                res = (vals['c1'] * vals['v1']) / vals['v2']
                tgt = "C₂"
            else:  # vals['v2'] is None
                res = (vals['c1'] * vals['v1']) / vals['c2']
                tgt = "V₂"

            self.res.configure(text=f"{tgt} = {res:.4f}", text_color="#4facfe")
            HistoryManager.add("Разбавление", f"{tgt} = {res:.4f}")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class StoichiometryTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Стехиометрия", desc="Расчет массы продукта по массе реагента")
        g = ctk.CTkFrame(c, fg_color="transparent")
        g.pack(padx=20, pady=15)

        # Реагент А
        ctk.CTkLabel(g, text="Реагент A:", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 5))
        ctk.CTkLabel(g, text="Масса A (г):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.mA = ctk.CTkEntry(g, width=100)
        self.mA.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(g, text="Молярная масса A:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.MA = ctk.CTkEntry(g, width=100)
        self.MA.grid(row=2, column=1, padx=5, pady=5)

        # Коэффициенты
        ctk.CTkLabel(g, text="Коэффициенты (A:B):").grid(row=3, column=0, padx=5, pady=10, sticky="e")
        coef_frame = ctk.CTkFrame(g, fg_color="transparent")
        coef_frame.grid(row=3, column=1, padx=5, pady=10)
        self.coefA = ctk.CTkEntry(coef_frame, width=40, placeholder_text="1")
        self.coefA.pack(side="left", padx=(0, 5))
        ctk.CTkLabel(coef_frame, text=":").pack(side="left", padx=5)
        self.coefB = ctk.CTkEntry(coef_frame, width=40, placeholder_text="1")
        self.coefB.pack(side="left", padx=(5, 0))

        # Продукт B
        ctk.CTkLabel(g, text="Продукт B:", font=("Arial", 12, "bold")).grid(row=4, column=0, columnspan=2, pady=(15, 5))
        ctk.CTkLabel(g, text="Молярная масса B:").grid(row=5, column=0, padx=5, pady=5, sticky="e")
        self.MB = ctk.CTkEntry(g, width=100)
        self.MB.grid(row=5, column=1, padx=5, pady=5)

        btn_frame = ctk.CTkFrame(c, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Рассчитать массу B", command=self.calc, width=160).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Вставить из буфера", command=self.paste, width=140, fg_color="gray").pack(
            side="left", padx=5)

        self.res = ResultLabel(c, text="0.0000 г")
        self.res.pack(pady=10)

    def receive_data(self, k, v):
        if k == "mw":
            self.MA.delete(0, "end")
            self.MA.insert(0, str(v))

    def paste(self):
        v = ContextManager.get()
        if v != "-":
            self.receive_data("mw", v)

    def calc(self):
        try:
            mA = float(self.mA.get())
            MA = float(self.MA.get())
            MB = float(self.MB.get())
            coefA = float(self.coefA.get() or "1")
            coefB = float(self.coefB.get() or "1")

            if mA <= 0 or MA <= 0 or MB <= 0 or coefA <= 0 or coefB <= 0:
                raise ValueError("Все значения должны быть положительными")

            # Расчет: (mA / MA) * (coefB / coefA) * MB
            molesA = mA / MA
            molesB = molesA * (coefB / coefA)
            massB = molesB * MB

            self.res.configure(text=f"{massB:.4f} г")
            HistoryManager.add("Стехиометрия", f"{massB:.4f} г продукта B")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class PeriodicTableTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        # --- ВЕРХНЯЯ ПАНЕЛЬ (Fix "что вверху") ---
        # Используем обычный фрейм с фиксированной высотой для аккуратности
        self.ctx = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, height=55)
        self.ctx.pack(fill="x", pady=(10, 5), padx=10)
        self.ctx.pack_propagate(False)  # Запрещаем изменение размера

        # Заголовок слева
        self.ctx_lbl = ctk.CTkLabel(self.ctx, text="Периодическая таблица",
                                    font=("Roboto Medium", 16), text_color="#4facfe")
        self.ctx_lbl.pack(side="left", padx=15, pady=10)

        # Контейнер для кнопок справа (чтобы они не сползали)
        self.action_container = ctk.CTkFrame(self.ctx, fg_color="transparent")
        self.action_container.pack(side="right", padx=10)

        # --- ОСНОВНАЯ ОБЛАСТЬ ТАБЛИЦЫ (Без прокрутки) ---
        # Используем обычный Frame, а не Scrollable
        self.center_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.center_frame.pack(fill="both", expand=True)

        # Фрейм для сетки (чтобы центрировать его)
        self.grid_frame = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        # pack с expand=True центрирует фиксированный фрейм внутри доступного места
        self.grid_frame.pack(expand=True)

        # --- РИСОВАНИЕ ТАБЛИЦЫ ---
        # Внутренний фрейм, куда кладем кнопки
        inner = ctk.CTkFrame(self.grid_frame, fg_color="transparent")
        # inner.place(relx=0.5, rely=0.5, anchor="center") # Альтернатива центрированию
        inner.pack()

        # Создание кнопок элементов
        for symbol, data in LAYOUT_CACHE.items():
            atomic_num = data[0]
            group = data[1]
            period = data[2]
            category = data[3]

            # Обработка лантаноидов и актиноидов
            if 57 <= atomic_num <= 71:
                period = 9
                group = atomic_num - 57 + 3
            elif 89 <= atomic_num <= 103:
                period = 10
                group = atomic_num - 89 + 3

            color = CATEGORY_COLORS.get(category, "gray")
            # Цвет текста для элементов с темным фоном
            text_color = "white" if category not in ['nonmetal', 'noble', 'metalloid'] else "black"

            btn = ctk.CTkButton(
                inner,
                text=f"{symbol}\n{atomic_num}",
                width=40,  # Уменьшен с 45 до 40 для лучшей вписываемости
                height=45,  # Уменьшен с 50 до 45
                fg_color=color,
                text_color=text_color,
                font=("Arial", 9, "bold"),  # Шрифт чуть меньше
                corner_radius=2,
                command=lambda s=symbol: self.select_element(s)
            )
            btn.grid(row=period, column=group, padx=1, pady=1)

        # Добавление меток периодов и групп
        for p in range(1, 8):
            ctk.CTkLabel(inner, text=str(p), width=25, font=("Arial", 8)).grid(row=p, column=0, padx=1)

        for g in range(1, 19):
            ctk.CTkLabel(inner, text=str(g), width=40, height=15, font=("Arial", 8), fg_color="#333333",
                         corner_radius=2).grid(row=0, column=g, padx=1)

        # --- НИЖНЯЯ ПАНЕЛЬ ИНФОРМАЦИИ ---
        info_frame = CardFrame(self, title="Информация об элементе")
        self.info_panel = ctk.CTkTextbox(info_frame, height=200, font=("Consolas", 11), wrap="word")
        self.info_panel.pack(fill="both", expand=True, padx=10, pady=10)
        self.info_panel.insert("0.0", "Нажмите на элемент в таблице для отображения подробной информации.\n"
                                      "Данные загружаются из библиотеки mendeleev (если установлена).")

    def select_element(self, symbol):
        name_ru = ELEMENTS_RU.get(symbol, symbol)
        self.ctx_lbl.configure(text=f"Выбран: {name_ru} ({symbol})", text_color="white")

        # Очистка контейнера кнопок действий
        for w in self.action_container.winfo_children():
            w.destroy()

        # Добавление кнопок действий в контейнер справа
        ctk.CTkButton(self.action_container, text="Электроны", width=70, height=30, fg_color="#d35400",
                      command=lambda: self.controller.transfer(ElectronTab, "el", symbol)).pack(side="left", padx=2)
        ctk.CTkButton(self.action_container, text="Связи", width=60, height=30, fg_color="#2980b9",
                      command=lambda: self.controller.transfer(BondingTab, "el", symbol)).pack(side="left", padx=2)
        ctk.CTkButton(self.action_container, text="MM", width=50, height=30, fg_color="#27ae60",
                      command=lambda: self.controller.transfer(MolarMassTab, "formula", symbol)).pack(side="left",
                                                                                                      padx=2)

        # Отображение информации
        if HAS_MENDELEEV:
            try:
                el = element(symbol)
                cat_en = LAYOUT_CACHE[symbol][3]
                cat_ru = CATEGORIES_RU.get(cat_en, cat_en)

                info = f"{'=' * 50}\n"
                info += f"Элемент: {name_ru} ({el.name})\n"
                info += f"Символ: {el.symbol} | Атомный номер: {el.atomic_number}\n"
                info += f"Атомная масса: {el.atomic_weight:.4f} а.е.м.\n"
                info += f"Категория: {cat_ru}\n"
                info += f"Электронная конфигурация: {el.econf}\n"
                info += f"{'-' * 50}\n"

                props = []
                if el.en_pauling is not None:
                    props.append(f"ЭО: {el.en_pauling}")
                if el.atomic_radius is not None:
                    props.append(f"Радиус: {el.atomic_radius} пм")
                if el.density is not None:
                    props.append(f"Плотность: {el.density} г/см³")
                if el.melting_point is not None:
                    props.append(f"Т.пл.: {el.melting_point - 273.15:.1f} °C")
                if el.boiling_point is not None:
                    props.append(f"Т.кип.: {el.boiling_point - 273.15:.1f} °C")
                if el.oxistates:
                    props.append(f"Степени окисления: {', '.join(map(str, sorted(set(el.oxistates))))}")

                if props:
                    info += "\n".join(props)
                else:
                    info += "Свойства недоступны"

                info += f"\n{'=' * 50}"

                self.info_panel.delete("0.0", "end")
                self.info_panel.insert("0.0", info)
                HistoryManager.add("Периодическая таблица", f"{name_ru}")
            except Exception as e:
                self.info_panel.delete("0.0", "end")
                self.info_panel.insert("0.0", f"Ошибка: {e}")
        else:
            self.info_panel.delete("0.0", "end")
            self.info_panel.insert("0.0", "Библиотека mendeleev не установлена.\nУстановите: pip install mendeleev")


class ElectronTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Электронная конфигурация")
        self.e = ctk.CTkEntry(c, placeholder_text="Символ элемента (напр. Fe, O, Na)")
        self.e.pack(pady=10, padx=20, fill="x")
        self.e.bind("<Return>", lambda e: self.show())

        btn_frame = ctk.CTkFrame(c, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Показать конфигурацию", command=self.show).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Очистить", command=self.clear, fg_color="gray").pack(side="left", padx=5)

        self.res = ctk.CTkLabel(c, text="", font=("Consolas", 14), justify="left", wraplength=450)
        self.res.pack(pady=15, padx=20)

    def clear(self):
        self.e.delete(0, "end")
        self.res.configure(text="")

    def receive_data(self, k, v):
        if k == "el":
            self.e.delete(0, "end")
            self.e.insert(0, v)
            self.show()

    def show(self):
        sym = self.e.get().strip()
        if not sym:
            self.res.configure(text="Введите символ элемента")
            return

        if not HAS_MENDELEEV:
            self.res.configure(text="Требуется библиотека mendeleev\nУстановите: pip install mendeleev")
            return

        try:
            el = element(sym)
            config = el.econf
            # Добавим информацию о валентных электронах
            valence = ""
            if hasattr(el, 'group_id'):
                valence = f"\nГруппа: {el.group_id} | Валентные электроны: {el.group_id if el.group_id <= 2 else el.group_id - 10 if el.group_id <= 12 else el.group_id - 10}"

            self.res.configure(text=f"Элемент: {el.name} ({el.symbol})\n"
                                    f"Атомный номер: {el.atomic_number}\n"
                                    f"Электронная конфигурация:\n{config}{valence}")
            HistoryManager.add("Электронная конфигурация", f"{el.symbol}: {config}")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}\nПроверьте правильность символа элемента")


class BondingTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Тип химической связи",
                      desc="Анализ связи по разнице электроотрицательностей (шкала Полинга)")

        input_frame = ctk.CTkFrame(c, fg_color="transparent")
        input_frame.pack(pady=15)

        ctk.CTkLabel(input_frame, text="Элемент 1:").grid(row=0, column=0, padx=5, pady=5)
        self.e1 = ctk.CTkEntry(input_frame, width=100)
        self.e1.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(input_frame, text="Элемент 2:").grid(row=1, column=0, padx=5, pady=5)
        self.e2 = ctk.CTkEntry(input_frame, width=100)
        self.e2.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkButton(c, text="Анализировать связь", command=self.calc, width=180).pack(pady=10)

        self.res = ctk.CTkLabel(c, text="Введите два элемента для анализа",
                                font=("Arial", 13), wraplength=450, justify="center")
        self.res.pack(pady=15, padx=20)

    def receive_data(self, k, v):
        if k == "el":
            if not self.e1.get():
                self.e1.delete(0, "end")
                self.e1.insert(0, v)
            elif not self.e2.get():
                self.e2.delete(0, "end")
                self.e2.insert(0, v)

    def calc(self):
        if not HAS_MENDELEEV:
            self.res.configure(text="Требуется библиотека mendeleev\nУстановите: pip install mendeleev",
                               text_color="red")
            return

        try:
            sym1 = self.e1.get().strip()
            sym2 = self.e2.get().strip()

            if not sym1 or not sym2:
                self.res.configure(text="Введите оба элемента!", text_color="orange")
                return

            el1 = element(sym1)
            el2 = element(sym2)

            en1 = el1.en_pauling
            en2 = el2.en_pauling

            if en1 is None or en2 is None:
                self.res.configure(text="Нет данных об электроотрицательности для одного из элементов",
                                   text_color="orange")
                return

            diff = abs(en1 - en2)

            if diff > 1.7:
                bond_type = "ИОННАЯ СВЯЗЬ"
                desc = "Полный переход электронов от одного атома к другому"
                color = "#e74c3c"
            elif diff > 0.4:
                bond_type = "КОВАЛЕНТНАЯ ПОЛЯРНАЯ СВЯЗЬ"
                desc = "Неравномерное распределение электронной плотности"
                color = "#f39c12"
            else:
                bond_type = "КОВАЛЕНТНАЯ НЕПОЛЯРНАЯ СВЯЗЬ"
                desc = "Равномерное распределение электронной плотности"
                color = "#2ecc71"

            result = f"{el1.name} ({el1.symbol}) ↔ {el2.name} ({el2.symbol})\n\n"
            result += f"ЭО({el1.symbol}) = {en1:.2f} | ЭО({el2.symbol}) = {en2:.2f}\n"
            result += f"Разница ΔЭО = {diff:.2f}\n\n"
            result += f"ТИП СВЯЗИ: {bond_type}\n{desc}"

            self.res.configure(text=result, text_color=color)
            HistoryManager.add("Анализ связи", f"{sym1}-{sym2}: Δ={diff:.2f} → {bond_type}")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class BalancerTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Балансировка химических реакций",
                      desc="Введите реагенты и продукты через '+' (напр. H2 + O2 / H2O)")

        ctk.CTkLabel(c, text="Реагенты:").pack(anchor="w", padx=20, pady=(10, 0))
        self.e1 = ctk.CTkEntry(c, placeholder_text="Например: Fe + O2", font=("Consolas", 13))
        self.e1.pack(pady=5, padx=20, fill="x")
        self.e1.bind("<Return>", lambda e: self.e2.focus_set())

        ctk.CTkLabel(c, text="Продукты:").pack(anchor="w", padx=20, pady=(10, 0))
        self.e2 = ctk.CTkEntry(c, placeholder_text="Например: Fe2O3", font=("Consolas", 13))
        self.e2.pack(pady=5, padx=20, fill="x")
        self.e2.bind("<Return>", lambda e: self.solve())

        btn_frame = ctk.CTkFrame(c, fg_color="transparent")
        btn_frame.pack(pady=15)
        ctk.CTkButton(btn_frame, text="Уравнять реакцию", command=self.solve, width=160).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Очистить", command=self.clear, width=100, fg_color="gray").pack(side="left",
                                                                                                       padx=5)

        self.res = ResultLabel(c, text="Результат появится здесь")
        self.res.pack(pady=15)

        # Примеры
        ex_frame = CardFrame(self, title="Примеры для тестирования")
        examples = [
            ("H2 + O2", "H2O"),
            ("Fe + O2", "Fe2O3"),
            ("CH4 + O2", "CO2 + H2O"),
            ("Al + HCl", "AlCl3 + H2")
        ]
        for reac, prod in examples:
            btn = ctk.CTkButton(ex_frame, text=f"{reac} → {prod}",
                                command=lambda r=reac, p=prod: self.set_example(r, p),
                                width=200, fg_color="#34495e")
            btn.pack(pady=3)

    def clear(self):
        self.e1.delete(0, "end")
        self.e2.delete(0, "end")
        self.res.configure(text="Результат появится здесь")

    def set_example(self, reac, prod):
        self.e1.delete(0, "end")
        self.e1.insert(0, reac)
        self.e2.delete(0, "end")
        self.e2.insert(0, prod)
        self.solve()

    def solve(self):
        if not HAS_CHEMPY:
            self.res.configure(text="Требуется ChemPy\npip install chempy", text_color="orange")
            return

        reac_str = self.e1.get().strip()
        prod_str = self.e2.get().strip()

        if not reac_str or not prod_str:
            self.res.configure(text="Введите реагенты и продукты!", text_color="orange")
            return

        result = EquationBalancer.balance(reac_str, prod_str)
        self.res.configure(text=result, text_color="#4facfe" if "Ошибка" not in result else "red")

        if "Ошибка" not in result and "Требуется" not in result and "→" in result:
            HistoryManager.add("Балансировка", result)


class GasLawsTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Газовые законы (PV = nRT)",
                      desc="Оставьте одно поле пустым для расчета. R = 0.08206 Л·атм/(моль·К)")

        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(pady=15, padx=20)

        # Поля ввода
        self.entries = {}
        labels = [("P", "Давление (атм)"), ("V", "Объем (Л)"), ("n", "Кол-во вещества (моль)"),
                  ("T", "Температура (K)")]

        for i, (key, label) in enumerate(labels):
            row = i // 2
            col = (i % 2) * 2

            ctk.CTkLabel(grid, text=label, font=("Arial", 11)).grid(row=row * 2, column=col, padx=5, pady=(5, 0),
                                                                    sticky="w")
            e = ctk.CTkEntry(grid, width=100, placeholder_text=key)
            e.grid(row=row * 2 + 1, column=col, padx=5, pady=(0, 10))
            self.entries[key] = e

        ctk.CTkButton(c, text="Рассчитать", command=self.solve, width=150).pack(pady=10)
        self.res = ResultLabel(c, text="Результат появится здесь")
        self.res.pack(pady=10)

    def solve(self):
        try:
            vals = {}
            for k, e in self.entries.items():
                txt = e.get().strip()
                vals[k] = float(txt) if txt else None

            none_count = sum(1 for v in vals.values() if v is None)
            if none_count != 1:
                self.res.configure(text="Оставьте ровно 1 поле пустым", text_color="orange")
                return

            R = 0.08206

            if vals['P'] is None:
                res = (vals['n'] * R * vals['T']) / vals['V']
                tgt = "P"
                unit = "атм"
            elif vals['V'] is None:
                res = (vals['n'] * R * vals['T']) / vals['P']
                tgt = "V"
                unit = "Л"
            elif vals['n'] is None:
                res = (vals['P'] * vals['V']) / (R * vals['T'])
                tgt = "n"
                unit = "моль"
            else:  # vals['T'] is None
                res = (vals['P'] * vals['V']) / (vals['n'] * R)
                tgt = "T"
                unit = "K"

            self.res.configure(text=f"{tgt} = {res:.4f} {unit}", text_color="#4facfe")
            HistoryManager.add("Газовые законы", f"{tgt} = {res:.4f} {unit}")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class PHTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Расчет pH", desc="Для сильных кислот/оснований")

        tabview = ctk.CTkTabview(c, height=250)
        tabview.pack(pady=10, padx=10, fill="x")

        # Вкладка кислоты
        tab_acid = tabview.add("Сильная кислота")
        ctk.CTkLabel(tab_acid, text="Концентрация кислоты (М):").pack(pady=(10, 5))
        self.acid_conc = ctk.CTkEntry(tab_acid, width=150)
        self.acid_conc.pack(pady=5)
        ctk.CTkButton(tab_acid, text="Рассчитать pH", command=self.calc_acid).pack(pady=10)
        self.acid_res = ctk.CTkLabel(tab_acid, text="", font=("Consolas", 16, "bold"))
        self.acid_res.pack(pady=5)

        # Вкладка основания
        tab_base = tabview.add("Сильное основание")
        ctk.CTkLabel(tab_base, text="Концентрация основания (М):").pack(pady=(10, 5))
        self.base_conc = ctk.CTkEntry(tab_base, width=150)
        self.base_conc.pack(pady=5)
        ctk.CTkButton(tab_base, text="Рассчитать pH", command=self.calc_base).pack(pady=10)
        self.base_res = ctk.CTkLabel(tab_base, text="", font=("Consolas", 16, "bold"))
        self.base_res.pack(pady=5)

    def calc_acid(self):
        try:
            c = float(self.acid_conc.get())
            if c <= 0:
                raise ValueError("Концентрация должна быть > 0")
            ph = -math.log10(c)
            self.acid_res.configure(text=f"pH = {ph:.2f}", text_color="#e74c3c" if ph < 7 else "#2ecc71")
            HistoryManager.add("pH кислоты", f"{ph:.2f}")
        except Exception as e:
            self.acid_res.configure(text=f"Ошибка: {str(e)}", text_color="red")

    def calc_base(self):
        try:
            c = float(self.base_conc.get())
            if c <= 0:
                raise ValueError("Концентрация должна быть > 0")
            pOH = -math.log10(c)
            ph = 14 - pOH
            self.base_res.configure(text=f"pH = {ph:.2f}", text_color="#2ecc71" if ph > 7 else "#e74c3c")
            HistoryManager.add("pH основания", f"{ph:.2f}")
        except Exception as e:
            self.base_res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class ConverterTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Конвертер единиц")

        # Выбор категории
        self.type_var = ctk.StringVar(value="Температура")
        self.types = ["Температура", "Давление", "Объем", "Энергия"]
        ctk.CTkOptionMenu(c, values=self.types, variable=self.type_var,
                          command=self.update_units, width=200).pack(pady=10)

        # Поле ввода значения
        self.e = ctk.CTkEntry(c, placeholder_text="Значение", width=200)
        self.e.pack(pady=10)

        # Выбор единиц
        unit_frame = ctk.CTkFrame(c, fg_color="transparent")
        unit_frame.pack(pady=5)

        self.u1 = ctk.CTkComboBox(unit_frame, values=["C", "K", "F"], width=100)
        self.u1.pack(side="left", padx=5)

        ctk.CTkLabel(unit_frame, text="→").pack(side="left", padx=5)

        self.u2 = ctk.CTkComboBox(unit_frame, values=["C", "K", "F"], width=100)
        self.u2.pack(side="left", padx=5)

        ctk.CTkButton(c, text="Перевести", command=self.conv, width=150).pack(pady=15)
        self.res = ResultLabel(c, text="Результат появится здесь")
        self.res.pack(pady=10)

        self.update_units("Температура")

    def update_units(self, choice):
        if choice == "Температура":
            vals = ["C", "K", "F"]
        else:
            vals = list(UnitConverter.UNITS[choice].keys())
        self.u1.configure(values=vals)
        self.u2.configure(values=vals)
        self.u1.set(vals[0])
        self.u2.set(vals[1] if len(vals) > 1 else vals[0])

    def conv(self):
        try:
            v = float(self.e.get())
            cat, u1, u2 = self.type_var.get(), self.u1.get(), self.u2.get()
            res = UnitConverter.convert(v, cat, u1, u2)
            if res is not None:
                self.res.configure(text=f"{res:.4f} {u2}", text_color="#4facfe")
                HistoryManager.add(f"Конвертер ({cat})", f"{v} {u1} → {res:.4f} {u2}")
            else:
                self.res.configure(text="Ошибка конвертации", text_color="red")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class GraphsTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        if not HAS_MATPLOTLIB:
            ctk.CTkLabel(self, text="Matplotlib не установлен.\nУстановите: pip install matplotlib",
                         font=("Arial", 14), text_color="red").pack(pady=50)
            return

        c = CardFrame(self, title="Графики в химии")

        # Выбор типа графика
        self.graph_type = ctk.StringVar(value="Титрование")
        types = ["Титрование", "Зависимость скорости от температуры", "Растворимость"]
        ctk.CTkOptionMenu(c, values=types, variable=self.graph_type,
                          command=self.plot, width=250).pack(pady=10)

        # Контейнер для графика
        self.graph_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.graph_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Первый график по умолчанию
        self.plot("Титрование")

    def plot(self, choice=None):
        # Очистка предыдущего графика
        for w in self.graph_frame.winfo_children():
            w.destroy()

        fig = plt.Figure(figsize=(5, 4), facecolor="#2b2b2b", dpi=100)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#2b2b2b")
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')

        choice = choice or self.graph_type.get()

        if choice == "Титрование":
            ax.set_title("Кривая титрования слабой кислоты", color='white')
            x = np.linspace(0, 30, 300)
            # Моделируем кривую титрования с точкой эквивалентности при 25 мл
            y = 3 + 4 / (1 + np.exp(-(x - 25) / 1.5))
            ax.plot(x, y, color='#3498db', linewidth=2)
            ax.axvline(x=25, color='red', linestyle='--', alpha=0.7, label='Точка эквивалентности')
            ax.set_xlabel("Объем титранта (мл)")
            ax.set_ylabel("pH")
            ax.legend(facecolor='#2b2b2b', edgecolor='white', labelcolor='white')
            ax.grid(True, alpha=0.3, color='gray')

        elif choice == "Зависимость скорости от температуры":
            ax.set_title("Зависимость скорости реакции от температуры", color='white')
            x = np.linspace(273, 373, 100)  # от 0°C до 100°C
            # По правилу Вант-Гоффа: скорость удваивается при повышении на 10К
            y = 1 * (2 ** ((x - 273) / 10))
            ax.plot(x, y, color='#e74c3c', linewidth=2)
            ax.set_xlabel("Температура (K)")
            ax.set_ylabel("Относительная скорость")
            ax.grid(True, alpha=0.3, color='gray')

        elif choice == "Растворимость":
            ax.set_title("Растворимость KNO₃ в воде", color='white')
            x = np.array([0, 20, 40, 60, 80, 100])
            y = np.array([13, 32, 64, 110, 169, 246])  # г/100г воды
            ax.plot(x, y, 'o-', color='#2ecc71', linewidth=2, markersize=6)
            ax.set_xlabel("Температура (°C)")
            ax.set_ylabel("Растворимость (г/100г воды)")
            ax.grid(True, alpha=0.3, color='gray')

        canvas = FigureCanvasTkAgg(fig, self.graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


class ThermoTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        card = CardFrame(self, title="Термодинамика (ΔG = ΔH - TΔS)")

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(pady=15, padx=20)

        ctk.CTkLabel(grid, text="ΔH (кДж/моль):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.dh = ctk.CTkEntry(grid, width=120)
        self.dh.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="ΔS (Дж/(моль·К)):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.ds = ctk.CTkEntry(grid, width=120)
        self.ds.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Температура (K):").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.t = ctk.CTkEntry(grid, width=120)
        self.t.grid(row=2, column=1, padx=5, pady=5)
        self.t.insert(0, "298")

        ctk.CTkButton(card, text="Рассчитать ΔG", command=self.calc, width=150).pack(pady=15)
        self.res = ResultLabel(card, text="ΔG = ? кДж/моль")
        self.res.pack(pady=10)

        info = ctk.CTkLabel(card, text="ΔG < 0: реакция спонтанна | ΔG > 0: реакция неспонтанна",
                            font=("Arial", 11), text_color="gray")
        info.pack(pady=(0, 10))

    def calc(self):
        try:
            dh = float(self.dh.get())  # кДж/моль
            ds = float(self.ds.get())  # Дж/(моль·К)
            t = float(self.t.get())

            # Переводим ΔS в кДж для согласования единиц
            dg = dh - t * (ds / 1000)

            color = "#2ecc71" if dg < 0 else "#e74c3c"
            spont = " (спонтанна)" if dg < 0 else " (неспонтанна)"

            self.res.configure(text=f"ΔG = {dg:.2f} кДж/моль{spont}", text_color=color)
            HistoryManager.add("Термодинамика", f"ΔG = {dg:.2f} кДж/моль")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


# MISSING CLASSES IMPLEMENTATION
class KineticsTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Химическая кинетика", desc="Уравнение Аррениуса")

        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(pady=15, padx=20)

        ctk.CTkLabel(grid, text="Константа k1:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.k1 = ctk.CTkEntry(grid, width=120)
        self.k1.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Температура T1 (K):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.t1 = ctk.CTkEntry(grid, width=120)
        self.t1.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Энергия активации Ea (Дж/моль):").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.ea = ctk.CTkEntry(grid, width=120)
        self.ea.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Температура T2 (K):").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.t2 = ctk.CTkEntry(grid, width=120)
        self.t2.grid(row=3, column=1, padx=5, pady=5)

        ctk.CTkButton(c, text="Рассчитать k2", command=self.calc, width=150).pack(pady=15)
        self.res = ResultLabel(c, text="k2 = ?")
        self.res.pack(pady=10)

    def calc(self):
        try:
            k1 = float(self.k1.get())
            t1 = float(self.t1.get())
            ea = float(self.ea.get())
            t2 = float(self.t2.get())

            R = 8.314
            k2 = k1 * math.exp((ea / R) * ((1 / t1) - (1 / t2)))
            self.res.configure(text=f"k2 = {k2:.4e}", text_color="#4facfe")
            HistoryManager.add("Кинетика", f"Calc k2 at {t2}K")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class NernstTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Уравнение Нернста", desc="E = E0 - (RT/nF) * ln(Q)")

        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(pady=15, padx=20)

        ctk.CTkLabel(grid, text="E0 (В):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.e0 = ctk.CTkEntry(grid, width=120)
        self.e0.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Температура (K):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.t = ctk.CTkEntry(grid, width=120)
        self.t.grid(row=1, column=1, padx=5, pady=5)
        self.t.insert(0, "298")

        ctk.CTkLabel(grid, text="Число электронов n:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.n = ctk.CTkEntry(grid, width=120)
        self.n.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="ln(Q):").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.lnq = ctk.CTkEntry(grid, width=120)
        self.lnq.grid(row=3, column=1, padx=5, pady=5)

        ctk.CTkButton(c, text="Рассчитать E", command=self.calc, width=150).pack(pady=15)
        self.res = ResultLabel(c, text="E = ? В")
        self.res.pack(pady=10)

    def calc(self):
        try:
            e0 = float(self.e0.get())
            t = float(self.t.get())
            n = float(self.n.get())
            lnq = float(self.lnq.get())

            R = 8.314
            F = 96485
            e = e0 - ((R * t) / (n * F)) * lnq

            self.res.configure(text=f"E = {e:.4f} В", text_color="#4facfe")
            HistoryManager.add("Нернст", f"E = {e:.4f} В")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class NuclearTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Ядерный распад", desc="Расчет остаточной массы")

        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(pady=15, padx=20)

        ctk.CTkLabel(grid, text="Начальная масса (г):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.m0 = ctk.CTkEntry(grid, width=120)
        self.m0.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Период полураспада (сек/год):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.hl = ctk.CTkEntry(grid, width=120)
        self.hl.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Прошедшее время:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.t = ctk.CTkEntry(grid, width=120)
        self.t.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkButton(c, text="Рассчитать массу", command=self.calc, width=150).pack(pady=15)
        self.res = ResultLabel(c, text="M = ? г")
        self.res.pack(pady=10)

    def calc(self):
        try:
            m0 = float(self.m0.get())
            hl = float(self.hl.get())
            t = float(self.t.get())

            if hl <= 0:
                raise ValueError("Период полураспада > 0")

            m = m0 * (0.5 ** (t / hl))
            self.res.configure(text=f"M = {m:.4f} г", text_color="#4facfe")
            HistoryManager.add("Ядерный распад", f"M = {m:.4f} г")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class SolubilityTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Произведение растворимости (Ksp)", desc="Простая соль типа AxBy")

        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(pady=15, padx=20)

        ctk.CTkLabel(grid, text="Ksp:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.ksp = ctk.CTkEntry(grid, width=120)
        self.ksp.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="Коэффициент x:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.cx = ctk.CTkEntry(grid, width=120)
        self.cx.grid(row=1, column=1, padx=5, pady=5)
        self.cx.insert(0, "1")

        ctk.CTkLabel(grid, text="Коэффициент y:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.cy = ctk.CTkEntry(grid, width=120)
        self.cy.grid(row=2, column=1, padx=5, pady=5)
        self.cy.insert(0, "1")

        ctk.CTkButton(c, text="Рассчитать S (моль/л)", command=self.calc, width=150).pack(pady=15)
        self.res = ResultLabel(c, text="S = ? М")
        self.res.pack(pady=10)

    def calc(self):
        try:
            ksp = float(self.ksp.get())
            x = float(self.cx.get())
            y = float(self.cy.get())

            denom = (x ** x) * (y ** y)
            s = (ksp / denom) ** (1 / (x + y))

            self.res.configure(text=f"S = {s:.4e} М", text_color="#4facfe")
            HistoryManager.add("Растворимость", f"S = {s:.4e} M")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


class BufferTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="Буферные растворы", desc="Уравнение Гендерсона-Хассельбаха")

        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(pady=15, padx=20)

        ctk.CTkLabel(grid, text="pKa:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.pka = ctk.CTkEntry(grid, width=120)
        self.pka.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(grid, text="[Соль] / [Кислота] (или log):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.ratio = ctk.CTkEntry(grid, width=120)
        self.ratio.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkButton(c, text="Рассчитать pH", command=self.calc, width=150).pack(pady=15)
        self.res = ResultLabel(c, text="pH = ?")
        self.res.pack(pady=10)

    def calc(self):
        try:
            pka = float(self.pka.get())
            ratio = float(self.ratio.get())

            if ratio <= 0:
                raise ValueError("Отношение должно быть > 0")

            ph = pka + math.log10(ratio)
            self.res.configure(text=f"pH = {ph:.2f}", text_color="#4facfe")
            HistoryManager.add("Буфер", f"pH = {ph:.2f}")
        except Exception as e:
            self.res.configure(text=f"Ошибка: {str(e)}", text_color="red")


# ===== NEW ADVANCED TABS =====
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

# ===== END NEW TABS =====

class AIAssistantTab(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        c = CardFrame(self, title="AI Помощник (Beta)")

        self.q = ctk.CTkEntry(c, placeholder_text="Задайте вопрос по химии...", font=("Arial", 14))
        self.q.pack(pady=10, padx=20, fill="x")
        self.q.bind("<Return>", lambda e: self.ask())

        ctk.CTkButton(c, text="Спросить", command=self.ask, width=150).pack(pady=5)

        self.ans = ctk.CTkTextbox(c, height=300, font=("Arial", 12), fg_color="gray15")
        self.ans.pack(pady=10, padx=20, fill="both", expand=True)
        self.ans.insert("0.0", "Ожидание вопроса...")
        self.ans.configure(state="disabled")

    def ask(self):
        query = self.q.get()
        if not query:
            return

        self.ans.configure(state="normal")
        self.ans.delete("0.0", "end")
        self.ans.insert("0.0", "Думаю...")
        self.ans.update()

        response = AIAssistantStub.ask(query)

        self.ans.delete("0.0", "end")
        self.ans.insert("0.0", response)
        self.ans.configure(state="disabled")
        HistoryManager.add("AI Assistant", query[:30] + "...")