"""Локальная модель: поиск llama.cpp, запуск сервера, список gguf.

Нужна, чтобы ИИ-чат работал без интернета и без чужого ключа. Движок
и модели ищутся в папке рядом с программой, но путь можно
переопределить: `ALCHEMY_LLAMA_DIR` для движка, `ALCHEMY_MODELS_DIR`
для папки с моделями.

Сервер поднимается отдельным процессом на localhost и говорит на
OpenAI-совместимом API, поэтому остальной код разницы не замечает.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

#: где искать движок и модели, если не задано переменными окружения
DEFAULT_ROOTS = [
    Path("D:/AI_Tools/disi-chat"),
    Path(__file__).resolve().parents[3].parent / "disi-chat",
]

#: подпапки с сборками llama.cpp, в порядке предпочтения
ENGINE_SUBDIRS = ("vulkan", "cuda", "cpu", "")

#: порт по умолчанию
DEFAULT_PORT = 1235

#: контекст по умолчанию. Схемы инструментов и системный промпт занимают
#: около трёх тысяч токенов, поэтому 4096 не хватает — модель отвечает
#: ошибкой переполнения
DEFAULT_CONTEXT = 8192

#: сколько ждать загрузку модели
LOAD_TIMEOUT = 240.0


def _roots() -> list[Path]:
    roots = list(DEFAULT_ROOTS)
    custom = os.environ.get("ALCHEMY_LLAMA_DIR")
    if custom:
        roots.insert(0, Path(custom))
    return roots


def find_engine() -> Path | None:
    """Найти llama-server.exe."""
    for root in _roots():
        for sub in ENGINE_SUBDIRS:
            base = root / "llama" / sub if sub else root / "llama"
            exe = base / "llama-server.exe"
            if exe.exists():
                return exe
        found = list((root / "llama").rglob("llama-server.exe"))
        if found:
            return found[0]
    return None


def find_models() -> list[Path]:
    """Найти gguf-модели."""
    dirs: list[Path] = []
    custom = os.environ.get("ALCHEMY_MODELS_DIR")
    if custom:
        dirs.append(Path(custom))
    for root in _roots():
        dirs.append(root / "models")

    seen: set[Path] = set()
    models: list[Path] = []
    for folder in dirs:
        if not folder.exists():
            continue
        for file in sorted(folder.glob("*.gguf")):
            if "mmproj" in file.name.lower():
                continue
            resolved = file.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            models.append(file)
    return models


def base_url(port: int = DEFAULT_PORT) -> str:
    return f"http://127.0.0.1:{port}/v1"


def health(port: int = DEFAULT_PORT) -> bool:
    """Отвечает ли сервер."""
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(request, timeout=2) as response:
            return b'"ok"' in response.read()
    except Exception:
        return False


def models_online(port: int = DEFAULT_PORT) -> list[str]:
    """Что сервер отдаёт в каталоге моделей."""
    try:
        request = urllib.request.Request(f"{base_url(port)}/models")
        with urllib.request.urlopen(request, timeout=5) as response:
            blob = json.loads(response.read().decode("utf-8", "replace"))
    except Exception:
        return []
    items = blob.get("data") if isinstance(blob, dict) else None
    if not isinstance(items, list):
        return []
    return [str(item.get("id")) for item in items if isinstance(item, dict)]


def running() -> bool:
    """Есть ли процесс llama-server, который мы запускали."""
    process = _STATE.get("process")
    return bool(process and process.poll() is None)


def start(model: Path | str | None = None, port: int = DEFAULT_PORT,
          gpu_layers: int = 99, context: int = 8192) -> tuple[bool, str]:
    """Запустить сервер. Возвращает (получилось, сообщение)."""
    if health(port):
        return True, "сервер уже работает"

    engine = find_engine()
    if engine is None:
        return False, ("не нашёл llama-server.exe. Положите сборку llama.cpp "
                       "в папку llama/ или укажите путь в ALCHEMY_LLAMA_DIR")

    chosen: Path | None = Path(model) if model else None
    if chosen is None:
        models = find_models()
        if not models:
            return False, ("не нашёл ни одного .gguf. Положите модели в папку "
                           "models/ или укажите путь в ALCHEMY_MODELS_DIR")
        chosen = models[0]
    if not chosen.exists():
        return False, f"файл модели не найден: {chosen}"

    log_path = Path(os.environ.get("TEMP", ".")) / "alchemy_llama.log"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        handle = open(log_path, "a", encoding="utf-8", buffering=1)
        process = subprocess.Popen(
            [str(engine), "-m", str(chosen),
             "-ngl", str(gpu_layers), "-c", str(context),
             "--port", str(port), "--host", "127.0.0.1"],
            cwd=str(engine.parent), stdout=handle, stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    except OSError as exc:
        return False, f"не удалось запустить движок: {exc}"

    _STATE["process"] = process
    _STATE["model"] = str(chosen)
    _STATE["port"] = port
    _STATE["log"] = str(log_path)

    deadline = time.time() + LOAD_TIMEOUT
    while time.time() < deadline:
        if process.poll() is not None:
            tail = _tail(log_path)
            return False, f"движок завершился. Лог: {tail or log_path}"
        if health(port):
            return True, f"запущено: {chosen.name}"
        time.sleep(2.0)

    return False, f"модель не загрузилась за {int(LOAD_TIMEOUT)} с. Лог: {log_path}"


def stop() -> None:
    """Остановить запущенный сервер."""
    process = _STATE.get("process")
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    _STATE.clear()


def status(port: int = DEFAULT_PORT) -> dict:
    """Что есть в наличии: движок, модели, живой сервер."""
    models = find_models()
    return {
        "engine": str(find_engine() or ""),
        "models": [m.name for m in models],
        "model_paths": [str(m) for m in models],
        "online": health(port),
        "managed": running(),
        "port": port,
        "base_url": base_url(port),
    }


def _tail(path: Path, lines: int = 3) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return " / ".join(line.strip() for line in text[-lines:] if line.strip())


_STATE: dict[str, object] = {}


if __name__ == "__main__":  # pragma: no cover - ручная проверка
    sys.stdout.reconfigure(encoding="utf-8")
    info = status()
    print("движок:", info["engine"] or "не найден")
    print("модели:", ", ".join(info["models"]) or "нет")
    print("сервер:", "работает" if info["online"] else "остановлен")
    print("адрес:", info["base_url"])
