"""Качественные реакции на ионы и определение вещества.

9 класс: распознавание ионов по внешнему эффекту реакции, ряд качественных
реакций на катионы и анионы, отличительные признаки осадков.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache

from ..core.errors import AlchemyError, DataNotFoundError, InputError
from ..core.results import Result, table_result

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "qualitative.json")


@lru_cache(maxsize=1)
def _database() -> dict:
    """Загрузить справочник качественных реакций."""
    try:
        with open(DATA_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover
        raise DataNotFoundError(
            "Не найден справочник качественных реакций "
            "(alchemy/data/qualitative.json)") from exc
    return data


def _all_rows() -> list[dict]:
    data = _database()
    rows = []
    for row in data.get("cations", []):
        rows.append({**row, "type": "катион"})
    for row in data.get("anions", []):
        rows.append({**row, "type": "анион"})
    return rows


def _normalize_ion(text: str) -> str:
    """Привести запись иона к виду справочника.

    Понимает Cl−, Cl-, Cl^-, хлорид.
    """
    raw = str(text or "").strip()
    if not raw:
        return ""

    def key(text: str) -> tuple[str, int, str]:
        """Тело иона и заряд: SO4^2- и SO4-2 дают одно и то же."""
        cleaned = (text.replace("−", "-").replace("⁺", "+")
                   .replace("⁻", "-").replace("^", "").replace(" ", ""))
        # Захват тела жадный: иначе «SO4-2» разбирается как тело «SO»
        # и заряд «4-»
        match = re.match(r"^(.*)(?:(\d+)([+-])|([+-])(\d+))$", cleaned)
        if not match:
            return cleaned.lower(), 1, ""
        body = match.group(1).lower()
        if match.group(2):
            return body, int(match.group(2) or 1), match.group(3)
        return body, int(match.group(5) or 1), match.group(4)

    wanted = key(raw)
    for row in _all_rows():
        if key(row["ion"]) == wanted:
            return row["ion"]

    # По названию иона: «хлорид» → Cl-
    lowered = raw.lower()
    for row in _all_rows():
        product = str(row.get("product", "")).lower()
        if lowered in product:
            return row["ion"]

    return ""


def ions_list() -> Result:
    """Все ионы, на которые есть качественные реакции."""
    rows = []
    for row in _all_rows():
        rows.append({
            "Ион": row["ion"],
            "Тип": row["type"],
            "Реагент": row["reagent"],
            "Признак": row["effect"],
            "Продукт": row["product"],
        })

    res = table_result(rows, label="Качественные реакции на ионы",
                       columns=["Ион", "Тип", "Реагент", "Признак", "Продукт"])
    res.method = "Справочник качественных реакций"
    res.with_step(f"Ионов в справочнике: {len(rows)}")
    res.with_step("Признак реакции — то, что видно глазами: осадок, его цвет, "
                  "газ, изменение окраски")
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def ion_reactions(ion: str) -> Result:
    """Качественные реакции на один ион."""
    key = _normalize_ion(ion)
    if not key:
        raise DataNotFoundError(
            f"Ион «{ion}» не найден в справочнике. Доступны: "
            + ", ".join(sorted({row['ion'] for row in _all_rows()})))

    reactions = [row for row in _all_rows() if row["ion"] == key]

    rows = []
    for row in reactions:
        rows.append({
            "Реагент": row["reagent"],
            "Формула реагента": row["reagent_formula"],
            "Признак": row["effect"],
            "Продукт": row["product"],
            "Примечание": row.get("note", ""),
        })

    res = table_result(rows, label=f"Качественные реакции на {key}",
                       columns=["Реагент", "Формула реагента", "Признак",
                                "Продукт", "Примечание"])
    res.method = "Справочник качественных реакций"
    res.with_step(f"Ион: {key} ({reactions[0]['type']})")
    res.with_step(f"Реакций в справочнике: {len(rows)}")
    res.with_step("")
    for row in reactions:
        res.with_step(f"  {row['reagent']} ({row['reagent_formula']}): "
                      f"{row['effect']}")
        if row.get("note"):
            res.with_step(f"    {row['note']}")

    res.with_meta("ion", key)
    res.with_meta("count", len(rows))
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def by_reagent(reagent: str) -> Result:
    """Какие ионы дают видимую реакцию с данным реагентом."""
    text = str(reagent or "").strip()
    if not text:
        raise InputError("Укажите реагент")

    lowered = text.lower()
    found = [row for row in _all_rows()
             if lowered in str(row["reagent"]).lower()
             or lowered in str(row["reagent_formula"]).lower()]

    if not found:
        raise DataNotFoundError(
            f"Реагент «{reagent}» не найден. Попробуйте: AgNO3, BaCl2, "
            f"NaOH, HCl, аммиак, лакмус")

    rows = []
    for row in found:
        rows.append({
            "Ион": row["ion"],
            "Признак": row["effect"],
            "Продукт": row["product"],
        })

    res = table_result(rows, label=f"Реакции с реагентом {reagent}",
                       columns=["Ион", "Признак", "Продукт"])
    res.method = "Справочник качественных реакций"
    res.with_step(f"Реагент: {reagent}")
    res.with_step(f"Реагирует с {len(rows)} ионами")
    res.with_step("")
    for row in rows:
        res.with_step(f"  {row['Ион']}: {row['Признак']}")
    res.with_meta("count", len(rows))
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def by_effect(text: str) -> Result:
    """Найти ионы по внешнему признаку реакции."""
    query = str(text or "").strip().lower()
    if not query:
        raise InputError("Опишите, что видно: цвет осадка, газ, окраска")

    words = [word for word in query.replace(",", " ").split() if len(word) > 2]
    scored = []
    for row in _all_rows():
        haystack = f"{row['effect']} {row.get('note', '')}".lower()
        score = sum(1 for word in words if word in haystack)
        if score:
            scored.append((score, row))

    if not scored:
        raise DataNotFoundError(
            f"По описанию «{text}» ничего не нашлось. Попробуйте описать "
            f"цвет осадка: белый, жёлтый, бурый, голубой, зелёный, чёрный.")

    scored.sort(key=lambda item: -item[0])
    rows = []
    for _score, row in scored[:15]:
        rows.append({
            "Ион": row["ion"],
            "Признак": row["effect"],
            "Реагент": row["reagent"],
            "Продукт": row["product"],
        })

    res = table_result(rows, label=f"Что даёт признак «{text}»",
                       columns=["Ион", "Признак", "Реагент", "Продукт"])
    res.method = "Поиск по признаку реакции"
    res.with_step(f"Запрос: {text}")
    res.with_step(f"Подходящих ионов: {len(rows)}")
    res.with_step("")
    for row in rows[:8]:
        res.with_step(f"  {row['Ион']} + {row['Реагент']}: "
                      f"{row['Признак']}")
    res.with_meta("count", len(rows))
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def identify_ion(ion: str) -> Result:
    """Как распознать ион: лучшая проба и мешающие ионы."""
    key = _normalize_ion(ion)
    if not key:
        raise DataNotFoundError(f"Ион «{ion}» не найден в справочнике")

    reactions = [row for row in _all_rows() if row["ion"] == key]
    best = reactions[0]

    # Ионы, дающие похожий признак с тем же реагентом
    similar = []
    for row in _all_rows():
        if row["ion"] == key:
            continue
        # Тот же реагент даёт осадок и с другими ионами: различить
        # можно только по цвету, и об этом надо предупредить
        if row["reagent"] == best["reagent"]:
            similar.append(row["ion"])

    res = Result(
        value=key,
        unit="",
        label=f"Как распознать {key}",
        method="Качественная реакция: реагент и внешний признак",
    )
    res.with_step(f"Ион: {key}")
    res.with_step(f"Лучшая проба: {best['reagent']} "
                  f"({best['reagent_formula']})")
    res.with_step(f"Признак: {best['effect']}")
    res.with_step(f"Продукт: {best['product']}")
    if best.get("note"):
        res.with_step(f"Примечание: {best['note']}")

    if similar:
        res.with_step("")
        res.with_step(f"Похожий признак дают: {', '.join(sorted(set(similar)))}. "
                      f"Отличить поможет дополнительная проба.")
        res.with_warning(
            f"Реакция с {best['reagent']} не различает {key} и "
            f"{', '.join(sorted(set(similar)))}")

    res.with_step("")
    res.with_step("Другие пробы на этот ион:")
    for row in reactions[1:]:
        res.with_step(f"  {row['reagent']}: {row['effect']}")

    res.with_meta("ion", key)
    res.with_meta("similar", sorted(set(similar)))
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res


def compare_ions(first: str, second: str) -> Result:
    """Чем отличаются два иона по качественным реакциям."""
    key_first = _normalize_ion(first)
    key_second = _normalize_ion(second)
    if not key_first or not key_second:
        raise DataNotFoundError("Один из ионов не найден в справочнике")

    rows = []
    for row in _all_rows():
        if row["ion"] in (key_first, key_second):
            rows.append({
                "Ион": row["ion"],
                "Реагент": row["reagent"],
                "Признак": row["effect"],
                "Продукт": row["product"],
            })

    res = table_result(rows, label=f"{key_first} против {key_second}",
                       columns=["Ион", "Реагент", "Признак", "Продукт"])
    res.method = "Сравнение качественных реакций"
    res.with_step(f"Сравниваются {key_first} и {key_second}")
    res.with_step("")
    res.with_step("Признак, который есть у одного иона и нет у другого, "
                  "и есть способ их различить.")
    res.with_meta("first", key_first)
    res.with_meta("second", key_second)
    res.with_source(_database().get("_source", "Школьный курс химии"))
    return res
