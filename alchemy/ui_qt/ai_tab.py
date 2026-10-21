"""Вкладка «ИИ-расчётчик»: модель выбирает расчёт, движок считает.

Отличие от остальных вкладок: здесь нет полей под каждый параметр.
Пользователь пишет вопрос словами, модель решает, какие инструменты
вызвать, а числа возвращает `alchemy.engines`. Под ответом всегда видно,
что именно считалось — чтобы можно было проверить.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QTextBrowser, QVBoxLayout, QWidget,
)

from ..ai.agent import Agent, Answer
from ..ai.client import AiError, ChatClient, load_settings
from ..ai.tools import REGISTRY
from ..ui.components import Card
from ..ui.widgets import CTkLabel

EXAMPLE = ("Например: «Какая молярная масса медного купороса?» "
           "или «Уравняй KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O»")


class _AskWorker(QThread):
    """Запрос к модели в отдельном потоке, чтобы окно не замирало."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, agent: Agent, question: str, history: list[dict]):
        super().__init__()
        self._agent = agent
        self._question = question
        self._history = history

    def run(self) -> None:  # pragma: no cover - требует сети
        try:
            answer = self._agent.ask(self._question, history=self._history)
        except AiError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(answer)


class AiTab(QWidget):
    """Вопрос словами — ответ из движков, с показом всех расчётов."""

    title = "ИИ-расчётчик"
    description = ("Задайте вопрос словами. Модель не считает сама: она "
                   "выбирает нужный расчёт, а числа берутся из движков "
                   "программы. Под ответом видно, что именно считалось.")

    def __init__(self, master=None, controller=None, **kwargs):
        super().__init__(master)
        self.controller = controller
        self._agent: Agent | None = None
        self._worker: _AskWorker | None = None
        self._history: list[dict] = []
        self._answer: Answer | None = None
        self._setup_error = ""

        self._build()

    # ---------------- построение окна ----------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        content.setObjectName("Page")
        column = QVBoxLayout(content)
        column.setContentsMargins(20, 16, 20, 16)
        column.setSpacing(10)
        scroll.setWidget(content)

        heading = QLabel(self.title)
        heading.setObjectName("PageTitle")
        column.addWidget(heading)

        description = QLabel(self.description)
        description.setObjectName("PageDesc")
        description.setWordWrap(True)
        column.addWidget(description)

        # --- проверка доступа к модели ---
        try:
            settings = load_settings()
            self._agent = Agent(ChatClient(settings))
            self._model_line = settings.source
        except AiError as exc:
            self._setup_error = str(exc)
            self._model_line = ""

        if self._setup_error:
            self._build_unavailable(column)
        else:
            self._build_question(column)
            self._build_answer(column)
            self._build_trace(column)
            self._status = QLabel(f"Модель: {self._model_line}")
            self._status.setObjectName("PageDesc")
            column.addWidget(self._status)

        column.addStretch(1)

    def _build_unavailable(self, column: QVBoxLayout) -> None:
        card = Card(title="Модель недоступна")
        label = CTkLabel(
            card.body,
            text="Вкладка работает через облачную модель, но ключ не найден.\n\n"
                 f"Причина: {self._setup_error}\n\n"
                 "Ключ берётся из настроек чата Диси (disi-chat/config.json) "
                 "или из файла, указанного в переменной окружения "
                 "ALCHEMY_AI_CONFIG. Без ключа остальные вкладки работают "
                 "как обычно.",
            font=("Segoe UI", 10), text_color="#9a9a9a", anchor="w")
        label.pack(fill="x")
        column.addWidget(card)

    def _build_question(self, column: QVBoxLayout) -> None:
        card = Card(title="Вопрос",
                    desc="Пишите как человеку. Модель сама поймёт, что считать.")
        self.question = QPlainTextEdit()
        self.question.setPlaceholderText(EXAMPLE)
        self.question.setFixedHeight(84)
        self.question.setTabChangesFocus(True)
        card.body.layout().addWidget(self.question)
        column.addWidget(card)

        row = QWidget()
        buttons = QHBoxLayout(row)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)

        self.ask_button = QPushButton("Спросить")
        self.ask_button.setObjectName("Primary")
        self.ask_button.setFixedWidth(190)
        self.ask_button.setMinimumHeight(34)
        self.ask_button.clicked.connect(self.ask)
        buttons.addWidget(self.ask_button)

        self.clear_button = QPushButton("Очистить")
        self.clear_button.setFixedWidth(110)
        self.clear_button.setMinimumHeight(34)
        self.clear_button.clicked.connect(self.reset)
        buttons.addWidget(self.clear_button)

        self.show_trace = QPushButton("Расчёты: вкл")
        self.show_trace.setCheckable(True)
        self.show_trace.setChecked(True)
        self.show_trace.setFixedWidth(140)
        self.show_trace.setMinimumHeight(34)
        self.show_trace.toggled.connect(self._trace_visibility)
        buttons.addWidget(self.show_trace)

        buttons.addStretch(1)
        column.addWidget(row)

    def _build_answer(self, column: QVBoxLayout) -> None:
        card = Card(title="Ответ")
        self.answer_view = QTextBrowser()
        self.answer_view.setOpenExternalLinks(True)
        self.answer_view.setMinimumHeight(150)
        self.answer_view.setPlaceholderText("Здесь появится ответ")
        card.body.layout().addWidget(self.answer_view)
        column.addWidget(card)

    def _build_trace(self, column: QVBoxLayout) -> None:
        self.trace_card = Card(
            title="Что считалось",
            desc="Вызовы инструментов и ответы движков — для проверки.")
        self.trace_view = QTextBrowser()
        self.trace_view.setMinimumHeight(140)
        self.trace_card.body.layout().addWidget(self.trace_view)
        column.addWidget(self.trace_card)

    # ---------------- работа ----------------

    def run(self) -> None:
        """Действие по умолчанию: тот же вопрос, что и кнопкой.

        Нужен, потому что остальные вкладки вызываются через run(),
        и проверки интерфейса ожидают этот метод у каждой.
        """
        self.ask()

    def _trace_visibility(self, visible: bool) -> None:
        self.trace_card.setVisible(visible)
        self.show_trace.setText("Расчёты: вкл" if visible else "Расчёты: выкл")

    def reset(self) -> None:
        self.question.clear()
        self.answer_view.clear()
        self.trace_view.clear()
        self._history = []
        self._answer = None
        if self._model_line:
            self._status.setText(f"Модель: {self._model_line}")

    def ask(self) -> None:
        """Отправить вопрос модели. Считает движок, не модель."""
        if self._agent is None:
            return
        question = self.question.toPlainText().strip()
        if not question:
            self.answer_view.setPlainText("Введите вопрос.")
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self.ask_button.setEnabled(False)
        self.ask_button.setText("Считаю…")
        self.answer_view.setPlainText("Запрос к модели…")
        self.trace_view.clear()
        self._status.setText(f"Модель: {self._model_line} · запрос отправлен")

        self._worker = _AskWorker(self._agent, question, list(self._history))
        self._worker.done.connect(self._on_answer)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

    def _on_answer(self, answer: Answer) -> None:
        self._answer = answer
        self.ask_button.setEnabled(True)
        self.ask_button.setText("Спросить")

        self.answer_view.setMarkdown(answer.text or "_Пустой ответ_")

        lines: list[str] = []
        if not answer.steps:
            lines.append("Движок не вызывался. Значит, в ответе нет расчётов — "
                         "модель либо отказалась, либо вопрос не про расчёт.")
        else:
            for index, step in enumerate(answer.steps, 1):
                lines.append(f"{index}. {step.summary()}")
                for line in step.result.splitlines():
                    lines.append(f"    {line}")
                lines.append("")
        self.trace_view.setPlainText("\n".join(lines).strip())

        cost = answer.usage.get("total_cost") if answer.usage else None
        tail = f" · {cost:.4f} за запрос" if isinstance(cost, (int, float)) and cost else ""
        suffix = f" · остановлено: {answer.stopped}" if answer.stopped else ""
        self._status.setText(f"Модель: {self._model_line}{tail}{suffix}")

        question = self.question.toPlainText().strip()
        self._history.append({"role": "user", "content": question})
        self._history.append({"role": "assistant", "content": answer.text})
        self._history = self._history[-8:]

    def _on_error(self, message: str) -> None:
        self.ask_button.setEnabled(True)
        self.ask_button.setText("Спросить")
        self.answer_view.setPlainText(f"Модель недоступна: {message}")
        self._status.setText(f"Модель: {self._model_line} · ошибка")

    def latex_source(self) -> str:
        """Экспорт в LaTeX для меню: отдаём ответ как текст."""
        return self._answer.text if self._answer else ""

    @property
    def tool_count(self) -> int:
        return len(REGISTRY)
