"""История диалогов с моделью: сохранение в профиле пользователя.

Файлы лежат рядом с настройками, в `%APPDATA%\\Alchemy\\chats`. В
репозиторий они не попадают: там могут быть вопросы человека.

Формат простой: JSON с заголовком, датами, моделью и сообщениями.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .settings_store import APP_DIR

#: расширение файлов истории
SUFFIX = ".json"

#: сколько символов заголовка оставлять
TITLE_LIMIT = 60


def chats_dir() -> Path:
    """Папка с историей диалогов."""
    from .settings_store import user_config_path

    return user_config_path().parent / "chats"


def _slug(text: str) -> str:
    """Безопасное имя файла из заголовка."""
    clean = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    clean = re.sub(r"[\s-]+", "_", clean)
    return clean[:40] or "chat"


def title_from(messages: list[dict]) -> str:
    """Заголовок по первому вопросу человека."""
    for message in messages:
        if message.get("role") == "user":
            text = str(message.get("content") or "").strip().replace("\n", " ")
            return text[:TITLE_LIMIT] or "Диалог"
    return "Диалог"


def save(messages: list[dict], title: str = "", model: str = "",
         chat_id: str = "") -> Path:
    """Сохранить диалог. Возвращает путь к файлу."""
    folder = chats_dir()
    folder.mkdir(parents=True, exist_ok=True)

    if not chat_id:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        chat_id = f"{_slug(title or title_from(messages))}-{stamp}"

    path = folder / f"{chat_id}{SUFFIX}"
    payload = {
        "id": chat_id,
        "title": title or title_from(messages),
        "model": model,
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "messages": messages,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def list_chats() -> list[dict]:
    """Список сохранённых диалогов, свежие сверху."""
    folder = chats_dir()
    if not folder.exists():
        return []

    items: list[dict] = []
    for path in folder.glob(f"*{SUFFIX}"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        messages = data.get("messages") or []
        items.append({
            "id": data.get("id") or path.stem,
            "title": data.get("title") or title_from(messages),
            "updated": data.get("updated") or "",
            "model": data.get("model") or "",
            "turns": sum(1 for m in messages if m.get("role") == "user"),
        })
    items.sort(key=lambda item: item["updated"], reverse=True)
    return items


def load(chat_id: str) -> dict | None:
    """Прочитать диалог по идентификатору."""
    path = chats_dir() / f"{chat_id}{SUFFIX}"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def delete(chat_id: str) -> bool:
    """Удалить диалог. Возвращает True, если файл был."""
    path = chats_dir() / f"{chat_id}{SUFFIX}"
    if not path.exists():
        return False
    path.unlink()
    return True


def clear_all() -> int:
    """Удалить всю историю. Возвращает число удалённых файлов."""
    count = 0
    for path in chats_dir().glob(f"*{SUFFIX}"):
        path.unlink()
        count += 1
    return count
