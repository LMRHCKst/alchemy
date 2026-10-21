"""Командная строка: спросить у модели, а посчитает движок.

    python -m alchemy.ai "какая молярная масса медного купороса"
    python -m alchemy.ai --verbose "уравняй KMnO4 + HCl"
    python -m alchemy.ai            # диалог

Ключ берётся из настроек чата Диси. Модель не считает сама: она вызывает
инструменты, а числа возвращает `alchemy.engines`.
"""

from __future__ import annotations

import argparse
import io
import sys

from .agent import Agent
from .client import AiError, ChatClient
from .settings_store import ensure_ready
from .tools import REGISTRY


def _utf8() -> None:
    """Русский текст в консоли Windows без кракозябр."""
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass


def _print_answer(answer, verbose: bool) -> None:
    print(answer.text)
    print()

    if answer.steps:
        print("Посчитано движком:")
        for index, step in enumerate(answer.steps, 1):
            mark = "" if step.ok else "  ← отказ"
            print(f"  {index}. {step.summary()}{mark}")
            if verbose:
                for line in step.result.splitlines():
                    print(f"       {line}")
    else:
        print("Движок не вызывался: ответ не содержит расчётов.")

    if answer.usage.get("total_cost"):
        print(f"\nСтоимость запроса: {answer.usage['total_cost']:.5f}")
    if answer.stopped:
        print(f"Остановлено: {answer.stopped}")


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        prog="alchemy.ai",
        description="Химический калькулятор, которым управляет языковая модель",
    )
    parser.add_argument("question", nargs="*", help="вопрос; без него — диалог")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="показывать полный результат инструментов")
    parser.add_argument("--config", help="путь к JSON с ключом")
    parser.add_argument("--model", help="переопределить модель")
    parser.add_argument("--tools", action="store_true",
                        help="показать список инструментов и выйти")
    parser.add_argument("--max-steps", type=int, default=6,
                        help="предел вызовов инструментов (по умолчанию 6)")
    args = parser.parse_args(argv)

    if args.tools:
        for name in sorted(REGISTRY):
            schema = next(t for t in __import__(
                "alchemy.ai.tools", fromlist=["TOOLS"]).TOOLS
                if t["function"]["name"] == name)
            print(f"{name}: {schema['function']['description']}")
            required = schema["function"]["parameters"].get("required") or []
            properties = schema["function"]["parameters"]["properties"]
            for key in properties:
                mark = "*" if key in required else " "
                print(f"    {mark} {key}")
        print(f"\nвсего инструментов: {len(REGISTRY)}")
        return 0

    try:
        if args.config:
            from .client import load_settings
            settings = load_settings(args.config)
        else:
            settings, _origin = ensure_ready()
    except AiError as exc:
        print(f"Нет доступа к модели: {exc}", file=sys.stderr)
        return 2

    if args.model:
        settings.model = args.model

    client = ChatClient(settings)
    agent = Agent(client, max_steps=args.max_steps)

    if args.question:
        question = " ".join(args.question)
        try:
            answer = agent.ask(question)
        except AiError as exc:
            print(f"Модель недоступна: {exc}", file=sys.stderr)
            return 3
        _print_answer(answer, args.verbose)
        return 0

    print(f"Диси · {settings.source}")
    print("Вопрос по химии. Пустая строка или Ctrl+C — выход.\n")
    history: list[dict] = []
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            return 0
        try:
            answer = agent.ask(question, history=history)
        except AiError as exc:
            print(f"Модель недоступна: {exc}\n", file=sys.stderr)
            continue
        _print_answer(answer, args.verbose)
        print()
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer.text})
        history = history[-8:]


if __name__ == "__main__":
    raise SystemExit(main())
