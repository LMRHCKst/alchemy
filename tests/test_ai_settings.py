# -*- coding: utf-8 -*-
"""Тесты хранения настроек модели.

Главное, что проверяется: ключ живёт в профиле пользователя, а не в
репозитории; при пустом профиле он один раз подтягивается из настроек
чата; ничего не пишется молча и не теряется.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from alchemy.ai import settings_store
from alchemy.ai.client import AiError


class IsolatedProfile(unittest.TestCase):
    """Каждый тест работает в своей временной папке профиля."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.profile_root = Path(self._temp.name)
        self._old_appdata = os.environ.get("APPDATA")
        self._old_env = os.environ.pop("ALCHEMY_AI_CONFIG", None)
        os.environ["APPDATA"] = str(self.profile_root)

    def tearDown(self):
        if self._old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._old_appdata
        if self._old_env is not None:
            os.environ["ALCHEMY_AI_CONFIG"] = self._old_env
        self._temp.cleanup()


class TestStorage(IsolatedProfile):
    def test_path_is_in_profile(self):
        path = settings_store.user_config_path()
        self.assertTrue(str(path).startswith(str(self.profile_root)))
        self.assertEqual(path.name, "ai.json")

    def test_save_and_load(self):
        saved = settings_store.save({
            "api_base": "https://example.test/v1",
            "api_key": "secret-key-123456",
            "model": "test-model",
            "max_tokens": 500,
            "temperature": 0.3,
        })
        self.assertTrue(saved.exists())

        data = settings_store.load_saved()
        self.assertEqual(data["api_base"], "https://example.test/v1")
        self.assertEqual(data["api_key"], "secret-key-123456")
        self.assertEqual(data["model"], "test-model")
        self.assertEqual(data["max_tokens"], 500)

    def test_save_requires_fields(self):
        for broken in (
            {"api_base": "", "api_key": "k", "model": "m"},
            {"api_base": "https://x/v1", "api_key": "", "model": "m"},
            {"api_base": "https://x/v1", "api_key": "k", "model": ""},
        ):
            with self.assertRaises(AiError):
                settings_store.save(broken)

    def test_nothing_written_on_invalid(self):
        with self.assertRaises(AiError):
            settings_store.save({"api_base": "", "api_key": "", "model": ""})
        self.assertFalse(settings_store.user_config_path().exists())

    def test_clear_removes_file(self):
        settings_store.save({"api_base": "https://x/v1", "api_key": "k",
                             "model": "m"})
        settings_store.clear()
        self.assertFalse(settings_store.user_config_path().exists())
        self.assertIsNone(settings_store.load_saved())

    def test_mask_hides_middle(self):
        masked = settings_store.mask("abcdefghijklmnop")
        self.assertIn("…", masked)
        self.assertTrue(masked.startswith("abcd"))
        self.assertTrue(masked.endswith("mnop"))
        self.assertNotIn("efgh", masked)

    def test_mask_short_key(self):
        self.assertEqual(settings_store.mask("abc"), "***")


class TestResolution(IsolatedProfile):
    def test_profile_wins(self):
        settings_store.save({"api_base": "https://profile/v1",
                             "api_key": "from-profile", "model": "m1"})
        settings, origin = settings_store.resolve_with_origin()
        self.assertEqual(settings.api_key, "from-profile")
        self.assertIn("профиль", origin)

    def test_import_from_chat_once(self):
        """Пустой профиль: ключ берётся из чата и остаётся в профиле."""
        chat_file = self.profile_root / "chat.json"
        chat_file.write_text(json.dumps({
            "api_key": "chat-key",
            "api_base": "https://chat/v1",
            "model": "chat-model",
            "max_tokens": 700,
        }), encoding="utf-8")

        with mock.patch("alchemy.ai.client.find_config", return_value=chat_file):
            settings, origin = settings_store.ensure_ready()

        self.assertEqual(settings.api_key, "chat-key")
        self.assertIn("перенесён", origin)

        # второй раз — уже из профиля, чат не нужен
        self.assertTrue(settings_store.user_config_path().exists())
        again, origin2 = settings_store.resolve_with_origin()
        self.assertEqual(again.api_key, "chat-key")
        self.assertIn("профиль", origin2)

    def test_no_import_when_profile_has_key(self):
        settings_store.save({"api_base": "https://profile/v1",
                             "api_key": "mine", "model": "m"})
        chat_file = self.profile_root / "chat.json"
        chat_file.write_text(json.dumps({"api_key": "chat", "model": "x"}),
                             encoding="utf-8")
        with mock.patch("alchemy.ai.client.find_config", return_value=chat_file):
            settings, origin = settings_store.ensure_ready()
        self.assertEqual(settings.api_key, "mine")
        self.assertNotIn("перенесён", origin)

    def test_nothing_anywhere_gives_clear_error(self):
        with mock.patch("alchemy.ai.client.find_config",
                        side_effect=AiError("нет файла")):
            with self.assertRaises(AiError) as ctx:
                settings_store.ensure_ready()
        self.assertIn("Настройки модели", str(ctx.exception))

    def test_explicit_env_wins(self):
        explicit = self.profile_root / "explicit.json"
        explicit.write_text(json.dumps({
            "api_key": "env-key", "api_base": "https://env/v1",
            "model": "env-model",
        }), encoding="utf-8")
        os.environ["ALCHEMY_AI_CONFIG"] = str(explicit)
        settings, origin = settings_store.resolve_with_origin()
        self.assertEqual(settings.api_key, "env-key")
        self.assertIn("ALCHEMY_AI_CONFIG", origin)


class TestKeyStaysOutOfRepo(unittest.TestCase):
    """Ключ не должен оказаться рядом с кодом."""

    def test_profile_is_outside_project(self):
        project = Path(settings_store.__file__).resolve().parents[3]
        profile = settings_store.user_config_path().resolve()
        self.assertNotEqual(project, profile.parent)
        self.assertNotIn(str(project), str(profile),
                         "файл с ключом оказался внутри проекта")

    def test_repo_has_no_key_files(self):
        project = Path(settings_store.__file__).resolve().parents[3]
        suspicious = []
        for pattern in ("ai.json", "config.ai.json", "*.key", "secrets.json"):
            for path in project.rglob(pattern):
                if ".git" in path.parts:
                    continue
                suspicious.append(str(path.relative_to(project)))
        self.assertEqual(suspicious, [], f"в проекте лежат файлы с ключами: {suspicious}")


if __name__ == "__main__":
    unittest.main()
