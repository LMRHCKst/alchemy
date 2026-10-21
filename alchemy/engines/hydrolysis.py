"""Гидролиз солей: тип, среда, константа, степень, pH.

11 класс. Соль гидролизуется тем сильнее, чем слабее образующие её
кислота или основание. Считаем по константам из справочника, а где
константы нет — говорим честно, что количественно считать нечего.

Слабый катион или анион определяется не по названию, а по справочникам
`acids.json` и по таблице сильных оснований.
"""

from __future__ import annotations

import math
import re

from ..core import formula as F
from ..core.errors import InputError
from ..core.results import Result, table_result
from ..data import acids as ADB
from . import ioniceq

#: катионы, которые гидролизу не подвергаются (щёлочи и щёлочноземельные)
INERT_CATIONS = {"Li^+", "Na^+", "K^+", "Rb^+", "Cs^+", "Ca^2+",
                 "Sr^2+", "Ba^2+"}

#: анионы сильных кислот
INERT_ANIONS = {"Cl^-", "Br^-", "I^-", "NO3^-", "ClO4^-", "HSO4^-",
                "SO4^2-", "ClO3^-", "MnO4^-", "Cr2O7^2-"}

#: анион -> кислота, по которой берётся Ka.
#: У многоосновных кислот гидролиз идёт по последней ступени, поэтому
#: для карбоната нужна HCO3⁻, а не H2CO3.
CONJUGATE_ACIDS = {
    "CO3^2-": "HCO3-", "SO3^2-": "HSO3-", "S^2-": "HS-",
    "PO4^3-": "HPO4^2-", "SiO3^2-": "HSiO3-", "HCO3^-": "H2CO3",
    "CH3COO^-": "CH3COOH", "F^-": "HF", "NO2^-": "HNO2",
    "ClO^-": "HClO", "HSO3^-": "H2SO3", "HS^-": "H2S",
    "HPO4^2-": "H2PO4-", "C2O4^2-": "HC2O4-", "C6H5O^-": "C6H5OH",
}

#: катион -> основание, по которому берётся Kb
CONJUGATE_BASES = {
    "NH4^+": "NH3", "Fe^2+": "Fe(OH)2", "Fe^3+": "Fe(OH)3",
    "Cu^2+": "Cu(OH)2", "Zn^2+": "Zn(OH)2", "Al^3+": "Al(OH)3",
    "Mg^2+": "Mg(OH)2", "Ag^+": "AgOH", "Pb^2+": "Pb(OH)2",
    "CH3NH3^+": "CH3NH2", "C2H5NH3^+": "C2H5NH2",
}

KW_298 = 1.0e-14


def _split_salt(salt: str) -> tuple[str, str]:
    """Разложить соль на катион и анион через движок ионных уравнений."""
    ions = ioniceq.decompose(salt)
    if not ions:
        raise InputError(
            f"Не удалось разложить «{salt}» на ионы. Нужна растворимая соль, "
            f"например NaCl, Na2CO3, NH4Cl, CH3COONa."
        )
    cations = [ion for ion in ions if ion.endswith("+")]
    anions = [ion for ion in ions if ion.endswith("-")]
    if not cations or not anions:
        raise InputError(f"«{salt}» не похожа на соль: нет катиона или аниона")
    return cations[0], anions[0]


def _acid_ka(anion: str) -> tuple[float, str] | None:
    """Ka сопряжённой кислоты для аниона."""
    acid_name = CONJUGATE_ACIDS.get(anion)
    if acid_name is None:
        return None
    acid = ADB.maybe_acid(acid_name)
    if acid is None:
        return None
    return 10.0 ** (-acid.pKa), acid.formula


def _base_kb(cation: str) -> tuple[float, str] | None:
    """Kb сопряжённого основания для катиона."""
    base_name = CONJUGATE_BASES.get(cation)
    if base_name is None:
        return None
    base = ADB.maybe_base(base_name)
    if base is None or base.pKb is None:
        return None
    return 10.0 ** (-base.pKb), base.formula


def salt_type(salt: str) -> dict:
    """Определить тип гидролиза, не считая числа.

    Возвращает словарь: катион, анион, тип, среда, слабые стороны.
    """
    cation, anion = _split_salt(salt)

    cation_weak = cation not in INERT_CATIONS
    anion_weak = anion not in INERT_ANIONS

    if not cation_weak and not anion_weak:
        kind = "none"
        medium = "нейтральная"
    elif cation_weak and not anion_weak:
        kind = "cation"
        medium = "кислая"
    elif not cation_weak and anion_weak:
        kind = "anion"
        medium = "щелочная"
    else:
        kind = "both"
        medium = "зависит от силы кислоты и основания"

    return {
        "salt": F.split_state(salt)[0],
        "cation": cation,
        "anion": anion,
        "kind": kind,
        "medium": medium,
        "cation_weak": cation_weak,
        "anion_weak": anion_weak,
    }



