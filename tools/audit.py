# -*- coding: utf-8 -*-
"""Разведка по проекту: слои, тихие падения, покрытие, данные, ИИ.

Только чтение. Ничего не меняет, ничего не запускает.

Запуск: python tools/audit.py
"""

from __future__ import annotations

import ast
import io
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

FORBIDDEN_UI = ("PySide6", "alchemy.ui", "alchemy.ui_qt", "tkinter")


def python_files(folder: str) -> list[Path]:
    return sorted((ROOT / folder).rglob("*.py"))


def parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        print(f"  СИНТАКСИС: {path.relative_to(ROOT)}: {exc}")
        return None


# ---------------------------------------------------------------- слои

def check_layers() -> list[str]:
    problems: list[str] = []
    for folder in ("alchemy/core", "alchemy/data", "alchemy/engines"):
        for path in python_files(folder):
            tree = parse(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if any(name.startswith(bad) for bad in FORBIDDEN_UI):
                        problems.append(
                            f"{path.relative_to(ROOT)}:{node.lineno} тянет {name}")
    return problems


# ------------------------------------------------- тихие падения

def check_silent() -> tuple[list[str], list[str]]:
    bare: list[str] = []
    swallow: list[str] = []
    for folder in ("alchemy", "tools"):
        for path in python_files(folder):
            tree = parse(path)
            if tree is None:
                continue
            source = path.read_text(encoding="utf-8").splitlines()
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    body = [n for n in node.body
                            if not isinstance(n, ast.Expr)
                            or not isinstance(n.value, ast.Constant)]
                    if not body or all(isinstance(n, ast.Pass) for n in body):
                        line = source[node.lineno - 1].strip() if source else ""
                        bare.append(f"{path.relative_to(ROOT)}:{node.lineno}  {line}")
            # `pass` в ветках if — признак недоделанной логики
            for node in ast.walk(tree):
                if isinstance(node, ast.If) and len(node.body) == 1 \
                        and isinstance(node.body[0], ast.Pass):
                    line = source[node.lineno - 1].strip() if source else ""
                    swallow.append(f"{path.relative_to(ROOT)}:{node.lineno}  {line}")
    return bare, swallow


# ------------------------------------------------- покрытие тестами

def check_coverage() -> list[str]:
    tests_text = "\n".join(
        p.read_text(encoding="utf-8") for p in python_files("tests"))
    uncovered: list[str] = []
    for path in python_files("alchemy/engines"):
        if path.name == "__init__.py":
            continue
        tree = parse(path)
        if tree is None:
            continue
        public = [n.name for n in tree.body
                  if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
        if not public:
            continue
        hits = sum(1 for name in public if name in tests_text)
        if hits == 0:
            uncovered.append(f"{path.name}: 0 из {len(public)} функций в тестах")
        elif hits < len(public) / 2:
            uncovered.append(
                f"{path.name}: {hits} из {len(public)} функций в тестах")
    return uncovered


# ------------------------------------------------- допуски в тестах

def check_tolerances() -> list[str]:
    found: list[str] = []
    for path in python_files("tests"):
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            match = re.search(r"places\s*=\s*(\d+)", line)
            if match and int(match.group(1)) >= 7:
                found.append(f"{path.name}:{number}  мест {match.group(1)}  "
                             f"{line.strip()[:60]}")
    return found


# ------------------------------------------------- ИИ против движков

def check_tools() -> tuple[list[str], int]:
    from alchemy.ai.tools import REGISTRY

    tools = set(REGISTRY)
    missing: list[str] = []
    total = 0
    for path in python_files("alchemy/engines"):
        if path.name.startswith("_"):
            continue
        tree = parse(path)
        if tree is None:
            continue
        public = [n.name for n in tree.body
                  if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
        total += len(public)
        for name in public:
            if name not in tools:
                missing.append(f"{path.stem}.{name}")
    return missing, total


# ------------------------------------------------- данные

COMMON = [
    "NaF", "NaCl", "KCl", "KOH", "NaOH", "H2SO4", "HNO3", "H3PO4", "Na2CO3",
    "NaHCO3", "CaCO3", "CaO", "Ca(OH)2", "Fe2O3", "Fe3O4", "CuO", "CuSO4",
    "ZnO", "ZnSO4", "PbO", "PbSO4", "NH3", "NH4Cl", "NH4NO3", "CO", "CO2",
    "NO", "NO2", "SO2", "SO3", "HCl", "H2S", "AgCl", "AgNO3", "KMnO4",
    "K2Cr2O7", "Al2O3", "Al(OH)3", "SiO2", "MgO", "Na2SO4", "K2SO4",
]


def check_data() -> tuple[int, int, list[str], list[str]]:
    from alchemy.core import formula as F
    from alchemy.data import thermo

    substances = list(thermo.all_substances())
    elements: set[str] = set()
    for substance in substances:
        try:
            elements |= set(F.parse(substance.formula).counts)
        except Exception:
            pass

    keys = {re.sub(r"\([^)]*\)", "", s.key).lower() for s in substances}
    absent = [item for item in COMMON
              if re.sub(r"\([^)]*\)", "", item).lower() not in keys]
    return len(substances), len(elements), absent, []


# ------------------------------------------------- отчёт

def main() -> int:
    print("=" * 70)
    print("РАЗВЕДКА ПО ПРОЕКТУ")
    print("=" * 70)

    print("\n[1] Слои: движки не должны знать про интерфейс")
    problems = check_layers()
    print(f"    нарушений: {len(problems)}")
    for item in problems[:10]:
        print("      " + item)

    print("\n[2] Тихие падения")
    bare, swallow = check_silent()
    print(f"    except без обработки: {len(bare)}")
    for item in bare[:12]:
        print("      " + item)
    print(f"    pass в ветках if: {len(swallow)}")
    for item in swallow[:8]:
        print("      " + item)

    print("\n[3] Покрытие движков тестами")
    uncovered = check_coverage()
    print(f"    движков со слабым покрытием: {len(uncovered)}")
    for item in uncovered[:12]:
        print("      " + item)

    print("\n[4] Слишком щедрые допуски в тестах")
    tolerances = check_tolerances()
    print(f"    мест >= 7: {len(tolerances)}")
    for item in tolerances[:8]:
        print("      " + item)

    print("\n[5] ИИ-инструменты против движков")
    missing, total = check_tools()
    print(f"    функций в движках: {total}, без инструмента: {len(missing)}")
    for item in missing[:15]:
        print("      " + item)

    print("\n[6] Данные")
    count, elements, absent, _extra = check_data()
    print(f"    веществ: {count}, элементов: {elements}")
    print(f"    из частых школьных отсутствуют: {len(absent)}")
    print("      " + ", ".join(absent) if absent else "      все на месте")

    print("\n[7] Размеры")
    for folder in ("alchemy/core", "alchemy/data", "alchemy/engines",
                   "alchemy/ui", "alchemy/ui_qt", "alchemy/ai", "tests", "tools"):
        files = python_files(folder)
        lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in files)
        print(f"    {folder:18} файлов {len(files):3}  строк {lines:6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
