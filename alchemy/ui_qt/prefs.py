# -*- coding: utf-8 -*-
"""Интерфейсные настройки: тема, и в будущем что угодно ещё.

Лежат в профиле пользователя, рядом с настройками модели.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FILE_NAME = "ui.json"
APP_DIR = "Alchemy"


def config_path() -> Path:
    """Где лежат настройки интерфейса."""
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_DIR / FILE_NAME
    return Path.home() / ".config" / "alchemy" / FILE_NAME


def load() -> dict:
    """Прочитать настройки, если файла нет — пустой словарь."""
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save(values: dict) -> Path:
    """Записать настройки интерфейса."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def is_light() -> bool:
    """Включена ли светлая тема."""
    return bool(load().get("light"))


def set_light(light: bool) -> Path:
    """Запомнить выбранную тему."""
    values = load()
    values["light"] = bool(light)
    return save(values)