#: ступени кислот для анионов: от сопряжённой кислоты к более протонированным
STAGE_PKA = {
    "CO3^2-": [10.33, 6.35],
    "PO4^3-": [12.35, 7.198, 2.148],
    "S^2-": [14.0, 7.02],
    "SO3^2-": [7.18, 1.9],
    "SiO3^2-": [9.8, 9.8],
    "C2O4^2-": [4.27, 1.25],
}


def hydrolysis_stages(salt: str, concentration: float = 0.1,
                      temperature_k: float = 298.15) -> Result:
    """Гидролиз по ступеням: каждая следующая подавлена предыдущей.

    Школьное правило: гидролиз идёт преимущественно по первой ступени.
    Здесь это не постулат, а число: у второй ступени Kh меньше на
    несколько порядков, и вклад в щёлочность падает вместе с ним.
    """
    if concentration <= 0:
        raise InputError("Концентрация должна быть больше нуля")

    info = salt_type(salt)
    anion = info["anion"]
    pkw = ADB.pkw_at(temperature_k)
    kw = 10.0 ** (-pkw)

    if not info["anion_weak"]:
        raise InputError(
            f"Анион {anion} — от сильной кислоты: гидролиза по аниону нет, "
            f"ступеней считать не из чего")

    stages = STAGE_PKA.get(anion) or []
    if not stages:
        raise InputError(
            f"Для аниона {anion} нет ступеней кислоты в справочнике")

    rows = []
    for index, pka in enumerate(stages, 1):
        ka = 10.0 ** (-pka)
        kh = kw / ka
        degree = math.sqrt(kh / concentration)
        rows.append({
            "Ступень": index,
            "pKa кислоты": pka,
            "Kh": f"{kh:.3e}",
            "Степень, %": round(degree * 100, 6),
            "Что образуется": _stage_product(anion, index),
        })

    res = table_result(
        rows,
        label=f"Гидролиз {info['salt']} по ступеням",
        columns=["Ступень", "pKa кислоты", "Kh", "Степень, %",
                 "Что образуется"])
    res.method = "Kh = Kw / Ka; h = √(Kh / C)"
    res.with_step(f"Концентрация соли: {concentration:g} моль/л")
    res.with_step(f"pKw при {temperature_k:g} К: {pkw:.4f}")
    res.with_step(
        "Каждая следующая ступень подавлена ионами OH⁻ от предыдущей, "
        "поэтому гидролиз практически идёт по первой")
    res.with_assumption(
        "Степень считается в приближении малой степени h = √(Kh/C): "
        "при h больше 10 % значение завышено.")
    res.with_source(ADB.source())
    return res


def _stage_product(anion: str, stage: int) -> str:
    """Что образуется на данной ступени гидролиза."""
    names = {
        "CO3^2-": ["HCO3⁻ (гидрокарбонат)", "H2CO3 (угольная кислота)"],
        "PO4^3-": ["HPO4^2⁻ (гидрофосфат)", "H2PO4⁻ (дигидрофосфат)",
                   "H3PO4 (фосфорная кислота)"],
        "S^2-": ["HS⁻ (гидросульфид)", "H2S (сероводород)"],
        "SO3^2-": ["HSO3⁻ (гидросульфит)", "H2SO3 (сернистая кислота)"],
        "SiO3^2-": ["HSiO3⁻ (гидросиликат)", "H2SiO3 (кремниевая кислота)"],
        "C2O4^2-": ["HC2O4⁻ (гидрооксалат)", "H2C2O4 (щавелевая кислота)"],
    }
    options = names.get(anion) or []
    return options[stage - 1] if stage <= len(options) else "—"


