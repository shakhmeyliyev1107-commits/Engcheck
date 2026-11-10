"""Fayl formatini imzo (ustun) va kengaytma bo'yicha aniqlash."""
import zipfile
from pathlib import Path


def detect_format(path: Path) -> str:
    """'pdf' | 'xlsx' | 'docx' | 'dxf' | 'dwg' | 'unknown'."""
    path = Path(path)
    with open(path, "rb") as f:
        head = f.read(4096)
    ext = path.suffix.lower()
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"AC10"):
        return "dwg"
    if head.startswith(b"PK"):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
        except (zipfile.BadZipFile, OSError):
            return ext.lstrip(".") if ext in (".xlsx", ".docx") else "unknown"
        if any(n.startswith("xl/") for n in names):
            return "xlsx"
        if any(n.startswith("word/") for n in names):
            return "docx"
        return "unknown"
    text = head.decode("latin-1", errors="replace")
    if "SECTION" in text and ("HEADER" in text or "ENTITIES" in text or "CLASSES" in text):
        return "dxf"
    if ext in (".pdf", ".xlsx", ".docx", ".dxf", ".dwg"):
        return ext.lstrip(".")
    return "unknown"
