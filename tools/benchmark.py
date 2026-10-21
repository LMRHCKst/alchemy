# -*- coding: utf-8 -*-
"""Замер времени на тяжёлых расчётах.

Нужен, чтобы замечать, когда что-то стало считаться заметно дольше.
Запуск: python tools/benchmark.py
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from alchemy.engines import acidbase as AB
from alchemy.engines import balancer as BAL
from alchemy.engines import gases as GAS
from alchemy.engines import nuclear as NUC
from alchemy.engines import solutions as SOL
from alchemy.engines import stoichiometry as ST
from alchemy.engines import thermo as TH

#: имя -> (функция, повторов)
CASES = {
    "уравнивание KMnO4": (
        lambda: BAL.balance("KMnO4 + HCl = KCl + MnCl2 + Cl2 + H2O"), 20),
    "кривая титрования (60 точек)": (
        lambda: AB.titration_curve("CH3COOH", 0.1, 20.0, 0.1, points=60), 3),
    "равновесие фосфорной": (
        lambda: AB.solve_acid_base(
            [AB.AcidSystem("H3PO4", 0.1, [2.148, 7.198, 12.35])]), 10),
    "энтальпия сгорания": (
        lambda: TH.reaction_enthalpy("C6H6(ж) + 7.5O2 = 6CO2 + 3H2O(ж)"), 20),
    "выход по уравнению": (
        lambda: ST.theoretical_yield(
            "Fe2O3 + 3CO = 2Fe + 3CO2", 1.0, "Fe2O3", "Fe"), 50),
    "цепочка распада (3 звена)": (
        lambda: NUC.decay_chain(1000.0, [10.0, 3.0, 0.5], 50.0, "с"), 10),
    "осмотическое давление": (
        lambda: SOL.osmotic_pressure(0.1, i=2.0), 100),
    "идеальный газ": (
        lambda: GAS.ideal_gas(pressure=1, temperature=300, moles=1), 200),
}


def main() -> int:
    print(f"{'задача':30} {'повторов':>9} {'всего, мс':>11} {'на раз, мс':>11}")
    print("-" * 66)

    slowest = ("", 0.0)
    for name, (operation, repeats) in CASES.items():
        # прогрев: первый вызов включает кэши
        operation()
        start = time.perf_counter()
        for _ in range(repeats):
            operation()
        elapsed = (time.perf_counter() - start) * 1000
        per_call = elapsed / repeats
        print(f"{name:30} {repeats:9} {elapsed:11.1f} {per_call:11.2f}")
        if per_call > slowest[1]:
            slowest = (name, per_call)

    print("-" * 66)
    print(f"самое медленное: {slowest[0]} — {slowest[1]:.1f} мс на вызов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
