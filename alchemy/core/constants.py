"""Физические и химические константы с прослеживаемостью до источника.

Каждая константа несёт не только значение, но и единицу, неопределённость
и ссылку на источник. Это нужно, чтобы любой результат в программе можно было
проверить, а не принимать на веру.

Источники:
    CODATA-2018   — Committee on Data for Science and Technology, 2018
    SI-2019       — реdefinition СИ, фиксированные значения
    IUPAC-2021    — стандартные условия и атомные массы
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------
# Контейнер константы
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Constant:
    """Физическая величина с единицей, неопределённостью и источником."""

    symbol: str
    value: float
    unit: str
    uncertainty: float
    source: str
    name: str = ""

    def __float__(self) -> float:
        return self.value

    def __str__(self) -> str:
        return f"{self.symbol} = {self.value:g} {self.unit}"

    @property
    def rel_uncertainty(self) -> float:
        """Относительная неопределённость."""
        if self.value == 0:
            return 0.0
        return abs(self.uncertainty / self.value)

    def pretty(self) -> str:
        """Строка вида «R = 8.314462618 Дж/(моль·К) [CODATA-2018]»."""
        if self.uncertainty == 0.0:
            return f"{self.symbol} = {self.value:g} {self.unit} [{self.source}]"
        return (
            f"{self.symbol} = {self.value:g} ± {self.uncertainty:g} "
            f"{self.unit} [{self.source}]"
        )


# --------------------------------------------------------------------------
# Универсальные константы (CODATA-2018)
# --------------------------------------------------------------------------

R = Constant(
    symbol="R",
    value=8.314462618,
    unit="Дж/(моль·К)",
    uncertainty=0.0,          # с 2019 года R определена точно через k_B и N_A
    source="CODATA-2018 (точно)",
    name="универсальная газовая постоянная",
)

R_ATM = Constant(
    symbol="R",
    value=0.082057366080960,
    unit="Л·атм/(моль·К)",
    uncertainty=0.0,
    source="CODATA-2018 (производная от R)",
    name="газовая постоянная в атм",
)

R_MMHG = Constant(
    symbol="R",
    value=62.363577,
    unit="Л·мм рт.ст./(моль·К)",
    uncertainty=0.0,
    source="CODATA-2018 (производная от R)",
    name="газовая постоянная в мм рт.ст.",
)

N_A = Constant(
    symbol="N_A",
    value=6.02214076e23,
    unit="1/моль",
    uncertainty=0.0,
    source="SI-2019 (точно)",
    name="постоянная Авогадро",
)

K_B = Constant(
    symbol="k_B",
    value=1.380649e-23,
    unit="Дж/К",
    uncertainty=0.0,
    source="SI-2019 (точно)",
    name="постоянная Больцмана",
)

H_PLANCK = Constant(
    symbol="h",
    value=6.62607015e-34,
    unit="Дж·с",
    uncertainty=0.0,
    source="SI-2019 (точно)",
    name="постоянная Планка",
)

C_LIGHT = Constant(
    symbol="c",
    value=299792458.0,
    unit="м/с",
    uncertainty=0.0,
    source="SI-2019 (точно)",
    name="скорость света в вакууме",
)

E_CHARGE = Constant(
    symbol="e",
    value=1.602176634e-19,
    unit="Кл",
    uncertainty=0.0,
    source="SI-2019 (точно)",
    name="элементарный заряд",
)

F_FARADAY = Constant(
    symbol="F",
    value=96485.33212,
    unit="Кл/моль",
    uncertainty=0.0,
    source="CODATA-2018 (производная N_A·e)",
    name="постоянная Фарадея",
)

SIGMA_SB = Constant(
    symbol="σ",
    value=5.670374419e-8,
    unit="Вт/(м²·К⁴)",
    uncertainty=0.0,
    source="CODATA-2018",
    name="постоянная Стефана — Больцмана",
)

M_E = Constant(
    symbol="m_e",
    value=9.1093837015e-31,
    unit="кг",
    uncertainty=2.8e-40,
    source="CODATA-2018",
    name="масса электрона",
)

M_P = Constant(
    symbol="m_p",
    value=1.67262192369e-27,
    unit="кг",
    uncertainty=5.1e-37,
    source="CODATA-2018",
    name="масса протона",
)

M_N = Constant(
    symbol="m_n",
    value=1.67492749804e-27,
    unit="кг",
    uncertainty=9.5e-37,
    source="CODATA-2018",
    name="масса нейтрона",
)

ALPHA_FS = Constant(
    symbol="α",
    value=7.2973525693e-3,
    unit="—",
    uncertainty=1.1e-12,
    source="CODATA-2018",
    name="постоянная тонкой структуры",
)

# --------------------------------------------------------------------------
# Водные растворы
# --------------------------------------------------------------------------

# Ионное произведение воды. Зависимость от температуры — по аппроксимации
# Harned & Owen (справочные таблицы), здесь базовое значение при 25 °C.
KW_25C = Constant(
    symbol="Kw",
    value=1.0e-14,
    unit="(моль/л)²",
    uncertainty=0.0,
    source="IUPAC-2021",
    name="ионное произведение воды при 25 °C",
)

# Стандартный потенциал водородного электрода — по определению 0.
E_STANDARD_HYDROGEN = Constant(
    symbol="E°(H⁺/H₂)",
    value=0.0,
    unit="В",
    uncertainty=0.0,
    source="IUPAC-2021 (по определению)",
    name="стандартный водородный электрод",
)

# --------------------------------------------------------------------------
# Стандартные условия
# --------------------------------------------------------------------------

# IUPAC с 1982 года: стандартное давление ровно 100 кПа.
# «Нормальные условия» в отечественной традиции — 101.325 кПа, 273.15 К.
STP_PRESSURE_PA = 101325.0        # нормальные условия, Па
STP_TEMPERATURE_K = 273.15        # нормальные условия, К
STANDARD_PRESSURE_PA = 100000.0   # стандартное состояние IUPAC, Па
STANDARD_TEMPERATURE_K = 298.15   # стандартная температура, К

# Молярный объём идеального газа при нормальных условиях (101.325 кПа, 273.15 К)
MOLAR_VOLUME_STP_L = R.value * STP_TEMPERATURE_K / STP_PRESSURE_PA * 1000.0
# = 22.4139... л/моль

# Нормальность (моль-эквивалент) — вне СИ, оставлена по требованию учебной практики.
MOLAR_MASS_CONSTANT = Constant(
    symbol="M_u",
    value=1e-3,
    unit="кг/моль",
    uncertainty=0.0,
    source="CODATA-2018",
    name="молярная постоянная масс",
)

# --------------------------------------------------------------------------
# Реестр для интерфейса справки
# --------------------------------------------------------------------------

ALL_CONSTANTS = (
    R, R_ATM, R_MMHG, N_A, K_B, H_PLANCK, C_LIGHT, E_CHARGE, F_FARADAY,
    SIGMA_SB, M_E, M_P, M_N, ALPHA_FS, KW_25C, E_STANDARD_HYDROGEN,
    MOLAR_MASS_CONSTANT,
)

# Быстрый доступ по символу
BY_SYMBOL = {c.symbol: c for c in ALL_CONSTANTS}


def get(symbol: str) -> Constant:
    """Вернуть константу по символу."""
    if symbol not in BY_SYMBOL:
        raise KeyError(f"Неизвестная константа: {symbol}")
    return BY_SYMBOL[symbol]


def value_of(symbol: str) -> float:
    """Числовое значение константы по символу."""
    return get(symbol).value
