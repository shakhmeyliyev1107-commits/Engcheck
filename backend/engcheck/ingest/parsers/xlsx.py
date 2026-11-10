"""XLSX: har varaq bitta sahifa, ishlatilgan diapazon bitta jadval."""
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from ..model import Cell, Page, ParsedDocument, Table


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse(path: Path) -> ParsedDocument:
    wb = openpyxl.load_workbook(path, data_only=True)
    pages = []
    for n, ws in enumerate(wb.worksheets, start=1):
        rows = []
        for r in range(1, ws.max_row + 1):
            rows.append([Cell(_text(ws.cell(r, c).value), f"{ws.title}!{get_column_letter(c)}{r}")
                         for c in range(1, ws.max_column + 1)])
        text = "\n".join(" | ".join(c.text for c in row if c.text) for row in rows)
        pages.append(Page(number=n, text=text, tables=[Table(rows)]))
    return ParsedDocument(pages)
