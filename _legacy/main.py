import sys
import subprocess
import importlib.util
import os
import tkinter as tk
from tkinter import messagebox


# БЛОК АВТО-УСТАНОВКИ ЗАВИСИМОСТЕЙ
def install_requirements():
    """
    Проверяет и устанавливает необходимые библиотеки перед запуском.
    Использует встроенный tkinter для уведомления, так как customtkinter может еще не быть.
    """
    required_libraries = {
        "customtkinter": "customtkinter",
        "numpy": "numpy",
        "matplotlib": "matplotlib",
        "chempy": "chempy",
        "mendeleev": "mendeleev"
    }

    missing = []
    for lib_import_name, pip_name in required_libraries.items():
        if importlib.util.find_spec(lib_import_name) is None:
            missing.append(pip_name)

    if missing:
        # Создаем временное окно, чтобы пользователь видел процесс
        root = tk.Tk()
        root.withdraw()  # Скрываем основное окно

        msg = f"Обнаружены отсутствующие библиотеки:\n{', '.join(missing)}\n\nНачинаю автоматическую установку.\nЭто может занять 1-2 минуты.\nПриложение запустится автоматически."
        messagebox.showinfo("Alchemy OS | Настройка", msg)

        root.destroy()

        # Попытка установки
        try:
            for lib in missing:
                print(f"Installing {lib}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

            # Сообщение об успехе
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Успех", "Все библиотеки установлены!\nЗапускаем Alchemy OS...")
            root.destroy()

        except Exception as e:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Ошибка", f"Не удалось установить библиотеки автоматически.\nОшибка: {e}")
            root.destroy()
            sys.exit(1)


# Запускаем проверку ДО импорта остальных модулей
install_requirements()

# ТЕПЕРЬ МОЖНО ИМПОРТИРОВАТЬ ПРИЛОЖЕНИЕ
import customtkinter as ctk
from alchemy_core import ContextManager, LibraryManager

# Импорт UI компонентов (Tabs)
from alchemy_ui import (
    HandbookTab, HistoryTab, MolarMassTab, PeriodicTableTab,
    BalancerTab, ConverterTab, SolutionRecipeTab, ConcentrationTab, DilutionTab,
    StoichiometryTab, GasLawsTab, PHTab, BufferTab, ElectronTab,
    BondingTab, ThermoTab, KineticsTab, NernstTab, NuclearTab,
    SolubilityTab, GraphsTab, AIAssistantTab,
    # --- НОВЫЕ РАСШИРЕННЫЕ ВКЛАДКИ ---
    FormulaAnalysisTab, AdvancedSolutionsTab, AdvancedAcidBaseTab,
    ColligativeTab, AdvancedGasTab, AdvancedThermoTab,
    AdvancedKineticsTab, AdvancedStoichiometryTab
)

# Настройки приложения
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")
APP_TITLE = "Alchemy OS v2.0 (Enhanced)"
COLOR_MAIN_BG = ("#1a1a1a", "#1a1a1a")


# Main Application Controller
class AlchemyOS(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Инициализация библиотечных данных
        LibraryManager.load()

        self.title(APP_TITLE)
        self.geometry("1300x900")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Sidebar
        self.sidebar = ctk.CTkScrollableFrame(self, width=260, corner_radius=0, fg_color="#111111")
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        logo = ctk.CTkLabel(self.sidebar, text="ALCHEMY OS", font=("Orbitron", 22, "bold"), text_color="#4facfe")
        logo.pack(pady=20, padx=20)

        # 2. Main Content Area
        self.main_area = ctk.CTkFrame(self, fg_color=COLOR_MAIN_BG, corner_radius=15)
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        self.tabs_map = {}
        self.current_frame = None

        # --- МЕНЮ ---
        self.add_menu_header("БАЗА И ИНСТРУМЕНТЫ")
        self.add_menu_btn("🔬 Молярная масса", MolarMassTab)
        self.add_menu_btn("🧬 Анализ формулы (НОВОЕ)", FormulaAnalysisTab)
        self.add_menu_btn("🧬 Таблица Менделеева", PeriodicTableTab)
        self.add_menu_btn("📚 Справочник", HandbookTab)
        self.add_menu_btn("📜 Журнал операций", HistoryTab)

        self.add_menu_header("РЕАКЦИИ И РАСТВОРЫ")
        self.add_menu_btn("⚖️ Балансировщик", BalancerTab)
        self.add_menu_btn("⚗️ Рецепт раствора", SolutionRecipeTab)
        self.add_menu_btn("💧 Разбавление", DilutionTab)
        self.add_menu_btn("🧪 Концентрация", ConcentrationTab)
        self.add_menu_btn("🧪 Растворы (РАСШИРЕННОЕ)", AdvancedSolutionsTab)
        self.add_menu_btn("📊 Стехиометрия", StoichiometryTab)
        self.add_menu_btn("📊 Стехиометрия (РАСШИРЕННАЯ)", AdvancedStoichiometryTab)

        self.add_menu_header("ФИЗИЧЕСКАЯ ХИМИЯ")
        self.add_menu_btn("🔥 Термодинамика", ThermoTab)
        self.add_menu_btn("🔥 Термодинамика (РАСШИРЕННАЯ)", AdvancedThermoTab)
        self.add_menu_btn("⏱ Кинетика", KineticsTab)
        self.add_menu_btn("⏱ Кинетика (РАСШИРЕННАЯ)", AdvancedKineticsTab)
        self.add_menu_btn("🎈 Газовые законы", GasLawsTab)
        self.add_menu_btn("🎈 Газовые законы (РАСШИРЕННЫЕ)", AdvancedGasTab)
        self.add_menu_btn("🔋 Уравнение Нернста", NernstTab)

        self.add_menu_header("АНАЛИТИКА И СТРУКТУРА")
        self.add_menu_btn("📉 Графики / Титрование", GraphsTab)
        self.add_menu_btn("⚡ Электронные уровни", ElectronTab)
        self.add_menu_btn("🔗 Тип химической связи", BondingTab)
        self.add_menu_btn("🧊 Растворимость", SolubilityTab)
        self.add_menu_btn("🧪 pH и Буферы", BufferTab)
        self.add_menu_btn("🧪 Кислоты-основания (РАСШИРЕННОЕ)", AdvancedAcidBaseTab)
        self.add_menu_btn("🧊 Коллигативные свойства (НОВОЕ)", ColligativeTab)
        self.add_menu_btn("☢️ Ядерный распад", NuclearTab)

        self.add_menu_header("ОБЩЕЕ")
        self.add_menu_btn("🔄 Конвертер единиц", ConverterTab)
        self.add_menu_btn("🤖 ИИ ПОМОЩНИК (Beta)", AIAssistantTab)

        # Статус-бар
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color="#111111")
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status_lbl = ctk.CTkLabel(self.status_bar, text="Система готова | v2.0 Enhanced", font=("Arial", 11), text_color="gray")
        self.status_lbl.pack(side="left", padx=20)

        ContextManager.register_listener(self.update_status)
        self.show_frame(MolarMassTab)

    def add_menu_header(self, text):
        ctk.CTkLabel(self.sidebar, text=text, font=("Arial", 11, "bold"), text_color="gray50", anchor="w").pack(
            fill="x", padx=20, pady=(15, 2))

    def add_menu_btn(self, text, cls):
        btn = ctk.CTkButton(self.sidebar, text=text, anchor="w", fg_color="transparent",
                            hover_color="#2c3e50", height=32, command=lambda: self.show_frame(cls))
        btn.pack(fill="x", padx=10, pady=1)
        self.tabs_map[cls] = None

    def show_frame(self, cls):
        if self.current_frame:
            self.current_frame.pack_forget()

        if self.tabs_map[cls] is None:
            self.tabs_map[cls] = cls(self.main_area, self)

        self.current_frame = self.tabs_map[cls]

        if hasattr(self.current_frame, 'refresh'):
            self.current_frame.refresh()

        self.current_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def transfer(self, target_cls, key, value):
        if self.tabs_map[target_cls] is None:
            self.tabs_map[target_cls] = target_cls(self.main_area, self)

        self.show_frame(target_cls)

        if hasattr(self.tabs_map[target_cls], 'receive_data'):
            self.tabs_map[target_cls].receive_data(key, value)

    def update_status(self, val, desc):
        self.status_lbl.configure(text=f"Результат: {val} | {desc}")


if __name__ == "__main__":
    app = AlchemyOS()
    app.mainloop()
