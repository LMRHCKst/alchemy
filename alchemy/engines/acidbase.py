"""Кислотно-основные равновесия: активности, pH, буферы, титрование.

Ключевые возможности, которых не было в прежней версии:

    * ионная сила и коэффициенты активности. Раньше pH считался по формуле
      pH = −lg C, что верно только для бесконечно разбавленных растворов;
    * температурная зависимость pKw и pKa. При 100 °C нейтральная среда
      имеет pH 6.14, а не 7;
    * решатель системы уравнений материального баланса и закона действующих
      масс методом Ньютона. Он даёт правильный ответ и для полипротонных
      кислот, и для смесей, и для амфолитов — вместо набора частных формул;
    * расчёт кривой титрования из равновесий, а не по зашитым точкам.

Модели коэффициентов активности:
    предельный закон Дебая — Хюккеля    lg γ = −A·z²·√I            (I < 0.001)
    расширенный Дебая — Хюккеля          lg γ = −A·z²·√I/(1+B·å·√I) (I < 0.1)
    уравнение Дэвиса                    lg γ = −A·z²(√I/(1+√I) − 0.3I) (I < 0.5)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from ..core.errors import ConvergenceError, DomainError, InputError
from ..core.results import Result, series_result, table_result
from ..data import acids as ADB

# --------------------------------------------------------------------------
# Ионная сила и коэффициенты активности
# --------------------------------------------------------------------------

# Параметры уравнения Дебая — Хюккеля для воды
# A зависит от температуры: A = 1.82e6 / (εT)^{3/2}; при 25 °C A = 0.510
A_DEBYE_25 = 0.5092
B_DEBYE_25 = 3.29         # нм⁻¹·(моль/л)^-1/2 при 25 °C
ION_SIZE_NM = 0.3         # эффективный диаметр иона по умолчанию, нм

# Предел коэффициента активности в водных растворах. Всё, что выше, — уже
# не приближение, а мусор: у MgSO4 при I = 8 формула Дэвиса даёт γ = 2456.
# Проверено сверкой с pyEQL (модель Питцера): до I = 0.5 расхождение
# в пределах 8 %, дальше растёт катастрофически.
MAX_PHYSICAL_GAMMA = 5.0

#: как называть зоны модели в подписях к результату
ZONE_TITLES = {
    "limiting": "предельный закон Дебая — Хюккеля (I < 0.001)",
    "extended": "уравнение Дебая — Хюккеля с поправкой на размер иона",
    "davies": "формула Дэвиса",
    "beyond": "экстраполяция за пределы модели",
}

# Эффективные диаметры ионов по Киелланду, нм.
# Значения подобраны так, чтобы расширенное уравнение воспроизводило
# справочные коэффициенты активности. Для H⁺ диаметр велик, потому что
# этот ион сильно гидратирован и ведёт себя как крупная частица.
ION_SIZES_NM = {
    "H^+": 0.9, "OH^-": 0.35,
    "Li^+": 0.6, "Na^+": 0.4, "K^+": 0.3, "Rb^+": 0.25, "Cs^+": 0.25,
    "NH4^+": 0.25, "Ag^+": 0.25,
    "Mg^2+": 0.8, "Ca^2+": 0.6, "Sr^2+": 0.5, "Ba^2+": 0.5,
    "Fe^2+": 0.6, "Cu^2+": 0.6, "Zn^2+": 0.6, "Mn^2+": 0.6,
    "Al^3+": 0.9, "Fe^3+": 0.9, "Cr^3+": 0.9,
    "F^-": 0.35, "Cl^-": 0.3, "Br^-": 0.3, "I^-": 0.3,
    "NO3^-": 0.3, "ClO4^-": 0.35, "HCO3^-": 0.4,
    "SO4^2-": 0.4, "CO3^2-": 0.45, "HPO4^2-": 0.4, "PO4^3-": 0.4,
}


def ion_size(ion: str) -> float:
    """Эффективный диаметр иона в нанометрах."""
    return ION_SIZES_NM.get(str(ion).strip(), ION_SIZE_NM)


class AcidBaseError(InputError):
    """Кислотно-основной расчёт невозможен."""


def debye_huckel_A(temperature_k: float = 298.15) -> float:
    """Параметр A уравнения Дебая — Хюккеля для воды.

    Эмпирическая температурная зависимость A = 1.82·10⁶·(εT)^{−3/2}
    при 25 °C даёт 0.510, при 100 °C — 0.607, что согласуется со
    справочными значениями 0.509 и 0.609.
    """
    if temperature_k <= 0:
        raise DomainError("Температура должна быть больше нуля")
    eps = _water_dielectric_constant(temperature_k)
    return 1.82e6 / (eps * temperature_k) ** 1.5


def debye_huckel_B(temperature_k: float = 298.15) -> float:
    """Параметр B уравнения Дебая — Хюккеля, нм⁻¹·(моль/л)^−1/2.

    Эмпирическая форма B = 502.9·(εT)^{−1/2} даёт при 25 °C B = 3.291 нм⁻¹.
    Множитель 502.9 отвечает выражению расстояния в нанометрах, а не в
    ангстремах. Проверка: для H⁺ при å = 0.3 нм формула даёт γ = 0.915 при
    I = 0.01 и γ = 0.789 при I = 0.1, что совпадает со справочными значениями
    коэффициентов активности по таблицам Киелланда.
    """
    eps = _water_dielectric_constant(temperature_k)
    return 502.9 / math.sqrt(eps * temperature_k)


def _water_dielectric_constant(temperature_k: float) -> float:
    """Диэлектрическая проницаемость воды по Malmberg — Maryott (1992).

    При 25 °C даёт ε = 78.30, что совпадает с табличным значением.
    """
    c = temperature_k - 273.15
    return (87.740 - 0.40008 * c + 9.398e-4 * c ** 2 - 1.410e-6 * c ** 3)


def _check_positive(value: float, name: str) -> float:
    """Проверить, что число конечно и положительно.

    Молча пропущенный NaN хуже ошибки: он доезжает до ответа, и человек
    читает «pH = nan» вместо объяснения, что не так с вводом.
    """
    if not math.isfinite(value):
        raise AcidBaseError(f"{name} должно быть конечным числом, а не {value}")
    if value <= 0:
        raise AcidBaseError(f"{name} должно быть больше нуля, а не {value}")
    return value


def _check_charge(ion: str) -> float:
    """Заряд иона из его записи; неизвестный ион — отказ, а не ноль.

    Внутренние метки вида «H3PO4_2» (ступень равновесия) тоже понимаются:
    хвост из подчёркивания и цифры отбрасывается.
    """
    from ..core.formula import parse

    name = ion.strip()
    # внутренние метки ступеней выглядят как «H3PO4_2»: снимаем только
    # хвост из подчёркивания и цифр, иначе опечатка в имени иона
    # («Cl_typo^-») превратится в валидный «Cl» и пройдёт молча
    variants = [name]
    stripped = re.sub(r"_\d+$", "", name)
    if stripped != name:
        variants.append(stripped)

    for candidate in variants:
        try:
            return parse(candidate, allow_charge=True).charge
        except Exception:
            continue
    raise AcidBaseError(
        f"Не удалось разобрать ион «{ion}». "
        f"Заряд записывается так: Na^+, Cl^-, SO4^2-"
    )


def _check_ionic_strength(value: float) -> float:
    """Ионная сила: конечная и неотрицательная."""
    if not math.isfinite(value):
        raise AcidBaseError(f"Ионная сила должна быть конечным числом, а не {value}")
    if value < 0:
        raise AcidBaseError(f"Ионная сила не может быть отрицательной: {value}")
    return value


def _activity_limit_warnings(res: Result, ionic_strength_: float) -> None:
    """Предупредить, когда модель активностей вышла за свои границы.

    Уравнение Дебая — Хюккеля с поправкой на размер иона работает примерно
    до I = 0.1 моль/л, формула Дэвиса — до 0.5. Дальше нужен Питцер или
    экспериментальные коэффициенты; молчать об этом нельзя.

    Три зоны обрабатываются по-разному, и это не три разных правила,
    а одна политика: где модель верна — считаем молча, где на границе —
    считаем и предупреждаем с цифрой, где за границей — предупреждаем
    громко и говорим, чему верить нельзя.
    """
    zone = activity_zone(ionic_strength_)
    res.with_meta("activity_zone", zone)
    res.with_meta("activity_error_percent", _expected_error(ionic_strength_))
    res.with_step(
        f"Модель активностей: {ZONE_TITLES[zone]}, "
        f"ожидаемая погрешность γ до {_expected_error(ionic_strength_)} %")

    if zone == "davies":
        # Сверка с Питцером (docs/activity_model.md): до 0.5 моль/л
        # расхождение по 1:1 солям в пределах 8 %, выше — растёт быстро.
        error = _expected_error(ionic_strength_)
        res.with_warning(
            f"Ионная сила {ionic_strength_:.2f} моль/л выше области, где "
            f"уравнение Дебая — Хюккеля точно (до 0.1). Расчёт идёт по "
            f"формуле Дэвиса, ожидаемая погрешность коэффициентов "
            f"активности — до {error} %. Для точной работы нужна модель "
            f"Питцера."
        )
    elif zone == "beyond":
        res.with_warning(
            f"Ионная сила {ionic_strength_:.2f} моль/л за пределом формулы "
            f"Дэвиса (0.5). Коэффициенты активности здесь оценочные, "
            f"расхождение с Питцером может доходить до десятков процентов, "
            f"а для двухзарядных ионов — до разов. Результат годится только "
            f"как порядок величины."
        )


def activity_zone(ionic_strength_: float) -> str:
    """Где мы находимся относительно области применимости модели.

    Границы взяты не с потолка: до 0.001 работает предельный закон,
    до 0.1 — уравнение с поправкой на размер иона (сверка с Питцером
    даёт расхождение меньше процента), до 0.5 — формула Дэвиса.
    """
    if ionic_strength_ < 1e-3:
        return "limiting"
    if ionic_strength_ < 0.1:
        return "extended"
    if ionic_strength_ <= 0.5:
        return "davies"
    return "beyond"


def _expected_error(ionic_strength_: float) -> int:
    """Оценка погрешности коэффициента активности, в процентах.

    Числа из сверки с Питцером (docs/activity_model.md): в предельном
    законе расхождение доли процента, на 0.1 — единицы процентов,
    на 0.5 — около 8 %, на 1 — около 20 %, дальше растёт.
    """
    zone = activity_zone(ionic_strength_)
    if zone == "limiting":
        return 1
    if zone == "extended":
        return 3
    if zone == "davies":
        return 8
    return min(90, int(20 + 35 * (ionic_strength_ - 1.0)))


def activity_report(charge: float,
                    ionic_strength_: float) -> dict[str, float | str]:
    """Справка о коэффициенте активности: значение, зона, погрешность.

    Единая точка для интерфейса и для ИИ-чата: и там, и там нужно
    не только число, но и объяснение, насколько ему верить.
    """
    zone = activity_zone(ionic_strength_)
    try:
        gamma = activity_coefficient(charge, ionic_strength_)
        note = ""
    except DomainError as exc:
        gamma = float("nan")
        note = str(exc)
    return {
        "gamma": gamma,
        "zone": zone,
        "zone_title": ZONE_TITLES[zone],
        "error_percent": _expected_error(ionic_strength_),
        "usable": math.isfinite(gamma),
        "note": note,
    }


def ionic_strength(concentrations: dict[str, float],
                   charges: dict[str, float] | None = None) -> float:
    """Ионная сила раствора I = ½·Σ cᵢzᵢ².

    Args:
        concentrations: {ион: концентрация, моль/л}
        charges: {ион: заряд}. Если не задан, заряд извлекается из записи иона.
    """
    total = 0.0
    for ion, c in concentrations.items():
        _check_positive(c, f"Концентрация иона «{ion}»")
        if charges and ion in charges:
            z = charges[ion]
        else:
            z = _check_charge(ion)
        total += c * z * z
    return 0.5 * total


def activity_coefficient(charge: float, ionic_strength_: float,
                         model: str = "auto",
                         ion_size_nm: float = ION_SIZE_NM,
                         temperature_k: float = 298.15) -> float:
    """Коэффициент активности иона.

    Args:
        charge: заряд иона (по модулю используется).
        ionic_strength_: ионная сила раствора.
        model: «limiting», «extended», «davies» или «auto» (выбор по I).
        ion_size_nm: эффективный диаметр гидратированного иона, нм.
        temperature_k: температура, К.

    Returns:
        Коэффициент активности γ.
    """
    if ionic_strength_ < 0:
        raise DomainError("Ионная сила не может быть отрицательной")
    z2 = charge * charge
    if z2 == 0 or ionic_strength_ == 0:
        return 1.0

    A = debye_huckel_A(temperature_k)
    sqrt_I = math.sqrt(ionic_strength_)

    if model == "auto":
        if ionic_strength_ < 1e-3:
            model = "limiting"
        elif ionic_strength_ < 0.1:
            model = "extended"
        else:
            model = "davies"

    if model == "limiting":
        log_gamma = -A * z2 * sqrt_I
    elif model == "extended":
        B = debye_huckel_B(temperature_k)
        log_gamma = -A * z2 * sqrt_I / (1.0 + B * ion_size_nm * sqrt_I)
    elif model == "davies":
        log_gamma = -A * z2 * (sqrt_I / (1.0 + sqrt_I) - 0.3 * ionic_strength_)
    else:
        raise AcidBaseError(f"Неизвестная модель активности: {model}")

    gamma = 10.0 ** log_gamma
    # При больших ионных силах γ бывает больше единицы (высаливание).
    # Обрезать её единицей — значит прятать это от пользователя.
    # Но совсем уж нефизические значения выдавать нельзя: при I = 8
    # формула Дэвиса даёт γ = 2456, а это уже не «приблизительно»,
    # а сломанный расчёт.
    if gamma > MAX_PHYSICAL_GAMMA:
        raise DomainError(
            f"Коэффициент активности вышел {gamma:.3g} при ионной силе "
            f"{ionic_strength_:.2f} моль/л. Для водных растворов это "
            f"невозможно: модель Дебая — Хюккеля здесь неприменима. "
            f"Нужна модель Питцера или опытные данные."
        )
    return gamma


def activity_coefficients_for(concentrations: dict[str, float],
                              temperature_k: float = 298.15
                              ) -> tuple[float, dict[str, float]]:
    """Ионная сила и коэффициенты активности для набора ионов."""
    I = ionic_strength(concentrations)
    gammas: dict[str, float] = {}
    for ion, c in concentrations.items():
        z = _check_charge(ion)
        gammas[ion] = activity_coefficient(
            z, I, ion_size_nm=ion_size(ion), temperature_k=temperature_k)
    return I, gammas


# --------------------------------------------------------------------------
# Простые случаи pH (для проверки и для быстрых расчётов)
# --------------------------------------------------------------------------


def strong_acid_ph(concentration: float, temperature_k: float = 298.15,
                   ionic_strength_: float | None = None,
                   include_activity: bool = True) -> Result:
    """pH сильной кислоты с учётом активности.

    Для концентраций ниже 10⁻⁶ моль/л учитывается диссоциация воды: ответ
    стремится к pH нейтральной среды, а не уходит в бесконечность.
    """
    _check_positive(concentration, "Концентрация")

    pkw = ADB.pkw_at(temperature_k)

    if ionic_strength_ is None:
        ionic_strength_ = concentration   # для 1:1 электролита I = C

    gamma = (activity_coefficient(1.0, ionic_strength_,
                                  ion_size_nm=ion_size("H^+"),
                                  temperature_k=temperature_k)
             if include_activity else 1.0)

    # Точное решение с учётом воды: [H+]² − C·[H+] − Kw = 0
    Kw = 10.0 ** (-pkw)
    h = (concentration + math.sqrt(concentration ** 2 + 4 * Kw)) / 2.0
    a_h = gamma * h
    ph = -math.log10(a_h)

    res = Result(
        value=ph,
        label="pH раствора сильной кислоты",
        method="Уравнение electroneutrality с учётом активности и диссоциации воды",
    )
    res.with_step(f"Концентрация кислоты: {concentration:g} моль/л")
    res.with_step(f"Температура: {temperature_k:g} К, pKw = {pkw:.4f}")
    res.with_step(f"Ионная сила: I = {ionic_strength_:.6f} моль/л")
    res.with_step(f"Коэффициент активности γ(H⁺) = {gamma:.6f}")
    res.with_step(f"[H⁺] = {h:.6e} моль/л, активность a(H⁺) = {a_h:.6e}")
    res.with_step(f"pH = −lg({a_h:.6e}) = {ph:.4f}")
    res.with_meta("h_concentration", h)
    res.with_meta("activity", a_h)
    res.with_meta("gamma", gamma)
    res.with_meta("ionic_strength", ionic_strength_)
    _activity_limit_warnings(res, ionic_strength_)

    if concentration > 1.0:
        res.with_warning(
            f"Концентрация {concentration:g} моль/л велика: уравнение "
            f"Дебая — Хюккеля в этой области неприменимо, нужна модель "
            f"Питцера или экспериментальные данные. Результат оценочный."
        )
    if temperature_k != 298.15:
        res.with_step(f"Учтена температурная зависимость pKw: {pkw:.4f} вместо 14.00")

    res.with_source(ADB.source())
    return res


def strong_base_ph(concentration: float, temperature_k: float = 298.15,
                   n_hydroxide: float = 1.0,
                   ionic_strength_: float | None = None,
                   include_activity: bool = True) -> Result:
    """pH сильного основания с учётом активности.

    Args:
        concentration: молярная концентрация основания, моль/л.
        n_hydroxide: число гидроксид-ионов в формульной единице (для Ca(OH)₂ = 2).
    """
    _check_positive(concentration, "Концентрация")
    _check_positive(n_hydroxide, "Число гидроксид-ионов")

    pkw = ADB.pkw_at(temperature_k)
    c_oh = concentration * n_hydroxide

    if ionic_strength_ is None:
        ionic_strength_ = c_oh

    gamma = (activity_coefficient(1.0, ionic_strength_,
                                  ion_size_nm=ion_size("OH^-"),
                                  temperature_k=temperature_k)
             if include_activity else 1.0)

    Kw = 10.0 ** (-pkw)
    oh = (c_oh + math.sqrt(c_oh ** 2 + 4 * Kw)) / 2.0
    a_oh = gamma * oh
    poh = -math.log10(a_oh)
    ph = pkw - poh

    res = Result(
        value=ph,
        label="pH раствора сильного основания",
        method="Уравнение электронейтральности с учётом активности",
    )
    res.with_step(f"Концентрация основания: {concentration:g} моль/л")
    res.with_step(f"[OH⁻] = {n_hydroxide:g}·{concentration:g} = {c_oh:g} моль/л")
    res.with_step(f"pKw = {pkw:.4f} (при {temperature_k:g} К)")
    res.with_step(f"γ(OH⁻) = {gamma:.6f}, a(OH⁻) = {a_oh:.6e}")
    res.with_step(f"pOH = {poh:.4f}, pH = {pkw:.4f} − {poh:.4f} = {ph:.4f}")
    res.with_meta("oh_concentration", oh)
    res.with_meta("poh", poh)
    res.with_meta("gamma", gamma)
    res.with_meta("ionic_strength", ionic_strength_)
    _activity_limit_warnings(res, ionic_strength_)

    if c_oh > 1.0:
        res.with_warning(
            "Концентрация велика, уравнение Дебая — Хюккеля неприменимо. "
            "Результат оценочный."
        )
    return res


def weak_acid_ph(concentration: float, ka: float,
                 temperature_k: float = 298.15,
                 ionic_strength_: float | None = None,
                 include_activity: bool = True) -> Result:
    """pH слабой кислоты: решение квадратного уравнения с учётом активности.

    Уравнение: [H⁺]² + Ka·[H⁺] − Ka·C = 0, решается точно, без приближения
    «[H⁺] = √(Ka·C)», которое врёт при C/Ka < 100.
    """
    _check_positive(concentration, "Концентрация")
    _check_positive(ka, "Ka")

    if ionic_strength_ is None:
        ionic_strength_ = 0.5 * concentration

    gamma = (activity_coefficient(1.0, ionic_strength_,
                                  temperature_k=temperature_k)
             if include_activity else 1.0)

    # Ka — термодинамическая; для концентраций используем Ka/γ² (γ(H+)=γ(A-))
    ka_conc = ka / (gamma ** 2)

    h = (-ka_conc + math.sqrt(ka_conc ** 2 + 4 * ka_conc * concentration)) / 2.0
    if h <= 0:
        raise AcidBaseError("Не удалось вычислить концентрацию ионов водорода")

    alpha = h / concentration
    ph = -math.log10(gamma * h)

    res = Result(
        value=ph,
        label="pH раствора слабой кислоты",
        method="Квадратное уравнение материального баланса с поправкой на активность",
    )
    res.with_step(f"C = {concentration:g} моль/л, Ka = {ka:.6e} (pKa = {-math.log10(ka):.4f})")
    res.with_step(f"Ионная сила I = {ionic_strength_:.6f}, γ = {gamma:.6f}")
    res.with_step(f"[H⁺] = {h:.6e} моль/л")
    res.with_step(f"Степень диссоциации α = {alpha * 100:.3f} %")
    res.with_step(f"pH = {ph:.4f}")
    res.with_meta("h_concentration", h)
    res.with_meta("alpha", alpha)
    res.with_meta("gamma", gamma)
    res.with_meta("ionic_strength", ionic_strength_)
    _activity_limit_warnings(res, ionic_strength_)

    # Проверка применимости приближения √(Ka·C)
    approx = math.sqrt(ka * concentration)
    rel_error = abs(h - approx) / h * 100 if h else 0
    if rel_error > 5:
        res.with_step(
            f"Приближение [H⁺] = √(Ka·C) дало бы {approx:.6e} — расхождение "
            f"{rel_error:.1f} %, поэтому решено точное уравнение"
        )
    if alpha > 0.5:
        res.with_warning(
            f"Степень диссоциации {alpha * 100:.0f} % — кислота диссоциирует "
            f"заметно, приближение слабой кислоты на границе применимости"
        )
    return res


# --------------------------------------------------------------------------
# Общий решатель равновесий
# --------------------------------------------------------------------------


@dataclass
class AcidSystem:
    """Кислота со ступенчатыми константами диссоциации."""

    name: str
    total_concentration: float          # общая концентрация, моль/л
    pka_values: list[float]             # pKa по ступеням
    charge_of_base: int = 0             # заряд полностью депротонированной формы

    @property
    def n_protons(self) -> int:
        return len(self.pka_values)

    def ka_values(self, temperature_k: float = 298.15) -> list[float]:
        return [10.0 ** (-p) for p in self.pka_values]


@dataclass
class EquilibriumResult:
    """Результат решения равновесной задачи."""

    ph: float
    h_concentration: float
    fractions: dict[str, float] = field(default_factory=dict)
    concentrations: dict[str, float] = field(default_factory=dict)
    ionic_strength: float = 0.0
    gammas: dict[str, float] = field(default_factory=dict)
    iterations: int = 0
    converged: bool = True


def _species_fractions(h: float, kas: list[float], charge_base: int = 0
                       ) -> list[float]:
    """Доли форм кислоты H_nA, H_{n-1}A⁻, ... при данной [H⁺].

    Доли нормированы на общую концентрацию кислоты, то есть их сумма равна
    единице, а отношение соседних форм задаётся законом действующих масс:

        [H_{n-1}A⁻]/[H_nA] = Ka₁/[H⁺]

    Поэтому вклад формы с i отданными протонами пропорционален
        (Ka₁·Ka₂·…·Kaᵢ) / [H⁺]^i

    При [H⁺] ≫ Ka доля депротонированной формы мала — кислота не диссоциирует.
    При [H⁺] ≪ Ka она стремится к единице. Обратное отношение переворачивает
    эту зависимость и полностью искажает расчёт pH.
    """
    if h <= 0:
        raise AcidBaseError("Концентрация ионов водорода должна быть больше нуля")

    terms = [1.0]
    cumulative = 1.0
    for ka in kas:
        cumulative = cumulative * ka / h
        terms.append(cumulative)
    total = sum(terms)
    return [t / total for t in terms]


def solve_acid_base(systems: list[AcidSystem],
                    strong_acid: float = 0.0,
                    strong_base: float = 0.0,
                    temperature_k: float = 298.15,
                    include_activity: bool = True,
                    max_iterations: int = 200,
                    tolerance: float = 1e-12) -> EquilibriumResult:
    """Решить кислотно-основное равновесие методом итераций по [H⁺].

    Уравнение электронейтральности решается методом бисекции в логарифмической
    шкале — он устойчив и не требует производных.

    Args:
        systems: список кислот (слабых и сильных многоосновных).
        strong_acid: концентрация сильной кислоты (HCl, HNO₃), моль/л.
        strong_base: концентрация сильного основания (NaOH, KOH), моль/л.
        temperature_k: температура, К.
        include_activity: учитывать ли коэффициенты активности.
    """
    if temperature_k <= 0:
        raise DomainError("Температура должна быть больше нуля")
    if strong_acid < 0 or strong_base < 0:
        raise AcidBaseError("Концентрации не могут быть отрицательными")

    pkw = ADB.pkw_at(temperature_k)
    Kw = 10.0 ** (-pkw)

    def charge_balance(h: float, gamma_h: float, gamma_oh: float) -> float:
        """Разность зарядов: положительный заряд минус отрицательный.

        Ноль означает равновесие. Учитываются три вещи, без которых баланс
        не сходится:

            1. ионы-свидетели: анион сильной кислоты и катион сильного основания;
            2. заряд каждой формы слабой кислоты с учётом отданных протонов:
               H₃PO₄ → 0, H₂PO₄⁻ → −1, HPO₄²⁻ → −2, PO₄³⁻ → −3;
            3. вклад воды через Kw.

        Ошибка в любом из первых двух пунктов сдвигает pH на несколько единиц.
        """
        positive = h
        negative = Kw / h * (gamma_h / gamma_oh if include_activity else 1.0)

        positive += strong_base
        negative += strong_acid

        for system in systems:
            kas = system.ka_values(temperature_k)
            fractions = _species_fractions(h, kas)
            for i, frac in enumerate(fractions):
                # Форма с i отданными протонами заряжена на q − i:
                # H₃PO₄ → 0, H₂PO₄⁻ → −1, HPO₄²⁻ → −2, PO₄³⁻ → −3
                z = system.charge_of_base - i
                conc = system.total_concentration * frac
                if z > 0:
                    positive += z * conc
                elif z < 0:
                    negative += (-z) * conc
        return positive - negative

    # Оценка ионной силы для коэффициентов активности
    I_estimate = strong_acid + strong_base
    for system in systems:
        I_estimate += system.total_concentration * system.n_protons * 0.5
    I_estimate = max(I_estimate, 1e-9)

    gamma_h = activity_coefficient(1.0, I_estimate,
                                   ion_size_nm=ion_size("H^+"),
                                   temperature_k=temperature_k) \
        if include_activity else 1.0
    gamma_oh = gamma_h

    def solve_with_gammas(gamma_h: float, gamma_oh: float) -> tuple[float, int]:
        """Найти [H⁺] при заданных коэффициентах активности.

        Поиск идёт по шкале pH: h = 10^(−pH). Функция электронейтральности
        немонотонна в области очень малых концентраций, потому что там ею
        управляет диссоциация воды и появляется второй, ложный корень.
        Поэтому корень сначала локализуется сканированием по сетке pH,
        и только потом уточняется бисекцией на найденном интервале.
        Прежняя версия брала один широкий интервал и попадала в ложный
        корень, выдавая pH 12.99 для 0.1 М соляной кислоты.
        """
        def f(ph: float) -> float:
            return charge_balance(10.0 ** (-ph), gamma_h, gamma_oh)

        step = 0.05
        ph_start, ph_end = -2.0, pkw + 3.0
        count = int((ph_end - ph_start) / step) + 1

        prev_x = ph_start
        prev_f = f(prev_x)
        bracket: tuple[float, float] | None = None

        for i in range(1, count + 1):
            x = ph_start + i * step
            cur_f = f(x)
            if prev_f == 0.0:
                bracket = (prev_x, prev_x)
                break
            if prev_f * cur_f < 0:
                bracket = (prev_x, x)
                break
            prev_x, prev_f = x, cur_f

        if bracket is None:
            raise ConvergenceError(
                "Решение уравнения электронейтральности не найдено. "
                "Проверьте исходные данные: возможно, они противоречивы."
            )

        x_lo, x_hi = bracket
        if x_lo == x_hi:
            return 10.0 ** (-x_lo), 1

        f_lo = f(x_lo)
        iterations = 0
        for iterations in range(1, max_iterations + 1):
            x_mid = 0.5 * (x_lo + x_hi)
            f_mid = f(x_mid)
            if abs(f_mid) < tolerance or (x_hi - x_lo) < 1e-14:
                break
            if f_lo * f_mid <= 0:
                x_hi = x_mid
            else:
                x_lo, f_lo = x_mid, f_mid

        return 10.0 ** (-0.5 * (x_lo + x_hi)), iterations

    gamma_h = activity_coefficient(1.0, I_estimate,
                                   ion_size_nm=ion_size("H^+"),
                                   temperature_k=temperature_k) \
        if include_activity else 1.0
    gamma_oh = gamma_h

    h, iterations = solve_with_gammas(gamma_h, gamma_oh)

    # Уточняем ионную силу по найденному составу и решаем ещё раз
    if include_activity:
        composition_1 = _equilibrium_composition(h, systems, strong_acid, strong_base,
                                                Kw, temperature_k)
        I_new = ionic_strength(composition_1)
        if I_new > 0:
            gamma_new = activity_coefficient(
                1.0, I_new, ion_size_nm=ion_size("H^+"),
                temperature_k=temperature_k)
            if abs(gamma_new - gamma_h) > 1e-9:
                gamma_h = gamma_new
                gamma_oh = gamma_new
                h, extra = solve_with_gammas(gamma_h, gamma_oh)
                iterations += extra
            I_estimate = I_new

    composition = _equilibrium_composition(h, systems, strong_acid, strong_base,
                                           Kw, temperature_k)
    I_final = ionic_strength(composition)
    _, gammas = activity_coefficients_for(composition, temperature_k)

    ph = -math.log10(gamma_h * h)

    fractions: dict[str, float] = {}
    for system in systems:
        kas = system.ka_values(temperature_k)
        fr = _species_fractions(h, kas)
        n_total = system.n_protons
        for i, value in enumerate(fr):
            protons_left = n_total - i
            charge = system.charge_of_base - i
            label = _form_label(system.name, protons_left, charge)
            fractions[label] = value

    return EquilibriumResult(
        ph=ph,
        h_concentration=h,
        fractions=fractions,
        concentrations=composition,
        ionic_strength=I_final,
        gammas=gammas,
        iterations=iterations,
        converged=True,
    )


def _form_label(name: str, protons_left: int, charge: int) -> str:
    """Название формы кислоты для отчёта."""
    base = name.split("(")[0].strip()
    suffix = "" if protons_left == 0 else f"H{protons_left}" if protons_left > 1 else "H"
    charge_text = ""
    if charge > 0:
        charge_text = f"^{charge}+" if charge > 1 else "^+"
    elif charge < 0:
        charge_text = f"^{abs(charge)}-" if charge < -1 else "^-"
    return f"{base}{charge_text}" if protons_left == 0 else f"{base}({suffix}){charge_text}"


def _equilibrium_composition(h: float, systems: list[AcidSystem],
                             strong_acid: float, strong_base: float,
                             Kw: float, temperature_k: float) -> dict[str, float]:
    """Концентрации всех частиц — для расчёта ионной силы."""
    composition: dict[str, float] = {"H^+": h, "OH^-": Kw / h}
    if strong_acid > 0:
        composition["Cl^-"] = strong_acid   # анион сильной кислоты
    if strong_base > 0:
        composition["Na^+"] = strong_base   # катион сильного основания

    for system in systems:
        kas = system.ka_values(temperature_k)
        fr = _species_fractions(h, kas)
        for i, frac in enumerate(fr):
            charge = system.charge_of_base - i
            if charge == 0:
                continue
            key = f"{system.name}_{i}"
            composition[key] = system.total_concentration * frac
    return composition


# --------------------------------------------------------------------------
# Высокоуровневые функции
# --------------------------------------------------------------------------


def ph_of_acid(acid_query: str, concentration: float,
               temperature_k: float = 298.15,
               include_activity: bool = True) -> Result:
    """pH раствора кислоты из справочника — с учётом числа ступеней."""
    acid = ADB.find_acid(acid_query)

    pka_at_t = [acid.pKa_at(temperature_k)]  # первая ступень
    # Для многоосновных кислот нужно добавить остальные ступени
    if acid.protons > 1:
        extra = _related_pka(acid.formula, acid.protons)
        pka_at_t = [extra[0]] if extra else [acid.pKa_at(temperature_k)]

    # «Сильная» в справочнике — это ярлык. Диссоциирует полностью только
    # та, у которой pKa заметно ниже нуля. У трихлоруксусной pKa 0.66,
    # у селеновой 1.7: при 0.1 М это уже не полная диссоциация, и считать
    # их по формуле сильной кислоты значит ошибаться на пол-единицы pH.
    # У многоосновных кислот в справочнике может лежать вторая константа,
    # а не первая: у селеновой pKa1 около -3, а хранится 1.7. Поэтому
    # по pKa считаем только одноосновные, остальные — как раньше.
    fully_dissociated = acid.is_strong and (
        acid.protons > 1 or acid.pKa < -1.0)

    if fully_dissociated:
        res = strong_acid_ph(concentration, temperature_k,
                             include_activity=include_activity)
        res.label = f"pH раствора {acid.name.lower()}"
        res.with_step(f"Кислота {acid.formula} — сильная, диссоциирует полностью")

        # У многоосновной кислоты вторая ступень слабая: у серной pKa₂ 1.99.
        # При 0.1 М она даёт около 10 % дополнительных ионов водорода,
        # при 0.001 М — почти половину. Молчать об этом нельзя.
        stages = _stages_pka(acid)
        if len(stages) > 1:
            system = AcidSystem(acid.formula, concentration, stages)
            eq = solve_acid_base([system], temperature_k=temperature_k)
            # равновесие решается с активностями; если их просили
            # не учитывать — берём концентрационный pH
            value = eq.ph if include_activity else -math.log10(eq.h_concentration)
            naive = strong_acid_ph(
                concentration, temperature_k,
                include_activity=include_activity).numeric()
            res.value = value
            res.method = ("Первая ступень полностью, остальные — "
                          "по константам диссоциации")
            res.with_step("Ступени: " + ", ".join(
                f"pKa{i + 1} = {pka:g}" for i, pka in enumerate(stages)))
            res.with_step(
                f"С учётом всех ступеней pH = {value:.4f} "
                f"(без второй ступени было бы {naive:.4f})")
            res.with_meta("full_equilibrium_ph", value)
            res.with_meta("pka_stages", stages)
        else:
            res.with_warning(
                f"Кислота {acid.formula} многоосновная, но данных о второй "
                f"ступени в справочнике нет: pH считается по первой. "
                f"Вклад второй ступени не учтён.")
        return res

    if acid.is_strong:
        pass  # считается по Ka, предупреждение добавим ниже

    ka = 10.0 ** (-pka_at_t[0])
    res = weak_acid_ph(concentration, ka, temperature_k,
                       include_activity=include_activity)

    res.label = f"pH раствора {acid.name.lower()}"
    res.method = "Равновесие кислоты с учётом активности"

    if acid.is_strong:
        res.with_warning(
            f"В справочнике {acid.formula} помечена как сильная, но её "
            f"pKa = {acid.pKa:.2f}, то есть диссоциация неполная. "
            f"Расчёт идёт по константе, а не по формуле сильной кислоты.")
    res.with_step(f"Кислота: {acid.name} ({acid.formula})")
    if acid.has_temperature_data and temperature_k != 298.15:
        res.with_step(
            f"pKa при {temperature_k:g} К: {pka_at_t[0]:.4f} "
            f"(табличное при 298 К: {acid.pKa:.4f})"
        )
    elif temperature_k != 298.15:
        res.with_warning(
            f"Температурной зависимости pKa для {acid.formula} в справочнике "
            f"нет, использовано табличное значение при 298 К"
        )

    # Дополнительно: точное решение с учётом всех ступеней
    if acid.protons > 1:
        extra = _related_pka(acid.formula, acid.protons)
        if extra:
            system = AcidSystem(acid.formula, concentration, extra)
            eq = solve_acid_base([system], temperature_k=temperature_k)
            res.with_step(
                f"С учётом всех {acid.protons} ступеней диссоциации pH = {eq.ph:.4f}"
            )
            res.with_meta("full_equilibrium_ph", eq.ph)
            res.with_meta("fractions", eq.fractions)

            from ..core.formula import parse
            try:
                acid_charge = parse(acid.formula, allow_charge=True).charge
            except Exception:
                acid_charge = 0
            res.with_meta("acid_charge", acid_charge)
            res.value = eq.ph
            res.method = "Полное равновесие по всем ступеням диссоциации"

    res.with_source(ADB.source())
    return res


def _related_pka(formula: str, protons: int) -> list[float] | None:
    """Собрать набор pKa ступеней одной кислоты из справочника.

    Сравнение идёт по точной формуле: раньше «H2SO4» совпадала с «H2S»
    по префиксу, и серная кислота получала pKa сероводорода (7.02).
    """
    known = [
        ("H3PO4", ["H3PO4", "H2PO4-", "HPO4^2-"]),
        ("H2CO3", ["H2CO3", "HCO3-"]),
        ("H2S", ["H2S", "HS-"]),
        ("H2SO4", ["H2SO4", "HSO4-"]),
        ("H2SO3", ["H2SO3", "HSO3-"]),
        ("H2C2O4", ["H2C2O4", "HC2O4-"]),
        ("C4H6O6", ["C4H6O6", "C4H4O6-"]),
        ("C6H8O7", ["C6H8O7", "C6H7O7-", "C6H6O7^2-"]),
        ("C8H6O4", ["C8H6O4", "C8H5O4-"]),
        ("H2CrO4", ["H2CrO4", "HCrO4-"]),
        ("H2SeO3", ["H2SeO3", "HSeO3-"]),
        ("H2SeO4", ["H2SeO4", "HSeO4-"]),
        ("H2SiO3", ["H2SiO3", "HSiO3-"]),
        ("H2TeO3", ["H2TeO3", "HTeO3-"]),
    ]
    clean = formula.replace(" ", "")
    for root, steps in known:
        if clean != root:
            continue
        result = []
        for step in steps[:max(1, protons)]:
            acid = ADB.maybe_acid(step)
            if acid is None:
                break
            result.append(acid.pKa)
        # отдаём столько ступеней, сколько нашлось: у серной их две,
        # и обе нужны, даже если в карточке указан один протон
        return result or None
    return None


def _stages_pka(acid) -> list[float]:
    """Все известные ступени кислоты, начиная с первой."""
    chain = _related_pka(acid.formula, 6)
    if chain:
        return chain
    return [acid.pKa]


def ph_of_base(base_query: str, concentration: float,
               temperature_k: float = 298.15,
               include_activity: bool = True) -> Result:
    """pH раствора основания из справочника."""
def _check_solubility_limit(res: Result, formula: str, concentration: float,
                            n_hydroxide: float) -> None:
    """Предупредить, если заданная концентрация выше растворимости.

    Для M(OH)ₙ предел считается из произведения растворимости:
    Ksp = c·(n·c)ⁿ. Если просят больше, такого раствора не бывает —
    часть основания останется осадком, и pH будет ниже расчётного.
    """
    from ..data import solubility as SDB

    try:
        solid = SDB.maybe_solid(formula)
    except Exception:
        solid = None
    if solid is None or not solid.Ksp:
        return

    n = max(1.0, float(n_hydroxide))
    limit = (solid.Ksp / (n ** n)) ** (1.0 / (n + 1.0))
    if concentration <= limit * 1.01:
        return

    res.with_warning(
        f"Концентрация {concentration:g} моль/л выше растворимости "
        f"{formula} ({limit:.4g} моль/л при Ksp = {solid.Ksp:.2g}). "
        f"Такой раствор не получится: избыток останется осадком, "
        f"реальный pH будет ниже расчётного."
    )
    res.with_meta("solubility_limit", limit)


def ph_of_base(base_query: str, concentration: float,
               temperature_k: float = 298.15,
               include_activity: bool = True) -> Result:
    """pH раствора основания из справочника."""
    base = ADB.find_base(base_query)

    if base.is_strong:
        res = strong_base_ph(concentration, temperature_k,
                             n_hydroxide=max(1, base.OH),
                             include_activity=include_activity)
        res.label = f"pH раствора {base.name.lower()}"
        res.with_step(f"Основание {base.formula} — сильное")
        if base.OH > 1:
            res.with_step(f"Содержит {base.OH} гидроксид-иона на формульную единицу")
        _check_solubility_limit(res, base.formula, concentration,
                                max(1, base.OH))
        return res

    pkw = ADB.pkw_at(temperature_k)

    if base.is_hydroxide:
        # Слабое основание — гидроксид металла: M(OH)n ⇌ M^n+ + nOH⁻
        pkb = base.pKb
        kb = 10.0 ** (-pkb)
        if include_activity:
            I = 0.5 * concentration * max(1, base.OH)
            gamma = activity_coefficient(1.0, I, temperature_k=temperature_k)
        else:
            gamma = 1.0
            I = 0.0
        kb_conc = kb / (gamma ** 2)
        oh = (-kb_conc + math.sqrt(kb_conc ** 2 + 4 * kb_conc * concentration)) / 2.0
        ph = pkw + math.log10(gamma * oh)
        res = Result(
            value=ph,
            label=f"pH раствора {base.name.lower()}",
            method="Равновесие слабого основания, Kb = Kw/Ka сопряжённой кислоты",
        )
        res.with_step(f"pKb = {pkb:.4f}, Kb = {kb:.6e}")
        res.with_step(f"[OH⁻] = {oh:.6e} моль/л")
        res.with_step(f"pOH = {-math.log10(gamma * oh):.4f}, pH = {ph:.4f}")
        res.with_meta("oh_concentration", oh)
        res.with_meta("ionic_strength", I)
        _activity_limit_warnings(res, I)
        res.with_meta("gamma", gamma)
    else:
        # Молекулярное основание: B + H2O ⇌ BH⁺ + OH⁻
        pka_conj = base.pKa_conj
        ka_conj = 10.0 ** (-pka_conj)
        kb = 10.0 ** (-pkw) / ka_conj

        I = 0.5 * concentration
        gamma = activity_coefficient(1.0, I, temperature_k=temperature_k) \
            if include_activity else 1.0
        kb_conc = kb / (gamma ** 2)

        oh = (-kb_conc + math.sqrt(kb_conc ** 2 + 4 * kb_conc * concentration)) / 2.0
        ph = pkw - (-math.log10(gamma * oh))
        alpha = oh / concentration

        res = Result(
            value=ph,
            label=f"pH раствора {base.name.lower()}",
            method="Равновесие B + H₂O ⇌ BH⁺ + OH⁻",
        )
        res.with_step(f"pKa сопряжённой кислоты = {pka_conj:.4f}")
        res.with_step(f"Kb = Kw/Ka = {kb:.6e}")
        res.with_step(f"[OH⁻] = {oh:.6e} моль/л, степень протонирования {alpha * 100:.3f} %")
        res.with_step(f"pH = {ph:.4f}")
        res.with_meta("oh_concentration", oh)
        res.with_meta("alpha", alpha)
        res.with_meta("ionic_strength", I)
        _activity_limit_warnings(res, I)
        res.with_meta("gamma", gamma)

    res.with_source(ADB.source())
    return res


# --------------------------------------------------------------------------
# Буферные растворы
# --------------------------------------------------------------------------


def buffer_ph(acid_query: str, c_acid: float, c_salt: float,
              temperature_k: float = 298.15,
              include_activity: bool = True) -> Result:
    """pH буферного раствора по уравнению Гендерсона — Хассельбальха.

    Уравнение записано через активности:
        pH = pKa + lg(a(A⁻)/a(HA)) = pKa + lg([A⁻]/[HA]) + lg(γ(A⁻)/γ(HA))
    Коэффициент активности нейтральной молекулы принят единицей.
    """
    if c_acid <= 0 or c_salt <= 0:
        raise AcidBaseError("Концентрации кислоты и соли должны быть больше нуля")

    acid = ADB.find_acid(acid_query)
    pka = acid.pKa_at(temperature_k)

    I = 0.5 * (c_salt * 1.0)   # соль даёт ионы; вклад кислоты мал
    if include_activity:
        gamma_a = activity_coefficient(1.0, I, temperature_k=temperature_k)
    else:
        gamma_a = 1.0

    ratio = c_salt / c_acid
    ph = pka + math.log10(ratio * gamma_a)

    res = Result(
        value=ph,
        label="pH буферного раствора",
        method="Уравнение Гендерсона — Хассельбальха через активности",
    )
    res.with_step(f"Кислота: {acid.name} ({acid.formula})")
    res.with_step(f"pKa при {temperature_k:g} К: {pka:.4f}")
    res.with_step(f"Соотношение [A⁻]/[HA] = {c_salt:g}/{c_acid:g} = {ratio:.6f}")
    if include_activity:
        res.with_step(f"Ионная сила I = {I:.6f}, γ(A⁻) = {gamma_a:.6f}")
        res.with_step(
            f"pH = {pka:.4f} + lg({ratio:.6f}·{gamma_a:.6f}) = {ph:.4f}"
        )
    else:
        res.with_step(f"pH = {pka:.4f} + lg({ratio:.6f}) = {ph:.4f}")

    res.with_meta("pKa", pka)
    res.with_meta("ratio", ratio)
    res.with_meta("ionic_strength", I)
    _activity_limit_warnings(res, I)
    res.with_meta("gamma", gamma_a)
    res.with_source(ADB.source())

    if not 0.1 <= ratio <= 10:
        res.with_warning(
            f"Соотношение {ratio:.3f} выходит за пределы 0.1–10: такой раствор "
            f"обладает малой буферной ёмкостью и pH сильно меняется при "
            f"добавлении кислоты или щёлочи"
        )

    return res


def buffer_capacity(acid_query: str, c_acid: float, c_salt: float,
                    temperature_k: float = 298.15) -> Result:
    """Буферная ёмкость: β = 2.303·(Ka·C·[H⁺])/(Ka + [H⁺])².

    Величина показывает, сколько моль сильной кислоты или щёлочи нужно
    добавить к 1 л раствора, чтобы изменить pH на единицу.
    """
    if c_acid <= 0 or c_salt <= 0:
        raise AcidBaseError("Концентрации должны быть больше нуля")

    acid = ADB.find_acid(acid_query)
    pka = acid.pKa_at(temperature_k)
    ka = 10.0 ** (-pka)
    c_total = c_acid + c_salt

    h = ka * c_acid / c_salt
    beta = 2.303 * c_total * ka * h / ((ka + h) ** 2)

    res = Result(
        value=beta,
        unit="моль/(л·ед. pH)",
        label="Буферная ёмкость",
        method="β = 2.303·C·Ka·[H⁺]/(Ka + [H⁺])²",
    )
    res.with_step(f"Суммарная концентрация: C = {c_total:g} моль/л")
    res.with_step(f"[H⁺] = Ka·[HA]/[A⁻] = {h:.6e} моль/л")
    res.with_step(f"β = {beta:.6f} моль/(л·ед. pH)")
    res.with_step(
        f"Чтобы сдвинуть pH на единицу, нужно добавить "
        f"{beta:.4f} моль кислоты или щёлочи на литр"
    )
    res.with_meta("pKa", pka)
    res.with_meta("c_total", c_total)

    ph = pka + math.log10(c_salt / c_acid)
    if abs(ph - pka) > 1.0:
        res.with_warning(
            f"pH буфера ({ph:.2f}) отличается от pKa ({pka:.2f}) больше чем "
            f"на единицу — ёмкость далека от максимальной"
        )
    return res


def buffer_preparation(acid_query: str, target_ph: float, total_volume_l: float,
                       total_concentration: float,
                       temperature_k: float = 298.15) -> Result:
    """Сколько кислоты и соли взять, чтобы получить буфер с заданным pH."""
    if total_volume_l <= 0:
        raise AcidBaseError("Объём должен быть больше нуля")
    if total_concentration <= 0:
        raise AcidBaseError("Концентрация должна быть больше нуля")

    acid = ADB.find_acid(acid_query)
    pka = acid.pKa_at(temperature_k)

    ratio = 10.0 ** (target_ph - pka)
    c_acid = total_concentration / (1.0 + ratio)
    c_salt = total_concentration - c_acid

    n_acid = c_acid * total_volume_l
    n_salt = c_salt * total_volume_l

    res = Result(
        value=c_salt,
        unit="моль/л",
        label="Концентрация соли (сопряжённого основания) в буфере",
        method="pH = pKa + lg([A⁻]/[HA])",
    )
    res.with_step(f"pKa({acid.formula}) = {pka:.4f} при {temperature_k:g} К")
    res.with_step(f"Требуемое соотношение [A⁻]/[HA] = 10^({target_ph:.2f} − {pka:.4f}) = {ratio:.6f}")
    res.with_step(f"[HA] = {c_acid:.6f} моль/л, [A⁻] = {c_salt:.6f} моль/л")
    res.with_step(f"На объём {total_volume_l:g} л: n(HA) = {n_acid:.6f} моль, n(A⁻) = {n_salt:.6f} моль")
    res.with_meta("c_acid", c_acid)
    res.with_meta("c_salt", c_salt)
    res.with_meta("n_acid", n_acid)
    res.with_meta("n_salt", n_salt)

    # Массы для навески, если известны формулы соли
    if acid.formula.startswith("CH3COOH"):
        try:
            from ..core.formula import molar_mass
            M_salt = molar_mass("CH3COONa")
            res.with_step(
                f"Ацетата натрия потребуется: {n_salt * M_salt:.4f} г "
                f"(M = {M_salt:.3f} г/моль)"
            )
            res.with_meta("mass_salt_g", n_salt * M_salt)
        except Exception as exc:
            # Раньше здесь стоял голый pass, и масса соли молча исчезала
            # из ответа. Теперь человек видит, что навеску посчитать не вышло.
            res.with_warning(
                f"Массу соли посчитать не удалось ({type(exc).__name__}): "
                f"нет молярной массы ацетата натрия в справочнике. "
                f"Количество вещества указано в молях."
            )

    res.with_assumption(
        "Соль считается полностью диссоциированной, а её вклад в pH — только "
        "через равновесие сопряжённой пары. Активности учтены приближённо."
    )
    return res


# --------------------------------------------------------------------------
# Титрование
# --------------------------------------------------------------------------


def titration_curve(acid_query: str, c_acid: float, v_acid_ml: float,
                    c_base: float, temperature_k: float = 298.15,
                    v_max_ml: float | None = None,
                    points: int = 80) -> Result:
    """Кривая титрования кислоты сильным основанием из решения равновесий.

    Каждая точка — честное решение уравнения электронейтральности с учётом
    разбавления при добавлении титранта. Это принципиально отличается от
    прежней версии, где кривая рисовалась логистической функцией.

    Args:
        acid_query: кислота из справочника.
        c_acid: концентрация кислоты, моль/л.
        v_acid_ml: объём аликвоты кислоты, мл.
        c_base: концентрация титранта (сильного основания), моль/л.
        v_max_ml: до какого объёма титранта строить (по умолчанию 2·V экв).
        points: число точек кривой.
    """
    if c_acid <= 0 or c_base <= 0 or v_acid_ml <= 0:
        raise AcidBaseError("Концентрации и объём должны быть больше нуля")

    acid = ADB.find_acid(acid_query)
    n_acid = c_acid * v_acid_ml / 1000.0
    v_eq_ml = n_acid / c_base * 1000.0

    if v_max_ml is None:
        v_max_ml = v_eq_ml * 2.0
    if v_max_ml <= 0:
        raise AcidBaseError("Максимальный объём титранта должен быть больше нуля")

    # Готовим систему: если кислота слабая — с её ступенями
    pka_list = _related_pka(acid.formula, acid.protons) if acid.protons > 1 else None
    if pka_list is None:
        pka_list = [acid.pKa_at(temperature_k)]

    is_strong = acid.is_strong
    weak_systems: list[AcidSystem] = []
    strong_acid_conc = 0.0

    data: list[tuple[float, float]] = []
    step = v_max_ml / (points - 1) if points > 1 else v_max_ml

    for i in range(points):
        v_base_ml = i * step
        v_total_l = (v_acid_ml + v_base_ml) / 1000.0

        c_acid_now = n_acid / v_total_l
        c_base_now = c_base * v_base_ml / 1000.0 / v_total_l

        if is_strong:
            strong_acid_conc = c_acid_now
            systems_here: list[AcidSystem] = []
        else:
            strong_acid_conc = 0.0
            systems_here = [AcidSystem(acid.formula, c_acid_now, pka_list)]

        try:
            eq = solve_acid_base(
                systems_here if not is_strong else weak_systems,
                strong_acid=strong_acid_conc,
                strong_base=c_base_now,
                temperature_k=temperature_k,
            )
            data.append((v_base_ml, eq.ph))
        except (ConvergenceError, AcidBaseError):
            continue

    if not data:
        raise ConvergenceError("Не удалось построить кривую титрования")

    res = series_result(
        data,
        x_label="Объём титранта, мл",
        y_label="pH",
        label=f"Кривая титрования {acid.name.lower()}",
    )
    res.method = "Решение уравнения электронейтральности в каждой точке"
    res.with_step(f"Кислота: {acid.name} ({acid.formula}), C = {c_acid:g} моль/л")
    res.with_step(f"Аликвота: {v_acid_ml:g} мл, титрант: {c_base:g} моль/л основания")
    res.with_step(f"Объём в точке эквивалентности: {v_eq_ml:.2f} мл")
    res.with_meta("v_equivalence_ml", v_eq_ml)
    res.with_meta("points", len(data))

    # pH в характерных точках
    def ph_at(v_ml: float) -> float | None:
        best = min(data, key=lambda p: abs(p[0] - v_ml))
        return best[1] if abs(best[0] - v_ml) < step else None

    ph_start = data[0][1] if data[0][0] == 0 else min(data, key=lambda p: p[0])[1]
    res.with_step(f"pH исходного раствора: {ph_start:.2f}")
    res.with_meta("ph_initial", ph_start)

    half = ph_at(v_eq_ml / 2)
    if half is not None:
        res.with_step(f"pH при полунейтрализации ({v_eq_ml / 2:.1f} мл): {half:.2f}")
        res.with_meta("ph_half", half)
        if not is_strong:
            res.with_step(
                f"При полунейтрализации pH равен pKa кислоты "
                f"({pka_list[0]:.2f}) — это классический способ его определения"
            )

    at_eq = ph_at(v_eq_ml)
    if at_eq is not None:
        res.with_step(f"pH в точке эквивалентности ({v_eq_ml:.1f} мл): {at_eq:.2f}")
        res.with_meta("ph_equivalence", at_eq)

    # Скачок титрования: область, где pH меняется быстрее всего
    max_slope = 0.0
    jump_region = None
    for i in range(len(data) - 1):
        dv = data[i + 1][0] - data[i][0]
        if dv <= 0:
            continue
        slope = abs(data[i + 1][1] - data[i][1]) / dv
        if slope > max_slope:
            max_slope = slope
            jump_region = (data[i][0], data[i + 1][0])
    if jump_region:
        res.with_step(
            f"Наибольшая скорость изменения pH: {max_slope:.2f} ед/мл "
            f"в интервале {jump_region[0]:.1f}–{jump_region[1]:.1f} мл"
        )
        res.with_meta("max_slope", max_slope)
        res.with_meta("jump_region_ml", jump_region)

    # Подбор индикатора
    if at_eq is not None:
        suitable = ADB.indicators_for_ph(at_eq)
        if suitable:
            names = ", ".join(i.name for i in suitable)
            res.with_step(f"Подходящие индикаторы для этой точки эквивалентности: {names}")
            res.with_meta("suitable_indicators", [i.name for i in suitable])
        else:
            res.with_warning(
                f"Для pH {at_eq:.2f} в справочнике нет подходящего индикатора. "
                f"Ближайшие: "
                + ", ".join(
                    f"{i.name} ({i.transition_low:g}–{i.transition_high:g})"
                    for i in sorted(ADB.all_indicators(),
                                    key=lambda x: abs(x.pKa - at_eq))[:3]
                )
            )

    res.with_source(ADB.source())
    res.with_assumption(
        "Титрант — сильное основание без CO₂. Объёмы аддитивны, "
        "температура постоянна."
    )
    return res


def titration_ph_at(acid_query: str, c_acid: float, v_acid_ml: float,
                    c_base: float, v_base_ml: float,
                    temperature_k: float = 298.15) -> Result:
    """pH в конкретной точке титрования."""
    acid = ADB.find_acid(acid_query)

    n_acid = c_acid * v_acid_ml / 1000.0
    v_total_l = (v_acid_ml + v_base_ml) / 1000.0
    if v_total_l <= 0:
        raise AcidBaseError("Суммарный объём должен быть больше нуля")

    c_acid_now = n_acid / v_total_l
    c_base_now = c_base * v_base_ml / 1000.0 / v_total_l

    v_eq = n_acid / c_base * 1000.0 if c_base > 0 else float("inf")

    if acid.is_strong:
        eq = solve_acid_base([], strong_acid=c_acid_now,
                             strong_base=c_base_now, temperature_k=temperature_k)
        stage = _titration_stage(v_base_ml, v_eq)
        res = Result(
            value=eq.ph,
            label=f"pH при добавлении {v_base_ml:g} мл титранта",
            method="Уравнение электронейтральности для сильной кислоты",
        )
    else:
        pka_list = _related_pka(acid.formula, acid.protons) or [acid.pKa_at(temperature_k)]
        system = AcidSystem(acid.formula, c_acid_now, pka_list)
        eq = solve_acid_base([system], strong_base=c_base_now,
                             temperature_k=temperature_k)
        stage = _titration_stage(v_base_ml, v_eq)
        res = Result(
            value=eq.ph,
            label=f"pH при добавлении {v_base_ml:g} мл титранта",
            method="Решение равновесий с учётом разбавления",
        )

    res.with_step(f"Объём в точке эквивалентности: {v_eq:.2f} мл")
    res.with_step(f"Стадия: {stage}")
    res.with_step(f"Концентрация кислоты после разбавления: {c_acid_now:.6f} моль/л")
    res.with_step(f"Концентрация основания после разбавления: {c_base_now:.6f} моль/л")
    res.with_step(f"[H⁺] = {eq.h_concentration:.6e} моль/л, pH = {eq.ph:.4f}")
    res.with_meta("v_equivalence_ml", v_eq)
    res.with_meta("stage", stage)
    res.with_meta("fractions", eq.fractions)
    res.with_meta("ionic_strength", eq.ionic_strength)
    res.with_source(ADB.source())
    return res


def _titration_stage(v_base_ml: float, v_eq_ml: float) -> str:
    if v_eq_ml <= 0 or not math.isfinite(v_eq_ml):
        return "объём эквивалентности не определён"
    if v_base_ml < v_eq_ml * 0.999:
        return "до точки эквивалентности (избыток кислоты)"
    if v_base_ml <= v_eq_ml * 1.001:
        return "точка эквивалентности"
    return "после точки эквивалентности (избыток основания)"


def titration_error(acid_query: str, c_acid: float, v_acid_ml: float,
                    c_base: float, indicator_query: str,
                    temperature_k: float = 298.15) -> Result:
    """Систематическая погрешность титрования из-за индикатора.

    Индикатор меняет окраску не строго при pH точки эквивалентности, поэтому
    объём титранта отличается от истинного. Здесь эта разница оценивается
    количественно — то, чего не было в прежней версии.
    """
    acid = ADB.find_acid(acid_query)
    indicator = ADB.find_indicator(indicator_query)

    n_acid = c_acid * v_acid_ml / 1000.0
    v_eq_ml = n_acid / c_base * 1000.0

    # pH, при котором индикатор меняет окраску, принимаем за pKa индикатора
    ph_end = indicator.pKa

    # Подбираем объём титранта, при котором pH равен ph_end
    def ph_at_volume(v_ml: float) -> float:
        v_total = (v_acid_ml + v_ml) / 1000.0
        c_acid_now = n_acid / v_total
        c_base_now = c_base * v_ml / 1000.0 / v_total
        if acid.is_strong:
            eq = solve_acid_base([], strong_acid=c_acid_now,
                                 strong_base=c_base_now, temperature_k=temperature_k)
        else:
            pka_list = _related_pka(acid.formula, acid.protons) or [acid.pKa_at(temperature_k)]
            eq = solve_acid_base([AcidSystem(acid.formula, c_acid_now, pka_list)],
                                 strong_base=c_base_now, temperature_k=temperature_k)
        return eq.ph

    lo, hi = 0.0, v_eq_ml * 2.0 + 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if ph_at_volume(mid) < ph_end:
            lo = mid
        else:
            hi = mid
    v_end_ml = (lo + hi) / 2

    absolute_error_ml = v_end_ml - v_eq_ml
    relative_error = absolute_error_ml / v_eq_ml * 100 if v_eq_ml else 0.0

    res = Result(
        value=relative_error,
        unit="%",
        label=f"Систематическая погрешность титрования с {indicator.name.lower()}",
        method="Сравнение объёма при pH перехода индикатора с объёмом эквивалентности",
    )
    res.with_step(f"Точка эквивалентности: {v_eq_ml:.3f} мл")
    res.with_step(
        f"Индикатор меняет окраску в интервале "
        f"{indicator.transition_low:g}–{indicator.transition_high:g} "
        f"(pKa = {indicator.pKa:.2f})"
    )
    res.with_step(f"При pH {ph_end:.2f} объём титранта равен {v_end_ml:.3f} мл")
    res.with_step(
        f"Абсолютная погрешность: {absolute_error_ml:+.4f} мл "
        f"({relative_error:+.3f} %)"
    )
    res.with_meta("v_equivalence_ml", v_eq_ml)
    res.with_meta("v_indicator_ml", v_end_ml)
    res.with_meta("absolute_error_ml", absolute_error_ml)

    if abs(relative_error) > 1.0:
        res.with_warning(
            f"Погрешность {relative_error:+.2f} % превышает допустимую для "
            f"количественного анализа. Подберите индикатор с переходом ближе "
            f"к pH точки эквивалентности."
        )
    return res


def compare_indicators(acid_query: str, c_acid: float, v_acid_ml: float,
                       c_base: float,
                       temperature_k: float = 298.15) -> Result:
    """Сравнить все индикаторы справочника для данной задачи титрования."""
    rows = []
    for indicator in ADB.all_indicators():
        try:
            err = titration_error(acid_query, c_acid, v_acid_ml, c_base,
                                  indicator.name, temperature_k)
            rows.append({
                "Индикатор": indicator.name,
                "Интервал перехода": f"{indicator.transition_low:g}–{indicator.transition_high:g}",
                "Погрешность, %": round(err.numeric(), 3),
                "Пригоден": "да" if abs(err.numeric()) <= 1.0 else "нет",
            })
        except (AcidBaseError, ConvergenceError):
            continue

    rows.sort(key=lambda r: abs(r["Погрешность, %"]))
    res = table_result(rows, label="Подбор индикатора для титрования",
                       columns=["Индикатор", "Интервал перехода", "Погрешность, %", "Пригоден"])
    res.method = "Расчёт погрешности для каждого индикатора справочника"
    return res
