"""Общие компоненты интерфейса: поля ввода, карточки, панель результата.

Задача этих компонентов — снять с вкладок рутину и держать единый вид.
Каждая расчётная вкладка описывает только свои поля и вызов движка,
а отрисовку результата, предупреждений и хода расчёта берёт на себя
ResultView.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from ..core.results import Result

# --------------------------------------------------------------------------
# Цветовая схема
# --------------------------------------------------------------------------

COLOR_BG = "#1a1a1a"
COLOR_CARD = "#242424"
COLOR_CARD_ALT = "#2b2b2b"
COLOR_ACCENT = "#4facfe"
COLOR_ACCENT_DIM = "#2c6fa8"
COLOR_OK = "#2ecc71"
COLOR_WARN = "#f39c12"
COLOR_ERROR = "#e74c3c"
COLOR_TEXT = "#e8e8e8"
COLOR_TEXT_DIM = "#9a9a9a"
COLOR_BORDER = "#3a3a3a"

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_HEADING = ("Segoe UI", 14, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 13)
FONT_RESULT = ("Consolas", 22, "bold")


def setup_theme() -> None:
    """Настроить внешний вид приложения."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")


# --------------------------------------------------------------------------
# Карточка
# --------------------------------------------------------------------------


class Card(ctk.CTkFrame):
    """Карточка с заголовком и пояснением."""

    def __init__(self, master, title: str = "", desc: str = "", **kwargs):
        super().__init__(master, fg_color=COLOR_CARD, corner_radius=12, **kwargs)

        if title:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", padx=18, pady=(14, 4))
            ctk.CTkLabel(header, text=title, font=FONT_HEADING,
                         text_color=COLOR_TEXT, anchor="w").pack(fill="x")
            if desc:
                ctk.CTkLabel(header, text=desc, font=FONT_SMALL,
                             text_color=COLOR_TEXT_DIM, anchor="w",
                             justify="left", wraplength=760).pack(fill="x", pady=(2, 0))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=18, pady=(6, 14))


class CollapsibleCard(ctk.CTkFrame):
    """Карточка, которую можно свернуть — для справочной информации."""

    def __init__(self, master, title: str, desc: str = "", expanded: bool = False, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD, corner_radius=12, **kwargs)
        self._expanded = expanded

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(12, 4))

        self._toggle_btn = ctk.CTkButton(
            header, text=f"{'▼' if expanded else '▶'}  {title}",
            anchor="w", fg_color="transparent", hover_color=COLOR_CARD_ALT,
            font=FONT_HEADING, text_color=COLOR_TEXT, height=28,
            command=self.toggle,
        )
        self._toggle_btn.pack(fill="x")

        if desc:
            ctk.CTkLabel(header, text=desc, font=FONT_SMALL,
                         text_color=COLOR_TEXT_DIM, anchor="w",
                         justify="left", wraplength=760).pack(fill="x", padx=8)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        if expanded:
            self.body.pack(fill="both", expand=True, padx=18, pady=(4, 14))

    def toggle(self) -> None:
        self._expanded = not self._expanded
        text = self._toggle_btn.cget("text")
        stripped = text.split("  ", 1)[1] if "  " in text else text
        if self._expanded:
            self._toggle_btn.configure(text=f"▼  {stripped}")
            self.body.pack(fill="both", expand=True, padx=18, pady=(4, 14))
        else:
            self._toggle_btn.configure(text=f"▶  {stripped}")
            self.body.pack_forget()


# --------------------------------------------------------------------------
# Поля ввода
# --------------------------------------------------------------------------


