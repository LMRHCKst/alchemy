"""Клиент OpenAI-совместимого API с поддержкой вызова инструментов.

Ключ и адрес берутся из профиля пользователя. Если его там нет,
программа смотрит внешний конфиг с ключом — чтобы при первом запуске
ничего не вводить руками. Путь переопределяется переменной окружения
`ALCHEMY_AI_CONFIG`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: где по умолчанию лежит конфиг чата
DEFAULT_CONFIGS = [
    Path("D:/AI_Tools/disi-chat/config.json"),
    Path(__file__).resolve().parents[3] / "disi-chat" / "config.json",
]


class AiError(RuntimeError):
    """Ошибка обращения к модели."""


@dataclass
class Settings:
    """Что нужно знать, чтобы отправить запрос.

    Продвинутые поля (top_p, штрафы, seed, число шагов, свой системный
    промпт) работают по-настоящему, но применяются только когда включён
    флаг `advanced`. В интерфейсе раздел заблокирован: значения по
    умолчанию проверены, а крутить их без понимания — способ сломать
    ответ и не заметить.
    """

    api_key: str
    api_base: str = "https://gptunnel.ru/v1"
    model: str = "claude-5.5-haiku"
    max_tokens: int = 900
    temperature: float = 0.2
    timeout: float = 180.0

    # --- продвинутые ---
    advanced: bool = False
    top_p: float = 1.0
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    seed: int | None = None
    max_steps: int = 6
    system_prompt: str = ""

    @property
    def source(self) -> str:
        return f"{self.api_base} · {self.model}"

    def generation_params(self) -> dict[str, Any]:
        """Параметры генерации для запроса.

        Базовые уходят всегда, продвинутые — только при `advanced`.
        """
        params: dict[str, Any] = {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if not self.advanced:
            return params
        params["top_p"] = self.top_p
        if self.presence_penalty:
            params["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty:
            params["frequency_penalty"] = self.frequency_penalty
        if self.seed is not None:
            params["seed"] = self.seed
        return params


def find_config(explicit: str | os.PathLike | None = None) -> Path:
    """Найти файл настроек: явный путь, переменная окружения, известные места."""
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise AiError(f"нет файла настроек: {path}")
        return path

    env = os.environ.get("ALCHEMY_AI_CONFIG")
    if env:
        path = Path(env)
        if not path.exists():
            raise AiError(f"ALCHEMY_AI_CONFIG указывает на несуществующий файл: {path}")
        return path

    for path in DEFAULT_CONFIGS:
        if path.exists():
            return path

    raise AiError(
        "не найден файл настроек с ключом. Укажи его через ALCHEMY_AI_CONFIG "
        "или положи в одно из мест: "
        + ", ".join(str(p) for p in DEFAULT_CONFIGS)
    )


def load_settings(explicit: str | os.PathLike | None = None) -> Settings:
    """Прочитать настройки из JSON чата и привести к нужному виду."""
    path = find_config(explicit)
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AiError(f"не удалось прочитать {path}: {exc}") from exc

    key = str(raw.get("api_key") or "").strip()
    if not key:
        raise AiError(f"в {path} не заполнен api_key")

    model = str(raw.get("model") or "").strip()
    if not model or model.lower() == "auto":
        fallbacks = raw.get("model_fallbacks") or []
        model = str(fallbacks[0]) if fallbacks else "claude-5.5-haiku"

    return Settings(
        api_key=key,
        api_base=str(raw.get("api_base") or "https://gptunnel.ru/v1").rstrip("/"),
        model=model,
        max_tokens=int(raw.get("max_tokens") or 900),
        temperature=0.2,
        timeout=float(raw.get("local_timeout") or 180.0),
    )


@dataclass
class Reply:
    """Ответ модели: текст и запрошенные вызовы инструментов."""

    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    finish: str = ""
    model: str = ""
    usage: dict = field(default_factory=dict)
    reasoning: str = ""


class ChatClient:
    """Минимальный клиент: один метод, один запрос."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        # GPTunnel принимает ключ без префикса Bearer
        return {
            "Authorization": self.settings.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "alchemy-ai/0.1",
        }

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        tool_choice: str = "auto",
    ) -> Reply:
        """Отправить диалог и получить ответ, возможно с вызовами."""
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
        }
        payload.update(self.settings.generation_params())
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.settings.api_base}/chat/completions",
            data=body,
            headers=self._headers(),
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
                blob = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            lower = detail.lower()
            if "context" in lower and "exceed" in lower:
                raise AiError(
                    "модель не вмещает запрос: контекст сервера слишком мал. "
                    "Перезапустите локальный сервер с -c 8192 или больше."
                ) from None
            raise AiError(f"HTTP {exc.code}: {detail or exc.reason}") from None
        except urllib.error.URLError as exc:
            raise AiError(f"сеть недоступна: {exc.reason}") from None
        except TimeoutError:
            raise AiError("модель не ответила за отведённое время") from None

        choices = blob.get("choices") or [{}]
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))

        return Reply(
            text=text.strip(),
            tool_calls=list(message.get("tool_calls") or []),
            finish=str(choices[0].get("finish_reason") or ""),
            model=str(blob.get("model") or self.settings.model),
            usage=blob.get("usage") or {},
            # локальные модели с рассуждениями кладут их отдельно;
            # в ответ пользователю это не попадает
            reasoning=str(message.get("reasoning_content")
                          or message.get("reasoning") or "").strip(),
        )

    def list_models(self) -> list[str]:
        """Каталог моделей провайдера — для проверки связи и подсказки.

        Не все OpenAI-совместимые серверы отдают этот список: у некоторых
        путь закрыт или требует другого ключа. Отсутствие списка не значит,
        что работать нельзя, поэтому ошибка здесь не поднимается.
        """
        request = urllib.request.Request(
            f"{self.settings.api_base}/models",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                blob = json.loads(response.read().decode("utf-8", "replace"))
        except Exception as exc:
            raise AiError(f"каталог моделей недоступен: {exc}") from None

        items = blob.get("data") if isinstance(blob, dict) else None
        if not isinstance(items, list):
            raise AiError("провайдер ответил, но список моделей не в том формате")

        names = []
        for item in items:
            if isinstance(item, dict):
                identifier = item.get("id") or item.get("name")
                if identifier:
                    names.append(str(identifier))
        return sorted(names)
