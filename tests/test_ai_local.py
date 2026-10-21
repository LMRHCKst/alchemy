# -*- coding: utf-8 -*-
"""Тесты локального режима и предохранителей против выдуманных чисел.

Сеть и настоящая модель не нужны: проверяется логика — когда ответ
признаётся неподтверждённым, что считается выдумкой, а что округлением.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from alchemy.ai import local_server
from alchemy.ai.agent import (
    Agent, Answer, _foreign_numbers, _has_numbers, _needs_calculation,
    _normalise, _numbers_in, _rounding_of,
)
from alchemy.ai.client import Reply
from alchemy.ai.tools import call_tool


class FakeClient:
    """Отдаёт заранее заданные ответы, запоминает запросы."""

    def __init__(self, replies: list[Reply]):
        self.replies = list(replies)
        self.seen: list[list[dict]] = []
        self.choices: list[str] = []

    def complete(self, messages, tools=None, *, tool_choice="auto") -> Reply:
        self.seen.append(list(messages))
        self.choices.append(tool_choice)
        if not self.replies:
            return Reply(text="сценарий кончился")
        return self.replies.pop(0)


def call(name: str, args: dict, call_id: str = "c1") -> dict:
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}


class TestQuestionClassification(unittest.TestCase):
    def test_calculation_questions(self):
        for question in (
            "Какая молярная масса серной кислоты?",
            "Посчитай pH 0.1 M уксусной",
            "Уравняй KMnO4 + HCl",
            "Сколько тепла выделится?",
            "Чему равна концентрация раствора?",
        ):
            self.assertTrue(_needs_calculation(question), question)

    def test_small_talk(self):
        for question in ("Привет, как дела?", "Что такое химия?", "Спасибо"):
            self.assertFalse(_needs_calculation(question), question)

    def test_formula_detected(self):
        self.assertTrue(_needs_calculation("Что будет с CuSO4?"))
        self.assertFalse(_needs_calculation("Что такое кислота?"))

    def test_numbers_in_text(self):
        self.assertTrue(_has_numbers("масса 18.015 г/моль"))
        self.assertFalse(_has_numbers("это невозможно"))


class TestNumberGuard(unittest.TestCase):
    def test_normalise(self):
        self.assertEqual(_normalise("36,1"), _normalise("36.1"))
        self.assertEqual(_normalise("36.10"), _normalise("36.1"))

    def test_rounding_is_allowed(self):
        pool = _numbers_in("ЗНАЧЕНИЕ: 36.0766 %")
        self.assertTrue(_rounding_of("36.1", pool))
        self.assertTrue(_rounding_of("36.08", pool))

    def test_substitution_is_caught(self):
        pool = _numbers_in("ЗНАЧЕНИЕ: 98.072 г/моль")
        self.assertFalse(_rounding_of("98.079", pool))
        self.assertFalse(_rounding_of("99.5", pool))

    def test_foreign_numbers_ignore_words(self):
        step = type("S", (), {"result": "ЗНАЧЕНИЕ: 98.072 г/моль"})()
        self.assertEqual(_foreign_numbers("Молярная масса 98.072 г/моль", [step]), [])
        self.assertEqual(_foreign_numbers("Масса 98.079 г/моль", [step]), ["98.079"])
        # «5» и «2» — числа-слова, они не считаются подменой
        self.assertEqual(_foreign_numbers("в 2 случаях из 5", [step]), [])


class TestAgentGuards(unittest.TestCase):
    def test_self_computed_answer_is_flagged(self):
        """Модель ответила числом, не вызвав движок."""
        client = FakeClient([
            Reply(text="Молярная масса 98.079 г/моль."),
            Reply(text="Молярная масса 98.079 г/моль."),
        ])
        answer = Agent(client).ask("Какая молярная масса серной кислоты?")

        self.assertEqual(answer.steps, [])
        self.assertFalse(answer.verified)
        self.assertIn("без расчёта", answer.stopped)
        # второй запрос должен требовать вызова инструмента
        self.assertEqual(client.choices, ["required", "required"])

    def test_nudge_asks_to_call_tool(self):
        client = FakeClient([
            Reply(text="Не знаю."),
            Reply(tool_calls=[call("molar_mass", {"formula": "H2O"})]),
            Reply(text="Вода 18.015 г/моль."),
        ])
        answer = Agent(client).ask("Какая молярная масса воды?")
        self.assertTrue(answer.steps)
        self.assertTrue(answer.verified)
        # в подталкивании сказано про инструмент
        nudge = client.seen[1][-1]["content"]
        self.assertIn("инструмент", nudge.lower())

    def test_substituted_number_is_flagged(self):
        client = FakeClient([
            Reply(tool_calls=[call("molar_mass", {"formula": "H2SO4"})]),
            Reply(text="Молярная масса 98.079 г/моль."),
        ])
        answer = Agent(client).ask("Какая молярная масса серной кислоты?")
        self.assertTrue(answer.steps)
        self.assertFalse(answer.verified)
        self.assertIn("не из движка", answer.stopped)

    def test_empty_answer_falls_back_to_engine(self):
        """Модель вызвала движок и промолчала — отдаём результат движка."""
        client = FakeClient([
            Reply(tool_calls=[call("molar_mass", {"formula": "H2O"})]),
            Reply(text=""),
            Reply(text=""),
        ])
        answer = Agent(client).ask("Молярная масса воды?")
        self.assertTrue(answer.verified)
        self.assertIn("18.015", answer.text)
        self.assertIn("движок", answer.text)

    def test_plain_refusal_is_verified(self):
        """Отказ без чисел — нормальный ответ, а не брак."""
        client = FakeClient([Reply(text="Этого я посчитать не могу.")])
        answer = Agent(client).ask("Сколько стоит натрий?")
        self.assertTrue(answer.verified)
        self.assertEqual(answer.steps, [])


class TestLocalServer(unittest.TestCase):
    """Поиск движка и моделей без запуска сервера."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self._old_engine = os.environ.get("ALCHEMY_LLAMA_DIR")
        self._old_models = os.environ.get("ALCHEMY_MODELS_DIR")

    def tearDown(self):
        for name, value in (("ALCHEMY_LLAMA_DIR", self._old_engine),
                            ("ALCHEMY_MODELS_DIR", self._old_models)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self._temp.cleanup()

    def test_finds_engine(self):
        engine_dir = self.root / "llama" / "vulkan"
        engine_dir.mkdir(parents=True)
        (engine_dir / "llama-server.exe").write_bytes(b"")
        os.environ["ALCHEMY_LLAMA_DIR"] = str(self.root)
        self.assertEqual(local_server.find_engine(), engine_dir / "llama-server.exe")

    def test_finds_models(self):
        models_dir = self.root / "models"
        models_dir.mkdir()
        (models_dir / "A.gguf").write_bytes(b"")
        (models_dir / "B.gguf").write_bytes(b"")
        (models_dir / "mmproj-x.gguf").write_bytes(b"")  # служебный, не модель
        os.environ["ALCHEMY_MODELS_DIR"] = str(models_dir)
        names = [p.name for p in local_server.find_models()]
        self.assertIn("A.gguf", names)
        self.assertIn("B.gguf", names)
        self.assertNotIn("mmproj-x.gguf", names)

    def test_no_engine_gives_clear_error(self):
        os.environ["ALCHEMY_LLAMA_DIR"] = str(self.root / "нет")
        os.environ["ALCHEMY_MODELS_DIR"] = str(self.root / "нет")
        with mock.patch.object(local_server, "DEFAULT_ROOTS", []), \
                mock.patch.object(local_server, "health", return_value=False):
            ok, message = local_server.start(port=59999)
        self.assertFalse(ok)
        self.assertIn("llama-server", message)

    def test_status_shape(self):
        info = local_server.status()
        for key in ("engine", "models", "online", "base_url", "port"):
            self.assertIn(key, info)


if __name__ == "__main__":
    unittest.main()
