"""Loyihaga ulangan hujjatlar papkasi: skanerlash va fayl yo'lini xavfsiz aniqlash.

Papka — shu kompyuterdagi yoki tarmoqdagi (\\\\server\\share, ulangan disk) katalog. Bulut manzillari (URL)
qo'llab-quvvatlanmaydi: bulut papkasi kompyuterga sinxronlangan bo'lsa, uning lokal yo'li ishlatiladi.
"""
import os
from pathlib import Path

SUPPORTED = (".pdf", ".docx", ".xlsx", ".dxf")
UNSUPPORTED_KNOWN = (".dwg",)          # ro'yxatda ko'rsatiladi, lekin yuklanmaydi (DXF ga o'tkazish kerak)
MAX_FILES = 2000
MAX_SIZE = 200 * 1024 * 1024


class FolderError(Exception):
    """code: folder_is_url | folder_not_absolute | folder_not_found | folder_unreadable"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def resolve(text: str) -> Path:
    text = (text or "").strip().strip('"')
    if "://" in text:
        raise FolderError("folder_is_url")
    path = Path(text).expanduser()
    if not text or not path.is_absolute():
        raise FolderError("folder_not_absolute")
    try:
        if not path.is_dir():
            raise FolderError("folder_not_found")
        next(os.scandir(path), None)
    except OSError as exc:
        raise FolderError("folder_unreadable") from exc
    return path


def scan(root: Path) -> tuple[list[dict], bool]:
    """([{path, size, supported}], kesilganmi). Yashirin kataloglar, havolalar va Office vaqtinchalik fayllari o'tkazib yuboriladi."""
    found, truncated = [], False
    try:
        for current, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith((".", "$", "~")) and not os.path.islink(os.path.join(current, d)))
            for name in sorted(files):
                suffix = os.path.splitext(name)[1].lower()
                full = os.path.join(current, name)
                if name.startswith(("~$", ".")) or suffix not in SUPPORTED + UNSUPPORTED_KNOWN or os.path.islink(full):
                    continue
                if len(found) >= MAX_FILES:
                    return found, True
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                found.append({"path": Path(full).relative_to(root).as_posix(), "size": size, "supported": suffix in SUPPORTED})
    except OSError as exc:
        raise FolderError("folder_unreadable") from exc
    return found, truncated


def locate(root: Path, relative: str) -> Path | None:
    """Papka ichidagi faylning to'liq yo'li; papkadan tashqariga chiqadigan yoki havola bo'lgan yo'l uchun None."""
    try:
        candidate = root / relative
        if Path(relative).is_absolute() or candidate.is_symlink() or not candidate.is_file():
            return None
        real, real_root = candidate.resolve(), root.resolve()
        if not real.is_relative_to(real_root) or real.suffix.lower() not in SUPPORTED:
            return None
        return real
    except (OSError, ValueError):
        return None
