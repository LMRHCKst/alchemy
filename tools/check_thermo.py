# -*- coding: utf-8 -*-
"""Сверка справочника: ΔG°f должно равняться ΔH°f − T·ΔS°f.

ΔS°f считается как S(вещества) минус сумма энтропий простых веществ
в расчёте на атом. Так проверяется вся тройка чисел разом: если одно
из них взято из другой таблицы или перепутано, это сразу видно.

Запуск: python tools/check_thermo.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from alchemy.core import formula as F
from alchemy.data import thermo

T = 298.15

#: стандартная энтропия простого вещества на один атом, Дж/(моль·К).
#: Для двухатомных газов — половина молярной энтропии молекулы.
ATOM_ENTROPY = {
    "H": 130.68 / 2, "O": 205.15 / 2, "N": 191.61 / 2, "F": 202.79 / 2,
    "Cl": 223.07 / 2, "Br": 152.23 / 2, "I": 116.14 / 2,
    "C": 5.74, "S": 32.05, "P": 41.09, "Si": 18.83, "B": 5.87,
    "Na": 51.21, "K": 64.18, "Li": 29.12, "Ca": 41.59, "Mg": 32.67,
    "Al": 28.33, "Fe": 27.28, "Cu": 33.15, "Zn": 41.63, "Ag": 42.55,
    "Ba": 62.42, "Pb": 64.81, "Mn": 32.01, "Cr": 23.77, "Ti": 30.63,
    "Ni": 29.87, "Sn": 51.18, "Co": 30.04, "Cd": 51.76, "Hg": 75.90,
}

#: допустимое расхождение, кДж/моль
TOLERANCE = 8.0


def check() -> tuple[list[tuple[str, float, float]], int]:
    rows: list[tuple[str, float, float]] = []
    checked = 0
    for substance in thermo.all_substances():
        if None in (substance.dHf, substance.dGf, substance.S):
            continue
        try:
            counts = F.parse(F.split_state(substance.key)[0]).counts
        except Exception:
            continue
        unknown = [element for element in counts if element not in ATOM_ENTROPY]
        if unknown or not counts:
            continue

        reference_entropy = sum(
            ATOM_ENTROPY[element] * amount for element, amount in counts.items())
        delta_s = substance.S - reference_entropy
        expected = substance.dHf - T * delta_s / 1000.0
        deviation = abs(expected - substance.dGf)
        checked += 1
        if deviation > TOLERANCE:
            rows.append((substance.key, substance.dGf, expected, deviation))
    return rows, checked


def main() -> int:
    rows, checked = check()
    print(f"проверено веществ: {checked}")
    print(f"расхождений больше {TOLERANCE:g} кДж: {len(rows)}")
    print()
    if rows:
        print(f"{'вещество':22} {'dG в базе':>11} {'по формуле':>11} {'разница':>8}")
        for key, actual, expected, deviation in sorted(rows, key=lambda r: -r[3]):
            print(f"{key:22} {actual:11.1f} {expected:11.1f} {deviation:8.1f}")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
