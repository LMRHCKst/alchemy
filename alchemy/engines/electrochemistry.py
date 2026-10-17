"""Электрохимия: Нернст, гальванические элементы, электролиз, диаграммы Пурбе.

Отличие от прежней версии: активности вместо концентраций, полная таблица
стандартных потенциалов, расчёт с произвольной температурой и pH, оценка
возможности коррозии. Расчёт потенциала через энергии Гиббса образования
позволяет перепроверить справочные данные независимым путём.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.constants import F_FARADAY, R
from ..core.errors import InputError
from ..core.results import Result, series_result, table_result
from ..data import electrodes as EDB

F_VALUE = F_FARADAY.value   # 96485.33212 Кл/моль
R_VALUE = R.value           # 8.314462618 Дж/(моль·К)

# Логарифм десятичный, а уравнение Нернста чаще пишут через десятичный логарифм
LN10 = math.log(10.0)


class ElectrochemistryError(InputError):
    """Электрохимический расчёт невозможен."""


# --------------------------------------------------------------------------
# Уравнение Нернста
# --------------------------------------------------------------------------


def nernst_potential(e0: float, n: int, temperature_k: float = 298.15,
                     oxidized: float | None = None,
                     reduced: float | None = None,
                     ph: float | None = None,
                     protons: int = 0) -> Result:
    """Потенциал электрода по уравнению Нернста.

    Для полуреакции Ox + n·e⁻ → Red:
        E = E° − (RT/nF)·ln(a(Red)/a(Ox))

    Важно: в числителе активности ВОССТАНОВЛЕННОЙ формы. Разбавление
    окисленной формы понижает потенциал, а не повышает — именно так
    и происходит на практике.

    Args:
        e0: стандартный потенциал, В.
        n: число электронов.
        temperature_k: температура, К.
        oxidized: активность окисленной формы.
        reduced: активность восстановленной формы (для твёрдых веществ 1).
        ph: pH раствора, если в полуреакции участвуют ионы H⁺.
        protons: число ионов H⁺ в полуреакции.
    """
    if n <= 0:
        raise ElectrochemistryError("Число электронов должно быть больше нуля")
    if temperature_k <= 0:
        raise ElectrochemistryError("Температура должна быть выше абсолютного нуля")

    if oxidized is None or reduced is None:
        raise ElectrochemistryError(
            "Задайте активности окисленной и восстановленной форм"
        )
    if oxidized <= 0 or reduced <= 0:
        raise ElectrochemistryError("Активности должны быть больше нуля")

    # Отношение a(Red)/a(Ox) — это и есть Q уравнения Нернста
    q = reduced / oxidized

    # Вклад pH: ионы H⁺ стоят в левой части полуреакции вместе с Ox,
    # поэтому их активность входит в числитель Q, то есть q делится на неё
    if ph is not None and protons:
        q /= 10.0 ** (-ph * protons)

    if q <= 0:
        raise ElectrochemistryError("Реакционная частность должна быть больше нуля")

    slope = R_VALUE * temperature_k / (n * F_VALUE)
    nernst_term = slope * math.log(q)
    potential = e0 - nernst_term

    res = Result(
        value=potential,
        unit="В",
        label="Потенциал электрода",
        method="Уравнение Нернста: E = E° − (RT/nF)·ln Q",
    )
    res.with_step(f"E° = {e0:+.4f} В, n = {n}")
    res.with_step(f"Температура: {temperature_k:g} К")
    res.with_step(
        f"Нернстовский коэффициент RT/(nF) = {R_VALUE:g}·{temperature_k:g}/"
        f"({n}·{F_VALUE:g}) = {slope:.6e} В"
    )
    if ph is not None and protons:
        res.with_step(f"Учтён вклад pH = {ph:g} при {protons} ионах H⁺ в полуреакции")
    res.with_step(f"Q = {q:.6e}, ln Q = {math.log(q):.6f}")
    res.with_step(f"E = {e0:+.4f} − {slope:.6e}·{math.log(q):.6f} = {potential:+.6f} В")

    res.with_meta("q", q)
    res.with_meta("nernst_slope", slope)
    res.with_meta("e0", e0)

    if temperature_k == 298.15:
        res.with_step(
            "При 25 °C удобно пользоваться формой E = E° − (0.0592/n)·lg Q"
        )
        res.with_meta("decimal_form_slope", 0.05916 / n)
    if abs(nernst_term) > 0.5:
        res.with_warning(
            f"Поправка Нернста ({nernst_term:+.3f} В) очень велика: потенциал "
            f"сильно отличается от стандартного. Это нормально для разбавленных "
            f"растворов, но проверьте, что активности заданы верно."
        )
    return res


def electrode_potential_electrode(identifier: str,
                                  concentration: float = 1.0,
                                  temperature_k: float = 298.15,
                                  ph: float | None = None) -> Result:
    """Потенциал полуреакции из справочника при заданной активности иона."""
    electrode = EDB.find(identifier)

    potential = nernst_potential(
        e0=electrode.E0, n=electrode.n, temperature_k=temperature_k,
        oxidized=concentration, reduced=1.0,
    )
    potential.label = f"Потенциал электрода {electrode.id}"
    potential.with_step(f"Полуреакция: {electrode.half_reaction}")
    potential.with_step(f"Активность окисленной формы: {concentration:g}")
    potential.with_source(EDB.source())

    if electrode.medium == "acid" and ph is not None:
        potential.with_warning(
            f"Полуреакция {electrode.id} протекает в кислой среде, но pH "
            f"не учтён в расчёте: для точного результата нужна полная "
            f"запись полуреакции с числом ионов H⁺"
        )
    return potential


# --------------------------------------------------------------------------
# Гальванический элемент
# --------------------------------------------------------------------------


@dataclass
class CellResult:
    """Результаты расчёта гальванического элемента."""

    emf: float
    e_cathode: float
    e_anode: float
    cathode: EDB.Electrode
    anode: EDB.Electrode
    n_electrons: int
    dG_kj: float
    K: float | None
    spontaneous: bool


def galvanic_cell(cathode: str, anode: str,
                  cathode_activity: float = 1.0,
                  anode_activity: float = 1.0,
                  temperature_k: float = 298.15) -> Result:
    """Собрать гальванический элемент из двух полуреакций и найти ЭДС.

    Катод — полуреакция с большим потенциалом, на нём идёт восстановление.
    Если переданные роли перепутаны, программа это заметит и предупредит:
    направление реакции определяется термодинамикой, а не порядком ввода.
    """
    cat = EDB.find(cathode)
    an = EDB.find(anode)

    if cat.id == an.id:
        raise ElectrochemistryError(
            "Катод и анод заданы одной и той же полуреакцией: элемент не соберётся"
        )

    if temperature_k <= 0:
        raise ElectrochemistryError("Температура должна быть выше абсолютного нуля")
    if cathode_activity <= 0 or anode_activity <= 0:
        raise ElectrochemistryError("Активности должны быть больше нуля")

    # Приводим полуреакции к общему числу электронов
    n = _lcm(cat.n, an.n)

    e_cat = nernst_potential(cat.E0, cat.n, temperature_k,
                             oxidized=cathode_activity, reduced=1.0).numeric()
    e_an = nernst_potential(an.E0, an.n, temperature_k,
                            oxidized=anode_activity, reduced=1.0).numeric()

    emf = e_cat - e_an
    n_electrons = n
    dG = -n_electrons * F_VALUE * emf / 1000.0

    K = None
    if abs(emf) > 0:
        exponent = n_electrons * F_VALUE * emf / (R_VALUE * temperature_k)
        if -700 < exponent < 700:
            K = math.exp(exponent)

    res = Result(
        value=emf,
        unit="В",
        label="ЭДС гальванического элемента",
        method="E = E(катод) − E(анод) с поправками Нернста",
    )
    res.with_step(f"Катод: {cat.half_reaction} (E° = {cat.E0:+.4f} В)")
    res.with_step(f"Анод:  {an.half_reaction} (E° = {an.E0:+.4f} В)")
    res.with_step(f"Общее число электронов: n = {n_electrons}")
    res.with_step(f"Потенциал катода: {e_cat:+.6f} В")
    res.with_step(f"Потенциал анода:  {e_an:+.6f} В")
    res.with_step(f"ЭДС = {e_cat:+.6f} − ({e_an:+.6f}) = {emf:+.6f} В")
    res.with_step(f"ΔG = −n·F·E = −{n_electrons}·{F_VALUE:g}·{emf:+.6f}/1000 = {dG:+.4f} кДж/моль")

    if K is not None:
        res.with_step(f"Константа равновесия K = exp(nFE/RT) = {K:.6e}")
        res.with_meta("K", K)
        if K > 1e5:
            res.with_step("K ≫ 1: реакция практически необратима в прямом направлении")

    res.with_meta("emf", emf)
    res.with_meta("e_cathode", e_cat)
    res.with_meta("e_anode", e_an)
    res.with_meta("n_electrons", n_electrons)
    res.with_meta("dG_kj", dG)
    res.with_meta("cathode", cat.id)
    res.with_meta("anode", an.id)
    res.with_source(EDB.source())

    if emf < 0:
        res.with_warning(
            f"ЭДС отрицательна: при таком подключении элемент работать не будет. "
            f"Поменяйте полюса — катодом должен быть электрод с большим "
            f"потенциалом ({' '.join(e.id for e in sorted([cat, an], key=lambda x: -x.E0))})"
        )
        res.with_step("Отрицательная ЭДС означает, что самопроизвольно реакция "
                      "пойдёт в обратную сторону")
    else:
        res.with_step("Положительная ЭДС: элемент работает самопроизвольно")

    if n != cat.n or n != an.n:
        res.with_assumption(
            f"Полуреакции приведены к общему числу электронов {n}: "
            f"{cat.id} (n={cat.n}) и {an.id} (n={an.n}). Потенциалы "
            f"полуреакций при этом не умножаются."
        )

    res.with_assumption(
        "Активности заданы для окисленных форм, активности твёрдых веществ "
        "приняты единице. Диффузионный потенциал и перенапряжение не учитываются."
    )
    return res


def _lcm(a: int, b: int) -> int:
    """Наименьшее общее кратное."""
    return abs(a * b) // math.gcd(a, b)


def compare_electrodes(element1: str, element2: str) -> Result:
    """Сравнить две полуреакции: пойдёт ли реакция между ними.

    Определяет, будет ли окисленная форма одной полуреакции окислять
    восстановленную форму другой.
    """
    e1 = EDB.find(element1)
    e2 = EDB.find(element2)

    emf = e1.E0 - e2.E0

    res = Result(
        value=emf,
        unit="В",
        label=f"Разность потенциалов {e1.id} и {e2.id}",
        method="E = E°₁ − E°₂",
    )
    res.with_step(f"{e1.half_reaction}  E° = {e1.E0:+.4f} В")
    res.with_step(f"{e2.half_reaction}  E° = {e2.E0:+.4f} В")
    res.with_step(f"Разность: {emf:+.4f} В")

    if emf > 0.1:
        res.with_step(
            f"Реакция возможна: окисленная форма {e1.id} окисляет "
            f"восстановленную форму {e2.id}"
        )
        res.with_meta("reaction_possible", True)
    elif emf < -0.1:
        res.with_step(
            f"Реакция идёт в обратном направлении: окисленная форма {e2.id} "
            f"окисляет восстановленную форму {e1.id}"
        )
        res.with_meta("reaction_possible", False)
    else:
        res.with_warning(
            f"Разность потенциалов всего {emf:+.4f} В — система близка "
            f"к равновесию, направление реакции зависит от концентраций. "
            f"Однозначный вывод сделать нельзя."
        )
        res.with_meta("reaction_possible", None)

    res.with_source(EDB.source())
    return res


def find_possible_oxidants(reductant: str, min_emf: float = 0.3) -> Result:
    """Подобрать окислители, способные окислить данную восстановленную форму."""
    target = EDB.find(reductant)

    rows = []
    for e in EDB.all_electrodes():
        if e.id == target.id:
            continue
        emf = e.E0 - target.E0
        if emf >= min_emf:
            rows.append({
                "Окислитель": e.id,
                "Полуреакция": e.half_reaction,
                "E°, В": round(e.E0, 4),
                "ЭДС, В": round(emf, 4),
            })

    if not rows:
        raise ElectrochemistryError(
            f"В справочнике нет окислителей с ЭДС не менее {min_emf:g} В "
            f"относительно {target.id}"
        )

    rows.sort(key=lambda r: -r["ЭДС, В"])
    res = table_result(rows, label=f"Окислители для {target.id}",
                       columns=["Окислитель", "Полуреакция", "E°, В", "ЭДС, В"])
    res.method = f"Отбор полуреакций с E° не менее чем на {min_emf:g} В выше {target.id}"
    res.with_step(f"Исходная полуреакция: {target.half_reaction}")
    res.with_step(f"E°({target.id}) = {target.E0:+.4f} В")
    res.with_step(f"Найдено подходящих окислителей: {len(rows)}")
    res.with_step(
        f"Самый сильный в списке: {rows[0]['Окислитель']} "
        f"(ЭДС {rows[0]['ЭДС, В']:+.4f} В)"
    )
    res.with_source(EDB.source())
    return res


def concentration_cell(electrode: str, c_dilute: float, c_concentrated: float,
                       temperature_k: float = 298.15) -> Result:
    """Концентрационный элемент: две полуреакции одного типа с разными активностями.

    ЭДС возникает только за счёт разности концентраций:
        E = (RT/nF)·ln(c(конц)/c(разб))
    """
    e = EDB.find(electrode)

    if c_dilute <= 0 or c_concentrated <= 0:
        raise ElectrochemistryError("Концентрации должны быть больше нуля")
    if c_dilute >= c_concentrated:
        raise ElectrochemistryError(
            "Концентрация в разбавленном растворе должна быть меньше, "
            "чем в концентрированном"
        )

    slope = R_VALUE * temperature_k / (e.n * F_VALUE)
    emf = slope * math.log(c_concentrated / c_dilute)

    res = Result(
        value=emf,
        unit="В",
        label=f"ЭДС концентрационного элемента {e.id}",
        method="E = (RT/nF)·ln(c₂/c₁)",
    )
    res.with_step(f"Полуреакция: {e.half_reaction}")
    res.with_step(f"Разбавленный раствор: {c_dilute:g} моль/л")
    res.with_step(f"Концентрированный раствор: {c_concentrated:g} моль/л")
    res.with_step(f"Отношение концентраций: {c_concentrated / c_dilute:.6g}")
    res.with_step(f"RT/(nF) = {slope:.6e} В")
    res.with_step(f"ЭДС = {emf:+.6f} В")
    res.with_meta("ratio", c_concentrated / c_dilute)
    res.with_source(EDB.source())
    res.with_assumption(
        "Активности заменены концентрациями. Для концентрированных растворов "
        "нужны коэффициенты активности, иначе ЭДС будет завышена."
    )
    return res


# --------------------------------------------------------------------------
# Электролиз и законы Фарадея
# --------------------------------------------------------------------------


def faraday_mass(current_a: float, time_s: float, n: int,
                 molar_mass_value: float, current_efficiency: float = 100.0) -> Result:
    """Масса вещества, выделившегося при электролизе.

    m = (I·t·M)/(n·F) · η/100

    Args:
        current_a: сила тока, А.
        time_s: время, с.
        n: число электронов на формульную единицу.
        molar_mass_value: молярная масса, г/моль.
        current_efficiency: выход по току, %.
    """
    if current_a <= 0:
        raise ElectrochemistryError("Сила тока должна быть больше нуля")
    if time_s < 0:
        raise ElectrochemistryError("Время не может быть отрицательным")
    if n <= 0:
        raise ElectrochemistryError("Число электронов должно быть больше нуля")
    if molar_mass_value <= 0:
        raise ElectrochemistryError("Молярная масса должна быть больше нуля")
    if not 0 < current_efficiency <= 100:
        raise ElectrochemistryError("Выход по току должен быть от 0 до 100 %")

    charge = current_a * time_s
    mass_theoretical = charge * molar_mass_value / (n * F_VALUE)
    mass = mass_theoretical * current_efficiency / 100.0

    res = Result(
        value=mass,
        unit="г",
        label="Масса вещества при электролизе",
        method="m = I·t·M/(n·F), с поправкой на выход по току",
    )
    res.with_step(f"Заряд: Q = I·t = {current_a:g}·{time_s:g} = {charge:.4f} Кл")
    res.with_step(
        f"Количество эквивалентов: Q/F = {charge:.4f}/{F_VALUE:g} "
        f"= {charge / F_VALUE:.6e} моль"
    )
    res.with_step(
        f"m(теоретическая) = {charge:.4f}·{molar_mass_value:.4f}/"
        f"({n}·{F_VALUE:g}) = {mass_theoretical:.6f} г"
    )
    if current_efficiency != 100.0:
        res.with_step(
            f"С учётом выхода по току {current_efficiency:g} %: "
            f"{mass_theoretical:.6f}·{current_efficiency / 100:g} = {mass:.6f} г"
        )
    res.with_meta("charge_c", charge)
    res.with_meta("mass_theoretical", mass_theoretical)
    res.with_meta("moles_electrons", charge / F_VALUE)
    res.with_meta("moles_substance", charge / (n * F_VALUE))
    res.with_source(F_FARADAY.pretty())
    return res


def faraday_volume(current_a: float, time_s: float, n: int,
                   temperature_k: float = 298.15, pressure_atm: float = 1.0,
                   current_efficiency: float = 100.0) -> Result:
    """Объём газа, выделившегося при электролизе."""
    if current_a <= 0 or time_s < 0:
        raise ElectrochemistryError("Ток и время заданы неверно")
    if n <= 0:
        raise ElectrochemistryError("Число электронов должно быть больше нуля")
    if temperature_k <= 0 or pressure_atm <= 0:
        raise ElectrochemistryError("Температура и давление должны быть больше нуля")
    if not 0 < current_efficiency <= 100:
        raise ElectrochemistryError("Выход по току должен быть от 0 до 100 %")

    R_atm = 0.082057366
    charge = current_a * time_s
    n_gas = charge / (n * F_VALUE) * current_efficiency / 100.0
    volume = n_gas * R_atm * temperature_k / pressure_atm

    res = Result(
        value=volume,
        unit="л",
        label="Объём газа при электролизе",
        method="n = Q/(n·F), затем V = nRT/P",
    )
    res.with_step(f"Заряд: {charge:.4f} Кл")
    res.with_step(f"Количество газа: {n_gas:.6e} моль")
    res.with_step(
        f"Объём при {temperature_k:g} К и {pressure_atm:g} атм: {volume:.6f} л"
    )
    res.with_step(
        f"При нормальных условиях это было бы {n_gas * 22.414:.6f} л"
    )
    res.with_meta("moles_gas", n_gas)
    res.with_meta("volume_stp_l", n_gas * 22.414)
    return res


def electrolysis_time(current_a: float, n: int, moles: float | None = None,
                      mass_g: float | None = None,
                      molar_mass_value: float | None = None) -> Result:
    """Время электролиза для получения заданного количества вещества."""
    if current_a <= 0:
        raise ElectrochemistryError("Сила тока должна быть больше нуля")
    if n <= 0:
        raise ElectrochemistryError("Число электронов должно быть больше нуля")

    if moles is None:
        if mass_g is None or molar_mass_value is None or molar_mass_value <= 0:
            raise ElectrochemistryError(
                "Задайте либо количество вещества в молях, либо массу "
                "вместе с молярной массой"
            )
        moles = mass_g / molar_mass_value

    if moles <= 0:
        raise ElectrochemistryError("Количество вещества должно быть больше нуля")

    charge = moles * n * F_VALUE
    time_s = charge / current_a

    res = Result(
        value=time_s,
        unit="с",
        label="Время электролиза",
        method="t = n·z·F/I",
    )
    res.with_step(f"Количество вещества: {moles:.6f} моль")
    res.with_step(f"Число электронов на частицу: {n}")
    res.with_step(f"Требуемый заряд: {moles:.6f}·{n}·{F_VALUE:g} = {charge:.4f} Кл")
    res.with_step(f"Время: {time_s:.4f} с = {time_s / 60:.4f} мин = {time_s / 3600:.4f} ч")
    res.with_meta("charge_c", charge)
    res.with_meta("time_h", time_s / 3600)
    res.with_assumption(
        "Выход по току принят 100 %. В реальности часть заряда расходуется "
        "на побочные процессы, поэтому времени потребуется больше."
    )
    return res


def current_efficiency(actual_mass: float, theoretical_mass: float) -> Result:
    """Выход по току."""
    if theoretical_mass <= 0:
        raise ElectrochemistryError("Теоретическая масса должна быть больше нуля")
    if actual_mass < 0:
        raise ElectrochemistryError("Фактическая масса не может быть отрицательной")

    value = actual_mass / theoretical_mass * 100.0

    res = Result(
        value=value,
        unit="%",
        label="Выход по току",
        method="η = m(факт)/m(теор)·100 %",
    )
    res.with_step(f"η = {actual_mass:g}/{theoretical_mass:g}·100 = {value:.4f} %")
    res.with_meta("loss_percent", 100.0 - value)

    if value > 100.0:
        res.with_warning(
            "Выход по току больше 100 %: это означает ошибку опыта или "
            "то, что часть осадка получена химическим путём, а не током"
        )
    elif value < 50:
        res.with_warning(
            f"Выход по току {value:.1f} % низкий — вероятно, идёт побочный "
            f"процесс, например выделение водорода"
        )
    return res


# --------------------------------------------------------------------------
# Диаграммы Пурбе
# --------------------------------------------------------------------------


# Системы для диаграмм Пурбе: элемент, его формы и переходы
POURBAIX_SYSTEMS: dict[str, dict] = {
    "Fe": {
        "name": "Железо",
        "lines": [
            {"label": "Fe²⁺ + 2e⁻ = Fe", "e0": -0.447, "n": 2,
             "ph_slope": 0.0, "kind": "metal"},
            {"label": "Fe³⁺ + e⁻ = Fe²⁺", "e0": 0.771, "n": 1,
             "ph_slope": 0.0, "kind": "redox"},
            {"label": "Fe(OH)₃ + 3H⁺ = Fe³⁺ + 3H₂O",
             "e0": 0.771, "n": 1, "ph_slope": -0.177, "kind": "hydrolysis"},
            {"label": "Fe(OH)₂ + 2H⁺ = Fe²⁺ + 2H₂O",
             "e0": -0.447, "n": 2, "ph_slope": -0.118, "kind": "hydrolysis"},
        ],
    },
    "Zn": {
        "name": "Цинк",
        "lines": [
            {"label": "Zn²⁺ + 2e⁻ = Zn", "e0": -0.7618, "n": 2,
             "ph_slope": 0.0, "kind": "metal"},
            {"label": "Zn(OH)₂ + 2H⁺ = Zn²⁺ + 2H₂O",
             "e0": -0.7618, "n": 2, "ph_slope": -0.0592, "kind": "hydrolysis"},
        ],
    },
    "Cu": {
        "name": "Медь",
        "lines": [
            {"label": "Cu²⁺ + 2e⁻ = Cu", "e0": 0.3419, "n": 2,
             "ph_slope": 0.0, "kind": "metal"},
            {"label": "Cu²⁺ + e⁻ = Cu⁺", "e0": 0.153, "n": 1,
             "ph_slope": 0.0, "kind": "redox"},
            {"label": "Cu(OH)₂ + 2H⁺ = Cu²⁺ + 2H₂O",
             "e0": 0.3419, "n": 2, "ph_slope": -0.0592, "kind": "hydrolysis"},
        ],
    },
    "Al": {
        "name": "Алюминий",
        "lines": [
            {"label": "Al³⁺ + 3e⁻ = Al", "e0": -1.662, "n": 3,
             "ph_slope": 0.0, "kind": "metal"},
            {"label": "Al(OH)₃ + 3H⁺ = Al³⁺ + 3H₂O",
             "e0": -1.662, "n": 3, "ph_slope": -0.0592, "kind": "hydrolysis"},
        ],
    },
}


def pourbaix_diagram(element: str, ph_min: float = 0.0, ph_max: float = 14.0,
                     points: int = 60) -> Result:
    """Диаграмма Пурбе: зависимость потенциала от pH для элемента.

    Строятся три характерные линии:
        a — равновесие металл/ион металла (горизонтальная);
        b — линия выделения водорода: E = −0.0592·pH;
        c — линия выделения кислорода: E = 1.229 − 0.0592·pH.

    Область между линиями b и c отвечает устойчивости воды: металл,
    потенциал которого в этой области ниже, будет восстанавливать воду,
    то есть корродировать с выделением водорода.
    """
    key = None
    for k, v in POURBAIX_SYSTEMS.items():
        if k.lower() == str(element).strip().lower() or \
           v["name"].lower() == str(element).strip().lower():
            key = k
            break
    if key is None:
        available = ", ".join(f"{k} ({v['name']})" for k, v in POURBAIX_SYSTEMS.items())
        raise ElectrochemistryError(
            f"Диаграмма Пурбе для «{element}» не построена. Доступны: {available}"
        )

    system = POURBAIX_SYSTEMS[key]

    if ph_min < 0 or ph_max > 14 or ph_min >= ph_max:
        raise ElectrochemistryError(
            "Диапазон pH должен лежать в пределах 0–14, причём начало меньше конца"
        )

    step = (ph_max - ph_min) / (points - 1) if points > 1 else 0

    data: dict[str, list[tuple[float, float]]] = {
        "выделение водорода": [],
        "выделение кислорода": [],
    }
    for line in system["lines"]:
        data[line["label"]] = []

    for i in range(points):
        ph = ph_min + i * step
        data["выделение водорода"].append((ph, -0.0592 * ph))
        data["выделение кислорода"].append((ph, 1.229 - 0.0592 * ph))
        for line in system["lines"]:
            e = line["e0"] + line["ph_slope"] * (ph - 0.0)
            data[line["label"]].append((ph, e))

    # Основная линия металла — первая в списке
    metal_line = system["lines"][0]
    metal_data = data[metal_line["label"]]

    res = series_result(
        metal_data,
        x_label="pH",
        y_label="Потенциал E, В",
        label=f"Диаграмма Пурбе для {system['name'].lower()}",
    )
    res.method = "Линии равновесия по уравнению Нернста с учётом pH"
    res.with_step(f"Элемент: {system['name']} ({key})")
    res.with_step(f"Всего линий на диаграмме: {len(data)}")
    for line in system["lines"]:
        res.with_step(
            f"  {line['label']}: E° = {line['e0']:+.4f} В, "
            f"наклон {line['ph_slope']:+.4f} В/pH"
        )
    res.with_step("")
    res.with_step("Линии устойчивости воды:")
    res.with_step("  выделение водорода:   E = −0.0592·pH")
    res.with_step("  выделение кислорода:  E = 1.229 − 0.0592·pH")

    # Прогноз коррозионной устойчивости
    e_metal_at_7 = metal_line["e0"] + metal_line["ph_slope"] * 7.0
    e_h2_at_7 = -0.0592 * 7.0
    e_o2_at_7 = 1.229 - 0.0592 * 7.0

    res.with_step("")
    res.with_step(f"При pH = 7: E({key}) = {e_metal_at_7:+.4f} В")
    res.with_step(f"  линия водорода:   {e_h2_at_7:+.4f} В")
    res.with_step(f"  линия кислорода:  {e_o2_at_7:+.4f} В")

    if e_metal_at_7 < e_h2_at_7:
        res.with_step(
            f"  Металл ниже линии водорода — термодинамически неустойчив, "
            f"корродирует с выделением водорода"
        )
        res.with_meta("corrosion_thermodynamic", True)
    elif e_metal_at_7 > e_o2_at_7:
        res.with_step(
            f"  Металл выше линии кислорода — благородный, в воде устойчив"
        )
        res.with_meta("corrosion_thermodynamic", False)
    else:
        res.with_step(
            f"  Металл между линиями — устойчив в отсутствие кислорода, "
            f"но может окисляться растворённым кислородом"
        )
        res.with_meta("corrosion_thermodynamic", None)

    res.with_meta("lines", {label: pts for label, pts in data.items()})
    res.with_meta("metal_line", metal_line["label"])
    res.with_assumption(
        "Диаграмма построена для активностей ионов 1 моль/л и 25 °C. "
        "Кинетика не учитывается: термодинамическая неустойчивость "
        "не всегда означает быструю коррозию — алюминий покрывается "
        "прочной оксидной плёнкой и практически устойчив."
    )
    return res


def corrosion_prediction(metal_electrode: str, ph: float = 7.0,
                         dissolved_oxygen: bool = True,
                         temperature_k: float = 298.15) -> Result:
    """Оценить термодинамическую возможность коррозии металла.

    Металл корродирует, если его потенциал ниже потенциала восстановления
    окислителя, присутствующего в среде.
    """
    metal = EDB.find(metal_electrode)

    e_metal = metal.E0
    e_h = -0.0592 * ph * (298.15 / temperature_k)

    oxidants = {"H⁺/H₂": e_h}
    if dissolved_oxygen:
        oxidants["O₂/H₂O"] = 1.229 - 0.0592 * ph * (298.15 / temperature_k)

    rows = []
    for name, e_ox in oxidants.items():
        emf = e_ox - e_metal
        rows.append({
            "Окислитель": name,
            "E окислителя, В": round(e_ox, 4),
            "ЭДС коррозии, В": round(emf, 4),
            "Возможна": "да" if emf > 0 else "нет",
        })

    res = table_result(rows, label=f"Коррозионная устойчивость {metal.id}",
                       columns=["Окислитель", "E окислителя, В",
                                "ЭДС коррозии, В", "Возможна"])
    res.method = "Сравнение потенциала металла с потенциалом окислителя среды"
    res.with_step(f"Полуреакция металла: {metal.half_reaction}")
    res.with_step(f"E°({metal.id}) = {metal.E0:+.4f} В")
    res.with_step(f"pH среды: {ph:g}")

    possible = [r for r in rows if r["Возможна"] == "да"]
    if possible:
        res.with_step(
            f"Термодинамически возможна коррозия под действием: "
            f"{', '.join(r['Окислитель'] for r in possible)}"
        )
        res.with_meta("corrosion_possible", True)
    else:
        res.with_step("Термодинамически коррозия невозможна")
        res.with_meta("corrosion_possible", False)

    res.with_source(EDB.source())
    res.with_assumption(
        "Оценивается только термодинамическая возможность, без кинетики. "
        "Пассивация (оксидная плёнка) может полностью остановить коррозию "
        "даже при положительной ЭДС."
    )
    return res


def electrolysis_products(identifiers: list[str],
                          temperature_k: float = 298.15) -> Result:
    """Определить, что выделится на катоде и аноде при электролизе.

    На катоде восстанавливается полуреакция с наибольшим потенциалом,
    на аноде окисляется полуреакция с наименьшим (то есть с наибольшей
    склонностью к окислению).
    """
    if len(identifiers) < 2:
        raise ElectrochemistryError(
            "Для определения продуктов электролиза нужно минимум две полуреакции"
        )

    candidates = []
    for ident in identifiers:
        e = EDB.find(ident)
        e_eff = nernst_potential(e.E0, e.n, temperature_k,
                                 oxidized=1.0, reduced=1.0).numeric()
        candidates.append((e, e_eff))

    # Катод — полуреакция восстановления с наибольшим потенциалом.
    # Анод — та, что осталась: она записана в таблице как восстановление,
    # но в элементе идёт в обратную сторону, поэтому её вклад вычитается.
    cathode_e, cathode_potential = max(candidates, key=lambda p: p[1])
    anode_candidates = [(e, p) for e, p in candidates if e.id != cathode_e.id]
    if not anode_candidates:
        raise ElectrochemistryError(
            "Все полуреакции совпадают: продукты электролиза определить нельзя"
        )
    anode_e, anode_potential = min(anode_candidates, key=lambda p: p[1])

    decomposition = cathode_potential - anode_potential

    res = Result(
        value=decomposition,
        unit="В",
        label="Напряжение разложения",
        method="Разность потенциалов наиболее выгодных полуреакций",
    )
    res.with_step("Рассмотренные полуреакции:")
    for e, pot in candidates:
        res.with_step(f"  {e.id}: E = {pot:+.4f} В — {e.half_reaction}")
    res.with_step("")
    res.with_step(
        f"Катод (восстановление, наибольший потенциал): {cathode_e.id}, "
        f"E = {cathode_potential:+.4f} В"
    )
    res.with_step(
        f"Анод (окисление, наименьший потенциал): {anode_e.id}, "
        f"E = {anode_potential:+.4f} В"
    )
    res.with_step(f"Минимальное напряжение разложения: {decomposition:.4f} В")
    res.with_meta("cathode", cathode_e.id)
    res.with_meta("anode", anode_e.id)
    res.with_meta("decomposition_voltage", decomposition)
    res.with_source(EDB.source())

    res.with_assumption(
        "Перенапряжение не учитывается. Реально требуемое напряжение выше, "
        "особенно для выделения водорода и кислорода: перенапряжение может "
        "достигать 0.5 В и более."
    )
    res.with_warning(
        f"Практическое напряжение электролиза будет выше {decomposition:.3f} В "
        f"из-за перенапряжения и омических потерь"
    )
    return res


def gibbs_from_emf(emf: float, n: int) -> Result:
    """Энергия Гиббса реакции по ЭДС: ΔG = −nFE."""
    if n <= 0:
        raise ElectrochemistryError("Число электронов должно быть больше нуля")

    dg = -n * F_VALUE * emf / 1000.0

    res = Result(value=dg, unit="кДж/моль",
                 label="Энергия Гиббса реакции",
                 method="ΔG = −n·F·E")
    res.with_step(f"ΔG = −{n}·{F_VALUE:g}·{emf:+.6f}/1000 = {dg:+.4f} кДж/моль")
    res.with_source(F_FARADAY.pretty())
    return res


def emf_from_gibbs(dg_kj: float, n: int) -> Result:
    """ЭДС по энергии Гиббса: E = −ΔG/(nF)."""
    if n <= 0:
        raise ElectrochemistryError("Число электронов должно быть больше нуля")

    emf = -dg_kj * 1000.0 / (n * F_VALUE)

    res = Result(value=emf, unit="В", label="ЭДС по энергии Гиббса",
                 method="E = −ΔG/(n·F)")
    res.with_step(f"E = −({dg_kj:+.4f}·1000)/({n}·{F_VALUE:g}) = {emf:+.6f} В")
    return res


def equilibrium_constant_from_emf(emf: float, n: int,
                                  temperature_k: float = 298.15) -> Result:
    """Константа равновесия из стандартной ЭДС: K = exp(nFE/RT)."""
    if n <= 0:
        raise ElectrochemistryError("Число электронов должно быть больше нуля")
    if temperature_k <= 0:
        raise ElectrochemistryError("Температура должна быть выше абсолютного нуля")

    exponent = n * F_VALUE * emf / (R_VALUE * temperature_k)

    res = Result(label="Константа равновесия реакции",
                 method="K = exp(n·F·E/(R·T))")
    res.with_step(f"Показатель степени: {n}·{F_VALUE:g}·{emf:+.6f}/"
                  f"({R_VALUE:g}·{temperature_k:g}) = {exponent:.6f}")

    if exponent > 700:
        res.value = float("inf")
        res.with_warning(
            "Показатель степени слишком велик: равновесие полностью смещено, "
            "численное значение K теряет смысл"
        )
        return res
    if exponent < -700:
        res.value = 0.0
        res.with_warning("Показатель степени слишком мал: реакция не идёт")
        return res

    K = math.exp(exponent)
    res.value = K
    res.with_step(f"K = e^{exponent:.6f} = {K:.6e}")
    res.with_step(f"lg K = {exponent / LN10:.4f}")
    res.with_meta("ln_K", exponent)
    res.with_meta("lg_K", exponent / LN10)
    return res
