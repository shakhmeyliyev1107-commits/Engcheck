"""DXF: model fazosidagi TEXT, MTEXT va blok atributlari koordinatasi bilan."""
from pathlib import Path

import ezdxf

from ..model import Page, ParsedDocument, TextItem


def _loc(point) -> str:
    return f"x={round(float(point[0]), 2)},y={round(float(point[1]), 2)}"


def parse(path: Path) -> ParsedDocument:
    doc = ezdxf.readfile(str(path))
    items: list[TextItem] = []
    for e in doc.modelspace():
        kind = e.dxftype()
        if kind == "TEXT":
            text = e.dxf.text.strip()
            if text:
                items.append(TextItem(text, _loc(e.dxf.insert)))
        elif kind == "MTEXT":
            text = e.plain_text().strip()
            if text:
                items.append(TextItem(text, _loc(e.dxf.insert)))
        elif kind == "INSERT":
            attrs = {a.dxf.tag: a.dxf.text.strip() for a in e.attribs}
            if attrs:
                items.append(TextItem(e.dxf.name, _loc(e.dxf.insert), attrs))
    lines = []
    for i in items:
        lines.append(i.text if not i.attrs else
                     f"[{i.text}] " + "; ".join(f"{k}={v}" for k, v in i.attrs.items()))
    return ParsedDocument([Page(number=1, text="\n".join(lines), items=items)])
