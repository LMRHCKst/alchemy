"""Цикл «модель выбирает инструмент — движок считает — модель объясняет».

Главное правило зашито в системный промпт и в устройство цикла: модель
не получает права считать. Любое число в её ответе должно быть взято
из результата инструмента. Если инструмент отказал, отказ идёт в ответ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .client import ChatClient, Reply
from .tools import TOOLS, ToolResult, call_tool

#: сколько раз разрешаем модели просить инструменты, прежде чем оборвать
MAX_STEPS = 6

SYSTEM_PROMPT = """Ты — Диси, инженер-расчётчик. Отвечаешь по-русски, коротко и по делу.

ПРАВИЛА, КОТОРЫЕ НЕЛЬЗЯ НАРУШАТЬ:

1. Ты не умеешь считать химию сам. Ни молярные массы, ни pH, ни тепловые
   эффекты, ни коэффициенты. Любое число в твоём ответе обязано прийти
   из результата вызванного инструмента. Если ты напишешь число «по памяти»,
   оно будет неверным, и это хуже, чем не ответить.

2. Если для вопроса нет подходящего инструмента — скажи прямо: «этого
   я посчитать не могу, вот почему». Не выдумывай и не оценивай на глаз.

3. Если инструмент вернул ОТКАЗ — передай причину своими словами и не
   пытайся обойти её другим инструментом или приблизительным расчётом.
   Отказ — это ответ, а не помеха.

4. Не пересчитывай и не округляй числа из результата. Переписывай их как
   есть, с той точностью, что дал движок. Единицы указывай всегда.
   Простая арифметика над уже полученными числами разрешена — сложить,
   разделить, взять долю. Но сама величина обязана прийти из инструмента.

5. Если результат содержит ПРЕДУПРЕЖДЕНИЯ или ДОПУЩЕНИЯ — обязательно
   упомяни их в ответе. Пользователь должен знать, где граница применимости.

6. Не вызывай инструменты без нужды. Одно и то же вещество в разной записи
   (CuSO4*5H2O и CuSO4·5H2O) — это одно вещество, повторный вызов не нужен.
   Если вопрос про долю части в веществе, ищи готовый инструмент, а не
   считай ту же формулу несколько раз.

Формат ответа: сначала ответ на вопрос, потом при необходимости пояснение
в одно-два предложения. Без вступлений вида «конечно, сейчас посчитаю»."""


@dataclass
class Step:
    """Один вызов инструмента в ходе ответа."""

    name: str
    arguments: dict
    result: str
    ok: bool

    def summary(self) -> str:
        args = ", ".join(f"{k}={v!r}" for k, v in self.arguments.items())
        mark = "" if self.ok else " (отказ)"
        return f"{self.name}({args}){mark}"


@dataclass
class Answer:
    """Что в итоге получил пользователь."""

    text: str
    steps: list[Step] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    model: str = ""
    stopped: str = ""

    def trace(self) -> str:
        """Короткая строка о том, какие расчёты выполнялись."""
        if not self.steps:
            return "без расчётов"
        return "; ".join(step.summary() for step in self.steps)


class Agent:
    """Диалог с моделью, у которой есть только наши движки."""

    def __init__(self, client: ChatClient, *, max_steps: int = MAX_STEPS,
                 on_tool: Callable[[str, dict, str], None] | None = None):
        self.client = client
        self.max_steps = max_steps
        self.on_tool = on_tool

    def _run_tool(self, call: dict) -> tuple[Step, dict]:
        """Выполнить вызов и подготовить сообщение для модели."""
        function = call.get("function") or {}
        name = str(function.get("name") or "")
        arguments = function.get("arguments") or "{}"

        result: ToolResult = call_tool(name, arguments)

        try:
            import json
            parsed = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
        except Exception:
            parsed = {"_raw": arguments}

        step = Step(name=name, arguments=parsed, result=result.text, ok=result.ok)
        if self.on_tool:
            self.on_tool(name, parsed, result.text)

        message = {
            "role": "tool",
            "tool_call_id": str(call.get("id") or ""),
            "name": name,
            "content": result.text,
        }
        return step, message

    def ask(self, question: str, *, history: list[dict] | None = None) -> Answer:
        """Задать вопрос и получить ответ, посчитанный движками."""
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": question})

        steps: list[Step] = []
        usage_total: dict[str, Any] = {}
        model = ""

        for _ in range(self.max_steps):
            reply: Reply = self.client.complete(messages, TOOLS)
            model = reply.model or model

            if reply.usage:
                for key, value in reply.usage.items():
                    if isinstance(value, (int, float)):
                        usage_total[key] = usage_total.get(key, 0) + value

            if not reply.tool_calls:
                return Answer(
                    text=reply.text or "Модель вернула пустой ответ.",
                    steps=steps,
                    usage=usage_total,
                    model=model,
                )

            # модель просит расчёты: фиксируем её сообщение и отвечаем результатами
            messages.append({
                "role": "assistant",
                "content": reply.text or "",
                "tool_calls": reply.tool_calls,
            })
            for call in reply.tool_calls:
                step, message = self._run_tool(call)
                steps.append(step)
                messages.append(message)

        return Answer(
            text="Модель не смогла закончить за отведённое число шагов. "
                 "Вот что удалось посчитать.",
            steps=steps,
            usage=usage_total,
            model=model,
            stopped="лимит шагов",
        )
