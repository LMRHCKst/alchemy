# -*- coding: utf-8 -*-
"""Сверка наших коэффициентов активности с pyEQL (модель Питцера).

Сравниваем средний ионный коэффициент γ± на одинаковой ионной силе:
pyEQL считает по моляльности, мы — по ионной силе, взятой у него же.
Так видно разницу именно моделей, а не пересчёта единиц.

Запуск: python tools/compare_activity.py
"""

from __future__ import annotations

import io
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from alchemy.engines import acidbase as AB

try:
    from pyEQL import Solution
    HAVE_PYEQL = True
except Exception:
    HAVE_PYEQL = False

#: электролит -> (катион, анион, заряд катиона, заряд аниона,
#:                число катионов, число анионов)
SALTS = {
    "NaCl": ("Na+", "Cl-", 1, 1, 1, 1),
    "KCl": ("K+", "Cl-", 1, 1, 1, 1),
    "HCl": ("H+", "Cl-", 1, 1, 1, 1),
    "CaCl2": ("Ca+2", "Cl-", 2, 1, 1, 2),
    "Na2SO4": ("Na+", "SO4-2", 1, 2, 2, 1),
    "MgSO4": ("Mg+2", "SO4-2", 2, 2, 1, 1),
}

MOLALITIES = [0.1, 0.5, 1.0, 2.0]


def mean_gamma(gamma_cat: float, gamma_an: float,
               n_cat: int, n_an: int) -> float:
    """Средний ионный коэффициент: γ± = (γ₊^ν₊ · γ₋^ν₋)^(1/ν)."""
    total = n_cat + n_an
    return (gamma_cat ** n_cat * gamma_an ** n_an) ** (1.0 / total)


def ours(ionic: float, z_cat: int, z_an: int,
         n_cat: int, n_an: int) -> float:
    gamma_cat = AB.activity_coefficient(z_cat, ionic)
    gamma_an = AB.activity_coefficient(z_an, ionic)
    return mean_gamma(gamma_cat, gamma_an, n_cat, n_an)


def main() -> int:
    if not HAVE_PYEQL:
        print("pyEQL не установлен")
        return 1

    header = (f"{'электролит':10} {'моль/кг':>8} {'I':>6} "
              f"{'наш γ±':>8} {'Pitzer':>8} {'разница':>10}")
    print(header)
    print("-" * len(header))

    worst: list[tuple[str, float, float, float]] = []
    for name, (cation, anion, z_cat, z_an, n_cat, n_an) in SALTS.items():
        for molality in MOLALITIES:
            try:
                solution = Solution(
                    {cation: f"{molality} mol/kg",
                     anion: f"{molality * n_an / n_cat} mol/kg"},
                    temperature="25 degC")
                ionic = float(solution.ionic_strength.magnitude
                              if hasattr(solution.ionic_strength, "magnitude")
                              else solution.ionic_strength)
                gamma_cat = float(solution.get_activity_coefficient(cation))
                gamma_an = float(solution.get_activity_coefficient(anion))
            except Exception as exc:
                print(f"{name:10} {molality:8.1f}  ошибка: {type(exc).__name__}")
                continue

            gamma_pitzer = mean_gamma(gamma_cat, gamma_an, n_cat, n_an)
            gamma_ours = ours(ionic, z_cat, z_an, n_cat, n_an)
            deviation = (gamma_ours - gamma_pitzer) / gamma_pitzer * 100
            print(f"{name:10} {molality:8.1f} {ionic:6.2f} "
                  f"{gamma_ours:8.3f} {gamma_pitzer:8.3f} {deviation:+9.1f} %")
            worst.append((name, molality, gamma_ours, gamma_pitzer))
        print()

    if worst:
        name, molality, ours_value, pitzer_value = max(
            worst, key=lambda row: abs(row[2] - row[3]) / row[3])
        print(f"худшее расхождение: {name} {molality} моль/кг — "
              f"наш {ours_value:.3f}, Питцер {pitzer_value:.3f}")

    print()
    print("=== pH сильной кислоты: что видит человек ===")
    for concentration in (0.1, 0.5, 1.0, 2.0):
        ours_ph = AB.ph_of_acid("HCl", concentration,
                                include_activity=True).numeric()
        try:
            solution = Solution({"H+": f"{concentration} mol/kg",
                                 "Cl-": f"{concentration} mol/kg"},
                                temperature="25 degC")
            pitzer_ph = -math.log10(float(solution.get_activity("H+")))
        except Exception:
            pitzer_ph = float("nan")
        print(f"  HCl {concentration:4.1f} моль/кг: наш {ours_ph:6.3f}, "
              f"Питцер {pitzer_ph:6.3f}, разница {ours_ph - pitzer_ph:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
