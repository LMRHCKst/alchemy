"""Коэффициенты активности по Питцеру.

Модель Дебая — Хюккеля в варианте Дэвиса перестаёт работать примерно
после 0.5 моль/кг: она не знает, что ионы бывают разного размера и
что они взаимодействуют друг с другом специфически. Питцер это
учитывает через параметры взаимодействия, полученные из опыта.

Формула для среднего коэффициента активности одного электролита
M(ν+)·X(ν−) при моляльности m:

    ln γ± = −|z+·z−|·Aφ·(√I/(1+b√I) + (2/b)·ln(1+b√I))
            + (2ν+ν−/ν)·m·B^γ
            + (2(ν+ν−)^{3/2}/ν)·m²·Cφ

где B^γ = 2β0 + (2β1/α1²I)·[1 − (1+α1√I − α1²I/2)e^{−α1√I}]
        + (2β2/α2²I)·[1 − (1+α2√I − α2²I/2)e^{−α2√I}]

Параметры β0, β1, β2, Cφ — из базы USGS pitzer.dat для PHREEQC,
которая ссылается на работы Питцера и соавторов. Значения проверены
сверкой со справочными коэффициентами (см. docs/activity_model.md).

Область применимости: до 2–6 моль/кг для 1:1, до 2 моль/кг для
2:1. Для 2:2 (MgSO₄) погрешность выше, потому что сильна ионная
ассоциация.
"""

from __future__ import annotations

import math

from ..core.errors import InputError
from ..core.results import Result, table_result

#: Aφ при 25 °C (кг/моль)^0.5
A_PHI = 0.3915

#: b — универсальный параметр Питцера
B_PITZER = 1.2

ALPHA1 = 2.0
ALPHA2 = 12.0

#: (катион, анион) -> (β0, β1, β2, Cφ)
PITZER_PARAMS: dict[tuple[str, str], tuple[float, float, float, float]] = {
    ("Na+", "Cl-"): (0.07534, 0.2769, 0.0, 0.00148),
    ("K+", "Cl-"): (0.04808, 0.2168, 0.0, -0.000788),
    ("Na+", "Br-"): (0.0973, 0.2791, 0.0, 0.00116),
    ("K+", "Br-"): (0.0569, 0.2212, 0.0, -0.0018),
    ("Ca2+", "Cl-"): (0.3159, 1.614, -1.13, 0.00014),
    ("Mg2+", "Cl-"): (0.351, 1.65, 0.0, 0.00651),
    ("Na+", "SO4^2-"): (0.0273, 0.956, 0.0, 0.003418),
    ("K+", "SO4^2-"): (0.0317, 0.756, 0.0, 0.00818),
    ("Mg2+", "SO4^2-"): (0.2135, 3.367, -32.45, 0.02875),
}

#: заряды ионов, которые встречаются в таблице
CHARGES = {
    "Na+": 1, "K+": 1, "Ca2+": 2, "Mg2+": 2, "H+": 1, "NH4+": 1,
    "Cl-": -1, "Br-": -1, "I-": -1, "NO3-": -1, "OH-": -1,
    "SO4^2-": -2, "CO3^2-": -2, "SO4-": -2, "CO3-": -2,
}

#: до какой моляльности модель сверена со справочными коэффициентами.
#: Сверка: NaCl 0.1/0.5/1/2 моль/кг — отклонение до 0.2 %;
#: KCl 0.1/1 — до 0.3 %. Остальные пары либо не сверялись, либо
#: расходятся сильнее, поэтому для них отдельный флаг.
VERIFIED = {
    ("Na+", "Cl-"): 2.0,
    ("K+", "Cl-"): 1.0,
}

#: 2:2 электролиты в этой реализации не считаются: для них нужен
#: вариант Питцера с α1 = 1.4 и учётом ассоциации, а без сверки
#: выдавать число — значит врать. MgSO4 при 0.1 моль/кг расходится
#: со справочником в 2.5 раза.
NOT_IMPLEMENTED = {("Mg+", "SO4^2-"), ("Mg2+", "SO4^2-")}

