# -*- coding: utf-8 -*-
"""Тесты истории диалогов: сохранение, список, чтение, удаление."""

import os
import tempfile
import unittest
from pathlib import Path

from alchemy.ai import history


class TestHistory(unittest.TestCase):
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

    def _messages(self):
        return [
            {"role": "user", "content": "Какая молярная масса воды?"},
            {"role": "assistant", "content": "18.015 г/моль"},
        ]

    def test_save_and_list(self):
        path = history.save(self._messages(), model="test-model")
        self.assertTrue(path.exists())
        items = history.list_chats()
        self.assertEqual(len(items), 1)
        self.assertIn("молярная масса", items[0]["title"])
        self.assertEqual(items[0]["turns"], 1)
        self.assertEqual(items[0]["model"], "test-model")

    def test_load_round_trip(self):
        path = history.save(self._messages())
        data = history.load(path.stem)
        self.assertIsNotNone(data)
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["role"], "user")

    def test_update_existing(self):
        path = history.save(self._messages())
        messages = self._messages() + [
            {"role": "user", "content": "А серной?"},
            {"role": "assistant", "content": "98.072 г/моль"},
        ]
        history.save(messages, chat_id=path.stem)
        self.assertEqual(len(history.list_chats()), 1)
        self.assertEqual(history.list_chats()[0]["turns"], 2)

    def test_delete(self):
        path = history.save(self._messages())
        self.assertTrue(history.delete(path.stem))
        self.assertEqual(history.list_chats(), [])
        self.assertFalse(history.delete(path.stem))

    def test_history_is_outside_project(self):
        folder = history.chats_dir().resolve()
        project = Path(history.__file__).resolve().parents[2]
        self.assertNotIn(str(project), str(folder))

    def test_title_from_first_question(self):
        title = history.title_from(self._messages())
        self.assertEqual(title, "Какая молярная масса воды?")

    def test_broken_file_is_skipped(self):
        folder = history.chats_dir()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "broken.json").write_text("{не json", encoding="utf-8")
        self.assertEqual(history.list_chats(), [])


if __name__ == "__main__":
    unittest.main()
