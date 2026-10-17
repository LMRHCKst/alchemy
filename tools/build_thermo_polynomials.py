# -*- coding: utf-8 -*-
"""Генерация снимка термохимических полиномов из базы Burcat.

Источник — локальный файл BURCAT_THR.xml из пакета thermochem. Он содержит
коэффициенты NASA для 1300+ веществ в двух температурных диапазонах, что даёт
температурную зависимость теплоёмкости. В ручном справочнике Cp хранится
одним числом при 298 К, поэтому нагрев выше комнатной температуры считался
с грубым допущением.

Снимок нужен, чтобы программа оставалась независимой от пакета: thermochem
требуется только при пересборке данных, как mendeleev для элементов.

Ключевая тонкость: поле «formula» в базе — это не формула, а название вида
«CH4   RRHO», «H2O(L)» или «AL(cr) REF ELEMEN». Поэтому записи индексируются
по составу, восстановленному из узла elements, а не по строке названия.

Запуск:
    python tools/build_thermo_polynomials.py
    python tools/build_thermo_polynomials.py --xml путь/к/BURCAT_THR.xml
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "alchemy", "data", "thermo_polynomials.json")

# Состояния в Burcat: G — газ, L — жидкость, S — твёрдое, C — кристаллическое.
STATE_MAP = {"G": "g", "L": "l", "S": "s", "C": "s"}

# «-241.826+/-0.04 KJ» — значение и погрешность в одной строке
_HF_RE = re.compile(
    r"(?P<value>[-+]?\d+(?:\.\d+)?)\s*(?:[+-]{1,2}\s*(?P<unc>\d+(?:\.\d+)?))?")

# Признак заряженной частицы в названии: завершающий + или -
_CHARGE_RE = re.compile(r"[+-]\s*$")


def composition_key(counts: dict[str, int], charge: int = 0) -> str:
    """Устойчивый ключ по составу: элементы по алфавиту, затем заряд."""
    body = "".join(f"{el}{counts[el]}" for el in sorted(counts))
    if charge:
        body += f"^{charge:+d}"
    return body


def parse_hf298(node) -> tuple[float | None, float | None]:
    """Извлечь энтальпию образования и её погрешность из узла hf298."""
    if node is None:
        return None, None
    for child in node:
        text = (child.text or "").strip()
        if not text:
            continue
        match = _HF_RE.search(text)
        if not match:
            continue
        value = float(match.group("value"))
        unc_text = match.group("unc")
        return value, (float(unc_text) if unc_text else None)
    return None, None


def parse_coefficients(node) -> tuple[list[float] | None, list[float] | None]:
    """Извлечь коэффициенты NASA для нижнего и верхнего диапазона."""
    if node is None:
        return None, None

    def read(tag: str):
        block = node.find(tag)
        if block is None:
            return None
        by_name = {}
        for coef in block:
            name = coef.attrib.get("name")
            text = (coef.text or "").strip()
            if not name or not text:
                continue
            try:
                by_name[name] = float(text.replace("D", "E"))
            except ValueError:
                return None
        if len(by_name) != 7:
            return None
        return [by_name[f"a{i}"] for i in range(1, 8)]

    return read("range_Tmin_to_1000"), read("range_1000_to_Tmax")


def parse_elements(node) -> dict[str, int]:
    """Состав вещества из узла elements."""
    result: dict[str, int] = {}
    if node is None:
        return result
    for element in node:
        name = element.attrib.get("name")
        count = element.attrib.get("num_of_atoms")
        if not name or count is None:
            continue
        try:
            result[name] = int(float(count))
        except ValueError:
            continue
    return result


def find_xml(explicit: str | None) -> str:
    """Найти файл базы Burcat."""
    if explicit:
        if not os.path.exists(explicit):
            raise SystemExit(f"Файл не найден: {explicit}")
        return explicit

    try:
        import thermochem
    except ImportError:
        raise SystemExit(
            "Пакет thermochem не установлен. Установите его:\n"
            "    python -m pip install thermochem\n"
            "или укажите путь к BURCAT_THR.xml через --xml"
        )

    path = os.path.join(os.path.dirname(thermochem.__file__), "BURCAT_THR.xml")
    if not os.path.exists(path):
        raise SystemExit(f"В пакете thermochem нет файла базы: {path}")
    return path


def quality_rank(quality: str) -> int:
    """Чем меньше число, тем лучше оценка качества данных."""
    return {"A": 0, "B": 1, "C": 2, "D": 3}.get(quality, 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", help="путь к BURCAT_THR.xml")
    parser.add_argument("--output", default=OUTPUT, help="куда записать снимок")
    args = parser.parse_args()

    xml_path = find_xml(args.xml)
    print(f"Источник: {xml_path}")
    print(f"Размер:   {os.path.getsize(xml_path) / 1024 / 1024:.2f} МБ")

    root = ET.parse(xml_path).getroot()
    records = root.findall("specie")
    print(f"Записей specie: {len(records)}")

    species: dict[str, dict] = {}
    stats = {
        "duplicates": 0,
        "charged_skipped": 0,
        "no_composition": 0,
        "no_coefficients": 0,
    }

    for specie in records:
        hf_value, hf_unc = parse_hf298(specie.find("hf298"))
        cas = specie.attrib.get("CAS", "")

        for phase in specie.findall("phase"):
            name = " ".join((phase.findtext("formula") or "").split())
            state_raw = (phase.findtext("phase") or "").strip().upper()
            if not name or state_raw not in STATE_MAP:
                continue

            counts = parse_elements(phase.find("elements"))
            if not counts:
                stats["no_composition"] += 1
                continue

            # Заряженные частицы сюда не берём: ионы в программе ведутся
            # отдельно, с конвенцией электрона. Смешивать их нельзя.
            if _CHARGE_RE.search(name):
                stats["charged_skipped"] += 1
                continue

            low, high = parse_coefficients(phase.find("coefficients"))
            if low is None or high is None:
                stats["no_coefficients"] += 1
                continue

            limits = phase.find("temp_limit")
            try:
                t_min = float(limits.attrib["low"]) if limits is not None else 200.0
                t_max = float(limits.attrib["high"]) if limits is not None else 6000.0
            except (KeyError, TypeError, ValueError):
                t_min, t_max = 200.0, 6000.0

            try:
                molar_mass = float((phase.findtext("molecular_weight") or "").strip())
            except ValueError:
                molar_mass = None

            state = STATE_MAP[state_raw]
            key = f"{composition_key(counts)}|{state}"
            quality = (phase.findtext("calc_quality") or "").strip().upper()[:1]

            entry = {
                "name": name,
                "state": state,
                "counts": counts,
                "Tmin": t_min,
                "Tmax": t_max,
                "M": molar_mass,
                "dHf": hf_value,
                "dHf_unc": hf_unc,
                "quality": quality,
                "cas": cas or None,
                "source": (phase.findtext("source") or "").strip() or None,
                "date": (phase.findtext("date") or "").strip() or None,
                "low": low,
                "high": high,
            }

            existing = species.get(key)
            if existing is not None:
                stats["duplicates"] += 1
                # Оставляем запись с более высокой оценкой качества,
                # при равенстве — ту, у которой есть энтальпия образования
                better_quality = (quality_rank(quality)
                                  < quality_rank(existing["quality"]))
                same_quality_with_hf = (quality_rank(quality)
                                        == quality_rank(existing["quality"])
                                        and hf_value is not None
                                        and existing["dHf"] is None)
                if not (better_quality or same_quality_with_hf):
                    continue

            species[key] = entry

    print(f"Сохранено веществ: {len(species)}")
    print(f"  дублей по составу: {stats['duplicates']}")
    print(f"  заряженных пропущено: {stats['charged_skipped']}")
    print(f"  без состава: {stats['no_composition']}")
    print(f"  без коэффициентов: {stats['no_coefficients']}")

    payload = {
        "_source": (
            "Alexander Burcat, Branko Ruscic. Thermodynamic Data for Combustion "
            "and Air-Pollution Use (BURCAT_THR). NASA 7-коэффициентные полиномы "
            "Cp/R, H/RT, S/R в двух температурных диапазонах. Локальная копия "
            "из пакета thermochem (файл BURCAT_THR.xml)."
        ),
        "_meta": {
            "coefficient_format": "NASA-7: Cp/R = a1+a2T+a3T²+a4T³+a5T⁴; "
                                  "H/RT = a1+a2T/2+a3T²/3+a4T³/4+a5T⁴/5+a6/T; "
                                  "S/R = a1·lnT+a2T+a3T²/2+a4T³/3+a5T⁴/4+a7",
            "key_format": "состав по алфавиту без пробелов | состояние, "
                          "например H2O1|g",
            "state_codes": {"g": "газ", "l": "жидкость", "s": "твёрдое"},
            "temperature_ranges": "low: от Tmin до 1000 К, high: от 1000 К до Tmax",
            "dHf_units": "кДж/моль при 298.15 К",
            "reference_temperature": 298.15,
            "charged_species_excluded": True,
            "records": len(species),
            "generator": "tools/build_thermo_polynomials.py",
        },
        "species": species,
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(args.output)
    print(f"Записано: {args.output} ({size / 1024:.0f} КБ)")


if __name__ == "__main__":
    main()
