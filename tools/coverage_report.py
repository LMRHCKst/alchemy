# -*- coding: utf-8 -*-
"""Отчёт о покрытии: какие функции движков упоминаются в тестах.

Грубая, но честная метрика: для каждой публичной функции движка ищем
имя в текстах тестов. Это не покрытие строк, а «есть ли вообще тест,
который трогает функцию».

Запуск: python tools/coverage_report.py [--strict]
"""

from __future__ import annotations

import ast
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ENGINES = ROOT / "alchemy" / "engines"
TESTS = ROOT / "tests"


def engine_functions() -> dict[str, list[str]]:
    """Публичные функции по модулям движков."""
    result: dict[str, list[str]] = {}
    for path in sorted(ENGINES.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = [node.name for node in tree.body
                 if isinstance(node, ast.FunctionDef)
                 and not node.name.startswith("_")]
        if names:
            result[path.stem] = names
    return result


def tests_text() -> str:
    """Весь текст тестов одним куском."""
    chunks = []
    for path in sorted(TESTS.glob("*.py")):
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    text = tests_text()
    functions = engine_functions()

    total = 0
    covered = 0
    gaps: list[tuple[str, str]] = []

    print(f"{'модуль':22} {'функций':>8} {'в тестах':>9} {'доля':>7}")
    print("-" * 50)
    for module, names in functions.items():
        hits = [name for name in names if name in text]
        total += len(names)
        covered += len(hits)
        share = len(hits) / len(names) * 100
        print(f"{module:22} {len(names):8} {len(hits):9} {share:6.0f} %")
        for name in names:
            if name not in hits:
                gaps.append((module, name))

    print("-" * 50)
    print(f"{'всего':22} {total:8} {covered:9} {covered / total * 100:6.0f} %")

    if gaps:
        print()
        print(f"без упоминаний в тестах: {len(gaps)}")
        for module, name in gaps[:40]:
            print(f"  {module}.{name}")
        if len(gaps) > 40:
            print(f"  … и ещё {len(gaps) - 40}")

    if strict and gaps:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
