"""Teg namunalari va normallashtirish."""
import re

from ..core.models import TagClass

_LINE = r'\d+(?:\.\d+)?"-[A-Z]{1,4}-\d{3,5}-[A-Z0-9]{2,6}'
# ISA 5.1: o'lchanadigan kattalik harfi + 1–3 funksiya harfi
_INSTRUMENT = r"[PTFLA][ICTSVEGYHLRQA]{1,3}-\d{3,5}"
_EQUIPMENT = r"[A-Z]{1,3}-\d{3,4}[A-D]?"
_BEFORE, _AFTER = r"(?<![A-Z0-9\-])", r"(?![A-Z0-9\-])"

_LINE_RE = re.compile(rf'(?<![A-Z0-9\-."]){_LINE}{_AFTER}')
_INSTRUMENT_RE = re.compile(_BEFORE + _INSTRUMENT + _AFTER)
_EQUIPMENT_RE = re.compile(_BEFORE + _EQUIPMENT + _AFTER)
_LOOSE_RE = re.compile(r"^([A-Z]{1,4})-?(\d{3,5})([A-D]?)$")


def _clean(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").upper()).replace("″", '"').replace("”", '"').replace("''", '"')


def classify(tag: str) -> TagClass:
    if re.fullmatch(_LINE, tag):
        return TagClass.line
    if re.fullmatch(_INSTRUMENT, tag):
        return TagClass.instrument
    return TagClass.equipment


def normalize_tag(text: str) -> str | None:
    """Bitta katakdagi tegni kanonik ko'rinishga keltiradi: 'p-101 a' -> 'P-101A'."""
    s = _clean(text)
    if re.fullmatch(_LINE, s):
        return s
    m = _LOOSE_RE.match(s)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}{m.group(3)}"


def find_tags(text: str) -> list[tuple[str, TagClass]]:
    """Erkin matndan teglarni topadi (takrorlarsiz, uchrash tartibida)."""
    s = (text or "").upper().replace("″", '"').replace("”", '"')
    found: list[tuple[int, str, TagClass]] = []
    for regex, cls in ((_LINE_RE, TagClass.line), (_INSTRUMENT_RE, TagClass.instrument),
                       (_EQUIPMENT_RE, TagClass.equipment)):
        def take(m, cls=cls):
            found.append((m.start(), m.group(0), cls))
            return "\x00" * len(m.group(0))  # topilgan joyni keyingi namunalardan yashiradi
        s = regex.sub(take, s)
    out, seen = [], set()
    for _, tag, cls in sorted(found):
        if tag not in seen:
            seen.add(tag)
            out.append((tag, cls))
    return out