class LabeledEntry(ctk.CTkFrame):
    """Поле ввода с подписью, единицей измерения и подсказкой."""

    def __init__(self, master, label: str, unit: str = "",
                 default: str = "", width: int = 140,
                 hint: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.unit = unit

        text = label + (f", {unit}" if unit else "")
        ctk.CTkLabel(self, text=text, font=FONT_BODY, text_color=COLOR_TEXT,
                     anchor="w").pack(side="left", padx=(0, 8))

        self.entry = ctk.CTkEntry(self, width=width, font=FONT_MONO)
        self.entry.pack(side="left")
        if default:
            self.entry.insert(0, default)

        if hint:
            ctk.CTkLabel(self, text=hint, font=FONT_SMALL,
                         text_color=COLOR_TEXT_DIM).pack(side="left", padx=(8, 0))

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value) -> None:
        self.entry.delete(0, "end")
        if value is not None:
            self.entry.insert(0, str(value))

    def clear(self) -> None:
        self.entry.delete(0, "end")

    def value(self, required: bool = True, name: str | None = None) -> float | None:
        """Прочитать число. Пустое поле даёт None, если значение необязательно."""
        from ..core.errors import InputError
        from ..core.units import UnitError, parse_quantity

        raw = self.get()
        if not raw:
            if required:
                raise InputError(f"Не заполнено поле «{name or self.entry.get()}»")
            return None
        try:
            value, _ = parse_quantity(raw)
        except UnitError:
            raise InputError(f"Не удалось прочитать число: «{raw}»")
        return value


class LabeledCombo(ctk.CTkFrame):
    """Выпадающий список с подписью.

    Ширина подписи по умолчанию совпадает с той, что использует помощник
    полей ввода, поэтому списки и обычные поля встают на одну вертикаль.
    Иначе в одной форме оказывалось два разных отступа и колонка выглядела
    рваной.
    """

    #: ширина колонки подписи, общая с LabeledEntry
    LABEL_WIDTH = 330

    def __init__(self, master, label: str, values: list[str],
                 default: str | None = None, width: int = 200,
                 label_width: int | None = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        if label:
            ctk.CTkLabel(self, text=label, font=FONT_BODY,
                         text_color=COLOR_TEXT,
                         width=self.LABEL_WIDTH if label_width is None
                         else label_width,
                         anchor="w").pack(side="left", padx=(0, 8))

        self.var = ctk.StringVar(value=default or (values[0] if values else ""))
        self.combo = ctk.CTkComboBox(self, values=values, variable=self.var,
                                     width=width, font=FONT_BODY)
        self.combo.pack(side="left")

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)


class KeyValueGrid(ctk.CTkFrame):
    """Таблица «поле — значение» для компактного ввода многих величин."""

    def __init__(self, master, fields: list[tuple[str, str, str]] | None = None,
                 columns: int = 2, **kwargs):
        """fields: список троек (ключ, подпись, значение по умолчанию)."""
        super().__init__(master, fg_color="transparent", **kwargs)
        self.entries: dict[str, ctk.CTkEntry] = {}
        self._row = 0
        self._col = 0
        self._columns = columns

        if fields:
            for key, label, default in fields:
                self.add_field(key, label, default)

    def add_field(self, key: str, label: str, default: str = "",
                  width: int = 120) -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=label, font=FONT_BODY,
                     text_color=COLOR_TEXT).grid(
            row=self._row, column=self._col * 2, padx=(10, 4), pady=4, sticky="e")
        entry = ctk.CTkEntry(self, width=width, font=FONT_MONO)
        entry.grid(row=self._row, column=self._col * 2 + 1, padx=(0, 16), pady=4, sticky="w")
        if default:
            entry.insert(0, default)
        self.entries[key] = entry

        self._col += 1
        if self._col >= self._columns:
            self._col = 0
            self._row += 1
        return entry

    def get(self, key: str) -> str:
        return self.entries[key].get().strip()

    def value(self, key: str, required: bool = True, label: str = "") -> float | None:
        from ..core.errors import InputError
        from ..core.units import UnitError, parse_quantity

        raw = self.get(key)
        if not raw:
            if required:
                raise InputError(f"Не заполнено поле «{label or key}»")
            return None
        try:
            value, _ = parse_quantity(raw)
        except UnitError:
            raise InputError(f"Не удалось прочитать число в поле «{label or key}»: «{raw}»")
        return value

    def set(self, key: str, value) -> None:
        self.entries[key].delete(0, "end")
        if value is not None:
            self.entries[key].insert(0, str(value))

    def clear(self) -> None:
        for entry in self.entries.values():
            entry.delete(0, "end")


