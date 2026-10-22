# -*- coding: utf-8 -*-
"""Собрать таблицы из внешней сверки в один JSON для движков.

Источник: docs/school_chem/audit2 (рабочая папка, в репозиторий не идёт).
Результат: alchemy/data/school_tables.json — уже в репозитории.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path("D:/AI_Tools/calk")
AUDIT = ROOT / "docs/school_chem/audit2"
TARGET = ROOT / "alchemy/data/school_tables.json"


def md_sections(text: str) -> dict[str, str]:
    """Разбить маркдаун на разделы по заголовкам «## 4.N…»."""
    parts = re.split(r"^## ", text, flags=re.M)
    result: dict[str, str] = {}
    for part in parts[1:]:
        head, _, body = part.partition("\n")
        number = head.split()[0].rstrip(".").strip()
        result[number] = result.get(number, "") + body
    return result


def md_tables(body: str) -> list[list[list[str]]]:
    """Все таблицы раздела: список таблиц, каждая — список строк-ячеек."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if current:
                tables.append(current)
                current = []
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        current.append(cells)
    if current:
        tables.append(current)
    return tables


def clean(text: str) -> str:
    """Убрать маркдаун-разметку из ячейки."""
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.strip()


def rows_as_dicts(table: list[list[str]]) -> list[dict[str, str]]:
    if not table:
        return []
    header = [clean(c) for c in table[0]]
    result = []
    for row in table[1:]:
        if len(row) != len(header):
            continue
        result.append({header[i]: clean(row[i]) for i in range(len(header))})
    return result


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    part4 = (AUDIT / "02_part4.md").read_text(encoding="utf-8")
    sections = {"4": part4}   # таблицы ищем по всему файлу

    data: dict[str, object] = {
        "_source": (
            "Внешняя сверка 22.10.2026: docs/school_chem/audit2. "
            "Тиры: A — справочник/стандарт, B — учебник, C — энциклопедия, "
            "? — не подтверждено."
        ),
    }

    # --- плотности
    density = load_csv(AUDIT / "data/density_h2so4.csv")
    data["density_h2so4"] = [
        {"w": float(r["w_percent"]), "rho": float(r["rho_g_cm3"]),
         "t": float(r["t_C"]), "tier": r["tier"]}
        for r in density
        if r.get("w_percent") and r.get("rho_g_cm3")
    ]

    # Крайние точки из вики-таблицы: NBS-скан заканчивается на 90 %,
    # а 98 % и 100 % нужны для концентрированной кислоты.
    for w, rho in ((98.0, 1.8365), (100.0, 1.8305)):
        data["density_h2so4"].append({"w": w, "rho": rho, "t": 20.0,
                                       "tier": "C"})
    data["density_h2so4"].sort(key=lambda row: row["w"])

    # --- ван-дер-ваальс
    vdw = load_csv(AUDIT / "data/vdw.csv")
    data["vdw"] = [
        {"name": r["substance"], "a": float(r["a_L2bar_mol2"]),
         "b": float(r["b_L_mol"])}
        for r in vdw
        if r.get("a_L2bar_mol2") and r.get("b_L_mol")
    ]

    # --- растворители
    solvents = load_csv(AUDIT / "data/kf_kb_solvents.csv")
    data["solvents"] = [
        {"name": r["solvent"], "t_boil": float(r["Tb_C"]),
         "t_freeze": float(r["Tf_C"]), "kb": float(r["Kb"]),
         "kf": float(r["Kf"]), "source": r["source"], "tier": r["tier"]}
        for r in solvents
        if r.get("Kb") and r.get("Kf")
    ]

    # --- электролиз
    electrolysis = []
    for table in md_tables(sections.get("4", "")):
        rows = rows_as_dicts(table)
        if rows and "Электролит" in rows[0]:
            electrolysis.extend(rows)
    data["electrolysis"] = electrolysis

    # --- термическое разложение
    decomposition = []
    for table in md_tables(sections.get("4", "")):
        rows = rows_as_dicts(table)
        if rows and "Вещество" in rows[0] and "Продукты" in rows[0]:
            decomposition.extend(rows)
    data["decomposition"] = decomposition

    # --- качественные реакции и цвета
    qualitative = []
    for table in md_tables(sections.get("4", "")):
        rows = rows_as_dicts(table)
        if rows and "Ион" in rows[0]:
            qualitative.extend(rows)
    data["qualitative"] = qualitative

    # --- амфотерные комплексы
    amphoteric = []
    for table in md_tables(sections.get("4", "")):
        rows = rows_as_dicts(table)
        if rows and "Гидроксид" in rows[0]:
            amphoteric.extend(rows)
    data["amphoteric"] = amphoteric

    # --- комплексы
    complexes = []
    for table in md_tables(sections.get("4", "")):
        rows = rows_as_dicts(table)
        if rows and "Формула" in rows[0] and "КЧ" in rows[0]:
            complexes.extend(rows)
    data["complexes"] = complexes

    # --- полимеры
    polymers = []
    for table in md_tables(sections.get("4", "")):
        rows = rows_as_dicts(table)
        if rows and "Полимер" in rows[0]:
            polymers.extend(rows)
    data["polymers"] = polymers

    # --- степени окисления в исключениях
    exceptions = []
    for table in md_tables(sections.get("4", "")):
        rows = rows_as_dicts(table)
        if rows and "Соединение" in rows[0]:
            exceptions.extend(rows)
    data["oxidation_exceptions"] = exceptions

    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                      encoding="utf-8")

    print(f"  файл: {TARGET}")
    for key, value in data.items():
        if isinstance(value, list):
            print(f"   {key}: {len(value)} записей")
        elif isinstance(value, dict):
            print(f"   {key}: {len(value)} записей")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
