"""Цикл «модель выбирает инструмент — движок считает — модель объясняет».

Главное правило зашито в системный промпт и в устройство цикла: модель
не получает права считать. Любое число в её ответе должно быть взято
из результата инструмента. Если инструмент отказал, отказ идёт в ответ.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .client import ChatClient, Reply
from .tools import TOOLS, ToolResult, call_tool

#: сколько раз разрешаем модели просить инструменты, прежде чем оборвать
MAX_STEPS = 6

#: признаки того, что вопрос требует расчёта, а не беседы.
#: Слова вроде «кислота» или «щелочь» сюда не входят: вопрос «что такое
#: кислота» — это определение, а не задача.
CALC_WORDS = (
    "масса", "массу", "моль", "молярн", "ph", "концентрац",
    "раствор", "реакц", "уравн", "степень окисл", "тепл", "энтальп", "гиббс",
    "энтроп", "выход", "растворим", "жёсткост", "жесткост", "осмос",
    "газ", "объём", "объем", "давлен", "электролиз", "эдс", "потенциал",
    "распад", "период полупревращ", "гидрат", "кристаллогидрат", "доля",
    "класс", "изомер", "сгора", "равновес", "ле шателье", "нернст",
)

#: формула в тексте: латинская буква + цифры, или вещество с зарядом
FORMULA_HINT = re.compile(
    r"\b[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)+|\b[A-Z][a-z]?\d*[+-]\b|\)\d")

#: число в ответе, похожее на посчитанное значение
NUMBER_HINT = re.compile(r"\d+[.,]\d+")


def _needs_calculation(question: str) -> bool:
    """Похоже ли, что без движка тут не обойтись."""
    text = (question or "").lower()
    if any(word in text for word in CALC_WORDS):
        return True
    return bool(FORMULA_HINT.search(question or ""))


def _has_numbers(text: str) -> bool:
    """Есть ли в ответе число, которое могло быть посчитано."""
    return bool(NUMBER_HINT.search(text or ""))


def _normalise(token: str) -> str:
    """Привести число к сравнимому виду: 98,079 и 98.079 — одно и то же."""
    text = token.replace(",", ".").strip(" .,")
    try:
        value = float(text)
    except ValueError:
        return text
    if value == int(value):
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _numbers_in(text: str) -> set[str]:
    """Все десятичные числа в тексте, нормализованные."""
    return {_normalise(m.group(0)) for m in NUMBER_HINT.finditer(text or "")}


def _foreign_numbers(answer: str, steps: list["Step"]) -> list[str]:
    """Числа из ответа, которых нет в результатах движка.

    Сравнение по подстроке: движок печатает «249.677», модель может
    написать «249,677» или «249.6770» — это одно и то же число.
    Округление числа движка тоже разрешено: 36.0766 → 36.1 не выдумка.
    А вот 98.079 при движковом 98.072 — уже подмена, и она ловится.
    """
    pool = " ".join(step.result for step in steps)
    pool_numbers = _numbers_in(pool)
    pool_text = pool.replace(",", ".")

    foreign = []
    for number in _numbers_in(answer):
        if number in pool_numbers:
            continue
        # короткие целые вроде «5» или «2» — это слова, а не расчёт
        if len(number) <= 2 and "." not in number:
            continue
        if number in pool_text:
            continue
        if _rounding_of(number, pool_numbers):
            continue
        foreign.append(number)
    return sorted(foreign)


def _rounding_of(number: str, pool: set[str]) -> bool:
    """Является ли число округлением одного из чисел движка."""
    try:
        value = float(number)
    except ValueError:
        return False
    digits = len(number.split(".")[1]) if "." in number else 0
    for candidate in pool:
        try:
            source = float(candidate)
        except ValueError:
            continue
        if round(source, digits) == value:
            return True
    return False

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

4. Не пересчитывай, не округляй и не выводи сам числа из результата.
   Переписывай только те числа, которые буквально есть в ответе инструмента,
   с той точностью, что дал движок. Единицы указывай всегда.
   Даже простая арифметика запрещена: если нужна доля, процент или
   производная величина — найди инструмент, который её считает. Число,
   которого нет в результате, считается выдуманным.

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
    #: True, если ответ опирается на расчёт движка или не содержит чисел
    verified: bool = True

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
        nudged = False

        for _ in range(self.max_steps):
            # если вопрос требует расчёта, а модель ещё ничего не вызвала —
            # на первом шаге разрешаем потребовать вызов
            force = bool(_needs_calculation(question)) and not steps
            reply: Reply = self.client.complete(
                messages, TOOLS, tool_choice="required" if force else "auto")
            model = reply.model or model

            if reply.usage:
                for key, value in reply.usage.items():
                    if isinstance(value, (int, float)):
                        usage_total[key] = usage_total.get(key, 0) + value

            if not reply.tool_calls:
                # модель ответила сама. Для расчётного вопроса это брак:
                # один раз просим вызвать инструмент, потом помечаем ответ.
                if _needs_calculation(question) and not steps and not nudged:
                    nudged = True
                    messages.append({"role": "assistant", "content": reply.text or ""})
                    messages.append({
                        "role": "user",
                        "content": "Это расчётный вопрос. Ты не вызывал ни одного "
                                   "инструмента, значит числа взяты не из движка. "
                                   "Вызови подходящий инструмент и ответь по его "
                                   "результату. Если подходящего нет — скажи, "
                                   "что посчитать не можешь.",
                    })
                    continue

                verified = bool(steps) or not _has_numbers(reply.text)
                if steps and reply.text:
                    # числа в ответе обязаны совпадать с числами из движка
                    foreign = _foreign_numbers(reply.text, steps)
                    if foreign:
                        verified = False
                        return Answer(
                            text=reply.text,
                            steps=steps,
                            usage=usage_total,
                            model=model,
                            verified=False,
                            stopped="число не из движка: " + ", ".join(foreign[:3]),
                        )

                if steps and not reply.text.strip():
                    # модель вызвала инструмент, но не сформулировала ответ.
                    # Не выдумываем за неё: показываем то, что посчитал движок.
                    if not nudged:
                        nudged = True
                        messages.append({
                            "role": "user",
                            "content": "Ты получил результат инструмента, но не "
                                       "написал ответ. Ответь одним-двумя "
                                       "предложениями, взяв числа из результата.",
                        })
                        continue
                    last = steps[-1].result
                    return Answer(
                        text="Модель не сформулировала ответ. Что посчитал движок:\n\n"
                             + last,
                        steps=steps,
                        usage=usage_total,
                        model=model,
                        verified=True,
                        stopped="ответ собран из результата движка",
                    )

                return Answer(
                    text=reply.text or "Модель вернула пустой ответ.",
                    steps=steps,
                    usage=usage_total,
                    model=model,
                    verified=verified,
                    stopped="" if verified else "ответ без расчёта",
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