#: верхняя граница, до которой верим модели
LIMIT = {
    ("Na+", "Cl-"): 6.0,
    ("K+", "Cl-"): 4.5,
    ("Na+", "Br-"): 4.0,
    ("K+", "Br-"): 4.0,
    ("Ca2+", "Cl-"): 2.0,
    ("Mg2+", "Cl-"): 2.0,
    ("Na+", "SO4^2-"): 2.0,
    ("K+", "SO4^2-"): 1.0,
    ("Mg2+", "SO4^2-"): 3.0,
}


def _normalize_ion(name: str) -> str:
    """Привести запись иона к ключу таблицы."""
    text = str(name).strip().replace(" ", "")
    if text in CHARGES:
        return text
    # «SO4-2» и «SO4^2-» — одно и то же
    if text.endswith("2-") and "^" not in text:
        text = text[:-2] + "^2-"
    return text


def _charge(ion: str) -> int:
    if ion in CHARGES:
        return CHARGES[ion]
    raise InputError(f"Неизвестен заряд иона {ion}")


def available() -> list[str]:
    """Электролиты, для которых есть параметры."""
    return [f"{c}{a}" for c, a in PITZER_PARAMS]


def _b_gamma(params: tuple[float, float, float, float],
              ionic_strength: float) -> float:
    """B^γ — второй вириальный коэффициент с поправкой на ионные силы."""
    beta0, beta1, beta2, _cphi = params
    x1 = ALPHA1 * math.sqrt(ionic_strength)
    term1 = (2 * beta1 / (ALPHA1 ** 2 * ionic_strength)) * (
        1 - (1 + x1 - (ALPHA1 ** 2) * ionic_strength / 2) * math.exp(-x1))
    result = 2 * beta0 + term1
    if beta2:
        x2 = ALPHA2 * math.sqrt(ionic_strength)
        term2 = (2 * beta2 / (ALPHA2 ** 2 * ionic_strength)) * (
            1 - (1 + x2 - (ALPHA2 ** 2) * ionic_strength / 2) * math.exp(-x2))
        result += term2
    return result


def mean_activity_coefficient(cation: str, anion: str,
                              molality: float) -> float:
    """Средний коэффициент активности электролита по Питцеру."""
    cation = _normalize_ion(cation)
    anion = _normalize_ion(anion)
    if molality <= 0:
        raise InputError("Моляльность должна быть больше нуля")

    if (cation, anion) in NOT_IMPLEMENTED or (
            abs(_charge(cation)) == 2 and abs(_charge(anion)) == 2):
        raise InputError(
            f"Для {cation} + {anion} коэффициенты Питцера этим движком "
            f"не считаются: для электролитов 2:2 нужен вариант модели "
            f"с α₁ = 1.4 и учётом ионной ассоциации, а он не сверен "
            f"со справочными значениями. Возьмите модель Дэвиса — "
            f"она даст грубую оценку без обещания точности."
        )

    params = PITZER_PARAMS.get((cation, anion))
    if params is None:
        raise InputError(
            f"Для {cation} + {anion} нет параметров Питцера. "
            f"Доступны: {', '.join(available())}")

    z_cat = _charge(cation)
    z_an = abs(_charge(anion))
    nu_cat, nu_an = z_an, z_cat          # электронейтральность: ν+z+ = ν−|z−|
    nu = nu_cat + nu_an

    ionic_strength = 0.5 * molality * (nu_cat * z_cat ** 2 + nu_an * z_an ** 2)

    root = math.sqrt(ionic_strength)
    first = -abs(z_cat * z_an) * A_PHI * (
        root / (1 + B_PITZER * root) + (2 / B_PITZER) * math.log(1 + B_PITZER * root))

    second = (2 * nu_cat * nu_an / nu) * molality * _b_gamma(params,
                                                             ionic_strength)
    third = (2 * (nu_cat * nu_an) ** 1.5 / nu) * molality ** 2 * params[3]

    ln_gamma = first + second + third
    return math.exp(ln_gamma)


