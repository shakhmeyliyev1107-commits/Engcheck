"""Matnni qidiruv uchun ustma-ust bo'laklarga ajratish."""
import re


def chunk_pages(pages: list[tuple[int, str]], size: int = 900, overlap: int = 150) -> list[tuple[int, str]]:
    """[(sahifa, matn)] -> [(sahifa, bo'lak)]. Bo'lak so'z o'rtasidan kesilmaydi."""
    out: list[tuple[int, str]] = []
    for page_no, raw in pages:
        text = re.sub(r"[ \t]+", " ", raw or "").strip()
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                cut = text.rfind(" ", start + size // 2, end)
                end = cut if cut > start else end
            piece = text[start:end].strip()
            if piece:
                out.append((page_no, piece))
            if end >= len(text):
                break
            nxt = text.find(" ", max(end - overlap, start + 1))
            start = nxt + 1 if 0 <= nxt < end else end
    return out