# --------------------------------------------------------------------------
# Панель результата
# --------------------------------------------------------------------------


class ResultView(ctk.CTkFrame):
    """Отображение результата расчёта: значение, допущения, предупреждения.

    Отдельно показывает ход расчёта — чтобы результат можно было проверить
    руками, а не принимать на веру.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD_ALT, corner_radius=12, **kwargs)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 0))

        self.label = ctk.CTkLabel(header, text="", font=FONT_HEADING,
                                  text_color=COLOR_TEXT, anchor="w")
        self.label.pack(fill="x")

        self.value_label = ctk.CTkLabel(self, text="—", font=FONT_RESULT,
                                        text_color=COLOR_ACCENT, anchor="w")
        self.value_label.pack(fill="x", padx=18, pady=(6, 0))

        self.method_label = ctk.CTkLabel(self, text="", font=FONT_SMALL,
                                         text_color=COLOR_TEXT_DIM, anchor="w",
                                         justify="left", wraplength=760)
        self.method_label.pack(fill="x", padx=18, pady=(2, 0))

        # Плашка предупреждений создаётся, но не упаковывается: пустой
        # CTkFrame по умолчанию занимает 200 px по высоте и оставляет
        # в панели результатов широкую пустую полосу. Появляется она
        # только когда есть что показать.
        self.warn_frame = ctk.CTkFrame(self, fg_color="transparent", height=0)

        # Таблица — для табличных результатов
        self.table_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Детали — сворачиваемый блок
        self.details_btn = ctk.CTkButton(
            self, text="▶  Показать ход расчёта и допущения",
            anchor="w", fg_color="transparent", hover_color=COLOR_CARD,
            text_color=COLOR_ACCENT, font=FONT_SMALL, height=26,
            command=self._toggle_details,
        )

        self.details_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.details_text = ctk.CTkTextbox(self.details_frame, height=240,
                                           font=("Consolas", 11),
                                           fg_color=COLOR_CARD,
                                           text_color=COLOR_TEXT,
                                           wrap="word")
        self.details_text.pack(fill="both", expand=True, padx=6, pady=(0, 12))
        self._details_shown = False

        self.clear()

    # ---------------- показ ----------------

    def clear(self) -> None:
        self.label.configure(text="Результат появится здесь")
        self.value_label.configure(text="—", text_color=COLOR_TEXT_DIM)
        self.method_label.configure(text="")
        for widget in self.warn_frame.winfo_children():
            widget.destroy()
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.table_frame.pack_forget()
        self._sync_warnings()
        # До расчёта показывать нечего, поэтому кнопка хода расчёта скрыта:
        # иначе она висит под пустой панелью и выглядит как приглашение
        self.details_btn.pack_forget()
        self._set_details_text("")

    def _sync_warnings(self) -> None:
        """Показать плашку предупреждений, только если есть что показать."""
        if not self.warn_frame.winfo_children():
            self.warn_frame.pack_forget()
            return
        if self.details_btn.winfo_manager():
            self.warn_frame.pack(fill="x", padx=18, pady=(8, 0),
                                 before=self.details_btn)
        else:
            self.warn_frame.pack(fill="x", padx=18, pady=(8, 0))

    def _sync_details_button(self) -> None:
        """Кнопка хода расчёта нужна только когда есть что показывать."""
        if self._details_text_has_content():
            self.details_btn.pack(fill="x", padx=12, pady=(6, 0))
        else:
            self.details_btn.pack_forget()

    def _pack_table(self) -> None:
        """Поставить таблицу между предупреждениями и кнопкой хода расчёта."""
        if self.details_btn.winfo_manager():
            self.table_frame.pack(fill="x", padx=18, pady=(10, 0),
                                  before=self.details_btn)
        else:
            self.table_frame.pack(fill="x", padx=18, pady=(10, 0))

    def _details_text_has_content(self) -> bool:
        return bool(self.details_text.get("0.0", "end").strip())

    def show(self, result: Result) -> None:
        """Показать результат расчёта."""
        self.label.configure(text=result.label or "Результат")

        # Для табличных результатов крупная строка «таблица, строк: 17»
        # ничего не сообщает: данные показывает сама таблица ниже.
        tabular = (result.kind in ("table", "series")
                   and isinstance(result.value, list))
        if tabular:
            self.value_label.pack_forget()
        else:
            self.value_label.pack(fill="x", padx=18, pady=(6, 0),
                                  before=self.method_label)
            if result.value is None:
                self.value_label.configure(text="расчёт не выполнен",
                                           text_color=COLOR_ERROR)
            else:
                self.value_label.configure(
                    text=result.formatted(),
                    text_color=(COLOR_ERROR if result.has_warnings
                                else COLOR_ACCENT),
                )

        self.method_label.configure(text=result.method or "")

        # Предупреждения
        for widget in self.warn_frame.winfo_children():
            widget.destroy()
        for warning in result.warnings:
            row = ctk.CTkFrame(self.warn_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text="⚠", font=FONT_BODY, text_color=COLOR_WARN,
                         width=20).pack(side="left", anchor="n")
            ctk.CTkLabel(row, text=warning, font=FONT_SMALL,
                         text_color=COLOR_WARN, anchor="w", justify="left",
                         wraplength=700).pack(side="left", fill="x", expand=True)
        self._sync_warnings()

        # Табличный результат
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        if result.kind == "table" and isinstance(result.value, list):
            self._build_table(result)
        elif result.kind == "series" and isinstance(result.value, list):
            self._build_series_note(result)

        # Текст деталей
        self._set_details_text(result.summary())
        self._sync_details_button()

        if result.has_warnings:
            self._show_details()

    def show_error(self, message: str) -> None:
        """Показать сообщение об ошибке."""
        self.label.configure(text="Ошибка расчёта")
        self.value_label.configure(text="—", text_color=COLOR_ERROR)
        self.method_label.configure(text="")
        for widget in self.warn_frame.winfo_children():
            widget.destroy()
        row = ctk.CTkFrame(self.warn_frame, fg_color="transparent")
        row.pack(fill="x", pady=1)
        ctk.CTkLabel(row, text="✕", font=FONT_BODY, text_color=COLOR_ERROR,
                     width=20).pack(side="left", anchor="n")
        ctk.CTkLabel(row, text=message, font=FONT_BODY, text_color=COLOR_ERROR,
                     anchor="w", justify="left", wraplength=700).pack(
            side="left", fill="x", expand=True)
        self._sync_warnings()
        self.table_frame.pack_forget()
        self._set_details_text("")
        self._sync_details_button()

    # ---------------- внутреннее ----------------

    def _set_details_text(self, text: str) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("0.0", "end")
        if text:
            self.details_text.insert("0.0", text)
        self.details_text.configure(state="disabled")

    def _toggle_details(self) -> None:
        if self._details_shown:
            self._hide_details()
        else:
            self._show_details()

    def _show_details(self) -> None:
        self.details_frame.pack(fill="both", expand=True)
        self.details_btn.configure(text="▼  Скрыть ход расчёта и допущения")
        self._details_shown = True

    def _hide_details(self) -> None:
        self.details_frame.pack_forget()
        self.details_btn.configure(text="▶  Показать ход расчёта и допущения")
        self._details_shown = False

    def _build_table(self, result: Result) -> None:
        rows = result.value
        if not rows:
            return
        columns = result.meta.get("columns") or list(rows[0].keys())

        self._pack_table()

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Alchemy.Treeview",
                        background=COLOR_CARD,
                        foreground=COLOR_TEXT,
                        fieldbackground=COLOR_CARD,
                        borderwidth=0,
                        font=FONT_SMALL)
        style.configure("Alchemy.Treeview.Heading",
                        background=COLOR_BORDER,
                        foreground=COLOR_TEXT,
                        font=FONT_SMALL)
        style.map("Alchemy.Treeview",
                  background=[("selected", COLOR_ACCENT_DIM)])

        height = min(len(rows), 12)
        tree = ttk.Treeview(self.table_frame, columns=columns, show="headings",
                            height=height, style="Alchemy.Treeview")
        for col in columns:
            tree.heading(col, text=col)
            width = max(90, min(220, 12 * max(len(str(col)), 8)))
            tree.column(col, width=width, anchor="w")

        for row in rows:
            values = []
            for col in columns:
                cell = row.get(col, "")
                if isinstance(cell, float):
                    values.append(f"{cell:.6g}")
                else:
                    values.append(str(cell))
            tree.insert("", "end", values=values)

        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical",
                                  command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        if len(rows) > height:
            scrollbar.pack(side="right", fill="y")

        if len(rows) > 12:
            ctk.CTkLabel(self.table_frame,
                         text=f"Показаны первые 12 строк из {len(rows)}",
                         font=FONT_SMALL, text_color=COLOR_TEXT_DIM).pack(
                side="bottom", anchor="w")

    def _build_series_note(self, result: Result) -> None:
        self._pack_table()
        count = len(result.value)
        x_label = result.meta.get("x_label", "x")
        y_label = result.meta.get("y_label", "y")
        ctk.CTkLabel(
            self.table_frame,
            text=f"Получен набор из {count} точек: {x_label} — {y_label}.\n"
                 f"Постройте график на вкладке «Графики», передав эти данные.",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM, justify="left",
            anchor="w", wraplength=680,
        ).pack(fill="x")


# --------------------------------------------------------------------------
# Базовая вкладка
# --------------------------------------------------------------------------


class BaseTab(ctk.CTkFrame):
    """Базовый класс расчётной вкладки.

    Наследник описывает поля в методе build_inputs и реализует calculate.
    Всё остальное — прокрутка, кнопки, показ результата, запись в журнал —
    берёт на себя этот класс.
    """

    #: заголовок вкладки
    title = "Вкладка"
    #: краткое описание под заголовком
    description = ""
    #: подпись кнопки расчёта
    action_label = "Рассчитать"
    #: имя действия для журнала
    history_action = ""

    def __init__(self, master, controller=None):
        super().__init__(master, fg_color="transparent")
        self.controller = controller

        # Прокручиваемая область: на маленьких экранах содержимое не обрежется
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(0, 10))
        ctk.CTkLabel(header, text=self.title, font=FONT_TITLE,
                     text_color=COLOR_TEXT, anchor="w").pack(fill="x")
        if self.description:
            ctk.CTkLabel(header, text=self.description, font=FONT_SMALL,
                         text_color=COLOR_TEXT_DIM, anchor="w",
                         justify="left", wraplength=800).pack(fill="x", pady=(2, 0))

        self.inputs_card = Card(self.scroll, title="Исходные данные")
        self.inputs_card.pack(fill="x", padx=2, pady=(0, 10))

        self.build_inputs(self.inputs_card.body)

        buttons = ctk.CTkFrame(self.scroll, fg_color="transparent")
        buttons.pack(fill="x", padx=2, pady=(0, 10))

        ctk.CTkButton(buttons, text=self.action_label, width=180, height=36,
                      font=("Segoe UI", 13, "bold"),
                      command=self.run).pack(side="left")
        ctk.CTkButton(buttons, text="Очистить", width=110, height=36,
                      fg_color="transparent", border_width=1,
                      border_color=COLOR_BORDER, text_color=COLOR_TEXT_DIM,
                      command=self.reset).pack(side="left", padx=8)

        self.extra_area = ctk.CTkFrame(self.scroll, fg_color="transparent",
                                       height=0)

        self.build_extra(self.extra_area)

        # Пустой CTkFrame по умолчанию занимает 200 px и оставляет между
        # кнопками и результатом широкую пустую полосу. Поэтому место под
        # дополнительные поля показывается, только если они там есть.
        if self.extra_area.winfo_children():
            self.extra_area.pack(fill="x", padx=2)

        self.result_view = ResultView(self.scroll)
        self.result_view.pack(fill="both", expand=True, padx=2, pady=(10, 20))

        # Панель результата растягивается на свободную высоту окна, чтобы
        # под ней не оставалась пустая половина экрана. Для этого содержимое
        # прокручиваемой области должно занимать всю её высоту, а не только
        # высоту по содержимому.
        self._attach_viewport_fill()

        self.bind_enter()

        # Некоторые вкладки нуждаются в данных, которые появляются только
        # после создания панели результата
        self.on_ready()

    def _attach_viewport_fill(self) -> None:
        """Растянуть содержимое вкладки на всю высоту окна.

        По умолчанию прокручиваемая область подстраивается под содержимое,
        поэтому при короткой форме внизу остаётся пустое место. Обработчик
        делает внутренний фрейм не ниже области просмотра: содержимое
        прижимается к верху, а панель результата забирает остаток высоты.

        Используется внутренний механизм CustomTkinter, поэтому любые
        неожиданности глушатся: без растяжения вкладка просто выглядит
        как раньше.
        """
        canvas = getattr(self.scroll, "_parent_canvas", None)
        window_id = getattr(self.scroll, "_create_window_id", None)
        if canvas is None or window_id is None:
            return

        def fill(event) -> None:
            try:
                needed = self.scroll.winfo_reqheight()
                canvas.itemconfigure(window_id, height=max(needed, event.height))
            except Exception:
                pass

        try:
            canvas.bind("<Configure>", fill, add="+")
        except Exception:
            pass

    # ---------------- для наследников ----------------

    def on_ready(self) -> None:
        """Вызывается после полной сборки вкладки. Переопределяется при нужде."""

    def build_inputs(self, parent) -> None:
        """Создать поля ввода. Переопределяется наследником."""

    def build_extra(self, parent) -> None:
        """Создать дополнительные блоки под полями. Необязательно."""

    def calculate(self) -> Result:
        """Выполнить расчёт. Обязателен для наследника."""
        raise NotImplementedError

    def reset(self) -> None:
        """Очистить поля. Наследник может переопределить."""
        self.clear_widgets(self.inputs_card.body)
        self.result_view.clear()

    # ---------------- общее ----------------

    def clear_widgets(self, parent) -> None:
        """Очистить все поля ввода внутри контейнера."""
        for child in parent.winfo_children():
            if isinstance(child, (ctk.CTkEntry, tk.Entry)):
                child.delete(0, "end")
            elif isinstance(child, KeyValueGrid):
                child.clear()
            elif isinstance(child, LabeledEntry):
                child.clear()
            elif isinstance(child, LabeledCombo):
                pass
            else:
                self.clear_widgets(child)

    def run(self) -> None:
        """Выполнить расчёт и показать результат."""
        from ..core.errors import AlchemyError

        try:
            result = self.calculate()
        except AlchemyError as exc:
            self.result_view.show_error(str(exc))
            return
        except ZeroDivisionError:
            self.result_view.show_error("Деление на ноль: проверьте исходные данные")
            return
        except Exception as exc:   # неожиданная ошибка — не роняем приложение
            self.result_view.show_error(
                f"Непредвиденная ошибка ({type(exc).__name__}): {exc}"
            )
            return

        self.result_view.show(result)

        # Запись в журнал
        if self.history_action or self.title:
            self.log(result)

    def log(self, result: Result) -> None:
        """Записать расчёт в журнал операций."""
        if self.controller is None:
            return
        logger = getattr(self.controller, "log_operation", None)
        if logger is None:
            return
        try:
            logger(self.history_action or self.title, result)
        except Exception:
            pass   # журнал не должен ломать расчёт

    def bind_enter(self) -> None:
        """Расчёт по Enter в любом поле ввода."""
        def handler(event):
            self.run()
            return "break"

        self.bind_all_entry(self, handler)

    def bind_all_entry(self, widget, handler) -> None:
        for child in widget.winfo_children():
            if isinstance(child, (ctk.CTkEntry, tk.Entry)):
                child.bind("<Return>", handler)
            else:
                self.bind_all_entry(child, handler)

    # ---------------- вспомогательные конструкторы ----------------

    def info_block(self, parent, text: str, title: str = "") -> None:
        """Вставить блок пояснений, формул и подсказок."""
        card = CollapsibleCard(parent, title=title or "Как это считается")
        card.pack(fill="x", padx=2, pady=(10, 0))
        ctk.CTkLabel(card.body, text=text, font=FONT_SMALL,
                     text_color=COLOR_TEXT_DIM, justify="left",
                     anchor="w", wraplength=780).pack(fill="x")

    def row(self, parent, *widgets) -> ctk.CTkFrame:
        """Разместить виджеты в одну строку."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=3)
        for w in widgets:
            w.pack(side="left", padx=(0, 12))
        return frame


