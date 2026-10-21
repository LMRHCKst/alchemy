# -*- coding: utf-8 -*-
"""Продвинутые настройки модели: работают, но по умолчанию закрыты."""

import os
import tempfile
import unittest

from alchemy.ai import settings_store
from alchemy.ai.client import Settings


class TestGenerationParams(unittest.TestCase):
    def test_basic_only_by_default(self):
        params = Settings(api_key="k").generation_params()
        self.assertEqual(set(params), {"max_tokens", "temperature"})

    def test_advanced_adds_fields(self):
        settings = Settings(api_key="k", advanced=True, top_p=0.9,
                            presence_penalty=0.5, frequency_penalty=0.2,
                            seed=42)
        params = settings.generation_params()
        self.assertEqual(params["top_p"], 0.9)
        self.assertEqual(params["presence_penalty"], 0.5)
        self.assertEqual(params["frequency_penalty"], 0.2)
        self.assertEqual(params["seed"], 42)

    def test_zero_penalties_are_omitted(self):
        """Нулевые штрафы не шлём: лишние поля в запросе ни к чему."""
        settings = Settings(api_key="k", advanced=True)
        params = settings.generation_params()
        self.assertNotIn("presence_penalty", params)
        self.assertNotIn("frequency_penalty", params)
        self.assertNotIn("seed", params)


class TestStorage(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._temp.name

    def tearDown(self):
        if self._old is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._old
        self._temp.cleanup()

    def test_round_trip(self):
        settings_store.save({
            "api_base": "https://x/v1", "api_key": "k", "model": "m",
            "advanced": True, "top_p": 0.85, "presence_penalty": 0.3,
            "frequency_penalty": 0.1, "seed": 5, "max_steps": 3,
            "system_prompt": "считать только через движки",
        })
        saved = settings_store.load_saved()
        self.assertTrue(saved["advanced"])
        self.assertEqual(saved["top_p"], 0.85)
        self.assertEqual(saved["seed"], 5)
        self.assertEqual(saved["max_steps"], 3)

        settings, _origin = settings_store.resolve_with_origin()
        self.assertTrue(settings.advanced)
        self.assertEqual(settings.seed, 5)
        self.assertEqual(settings.system_prompt,
                         "считать только через движки")

    def test_locked_by_default_in_profile(self):
        settings_store.save({"api_base": "https://x/v1", "api_key": "k",
                             "model": "m"})
        settings, _origin = settings_store.resolve_with_origin()
        self.assertFalse(settings.advanced)
        self.assertEqual(settings.top_p, 1.0)
        self.assertEqual(settings.max_steps, 6)


class TestAgentUsesPrompt(unittest.TestCase):
    def test_default_prompt(self):
        from alchemy.ai.agent import SYSTEM_PROMPT, Agent

        class FakeClient:
            def complete(self, *args, **kwargs):
                from alchemy.ai.client import Reply
                return Reply(text="ок")

        agent = Agent(FakeClient())
        self.assertEqual(agent.system_prompt, SYSTEM_PROMPT)

    def test_custom_prompt(self):
        from alchemy.ai.agent import Agent

        class FakeClient:
            def complete(self, *args, **kwargs):
                from alchemy.ai.client import Reply
                return Reply(text="ок")

        agent = Agent(FakeClient(), system_prompt="мой промпт")
        self.assertEqual(agent.system_prompt, "мой промпт")


if __name__ == "__main__":
    unittest.main()