def hydrolysis(salt: str, concentration: float = 0.1,
               temperature_k: float = 298.15) -> Result:
    """Гидролиз соли: уравнение, тип, среда, константа, степень, pH."""
    if concentration <= 0:
        raise InputError("Концентрация должна быть больше нуля")

    info = salt_type(salt)
    kind = info["kind"]
    cation = info["cation"]
    anion = info["anion"]

    pkw = ADB.pkw_at(temperature_k)
    kw = 10.0 ** (-pkw)

    if kind == "none":
        res = Result(
            value="не гидролизуется",
            unit="",
            label="Гидролиз соли",
            method="Соль образована сильным основанием и сильной кислотой",
        )
        res.with_step(f"Катион {cation} — от сильного основания")
        res.with_step(f"Анион {anion} — от сильной кислоты")
        res.with_step("Среда нейтральная, гидролиз не идёт")
        res.with_meta("kind", kind)
        res.with_meta("medium", "нейтральная")
        return res

    # константы
    ka_data = _acid_ka(anion) if info["anion_weak"] else None
    kb_data = _base_kb(cation) if info["cation_weak"] else None

    res = Result(
        value=info["medium"],
        unit="",
        label="Гидролиз соли",
        method="Соль образована слабым электролитом, идёт гидролиз",
    )

    kh = None
    kh_note = ""
    if kind == "anion" and ka_data:
        kh = kw / ka_data[0]
        kh_note = f"Kh = Kw / Ka({ka_data[1]})"
    elif kind == "cation" and kb_data:
        kh = kw / kb_data[0]
        kh_note = f"Kh = Kw / Kb({kb_data[1]})"
    elif kind == "both" and ka_data and kb_data:
        # обе стороны слабые: pH почти не зависит от концентрации и равен
        # 7 + ½(pKa − pKb). Формула стандартная для школьного курса.
        pka = -math.log10(ka_data[0])
        pkb = -math.log10(kb_data[0])
        ph = 7.0 + 0.5 * (pka - pkb)
        res.with_step(f"Ka({ka_data[1]}) = {ka_data[0]:.3g} (pKa = {pka:.2f})")
        res.with_step(f"Kb({kb_data[1]}) = {kb_data[0]:.3g} (pKb = {pkb:.2f})")
        res.with_step(f"pH = 7 + ½(pKa − pKb) = {ph:.2f}")
        res.with_meta("ph", ph)
        res.with_meta("pka", pka)
        res.with_meta("pkb", pkb)
        medium = ("кислая" if ph < 6.5
                  else "щелочная" if ph > 7.5 else "близка к нейтральной")
        res.value = f"{medium}, pH {ph:.2f}"

    kind_text = {
        "cation": "по катиону",
        "anion": "по аниону",
        "both": "и по катиону, и по аниону",
    }[kind]
    res.with_step(f"Гидролиз {kind_text}")
    res.with_step(f"Катион {cation}: "
                  f"{'слабый' if info['cation_weak'] else 'от сильного основания'}")
    res.with_step(f"Анион {anion}: "
                  f"{'слабый' if info['anion_weak'] else 'от сильной кислоты'}")

    if kind == "anion" and ka_data:
        res.with_step(f"Сопряжённая кислота: {ka_data[1]}, "
                      f"Ka = {ka_data[0]:.3g}")
        res.with_step(f"{kh_note} = {kh:.3g}")
        degree = math.sqrt(kh / concentration)
        oh = math.sqrt(kh * concentration)
        ph = 14.0 - (-math.log10(oh)) if oh > 0 else 7.0
        res.with_step(f"Степень гидролиза h = √(Kh/C) = {degree * 100:.3f} %")
        res.with_step(f"[OH⁻] = √(Kh·C) = {oh:.3e} моль/л")
        res.with_step(f"pH = {ph:.2f}")
        res.with_meta("kh", kh)
        res.with_meta("degree", degree)
        res.with_meta("ph", ph)
        res.value = f"{info['medium']}, pH {ph:.2f}"

        stages = STAGE_PKA.get(anion) or []
        if len(stages) > 1:
            second_ka = 10.0 ** (-stages[1])
            second_kh = kw / second_ka
            second_degree = math.sqrt(second_kh / concentration)
            res.with_step(
                f"Вторая ступень: Kh = {second_kh:.3e}, "
                f"h = {second_degree * 100:.2e} % — "
                f"подавлена в {degree / second_degree:.0f} раз")
            res.with_meta("second_stage_degree", second_degree)
    elif kind == "cation" and kb_data:
        res.with_step(f"Сопряжённое основание: {kb_data[1]}, "
                      f"Kb = {kb_data[0]:.3g}")
        res.with_step(f"{kh_note} = {kh:.3g}")
        degree = math.sqrt(kh / concentration)
        h = math.sqrt(kh * concentration)
        ph = -math.log10(h) if h > 0 else 7.0
        res.with_step(f"Степень гидролиза h = √(Kh/C) = {degree * 100:.3f} %")
        res.with_step(f"[H⁺] = √(Kh·C) = {h:.3e} моль/л")
        res.with_step(f"pH = {ph:.2f}")
        res.with_meta("kh", kh)
        res.with_meta("degree", degree)
        res.with_meta("ph", ph)
        res.value = f"{info['medium']}, pH {ph:.2f}"
    else:
        res.with_warning(
            "Для этой соли нет константы слабого электролита в справочнике: "
            "тип гидролиза определён, а степень и pH не считаются. "
            "Среда указана качественно."
        )

    res.with_meta("kind", kind)
    res.with_meta("medium", info["medium"])
    res.with_assumption(
        "Степень гидролиза считается в приближении малой степени: "
        "h = √(Kh/C). При h больше 10 % результат завышен."
    )
    res.with_source(ADB.source())
    return res
