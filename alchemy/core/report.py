"""Выгрузка расчётов в DOCX.

Отчёт собирается из результатов программы: заголовок, дата, таблица
величин, ход расчёта, предупреждения и источники. Формулы дублируются
в LaTeX — их можно скопировать в статью или пояснительную записку.

python-docx необязателен: без него программа работает, а экспорт
сообщает, что нужно установить.
"""

from __future__ import annotations

import datetime
import os

from . import latex as LX
from .errors import AlchemyError
from .results import Result


def _document():
    """Создать документ и настроить стили под тёмный текст на белом."""
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError as exc:  # pragma: no cover
        raise AlchemyError(
            "Для выгрузки в DOCX нужен пакет python-docx.\n"
            "Установите его:  python -m pip install python-docx"
        ) from exc

    document = Document()

    style = document.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    return document


def _add_heading(document, text: str, level: int = 1) -> None:
    from docx.shared import Pt

    heading = document.add_heading(text, level=level)
    for run in heading.runs:
        run.font.name = "Times New Roman"
    if level == 1:
        for run in heading.runs:
            run.font.size = Pt(16)


def _add_kv_table(document, rows: list[tuple[str, str]]) -> None:
    """Таблица «величина — значение»."""
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"

    for name, value in rows:
        cells = table.add_row().cells
        cells[0].text = str(name)
        cells[1].text = str(value)

        for paragraph in cells[0].paragraphs:
            for run in paragraph.runs:
                run.bold = True


def latex_of(result: Result, source: str = "") -> str:
    """LaTeX для результата, если он про уравнение или формулу.

    source — исходное уравнение или формула: вкладка знает его точно,
    а в самом результате его может не быть.
    """
    if source:
        return LX.to_latex(source)

    for key in ("equation", "formula", "reaction"):
        value = result.meta.get(key)
        if value:
            return LX.to_latex(value)

    label = result.label or ""
    # «Стандартная энтальпия реакции ΔH°...» — уравнения в метке нет,
    # поэтому берём значение, если оно похоже на уравнение
    if LX.looks_like_equation(label):
        return LX.to_latex(label)

    return ""


def export_result(path: str, result: Result, title: str = "",
                  source: str = "") -> str:
    """Сохранить один результат в DOCX. Возвращает путь к файлу."""
    document = _document()

    heading = title or result.label or "Результат расчёта"
    _add_heading(document, heading, level=1)

    stamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    paragraph = document.add_paragraph(f"Дата расчёта: {stamp}")
    paragraph.runs[0].italic = True

    # Основное значение
    _add_heading(document, "Результат", level=2)
    rows = [("Значение", result.formatted())]
    if result.method:
        rows.append(("Метод", result.method))
    if result.unit:
        rows.append(("Единица", result.unit))
    _add_kv_table(document, rows)

    # LaTeX
    snippet = latex_of(result, source=source)
    if snippet:
        _add_heading(document, "Запись в LaTeX", level=2)
        code = document.add_paragraph(snippet)
        code.runs[0].font.name = "Consolas"

    # Предупреждения
    if result.warnings:
        _add_heading(document, "Предупреждения", level=2)
        for warning in result.warnings:
            document.add_paragraph(str(warning), style="List Bullet")

    # Ход расчёта
    if result.steps:
        _add_heading(document, "Ход расчёта", level=2)
        for step in result.steps:
            text = str(step)
            if text.strip():
                document.add_paragraph(text)
            else:
                document.add_paragraph("")

    if result.assumptions:
        _add_heading(document, "Допущения", level=2)
        for assumption in result.assumptions:
            document.add_paragraph(str(assumption), style="List Bullet")

    if result.sources:
        _add_heading(document, "Источники данных", level=2)
        for source in result.sources:
            document.add_paragraph(str(source), style="List Bullet")

    document.save(path)
    return path


def export_journal(path: str, entries: list[dict],
                   title: str = "Протокол расчётов") -> str:
    """Сохранить журнал операций в DOCX. Возвращает путь к файлу."""
    document = _document()

    _add_heading(document, title, level=1)

    stamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    paragraph = document.add_paragraph(
        f"Составлено: {stamp}. Записей: {len(entries)}.")
    paragraph.runs[0].italic = True

    if not entries:
        document.add_paragraph("Журнал пуст.")
        document.save(path)
        return path

    # Сводная таблица
    _add_heading(document, "Сводная таблица", level=2)
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"

    header = table.rows[0].cells
    for index, name in enumerate(("Время", "Операция", "Результат")):
        header[index].text = name
        for paragraph in header[index].paragraphs:
            for run in paragraph.runs:
                run.bold = True

    for entry in entries:
        cells = table.add_row().cells
        cells[0].text = str(entry.get("time", ""))
        cells[1].text = str(entry.get("action", ""))
        cells[2].text = str(entry.get("result", ""))

    # Подробности по записям
    _add_heading(document, "Подробности", level=2)
    for number, entry in enumerate(entries, start=1):
        time_text = entry.get("time", "")
        action = entry.get("action", "")
        document.add_heading(f"{number}. {action} ({time_text})", level=3)

        detail = str(entry.get("detail", "")).strip()
        if detail:
            code = document.add_paragraph(detail)
            code.runs[0].font.name = "Consolas"

        for warning in entry.get("warnings", []) or []:
            document.add_paragraph(str(warning), style="List Bullet")

    document.save(path)
    return path


def suggested_name(prefix: str = "alchemy") -> str:
    """Имя файла по умолчанию."""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    return f"{prefix}_{stamp}.docx"


def available() -> bool:
    """Установлен ли python-docx."""
    try:
        import docx  # noqa: F401
    except ImportError:
        return False
    return True
