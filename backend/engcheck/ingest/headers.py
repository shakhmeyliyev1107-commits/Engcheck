"""Sarlavha lug'ati: ustun/qator nomini parametrga bog'laydi (uz/en/ru)."""
import re

_SYNONYMS: dict[str, list[str]] = {
    "tag": ["tag", "tag no", "tag number", "item", "item no", "equipment no", "equipment tag",
            "equipment number", "line no", "line number", "teg", "teg raqami", "pozitsiya",
            "liniya raqami", "тег", "позиция", "поз", "номер линии", "номер позиции"],
    "design_pressure": ["design pressure", "design press", "des press", "loyiha bosimi",
                        "hisobiy bosim", "расчетное давление", "расчётное давление"],
    "operating_pressure": ["operating pressure", "oper pressure", "op pressure", "working pressure",
                           "ish bosimi", "ishchi bosim", "рабочее давление"],
    "design_temperature": ["design temperature", "design temp", "des temp", "loyiha harorati",
                           "hisobiy harorat", "расчетная температура", "расчётная температура"],
    "operating_temperature": ["operating temperature", "oper temperature", "op temperature",
                              "working temperature", "ish harorati", "ishchi harorat",
                              "рабочая температура"],
    "material": ["material", "material of construction", "moc", "materiali", "материал"],
    "pipe_class": ["pipe class", "piping class", "line class", "pipe spec", "quvur sinfi",
                   "класс трубопровода", "класс трубы"],
    "size": ["size", "nominal size", "line size", "diameter", "nps", "dn", "o'lcham", "diametr",
             "диаметр", "размер"],
    "fluid": ["fluid", "service", "medium", "muhit", "среда"],
    "flow_rate": ["flow rate", "flow", "capacity", "rated flow", "sarf", "unumdorlik", "расход",
                  "производительность"],
    "power": ["power", "motor power", "rated power", "quvvat", "dvigatel quvvati", "мощность"],
    "revision": ["revision", "rev", "reviziya", "ревизия"],
    "doc_number": ["document no", "doc no", "document number", "hujjat raqami", "номер документа"],
}
_LOOKUP = {syn: param for param, syns in _SYNONYMS.items() for syn in syns}
# Sarlavhaning o'zi birlikni bildiradi: "DN" ustunidagi 150 -> 150 mm
_IMPLIED_UNIT = {"dn": "DN", "nps": "NPS"}
_UNIT_RE = re.compile(r"^(.*?)\s*(?:,\s*([^,]+)|\(([^)]*)\)|\[([^\]]*)\])\s*$")


def _norm(name: str) -> str:
    s = name.lower().replace("_", " ").replace("’", "'").replace("ʻ", "'").replace("`", "'")
    s = re.sub(r"[.:№#]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def match_header(text: str) -> tuple[str, str | None] | None:
    """(parametr, birlik) yoki mos kelmasa None."""
    raw = re.sub(r"\s+", " ", (text or "")).strip()
    if not raw:
        return None
    param = _LOOKUP.get(_norm(raw))
    if param:
        return param, _IMPLIED_UNIT.get(_norm(raw))
    m = _UNIT_RE.match(raw)
    if m:
        param = _LOOKUP.get(_norm(m.group(1)))
        unit = next((g for g in m.groups()[1:] if g), None)
        if param:
            return param, (unit.strip() if unit and unit.strip() else None)
    return None
