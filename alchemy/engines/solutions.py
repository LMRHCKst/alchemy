"""Движок расчётов растворов: концентрации, разбавление, смешивание, рецепты.

Главное отличие от прежней версии: пересчёты между способами выражения
концентрации выполняются строго, через массу раствора, а не через
приближённые формулы вида «молярность = моляльность · плотность». Именно
такие приближения давали ошибку в разы.

Опорные величины:
    m₁ — масса растворённого вещества, г
    m₀ — масса растворителя, г
    m  = m₁ + m₀ — масса раствора, г
    V  — объём раствора, л
    d  — плотность раствора, г/мл
    M₁ — молярная масса растворённого вещества, г/моль
    M₀ — молярная масса растворителя, г/моль

Через них:
    w   = m₁ / m                          массовая доля
    C   = (m₁/M₁) / V                     молярность
    b   = (m₁/M₁) / (m₀/1000)             моляльность
    x   = (m₁/M₁) / (m₁/M₁ + m₀/M₀)       мольная доля
    N   = C · z                           нормальность
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import DomainError, InputError
from ..core.formula import molar_mass
from ..core.results import Result, table_result
from ..data import solubility as SDB

# Молярная масса воды — растворитель по умолчанию
M_WATER = 18.015


class SolutionError(InputError, DomainError):
    """Некорректные или физически невозможные данные раствора.

    Наследуется и от InputError, и от DomainError, чтобы перехватываться
    любым из них: в интерфейсе удобно ловить по одному типу.
    """


# Константа для пересчёта атм -> кПа
ATM_TO_KPA = 101.325


# --------------------------------------------------------------------------
# Модель раствора
# --------------------------------------------------------------------------


@dataclass
class Solution:
    """Раствор, описанный через первичные величины.

    Хранит массы и объём, а все концентрации вычисляет из них. Это исключает
    ситуацию, когда программа помнит одно представление и пересчитывает его
    в другое с накоплением ошибки.
    """

    solute_mass: float          # масса растворённого вещества, г
    solvent_mass: float         # масса растворителя, г
    solute_molar_mass: float    # молярная масса вещества, г/моль
    volume_l: float | None = None       # объём раствора, л
    density: float | None = None        # плотность раствора, г/мл
    solvent_molar_mass: float = M_WATER
    equivalents: float | None = None    # число эквивалентов (фактор эквивалентности)
    density_source: str = ""            # откуда взята плотность
    temperature: float = 298.15

    def __post_init__(self):
        # Все проверки приводятся к одному типу SolutionError, чтобы
        # вызывающий код перехватывал их единообразно
        if self.solute_mass < 0:
            raise SolutionError("Масса растворённого вещества не может быть отрицательной")
        if self.solvent_mass <= 0:
            raise SolutionError("Масса растворителя должна быть больше нуля")
        if self.solute_molar_mass <= 0:
            raise SolutionError("Молярная масса должна быть больше нуля")

        total = self.total_mass
        if self.solute_mass > total:
            raise SolutionError(
                "Масса растворённого вещества не может быть больше массы "
                "раствора: проверьте данные"
            )

        # Плотность и объём достраиваются друг из друга только когда это
        # действительно следует из данных. Плотность не выдумывается:
        # если она неизвестна, объёмные величины считаться не будут.
        if self.volume_l is None and self.density is not None:
            self.volume_l = total / (self.density * 1000.0)

    # ---------------- первичные ----------------

    @property
    def total_mass(self) -> float:
        """Масса раствора, г."""
        return self.solute_mass + self.solvent_mass

    @property
    def solute_moles(self) -> float:
        """Количество растворённого вещества, моль."""
        return self.solute_mass / self.solute_molar_mass

    @property
    def solvent_moles(self) -> float:
        """Количество растворителя, моль."""
        return self.solvent_mass / self.solvent_molar_mass

    # ---------------- концентрации ----------------

    @property
    def mass_fraction(self) -> float:
        """Массовая доля растворённого вещества, 0..1."""
        return self.solute_mass / self.total_mass

    @property
    def mass_percent(self) -> float:
        """Массовая доля, %."""
        return self.mass_fraction * 100.0

    @property
    def molarity(self) -> float:
        """Молярность, моль/л. Требует известного объёма или плотности."""
        if self.volume_l is None or self.volume_l <= 0:
            raise SolutionError(
                "Для молярности нужен объём раствора или его плотность"
            )
        return self.solute_moles / self.volume_l

    @property
    def molality(self) -> float:
        """Моляльность, моль/кг растворителя."""
        return self.solute_moles / (self.solvent_mass / 1000.0)

    @property
    def mole_fraction(self) -> float:
        """Мольная доля растворённого вещества."""
        n1, n0 = self.solute_moles, self.solvent_moles
        if n1 + n0 == 0:
            raise SolutionError("Суммарное количество вещества равно нулю")
        return n1 / (n1 + n0)

    @property
    def mole_fraction_solvent(self) -> float:
        """Мольная доля растворителя."""
        return 1.0 - self.mole_fraction

    @property
    def normality(self) -> float:
        """Нормальность, моль-экв/л."""
        if self.equivalents is None:
            raise SolutionError(
                "Для нормальности нужно указать число эквивалентов "
                "(фактор эквивалентности)"
            )
        return self.molarity * self.equivalents

    @property
    def mass_concentration(self) -> float:
        """Массовая концентрация, г/л."""
        if self.volume_l is None or self.volume_l <= 0:
            raise SolutionError("Для массовой концентрации нужен объём раствора")
        return self.solute_mass / self.volume_l

    @property
    def ppm(self) -> float:
        """Массовая доля в миллионных долях (мг/кг раствора)."""
        return self.mass_fraction * 1e6

    @property
    def ppb(self) -> float:
        """Массовая доля в миллиардных долях."""
        return self.mass_fraction * 1e9

    def molality_to_molarity(self) -> float:
        """Строгий пересчёт моляльности в молярность.

        C = b·d / (1 + b·M₁/1000), где d — плотность раствора в г/мл,
        а b·M₁/1000 — масса растворённого вещества в 1 кг растворителя,
        переведённая в килограммы.
        """
        if self.density is None:
            raise SolutionError(
                "Для пересчёта моляльности в молярность нужна плотность раствора"
            )
        b = self.molality
        return b * self.density / (1.0 + b * self.solute_molar_mass / 1000.0)

    def summary(self) -> dict[str, float | str]:
        """Все концентрации одним словарём."""
        data: dict[str, float | str] = {
            "масса вещества, г": self.solute_mass,
            "масса растворителя, г": self.solvent_mass,
            "масса раствора, г": self.total_mass,
            "количество вещества, моль": self.solute_moles,
            "массовая доля, %": self.mass_percent,
            "моляльность, моль/кг": self.molality,
            "мольная доля": self.mole_fraction,
        }
        if self.volume_l:
            data["объём раствора, л"] = self.volume_l
            data["молярность, моль/л"] = self.molarity
            data["массовая концентрация, г/л"] = self.mass_concentration
        if self.density:
            data["плотность, г/мл"] = self.density
        if self.equivalents:
            try:
                data["нормальность, моль-экв/л"] = self.normality
            except SolutionError:
                pass
        return data


# --------------------------------------------------------------------------
# Построение раствора из разных исходных данных
# --------------------------------------------------------------------------


def _density_for(solute_formula: str, mass_percent: float,
                 temperature_c: float) -> tuple[float | None, str]:
    """Подобрать плотность раствора по справочнику.

    Возвращает (плотность, пояснение). Если данных нет, плотность не
    выдумывается: возвращается None, и вызывающий код обязан предупредить
    пользователя.
    """
    body = solute_formula.split("(")[0] if "(" in solute_formula else solute_formula

    if SDB.has_density_table(body):
        d = SDB.density_of_solution(body, mass_percent, temperature_c)
        if d is not None:
            return d, f"плотность по справочнику для {body} при {temperature_c:g} °C"
        # Таблица есть, но концентрация вне её диапазона
        return None, (
            f"таблица плотности для {body} не покрывает концентрацию "
            f"{mass_percent:g} %"
        )

    return None, f"таблицы плотности для {body} нет в справочнике"


def from_mass_fraction(solute_formula: str, mass_percent: float,
                       solution_mass: float | None = None,
                       solvent_mass: float | None = None,
                       total_volume_l: float | None = None,
                       density: float | None = None,
                       temperature_c: float = 20.0,
                       equivalents: float | None = None) -> Solution:
    """Построить раствор по массовой доле.

    Нужно задать хотя бы одну из величин: массу раствора, массу растворителя
    или объём раствора.
    """
    if not 0 < mass_percent < 100:
        raise SolutionError(
            f"Массовая доля должна быть между 0 и 100 %, получено {mass_percent:g}"
        )

    M1 = molar_mass(solute_formula)
    w = mass_percent / 100.0

    # Плотность: явно заданная или из справочника
    density_note = "задана вручную"
    if density is None:
        density, density_note = _density_for(solute_formula, mass_percent,
                                             temperature_c)

    if solution_mass is not None:
        total = solution_mass
    elif solvent_mass is not None:
        total = solvent_mass / (1.0 - w)
    elif total_volume_l is not None:
        if density is None:
            raise SolutionError(
                "Для расчёта по объёму нужна плотность раствора. "
                "Укажите её явно: справочник не покрывает эту концентрацию."
            )
        total = total_volume_l * density * 1000.0
    else:
        raise SolutionError(
            "Задайте массу раствора, массу растворителя или объём раствора"
        )

    solute = total * w
    solvent = total - solute
    volume = total_volume_l
    if volume is None and density is not None:
        volume = total / (density * 1000.0)

    return Solution(
        solute_mass=solute,
        solvent_mass=solvent,
        solute_molar_mass=M1,
        volume_l=volume,
        density=density,
        equivalents=equivalents,
        density_source=density_note,
        temperature=temperature_c + 273.15,
    )


def from_molarity(solute_formula: str, molarity: float, volume_l: float,
                  density: float | None = None,
                  temperature_c: float = 20.0,
                  equivalents: float | None = None) -> Solution:
    """Построить раствор по молярности и объёму.

    Без плотности раствор описывается как идеальный: объём считается равным
    объёму раствора, а масса растворителя — по разности. Это допущение
    отмечается в результате.
    """
    if molarity <= 0:
        raise SolutionError("Молярность должна быть больше нуля")
    if volume_l <= 0:
        raise SolutionError("Объём должен быть больше нуля")

    M1 = molar_mass(solute_formula)
    n = molarity * volume_l
    solute = n * M1

    if density is None:
        # Оценим массовую долю для поиска плотности по справочнику
        estimated_percent = molarity * M1 / 10.0   # при плотности 1 г/мл
        density, note = _density_for(solute_formula, estimated_percent,
                                     temperature_c)
        if density is None:
            # Плотность неизвестна: считаем раствор водой по массе,
            # но не выдаём это за справочные данные
            density = 1.0
            note = (
                "плотность принята равной 1.000 г/мл, справочных данных нет. "
                "Объёмные величины приближённые — укажите плотность для "
                "точного расчёта"
            )
    else:
        note = "задана вручную"

    total_mass = volume_l * density * 1000.0
    solvent = total_mass - solute
    if solvent <= 0:
        raise SolutionError(
            f"Масса растворителя получилась отрицательной ({solvent:.2f} г). "
            f"Концентрация {molarity:g} моль/л при плотности {density:g} г/мл "
            f"физически невозможна"
        )

    mass_fraction = solute / total_mass
    if mass_fraction >= 0.99:
        raise SolutionError(
            f"Расчёт даёт массовую долю {mass_fraction * 100:.1f} %, что "
            f"означает почти чистое вещество. Концентрация {molarity:g} моль/л "
            f"при плотности {density:g} г/мл невозможна: проверьте данные."
        )

    # Плотность обязана согласоваться с массами: если из массы вещества
    # и воды получается другая плотность, значит данные противоречивы.
    # 6 моль/л NaCl (351 г/л) при плотности 1.0 г/мл дали бы 1.07 г/мл —
    # такой раствор невозможен, и об этом надо сказать, а не считать его.
    implied_density = total_mass / (volume_l * 1000.0)
    if abs(density - implied_density) / implied_density > 0.02:
        raise SolutionError(
            f"Данные противоречивы: при концентрации {molarity:g} моль/л и "
            f"плотности {density:g} г/мл масса растворителя не сходится с "
            f"массой раствора. Проверьте плотность — для {solute_formula} она "
            f"должна быть около {implied_density:.3f} г/мл."
        )

    solution = Solution(
        solute_mass=solute,
        solvent_mass=solvent,
        solute_molar_mass=M1,
        volume_l=volume_l,
        density=density,
        equivalents=equivalents,
        density_source=note,
        temperature=temperature_c + 273.15,
    )

    # Проверка на физическую реализуемость: если справочник знает предельную
    # концентрацию этого вещества, запрошенная не должна её превышать
    _check_feasible(solute_formula, solution.mass_percent)
    return solution


def _check_feasible(solute_formula: str, mass_percent: float) -> None:
    """Отклонить концентрацию, недостижимую для данного вещества.

    Растворимость хлорида натрия при 20 °C — около 26.4 %, поэтому раствор
    с массовой долей 35 % существовать не может. Раньше программа молча
    считала такой раствор, выдавая бессмысленный результат.
    """
    body = solute_formula.split("(")[0] if "(" in solute_formula else solute_formula

    w_max = SDB.max_mass_fraction(body)
    if w_max is not None and mass_percent > w_max + 1e-9:
        raise SolutionError(
            f"Массовая доля {mass_percent:.2f} % превышает предельно возможную "
            f"для {body} ({w_max:g} %). Такой раствор существовать не может: "
            f"проверьте концентрацию и плотность."
        )


def from_molality(solute_formula: str, molality: float,
                  solvent_mass: float, density: float | None = None,
                  temperature_c: float = 20.0,
                  equivalents: float | None = None) -> Solution:
    """Построить раствор по моляльности и массе растворителя."""
    if molality <= 0:
        raise SolutionError("Моляльность должна быть больше нуля")
    if solvent_mass <= 0:
        raise SolutionError("Масса растворителя должна быть больше нуля")

    M1 = molar_mass(solute_formula)
    n = molality * solvent_mass / 1000.0
    solute = n * M1
    total = solute + solvent_mass

    note = "плотность не требуется для моляльности"
    volume = None
    if density is not None:
        volume = total / (density * 1000.0)
        note = "задана вручную"

    return Solution(
        solute_mass=solute,
        solvent_mass=solvent_mass,
        solute_molar_mass=M1,
        volume_l=volume,
        density=density,
        equivalents=equivalents,
        density_source=note,
        temperature=temperature_c + 273.15,
    )


def from_mass_concentration(solute_formula: str, grams_per_liter: float,
                            volume_l: float = 1.0,
                            density: float | None = None,
                            temperature_c: float = 20.0,
                            equivalents: float | None = None) -> Solution:
    """Построить раствор по массовой концентрации, г/л."""
    if grams_per_liter <= 0:
        raise SolutionError("Массовая концентрация должна быть больше нуля")
    if volume_l <= 0:
        raise SolutionError("Объём должен быть больше нуля")

    M1 = molar_mass(solute_formula)
    solute = grams_per_liter * volume_l

    note = "плотность не задана"
    if density is None:
        estimated_percent = grams_per_liter / 10.0
        density, note = _density_for(solute_formula, estimated_percent, temperature_c)
        if density is None:
            # Плотность неизвестна — не выдумываем её
            note = ("плотность неизвестна: справочных данных нет. "
                    "Массы растворённого вещества и растворителя определить нельзя")

    if density is None:
        # Без плотности известна только масса вещества; растворитель не определён,
        # поэтому описываем раствор как гипотетический с растворителем по массе 1 л
        solvent = 1000.0 - solute if solute < 1000.0 else None
        if solvent is None or solvent <= 0:
            raise SolutionError(
                "Без плотности раствора определить массу растворителя нельзя: "
                "задайте плотность явно"
            )
        return Solution(
            solute_mass=solute,
            solvent_mass=solvent,
            solute_molar_mass=M1,
            volume_l=volume_l,
            density=None,
            equivalents=equivalents,
            density_source=note,
            temperature=temperature_c + 273.15,
        )

    total = volume_l * density * 1000.0
    solvent = total - solute
    if solvent <= 0:
        raise SolutionError(
            "Масса растворителя отрицательна — концентрация слишком велика "
            "для заданной плотности"
        )

    _check_feasible(solute_formula, solute / total * 100.0)

    return Solution(
        solute_mass=solute,
        solvent_mass=solvent,
        solute_molar_mass=M1,
        volume_l=volume_l,
        density=density,
        equivalents=equivalents,
        density_source=note,
        temperature=temperature_c + 273.15,
    )


# --------------------------------------------------------------------------
# Отчёт о растворе
# --------------------------------------------------------------------------


def describe(solution: Solution, label: str = "Раствор") -> Result:
    """Подробный отчёт обо всех концентрациях раствора."""
    res = Result(
        value=solution.summary(),
        unit="",
        label=label,
        kind="table",
        method="Пересчёт через массу раствора (точные формулы)",
    )

    res.with_step(f"Масса вещества: {solution.solute_mass:.4f} г")
    res.with_step(f"Масса растворителя: {solution.solvent_mass:.4f} г")
    res.with_step(f"Масса раствора: {solution.total_mass:.4f} г")
    res.with_step(
        f"Количество вещества: {solution.solute_moles:.6f} моль "
        f"(M = {solution.solute_molar_mass:.4f} г/моль)"
    )
    res.with_step(f"Массовая доля: {solution.mass_percent:.4f} %")

    try:
        res.with_step(f"Моляльность: {solution.molality:.6f} моль/кг")
    except SolutionError:
        pass
    try:
        res.with_step(f"Молярность: {solution.molarity:.6f} моль/л")
    except SolutionError:
        pass

    if solution.density is not None:
        res.with_step(f"Плотность: {solution.density:.4f} г/мл ({solution.density_source})")
        res.with_source(SDB.solvents_source())
        matches_reference = "справочник" in solution.density_source
    else:
        matches_reference = False

    if not matches_reference:
        res.with_warning(
            "Плотность раствора не подтверждена справочными данными. Объёмные "
            "величины (молярность, нормальность) либо не определены, либо "
            "приближённы. Для точного расчёта задайте плотность вручную."
        )

    res.with_meta("solution", solution)
    return res


# --------------------------------------------------------------------------
# Приготовление раствора
# --------------------------------------------------------------------------


def recipe(solute_formula: str, target_molarity: float, target_volume_ml: float,
           purity: float = 100.0, density: float | None = None,
           hydrate_water: int = 0) -> Result:
    """Сколько вещества взвесить для приготовления раствора заданной молярности.

    Args:
        solute_formula: формула вещества (можно с гидратной водой).
        target_molarity: требуемая молярность, моль/л.
        target_volume_ml: объём мерной колбы, мл.
        purity: содержание основного вещества в реактиве, %.
        density: плотность жидкости, если отвешивать неудобно и надо отмерить объём.
        hydrate_water: число молекул кристаллизационной воды, если формула
                       задана безводной, а реактив — гидрат.
    """
    if target_molarity <= 0:
        raise SolutionError("Молярность должна быть больше нуля")
    if target_volume_ml <= 0:
        raise SolutionError("Объём колбы должен быть больше нуля")
    if not 0 < purity <= 100:
        raise SolutionError("Содержание основного вещества должно быть от 0 до 100 %")

    formula_to_weigh = solute_formula
    if hydrate_water > 0 and "*" not in solute_formula:
        formula_to_weigh = f"{solute_formula}*{hydrate_water}H2O"

    M = molar_mass(formula_to_weigh)
    volume_l = target_volume_ml / 1000.0
    n_needed = target_molarity * volume_l
    mass_pure = n_needed * M
    mass_with_impurity = mass_pure / (purity / 100.0)

    res = Result(
        value=mass_with_impurity,
        unit="г",
        label=f"Навеска {formula_to_weigh} для {target_volume_ml:g} мл "
              f"{target_molarity:g} М раствора",
        method="m = C·V·M, с поправкой на содержание основного вещества",
    )
    res.with_step(f"{formula_to_weigh}: M = {M:.4f} г/моль")
    res.with_step(f"Требуется вещества: n = {target_molarity:g}·{volume_l:g} = {n_needed:.6f} моль")
    res.with_step(f"Масса чистого вещества: {mass_pure:.4f} г")
    if purity != 100.0:
        res.with_step(
            f"С учётом содержания {purity:g} %: {mass_pure:.4f}/{purity / 100:g} "
            f"= {mass_with_impurity:.4f} г"
        )

    res.with_meta("molar_mass", M)
    res.with_meta("moles", n_needed)
    res.with_meta("mass_pure", mass_pure)
    res.with_meta("formula_weighed", formula_to_weigh)

    if density is not None and density > 0:
        volume_ml = mass_with_impurity / density
        res.with_step(
            f"Если отмеривать по объёму при плотности {density:g} г/мл: "
            f"{volume_ml:.3f} мл"
        )
        res.with_meta("volume_to_measure_ml", volume_ml)
        res.method += "; объём через плотность"

    res.with_assumption(
        "Расчёт для приготовления в мерной колбе: навеску растворяют "
        "и доводят объём до метки, а не доливают указанный объём воды"
    )

    if purity < 99.0:
        res.with_warning(
            f"Содержание основного вещества {purity:g} % — навеска увеличена "
            f"пропорционально. Проверьте, что примеси не мешают анализу."
        )

    return res


# --------------------------------------------------------------------------
# Разбавление и смешивание
# --------------------------------------------------------------------------


def dilution(c_initial: float | None = None, v_initial: float | None = None,
             c_final: float | None = None, v_final: float | None = None,
             stock_volume_l: float | None = None) -> Result:
    """Разбавление: C₁V₁ = C₂V₂. Ровно одна величина должна быть неизвестна.

    Args:
        c_initial: исходная концентрация, моль/л
        v_initial: объём отбираемой порции, л
        c_final: конечная концентрация, моль/л
        v_final: конечный объём, л
        stock_volume_l: объём исходного раствора в наличии, л (для проверки)
    """
    params = {"C₁": c_initial, "V₁": v_initial, "C₂": c_final, "V₂": v_final}
    unknown = [k for k, v in params.items() if v is None]

    if len(unknown) != 1:
        raise SolutionError(
            "Нужно задать ровно три величины из четырёх (C₁, V₁, C₂, V₂), "
            "четвёртая будет найдена"
        )

    name = unknown[0]
    known = {k: v for k, v in params.items() if v is not None}
    for k, v in known.items():
        if v <= 0:
            raise SolutionError(f"{k} должна быть больше нуля")

    if name == "C₁":
        value = c_final * v_final / v_initial
    elif name == "V₁":
        value = c_final * v_final / c_initial
    elif name == "C₂":
        value = c_initial * v_initial / v_final
    else:  # V₂
        value = c_initial * v_initial / c_final

    unit = "л" if name.startswith("V") else "моль/л"

    res = Result(
        value=value,
        unit=unit,
        label=f"Найдено {name} при разбавлении",
        method="C₁V₁ = C₂V₂ (закон сохранения количества вещества)",
    )
    res.with_step(f"Уравнение: C₁·V₁ = C₂·V₂")
    for k, v in params.items():
        marker = " ← найдено" if k == name else ""
        res.with_step(f"{k} = {'?' if v is None else f'{v:g}'}{marker}")
    res.with_step(f"{name} = {value:.6g} {unit}")

    if name == "V₁":
        added = v_final - value
        res.with_step(f"Отобрать {value * 1000:.2f} мл исходного раствора")
        res.with_step(
            f"Довести объём до {v_final * 1000:.2f} мл, то есть добавить "
            f"около {added * 1000:.2f} мл растворителя"
        )
        res.with_meta("volume_to_take_ml", value * 1000)
        res.with_meta("solvent_to_add_ml", added * 1000)
        if added < 0:
            res.with_warning(
                "Расчётный объём добавки отрицателен: конечный объём меньше "
                "отбираемой порции. Проверьте данные."
            )
    elif name == "V₂":
        added = value - v_initial
        res.with_step(f"Довести объём до {value * 1000:.2f} мл")
        if added > 0:
            res.with_step(f"Добавить около {added * 1000:.2f} мл растворителя")
        res.with_meta("solvent_to_add_ml", added * 1000)

    if stock_volume_l is not None and name == "V₁" and value >= stock_volume_l:
        res.with_warning(
            f"Требуется {value * 1000:.1f} мл, а в наличии только "
            f"{stock_volume_l * 1000:.1f} мл исходного раствора"
        )

    res.with_assumption(
        "Объёмы считаются аддитивными, а плотность при разбавлении не "
        "меняется. Для концентрированных растворов это даёт заметную "
        "погрешность: реальный объём после смешивания не равен сумме объёмов."
    )
    return res


def serial_dilution(c_initial: float, transfer_volume_ml: float,
                    flask_volume_ml: float, n_steps: int) -> Result:
    """Серийное разбавление: перенос порции в чистую колбу на каждом шаге.

    В отличие от прежней реализации, коэффициент разбавления считается
    правильно: C(n) = C₀·(V_переноса/V_колбы)ⁿ. Ранее объём колбы
    использовался как объём переноса, что давало неверный результат.
    """
    if c_initial <= 0:
        raise SolutionError("Начальная концентрация должна быть больше нуля")
    if transfer_volume_ml <= 0 or flask_volume_ml <= 0:
        raise SolutionError("Объёмы должны быть больше нуля")
    if transfer_volume_ml > flask_volume_ml:
        raise SolutionError("Объём переноса не может превышать объём колбы")
    if n_steps < 1:
        raise SolutionError("Число шагов должно быть не меньше единицы")
    if n_steps != int(n_steps):
        raise SolutionError("Число шагов должно быть целым")

    n_steps = int(n_steps)
    factor = transfer_volume_ml / flask_volume_ml

    rows = [{"Шаг": 0, "Концентрация, моль/л": c_initial,
             "Степень разбавления": 1.0}]
    for i in range(1, n_steps + 1):
        c = c_initial * factor ** i
        rows.append({
            "Шаг": i,
            "Концентрация, моль/л": c,
            "Степень разбавления": 1.0 / (factor ** i),
        })

    res = table_result(rows, label=f"Серийное разбавление, {n_steps} шагов",
                       columns=["Шаг", "Концентрация, моль/л", "Степень разбавления"])
    res.method = "C(n) = C₀·(V_переноса/V_колбы)ⁿ"
    res.with_step(
        f"Коэффициент разбавления за шаг: {transfer_volume_ml:g}/{flask_volume_ml:g} "
        f"= {factor:.6f}"
    )
    res.with_step(f"Итоговая концентрация: {c_initial * factor ** n_steps:.6e} моль/л")
    res.with_step(f"Общее разбавление: в {1 / factor ** n_steps:.4g} раз")
    res.with_meta("concentrations", [r["Концентрация, моль/л"] for r in rows])
    res.with_assumption(
        "На каждом шаге порция переносится в чистую колбу и доводится до метки"
    )
    return res


def mixing(solutions: list[dict]) -> Result:
    """Смешивание нескольких растворов одного вещества.

    Args:
        solutions: список словарей с ключами:
            concentration — моль/л (или mass_percent — %),
            volume_l — объём, л (или mass_g — масса, г).
    """
    if not solutions:
        raise SolutionError("Нужно указать хотя бы один раствор")
    if len(solutions) < 2:
        raise SolutionError("Для смешивания нужно не менее двух растворов")

    total_moles = 0.0
    total_volume = 0.0
    total_mass = 0.0
    rows = []

    for i, s in enumerate(solutions, 1):
        if "concentration" in s and "volume_l" in s:
            c, v = float(s["concentration"]), float(s["volume_l"])
            if c < 0 or v <= 0:
                raise SolutionError(f"Раствор {i}: концентрация и объём должны быть положительны")
            n = c * v
            total_moles += n
            total_volume += v
            rows.append({
                "Раствор": i,
                "Концентрация, моль/л": c,
                "Объём, л": v,
                "Количество, моль": round(n, 8),
            })
        elif "mass_percent" in s and "mass_g" in s:
            w, m = float(s["mass_percent"]) / 100.0, float(s["mass_g"])
            if not 0 < w < 1 or m <= 0:
                raise SolutionError(f"Раствор {i}: некорректные массовая доля или масса")
            total_mass += m
            rows.append({
                "Раствор": i,
                "Массовая доля, %": w * 100,
                "Масса, г": m,
                "Масса вещества, г": round(w * m, 8),
            })
        else:
            raise SolutionError(
                f"Раствор {i}: нужны либо (concentration, volume_l), "
                f"либо (mass_percent, mass_g)"
            )

    if total_volume > 0:
        c_mix = total_moles / total_volume
        res = Result(
            value=c_mix,
            unit="моль/л",
            label="Концентрация после смешивания",
            method="C = Σ(CᵢVᵢ) / ΣVᵢ",
        )
        res.with_step(f"Суммарное количество вещества: {total_moles:.8f} моль")
        res.with_step(f"Суммарный объём: {total_volume:.6f} л")
        res.with_step(f"C = {total_moles:.8f} / {total_volume:.6f} = {c_mix:.8f} моль/л")
        res.with_meta("total_volume_l", total_volume)
        res.with_meta("total_moles", total_moles)
        res.with_assumption(
            "Объёмы аддитивны. Для концентрированных растворов разных веществ "
            "это неверно: реальный объём смеси меньше суммы объёмов."
        )
    else:
        w_mix = sum(s["Масса вещества, г"] for s in rows) / total_mass
        res = Result(
            value=w_mix * 100,
            unit="%",
            label="Массовая доля после смешивания",
            method="w = Σ(mᵢwᵢ) / Σmᵢ",
        )
        res.with_step(f"Суммарная масса: {total_mass:.4f} г")
        res.with_step(f"w = {w_mix * 100:.4f} %")
        res.with_meta("total_mass_g", total_mass)

    res.with_meta("components", rows)
    res.with_meta("table", rows)
    return res


def mixing_rule(c1: float, c2: float, c_target: float) -> Result:
    """Правило смешения (крест Пирсона): в каком массовом отношении смешать.

    Нужно для приготовления раствора промежуточной концентрации из двух
    имеющихся.
    """
    for name, value in (("C₁", c1), ("C₂", c2), ("C_целевая", c_target)):
        if value < 0:
            raise SolutionError(f"{name} не может быть отрицательной")

    if not (min(c1, c2) < c_target < max(c1, c2)):
        raise SolutionError(
            f"Целевая концентрация {c_target:g} должна лежать между "
            f"{min(c1, c2):g} и {max(c1, c2):g}"
        )

    part1 = abs(c_target - c2)
    part2 = abs(c1 - c_target)
    total = part1 + part2

    res = Result(
        value=part1 / part2,
        unit="",
        label="Массовое отношение первого раствора ко второму",
        method="Правило смешения (крест Пирсона)",
    )
    res.with_step(f"Частей раствора с C₁ = {c1:g}: |{c_target:g} − {c2:g}| = {part1:g}")
    res.with_step(f"Частей раствора с C₂ = {c2:g}: |{c1:g} − {c_target:g}| = {part2:g}")
    res.with_step(f"Отношение: {part1:g} : {part2:g}")
    res.with_meta("ratio", (part1, part2))
    res.with_meta("fractions", (part1 / total, part2 / total))
    return res


# --------------------------------------------------------------------------
# Коллигативные свойства
# --------------------------------------------------------------------------


def vant_hoff_factor(n_particles: int, n_formula_units: int = 1) -> Result:
    """Фактор Вант-Гоффа i = число частиц / число формульных единиц."""
    if n_formula_units <= 0:
        raise SolutionError("Число формульных единиц должно быть больше нуля")
    if n_particles < 0:
        raise SolutionError("Число частиц не может быть отрицательным")

    i = n_particles / n_formula_units

    res = Result(
        value=i,
        label="Фактор Вант-Гоффа",
        method="i = число частиц / число формульных единиц",
    )
    res.with_step(f"i = {n_particles}/{n_formula_units} = {i:.4f}")
    res.with_assumption(
        "Принято, что диссоциация полная. Для слабых электролитов фактор "
        "нужно считать через степень диссоциации."
    )
    return res


def vant_hoff_from_dissociation(alpha: float, n_ions: int) -> Result:
    """Фактор Вант-Гоффа через степень диссоциации: i = 1 + α(n − 1)."""
    if not 0 <= alpha <= 1:
        raise SolutionError("Степень диссоциации должна быть от 0 до 1")
    if n_ions < 1:
        raise SolutionError("Число ионов должно быть не меньше единицы")

    i = 1.0 + alpha * (n_ions - 1)

    res = Result(
        value=i,
        label="Фактор Вант-Гоффа",
        method="i = 1 + α·(n − 1)",
    )
    res.with_step(f"i = 1 + {alpha:g}·({n_ions} − 1) = {i:.4f}")
    res.with_assumption("Электролит диссоциирует на одинаковые частицы ступенчато одинаково")
    return res


def dissociation_from_vant_hoff(i: float, n_ions: int) -> Result:
    """Степень диссоциации из фактора Вант-Гоффа: α = (i − 1)/(n − 1)."""
    if n_ions < 2:
        raise SolutionError("Для расчёта степени диссоциации нужно не менее двух ионов")
    if not 1 <= i <= n_ions:
        raise SolutionError(
            f"Фактор Вант-Гоффа должен быть от 1 до {n_ions}, получено {i:g}"
        )

    alpha = (i - 1.0) / (n_ions - 1)

    res = Result(
        value=alpha,
        label="Степень диссоциации",
        method="α = (i − 1)/(n − 1)",
    )
    res.with_step(f"α = ({i:g} − 1)/({n_ions} − 1) = {alpha:.6f}")
    res.with_step(f"В процентах: {alpha * 100:.2f} %")
    return res


def boiling_point_elevation(solvent_name: str, molality: float,
                            i: float = 1.0) -> Result:
    """Повышение температуры кипения. ΔT = i·Kb·b.

    Фактор Вант-Гоффа учтён: для 0.5 моль/кг NaCl (i = 2) повышение вдвое
    больше, чем для неэлектролита. В прежней версии это игнорировалось.
    """
    if molality < 0:
        raise SolutionError("Моляльность не может быть отрицательной")
    if i <= 0:
        raise SolutionError("Фактор Вант-Гоффа должен быть больше нуля")

    solvent = SDB.find_solvent(solvent_name)
    if solvent.Kb is None:
        raise SolutionError(f"Для растворителя «{solvent.name}» нет Kb")
    if solvent.Tb is None:
        raise SolutionError(f"Для растворителя «{solvent.name}» нет температуры кипения")

    dT = i * solvent.Kb * molality
    t_boil = solvent.Tb + dT

    res = Result(
        value=t_boil,
        unit="К",
        label=f"Температура кипения раствора в {solvent.name.lower()}е",
        method="ΔT = i·Kb·b",
    )
    res.with_step(f"Kb({solvent.name}) = {solvent.Kb:g} К·кг/моль")
    res.with_step(f"ΔT = {i:g}·{solvent.Kb:g}·{molality:g} = {dT:.4f} К")
    res.with_step(f"T кипения = {solvent.Tb:.2f} + {dT:.4f} = {t_boil:.4f} К = {t_boil - 273.15:.2f} °C")
    res.with_meta("delta_T", dT)
    res.with_meta("Tb_pure", solvent.Tb)
    res.with_source(SDB.solvents_source())

    if i == 1.0:
        res.with_warning(
            "Фактор Вант-Гоффа принят равным единице (неэлектролит). "
            "Для солей и кислот укажите i, иначе результат занижен"
        )
    return res


def freezing_point_depression(solvent_name: str, molality: float,
                              i: float = 1.0) -> Result:
    """Понижение температуры замерзания. ΔT = i·Kf·b."""
    if molality < 0:
        raise SolutionError("Моляльность не может быть отрицательной")
    if i <= 0:
        raise SolutionError("Фактор Вант-Гоффа должен быть больше нуля")

    solvent = SDB.find_solvent(solvent_name)
    if solvent.Kf is None:
        raise SolutionError(
            f"Для растворителя «{solvent.name}» нет криоскопической константы"
        )
    if solvent.Tf is None:
        raise SolutionError(f"Для растворителя «{solvent.name}» нет температуры плавления")

    dT = i * solvent.Kf * molality
    t_freeze = solvent.Tf - dT

    res = Result(
        value=t_freeze,
        unit="К",
        label=f"Температура замерзания раствора в {solvent.name.lower()}е",
        method="ΔT = i·Kf·b",
    )
    res.with_step(f"Kf({solvent.name}) = {solvent.Kf:g} К·кг/моль")
    res.with_step(f"ΔT = {i:g}·{solvent.Kf:g}·{molality:g} = {dT:.4f} К")
    res.with_step(f"T замерзания = {solvent.Tf:.2f} − {dT:.4f} = {t_freeze:.4f} К = {t_freeze - 273.15:.2f} °C")
    res.with_meta("delta_T", dT)
    res.with_meta("Tf_pure", solvent.Tf)
    res.with_source(SDB.solvents_source())

    if i == 1.0:
        res.with_warning("Фактор Вант-Гоффа принят равным единице (неэлектролит)")
    return res


def osmotic_pressure(molarity: float, temperature_k: float = 298.15,
                     i: float = 1.0) -> Result:
    """Осмотическое давление. π = i·C·R·T (атм при C в моль/л)."""
    if molarity < 0:
        raise SolutionError("Молярность не может быть отрицательной")
    if temperature_k <= 0:
        raise SolutionError("Температура должна быть больше нуля")
    if i <= 0:
        raise SolutionError("Фактор Вант-Гоффа должен быть больше нуля")

    R = 0.082057366080960   # Л·атм/(моль·К)
    pi = i * molarity * R * temperature_k

    res = Result(
        value=pi,
        unit="атм",
        label="Осмотическое давление",
        method="π = i·C·R·T",
    )
    res.with_step(f"π = {i:g}·{molarity:g}·{R:g}·{temperature_k:g} = {pi:.6f} атм")
    res.with_step(f"В килопаскалях: {pi * 101.325:.4f} кПа")
    res.with_meta("kPa", pi * 101.325)
    return res


def molar_mass_from_freezing(solvent_name: str, delta_t: float,
                             solute_mass_g: float, solvent_mass_g: float,
                             i: float = 1.0) -> Result:
    """Молярная масса вещества по понижению температуры замерзания.

    Классический метод криоскопии: M = i·Kf·m_вещества/(ΔT·m_растворителя_кг).
    """
    if delta_t <= 0:
        raise SolutionError("Понижение температуры должно быть больше нуля")
    if solute_mass_g <= 0:
        raise SolutionError("Масса вещества должна быть больше нуля")
    if solvent_mass_g <= 0:
        raise SolutionError("Масса растворителя должна быть больше нуля")

    solvent = SDB.find_solvent(solvent_name)
    if solvent.Kf is None:
        raise SolutionError(f"Для «{solvent.name}» нет криоскопической константы")

    m_kg = solvent_mass_g / 1000.0
    M = i * solvent.Kf * solute_mass_g / (delta_t * m_kg)

    res = Result(
        value=M,
        unit="г/моль",
        label="Молярная масса по криоскопии",
        method="M = i·Kf·m/(ΔT·m_растворителя)",
    )
    res.with_step(f"Kf({solvent.name}) = {solvent.Kf:g}")
    res.with_step(f"m(растворителя) = {solvent_mass_g:g} г = {m_kg:g} кг")
    res.with_step(
        f"M = {i:g}·{solvent.Kf:g}·{solute_mass_g:g}/({delta_t:g}·{m_kg:g}) = {M:.4f} г/моль"
    )
    res.with_assumption(
        "Раствор считается разбавленным, поэтому моляльность равна "
        "концентрации всех частиц. Для концентрированных растворов метод "
        "даёт завышенную молярную массу."
    )
    return res


def colligative_report(solvent_name: str, molality: float, i: float = 1.0,
                       temperature_k: float = 298.15,
                       molarity: float | None = None) -> Result:
    """Полный отчёт по коллигативным свойствам раствора."""
    rows = []

    try:
        bpe = boiling_point_elevation(solvent_name, molality, i)
        rows.append({
            "Свойство": "Повышение температуры кипения",
            "Значение": round(bpe.meta["delta_T"], 4),
            "Единица": "К",
            "Формула": "ΔT = i·Kb·b",
        })
    except SolutionError as exc:
        rows.append({"Свойство": "Повышение температуры кипения",
                     "Значение": None, "Единица": "—", "Формула": str(exc)})

    try:
        fpd = freezing_point_depression(solvent_name, molality, i)
        rows.append({
            "Свойство": "Понижение температуры замерзания",
            "Значение": round(fpd.meta["delta_T"], 4),
            "Единица": "К",
            "Формула": "ΔT = i·Kf·b",
        })
    except SolutionError as exc:
        rows.append({"Свойство": "Понижение температуры замерзания",
                     "Значение": None, "Единица": "—", "Формула": str(exc)})

    if molarity is not None:
        op = osmotic_pressure(molarity, temperature_k, i)
        rows.append({
            "Свойство": "Осмотическое давление",
            "Значение": round(op.numeric(), 6),
            "Единица": "атм",
            "Формула": "π = i·C·R·T",
        })

    solvent = SDB.find_solvent(solvent_name)
    rows.append({
        "Свойство": "Моляльность",
        "Значение": round(molality, 6),
        "Единица": "моль/кг",
        "Формула": "—",
    })
    rows.append({
        "Свойство": "Фактор Вант-Гоффа",
        "Значение": round(i, 4),
        "Единица": "—",
        "Формула": "i = 1 + α(n − 1)",
    })

    res = table_result(rows, label=f"Коллигативные свойства в {solvent.name.lower()}е",
                       columns=["Свойство", "Значение", "Единица", "Формула"])
    res.method = "Коллигативные законы Рауля и Вант-Гоффа"
    res.with_source(SDB.solvents_source())
    res.with_assumption(
        "Раствор разбавленный и идеальный: взаимодействие между частицами "
        "не учитывается, коэффициенты активности равны единице"
    )
    return res


# --------------------------------------------------------------------------
# Массовая доля по плотности — практическая задача
# --------------------------------------------------------------------------


def concentration_from_density(solute_formula: str, density: float,
                               temperature_c: float = 20.0) -> Result:
    """Определить концентрацию раствора по его измеренной плотности.

    Практическая задача: ареометр показывает плотность товарной кислоты,
    а нужна молярность.
    """
    if density <= 0:
        raise SolutionError("Плотность должна быть больше нуля")

    if not SDB.has_density_table(solute_formula):
        raise SolutionError(
            f"Для «{solute_formula}» нет таблицы плотности в справочнике. "
            f"Доступны: {', '.join(SDB.density_table_names())}"
        )

    percent = SDB.mass_fraction_from_density(solute_formula, density, temperature_c)
    if percent is None:
        raise SolutionError(
            f"Плотность {density:g} г/мл не соответствует однозначной "
            f"концентрации раствора {solute_formula}: зависимость немонотонна "
            f"(у серной кислоты максимум около 98 %). Укажите массовую долю явно."
        )

    solution = from_mass_fraction(
        solute_formula, percent, total_volume_l=1.0,
        density=density, temperature_c=temperature_c,
    )

    res = Result(
        value=percent,
        unit="%",
        label=f"Массовая доля {solute_formula} по плотности {density:g} г/мл",
        method="Обратная интерполяция справочной таблицы плотности",
    )
    res.with_step(f"Плотность {density:g} г/мл при {temperature_c:g} °C")
    res.with_step(f"Массовая доля: {percent:.2f} %")
    res.with_step(f"Молярность: {solution.molarity:.4f} моль/л")
    res.with_step(f"Моляльность: {solution.molality:.4f} моль/кг")
    res.with_step(f"Масса вещества в 1 л раствора: {solution.solute_mass:.2f} г")
    res.with_meta("molarity", solution.molarity)
    res.with_meta("molality", solution.molality)
    res.with_source(SDB.solvents_source())
    res.with_assumption(
        "Температура раствора совпадает с указанной; температурная поправка "
        "плотности линейна и справедлива в интервале 15–30 °C"
    )
    return res
