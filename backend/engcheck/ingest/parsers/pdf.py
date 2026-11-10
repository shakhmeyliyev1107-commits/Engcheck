"""PDF: matn va jadvallar (pdfplumber). Skanerlangan PDF qo'llab-quvvatlanmaydi."""
from pathlib import Path

import pdfplumber

from ..model import Cell, Page, ParsedDocument, Table


def parse(path: Path) -> ParsedDocument:
    pages: list[Page] = []
    with pdfplumber.open(path) as pdf:
        for i, p in enumerate(pdf.pages, start=1):
            tables = []
            for ti, raw in enumerate(p.extract_tables(), start=1):
                rows = [[Cell((c or "").strip(), f"t{ti}:r{ri}:c{ci}")
                         for ci, c in enumerate(row, start=1)]
                        for ri, row in enumerate(raw, start=1)]
                tables.append(Table(rows))
            pages.append(Page(number=i, text=p.extract_text() or "", tables=tables))
    return ParsedDocument(pages)
