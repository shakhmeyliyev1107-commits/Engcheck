"""Teg namunalari va normallashtirish."""
import re

from ..core.models import TagClass

_SIZE = r"(?:\d+-\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
_LINE = _SIZE + r'"-[A-Z]{1,4}-\d{3,5}-[A-Z0-9]{2,6}(?:-[A-Z0-9]{1,4})?'
# ISA 5.1: o'lchanadigan kattalik harfi + 1–3 funksiya harfi (klapanlar ham: XV, HV, SDV)
_INSTRUMENT = r"[PTFLAXHSZ][ICTSVEGYHLRQADOWZ]{1,3}-\d{3,5}"
_EQUIPMENT = r"[A-Z]{1,3}-\d{3,4}(?:[A-D](?:/[A-D])*)?"
_BEFORE, _AFTER = r"(?<![A-Z0-9\-])", r"(?![A-Z0-9\-])"

_LINE_RE = re.compile(rf'(?<![A-Z0-9\-."/]){_LINE}{_AFTER}')
_INSTRUMENT_RE = re.compile(_BEFORE + _INSTRUMENT + _AFTER)
_EQUIPMENT_RE = re.compile(_BEFORE + _EQUIPMENT + _AFTER)
_LOOSE_RE = re.compile(r"^(?:(\d{1,3})-)?([A-Z]{1,4})-?(\d{3,5})((?:[A-D](?:/[A-D])*)?)$")
_MIXED_FRACTION_RE = re.compile(r'(\d+)\s+(\d+/\d+")')
_PREFIX_RE = re.compile(r"^(?:\d{1,3}-)?([A-Z]{1,4})-")

# Lotin harfiga o'xshash kirill harflari, turli chiziqcha va qo'shtirnoqlar
_CHARS = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "Х": "X", "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    "″": '"', "”": '"', "“": '"',
})


def _canon_text(text: str) -> str:
    s = (text or "").upper().translate(_CHARS).replace("''", '"')
    return _MIXED_FRACTION_RE.sub(r"\1-\2", s)


def classify(tag: str) -> TagClass:
    if re.fullmatch(_LINE, tag):
        return TagClass.line
    if re.fullmatch(_INSTRUMENT, tag):
        return TagClass.instrument
    return TagClass.equipment


def tag_prefix(tag: str) -> str | None:
    """Uskuna tegining harfli prefiksi: 'P-101A' -> 'P', '10-P-101A' -> 'P'."""
    m = _PREFIX_RE.match(tag)
    return m.group(1) if m else None


def _expand(letters: str, digits: str, suffixes: str, unit: str | None = None) -> list[str]:
    head = f"{unit}-{letters}-{digits}" if unit else f"{letters}-{digits}"
    return [head + s for s in suffixes.split("/")] if suffixes else [head]


def _one(part: str) -> list[str]:
    s = re.sub(r"\s+", "", part)
    if re.fullmatch(_LINE, s):
        return [s]
    m = _LOOSE_RE.match(s)
    return _expand(m.group(2), m.group(3), m.group(4), m.group(1)) if m else []


def normalize_tags(text: str) -> list[str]:
    """Bitta katakdagi teg(lar)ni kanonik ko'rinishga keltiradi.

    'p-101 a' -> ['P-101A'];  'P-101A/B' -> ['P-101A', 'P-101B'];  tanilmasa [].
    """
    s = re.sub(r"\([^)]*\)", " ", _canon_text(text)).strip()
    if not s:
        return []
    whole = _one(s)
    if whole:
        return whole
    parts = [p for p in re.split(r"[,;&]|\s+/\s+", s) if p.strip()]
    if len(parts) < 2:
        return []
    out: list[str] = []
    for part in parts:
        tags = _one(part)
        if not tags:
            return []
        out += [t for t in tags if t not in out]
    return out


def normalize_tag(text: str) -> str | None:
    tags = normalize_tags(text)
    return tags[0] if len(tags) == 1 else None


def find_tags(text: str) -> list[tuple[str, TagClass]]:
    """Erkin matndan teglarni topadi (takrorlarsiz, uchrash tartibida)."""
    s = _canon_text(text)
    found: list[tuple[int, str, TagClass]] = []
    for regex, cls in ((_LINE_RE, TagClass.line), (_INSTRUMENT_RE, TagClass.instrument),
                       (_EQUIPMENT_RE, TagClass.equipment)):
        def take(m, cls=cls):
            found.append((m.start(), m.group(0), cls))
            return "\x00" * len(m.group(0))  # topilgan joyni keyingi namunalardan yashiradi
        s = regex.sub(take, s)
    out, seen = [], set()
    for _, raw, cls in sorted(found):
        for tag in (normalize_tags(raw) if cls == TagClass.equipment else [raw]):
            if tag not in seen:
                seen.add(tag)
                out.append((tag, cls))
    return out
