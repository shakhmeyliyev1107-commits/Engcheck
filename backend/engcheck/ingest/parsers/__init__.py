"""Formatni aniqlab, mos parserga uzatadi."""
from pathlib import Path

from ..detect import detect_format
from ..model import ParsedDocument


class ParseError(Exception):
    """code: unsupported_dwg | unknown_format | corrupt | needs_ocr"""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def parse_file(path: Path) -> ParsedDocument:
    from . import docx, dxf, pdf, xlsx

    path = Path(path)
    if path.stat().st_size == 0:
        raise ParseError("corrupt", "fayl bo'sh")
    fmt = detect_format(path)
    if fmt == "dwg":
        raise ParseError("unsupported_dwg")
    parser = {"pdf": pdf.parse, "xlsx": xlsx.parse, "docx": docx.parse, "dxf": dxf.parse}.get(fmt)
    if parser is None:
        raise ParseError("unknown_format")
    try:
        doc = parser(path)
    except Exception as exc:  # kutubxonalar turli istisnolar tashlaydi; hammasi "buzilgan fayl"
        raise ParseError("corrupt", f"{type(exc).__name__}: {exc}") from exc
    if fmt == "pdf" and not any(p.text.strip() for p in doc.pages):
        raise ParseError("needs_ocr")
    return doc