def ionic_strength_of(cation: str, anion: str, molality: float) -> float:
    """Ионная сила раствора одного электролита."""
    cation = _normalize_ion(cation)
    anion = _normalize_ion(anion)
    z_cat = _charge(cation)
    z_an = abs(_charge(anion))
    nu_cat, nu_an = z_an, z_cat
    return 0.5 * molality * (nu_cat * z_cat ** 2 + nu_an * z_an ** 2)


def Davies_gamma(charge: float, ionic_strength: float) -> float:
    """Коэффициент активности по Дэвису — для сравнения."""
    if ionic_strength <= 0:
        return 1.0
    root = math.sqrt(ionic_strength)
    log10_gamma = (-0.51 * charge ** 2 *
                   (root / (1 + root) - 0.3 * ionic_strength))
    return 10.0 ** log10_gamma


def pitzer_gamma(cation: str, anion: str, molality: float) -> Result:
    """Коэффициент активности электролита по Питцеру."""
    gamma = mean_activity_coefficient(cation, anion, molality)
    ionic = ionic_strength_of(cation, anion, molality)
    params = PITZER_PARAMS[(_normalize_ion(cation), _normalize_ion(anion))]
    limit = LIMIT.get((_normalize_ion(cation), _normalize_ion(anion)), 2.0)

    res = Result(
        value=gamma,
        unit="",
        label=f"Средний коэффициент активности {cation}{anion}",
        method="Уравнение Питцера с параметрами взаимодействия ионов",
    )
    res.with_step(f"Моляльность: {molality:g} моль/кг")
    res.with_step(f"Ионная сила: I = {ionic:.4f} моль/кг")
    res.with_step(f"Параметры: β⁰ = {params[0]}, β¹ = {params[1]}, "
                  f"β² = {params[2]}, Cφ = {params[3]}")
    res.with_step(f"γ± = {gamma:.4f}")
    res.with_meta("ionic_strength", ionic)
    res.with_meta("limit", limit)
    res.with_meta("electrolyte", f"{cation}{anion}")

    verified = VERIFIED.get((_normalize_ion(cation), _normalize_ion(anion)))
    if verified is None:
        res.with_warning(
            f"Параметры для {cation}{anion} взяты из базы, но этот движок "
            f"не сверял их со справочными коэффициентами: число может "
            f"расходиться на проценты. Для NaCl и KCl сверка есть.")
    elif molality > verified:
        res.with_warning(
            f"Моляльность {molality:g} выше сверенной области "
            f"({verified:g} моль/кг): дальше параметры работают, но "
            f"проверки не было.")

    if molality > limit:
        res.with_warning(
            f"Моляльность {molality:g} выше обычной области параметров "
            f"({limit:g} моль/кг): экстраполяция.")
    res.with_source("USGS pitzer.dat (PHREEQC), Pitzer K.S. и соавторы")
    return res


def model_comparison(cation: str, anion: str, molality: float) -> Result:
    """Сравнить три модели активности на одном растворе."""
    gamma = mean_activity_coefficient(cation, anion, molality)
    ionic = ionic_strength_of(cation, anion, molality)
    charge = max(abs(_charge(_normalize_ion(cation))),
                 abs(_charge(_normalize_ion(anion))))

    davies = Davies_gamma(charge, ionic)
    limiting = 10.0 ** (-0.51 * charge ** 2 * math.sqrt(ionic))

    rows = [
        {"Модель": "предельный закон", "γ": round(limiting, 4),
         "Отличие от Питцера, %": round((limiting / gamma - 1) * 100, 1)},
        {"Модель": "Дэвис", "γ": round(davies, 4),
         "Отличие от Питцера, %": round((davies / gamma - 1) * 100, 1)},
        {"Модель": "Питцер", "γ": round(gamma, 4), "Отличие от Питцера, %": 0.0},
    ]

    res = table_result(
        rows,
        label=f"Сравнение моделей активности: {cation}{anion}",
        columns=["Модель", "γ", "Отличие от Питцера, %"],
    )
    res.method = "Предельный закон, Дэвис и Питцер при одной ионной силе"
    res.with_step(f"Моляльность {molality:g} моль/кг, I = {ionic:.4f}")
    res.with_meta("ionic_strength", ionic)
    res.with_source("USGS pitzer.dat (PHREEQC)")
    return res
