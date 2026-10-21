"""Ионные уравнения: молекулярное → полное ионное → сокращённое.

9 класс, ключевой навык. Правило одно: сильные электролиты пишутся
ионами, слабые, нерастворимые и газы — молекулами.

Сила электролита берётся из справочников: кислоты и основания из
`acids.json`, растворимость солей из `solubility.json`. Ничего не
угадывается по названию.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from ..core import formula as F
from ..core.errors import InputError
from ..core.results import Result
from ..data import acids as ADB
from ..data import solubility as SDB
from .balancer import balance

#: газы, которые в растворе остаются молекулами
GASES = {"CO2", "SO2", "SO3", "NH3", "H2S", "NO2", "NO", "Cl2", "H2",
         "O2", "N2", "F2", "Br2", "I2", "CH4", "C2H2", "O3"}

#: слабые электролиты, которые не диссоциируют
WEAK = {"H2O", "H2CO3", "H2SO3", "H2S", "H2SiO3", "H3PO4", "HNO2",
        "CH3COOH", "HF", "HClO", "H2C2O4", "C6H5OH", "NH3", "NH4OH",
        "H2SeO3", "H3BO3", "Al(OH)3", "Fe(OH)3", "Cu(OH)2", "Zn(OH)2",
        "Mg(OH)2"}

#: заряды катионов металлов, встречающихся в школе
CATION_CHARGES = {
    "Li": 1, "Na": 1, "K": 1, "Rb": 1, "Cs": 1, "Ag": 1, "H": 1,
    "Mg": 2, "Ca": 2, "Sr": 2, "Ba": 2, "Zn": 2, "Cd": 2, "Cu": 2,
    "Fe": 2, "Mn": 2, "Ni": 2, "Co": 2, "Sn": 2, "Pb": 2, "Hg": 2,
    "Al": 3, "Cr": 3, "Fe3": 3, "Bi": 3,
}

#: анионы: формула остатка -> запись иона. Ключи строятся из разбора,
#: поэтому порядок элементов в записи не важен.
_ANION_TABLE: list[tuple[str, str]] = [
    ("Cl", "Cl^-"), ("Br", "Br^-"), ("I", "I^-"), ("F", "F^-"),
    ("S", "S^2-"), ("O", "O^2-"), ("N", "N^3-"), ("P", "P^3-"),
    ("SO4", "SO4^2-"), ("SO3", "SO3^2-"), ("CO3", "CO3^2-"),
    ("NO2", "NO2^-"), ("NO3", "NO3^-"), ("PO4", "PO4^3-"),
    ("ClO3", "ClO3^-"), ("ClO4", "ClO4^-"), ("MnO4", "MnO4^-"),
    ("CrO4", "CrO4^2-"), ("Cr2O7", "Cr2O7^2-"), ("SiO3", "SiO3^2-"),
    ("CH3COO", "CH3COO^-"), ("HCO3", "HCO3^-"), ("HSO4", "HSO4^-"),
]


def _charge_of(ion: str) -> int:
    """Заряд из записи иона: «SO4^2-» -> -2, «Cl^-» -> -1."""
    match = re.search(r"\^(\d*)([+-])$", ion)
    if not match:
        return 0
    digits, sign = match.group(1), match.group(2)
    value = int(digits) if digits else 1
    return value if sign == "+" else -value


def _parts(composition: dict[str, float]) -> dict[str, float]:
    """Привести состав к целым числам."""
    return {element: round(amount, 6)
            for element, amount in composition.items() if amount > 0}


def _anion_of(counts: dict[str, float]) -> tuple[str, int, int] | None:
    """Определить анион: (запись иона, заряд, сколько таких групп).

    Остаток бывает умноженным: у Fe(NO3)3 в составе N3O9, а это
    три группы NO3. Поэтому остаток делится на кандидата.
    """
    clean = _parts(counts)
    if not clean:
        return None
    for formula, ion in _ANION_TABLE:
        group = _parts(F.parse(formula).counts)
        for multiplier in range(1, 9):
            scaled = {element: amount * multiplier
                      for element, amount in group.items()}
            if scaled == clean:
                return ion, _charge_of(ion), multiplier
    return None


def _cation_of(formula: str) -> tuple[str, int, int] | None:
    """Катион формулы: (символ, заряд, число).

    Заряд не берётся из таблицы вслепую: у железа он бывает 2+ и 3+.
    Считаем из баланса — по числу гидроксидов или по заряду аниона.
    """
    clean = F.split_state(formula)[0]
    counts = F.parse(clean).counts
    symbols = re.findall(r"[A-Z][a-z]?", clean)
    if not symbols:
        return None

    symbol = None
    for candidate in symbols:
        if candidate in CATION_CHARGES and candidate != "H":
            symbol = candidate
            break
    if symbol is None and "H" in counts:
        symbol = "H"
    if symbol is None:
        return None

    amount = int(counts.get(symbol, 1))

    # M(OH)n: заряд равен числу гидроксидов
    if "OH" in clean:
        charge = counts.get("O", amount)
        return symbol, max(1, int(round(charge / amount))), amount

    rest = dict(counts)
    rest.pop(symbol, None)
    anion = _anion_of(rest)
    if anion is not None:
        _ion, anion_charge, groups = anion
        total = abs(anion_charge) * groups
        if total % amount == 0:
            return symbol, total // amount, amount

    return symbol, CATION_CHARGES.get(symbol, 2), amount


def _is_strong_acid(formula: str) -> bool:
    try:
        acid = ADB.find_acid(formula)
    except Exception:
        return False
    return bool(getattr(acid, "is_strong", False)
                and (getattr(acid, "protons", 1) > 1 or acid.pKa < -1.0))


def _is_strong_base(formula: str) -> bool:
    if "OH" not in formula:
        return False
    if formula in WEAK:
        return False
    try:
        solid = SDB.maybe_solid(formula)
    except Exception:
        solid = None
    if solid is not None and solid.Ksp is not None:
        return solid.Ksp > 1e-3
    # гидроксиды щелочных и щёлочноземельных металлов растворимы
    cation = _cation_of(formula)
    if cation is None:
        return False
    return cation[0] in ("Li", "Na", "K", "Rb", "Cs", "Ca", "Sr", "Ba")


def _is_soluble_salt(formula: str) -> bool:
    if formula in WEAK or formula in GASES:
        return False
    if "OH" in formula:
        return _is_strong_base(formula)
    try:
        solid = SDB.maybe_solid(formula)
    except Exception:
        solid = None
    if solid is None:
        return True
    return bool(solid.Ksp is not None and solid.Ksp > 1e-4)


def dissociates(formula: str) -> bool:
    """Распадается ли вещество на ионы в растворе."""
    clean = F.split_state(formula)[0]
    if clean in WEAK or clean in GASES or clean == "H2O":
        return False

    # кислота
    try:
        ADB.find_acid(clean)
        return _is_strong_acid(clean)
    except Exception:
        pass

    if "OH" in clean:
        return _is_strong_base(clean)

    return _is_soluble_salt(clean)


def decompose(formula: str) -> Counter | None:
    """На какие ионы и в каком количестве распадается вещество.

    Возвращает Counter вида {'Na^+': 2, 'SO4^2-': 1} или None,
    если вещество записывается молекулой.
    """
    clean = F.split_state(formula)[0]
    if not dissociates(clean):
        return None

    counts = F.parse(clean).counts

    # соли аммония: NH4Cl, (NH4)2SO4, CH3COONH4
    if "NH4" in clean and "OH" not in clean:
        groups_nh4 = int(counts.get("N", 0))
        rest = dict(counts)
        rest["N"] = rest.get("N", 0) - groups_nh4
        rest["H"] = rest.get("H", 0) - 4 * groups_nh4
        if rest.get("N", 0) < 0 or rest.get("H", 0) < 0:
            return None
        rest = {element: amount for element, amount in rest.items()
                if amount > 0}
        if not rest:
            return None
        anion = _anion_of(rest)
        if anion is None:
            return None
        ion, _charge, groups = anion
        return Counter({"NH4^+": groups_nh4, ion: groups})

    # кислота: H⁺ и кислотный остаток
    if re.match(r"^H\d*[A-Z]", clean) and clean not in WEAK:
        protons = int(counts.get("H", 1))
        rest = dict(counts)
        rest.pop("H", None)
        anion = _anion_of(rest)
        if anion is None:
            return None
        ion, _charge, _groups = anion
        return Counter({"H^+": protons, ion: 1})

    # гидроксид: M(OH)n
    if "OH" in clean:
        cation = _cation_of(clean)
        if cation is None:
            return None
        symbol, charge, amount = cation
        return Counter({_ion_name(symbol, charge): amount,
                        "OH^-": int(counts.get("O", 1))})

    # соль: катион + кислотный остаток
    cation = _cation_of(clean)
    if cation is None:
        return None
    symbol, charge, amount = cation
    rest = dict(counts)
    rest.pop(symbol, None)
    anion = _anion_of(rest)
    if anion is None:
        return None
    ion, anion_charge, groups = anion
    return Counter({_ion_name(symbol, charge): amount, ion: groups})


def _ion_name(symbol: str, charge: int) -> str:
    """Запись иона: Na^+, Ca^2+, Al^3+ (единица не пишется)."""
    if charge == 1:
        return f"{symbol}^+"
    return f"{symbol}^{charge}+"


def _split_species(item: str) -> tuple[int, str]:
    """«2H2O» -> (2, «H2O»)."""
    text = item.strip()
    match = re.match(r"^(\d+)\s*(.+)$", text)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return 1, text


def _side(equation_side: str) -> Counter:
    """Разложить сторону уравнения на частицы с количеством."""
    particles: Counter = Counter()
    for item in equation_side.split("+"):
        coefficient, formula = _split_species(item)
        ions = decompose(formula)
        if ions is None:
            particles[F.split_state(formula)[0]] += coefficient
        else:
            for ion, amount in ions.items():
                particles[ion] += amount * coefficient
    return particles


def _reduce_pair(left: Counter, right: Counter) -> tuple[Counter, Counter]:
    """Сократить обе части уравнения на ОДИН общий делитель.

    Раньше каждая часть сокращалась отдельно, своим НОД. Из-за этого
    «2Al + 6HCl = 2AlCl3 + 3H2» превращалось в уравнение, где не сходились
    ни атомы, ни заряд: слева делили на 2, справа — на 1.
    """
    values = [int(amount) for amount in
              list(left.values()) + list(right.values()) if amount > 0]
    if not values:
        return left, right
    divisor = values[0]
    for value in values[1:]:
        divisor = math.gcd(divisor, value)
    if divisor <= 1:
        return left, right
    return (Counter({p: a // divisor for p, a in left.items() if a > 0}),
            Counter({p: a // divisor for p, a in right.items() if a > 0}))


def _reduce(particles: Counter) -> Counter:
    """Сократить коэффициенты на наибольший общий делитель."""
    values = [int(amount) for amount in particles.values() if amount > 0]
    if not values:
        return particles
    divisor = values[0]
    for value in values[1:]:
        divisor = math.gcd(divisor, value)
    if divisor <= 1:
        return particles
    return Counter({particle: amount // divisor
                    for particle, amount in particles.items() if amount > 0})


def _order_key(particle: str, molecules_first: bool) -> tuple[int, str]:
    """Порядок в записи.

    Слева молекулы идут первыми (Fe(OH)3 + 3H⁺), справа — наоборот,
    сначала ионы, потом вода и газы (Fe³⁺ + 3H2O).
    """
    if re.search(r"\^\d*\+$", particle):
        rank = 1
    elif re.search(r"\^\d*-$", particle):
        rank = 2
    else:
        rank = 0 if molecules_first else 3
    return (rank, particle)


def _render(particles: Counter, molecules_first: bool = True) -> str:
    """Собрать строку уравнения из частиц."""
    if not particles:
        return "—"
    chunks = []
    for particle in sorted(particles, key=lambda p: _order_key(p, molecules_first)):
        amount = particles[particle]
        chunks.append(particle if amount == 1 else f"{amount}{particle}")
    return " + ".join(chunks)


def _render_molecular(molecular: Counter) -> str:
    """Собрать молекулярную сторону."""
    if not molecular:
        return "—"
    chunks = []
    for formula, amount in molecular.items():
        chunks.append(formula if amount == 1 else f"{amount}{formula}")
    return " + ".join(chunks)


def ionic_equation(equation: str) -> Result:
    """Полное и сокращённое ионное уравнение.

    Args:
        equation: молекулярное уравнение, например «NaOH + HCl = NaCl + H2O».
    """
    if "=" not in equation and "→" not in equation:
        raise InputError("Нужно уравнение со знаком «=»")

    balanced = balance(equation).value
    left_text, right_text = balanced.split("→")

    left_molecular = Counter()
    right_molecular = Counter()
    for side_text, target in ((left_text, left_molecular),
                              (right_text, right_molecular)):
        for item in side_text.split("+"):
            coefficient, formula = _split_species(item)
            target[F.split_state(formula)[0]] += coefficient

    left_ions = _side(left_text)
    right_ions = _side(right_text)

    full = (f"{_render(left_ions, True)} = "
            f"{_render(right_ions, False)}")

    # сокращаем одинаковые ионы
    common = left_ions & right_ions
    for ion, amount in common.items():
        left_ions[ion] -= amount
        right_ions[ion] -= amount
    left_ions = +left_ions
    right_ions = +right_ions

    left_ions, right_ions = _reduce_pair(left_ions, right_ions)
    if not left_ions and not right_ions:
        net = "реакция идёт только в присутствии всех ионов, изменений нет"
    else:
        net = (f"{_render(left_ions, True)} = "
               f"{_render(right_ions, False)}")

    res = Result(
        value=net,
        unit="",
        label="Сокращённое ионное уравнение",
        method="Сильные электролиты записаны ионами, слабые — молекулами",
    )
    res.with_step(f"Молекулярное: {_render_molecular(left_molecular)} → "
                  f"{_render_molecular(right_molecular)}")
    res.with_step(f"Полное ионное: {full}")
    res.with_step(f"Сокращённое: {net}")

    for formula, _amount in list(left_molecular.items()) + \
            list(right_molecular.items()):
        note = "ионами" if decompose(formula) else "молекулой"
        res.with_step(f"{formula}: {note}")

    res.with_assumption(
        "Сильные электролиты считаются диссоциированными полностью. "
        "Слабые, малорастворимые и газы записаны молекулами."
    )
    res.with_source("Справочник растворимости и констант кислотности")
    return res
