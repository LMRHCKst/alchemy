# -*- coding: utf-8 -*-
"""Вытащить из АСТРА список индивидуальных веществ и сравнить с нашей базой.

Исходник — LIST_OF.SPE из комплекта АСТРА.4/pc (база на 2595 веществ).
Результат — docs/astra_species.md.

Запуск: python tools/extract_astra.py [путь к LIST_OF.SPE]
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_SOURCE = Path(r"D:\4курс\НИР\Астра\Астра\LIST_OF.SPE")
OUTPUT = ROOT / "docs" / "astra_species.md"

#: всё, что похоже на формулу вещества, включая пометку конденсированной фазы
SPECIES_RE = re.compile(r"[A-Za-z][A-Za-z0-9().+\-]*")


def read_species(path: Path) -> list[str]:
    """Прочитать список веществ из файла АСТРА."""
    raw = path.read_bytes()
    text = raw.decode("cp866", "replace")

    species: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "Список" in stripped or "База" in stripped or "Astra" in stripped:
            continue
        for token in stripped.split():
            if SPECIES_RE.fullmatch(token) and re.search(r"[A-Z]", token):
                species.append(token)
    return species


def split_state(formula: str) -> tuple[str, str]:
    """Отделить пометку фазы: Al2O3(c) -> (Al2O3, c)."""
    match = re.fullmatch(r"(.*)\((c)\)", formula)
    if match:
        return match.group(1), "c"
    return formula, "g"


def elements_of(formula: str) -> list[str]:
    """Символы элементов в формуле."""
    return re.findall(r"[A-Z][a-z]?", formula)


def our_substances() -> dict[str, str]:
    """Наши вещества: нормализованная формула -> ключ справочника."""
    from alchemy.data import thermo

    result: dict[str, str] = {}
    for substance in thermo.all_substances():
        key = substance.key
        # ключ вида "H2O(ж)" или "CH4": берём формулу до скобки состояния
        formula = re.sub(r"\([^)]*\)", "", key).strip()
        result.setdefault(normalize(formula), key)
    return result


def normalize(formula: str) -> str:
    """Привести формулу к сравнимому виду: убрать точки, звёздочки, пробелы."""
    text = formula.replace("·", "").replace("*", "").replace(" ", "")
    return text.lower()


def composition_key(formula: str) -> str | None:
    """Ключ по составу, а не по записи.

    АСТРА пишет формулы по Хиллу (этанол — C2H6O), мы можем записать
    структурно (C2H5OH). Сравнивать строки бессмысленно: считаем атомы.
    """
    from alchemy.core import formula as parser

    clean = re.sub(r"\([^)]*\)", "", formula).strip()
    clean = clean.replace("·", "*")
    try:
        parsed = parser.parse(clean)
        counts = parsed.counts
    except Exception:
        # запасной разбор: формулы со звёздочками и зарядами
        counts = Counter()
        for element, number in re.findall(r"([A-Z][a-z]?)(\d*\.?\d*)", clean):
            if not number:
                counts[element] += 1
            else:
                try:
                    counts[element] += float(number)
                except ValueError:
                    counts[element] += 1
        if not counts:
            return None
    return "".join(f"{element}{counts[element]:g}" for element in sorted(counts))


def main(argv: list[str]) -> int:
    source = Path(argv[1]) if len(argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        print(f"нет файла: {source}")
        return 1

    species = read_species(source)
    # в файле вещества идут блоками по элементам и повторяются; для таблицы
    # оставляем первое вхождение, а для статистики считаем как есть
    unique_species = list(dict.fromkeys(species))
    condensed = [s for s in species if s.endswith("(c)")]
    gases = [s for s in species if not s.endswith("(c)")]
    ions = [s for s in species if s.rstrip("(c)").endswith(("+", "-"))]
    organics = [
        s for s in species
        if "C" in s and "H" in s and not s.endswith("(c)")
    ]
    formulas = {normalize(split_state(s)[0]) for s in species}

    element_counter: Counter[str] = Counter()
    for item in species:
        for element in set(elements_of(split_state(item)[0])):
            element_counter[element] += 1

    ours = our_substances()
    astra_by_composition: dict[str, str] = {}
    for item in species:
        key = composition_key(split_state(item)[0])
        if key:
            astra_by_composition.setdefault(key, item)

    ours_by_composition: dict[str, str] = {}
    for key, name in ours.items():
        composition = composition_key(name)
        if composition:
            ours_by_composition.setdefault(composition, name)

    missing = sorted(
        (astra_by_composition[key], key)
        for key in astra_by_composition if key not in ours_by_composition
    )
    shared = sorted(
        (astra_by_composition[key], ours_by_composition[key])
        for key in astra_by_composition if key in ours_by_composition
    )
    covered = sum(1 for key in ours_by_composition if key in astra_by_composition)
    uncovered = sorted(
        ours_by_composition[key]
        for key in ours_by_composition if key not in astra_by_composition
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    add = lines.append

    add("# Вещества из базы АСТРА.4/pc")
    add("")
    add("Разбор комплекта АСТРА.4/pc (МГТУ им. Н.Э. Баумана, автор Б.Г. Трусов,")
    add("руководство 1991 года, исполняемые файлы 1997 и 2004). Из всего комплекта")
    add("вытащен только список индивидуальных веществ: он текстовый и не зависит")
    add("от DOS. Остальное — бинарная база и скомпилированные программы.")
    add("")
    add("Источник: `LIST_OF.SPE`, кодировка CP866.")
    add("")
    add("## Что в списке")
    add("")
    add(f"- записей: {len(species)}, из них уникальных: **{len(unique_species)}**")
    add(f"- разных формул без учёта фазы: **{len(formulas)}**")
    add(f"- газов и прочих: {len(gases)}")
    add(f"- конденсированных (пометка `(c)`): {len(condensed)}")
    add(f"- разных элементов: **{len(element_counter)}**")
    add(f"- заряженных частиц (ионы): {len(ions)}")
    add(f"- органических соединений в газе: {len(organics)}")
    add("")
    add("Вещества повторяются, потому что в файле они сгруппированы по элементам:")
    add("кислород встречается и в блоке O, и в блоках соединений.")
    add("")
    add("Самые частые элементы (по числу веществ):")
    add("")
    add("| Элемент | Веществ |")
    add("|---|---|")
    for element, count in element_counter.most_common(12):
        add(f"| {element} | {count} |")
    add("")
    add("## Как устроена база")
    add("")
    add("По руководству АСТРА, на каждое вещество в базе хранится: формула,")
    add("нижняя и верхняя границы температурной аппроксимации, семь")
    add("коэффициентов аппроксимации свободной энергии Гиббса и энтальпия")
    add("образования. Файл `ASTRA.BAS` — это и есть база, только в двоичном виде")
    add("(float32, 422 КБ), без имён внутри: порядок веществ жёстко зашит")
    add("в программу. Имя `.BAS` обманчиво, исходника там нет.")
    add("")
    add("## Сверка с нашими справочниками")
    add("")
    add(f"У нас {len(ours_by_composition)} веществ. Из них в базе АСТРА есть")
    add(f"**{covered}**. Сверка идёт по составу, а не по записи: АСТРА пишет")
    add("формулы по Хиллу (`C2H6O`), у нас часть записана структурно (`C2H5OH`),")
    add("и это одно и то же вещество.")
    add("")
    add(f"Всего совпало по составу: **{len(shared)}**.")
    add(f"Есть у АСТРА, нет у нас: **{len(missing)}** составов.")
    add("")
    if uncovered:
        add(f"Наши вещества, которых у АСТРА нет совсем ({len(uncovered)}):")
        add("")
        for key in uncovered:
            add(f"- `{key}`")
        add("")
    if shared:
        add("Совпавшие:")
        add("")
        for astra_name, our_key in shared:
            add(f"- `{astra_name}` — `{our_key}`")
        add("")
    if missing:
        add("Чего у нас нет (первые 60 по алфавиту):")
        add("")
        for astra_name, _key in missing[:60]:
            add(f"- `{astra_name}`")
        add("")
        add("Остальное — в полном списке ниже.")
        add("")
    add("## Что из этого следует")
    add("")
    add("База АСТРА собрана под высокотемпературные задачи: горение, плазма,")
    add("ракетные топлива. Отсюда 172 иона, фториды и хлориды почти всех")
    add("элементов, оксиды тугоплавких металлов и верхняя граница 20000 К.")
    add("")
    add("Школьной химии в ней меньше, чем ожидаешь: нет нитрата серебра,")
    add("хлорида серебра, сульфата меди, перманганата, дихромата, сахаров.")
    add("Это не пробел, а другое назначение базы.")
    add("")
    add("Для нас отсюда полезен только перечень как контрольный список: если")
    add("когда-нибудь расширять свои справочники, видно, какие вещества бывают")
    add("в расчётных базах и в какой форме их записывают. Числа брать негде —")
    add("коэффициенты лежат в двоичном файле без имён.")
    add("")
    add("## Полный список")
    add("")
    add("Пометка `(c)` означает конденсированную фазу в базе АСТРА.")
    add("")
    add("```")
    for start in range(0, len(unique_species), 5):
        row = unique_species[start:start + 5]
        add("  ".join(f"{item:<14}" for item in row).rstrip())
    add("```")
    add("")
    add("Сгенерировано `tools/extract_astra.py`.")
    add("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"записей: {len(species)}, уникальных: {len(unique_species)}")
    print(f"формул: {len(formulas)}, конденсированных: {len(condensed)}")
    print(f"элементов: {len(element_counter)}")
    print(f"наших покрыто: {covered} из {len(ours)}, нет у нас: {len(missing)}")
    print(f"записано: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
