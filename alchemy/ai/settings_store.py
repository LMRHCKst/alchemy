"""Хранение настроек модели: адрес, ключ, модель.

Ключ никогда не попадает в репозиторий: файл лежит в пользовательской
папке приложения, а не рядом с кодом.

Порядок поиска:

1. `ALCHEMY_AI_CONFIG` — явный путь, если задан.
2. Файл настроек пользователя (`%APPDATA%\\Alchemy\\ai.json`).
3. Внешний конфиг с ключом — чтобы при первом запуске ничего
   не вводить, если ключ уже где-то сохранён.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .client import AiError, Settings

#: имя файла настроек
FILE_NAME = "ai.json"

#: папка приложения в профиле пользователя
APP_DIR = "Alchemy"


def user_config_path() -> Path:
    """Где лежат настройки пользователя."""
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_DIR / FILE_NAME
    return Path.home() / ".config" / "alchemy" / FILE_NAME


#: готовые адреса: подставляются в форму, чтобы не искать вручную
PRESETS: list[tuple[str, str]] = [
    ("GPTunnel", "https://gptunnel.ru/v1"),
    ("OpenAI", "https://api.openai.com/v1"),
    ("OpenRouter", "https://openrouter.ai/api/v1"),
    ("DeepSeek", "https://api.deepseek.com/v1"),
    ("Mistral", "https://api.mistral.ai/v1"),
    ("Локальная (llama.cpp)", "http://127.0.0.1:1235/v1"),
    ("Локальная (Ollama)", "http://127.0.0.1:11434/v1"),
    ("Локальная (LM Studio)", "http://127.0.0.1:1234/v1"),
    ("Свой адрес", ""),
]


def load_saved() -> dict | None:
    """Прочитать сохранённые настройки пользователя, если они есть."""
    path = user_config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save(values: dict) -> Path:
    """Записать настройки в профиль пользователя.

    Ключ пишется как есть, в обычный файл. Это локальный профиль, не
    репозиторий; на уровне программы шифровать его нечем и незачем.
    """
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    clean = {
        "api_base": str(values.get("api_base") or "").strip(),
        "api_key": str(values.get("api_key") or "").strip(),
        "model": str(values.get("model") or "").strip(),
        "max_tokens": int(values.get("max_tokens") or 900),
        "temperature": float(values.get("temperature") or 0.2),
    }
    if not clean["api_base"]:
        raise AiError("не заполнен адрес API")
    if not clean["api_key"]:
        raise AiError("не заполнен ключ")
    if not clean["model"]:
        raise AiError("не заполнена модель")

    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def clear() -> None:
    """Удалить сохранённые настройки."""
    user_config_path().unlink(missing_ok=True)


def mask(key: str) -> str:
    """Показать ключ так, чтобы его нельзя было скопировать с экрана."""
    text = str(key or "")
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}…{text[-4:]}"


def resolve() -> Settings:
    """Собрать настройки по цепочке: явный путь → профиль → внешний конфиг."""
    explicit = os.environ.get("ALCHEMY_AI_CONFIG")
    if explicit:
        return _from_json(Path(explicit))

def resolve_with_origin() -> tuple[Settings, str]:
    """Собрать настройки и сказать, откуда они взялись."""
    explicit = os.environ.get("ALCHEMY_AI_CONFIG")
    if explicit:
        return _from_json(Path(explicit)), "файл из ALCHEMY_AI_CONFIG"

    saved = load_saved()
    if saved and str(saved.get("api_key") or "").strip():
        return _from_dict(saved, "профиль"), "профиль пользователя"

    from .client import find_config, load_settings  # локальный импорт

    try:
        chat_config = find_config(None)
    except AiError:
        raise AiError(
            "модель не настроена. Откройте «Настройки модели» во вкладке "
            "ИИ-расчётчик и укажите адрес, ключ и модель."
        ) from None

    return load_settings(chat_config), f"внешний конфиг ({chat_config})"


def resolve() -> Settings:
    """Настройки по цепочке, без сведений об источнике."""
    return resolve_with_origin()[0]


def ensure_ready() -> tuple[Settings, str]:
    """Настройки плюс однократный перенос ключа в профиль.

    Если ключ нашёлся в настройках чата, он один раз сохраняется в профиль
    приложения. Дальше программа берёт его оттуда и не зависит от чата;
    и вставлять его руками каждый раз не нужно.

    Переносится только в профиль пользователя — в репозиторий ключ
    не попадает никогда.
    """
    settings, origin = resolve_with_origin()

    if origin.startswith("внешний конфиг"):
        try:
            save({
                "api_base": settings.api_base,
                "api_key": settings.api_key,
                "model": settings.model,
                "max_tokens": settings.max_tokens,
                "temperature": settings.temperature,
            })
        except AiError:
            # профиль недоступен на запись — работаем как есть, не падаем
            return settings, origin
        return settings, "профиль пользователя (ключ перенесён из конфига)"

    return settings, origin


def _from_dict(data: dict, source: str) -> Settings:
    return Settings(
        api_key=str(data.get("api_key") or "").strip(),
        api_base=str(data.get("api_base") or "https://gptunnel.ru/v1").rstrip("/"),
        model=str(data.get("model") or "").strip(),
        max_tokens=int(data.get("max_tokens") or 900),
        temperature=float(data.get("temperature") or 0.2),
    )


def _from_json(path: Path) -> Settings:
    if not path.exists():
        raise AiError(f"нет файла настроек: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AiError(f"не удалось прочитать {path}: {exc}") from exc
    if not str(data.get("api_key") or "").strip():
        raise AiError(f"в {path} не заполнен api_key")
    return _from_dict(data, "файл")
