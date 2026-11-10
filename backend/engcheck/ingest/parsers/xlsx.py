"""XLSX: har varaq bitta sahifa, to'ldirilgan diapazon bitta jadval."""
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from ..model import Cell, Page, ParsedDocument, Table

MAX_CELLS = 400_000  # bitta varaq uchun; undan katta jadval muhandislik ro'yxati emas


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
        # Faqat haqiqatan to'ldirilgan kataklar: uzoqdagi bo'sh/probelli katak diapazonni shishirmaydi.
        filled = {(c.row, c.column): text for c in ws._cells.values() if (text := _text(c.value))}
        max_row = max((r for r, _ in filled), default=0)
        max_col = max((c for _, c in filled), default=0)
        if max_row * max_col > MAX_CELLS:
            raise ValueError(f"varaq juda katta: {ws.title} ({max_row}×{max_col} katak)")
        rows = [[Cell(filled.get((r, c), ""), f"{ws.title}!{get_column_letter(c)}{r}")
                 for c in range(1, max_col + 1)] for r in range(1, max_row + 1)]
        text = "\n".join(" | ".join(c.text for c in row if c.text) for row in rows)
        pages.append(Page(number=n, text=text, tables=[Table(rows)]))
    return ParsedDocument(pages)
