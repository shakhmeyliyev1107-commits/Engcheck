"""DOCX: paragraflar va jadvallar. Sahifa tushunchasi yo'q, hammasi 1-sahifa."""
from pathlib import Path

import docx

from ..model import Cell, Page, ParsedDocument, Table, TextItem


def parse(path: Path) -> ParsedDocument:
    d = docx.Document(str(path))
    items = [TextItem(p.text.strip(), f"para{i}")
             for i, p in enumerate(d.paragraphs, start=1) if p.text.strip()]
    tables = []
    for ti, t in enumerate(d.tables, start=1):
        rows = [[Cell(c.text.strip(), f"table{ti}:r{ri}:c{ci}")
                 for ci, c in enumerate(row.cells, start=1)]
                for ri, row in enumerate(t.rows, start=1)]
        tables.append(Table(rows))
    lines = [i.text for i in items]
    for t in tables:
        lines += [" | ".join(c.text for c in row) for row in t.rows]
    return ParsedDocument([Page(number=1, text="\n".join(lines), tables=tables, items=items)])