# --------------------------------------------------------------------------
# Вкладка со списком веществ и табличным вводом
# --------------------------------------------------------------------------


class EditableTable(ctk.CTkFrame):
    """Простая редактируемая таблица «вещество — значение».

    Нужна там, где число участников заранее неизвестно: смеси, наборы
    опытных точек, список реагентов.
    """

    def __init__(self, master, columns: list[str] | None = None,
                 add_label: str = "Добавить строку", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.columns = columns or ["Вещество", "Значение"]
        self._rows: list[list[ctk.CTkEntry]] = []

        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x")
        for col in self.columns:
            ctk.CTkLabel(self.header, text=col, font=FONT_SMALL,
                         text_color=COLOR_TEXT_DIM, width=150,
                         anchor="w").pack(side="left", padx=4)

        self.rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.rows_frame.pack(fill="x")

        ctk.CTkButton(self, text=f"+ {add_label}", width=160, height=28,
                      fg_color="transparent", border_width=1,
                      border_color=COLOR_BORDER, text_color=COLOR_ACCENT,
                      font=FONT_SMALL, command=self.add_row).pack(
            anchor="w", pady=(6, 0))

        self.add_row()

    def add_row(self, values: list[str] | None = None) -> None:
        row_frame = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        entries: list[ctk.CTkEntry] = []
        for i, _ in enumerate(self.columns):
            entry = ctk.CTkEntry(row_frame, width=150, font=FONT_MONO)
            entry.pack(side="left", padx=4)
            if values and i < len(values):
                entry.insert(0, str(values[i]))
            entries.append(entry)

        def remove():
            self._rows.remove(entries)
            row_frame.destroy()

        ctk.CTkButton(row_frame, text="✕", width=30, height=26,
                      fg_color="transparent", hover_color=COLOR_ERROR,
                      text_color=COLOR_TEXT_DIM, font=FONT_SMALL,
                      command=remove).pack(side="left", padx=4)

        self._rows.append(entries)

    def get_rows(self) -> list[list[str]]:
        """Все непустые строки."""
        result = []
        for entries in self._rows:
            values = [e.get().strip() for e in entries]
            if any(values):
                result.append(values)
        return result

    def clear(self) -> None:
        for entries in self._rows:
            for entry in entries:
                entry.delete(0, "end")

    def reset(self) -> None:
        for frame in self.rows_frame.winfo_children():
            frame.destroy()
        self._rows.clear()
        self.add_row()
