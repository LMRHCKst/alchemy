"""Стехиометрические расчёты: лимитирующий реагент, выход, избыток, растворы.

Стехиометрия берётся из уравненной реакции, а не вводится вручную: сначала
уравнение уравнивается методом Гаусса, затем по коэффициентам считаются
количества. Это убирает целый класс ошибок, когда коэффициент в расчёте
не совпадает с уравнением.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import InputError
from ..core.formula import molar_mass, parse, split_state
from ..core.results import Result, table_result
from .balancer import balance


class StoichiometryError(InputError):
    """Стехиометрический расчёт невозможен."""


# --------------------------------------------------------------------------
# Разбор уравнения в участников реакции
# --------------------------------------------------------------------------


@dataclass
class Species:
    """Вещество реакции с ролью и коэффициентом."""

    text: str
    formula: str            # формула без обозначения состояния
    coefficient: int
    is_product: bool
    molar_mass: float

    @property
    def side(self) -> str:
        return "продукт" if self.is_product else "реагент"

    def __repr__(self) -> str:
        return f"<{self.text} ×{self.coefficient} ({self.side})>"


def parse_reaction(equation: str) -> tuple[list[Species], list[Species]]:
    """Разобрать уравнение в список реагентов и продуктов с молярными массами."""
    bal = balance(equation)

    def build(coeffs: dict[str, int], is_product: bool) -> list[Species]:
        result = []
        for text, c in coeffs.items():
            body, _ = split_state(text)
            try:
                M = molar_mass(body)
            except Exception as exc:
                raise StoichiometryError(
                    f"Не удалось определить молярную массу {text}: {exc}"
                ) from exc
            result.append(Species(text=text, formula=body, coefficient=c,
                                  is_product=is_product, molar_mass=M))
        return result

    return build(bal.meta["left"], False), build(bal.meta["right"], True)


def _find(species: list[Species], query: str) -> Species:
    """Найти вещество в списке по формуле или записи."""
    body_query, _ = split_state(str(query))
    key = body_query.replace(" ", "")
    for sp in species:
        if sp.formula.replace(" ", "") == key or sp.text.replace(" ", "") == key:
            return sp
    raise StoichiometryError(
        f"Вещества «{query}» нет среди {', '.join(s.text for s in species)}"
    )


# --------------------------------------------------------------------------
# Лимитирующий реагент
# --------------------------------------------------------------------------


def limiting_reagent(equation: str,
                     amounts: dict[str, float],
                     amount_kind: str = "moles") -> Result:
    """Определить лимитирующий реагент.

    Args:
        equation: уравнение реакции.
        amounts: {вещество: количество}. Ключ — формула или запись из уравнения.
        amount_kind: «moles» (моль), «mass» (г) или «volume_l» (л газа при н.у.).

    Возвращает таблицу с мольными количествами, отношением количества
    к коэффициенту и указанием лимитирующего реагента.
    """
    if not amounts:
        raise StoichiometryError("Не заданы количества реагентов")

    reactants, products = parse_reaction(equation)

    rows = []
    ratios: dict[str, float] = {}

    for query, amount in amounts.items():
        if amount < 0:
            raise StoichiometryError(f"Количество {query} не может быть отрицательным")
        sp = _find(reactants, query)

        if amount_kind == "moles":
            n = amount
        elif amount_kind == "mass":
            n = amount / sp.molar_mass
        elif amount_kind == "volume_l":
            n = amount / 22.414
        else:
            raise StoichiometryError(
                f"Неизвестный способ задания количества: {amount_kind}"
            )

        ratio = n / sp.coefficient
        ratios[sp.text] = ratio

        rows.append({
            "Вещество": sp.text,
            "Коэффициент": sp.coefficient,
            "Количество, моль": round(n, 6),
            "Количество / коэффициент": round(ratio, 6),
        })

    if not rows:
        raise StoichiometryError("Ни одно из заданных веществ не найдено в реакции")

    limiting = min(ratios, key=ratios.get)

    res = table_result(rows, label="Определение лимитирующего реагента",
                       columns=["Вещество", "Коэффициент", "Количество, моль",
                                "Количество / коэффициент"])
    res.method = "Сравнение отношений n/ν: минимальное отношение указывает на лимитирующий реагент"
    res.with_step(f"Уравнение: {balance(equation).value}")
    for sp_text, r in ratios.items():
        res.with_step(f"{sp_text}: n/ν = {r:.6f}")
    res.with_step(
        f"Лимитирующий реагент — {limiting}: он израсходуется первым, "
        f"остальные останутся в избытке"
    )
    res.with_meta("limiting", limiting)
    res.with_meta("ratios", ratios)
    res.meta["reagents"] = {
        row["Вещество"]: {
            "moles": row["Количество, моль"],
            "coefficient": row["Коэффициент"],
            "ratio": row["Количество / коэффициент"],
        }
        for row in rows
    }

    # Предупреждение о стехиометрической смеси
    values = list(ratios.values())
    if len(values) > 1:
        spread = (max(values) - min(values)) / max(values)
        if spread < 0.001:
            res.with_warning(
                "Реагенты взяты практически в стехиометрическом соотношении: "
                "лимитирующий реагент определён по минимальному отклонению, "
                "разница ничтожна"
            )

    return res


# --------------------------------------------------------------------------
# Выход продукта
# --------------------------------------------------------------------------


def theoretical_yield(equation: str, limiting_amount: float,
                      limiting_species: str, target_species: str,
                      amount_kind: str = "moles",
                      solution: bool = False) -> Result:
    """Теоретический выход продукта.

    Args:
        equation: уравнение реакции.
        limiting_amount: количество лимитирующего реагента.
        limiting_species: формула лимитирующего реагента.
        target_species: формула целевого продукта.
        amount_kind: «moles», «mass», «volume_l» или «concentration_volume»
                     (тогда limiting_amount — это C·V, то есть моли).
        solution: считать ли выход в молях, а не в граммах.
    """
    reactants, products = parse_reaction(equation)

    lim = _find(reactants, limiting_species)
    target = _find(products, target_species)

    if amount_kind == "moles":
        n_lim = limiting_amount
    elif amount_kind == "mass":
        n_lim = limiting_amount / lim.molar_mass
    elif amount_kind == "volume_l":
        n_lim = limiting_amount / 22.414
    elif amount_kind == "concentration_volume":
        n_lim = limiting_amount
    else:
        raise StoichiometryError(f"Неизвестный способ задания количества: {amount_kind}")

    if n_lim < 0:
        raise StoichiometryError("Количество не может быть отрицательным")

    n_target = n_lim * target.coefficient / lim.coefficient

    res = Result(
        label=f"Теоретический выход {target.text}",
        method="n(продукт) = n(лимитирующего)·ν(продукт)/ν(лимитирующего)",
    )
    res.with_step(f"Уравнение: {balance(equation).value}")
    res.with_step(
        f"n({lim.text}) = {n_lim:.6f} моль "
        f"(коэффициент {lim.coefficient})"
    )
    res.with_step(
        f"n({target.text}) = {n_lim:.6f}·{target.coefficient}/{lim.coefficient} "
        f"= {n_target:.6f} моль"
    )

    if solution:
        res.value = n_target
        res.unit = "моль"
    else:
        mass = n_target * target.molar_mass
        res.value = mass
        res.unit = "г"
        res.with_step(
            f"m({target.text}) = {n_target:.6f}·{target.molar_mass:.4f} "
            f"= {mass:.6f} г"
        )
        res.with_meta("mass_g", mass)

    res.with_meta("moles", n_target)
    res.with_meta("target_molar_mass", target.molar_mass)
    res.with_meta("limiting_molar_mass", lim.molar_mass)
    res.with_meta("equation", balance(equation).value)

    res.with_assumption(
        "Выход принят количественным: весь лимитирующий реагент превращается "
        "в целевой продукт. Реальный выход всегда ниже."
    )
    return res


def percent_yield(actual: float, theoretical: float) -> Result:
    """Выход продукта в процентах от теоретического."""
    if theoretical <= 0:
        raise StoichiometryError("Теоретический выход должен быть больше нуля")
    if actual < 0:
        raise StoichiometryError("Фактический выход не может быть отрицательным")

    value = actual / theoretical * 100.0

    res = Result(
        value=value,
        unit="%",
        label="Выход продукта",
        method="η = m(практ)/m(теор)·100 %",
    )
    res.with_step(f"η = {actual:g}/{theoretical:g}·100 = {value:.4f} %")
    res.with_meta("loss", theoretical - actual)
    res.with_meta("loss_percent", 100.0 - value)

    if value > 100.0:
        res.with_warning(
            f"Выход {value:.2f} % превышает 100 % — это означает ошибку: "
            f"продукт загрязнён, не высушен до конца или теоретический выход "
            f"рассчитан неверно"
        )
    elif value < 30:
        res.with_warning(
            f"Выход {value:.1f} % низкий. Проверьте условия синтеза и чистоту "
            f"исходных реагентов"
        )
    return res


def actual_yield_from_percent(percent: float, theoretical: float) -> Result:
    """Практический выход по известному проценту."""
    if theoretical <= 0:
        raise StoichiometryError("Теоретический выход должен быть больше нуля")
    if percent < 0:
        raise StoichiometryError("Процент выхода не может быть отрицательным")

    value = percent / 100.0 * theoretical

    res = Result(
        value=value,
        unit="(та же единица, что и теоретический выход)",
        label="Практический выход",
        method="m(практ) = η/100 · m(теор)",
    )
    res.with_step(f"m = {percent:g}/100·{theoretical:g} = {value:.6f}")
    return res


# --------------------------------------------------------------------------
# Избыток реагента
# --------------------------------------------------------------------------


def excess_reagent(equation: str, amounts: dict[str, float],
                   amount_kind: str = "moles") -> Result:
    """Сколько каждого реагента останется после реакции.

    Args:
        amounts: {вещество: количество} для всех реагентов.
        amount_kind: «moles», «mass» или «concentration_volume» (моли).
    """
    if len(amounts) < 2:
        raise StoichiometryError(
            "Для расчёта избытка нужно не менее двух реагентов"
        )

    reactants, _ = parse_reaction(equation)

    moles: dict[str, float] = {}
    species_by_text: dict[str, Species] = {}

    for query, amount in amounts.items():
        if amount < 0:
            raise StoichiometryError(f"Количество {query} не может быть отрицательным")
        sp = _find(reactants, query)
        species_by_text[sp.text] = sp

        if amount_kind == "moles" or amount_kind == "concentration_volume":
            n = amount
        elif amount_kind == "mass":
            n = amount / sp.molar_mass
        elif amount_kind == "volume_l":
            n = amount / 22.414
        else:
            raise StoichiometryError(f"Неизвестный способ задания количества: {amount_kind}")
        moles[sp.text] = n

    ratios = {t: moles[t] / species_by_text[t].coefficient for t in moles}
    limiting = min(ratios, key=ratios.get)
    ratio_lim = ratios[limiting]

    rows = []
    for text, n in moles.items():
        sp = species_by_text[text]
        needed = ratio_lim * sp.coefficient
        leftover = n - needed
        rows.append({
            "Вещество": text,
            "Взято, моль": round(n, 6),
            "Требуется, моль": round(needed, 6),
            "Остаток, моль": round(max(0.0, leftover), 6),
            "Остаток, г": round(max(0.0, leftover) * sp.molar_mass, 6),
            "Роль": "лимитирующий" if text == limiting else "в избытке",
        })

    res = table_result(rows, label="Расчёт остатков реагентов",
                       columns=["Вещество", "Взято, моль", "Требуется, моль",
                                "Остаток, моль", "Остаток, г", "Роль"])
    res.method = "По стехиометрии от лимитирующего реагента"
    res.with_step(f"Уравнение: {balance(equation).value}")
    res.with_step(f"Лимитирующий реагент: {limiting} ({ratio_lim:.6f} моль на коэффициент)")
    for row in rows:
        if row["Роль"] == "в избытке":
            sp = species_by_text[row["Вещество"]]
            percent = (row["Остаток, моль"] / row["Взято, моль"] * 100
                       if row["Взято, моль"] else 0)
            res.with_step(
                f"{row['Вещество']}: останется {row['Остаток, моль']:.6f} моль "
                f"({row['Остаток, г']:.4f} г), это {percent:.1f} % от взятого"
            )
    res.with_meta("limiting", limiting)
    res.with_meta("leftovers", {r["Вещество"]: r["Остаток, моль"] for r in rows})

    res.with_assumption(
        "Реакция идёт до полного расходования лимитирующего реагента. "
        "Обратимость и побочные процессы не учитываются."
    )
    return res


# --------------------------------------------------------------------------
# Стехиометрия растворов
# --------------------------------------------------------------------------


def solution_stoichiometry(equation: str,
                           solutions: dict[str, tuple[float, float]],
                           target: str,
                           target_is_solution: bool = False) -> Result:
    """Расчёт по реакции, где реагенты заданы растворами.

    Args:
        equation: уравнение реакции.
        solutions: {вещество: (концентрация моль/л, объём мл)}.
        target: формула целевого вещества.
        target_is_solution: если True, находится требуемый объём раствора
                            продукта при заданной концентрации.

    Классический тип задачи: «какой объём 0.1 М NaOH нужен для нейтрализации
    20 мл 0.15 М HCl».
    """
    if not solutions:
        raise StoichiometryError("Не заданы растворы реагентов")

    reactants, products = parse_reaction(equation)

    moles: dict[str, float] = {}
    sp_by_text: dict[str, Species] = {}

    for query, (c, v_ml) in solutions.items():
        if c <= 0 or v_ml <= 0:
            raise StoichiometryError(
                f"Концентрация и объём для {query} должны быть больше нуля"
            )
        sp = _find(reactants, query)
        n = c * v_ml / 1000.0
        moles[sp.text] = n
        sp_by_text[sp.text] = sp

    ratios = {t: moles[t] / sp_by_text[t].coefficient for t in moles}
    limiting = min(ratios, key=ratios.get)
    ratio_lim = ratios[limiting]

    lim_sp = sp_by_text[limiting]
    n_limiting = moles[limiting]

    res = Result(
        label="Стехиометрия растворов",
        method="По уравнению реакции с переходом от объёма раствора к молям",
    )
    res.with_step(f"Уравнение: {balance(equation).value}")

    for query, (c, v_ml) in solutions.items():
        sp = _find(reactants, query)
        n = moles[sp.text]
        res.with_step(
            f"{sp.text}: C = {c:g} моль/л, V = {v_ml:g} мл → "
            f"n = {c:g}·{v_ml / 1000:g} = {n:.6f} моль"
        )

    if len(ratios) > 1:
        res.with_step(f"Лимитирующий реагент: {limiting}")

    target_sp = _find(products, target)
    n_target = n_limiting * target_sp.coefficient / lim_sp.coefficient

    res.with_step(
        f"n({target_sp.text}) = {n_limiting:.6f}·{target_sp.coefficient}/"
        f"{lim_sp.coefficient} = {n_target:.6f} моль"
    )

    if target_is_solution:
        # Ищем нужный объём раствора для такого количества
        c_target, _ = solutions.get(target, (0.0, 0.0))
        if c_target <= 0:
            raise StoichiometryError(
                f"Для расчёта объёма раствора {target} задайте его концентрацию"
            )
        v_ml = n_target / c_target * 1000.0
        res.value = v_ml
        res.unit = "мл"
        res.label = f"Объём раствора {target_sp.text}"
        res.with_step(
            f"V = n/C = {n_target:.6f}/{c_target:g} = {v_ml:.6f} мл"
        )
        res.with_meta("volume_ml", v_ml)
    else:
        mass = n_target * target_sp.molar_mass
        res.value = mass
        res.unit = "г"
        res.label = f"Масса {target_sp.text}"
        res.with_step(
            f"m = {n_target:.6f}·{target_sp.molar_mass:.4f} = {mass:.6f} г"
        )

    res.with_meta("moles", n_target)
    res.with_meta("moles_given", moles)
    res.with_meta("limiting", limiting)

    res.with_assumption(
        "Растворы считаются полностью диссоциированными, объёмы аддитивны, "
        "реакция идёт до конца"
    )
    return res


def titration_volume(equation: str, analyte: str, analyte_c: float,
                     analyte_v_ml: float, titrant: str,
                     titrant_c: float) -> Result:
    """Объём титранта, необходимый для реакции с анализируемым раствором."""
    if titrant_c <= 0:
        raise StoichiometryError("Концентрация титранта должна быть больше нуля")

    reactants, products = parse_reaction(equation)
    _find(reactants, analyte)
    titrant_sp = _find(reactants, titrant)

    n_analyte = analyte_c * analyte_v_ml / 1000.0
    analyte_sp = _find(reactants, analyte)
    n_titrant = n_analyte * titrant_sp.coefficient / analyte_sp.coefficient
    volume_ml = n_titrant / titrant_c * 1000.0

    res = Result(
        value=volume_ml,
        unit="мл",
        label=f"Объём {titrant_sp.text}, необходимый для реакции",
        method="По уравнению реакции: n(титранта) = n(аналита)·ν(титранта)/ν(аналита)",
    )
    res.with_step(f"Уравнение: {balance(equation).value}")
    res.with_step(
        f"n({analyte_sp.text}) = {analyte_c:g}·{analyte_v_ml / 1000:g} "
        f"= {n_analyte:.6f} моль"
    )
    res.with_step(
        f"n({titrant_sp.text}) = {n_analyte:.6f}·{titrant_sp.coefficient}/"
        f"{analyte_sp.coefficient} = {n_titrant:.6f} моль"
    )
    res.with_step(
        f"V = {n_titrant:.6f}/{titrant_c:g} = {volume_ml / 1000:.6f} л "
        f"= {volume_ml:.4f} мл"
    )
    res.with_meta("volume_l", volume_ml / 1000)
    res.with_meta("moles_titrant", n_titrant)
    res.with_meta("moles_analyte", n_analyte)
    res.with_assumption(
        "Растворы полностью диссоциированы, реакция идёт до конца "
        "в стехиометрическом соотношении"
    )
    return res


# --------------------------------------------------------------------------
# Пересчёты количества вещества
# --------------------------------------------------------------------------


def moles_from(species: str, amount: float, kind: str) -> Result:
    """Перевести массу, объём газа или объём раствора в моли.

    Args:
        species: формула вещества.
        amount: числовое значение.
        kind: «mass» (г), «gas_volume_l» (л при н.у.),
              «solution» (тогда amount — произведение C·V в молях уже).
    """
    if amount < 0:
        raise StoichiometryError("Величина не может быть отрицательной")

    M = molar_mass(species)

    if kind == "mass":
        n = amount / M
        res = Result(value=n, unit="моль",
                     label=f"Количество вещества {species}",
                     method="n = m/M")
        res.with_step(f"n = {amount:g}/{M:.4f} = {n:.6f} моль")
    elif kind == "gas_volume_l":
        n = amount / 22.414
        res = Result(value=n, unit="моль",
                     label=f"Количество газа {species}",
                     method="n = V/Vm, Vm = 22.414 л/моль при н.у.")
        res.with_step(f"n = {amount:g}/22.414 = {n:.6f} моль")
    elif kind == "solution":
        n = amount
        res = Result(value=n, unit="моль",
                     label="Количество вещества в растворе",
                     method="n = C·V")
        res.with_step(f"n = {n:.6f} моль")
    else:
        raise StoichiometryError(f"Неизвестный способ: {kind}")

    res.with_meta("molar_mass", M)
    res.with_meta("moles", n)
    return res


def mass_from_moles(species: str, moles: float) -> Result:
    """Масса по количеству вещества."""
    if moles < 0:
        raise StoichiometryError("Количество вещества не может быть отрицательным")

    M = molar_mass(species)
    mass = moles * M

    res = Result(value=mass, unit="г",
                 label=f"Масса {species}",
                 method="m = n·M")
    res.with_step(f"m = {moles:.6f}·{M:.4f} = {mass:.6f} г")
    res.with_meta("molar_mass", M)
    return res


def mass_conversion(from_species: str, to_species: str, mass: float) -> Result:
    """Пересчёт массы одного вещества в массу другого (без реакции).

    Нужно, например, чтобы узнать, сколько безводной соли соответствует
    навеске кристаллогидрата.
    """
    if mass < 0:
        raise StoichiometryError("Масса не может быть отрицательной")

    M_from = molar_mass(from_species)
    M_to = molar_mass(to_species)
    n = mass / M_from
    mass_to = n * M_to

    res = Result(value=mass_to, unit="г",
                 label=f"Масса {to_species}, эквивалентная {mass:g} г {from_species}",
                 method="n = m/M, затем m = n·M")
    res.with_step(f"M({from_species}) = {M_from:.4f} г/моль")
    res.with_step(f"n = {mass:g}/{M_from:.4f} = {n:.6f} моль")
    res.with_step(f"M({to_species}) = {M_to:.4f} г/моль")
    res.with_step(f"m = {n:.6f}·{M_to:.4f} = {mass_to:.6f} г")
    if M_from > M_to:
        ratio = M_from / M_to
        res.with_step(f"Соотношение масс: 1 г {from_species} соответствует "
                      f"{M_to / M_from:.6f} г {to_species}")
    res.with_meta("moles", n)
    return res


def element_mass_in_sample(species: str, element: str, mass: float) -> Result:
    """Масса элемента в навеске соединения.

    Нужно для гравиметрии и для задач «сколько железа в руде».
    """
    if mass < 0:
        raise StoichiometryError("Масса не может быть отрицательной")

    comp = parse(species)
    if element not in comp.counts:
        raise StoichiometryError(
            f"Элемента {element} нет в формуле {species}"
        )

    M = comp.molar_mass
    n_sample = mass / M
    n_element = n_sample * comp.counts[element]
    from ..core import periodic
    m_element = n_element * periodic.atomic_mass(element)

    res = Result(
        value=m_element,
        unit="г",
        label=f"Масса {periodic.by_symbol(element).name_ru.lower()} в {mass:g} г {species}",
        method="Через массовую долю элемента",
    )
    res.with_step(f"M({species}) = {M:.4f} г/моль")
    res.with_step(
        f"Атомов {element} в формульной единице: {comp.counts[element]:g}"
    )
    res.with_step(f"n(образца) = {mass:g}/{M:.4f} = {n_sample:.6f} моль")
    res.with_step(f"n({element}) = {n_element:.6f} моль")
    res.with_step(f"m({element}) = {m_element:.6f} г")
    res.with_step(
        f"Массовая доля {element}: {comp.mass_percentages[element]:.4f} %"
    )
    res.with_meta("mass_percent", comp.mass_percentages[element])
    res.with_meta("moles", n_element)
    return res


def complex_problem(equation: str, given: list[dict],
                    targets: list[str] | None = None) -> Result:
    """Полный разбор задачи по реакции: лимитирующий реагент, выход, избыток.

    Args:
        equation: уравнение реакции.
        given: список словарей с ключами:
            species — вещество,
            amount — количество,
            kind — «moles», «mass», «volume_l», «solution» (тогда amount = C·V).
        targets: список целевых продуктов. Если не задан — все продукты.
    """
    if not given:
        raise StoichiometryError("Не заданы исходные данные")

    reactants, products = parse_reaction(equation)

    amounts_moles: dict[str, float] = {}
    for item in given:
        sp = _find(reactants, item["species"])
        amount = float(item["amount"])
        kind = item.get("kind", "moles")
        if amount < 0:
            raise StoichiometryError(f"Количество {sp.text} отрицательно")
        if kind == "moles" or kind == "solution":
            n = amount
        elif kind == "mass":
            n = amount / sp.molar_mass
        elif kind == "volume_l":
            n = amount / 22.414
        else:
            raise StoichiometryError(f"Неизвестный способ: {kind}")
        amounts_moles[sp.text] = n

    ratios = {}
    for text, n in amounts_moles.items():
        sp = _find(reactants, text)
        ratios[text] = n / sp.coefficient

    limiting = min(ratios, key=ratios.get)
    lim_sp = _find(reactants, limiting)
    n_lim = amounts_moles[limiting]

    if targets is None:
        target_species = products
    else:
        target_species = [_find(products, t) for t in targets]

    rows = []
    for sp in target_species:
        n = n_lim * sp.coefficient / lim_sp.coefficient
        rows.append({
            "Продукт": sp.text,
            "Количество, моль": round(n, 6),
            "Масса, г": round(n * sp.molar_mass, 6),
            "Объём газа при н.у., л": round(n * 22.414, 6),
        })

    res = table_result(rows, label="Результат решения задачи",
                       columns=["Продукт", "Количество, моль", "Масса, г",
                                "Объём газа при н.у., л"])
    res.method = "Стехиометрия от лимитирующего реагента"
    res.with_step(f"Уравнение: {balance(equation).value}")
    for text, n in amounts_moles.items():
        sp = _find(reactants, text)
        res.with_step(
            f"{sp.text}: n = {n:.6f} моль, n/ν = {ratios[text]:.6f}"
        )
    res.with_step(f"Лимитирующий реагент: {limiting}, n = {n_lim:.6f} моль")

    for row in rows:
        res.with_step(
            f"{row['Продукт']}: {row['Количество, моль']:.6f} моль = "
            f"{row['Масса, г']:.4f} г"
        )

    # Остатки реагентов
    if len(amounts_moles) > 1:
        excess_rows = []
        ratio_lim = ratios[limiting]
        for text, n in amounts_moles.items():
            sp = _find(reactants, text)
            needed = ratio_lim * sp.coefficient
            if n - needed > 1e-12:
                excess_rows.append({
                    "Вещество": sp.text,
                    "Остаток, моль": round(n - needed, 6),
                    "Остаток, г": round((n - needed) * sp.molar_mass, 6),
                })
        if excess_rows:
            res.meta["excess"] = excess_rows
            for row in excess_rows:
                res.with_step(
                    f"В избытке останется {row['Вещество']}: "
                    f"{row['Остаток, моль']:.6f} моль ({row['Остаток, г']:.4f} г)"
                )

    res.with_meta("limiting", limiting)
    res.with_meta("amounts", amounts_moles)
    res.with_assumption(
        "Реакция идёт до полного расходования лимитирующего реагента, "
        "выход количественный. Газы считаются идеальными при нормальных условиях."
    )
    return res
