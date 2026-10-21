# -*- coding: utf-8 -*-
"""Тесты связки «модель — движок».

Сеть не используется: клиент подменяется поддельным, который отдаёт
заранее заданные ответы. Проверяется главное правило — числа берутся
из движка, отказ движка доходит до пользователя, а не замазывается.
"""

from __future__ import annotations

import json
import unittest

from alchemy.ai.agent import SYSTEM_PROMPT, Agent, Answer
from alchemy.ai.client import AiError, Reply, Settings, load_settings
from alchemy.ai.tools import REGISTRY, TOOLS, call_tool


class FakeClient:
    """Клиент, который отвечает по сценарию."""

    def __init__(self, replies: list[Reply]):
        self.replies = list(replies)
        self.seen: list[list[dict]] = []
        self.tools_seen: list = []

    def complete(self, messages, tools=None, *, tool_choice="auto") -> Reply:
        self.seen.append(list(messages))
        self.tools_seen.append(tools)
        if not self.replies:
            return Reply(text="сценарий кончился")
        return self.replies.pop(0)


def tool_call(name: str, arguments: dict, call_id: str = "call_1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


class TestToolLayer(unittest.TestCase):
    """Инструменты вызывают движки и не врут."""

    def test_molar_mass_from_engine(self):
        result = call_tool("molar_mass", {"formula": "CuSO4*5H2O"})
        self.assertTrue(result.ok)
        self.assertIn("249.677", result.text)

    def test_water_of_crystallization(self):
        result = call_tool("water_of_crystallization", {"formula": "CuSO4*5H2O"})
        self.assertTrue(result.ok)
        # 90.075 / 249.677 = 36.08 %
        self.assertIn("36.0", result.text)

    def test_water_tool_refuses_non_hydrate(self):
        result = call_tool("water_of_crystallization", {"formula": "NaCl"})
        self.assertFalse(result.ok)
        self.assertIn("ОТКАЗ", result.text)

    def test_engine_refusal_is_passed_through(self):
        result = call_tool("molar_mass", {"formula": "Xx2O3"})
        self.assertFalse(result.ok)
        self.assertIn("ОТКАЗ", result.text)

    def test_unknown_tool(self):
        result = call_tool("nope", {})
        self.assertFalse(result.ok)
        self.assertIn("НЕТ ТАКОГО ИНСТРУМЕНТА", result.text)

    def test_bad_arguments(self):
        result = call_tool("molar_mass", "{не json}")
        self.assertFalse(result.ok)
        self.assertIn("НЕ РАЗОБРАТЬ", result.text)

    def test_missing_required_argument(self):
        result = call_tool("molar_mass", {})
        self.assertFalse(result.ok)

    def test_every_schema_has_handler(self):
        names = {tool["function"]["name"] for tool in TOOLS}
        self.assertEqual(names, set(REGISTRY))

    def test_schemas_are_json_serializable(self):
        blob = json.dumps(TOOLS, ensure_ascii=False)
        self.assertGreater(len(blob), 1000)

    def test_every_tool_has_description(self):
        for tool in TOOLS:
            self.assertTrue(tool["function"]["description"].strip(),
                            tool["function"]["name"])


class TestAgentLoop(unittest.TestCase):
    """Цикл: модель просит расчёт, движок считает, модель отвечает."""

    def test_numbers_come_from_engine(self):
        client = FakeClient([
            Reply(tool_calls=[tool_call("molar_mass", {"formula": "H2O"})],
                  finish="tool_calls"),
            Reply(text="Молярная масса воды 18.015 г/моль."),
        ])
        answer = Agent(client).ask("Молярная масса воды?")

        self.assertEqual(answer.text, "Молярная масса воды 18.015 г/моль.")
        self.assertEqual(len(answer.steps), 1)
        self.assertEqual(answer.steps[0].name, "molar_mass")
        self.assertIn("18.015", answer.steps[0].result)

    def test_tool_result_reaches_model(self):
        client = FakeClient([
            Reply(tool_calls=[tool_call("molar_mass", {"formula": "H2O"})]),
            Reply(text="готово"),
        ])
        Agent(client).ask("вопрос")

        # второй запрос обязан содержать сообщение с результатом инструмента
        second = client.seen[1]
        roles = [message["role"] for message in second]
        self.assertIn("tool", roles)
        tool_message = next(m for m in second if m["role"] == "tool")
        self.assertIn("18.015", tool_message["content"])
        self.assertEqual(tool_message["tool_call_id"], "call_1")

    def test_system_prompt_forbids_self_calculation(self):
        self.assertIn("не умеешь считать", SYSTEM_PROMPT.lower())
        self.assertIn("инструмент", SYSTEM_PROMPT.lower())

    def test_refusal_goes_to_model(self):
        client = FakeClient([
            Reply(tool_calls=[tool_call("molar_mass", {"formula": "Xx2O3"})]),
            Reply(text="Не могу: элемента Xx не существует."),
        ])
        answer = Agent(client).ask("Молярная масса Xx2O3?")

        self.assertFalse(answer.steps[0].ok)
        self.assertIn("ОТКАЗ", answer.steps[0].result)
        self.assertIn("не", answer.text.lower())

    def test_several_tools_in_one_turn(self):
        client = FakeClient([
            Reply(tool_calls=[
                tool_call("molar_mass", {"formula": "H2O"}, "c1"),
                tool_call("molar_mass", {"formula": "CO2"}, "c2"),
            ]),
            Reply(text="готово"),
        ])
        answer = Agent(client).ask("сравни")
        self.assertEqual(len(answer.steps), 2)
        self.assertEqual(answer.steps[0].arguments, {"formula": "H2O"})

    def test_no_tools_means_no_calculation(self):
        client = FakeClient([Reply(text="Этого я посчитать не могу.")])
        answer = Agent(client).ask("Сколько стоит натрий?")
        self.assertEqual(answer.steps, [])
        self.assertIn("без расчётов", answer.trace())

    def test_step_limit_stops_runaway(self):
        endless = [Reply(tool_calls=[tool_call("molar_mass", {"formula": "H2O"})])
                   for _ in range(20)]
        client = FakeClient(endless)
        answer = Agent(client, max_steps=3).ask("вопрос")
        self.assertEqual(len(answer.steps), 3)
        self.assertEqual(answer.stopped, "лимит шагов")

    def test_usage_is_summed(self):
        client = FakeClient([
            Reply(tool_calls=[tool_call("molar_mass", {"formula": "H2O"})],
                  usage={"prompt_tokens": 10, "total_cost": 0.5}),
            Reply(text="ответ", usage={"prompt_tokens": 5, "total_cost": 0.25}),
        ])
        answer = Agent(client).ask("вопрос")
        self.assertEqual(answer.usage["prompt_tokens"], 15)
        self.assertAlmostEqual(answer.usage["total_cost"], 0.75)

    def test_tools_are_passed_to_model(self):
        client = FakeClient([Reply(text="ok")])
        Agent(client).ask("вопрос")
        self.assertTrue(client.tools_seen[0])
        names = {t["function"]["name"] for t in client.tools_seen[0]}
        self.assertIn("molar_mass", names)

    def test_history_is_prepended(self):
        client = FakeClient([Reply(text="ok")])
        Agent(client).ask("второй вопрос", history=[
            {"role": "user", "content": "первый"},
            {"role": "assistant", "content": "ответ"},
        ])
        roles = [m["role"] for m in client.seen[0]]
        self.assertEqual(roles[0], "system")
        self.assertEqual(roles[1], "user")
        self.assertEqual(roles[-1], "user")


class TestSettings(unittest.TestCase):
    """Настройки: понятные ошибки вместо падений."""

    def test_missing_config_message(self):
        with self.assertRaises(AiError) as ctx:
            load_settings("D:/нет/такого/файла.json")
        self.assertIn("нет файла настроек", str(ctx.exception))

    def test_empty_key_is_reported(self, ):
        import tempfile
        from pathlib import Path

        path = Path(tempfile.gettempdir()) / "alchemy_ai_empty.json"
        path.write_text(json.dumps({"api_key": "", "model": "x"}), encoding="utf-8")
        try:
            with self.assertRaises(AiError) as ctx:
                load_settings(path)
            self.assertIn("api_key", str(ctx.exception))
        finally:
            path.unlink(missing_ok=True)

    def test_auto_model_falls_back(self):
        import tempfile
        from pathlib import Path

        path = Path(tempfile.gettempdir()) / "alchemy_ai_auto.json"
        path.write_text(json.dumps({
            "api_key": "k", "model": "auto",
            "model_fallbacks": ["claude-test"],
        }), encoding="utf-8")
        try:
            settings = load_settings(path)
            self.assertEqual(settings.model, "claude-test")
        finally:
            path.unlink(missing_ok=True)


class TestAnswerTrace(unittest.TestCase):
    """След расчётов читается человеком."""

    def test_trace_lists_calls(self):
        client = FakeClient([
            Reply(tool_calls=[tool_call("molar_mass", {"formula": "H2O"})]),
            Reply(text="готово"),
        ])
        answer = Agent(client).ask("вопрос")
        self.assertIn("molar_mass", answer.trace())
        self.assertIn("H2O", answer.trace())

    def test_trace_marks_refusal(self):
        client = FakeClient([
            Reply(tool_calls=[tool_call("molar_mass", {"formula": "Xx"})]),
            Reply(text="нет"),
        ])
        answer = Agent(client).ask("вопрос")
        self.assertIn("отказ", answer.trace())


if __name__ == "__main__":
    unittest.main()
